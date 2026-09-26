# Topographical Scramble — PNW Terrain Route Planner

A terrain-aware route planner: given elevation data and two points, it finds not just *a* path but the *right kind* of path — shortest, fastest, gentlest-graded, or steepness-averse — using A* search over a slope-costed graph, with a post-search line-of-sight smoother that turns the jagged 8-connected grid path into a natural any-angle route.

This repo has two things in it, in order of maturity:

1. **`scramble_router.py`** — the original prototype. Synthetic terrain, interactive matplotlib UI, single "scramble" cost model. Fully unit-tested (`tests/test_scramble_router.py`, 12 passing tests). This is where the core algorithm — A*, line-of-sight smoothing, directional (asymmetric ascent/descent) edge costs — was designed and debugged.
2. **`index.html` + `mount_si_dem.json`** — the real thing. A self-contained web app routing over **real USGS elevation data for Mount Si, WA** (North Bend), with four distinct routing strategies computed from the same terrain-cost engine, rendered on a real topographic basemap. No server, no build step — open `index.html` in a browser, or host it on GitHub Pages.

## Try it

Open `index.html` in any browser. It loads instantly (the terrain data is embedded, not fetched — no CORS/server issues). Click the map once to set a start point, click again to set a destination, and all four routes recompute in milliseconds.

Or host it for free: enable GitHub Pages on this repo (Settings → Pages → deploy from `main` / root) and you get a public URL — see [Publishing on GitHub Pages](#publishing-on-github-pages) below.

## The four strategies

All four share one cost engine (8-connected A* over a slope-costed grid, plus a line-of-sight smoother) and differ only in how each edge is priced:

| Strategy | What it optimizes | Hard slope cutoff |
|---|---|---|
| **Shortest** | Pure horizontal distance, ignores terrain | 50° (still can't cross literal cliffs) |
| **Fastest** | Tobler's hiking-speed function (real hiking-science model of pace vs. grade) | 50° |
| **Min. elevation gain** | Total ascent | 50° |
| **Safer** | Grade, penalized quadratically above a preferred threshold | 35° (much tighter) |

On the default Old Si Trail → summit route, the algorithm finds real, meaningful trade-offs: **Shortest** is a straight line that happens to cross a 41° pitch — steep enough that no real trail would take it. **Fastest** is ~50% longer but caps the worst pitch around 22°. **Safer** is longer still but never exceeds ~24°. **Min. elevation gain** converges close to Shortest here — because Mount Si's summit sits atop a nearly continuous ridge, there's very little room to reduce total climbing below the physical floor (destination elevation minus start elevation) without a large detour. That's not a bug; it's a genuine, verified property of this specific climb (see [Honest findings](#honest-findings-and-limitations) below) — and the same algorithm, tested against other point pairs in the same dataset, found routes cutting total gain by 1,000+ ft when a real detour-around-a-dip option existed.

## Data source

`mount_si_dem.json` and the terrain grid embedded in `index.html` are a 40×40 elevation grid (47.483–47.522°N, 121.748–121.717°W) covering the Old Si Trail corridor from the trailhead to the summit, **point-sampled live from the USGS 3DEP Elevation Point Query Service** (`epqs.nationalmap.gov`) — 1-meter-resolution LIDAR-derived elevation, the same authoritative dataset USGS topo maps are built from. Every value in the grid is a real, independently-queryable elevation, not synthetic or interpolated from a cached tile.

A free alternative (`api.open-elevation.com`) was tried first and rejected: it returned large blocks of identical values (effective resolution far coarser than advertised, would have produced visibly blocky, unrealistic terrain). USGS EPQS gives genuinely-varying, high-resolution values and was used instead — worth knowing if you extend this to other mountains and are choosing a data source.

## Honest findings and limitations

- **Grid summit vs. official benchmark:** the grid cell nearest Mount Si's official summit coordinate (per Wikipedia/USGS GNIS, 47.5075°N 121.7400°W) reads 4,112 ft against a listed 4,167 ft — a 55 ft / 1.3% gap, well within normal DEM-vs-survey-benchmark variance.
- **Elevation gain is close to a physical floor for the default route.** For the trailhead→summit pair, total ascent can't usefully be reduced below (summit elevation − trailhead elevation) because the terrain offers an essentially monotonic ridge climb. The min-gain strategy is correctly implemented — verified independently on other point pairs in the same dataset, where it found dramatically different (lower-gain, longer-distance) routes — it just has little to work with on this specific out-and-back.
- **Reported slope stats are computed on the full underlying grid resolution**, not the sparse smoothed waypoints, specifically to avoid a long straight "shortest" segment misreporting its net chord slope instead of the true local terrain it crosses.
- **This is a planning/visualization tool, not a navigation or mountaineering safety system.** Always use current maps, forecasts, local guidance, and your own judgment in the field.

## Publishing on GitHub Pages

Once this is pushed to GitHub (see below), turn it into a live public URL for free:

1. On GitHub, go to your repo → **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to "Deploy from a branch", branch `main`, folder `/ (root)`.
3. Save. GitHub gives you a URL like `https://devj123.github.io/<repo-name>/` within a minute or two.

That URL is a real, live, shareable product — no server to maintain, no hosting bill.

## Requirements (Python prototype only)

The web app (`index.html`) needs nothing but a browser. The Python prototype needs:

```
pip install -r requirements.txt
python scramble_router.py          # synthetic demo terrain
python scramble_router.py dem.tif  # real GeoTIFF DEM, if you have one
pytest tests/                       # run the test suite
```

## Roadmap

See [ROADMAP.md](ROADMAP.md) for what's next — turning this from "a working demo" into "a tool real PNW hikers actually use," including the parts that need your own ongoing effort (recruiting testers, collecting feedback, expanding to more mountains) rather than more code.
