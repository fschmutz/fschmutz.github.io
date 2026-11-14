# fschmutz.github.io

The home page at **<https://fschmutz.github.io/>** — one card for every free, public thing
I have made, grouped so you can find the one you came for.

It is a GitHub **user site**: Pages publishes the `main` branch from the repository root,
there is no build step on the server, and the page needs no JavaScript to read. No webfont,
no analytics, no third-party request of any kind — a Content-Security-Policy meta tag in
`index.html` enforces that.

**The whole card is the link.** Clicking anywhere on a card — the thumbnail, the blurb, the
empty corner — opens the project. There is no separate Play button. The only other target
is the small `Source` link at the bottom, which goes to GitHub.

| Screen | Light | Dark |
| --- | --- | --- |
| 320 px | [`docs/screenshots/mobile-320-light.png`](docs/screenshots/mobile-320-light.png) | [`docs/screenshots/mobile-320-dark.png`](docs/screenshots/mobile-320-dark.png) |
| 1280 px | [`docs/screenshots/desktop-1280-light.png`](docs/screenshots/desktop-1280-light.png) | [`docs/screenshots/desktop-1280-dark.png`](docs/screenshots/desktop-1280-dark.png) |

## One source of truth

Everything about a project is written once, in [`projects.json`](projects.json):

```
projects.json ──► tools/site.py build ──┬──► the card sections in index.html
                                        ├──► the ItemList JSON-LD in index.html
                                        └──► sitemap.xml
              └─► tools/make-og.py    ──┬──► assets/og.svg
                                        └──► assets/og.png (the social card)
```

The regions of `index.html` between the `BEGIN GENERATED` / `END GENERATED` comments are
written by the script. Everything outside them — the head, the header, the intro, the
footer — is hand-written and left alone.

## Which projects belong here

> A card exists for every public repository owned by `fschmutz` that is **not a fork**, not
> archived, and has something a visitor can actually use: a GitHub Pages site, a
> downloadable artefact, or a single self-contained file. Forks are never listed, however
> useful, because the work is someone else's. A repository that only supports another card —
> a Homebrew tap, a release channel — is folded into that card instead of getting one of
> its own.

The rule and every deliberate exception live in `inclusion` in `projects.json`, each
exception with its reason. `tools/check.py --repos` enforces the Pages half of it against
the GitHub API, so a new public project cannot stay off the page unnoticed.

## Adding a project

1. Draw the thumbnail as `assets/thumbs/<slug>.svg`, 240 × 150, `viewBox="0 0 240 150"`.
   Every `id` inside it must start with the slug: the nine thumbnails end up inlined in one
   document and would otherwise borrow each other's gradients.
2. Add the item to the right group in `projects.json`:

   ```json
   {
     "slug": "deep-peace",
     "repo": "DEEP-PEACE",
     "name": "Deep Peace",
     "kind": "Yoga sound app",
     "lang": null,
     "summary": "One line saying what you get, not what it is built with.",
     "action": "Open",
     "url": "https://fschmutz.github.io/DEEP-PEACE/",
     "source": "https://github.com/fschmutz/DEEP-PEACE",
     "lastmod": "2026-11-07"
   }
   ```

   `slug` names the thumbnail file and the install ids. `url` is where the whole card
   goes. `lang` is `null` for English and an ISO code — `"fr"` — for anything else, which
   prints the tag on the card. `action` is `Play`, `Open` or `View`; since the card has no
   button, the word only shapes the link's accessible name — *"Deep Peace — open the app"*.
   `lastmod` goes into `sitemap.xml`; use the repository's last push date. An optional
   `install` object adds a copyable command to the card:

   ```json
   "install": { "label": "Install on macOS", "command": "brew install --cask …", "note": "…", "tap": "…" }
   ```

3. Regenerate and check:

   ```sh
   python3 tools/site.py build
   python3 tools/make-og.py        # only when the card list changed
   python3 tools/check.py
   npm ci && npx playwright install chromium && node tools/flow-check.mjs
   ```

4. Commit `projects.json`, the thumbnail, `index.html`, `sitemap.xml` and the social card.

A project with no live page of its own — `founder-bot-meme` is one PNG, with Pages off —
points its card at the best public artefact it has and its `Source` link at the repository
root. Every card keeps a `Source` link for that reason; it is dropped only when `source`
and `url` are the same string, which the flow check verifies.

To add a whole group, append an object with `id`, `name`, `tagline` and `items`. The card
grid and the social card both read the group order straight from the file; the social card
has room for six groups and raises an error, rather than overlapping itself, when a group
grows past what will fit.

## The checks

`tools/check.py` is three checks, all on by default, each also runnable alone. Standard
library only — no npm, no pip.

