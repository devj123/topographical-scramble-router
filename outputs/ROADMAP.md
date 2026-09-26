# Roadmap

What's done, what's next, and — importantly — which parts of "next" need your own ongoing effort rather than more code from an AI in one sitting. Real user testing and public traction are earned over weeks, not generated in a session.

## Done (this session)

- Real elevation data for Mount Si, WA, sourced live from USGS 3DEP (1m LIDAR DEM), not synthetic terrain.
- Four distinct, verified routing strategies (shortest / fastest-Tobler / min-gain / safer) on one shared cost engine.
- A deployable web app (`index.html`) — client-side JS, real Leaflet map, real topo basemap, click-to-route, live stats + auto-generated explanations. No server needed.
- Honest data-quality and limitations write-up (see README's "Honest findings" section) — this matters for credibility as much as the algorithm does.
- Git/GitHub push instructions (see below) so this becomes a real, public, citable repo.

## Immediate next steps (you, ~1 hour)

1. **Push to GitHub** and **enable Pages** (both covered in README). This alone turns "a project on my laptop" into "a live URL I can put on an application" — probably the single highest-leverage thing left.
2. **Proofread the explanation text** the app generates against the actual numbers once it's live — I verified the logic extensively, but a second human read-through before you show it to anyone else is always worth doing.
3. **Decide on a license** (MIT is a reasonable default for a portfolio project) and add a `LICENSE` file — GitHub will prompt you for this when you create the repo.

## Near-term (you + a few more sessions with me)

- **Add 2–3 more real mountains.** The DEM-fetching approach (USGS EPQS, point-sampled on a regular grid, entirely scriptable) generalizes directly — Mailbox Peak and Tiger Mountain were the other two candidates discussed. Each one is a genuinely separate proof point ("works on Mount Si" is one data point; "works on 4 different PNW peaks with different terrain shapes" is a pattern).
- **A second demonstrated min-gain trade-off.** The Mount Si trailhead→summit pair happens to sit on a monotonic ridge (see README). Picking a second start/goal pair *within the existing dataset* that does have a real saddle/detour option (already found and verified during this session — ~1,000+ ft of gain saved for ~26% more distance) and writing it up as a second example would make the min-gain strategy's value undeniable rather than something you have to explain away.
- **GPX export**, so a generated route can actually be loaded into a phone/GPS device — turns this from "a visualization" into "a tool that produces something you'd bring on a hike."

## Medium-term: real users (this is on you, and it's the part that actually matters most for "measurable impact")

This is the step that turns "I built X" into "X was used by Y people, Z times" — the difference between a demo and a product, and the part no amount of additional coding substitutes for.

- Share the GitHub Pages link in 1–2 relevant places: a PNW hiking subreddit/Discord, a school robotics/CS club, WTA forums (read their rules on self-promotion first), or just directly with hiker friends and ask them to try routing a hike they know well and tell you if it's wrong.
- Ask each tester one concrete question: *"Does this match a route you've actually hiked? Where does it diverge, and why?"* — real trail knowledge will surface real bugs and real insights (e.g., a "safer" route that's technically gentler-graded but crosses a known scramble section a real trail avoids for other reasons, like exposure or loose rock, that pure slope-costing can't see).
- Track, even informally in a spreadsheet: number of unique visitors (GitHub Pages + a free analytics snippet like Plausible or GoatCounter), routes generated, and any direct feedback. Even "12 hikers tried it, 9 said the fastest-route recommendation matched their real experience" is a concrete, honest, citable result — a lot more credible than a bigger claim with no numbers behind it.

## Longer-term (optional, pick based on where your interest actually is)

- **Weather/conditions overlay** (recent precipitation → higher effective slope-penalty, since wet steep terrain is more dangerous than the same terrain dry).
- **Multi-day / multi-waypoint routing** (already partially supported in the Python prototype's `_route_all_legs` concept — porting that to the web app is straightforward).
- **A small backend** if you want saved routes / user accounts down the line — not needed for the current scope, and adds real maintenance burden, so only take this on if the project has actual recurring users asking for it.

## Explicitly not pursuing

You asked about a note referencing "local business optimization" — per your call, that's unrelated to this project and isn't reflected here.
