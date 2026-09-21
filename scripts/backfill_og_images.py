#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx"]
# ///
"""
投稿のアイキャッチ (featured_image) が空の投稿に、コンテンツの素材から画像を取得して EmDash のメディアとして設定する。
featured_image はカードのサムネイルと OGP 画像に使われる。

外部サービスの画像は消えたり差し替わったりするため、一度取得したら EmDash (R2) に保持する。
featured_image が既に入っている投稿と、写真を持つ投稿は対象外。何度実行してもよい。

素材の優先順:
  1. YouTube 動画のサムネイル (maxresdefault → hqdefault)
  2. 本文のリンク先: Spotify (oEmbed) / Apple Music (iTunes lookup) / 一般サイトの og:image

使い方 (web/ で emdash CLI を使うため、リポジトリ直下から実行):
  uv run scripts/backfill_og_images.py --url http://localhost:4321          # ローカル (dev bypass)
  uv run scripts/backfill_og_images.py --url https://puppets.jp --dry-run   # 本番: 対象の確認のみ
  uv run scripts/backfill_og_images.py --url https://puppets.jp             # 本番: 保存

本番の認証は `npx emdash login --url https://puppets.jp` (web/ で実行) の資格情報、または EMDASH_TOKEN。
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import httpx

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
YOUTUBE_ID_RE = re.compile(r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")
SKIP_HOSTS = {"creativecommons.org"}
HTTP = httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; puppets.jp OGP backfill)"})


def emdash(args: list[str], url: str) -> dict:
    """web/ で emdash CLI を実行して JSON を返す"""
    cmd = ["npx", "--no-install", "emdash", *args, "--url", url, "--json"]
    out = subprocess.run(cmd, cwd=WEB_DIR, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:3])}: {out.stderr.strip()[-500:]}")
    return json.loads(out.stdout)


def list_posts(url: str) -> list[str]:
    slugs, cursor = [], None
    while True:
        args = ["content", "list", "posts", "--limit", "100"] + (["--cursor", cursor] if cursor else [])
        page = emdash(args, url)
        slugs += [item["slug"] for item in page["items"]]
        cursor = page.get("nextCursor")
        if not cursor or not page["items"]:
            return slugs


class OgImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.image: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag != "meta" or self.image:
            return
        a = dict(attrs)
        key = (a.get("property") or a.get("name") or "").lower()
        if key in ("og:image", "og:image:secure_url", "twitter:image") and a.get("content"):
            self.image = a["content"]


def youtube_thumbnail(video_id: str) -> str | None:
    for name in ("maxresdefault", "hqdefault"):
        u = f"https://i.ytimg.com/vi/{video_id}/{name}.jpg"
        r = HTTP.head(u)
        # 存在しない maxres は 404 (まれに 120x90 のプレースホルダ) になる
        if r.status_code == 200 and int(r.headers.get("content-length", "0")) > 2000:
            return u
    return None


def image_for_link(link: str) -> str | None:
    host = urlparse(link).hostname or ""
    yt = YOUTUBE_ID_RE.search(link)
    if yt:
        return youtube_thumbnail(yt.group(1))
    if host == "open.spotify.com":
        r = HTTP.get(f"https://open.spotify.com/oembed?url={quote(link, safe='')}")
        thumb = r.json().get("thumbnail_url") if r.status_code == 200 else None
        # oEmbed のサムネイルは 300px。同じ画像の 640px 版 (ab67616d0000b273) に置き換える
        return thumb.replace("ab67616d00001e02", "ab67616d0000b273") if thumb else None
    if host.endswith("music.apple.com"):
        m = re.search(r"[?&]i=(\d+)", link) or re.search(r"/(\d+)/?(?:\?|$)", link)
        if not m:
            return None
        r = HTTP.get(f"https://itunes.apple.com/lookup?id={m.group(1)}&country=jp")
        results = r.json().get("results", []) if r.status_code == 200 else []
        art = next((x["artworkUrl100"] for x in results if x.get("artworkUrl100")), None)
        return re.sub(r"/\d+x\d+bb\.", "/1200x1200bb.", art) if art else None
    html, final_url = fetch_html(link)
    if not html:
        return None
    parser = OgImageParser()
    parser.feed(html[:256 * 1024])
    return urljoin(final_url, parser.image) if parser.image else None


def fetch_html(url: str) -> tuple[str | None, str]:
    """一般サイトの HTML を取得する。httpx だと TLS 指紋で弾くサイト (Flickr 等) があるため curl を使う"""
    out = subprocess.run(
        ["curl", "-sL", "--max-time", "15", "-A", "Mozilla/5.0", "-w", "\n%{http_code} %{content_type} %{url_effective}", url],
        capture_output=True, text=True, errors="replace",
    )
    body, _, status = out.stdout.rpartition("\n")
    code, ctype, final_url = (status.split(" ", 2) + ["", ""])[:3]
    if out.returncode != 0 or code != "200" or "html" not in ctype:
        return None, url
    return body, final_url or url


def content_links(blocks: list, site_url: str) -> list[str]:
    links: list[str] = []
    for block in blocks or []:
        if block.get("_type") == "embed" and isinstance(block.get("url"), str):
            links.append(block["url"])
        for d in block.get("markDefs") or []:
            if d.get("_type") == "link" and isinstance(d.get("href"), str):
                links.append(d["href"])
    site_host = urlparse(site_url).hostname
    seen, result = set(), []
    for link in links:
        host = urlparse(link).hostname
        if link in seen or not link.startswith("http") or host in SKIP_HOSTS or host in (site_host, "puppets.jp"):
            continue
        seen.add(link)
        result.append(link)
    return result


def find_source(data: dict, site_url: str) -> tuple[str, str] | None:
    """(画像 URL, 由来の説明) を返す。写真を持つ投稿・素材が無い投稿は None"""
    yt = YOUTUBE_ID_RE.search(data.get("video_url") or "")
    if yt:
        image = youtube_thumbnail(yt.group(1))
        return (image, "YouTube") if image else None
    if data.get("photos"):
        return None
    for link in content_links(data.get("content"), site_url)[:3]:
        try:
            image = image_for_link(link)
        except (httpx.HTTPError, ValueError):
            image = None
        if image:
            return image, link
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="EmDash のサイト URL")
    ap.add_argument("--dry-run", action="store_true", help="対象と素材の確認のみ")
    args = ap.parse_args()

    try:
        slugs = list_posts(args.url)
    except RuntimeError as e:
        if "Not authenticated" in str(e):
            sys.exit(f"未ログイン: web/ で `npx emdash login --url {args.url}` を実行してから再実行してください")
        raise

    done = skipped = failed = 0
    for slug in slugs:
        entry = emdash(["content", "get", "posts", slug, "--raw"], args.url)
        data = entry["data"]
        if data.get("featured_image"):
            skipped += 1
            continue
        source = find_source(data, args.url)
        if not source:
            skipped += 1
            continue
        image_url, origin = source
        print(f"{slug}: {origin} → {image_url}")
        if args.dry_run:
            done += 1
            continue
        try:
            r = HTTP.get(image_url)
            r.raise_for_status()
            suffix = {"image/png": ".png", "image/webp": ".webp"}.get(r.headers.get("content-type", "").split(";")[0], ".jpg")
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / f"og-{slug[:60]}{suffix}"
                path.write_bytes(r.content)
                media = emdash(["media", "upload", str(path), "--alt", data.get("title") or slug], args.url)
            value = {
                "provider": "local",
                "id": media["id"],
                "alt": data.get("title") or slug,
                "width": media.get("width"),
                "height": media.get("height"),
                "mimeType": media.get("mimeType"),
                "filename": media.get("filename"),
                "meta": {"storageKey": media["storageKey"], "sourceUrl": image_url},
            }
            emdash(["content", "update", "posts", slug, "--rev", entry["_rev"], "--data", json.dumps({"featured_image": value})], args.url)
            done += 1
        except (httpx.HTTPError, RuntimeError, KeyError) as e:
            failed += 1
            print(f"  失敗: {e}", file=sys.stderr)

    verb = "対象" if args.dry_run else "保存"
    print(f"\n{verb} {done} 件 / スキップ {skipped} 件 / 失敗 {failed} 件")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