| Flag | What fails the build |
| --- | --- |
| `--sync` | `index.html` or `sitemap.xml` no longer matches `projects.json`, with a diff of what `tools/site.py build` would write |
| `--repos` | a public, non-fork, non-archived `fschmutz` repository with Pages enabled has no card and no entry in `inclusion.omissions`; or a card points at a repository that is a fork or does not exist |
| `--links` | a link on `index.html` or `404.html` does not answer `200`, or a relative reference points at a file that is not in the repository |

Rate limits are not failures: a `403`, `429` or `503`, or a host that never answers, is
reported as a warning and the check carries on. `GITHUB_TOKEN` is used for the API calls
when it is set. The link check reads the **published** site, so a brand-new path 404s until
the pull request merges.

`tools/flow-check.mjs` is the part CSS cannot prove: it drives Chromium over the cards and
asserts that a click on an empty corner and a click on the thumbnail both open the
project's URL, that the `Source` link opens the repository instead, that the install
command and its Copy button are not swallowed by the overlay, and that <kbd>Tab</kbd>
reaches the card link and then its `Source` link. A hit-test samples every card on a 6 px
grid at 320, 390 and 1280 px, light and dark: `elementFromPoint` must land on the card's
link or on one of the three lifted controls, so a dead strip anywhere fails the build. It
proves itself by planting the old bug (the rows lifted whole) and requiring every affected
card to be flagged. The same pass fails a group that leaves an empty grid track. It starts its own static server on a
loopback port and answers every other host with a stub, so no click in it touches the
network. Playwright is the one development dependency — pinned in `package-lock.json`,
never shipped to the site.

Both run in [`.github/workflows/checks.yml`](.github/workflows/checks.yml), on every pull
request, on pushes to `main`, and every Monday — because a link rots on its own schedule,
not on ours. The workflow asks for `contents: read` and nothing else, and pins its one
action to a full commit SHA.

## How the card is clickable

No JavaScript and no `<a>` wrapped around the card — that would put the thumbnail, the
blurb and the `Source` link inside one link and make a mess of the accessibility tree.
Instead the card's heading link covers the card:

```css
.card            { position: relative; }      /* the containing block */
.name .go::after { content: ""; position: absolute; inset: 0; z-index: 1; }
.src, .install code, .copy { position: relative; z-index: 2; }   /* above the overlay */
```

Only those three boxes are lifted, never the rows that hold them: a lifted `.links` or
`.install` row is a full-width strip that swallows clicks meant for the card.

So there is exactly one link per card in the tab order, plus `Source`, and the hover and
focus states belong to the card: `.card:hover` and `.card:has(.name .go:focus-visible)`,
the latter inside `@supports selector(:has(*))` so the link keeps its own ring where
`:has()` is missing. `prefers-reduced-motion` drops the lift and the arrow nudge. The
trade-off of the pattern is that text under the overlay is not selectable; the install
command is lifted above it precisely so that it stays so.

## Themes, scripts and the social card

The page themes itself from `prefers-color-scheme`. `assets/boot.js` runs before the first
paint and does two things: it reapplies an explicit choice from `localStorage`, and it
marks the document so the stylesheet can reveal controls that need a script.
`assets/site.js` wires the theme toggle and the copy buttons, both of which ship `hidden`
so that nothing on the page is inert without JavaScript. Colours are one token block using
`light-dark()`, with a plain fallback declaration ahead of each one; every pair clears 7:1
against the lightest pixel its theme's background gradient produces.

`tools/make-og.py` draws `assets/og.svg` from `projects.json` and rasterises it to
`assets/og.png`. Rasterising wants `rsvg-convert`, `inkscape` or Chrome on `PATH`, and
`pngquant` plus `oxipng`/`optipng` if you want the file small. Both files are committed, so
nobody needs any of that to work on the site.

## Preview

```sh
python3 -m http.server 8000     # then open http://localhost:8000/
```

## What is where

| Path | Role |
| --- | --- |
| `projects.json` | Every project, its group, and the inclusion rule |
| `index.html` | The page; the regions between `BEGIN GENERATED` and `END GENERATED` come from `projects.json` |
| `assets/home.css` | One token block, the card grid, the stretched link |
| `assets/boot.js`, `assets/site.js` | Pre-paint theme, then the toggle and the copy buttons |
| `assets/thumbs/*.svg` | One thumbnail per card, inlined at build time |
| `assets/og.svg`, `assets/og.png` | The social card and its source |
| `tools/site.py` | `build` / `check` the generated regions and `sitemap.xml` |
| `tools/check.py` | Sync, repository coverage and link checks |
| `tools/flow-check.mjs` | Browser check of the card interactions |
| `tools/make-og.py` | Redraws the social card |
| `docs/screenshots/` | Committed screenshots at 320 px and 1280 px, light and dark |

---

Falco Schmutz · <https://github.com/fschmutz> · 2026
