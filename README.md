# fschmutz.github.io

The personal home page at **<https://fschmutz.github.io/>** — a dark card grid listing a
hand-picked set of public projects.

## What is here

| File | Role |
| --- | --- |
| `index.html` | The whole page: cards, copy and inline SVG thumbnails |
| `assets/home.css` | Slate surfaces, one indigo accent, dark by default |
| `assets/theme-boot.js` | Applies the stored theme before the first paint |
| `assets/theme.js` | The light/dark toggle in the header |
| `assets/favicon.svg`, `assets/og.png` | Icon and social card |
| `404.html` | Matching not-found page |
| `robots.txt`, `sitemap.xml` | Crawler basics |
| `tools/make-og.py` | Build-time script that redraws `assets/og.png` |

The project list is **static and curated**: it is written by hand in `index.html` and never
calls the GitHub API, so forks, taps and abandoned experiments stay out.

## How the site is served

This is a GitHub **user site**, so Pages follows the legacy convention: it publishes the
`main` branch from the repository root (`/`). There is no build step and no workflow — push
to `main` and the files go live as they are. Nothing here needs npm, a bundler or any
runtime dependency; the page is plain HTML, CSS and two short vanilla scripts.

Preview it locally with any static server, for example:

```sh
python3 -m http.server 8000
# then open http://localhost:8000/
```

## Editing the list

Add or change a project by editing its `<li class="card project">` block in `index.html`:
the inline SVG thumbnail, the kind label, the title, the one-sentence blurb, the primary
link to the live site and the secondary link to the source. Keep the matching entry in the
`ItemList` JSON-LD block in `<head>` in sync.

`assets/og.png` is committed, so regenerating it is optional:

```sh
pip install Pillow && python3 tools/make-og.py
```

---

Falco Schmutz · <https://github.com/fschmutz> · 2026
