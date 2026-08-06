# Topographical Scramble Router

An interactive Python prototype that turns a DEM into an implicit 8-neighbor graph and uses Theta* (any-angle A*) to find a terrain-preference route. It starts with a synthetic mountain so the whole workflow is testable before acquiring an elevation raster.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scramble_router.py
```

Left-click to set the start point; shift+left-click to append a waypoint; right-click to set a new goal. The hillshade/contours reveal terrain shape, while the title reports route distance, elevation gain/loss, and an indicative Naismith time estimate.

To use an acquired, projected, metric GeoTIFF DEM:

```powershell
python scramble_router.py C:\data\shuksan-dem.tif --max-slope 45 --scramble-min 12 --scramble-max 35 --cost-model tobler
```

The loader downsamples very large rasters to at most 900 pixels across for interactive performance. Use a local projected CRS with horizontal units in metres; geographic degree rasters are rejected because slope calculations would be wrong.

## Cost model

Each cell has eight potential neighbors, with all eight directed cost grids vectorized once when the DEM loads. Edges at or above `--max-slope` are blocked. Theta* uses a Bresenham line-of-sight check to join a node to its parent's parent when every crossed edge is permitted, removing grid-aligned staircase artifacts. `--cost-model scramble` uses asymmetric uphill/downhill effort with scramble-band penalties; `--cost-model tobler` uses Tobler's directed hiking-speed function. The graph is generated on demand, so it does not allocate millions of Python node objects.

Run the algorithm tests with:

```powershell
pytest tests
```

## Important limitation

This is a terrain-shape exploration tool, not a route recommendation or safety system. A DEM does not capture rock quality, snow/ice, crevasses, cliffs smaller than the raster resolution, avalanche exposure, access restrictions, changing conditions, or human capability. Do not use its output for on-mountain navigation or safety decisions.
