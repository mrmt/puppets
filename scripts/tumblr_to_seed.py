#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-frontmatter",
#   "python-slugify",
#   "httpx",
#   "keyring",
# ]
# ///
"""
Tumblr 投稿 (content/posts/*.md) を EmDash の seed に変換する移行スクリプト

使い方:
  uv run scripts/tumblr_to_seed.py            # seed 生成 (画像は Tumblr API で原寸 URL を解決)
  uv run scripts/tumblr_to_seed.py --offline  # API を使わず migration/media-urls.json のキャッシュのみで生成

出力:
  web/seed/seed.json                 スキーマ + 全投稿 + アーティスト
  web/seed/published-at.sql          seed 適用後に流す公開日時の UPDATE 文
  web/src/utils/tumblr-id-map.json   Tumblr post id → 新 slug (旧 URL リダイレクト用)
  migration/media/                   Tumblr ホスト画像の原本 (アーカイブ)
  migration/media-urls.json          post id → 原寸画像 URL のキャッシュ
"""

import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import frontmatter
import httpx
from slugify import slugify

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content/posts"
SEED_PATH = ROOT / "web/seed/seed.json"
SQL_PATH = ROOT / "web/seed/published-at.sql"
ID_MAP_PATH = ROOT / "web/src/utils/tumblr-id-map.json"
MEDIA_DIR = ROOT / "migration/media"
MEDIA_URLS_PATH = ROOT / "migration/media-urls.json"

YOUTUBE_ID_RE = re.compile(r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})")

# アーティスト (レーベル所属) — tag はこのタグが付いた投稿をアーティストページに集約する
ARTISTS = [
    {
        "slug": "diastereomer",
        "name": "Diastereomer",
        "tag": "diastereomer",
        # 説明文は旧 /fa ページ (Fourier Analyze 2025) の紹介文より
        "description": "1986年に東京で結成されたニューウェーブの2人組バンド。1989年に自主制作シングルMothersunを200枚限定でリリース。2018年にはBitter Lake Recordingsから未発表のスタジオ録音やライブ音源を収録したアルバムIgnition Advancerがリリースされ、翌年にはDemo And Live Tracks, Vol. 1もリリースされた。",
        "links": [
            {"label": "Spotify", "url": "https://open.spotify.com/album/4hyRtPapIfbCLESVWL5RKC"},
            {"label": "Bandcamp", "url": "https://bitterlakerecordings.bandcamp.com/album/ignition-advancer"},
        ],
    },
    {
        "slug": "sect-commune",
        "name": "Sect Commune",
        "tag": "sectcommune",
        "description": "1987年に東京で結成されたエレクトロニック・ポップ/ロックユニット。2019年にはミニアルバムSix Ambient Tracksをリリース。エレクトロニカやテクノの要素を取り入れた独自のスタイルが特徴。",
        "links": [
            {"label": "Official site", "url": "https://sect-commune.com"},
            {"label": "YouTube", "url": "https://www.youtube.com/@sect-commune"},
            {"label": "Spotify", "url": "https://open.spotify.com/intl-ja/artist/0yTfw5G8fut4YChAlSzCgz"},
            {"label": "Apple Music", "url": "https://music.apple.com/jp/artist/sect-commune/486130726"},
            {"label": "SoundCloud", "url": "https://soundcloud.com/sectcommune"},
        ],
    },
    {
        "slug": "metafictions",
        "name": "metafictions",
        "tag": "metafictions",
        "links": [
            {"label": "Official site", "url": "https://metafictions.net"},
            {"label": "YouTube", "url": "https://www.youtube.com/@metafictions-plex"},
            {"label": "Spotify", "url": "https://open.spotify.com/intl-ja/artist/1Axn9FNf9tzjrgEmSL1B2H"},
            {"label": "Apple Music", "url": "https://music.apple.com/jp/artist/metafictions/1862998299"},
            {"label": "Amazon Music", "url": "https://music.amazon.co.jp/artists/B0G9P8RDT1/metafictions"},
            {"label": "SoundCloud", "url": "https://soundcloud.com/metafictions"},
        ],
    },
    {"slug": "sfh", "name": "SFH", "tag": "sfh", "links": []},
    {"slug": "the-twilight-states", "name": "The Twilight States", "tag": "the twilight states", "links": []},
    {"slug": "dizzy-states", "name": "Dizzy States", "tag": "dizzy states", "links": []},
    {"slug": "fourier-analysis", "name": "Fourier Analysis", "tag": "fourier analysis", "links": []},
]


# --- HTML → Portable Text ---

