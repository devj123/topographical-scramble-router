"""Interactive, any-angle terrain route explorer for projected DEM rasters.

This is a planning/visualization prototype, not a navigation or mountaineering
safety system. Always use current maps, forecasts, local guidance, and qualified
human judgment in the field.
"""

from __future__ import annotations

import argparse
import heapq
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource
except ImportError:
    plt = None
    LightSource = None

try:
    import rasterio
except ImportError:
    rasterio = None


@dataclass(frozen=True)
class RouterConfig:
    """Routing preferences. Gradients are in degrees; costs are seconds/metres."""

    preferred_min_slope: float = 12.0
    preferred_max_slope: float = 38.0
    impassable_slope: float = 50.0
    flat_penalty: float = 9.0
    steep_penalty: float = 14.0
    cost_model: str = "scramble"

    def __post_init__(self) -> None:
        if not 0 <= self.preferred_min_slope < self.preferred_max_slope < self.impassable_slope < 90:
            raise ValueError("Require 0 <= scramble-min < scramble-max < max-slope < 90.")
        if self.flat_penalty < 0 or self.steep_penalty < 0:
            raise ValueError("Slope penalties must be non-negative.")
        if self.cost_model not in {"scramble", "tobler"}:
            raise ValueError("cost_model must be 'scramble' or 'tobler'.")


@dataclass
class Terrain:
    elevation: np.ndarray
    x_resolution_m: float
    y_resolution_m: float
    name: str = "terrain"

    def __post_init__(self) -> None:
        self.elevation = np.asarray(self.elevation, dtype=float)
        if self.elevation.ndim != 2:
            raise ValueError("Elevation data must be a two-dimensional array.")
        if self.x_resolution_m <= 0 or self.y_resolution_m <= 0:
            raise ValueError("Pixel resolutions must be positive metres.")


def load_geotiff(path: Path, band: int = 1, max_dimension: int = 900) -> Terrain:
    """Load a projected metric DEM and downsample oversized rasters for interaction."""
    if rasterio is None:
        raise RuntimeError("rasterio is required to load GeoTIFF files. Install requirements.txt.")
    with rasterio.open(path) as src:
        if src.crs is None or not src.crs.is_projected:
            raise ValueError("Use a DEM in a projected CRS with metre-like horizontal units.")
        scale = min(1.0, max_dimension / max(src.width, src.height))
        out_h, out_w = max(2, round(src.height * scale)), max(2, round(src.width * scale))
        elevation = src.read(band, out_shape=(out_h, out_w), masked=True).filled(np.nan).astype(float)
        transform = src.transform * src.transform.scale(src.width / out_w, src.height / out_h)
        return Terrain(elevation, abs(transform.a), abs(transform.e), path.name)


def synthetic_mountain(size: int = 320) -> Terrain:
    """A deterministic demo surface with a summit, ridges, and a cliff-like band."""
    y, x = np.mgrid[-1:1:complex(size), -1:1:complex(size)]
    summit = 2100 * np.exp(-3.2 * (x * x + y * y))
    ridge = 360 * np.exp(-36 * (y - 0.34 * x + 0.08) ** 2) * (1 - 0.35 * x)
    gully = -300 * np.exp(-70 * (x + 0.40) ** 2 - 10 * (y - 0.1) ** 2)
    texture = 28 * np.sin(16 * x + 6 * y) * np.cos(12 * y)
    return Terrain(900 + summit + ridge + gully + texture, 20.0, 20.0, "synthetic mountain")


