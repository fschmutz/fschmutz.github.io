#!/usr/bin/env python3
"""Render the generated parts of the site from projects.json.

projects.json is the only place a project is described. This script writes
three things from it, so they cannot drift apart:

  * the grouped card sections in index.html
  * the ItemList JSON-LD block in index.html
  * sitemap.xml

    python3 tools/site.py build    # rewrite the generated regions
    python3 tools/site.py check    # fail if the committed files differ

Standard library only: GitHub Pages serves the repository as it is, and the
build is something a contributor runs by hand before committing.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "projects.json"
INDEX = ROOT / "index.html"
SITEMAP = ROOT / "sitemap.xml"
THUMBS = ROOT / "assets" / "thumbs"

# Everything between a pair of these markers in index.html is generated.
BEGIN = "<!-- BEGIN GENERATED {name} — edit projects.json, then run tools/site.py build -->"
END = "<!-- END GENERATED {name} -->"


# --------------------------------------------------------------------------- data


def load() -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    seen: set[str] = set()
    for item in items(data):
        for field in ("slug", "repo", "name", "kind", "summary", "action", "url", "source", "lastmod"):
            if not item.get(field):
                raise SystemExit(f"projects.json: {item.get('slug', '?')} is missing {field!r}")
        if item["slug"] in seen:
            raise SystemExit(f"projects.json: duplicate slug {item['slug']!r}")
        seen.add(item["slug"])
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["lastmod"]):
            raise SystemExit(f"projects.json: {item['slug']} lastmod is not YYYY-MM-DD")
    return data


def items(data: dict) -> list[dict]:
    """Every card, in the order it appears on the page."""
    return [item for group in data["groups"] for item in group["items"]]


# --------------------------------------------------------------------------- svg


def thumb(slug: str, indent: str) -> str:
    """Inline assets/thumbs/<slug>.svg as the card thumbnail."""
    path = THUMBS / f"{slug}.svg"
    if not path.exists():
        raise SystemExit(f"missing thumbnail {path.relative_to(ROOT)}")
    raw = path.read_text(encoding="utf-8")

    open_tag = raw.index("<svg")
    close_tag = raw.rindex("</svg>")
    head = raw[open_tag : raw.index(">", open_tag) + 1]
    if 'viewBox="0 0 240 150"' not in head:
        raise SystemExit(f"{path.name}: thumbnails must use viewBox=\"0 0 240 150\"")
    body = raw[raw.index(">", open_tag) + 1 : close_tag]

    # Nine thumbnails share one document once inlined, so every id has to be
    # namespaced or the gradients would reference each other.
    for found in re.findall(r'\bid="([^"]+)"', body):
        if not found.startswith(slug):
            raise SystemExit(f"{path.name}: id {found!r} must start with {slug!r} to stay unique when inlined")

    lines = [line.strip() for line in body.splitlines() if line.strip()]
    inner = "\n".join(f"{indent}  {line}" for line in lines)
    return (
        f'{indent}<svg class="thumb" viewBox="0 0 240 150" aria-hidden="true" focusable="false">\n'
        f"{inner}\n"
        f"{indent}</svg>"
    )


# --------------------------------------------------------------------------- html


# The whole card is the link, so the action word has nowhere visible to live.
# It becomes the rest of the link's accessible name instead.
ACTIONS = {
    "Play": "play it in the browser",
    "Open": "open the app",
    "View": "view it on GitHub",
}


def card(item: dict, indent: str) -> str:
    slug = item["slug"]
    name = escape(item["name"])
    action = item["action"]
    if action not in ACTIONS:
        raise SystemExit(f"projects.json: {slug} has action {action!r}; expected one of {sorted(ACTIONS)}")
    out = [f'{indent}<li class="card">', thumb(slug, indent + "  ")]

    kind = f'{indent}  <p class="kind">{escape(item["kind"])}'
    if item.get("lang"):
        tag = item["lang"].upper()
        label = {"fr": "in French"}.get(item["lang"], f"in {tag}")
        kind += f'<span class="lang">{tag}<span class="sr-only"> — {escape(label)}</span></span>'
    out.append(kind + "</p>")

    # The stretched link: .go::after covers the card, so a click anywhere that
    # is not another control activates this one.
    out.append(
        f'{indent}  <h3 class="name"><a class="go" href="{escape(item["url"])}">{name}'
        f'<span class="sr-only"> — {ACTIONS[action]}</span>'
        f'<span class="arrow" aria-hidden="true">→</span></a></h3>'
    )
    out.append(f'{indent}  <p class="summary">{escape(item["summary"])}</p>')

    install = item.get("install")
    if install:
        out += [
            f'{indent}  <div class="install">',
            f'{indent}    <span class="install-label" id="{slug}-install">{escape(install["label"])}</span>',
            f'{indent}    <code id="{slug}-cmd">{escape(install["command"])}</code>',
            # Hidden until assets/site.js wires it up: the command is selectable either way.
            f'{indent}    <button class="copy" type="button" hidden data-copy="{slug}-cmd"'
            f' aria-describedby="{slug}-install">Copy<span class="sr-only"> the install command</span></button>',
            f"{indent}  </div>",
        ]

    # Source sits above the stretched overlay so it stays its own target. It is
    # dropped only when it would repeat the card's own link exactly.
    if item["source"] != item["url"]:
        out += [
            f'{indent}  <p class="links">',
            f'{indent}    <a class="src" href="{escape(item["source"])}">Source'
            f'<span class="sr-only"> code for {name} on GitHub</span></a>',
            f"{indent}  </p>",
        ]
    out.append(f"{indent}</li>")
    return "\n".join(out)


NUMBERS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
    8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen",
    14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen",
    19: "nineteen", 20: "twenty",
}


def intro(data: dict, indent: str) -> str:
    """The one sentence with a number in it, so the number cannot go stale."""
    count = len(items(data))
    if count not in NUMBERS:
        raise SystemExit(f"tools/site.py: add {count} to NUMBERS to spell the intro count")
    return "\n".join(
        [
            f'{indent}<p class="intro">',
            f"{indent}  Everything I have made public lives here: "
            f"<strong>{NUMBERS[count]} free, open-source things</strong>",
            f"{indent}  you can open in a tab. No account, no tracking, no cookie banner — most of them keep",
            f"{indent}  working with the network off.",
            f"{indent}</p>",
        ]
    )


def sections(data: dict, indent: str) -> str:
    blocks = []
    for group in data["groups"]:
        gid = escape(group["id"])
        cards = "\n".join(card(item, indent + "    ") for item in group["items"])
        blocks.append(
            "\n".join(
                [
                    f'{indent}<section class="group" aria-labelledby="{gid}-heading">',
                    f"{indent}  <div class=\"group-head\">",
                    f'{indent}    <h2 id="{gid}-heading">{escape(group["name"])}</h2>',
                    f'{indent}    <p class="group-tagline">{escape(group["tagline"])}</p>',
                    f"{indent}  </div>",
                    f'{indent}  <ul class="cards">',
                    cards,
                    f"{indent}  </ul>",
                    f"{indent}</section>",
                ]
            )
        )
    return "\n\n".join(blocks)


def jsonld(data: dict, indent: str) -> str:
    origin = data["site"]["origin"]
    doc = {
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        "url": f"{origin}/",
        "inLanguage": "en",
        "mainEntity": {
            "@type": "Person",
            "name": "Falco Schmutz",
            "url": f"{origin}/",
            "sameAs": [f"https://github.com/{data['site']['owner']}"],
        },
        "mainContentOfPage": {
            "@type": "ItemList",
            "name": "Public projects",
            "numberOfItems": len(items(data)),
            "itemListElement": [
                {"@type": "ListItem", "position": i, "name": item["name"], "url": item["url"]}
                for i, item in enumerate(items(data), start=1)
            ],
        },
    }
    body = json.dumps(doc, indent=2, ensure_ascii=False)
    body = "\n".join(f"{indent}{line}" for line in body.splitlines())
    return f'{indent}<script type="application/ld+json">\n{body}\n{indent}</script>'


def region(text: str, name: str, body: str) -> str:
    begin, end = BEGIN.format(name=name), END.format(name=name)
    if begin not in text or end not in text:
        raise SystemExit(f"index.html: missing the {name!r} generated region markers")
    head, rest = text.split(begin, 1)
    _, tail = rest.split(end, 1)
    indent = head[head.rindex("\n") + 1 :]
    return f"{head}{begin}\n{body}\n{indent}{end}{tail}"


def render_index(data: dict) -> str:
    text = INDEX.read_text(encoding="utf-8")
    text = region(text, "json-ld", jsonld(data, "  "))
    text = region(text, "intro", intro(data, "      "))
    text = region(text, "projects", sections(data, "      "))
    return text


# --------------------------------------------------------------------------- sitemap


def render_sitemap(data: dict) -> str:
    origin = data["site"]["origin"]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!-- Generated by tools/site.py from projects.json. Do not edit by hand. -->",
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        "  <url>",
        f"    <loc>{origin}/</loc>",
        f'    <lastmod>{data["site"]["lastmod"]}</lastmod>',
        "    <changefreq>monthly</changefreq>",
        "    <priority>1.0</priority>",
        "  </url>",
    ]
    # A sitemap may only list URLs under its own host, so cards that point at
    # github.com are represented by their card on the home page above.
    for item in items(data):
        if not item["url"].startswith(f"{origin}/"):
            continue
        lines += [
            "  <url>",
            f'    <loc>{escape(item["url"])}</loc>',
            f'    <lastmod>{item["lastmod"]}</lastmod>',
            "    <changefreq>monthly</changefreq>",
            "    <priority>0.8</priority>",
            "  </url>",
        ]
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- cli


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("build", "check"))
    args = parser.parse_args()

    data = load()
    wanted = {INDEX: render_index(data), SITEMAP: render_sitemap(data)}

    if args.command == "build":
        for path, text in wanted.items():
            changed = path.read_text(encoding="utf-8") != text
            path.write_text(text, encoding="utf-8")
            print(f"{'wrote' if changed else 'unchanged'} {path.relative_to(ROOT)}")
        return 0

    stale = []
    for path, text in wanted.items():
        current = path.read_text(encoding="utf-8")
        if current == text:
            print(f"ok    {path.relative_to(ROOT)} matches projects.json")
            continue
        stale.append(path)
        print(f"STALE {path.relative_to(ROOT)} does not match projects.json", file=sys.stderr)
        diff = difflib.unified_diff(
            current.splitlines(), text.splitlines(), "committed", "from projects.json", lineterm=""
        )
        print("\n".join(diff), file=sys.stderr)
    if stale:
        print("\nRun: python3 tools/site.py build", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