class PortableTextBuilder(HTMLParser):
    """Tumblr の投稿 HTML (実際に使われているタグのみ) を Portable Text に変換する"""

    INLINE_MARKS = {"b": "strong", "strong": "strong", "i": "em", "em": "em"}

    def __init__(self, key_prefix: str):
        super().__init__(convert_charrefs=True)
        self.key_prefix = key_prefix
        self.key_seq = 0
        self.blocks: list[dict] = []
        self.images: list[str] = []  # figure > img の src (本文から取り除き photos に回す)
        self.current: dict | None = None
        self.marks: list[str] = []
        self.link_stack: list[str | None] = []
        self.in_pre = False
        self.skip_depth = 0  # figure 内など、テキストを拾わない領域

    def _key(self) -> str:
        self.key_seq += 1
        return f"{self.key_prefix}-{self.key_seq}"

    def _open_block(self):
        if self.current is None:
            self.current = {"_type": "block", "_key": self._key(), "style": "normal", "markDefs": [], "children": []}

    def _close_block(self):
        if self.current is None:
            return
        # 前後の空白・改行を削り、空ブロックは捨てる
        children = self.current["children"]
        if children:
            children[0]["text"] = children[0]["text"].lstrip()
            children[-1]["text"] = children[-1]["text"].rstrip()
        children[:] = [c for c in children if c["text"]]
        if children:
            self.blocks.append(self.current)
        self.current = None

    def _add_text(self, text: str):
        if not text:
            return
        self._open_block()
        marks = list(self.marks)
        children = self.current["children"]
        if children and children[-1]["marks"] == marks:
            children[-1]["text"] += text
        else:
            children.append({"_type": "span", "_key": self._key(), "text": text, "marks": marks})

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.skip_depth:
            if tag == "img" and attrs.get("src"):
                self.images.append(attrs["src"])
            if tag not in ("img", "br"):
                self.skip_depth += 1
            return
        if tag in ("p", "div"):
            self._close_block()
        elif tag == "pre":
            self._close_block()
            self.in_pre = True
        elif tag == "br":
            self._add_text("\n")
        elif tag in self.INLINE_MARKS:
            self.marks.append(self.INLINE_MARKS[tag])
        elif tag == "a":
            href = attrs.get("href")
            key = None
            if href:
                self._open_block()
                key = self._key()
                self.current["markDefs"].append({"_type": "link", "_key": key, "href": href})
                self.marks.append(key)
            self.link_stack.append(key)
        elif tag == "figure":
            self._close_block()
            self.skip_depth = 1
        elif tag == "img":
            if attrs.get("src"):
                self.images.append(attrs["src"])
        elif tag == "iframe":
            self._close_block()
            self.blocks.append({"_type": "embed", "_key": self._key(), "url": html.unescape(attrs["src"])})
        else:
            raise ValueError(f"未対応のタグ: <{tag}>")

    def handle_endtag(self, tag):
        if self.skip_depth:
            if tag not in ("img", "br"):
                self.skip_depth -= 1
            return
        if tag in ("p", "div"):
            self._close_block()
        elif tag == "pre":
            self._close_block()
            self.in_pre = False
        elif tag in self.INLINE_MARKS:
            self.marks.remove(self.INLINE_MARKS[tag])
        elif tag == "a":
            key = self.link_stack.pop()
            if key:
                self.marks.remove(key)

    def handle_data(self, data):
        if self.skip_depth:
            return
        if not self.in_pre:
            # HTML 上の改行・インデントは空白 1 つに畳む (改行は <br> のみ)
            data = re.sub(r"\s+", " ", data)
            if self.current is None and not data.strip():
                return
        self._add_text(data)

    def result(self) -> list[dict]:
        self._close_block()
        # 先頭の改行を落としたあと残る "\n " などを整理
        for block in self.blocks:
            for child in block.get("children", []):
                child["text"] = re.sub(r" *\n *", "\n", child["text"])
        return self.blocks


def html_to_portable_text(body: str, key_prefix: str) -> tuple[list[dict], list[str]]:
    builder = PortableTextBuilder(key_prefix)
    builder.feed(body)
    builder.close()
    return builder.result(), builder.images


def plain_text(blocks: list[dict]) -> str:
    return "\n".join("".join(c["text"] for c in b.get("children", [])) for b in blocks if b["_type"] == "block")


# --- 画像 URL 解決 ---

def largest_srcset_url(img_src: str, body: str) -> str:
    """npf 画像は srcset の最大サイズを原寸として使う"""
    for m in re.finditer(r'srcset="([^"]+)"', body):
        candidates = [c.strip().rsplit(" ", 1) for c in m.group(1).split(",")]
        urls = [u for u, _ in candidates]
        if img_src in urls:
            return max(candidates, key=lambda c: int(c[1].rstrip("w")))[0]
    return img_src