class AStarRouter:
    """Theta* router with precomputed directional edge costs."""

    steps = tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc)

    def __init__(self, terrain: Terrain, config: RouterConfig) -> None:
        self.terrain, self.config = terrain, config
        self.rows, self.cols = terrain.elevation.shape
        self.valid = np.isfinite(terrain.elevation)
        self.step_index = {step: index for index, step in enumerate(self.steps)}
        self.directional_costs = self._precompute_costs()

    def _precompute_costs(self) -> np.ndarray:
        """Vectorize all eight directed cost surfaces once per fixed DEM."""
        costs = np.full((len(self.steps), self.rows, self.cols), np.inf, dtype=float)
        z, c = self.terrain.elevation, self.config
        for index, (dr, dc) in enumerate(self.steps):
            source_rows = slice(max(0, -dr), self.rows - max(0, dr))
            source_cols = slice(max(0, -dc), self.cols - max(0, dc))
            target_rows = slice(max(0, dr), self.rows - max(0, -dr))
            target_cols = slice(max(0, dc), self.cols - max(0, -dc))
            source = z[source_rows, source_cols]
            target = z[target_rows, target_cols]
            horizontal = math.hypot(dc * self.terrain.x_resolution_m, dr * self.terrain.y_resolution_m)
            signed_grade = (target - source) / horizontal
            slope = np.degrees(np.arctan(np.abs(signed_grade)))
            below = np.maximum(0.0, c.preferred_min_slope - slope) / max(c.preferred_min_slope, 0.1)
            above = np.maximum(0.0, slope - c.preferred_max_slope) / (c.impassable_slope - c.preferred_max_slope)
            if c.cost_model == "tobler":
                # Tobler: 6 * exp(-3.5 * abs(grade + 0.05)) km/h; it naturally
                # distinguishes ascent from descent and yields travel time in seconds.
                speed_mps = (6_000 / 3_600) * np.exp(-3.5 * np.abs(signed_grade + 0.05))
                edge = horizontal / speed_mps
            else:
                # Scramble preference adds an explicitly asymmetric effort term:
                # ascending is costlier, while extremely steep descents also grow costly.
                ascent = np.maximum(signed_grade, 0.0)
                descent = np.maximum(-signed_grade, 0.0)
                edge = horizontal * (1 + c.flat_penalty * below**2 + c.steep_penalty * above**2)
                edge *= 1 + 1.8 * ascent + 0.8 * descent
            usable = np.isfinite(source) & np.isfinite(target) & (slope < c.impassable_slope)
            costs[index, source_rows, source_cols] = np.where(usable, edge, np.inf)
        return costs

    def _edge_cost(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        dr, dc = b[0] - a[0], b[1] - a[1]
        index = self.step_index.get((dr, dc))
        return math.inf if index is None else float(self.directional_costs[index, a[0], a[1]])

    def _heuristic(self, point: tuple[int, int], goal: tuple[int, int]) -> float:
        # Optimistic base distance (or 0.6 sec/m for Tobler) remains a lower bound.
        distance = math.hypot((point[0] - goal[0]) * self.terrain.y_resolution_m,
                              (point[1] - goal[1]) * self.terrain.x_resolution_m)
        return distance * (0.6 if self.config.cost_model == "tobler" else 1.0)

    @staticmethod
    def _bresenham(a: tuple[int, int], b: tuple[int, int]):
        """Yield a cell-to-cell raster line (inclusive), suitable for Theta* LOS."""
        r0, c0 = a
        r1, c1 = b
        dr, dc = abs(r1 - r0), abs(c1 - c0)
        sr, sc = (1 if r0 < r1 else -1), (1 if c0 < c1 else -1)
        err = dr - dc
        while True:
            yield r0, c0
            if (r0, c0) == (r1, c1):
                return
            twice = 2 * err
            if twice > -dc:
                err -= dc
                r0 += sr
            if twice < dr:
                err += dr
                c0 += sc

    def _line_cost(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        cells = list(self._bresenham(a, b))
        if len(cells) == 1:
            return 0.0
        total = 0.0
        for origin, target in zip(cells, cells[1:]):
            edge = self._edge_cost(origin, target)
            if not math.isfinite(edge):
                return math.inf
            total += edge
        return total

    def _valid_point(self, point: tuple[int, int], name: str) -> None:
        r, c = point
        if not (0 <= r < self.rows and 0 <= c < self.cols and self.valid[r, c]):
            raise ValueError(f"{name} must be a valid raster cell")

    def route(self, start: tuple[int, int], goal: tuple[int, int]) -> tuple[list[tuple[int, int]], float]:
        """Find an any-angle path using Theta* parent line-of-sight relaxation."""
        self._valid_point(start, "start")
        self._valid_point(goal, "goal")
        queue = [(self._heuristic(start, goal), 0.0, start)]
        parent: dict[tuple[int, int], tuple[int, int]] = {start: start}
        cost = {start: 0.0}
        closed: set[tuple[int, int]] = set()
        while queue:
            _, current_cost, current = heapq.heappop(queue)
            if current in closed or current_cost != cost.get(current):
                continue
            if current == goal:
                path = [current]
                while path[-1] != start:
                    path.append(parent[path[-1]])
                return list(reversed(path)), current_cost
            closed.add(current)
            for dr, dc in self.steps:
                nxt = current[0] + dr, current[1] + dc
                if not (0 <= nxt[0] < self.rows and 0 <= nxt[1] < self.cols and self.valid[nxt]) or nxt in closed:
                    continue
                # Theta*: try the current node's parent first. A finite raster-line
                # cost means every sampled edge is traversable, so LOS is clear.
                ancestor = parent[current]
                via_ancestor = self._line_cost(ancestor, nxt)
                if math.isfinite(via_ancestor):
                    candidate_parent, new_cost = ancestor, cost[ancestor] + via_ancestor
                else:
                    edge = self._edge_cost(current, nxt)
                    candidate_parent, new_cost = current, current_cost + edge
                if new_cost < cost.get(nxt, math.inf):
                    cost[nxt], parent[nxt] = new_cost, candidate_parent
                    heapq.heappush(queue, (new_cost + self._heuristic(nxt, goal), new_cost, nxt))
        return [], math.inf


def route_stats(terrain: Terrain, path: list[tuple[int, int]]) -> tuple[float, float, float, float]:
    """Return horizontal distance metres, gain m, loss m, and Naismith hours."""
    distance = gain = loss = 0.0
    for a, b in zip(path, path[1:]):
        distance += math.hypot((b[1] - a[1]) * terrain.x_resolution_m, (b[0] - a[0]) * terrain.y_resolution_m)
        change = terrain.elevation[b] - terrain.elevation[a]
        gain += max(change, 0.0)
        loss += max(-change, 0.0)
    return distance, gain, loss, distance / 5_000 + gain / 600


class InteractiveMap:
    def __init__(self, router: AStarRouter, summit: tuple[int, int]) -> None:
        if plt is None or LightSource is None:
            raise RuntimeError("matplotlib is required for the interactive map. Install requirements.txt.")
        self.router, self.goal = router, summit
        self.start: tuple[int, int] | None = None
        self.waypoints: list[tuple[int, int]] = []
        self.artists: list = []
        self.figure, self.ax = plt.subplots(figsize=(10, 8), layout="constrained")
        self._draw_base()
        self.figure.canvas.mpl_connect("button_press_event", self._click)

    def _draw_base(self) -> None:
        terrain = self.router.terrain
        z = terrain.elevation
        hillshade = LightSource(azdeg=315, altdeg=45).shade(z, cmap=plt.get_cmap("terrain"), blend_mode="overlay")
        self.ax.imshow(hillshade, origin="upper")
        self.ax.contour(z, levels=np.linspace(np.nanmin(z), np.nanmax(z), 22), colors="black", linewidths=0.35, alpha=0.45)
        self.artists.append(self.ax.plot(self.goal[1], self.goal[0], "y*", ms=13, mec="black", label="goal")[0])
        self._set_title("Left-click start • Shift+left-click waypoint • Right-click goal")
        self.ax.set_xlabel("raster column")
        self.ax.set_ylabel("raster row")
        self.ax.legend(loc="upper right")

    def _set_title(self, text: str) -> None:
        self.ax.set_title(f"{self.router.terrain.name}: {text}")

    def _clear_route_artists(self) -> None:
        for artist in self.artists[1:]:
            artist.remove()
        self.artists = self.artists[:1]

    def _route_all_legs(self) -> tuple[list[tuple[int, int]], float]:
        if self.start is None:
            return [], 0.0
        stops = [self.start, *self.waypoints, self.goal]
        complete: list[tuple[int, int]] = []
        total_cost = 0.0
        for a, b in zip(stops, stops[1:]):
            leg, cost = self.router.route(a, b)
            if not leg:
                return [], math.inf
            complete.extend(leg if not complete else leg[1:])
            total_cost += cost
        return complete, total_cost

    def _render_route(self) -> None:
        self._clear_route_artists()
        if self.start is None:
            self._set_title("Left-click start • Shift+left-click waypoint • Right-click goal")
            return
        self.artists.append(self.ax.plot(self.start[1], self.start[0], "wo", ms=6, mec="black", label="start")[0])
        if self.waypoints:
            points = np.asarray(self.waypoints)
            self.artists.append(self.ax.plot(points[:, 1], points[:, 0], "co", ms=5, mec="black", label="waypoint")[0])
        path, cost = self._route_all_legs()
        if path:
            points = np.asarray(path)
            self.artists.append(self.ax.plot(points[:, 1], points[:, 0], color="magenta", lw=2.3, label="Theta* route")[0])
            distance, gain, loss, hours = route_stats(self.router.terrain, path)
            self._set_title(f"{distance / 1000:.2f} km • +{gain:.0f}/-{loss:.0f} m • Naismith {hours:.1f} h • cost {cost:.0f}")
        else:
            self._set_title("No route through permitted slope cells")
        self.ax.legend(loc="upper right")

    def _click(self, event) -> None:
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            return
        point = round(event.ydata), round(event.xdata)
        try:
            self.router._valid_point(point, "selected point")
            if event.button == 3:
                self.goal = point
                self.artists[0].set_data([point[1]], [point[0]])
            elif event.button == 1 and event.key == "shift":
                self.waypoints.append(point)
            elif event.button == 1:
                self.start, self.waypoints = point, []
            else:
                return
            self._render_route()
        except ValueError as exc:
            self._set_title(str(exc))
        self.figure.canvas.draw_idle()

    def show(self) -> None:
        plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description="Explore Theta* terrain routes over a DEM.")
    parser.add_argument("dem", nargs="?", type=Path, help="Projected DEM GeoTIFF (optional; synthetic demo if omitted)")
    parser.add_argument("--band", type=int, default=1, help="GeoTIFF band containing elevation")
    parser.add_argument("--max-slope", type=float, default=50.0, help="Slope cutoff in degrees")
    parser.add_argument("--scramble-min", type=float, default=12.0, help="Preferred minimum slope in degrees")
    parser.add_argument("--scramble-max", type=float, default=38.0, help="Preferred maximum slope in degrees")
    parser.add_argument("--cost-model", choices=("scramble", "tobler"), default="scramble", help="Directed traversal-cost model")
    args = parser.parse_args()
    terrain = load_geotiff(args.dem, args.band) if args.dem else synthetic_mountain()
    config = RouterConfig(args.scramble_min, args.scramble_max, args.max_slope, cost_model=args.cost_model)
    router = AStarRouter(terrain, config)
    summit = tuple(np.unravel_index(np.nanargmax(terrain.elevation), terrain.elevation.shape))
    InteractiveMap(router, summit).show()


if __name__ == "__main__":
    main()
