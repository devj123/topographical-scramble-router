# Topographical Scramble Router

An interactive Python prototype that turns a DEM into an implicit 8-neighbor graph and uses A* to find a terrain-preference route to the highest cell. It starts with a synthetic mountain so the whole workflow is testable before acquiring an elevation raster.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scramble_router.py
```

Click any location on the map to place a start point. The yellow star is the highest DEM cell and the magenta line is the calculated route.

To use an acquired, projected, metric GeoTIFF DEM:

```powershell
python scramble_router.py C:\data\shuksan-dem.tif --max-slope 45 --scramble-min 12 --scramble-max 35
```

The loader downsamples very large rasters to at most 900 pixels across for interactive performance. Use a local projected CRS with horizontal units in metres; geographic degree rasters are rejected because slope calculations would be wrong.

## Cost model

Each cell has eight potential neighbors. An edge is blocked at or above `--max-slope`; below that, its cost is horizontal distance plus quadratic penalties for slopes outside the selected scrambling band. A* uses planar straight-line distance to the summit as an admissible lower-bound heuristic. The graph is generated on demand, so it does not allocate millions of Python node objects.

## Important limitation

This is a terrain-shape exploration tool, not a route recommendation or safety system. A DEM does not capture rock quality, snow/ice, crevasses, cliffs smaller than the raster resolution, avalanche exposure, access restrictions, changing conditions, or human capability. Do not use its output for on-mountain navigation or safety decisions.