def fetch_photo_urls(post_id: str) -> list[dict]:
    """Tumblr API から photo 投稿の原寸画像 URL を取得する"""
    sys.path.insert(0, str(ROOT / "scripts"))
    from sync import API_BASE, BLOG_IDENTIFIER, make_client  # noqa: E402

    with make_client() as client:
        resp = client.get(f"{API_BASE}/blog/{BLOG_IDENTIFIER}/posts", params={"id": post_id})
        resp.raise_for_status()
        post = resp.json()["response"]["posts"][0]
    return [
        {"url": p["original_size"]["url"], "alt": p.get("caption") or ""}
        for p in post.get("photos", [])
    ]


def download(url: str) -> Path:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    name = "-".join(url.split("/")[-3:])  # hash-size-file で一意化
    dest = MEDIA_DIR / name
    if not dest.exists():
        resp = httpx.get(url, timeout=60, follow_redirects=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return dest


# --- 変換本体 ---

def tumblr_date_to_iso(value) -> str:
    """frontmatter の date (Tumblr 形式 / ISO 形式) を ISO 8601 UTC に正規化"""
    s = str(value).strip()
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) GMT", s)
    if m:
        return f"{m.group(1)}T{m.group(2)}.000Z"
    from datetime import datetime, timezone

    dt = datetime.fromisoformat(s).astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def derive_title(meta: dict, blocks: list[dict], fallback: str) -> str:
    if meta.get("title"):
        return str(meta["title"]).strip()
    # 本文先頭の太字 (Tumblr 動画投稿の慣習的なタイトル行)
    for block in blocks[:2]:
        for child in block.get("children", []):
            if "strong" in child["marks"] and child["text"].strip():
                return child["text"].strip().split("\n")[0]
    # 本文先頭行
    text = plain_text(blocks).strip()
    if text:
        line = text.split("\n")[0].strip()
        return line[:80] + ("…" if len(line) > 80 else "")
    return fallback


def make_slug(meta: dict, title: str, post_id: str, used: set[str]) -> str:
    base = str(meta.get("slug") or "")
    if not base or base.startswith("post-") or not base.isascii():
        # 日本語は音訳せず落とし、ASCII 部分だけで slug を作る
        ascii_title = re.sub(r"[^\x00-\x7f]+", " ", title)
        base = slugify(ascii_title, max_length=60, word_boundary=True)
        if len(base) < 8:
            base = ""
    base = base or f"post-{post_id}"
    slug = base
    if slug in used:
        slug = f"{base}-{post_id[-6:]}"
    used.add(slug)
    return slug


def tag_slug(tag: str) -> str:
    return slugify(tag) or "tag"


