# Topographical Scramble Router

An interactive Python prototype that turns a DEM into an implicit 8-neighbor graph, uses A* to find a terrain-cost-optimal grid route, then smooths that finished route with valid, non-worsening line-of-sight shortcuts. It starts with a synthetic mountain so the whole workflow is testable before acquiring an elevation raster.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scramble_router.py
```

Left-click to set the start point; shift+left-click (or backend-independent middle-click) appends a waypoint; right-click sets a new goal. The sliders and cost-model chooser reroute live after a 150 ms pause, so dragging controls does not repeatedly recompute the 8-direction cost surface. The solid magenta primary route is accompanied by a thin dashed cyan route that penalizes reuse of its cells, making a useful alternate visible at a glance. The hillshade/contours reveal terrain shape, while the title reports route distance, elevation gain/loss, and an indicative Naismith time estimate.

Press `E` to export the last route as WGS84 GeoJSON. GeoTIFFs retain their CRS and affine transform, so a real DEM route can be overlaid in GIS or web-map software. Use `--export C:\data\route.geojson` to choose the destination; otherwise it writes `theta_route.geojson` in the current folder. Synthetic terrain has no geographic reference and cannot be exported.

To use an acquired, projected, metric GeoTIFF DEM:

```powershell
python scramble_router.py C:\data\shuksan-dem.tif --max-slope 45 --scramble-min 12 --scramble-max 35 --cost-model tobler
```

The loader downsamples very large rasters to at most 900 pixels across for interactive performance. Use a local projected CRS with horizontal units in metres; geographic degree rasters are rejected because slope calculations would be wrong.

## Cost model

Each cell has eight potential neighbors, with all eight directed cost grids vectorized once when the DEM loads. Edges at or above `--max-slope` are blocked. A* uses consistent O(1) grid-edge relaxations. Any-angle rendering/export is then produced by greedy, valid, non-worsening line-of-sight shortcutting on the completed route, keeping Bresenham scans out of the expansion hot loop. This is path smoothing, not Theta*; it cannot explore a separate any-angle corridor during search. The terrain-specific minimum directed cost per metre supplies a tighter admissible A* heuristic. `--cost-model scramble` uses asymmetric uphill/downhill effort with scramble-band penalties; `--cost-model tobler` uses Tobler's directed hiking-speed function.

Run the algorithm tests with:

```powershell
pytest tests
```

## Important limitation

This is a terrain-shape exploration tool, not a route recommendation or safety system. A DEM does not capture rock quality, snow/ice, crevasses, cliffs smaller than the raster resolution, avalanche exposure, access restrictions, changing conditions, or human capability. Do not use its output for on-mountain navigation or safety decisions.
