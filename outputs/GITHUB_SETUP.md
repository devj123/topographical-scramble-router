# Pushing this to GitHub (devj123)

I can't run git or push code myself (no server access from here, and I shouldn't handle your credentials anyway) — but this is genuinely just two real steps.

## 1. Create the empty repo on GitHub

Go to [github.com/new](https://github.com/new), signed in as **devj123** (swap in your actual username below if that's not exact):

- Repository name: `topographical-scramble` (or whatever you'd like)
- **Don't** check "Add a README" / "Add .gitignore" / "Choose a license" — leave it completely empty, since you already have all of that locally.
- Click **Create repository**. GitHub will show you a page with setup commands — ignore it and use the ones below instead (they're the same thing, just copy-paste ready).

## 2. Push your code

Open a terminal **in this project's `outputs` folder** (the one with `index.html`, `scramble_router.py`, etc. in it) and run:

```bash
git init
git add .
git commit -m "Mount Si terrain router: real USGS DEM, 4 routing strategies, web app"
git branch -M main
git remote add origin https://github.com/devj123/topographical-scramble.git
git push -u origin main
```

Replace the URL in the `git remote add` line with the exact URL GitHub showed you after creating the repo, if it differs (e.g. different repo name).

If you don't have git installed, the fastest path is **GitHub Desktop** (github.com/apps/desktop) — point it at this folder, it'll offer to initialize + publish the repo with a couple of clicks, no command line needed.

## 3. Turn it into a live public URL (optional but recommended)

Once it's pushed: on the repo page, go to **Settings → Pages**, set **Source** to "Deploy from a branch," branch `main`, folder `/ (root)`, and save. Within a minute or two you'll have a real URL like:

```
https://devj123.github.io/topographical-scramble/
```

That's a live, working, shareable web app — exactly the kind of link that's genuinely useful on a college application, not just a link to source code.

## What's in this repo

- `index.html` — the real product: real Mount Si terrain, 4 routing strategies, interactive map. Just open it in a browser.
- `mount_si_dem.json` — the real elevation dataset, documented and independently inspectable.
- `scramble_router.py` — the original algorithm prototype (synthetic terrain, matplotlib UI), fully unit-tested.
- `tests/test_scramble_router.py` — 12 passing tests covering the core A* + smoothing logic, including two regression tests for a hang bug and a directional-penalty bug found and fixed in earlier review rounds.
- `README.md` — project overview, methodology, honest limitations.
- `ROADMAP.md` — what's next, including the parts that need your own effort (real users, not more code).
- `requirements.txt` — Python deps for the prototype only; the web app needs nothing but a browser.
