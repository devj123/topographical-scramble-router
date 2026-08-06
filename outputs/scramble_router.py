"""Interactive terrain-cost route explorer for DEM rasters.

This is a planning/visualization prototype, not a navigation or mountaineering
safety system. Always use current maps, forecasts, local land-manager guidance,
and qualified human judgment in the field.
"""

from __future__ import annotations

import argparse
import heapq
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

try:
    import rasterio
except ImportError:  # Lets the synthetic demo run without rasterio.
    rasterio = None


@dataclass(frozen=True)
class RouterConfig:
    """Terrain preference settings. Slopes are measured in degrees."""

    preferred_min_slope: float = 12.0
    preferred_max_slope: float = 38.0
    impassable_slope: float = 50.0
    flat_penalty: float = 9.0
    steep_penalty: float = 14.0


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
    """Load a projected metric DEM, optionally downsampling for interaction."""
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
    """A deterministic demo surface with a summit, ridges, and a cliff band."""
    y, x = np.mgrid[-1:1:complex(size), -1:1:complex(size)]
    summit = 2100 * np.exp(-3.2 * (x * x + y * y))
    ridge = 360 * np.exp(-36 * (y - 0.34 * x + 0.08) ** 2) * (1 - 0.35 * x)
    gully = -300 * np.exp(-70 * (x + 0.40) ** 2 - 10 * (y - 0.1) ** 2)
    texture = 28 * np.sin(16 * x + 6 * y) * np.cos(12 * y)
    return Terrain(900 + summit + ridge + gully + texture, 20.0, 20.0, "synthetic mountain")


class AStarRouter:
    def __init__(self, terrain: Terrain, config: RouterConfig) -> None:
        self.terrain, self.config = terrain, config
        self.rows, self.cols = terrain.elevation.shape
        self.valid = np.isfinite(terrain.elevation)
        self.steps = tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc)

    def _edge_cost(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        ar, ac = a
        br, bc = b
        horizontal = math.hypot((bc - ac) * self.terrain.x_resolution_m, (br - ar) * self.terrain.y_resolution_m)
        rise = abs(self.terrain.elevation[br, bc] - self.terrain.elevation[ar, ac])
        slope = math.degrees(math.atan2(rise, horizontal))
        c = self.config
        if slope >= c.impassable_slope:
            return math.inf
        # Distance is the base cost. The extra terms express a *scramble-style*
        # preference, not a safety rating: flatter terrain is deliberately less
        # desirable and slopes approaching the cutoff become increasingly costly.
        below = max(0.0, c.preferred_min_slope - slope) / max(c.preferred_min_slope, 0.1)
        above = max(0.0, slope - c.preferred_max_slope) / max(c.impassable_slope - c.preferred_max_slope, 0.1)
        return horizontal * (1.0 + c.flat_penalty * below**2 + c.steep_penalty * above**2)

    def _heuristic(self, point: tuple[int, int], goal: tuple[int, int]) -> float:
        dr, dc = point[0] - goal[0], point[1] - goal[1]
        return math.hypot(dr * self.terrain.y_resolution_m, dc * self.terrain.x_resolution_m)

    def route(self, start: tuple[int, int], goal: tuple[int, int]) -> tuple[list[tuple[int, int]], float]:
        for point, name in ((start, "start"), (goal, "goal")):
            r, c = point
            if not (0 <= r < self.rows and 0 <= c < self.cols and self.valid[r, c]):
                raise ValueError(f"{name} must be a valid raster cell")
        queue = [(self._heuristic(start, goal), 0.0, start)]
        parent: dict[tuple[int, int], tuple[int, int]] = {}
        cost = {start: 0.0}
        while queue:
            _, current_cost, current = heapq.heappop(queue)
            if current_cost != cost.get(current):
                continue
            if current == goal:
                path = [current]
                while current in parent:
                    current = parent[current]
                    path.append(current)
                return list(reversed(path)), current_cost
            for dr, dc in self.steps:
                nxt = current[0] + dr, current[1] + dc
                if not (0 <= nxt[0] < self.rows and 0 <= nxt[1] < self.cols and self.valid[nxt]):
                    continue
                edge = self._edge_cost(current, nxt)
                new_cost = current_cost + edge
                if new_cost < cost.get(nxt, math.inf):
                    cost[nxt], parent[nxt] = new_cost, current
                    heapq.heappush(queue, (new_cost + self._heuristic(nxt, goal), new_cost, nxt))
        return [], math.inf


class InteractiveMap:
    def __init__(self, router: AStarRouter, summit: tuple[int, int]) -> None:
        if plt is None:
            raise RuntimeError("matplotlib is required for the interactive map. Install requirements.txt.")
        self.router, self.summit = router, summit
        self.path_line = None
        self.start_marker = None
        self.figure, self.ax = plt.subplots(figsize=(10, 8), layout="constrained")
        self._draw_base()
        self.figure.canvas.mpl_connect("button_press_event", self._click)

    def _draw_base(self) -> None:
        terrain = self.router.terrain
        z = terrain.elevation
        self.ax.imshow(z, cmap="terrain", origin="upper")
        levels = np.linspace(np.nanmin(z), np.nanmax(z), 22)
        self.ax.contour(z, levels=levels, colors="black", linewidths=0.35, alpha=0.45)
        self.ax.plot(self.summit[1], self.summit[0], "y*", ms=13, mec="black", label="summit")
        self.ax.set_title(f"{terrain.name}: click a start cell to calculate an A* route")
        self.ax.set_xlabel("raster column")
        self.ax.set_ylabel("raster row")
        self.ax.legend(loc="upper right")

    def _click(self, event) -> None:
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            return
        start = round(event.ydata), round(event.xdata)
        try:
            path, cost = self.router.route(start, self.summit)
        except ValueError as exc:
            self.ax.set_title(str(exc))
            self.figure.canvas.draw_idle()
            return
        if self.path_line:
            self.path_line.remove()
        if self.start_marker:
            self.start_marker.remove()
        self.start_marker = self.ax.plot(start[1], start[0], "wo", ms=6, mec="black", label="start")[0]
        if path:
            points = np.asarray(path)
            self.path_line = self.ax.plot(points[:, 1], points[:, 0], color="magenta", lw=2.3, label="A* route")[0]
            self.ax.set_title(f"Route found — terrain objective cost: {cost:,.0f}. Click elsewhere to reroute.")
        else:
            self.ax.set_title("No route through permitted slope cells. Click elsewhere to reroute.")
        self.ax.legend(loc="upper right")
        self.figure.canvas.draw_idle()

    def show(self) -> None:
        plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description="Explore A* terrain routes over a DEM.")
    parser.add_argument("dem", nargs="?", type=Path, help="Projected DEM GeoTIFF (optional; synthetic demo if omitted)")
    parser.add_argument("--band", type=int, default=1, help="GeoTIFF band containing elevation")
    parser.add_argument("--max-slope", type=float, default=50.0, help="Slope cutoff in degrees")
    parser.add_argument("--scramble-min", type=float, default=12.0, help="Preferred minimum slope in degrees")
    parser.add_argument("--scramble-max", type=float, default=38.0, help="Preferred maximum slope in degrees")
    args = parser.parse_args()
    terrain = load_geotiff(args.dem, args.band) if args.dem else synthetic_mountain()
    config = RouterConfig(args.scramble_min, args.scramble_max, args.max_slope)
    router = AStarRouter(terrain, config)
    summit = tuple(np.unravel_index(np.nanargmax(terrain.elevation), terrain.elevation.shape))
    InteractiveMap(router, summit).show()


if __name__ == "__main__":
    main()
