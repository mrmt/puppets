#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx", "python-frontmatter"]
# ///
"""
旧 Tumblr URL が新サイトで 301 → 200 になることを全投稿について検証する

使い方:
  uv run scripts/verify_legacy_urls.py http://localhost:4321
  uv run scripts/verify_legacy_urls.py https://puppets-web.exsead.workers.dev
"""

import json
import sys
from pathlib import Path
from urllib.parse import quote

import frontmatter
import httpx

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "migration/tumblr-export/posts"


def legacy_paths() -> list[tuple[str, str]]:
    """(旧パス, 期待する新パス) の一覧"""
    id_map = json.loads((ROOT / "web/src/utils/tumblr-id-map.json").read_text())
    cases = []
    for f in sorted(POSTS_DIR.glob("[0-9]*.md")):
        meta = frontmatter.load(str(f)).metadata
        post_id = str(meta["id"])
        slug = quote(str(meta.get("slug") or ""))
        path = f"/post/{post_id}/{slug}" if slug else f"/post/{post_id}"
        cases.append((path, f"/posts/{id_map[post_id]}"))
    cases += [
        ("/tagged/sectcommune", "/artists/sect-commune"),
        ("/tagged/metafictions", "/artists/metafictions"),
        ("/tagged/diastereomer", "/artists/diastereomer"),
        ("/tagged/sfh", "/artists/sfh"),
        ("/tagged/the%20twilight%20states", "/artists/the-twilight-states"),
        ("/tagged/dizzy%20states", "/artists/dizzy-states"),
        ("/tagged/live", "/tag/live"),
        ("/rss", "/rss.xml"),
        ("/archive", "/posts"),
        ("/page/2", "/posts"),
    ]
    return cases


def main():
    base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:4321"
    ng = 0
    cases = legacy_paths()
    with httpx.Client(timeout=30) as client:
        for old, expected in cases:
            r = client.get(base + old)
            loc = r.headers.get("location", "")
            to_path = httpx.URL(loc).path if loc else ""
            ok = r.status_code == 301 and to_path == expected
            if ok:
                final = client.get(base + loc if loc.startswith("/") else loc)
                ok = final.status_code == 200
            if not ok:
                ng += 1
                print(f"NG {old} → {r.status_code} {loc} (期待: {expected})")
        for path in ["/fa", "/rss.xml", "/sitemap.xml"]:
            r = client.get(base + path)
            if r.status_code != 200:
                ng += 1
                print(f"NG {path} → {r.status_code}")
    total = len(cases) + 3
    print(f"{total - ng}/{total} OK")
    sys.exit(1 if ng else 0)


if __name__ == "__main__":
    main()
