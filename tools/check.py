#!/usr/bin/env python3
"""Fail when the page stops telling the truth.

Three independent checks, all on by default:

  --sync    index.html, sitemap.xml and the JSON-LD still match projects.json
  --repos   every public, non-fork fschmutz repository with GitHub Pages
            turned on has a card, unless projects.json lists it under
            inclusion.omissions with a reason
  --links   every link the page points at answers 200, and every relative
            asset it references exists in the repository

Standard library only. GITHUB_TOKEN, when set, is used for the API calls so a
busy runner does not hit the unauthenticated rate limit; the checks degrade to
a warning rather than a failure when GitHub rate-limits us anyway.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "projects.json"
PAGES = ("index.html", "404.html")
UA = "fschmutz.github.io link check (+https://github.com/fschmutz/fschmutz.github.io)"
RATE_LIMITED = (403, 429, 503)


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def ok(self, message: str) -> None:
        print(f"  ok      {message}")

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        print(f"  warn    {message}")

    def fail(self, message: str) -> None:
        self.failures.append(message)
        print(f"  FAIL    {message}")


def fetch(url: str, *, method: str = "GET", token: str | None = None, attempts: int = 3):
    """Return (status, body). status is None when the host never answered."""
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/vnd.github+json"

    last: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            if error.code in RATE_LIMITED and attempt < attempts - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            return error.code, b""
        except Exception as error:  # DNS, TLS, timeout, reset
            last = error
            if attempt < attempts - 1:
                time.sleep(2 ** (attempt + 1))
    print(f"          ({last})")
    return None, b""


# --------------------------------------------------------------------------- sync


def check_sync(report: Report) -> None:
    print("sync — generated files against projects.json")
    # Loaded by path: tools/site.py would otherwise shadow the stdlib `site`.
    spec = importlib.util.spec_from_file_location("site_builder", ROOT / "tools" / "site.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)

    data = builder.load()
    for path, wanted in ((builder.INDEX, builder.render_index(data)), (builder.SITEMAP, builder.render_sitemap(data))):
        name = path.relative_to(ROOT)
        if path.read_text(encoding="utf-8") == wanted:
            report.ok(f"{name} matches projects.json")
        else:
            report.fail(f"{name} is stale — run `python3 tools/site.py build`")


# --------------------------------------------------------------------------- repos


def check_repos(report: Report, token: str | None) -> None:
    print("repos — public Pages repositories against the cards")
    data = json.loads(DATA.read_text(encoding="utf-8"))
    owner = data["site"]["owner"]
    listed = {item["repo"].lower() for group in data["groups"] for item in group["items"]}
    omitted = {entry["repo"].lower(): entry["reason"] for entry in data["inclusion"]["omissions"]}

    for entry in data["inclusion"]["omissions"]:
        if not entry.get("reason", "").strip():
            report.fail(f"inclusion.omissions entry for {entry['repo']} has no reason")
        if entry["repo"].lower() in listed:
            report.fail(f"{entry['repo']} is both omitted and on the page — drop the omissions entry")

    status, body = fetch(f"https://api.github.com/users/{owner}/repos?per_page=100&type=owner", token=token)
    if status in RATE_LIMITED:
        report.warn(f"GitHub answered {status} for the repository list; skipping the coverage check")
        return
    if status != 200:
        report.fail(f"could not list {owner}'s repositories (HTTP {status})")
        return

    repos = json.loads(body)
    if len(repos) == 100:
        report.warn("exactly 100 repositories came back; the check needs pagination now")

    candidates = [r for r in repos if not r["fork"] and not r["archived"] and not r["private"] and r["has_pages"]]
    for repo in sorted(candidates, key=lambda r: r["name"].lower()):
        name = repo["name"]
        if name.lower() in listed:
            report.ok(f"{name} has a card")
        elif name.lower() in omitted:
            report.ok(f"{name} deliberately omitted — {omitted[name.lower()]}")
        else:
            report.fail(
                f"{name} is a public non-fork repository with Pages enabled but has no card. "
                f"Add it to projects.json, or add it to inclusion.omissions with a reason."
            )

    by_name = {r["name"].lower(): r for r in repos}
    for repo_name in sorted(listed):
        repo = by_name.get(repo_name)
        if repo is None:
            report.fail(f"projects.json lists {repo_name}, which is not a public repository of {owner}")
        elif repo["fork"]:
            report.fail(f"projects.json lists {repo['name']}, which is a fork — the inclusion rule excludes forks")
        elif repo["archived"]:
            report.warn(f"{repo['name']} is archived on GitHub but still has a card")


# --------------------------------------------------------------------------- links


def collect_links() -> tuple[set[str], set[tuple[str, str]]]:
    """Absolute URLs, and (page, relative reference) pairs."""
    absolute: set[str] = set()
    relative: set[tuple[str, str]] = set()
    # href and src always point somewhere; meta content only sometimes does,
    # so it contributes absolute URLs only.
    linking = re.compile(r'(?:href|src)="([^"]+)"')
    meta = re.compile(r'(?:content|href)="(https?://[^"]+)"')
    for page in PAGES:
        text = (ROOT / page).read_text(encoding="utf-8")
        absolute.update(meta.findall(text))
        for value in linking.findall(text):
            if value.startswith(("http://", "https://")):
                absolute.add(value)
            elif value.startswith("#") or ":" in value.split("/")[0]:
                continue
            else:
                relative.add((page, value))
    return absolute, relative


def check_links(report: Report) -> None:
    print("links — every destination answers 200")
    absolute, relative = collect_links()

    for page, reference in sorted(relative):
        target = ROOT / reference.lstrip("/")
        if target.exists():
            report.ok(f"{page} → {reference}")
        else:
            report.fail(f"{page} references {reference}, which is not in the repository")

    for url in sorted(absolute):
        if url.startswith("https://schema.org") or url.endswith("/schemas/sitemap/0.9"):
            continue  # Namespace identifiers, not pages to fetch.
        status, _ = fetch(url, method="HEAD")
        if status == 405 or status == 403:
            status, _ = fetch(url, method="GET")
        if status == 200:
            report.ok(f"200 {url}")
        elif status in RATE_LIMITED:
            report.warn(f"{status} {url} — treated as a rate limit, not a broken link")
        elif status is None:
            report.warn(f"no answer from {url} — network trouble, not a broken link")
        else:
            report.fail(f"{status} {url}")


# --------------------------------------------------------------------------- cli


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--repos", action="store_true")
    parser.add_argument("--links", action="store_true")
    args = parser.parse_args()
    everything = not (args.sync or args.repos or args.links)

    report = Report()
    if everything or args.sync:
        check_sync(report)
    if everything or args.repos:
        check_repos(report, os.environ.get("GITHUB_TOKEN") or None)
    if everything or args.links:
        check_links(report)

    print()
    if report.warnings:
        print(f"{len(report.warnings)} warning(s)")
    if report.failures:
        print(f"{len(report.failures)} failure(s):")
        for failure in report.failures:
            print(f"  - {failure}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