def main():
    offline = "--offline" in sys.argv
    media_urls: dict = json.loads(MEDIA_URLS_PATH.read_text()) if MEDIA_URLS_PATH.exists() else {}

    files = sorted(POSTS_DIR.glob("[0-9]*.md"))
    entries, id_map, sql_lines = [], {}, []
    tags: dict[str, str] = {}
    used_slugs: set[str] = set()

    # 古い順に処理して slug 重複時は新しい方に接尾辞を付ける
    posts = []
    for f in files:
        post = frontmatter.load(str(f))
        posts.append((tumblr_date_to_iso(post.metadata["date"]), f, post))
    posts.sort(key=lambda p: p[0])

    for published_at, f, post in posts:
        meta = post.metadata
        post_id = str(meta["id"])
        body = post.content
        blocks, inline_images = html_to_portable_text(body, f"t{post_id}")

        # 画像: photo 投稿は API の原寸、本文 figure は srcset 最大サイズ
        photo_urls = []
        if meta["type"] == "photo":
            if post_id not in media_urls:
                if offline:
                    raise SystemExit(f"--offline だが画像 URL キャッシュが無い: {post_id}")
                media_urls[post_id] = fetch_photo_urls(post_id)
            photo_urls = media_urls[post_id]
        photo_urls += [{"url": largest_srcset_url(src, body), "alt": ""} for src in inline_images]
        for p in photo_urls:
            download(p["url"])

        title = derive_title(meta, blocks, f"post-{post_id}")
        slug = make_slug(meta, title, post_id, used_slugs)
        id_map[post_id] = slug

        data: dict = {"title": title, "content": blocks}
        if meta.get("video_url"):
            if not YOUTUBE_ID_RE.search(meta["video_url"]):
                raise SystemExit(f"YouTube 以外の動画: {f.name}")
            data["video_url"] = meta["video_url"]
        if photo_urls:
            media = [
                {"$media": {"url": p["url"], "alt": p["alt"] or title, "filename": f"{post_id}-{i + 1}{Path(p['url']).suffix}"}}
                for i, p in enumerate(photo_urls)
            ]
            data["featured_image"] = media[0]
            data["photos"] = media
        excerpt = plain_text(blocks).strip()
        if excerpt:
            data["excerpt"] = excerpt[:200]

        post_tags = [str(t) for t in (meta.get("tags") or [])]
        term_slugs = []
        for t in post_tags:
            s = tag_slug(t)
            tags.setdefault(s, t)
            if s not in term_slugs:
                term_slugs.append(s)

        entry = {
            "id": f"tumblr-{post_id}",
            "slug": slug,
            "status": "published" if meta.get("state", "published") == "published" else "draft",
            "data": data,
        }
        if term_slugs:
            entry["taxonomies"] = {"tag": term_slugs}
        entries.append(entry)
        sql_lines.append(f"UPDATE ec_posts SET published_at = '{published_at}' WHERE slug = '{slug}';")

    MEDIA_URLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEDIA_URLS_PATH.write_text(json.dumps(media_urls, ensure_ascii=False, indent=2) + "\n")

    artists = []
    for i, a in enumerate(ARTISTS):
        data = {
            "name": a["name"],
            "tag": tag_slug(a["tag"]),
            "links": a["links"],
            "sort_order": i + 1,
        }
        if a.get("description"):
            data["description"] = [{
                "_type": "block", "_key": f"artist-{a['slug']}-1", "style": "normal", "markDefs": [],
                "children": [{"_type": "span", "_key": f"artist-{a['slug']}-2", "text": a["description"], "marks": []}],
            }]
        artists.append({
            "id": f"artist-{a['slug']}",
            "slug": a["slug"],
            "status": "published",
            "data": data,
        })

    seed = {
        "$schema": "https://emdashcms.com/seed.schema.json",
        "version": "1",
        "meta": {"name": "puppets records", "description": "puppets records official site", "author": "puppets records"},
        "settings": {
            "title": "puppets records",
            "tagline": "Electronic music label since 1989",
            "url": "https://puppets.jp",
            "dateFormat": "YYYY.MM.DD",
            "timezone": "Asia/Tokyo",
        },
        "collections": [
            {
                "slug": "posts",
                "label": "Posts",
                "labelSingular": "Post",
                "supports": ["drafts", "revisions", "search", "seo"],
                "urlPattern": "/posts/{slug}",
                "fields": [
                    {"slug": "title", "label": "Title", "type": "string", "required": True, "searchable": True},
                    {"slug": "video_url", "label": "YouTube URL", "type": "string"},
                    {"slug": "featured_image", "label": "Featured Image", "type": "image"},
                    {"slug": "photos", "label": "Photos", "type": "json"},
                    {"slug": "content", "label": "Content", "type": "portableText", "searchable": True},
                    {"slug": "excerpt", "label": "Excerpt", "type": "text"},
                ],
            },
            {
                "slug": "pages",
                "label": "Pages",
                "labelSingular": "Page",
                "supports": ["drafts", "revisions", "search", "seo"],
                "urlPattern": "/pages/{slug}",
                "fields": [
                    {"slug": "title", "label": "Title", "type": "string", "required": True, "searchable": True},
                    {"slug": "content", "label": "Content", "type": "portableText", "searchable": True},
                ],
            },
            {
                "slug": "artists",
                "label": "Artists",
                "labelSingular": "Artist",
                "supports": ["revisions"],
                "urlPattern": "/artists/{slug}",
                "titleField": "name",
                "fields": [
                    {"slug": "name", "label": "Name", "type": "string", "required": True, "searchable": True},
                    {"slug": "tag", "label": "Tag slug", "type": "string", "required": True},
                    {"slug": "image", "label": "Image", "type": "image"},
                    {"slug": "description", "label": "Description", "type": "portableText"},
                    {"slug": "links", "label": "Links", "type": "json"},
                    {"slug": "sort_order", "label": "Sort order", "type": "integer"},
                ],
            },
        ],
        "taxonomies": [
            {
                "name": "tag",
                "label": "Tags",
                "labelSingular": "Tag",
                "hierarchical": False,
                "collections": ["posts"],
                "terms": [{"slug": s, "label": label} for s, label in sorted(tags.items())],
            }
        ],
        "menus": [
            {
                "name": "primary",
                "label": "Primary Navigation",
                "items": [
                    {"type": "custom", "label": "Artists", "url": "/artists"},
                    {"type": "custom", "label": "Posts", "url": "/posts"},
                ],
            }
        ],
        "content": {"posts": entries, "artists": artists},
    }

    SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEED_PATH.write_text(json.dumps(seed, ensure_ascii=False, indent="\t") + "\n")
    SQL_PATH.write_text("-- seed 適用後に実行: Tumblr の投稿日時を公開日時に反映する\n" + "\n".join(sql_lines) + "\n")
    ID_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    ID_MAP_PATH.write_text(json.dumps(id_map, ensure_ascii=False, indent=2) + "\n")

    print(f"投稿 {len(entries)} 件 / タグ {len(tags)} 件 / アーティスト {len(artists)} 件")
    print(f"→ {SEED_PATH.relative_to(ROOT)}, {SQL_PATH.relative_to(ROOT)}, {ID_MAP_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
