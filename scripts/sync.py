#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx",
#   "keyring",
#   "python-frontmatter",
#   "python-slugify",
# ]
# ///
"""
Tumblr コンテンツ同期スクリプト

使い方:
  uv run scripts/sync.py pull           # Tumblr → ローカルへ全件同期
  uv run scripts/sync.py push           # ローカル差分 → Tumblr へ反映
  uv run scripts/sync.py push --dry-run # 変更内容の確認のみ（API呼び出しなし）
  uv run scripts/sync.py status         # ローカル差分サマリー（API不使用）
"""

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import frontmatter
import httpx
import keyring
from slugify import slugify

# --- 定数 ---

KEYRING_SERVICE = "puppets-tumblr"
BLOG_IDENTIFIER = "puppets.jp"
API_BASE = "https://api.tumblr.com/v2"

CONTENT_DIR = Path("content/posts")
MANIFEST_PATH = Path(".tumblr-manifest.json")


# --- トークン管理 ---

def load_token() -> dict:
    token_json = keyring.get_password(KEYRING_SERVICE, "token_json")
    if not token_json:
        print("トークンが見つかりません。先に scripts/auth.py を実行してください。")
        sys.exit(1)
    return json.loads(token_json)


def refresh_access_token(token: dict) -> dict | None:
    """リフレッシュトークンでアクセストークンを更新する"""
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        return None
    consumer_key = keyring.get_password(KEYRING_SERVICE, "consumer_key")
    consumer_secret = keyring.get_password(KEYRING_SERVICE, "consumer_secret")
    if not consumer_key or not consumer_secret:
        return None
    try:
        resp = httpx.post(
            f"{API_BASE}/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": consumer_key,
                "client_secret": consumer_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        new_token = resp.json()
        keyring.set_password(KEYRING_SERVICE, "token_json", json.dumps(new_token))
        return new_token
    except Exception:
        return None


def make_client() -> httpx.Client:
    token = load_token()
    return httpx.Client(
        headers={"Authorization": f"Bearer {token['access_token']}"},
        timeout=60,
        event_hooks={"response": [_handle_auth_error]},
    )


def _handle_auth_error(response: httpx.Response):
    """401 を受け取ったらトークンをリフレッシュして再試行（1回のみ）"""
    if response.status_code == 401 and not getattr(response.request, "_refreshed", False):
        token = load_token()
        new_token = refresh_access_token(token)
        if new_token:
            response.request.headers["Authorization"] = f"Bearer {new_token['access_token']}"
            response.request._refreshed = True  # type: ignore[attr-defined]
        else:
            print("トークンの更新に失敗しました。scripts/auth.py を再実行してください。")
            sys.exit(1)


# --- マニフェスト管理 ---

def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"schema_version": 1, "last_pull": None, "posts": {}}


def save_manifest(manifest: dict):
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# --- ユーティリティ ---

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode()).hexdigest()


def make_slug(post: dict) -> str:
    """投稿からスラッグを生成する"""
    # Tumblr の slug フィールドを優先
    if post.get("slug"):
        return slugify(post["slug"])[:50]
    # タイトルから生成
    if post.get("title"):
        return slugify(post["title"])[:50]
    # サマリーから生成
    summary = post.get("summary", "")
    if summary:
        return slugify(summary)[:50]
    return f"post-{post['id']}"


def post_file_path(post_id: str, post_type: str, slug: str) -> Path:
    return CONTENT_DIR / f"{post_id}_{post_type}_{slug}.md"


def extract_id_from_filename(filename: str) -> str | None:
    """ファイル名から Tumblr ID を抽出する（数字始まりのもの）"""
    parts = filename.split("_")
    if parts and parts[0].isdigit():
        return parts[0]
    return None


# --- Tumblr → Markdown 変換 ---

def tumblr_post_to_markdown(post: dict) -> str:
    """Tumblr API レスポンスを Markdown ファイル形式に変換する"""
    meta: dict = {
        "id": post["id"],
        "type": post["type"],
        "slug": post.get("slug") or make_slug(post),
        "tags": post.get("tags", []),
        "date": post.get("date", ""),
        "state": post.get("state", "published"),
    }

    if post["type"] == "text":
        meta["title"] = post.get("title", "")
        body = post.get("body", "")

    elif post["type"] == "photo":
        photos = []
        for p in post.get("photos", []):
            orig = p.get("original_size", {})
            photos.append({
                "url": orig.get("url", ""),
                "alt_text": p.get("alt_text", "") or "",
            })
        meta["photos"] = photos
        body = post.get("caption", "")

    elif post["type"] == "video":
        # YouTube 等の外部動画は permalink_url に URL が入る
        video_url = (
            post.get("permalink_url")
            or post.get("video_url")
            or ""
        )
        meta["video_url"] = video_url
        meta["video_type"] = post.get("video_type", "")
        meta["thumbnail_url"] = post.get("thumbnail_url", "")
        body = post.get("caption", "")

    elif post["type"] == "quote":
        meta["source"] = post.get("source", "")
        body = post.get("text", "")

    elif post["type"] == "link":
        meta["url"] = post.get("url", "")
        meta["link_title"] = post.get("title", "")
        meta["description"] = post.get("description", "")
        body = post.get("description", "")

    else:
        body = post.get("body", post.get("caption", ""))

    post_obj = frontmatter.Post(body, **meta)
    return frontmatter.dumps(post_obj) + "\n"


# --- Markdown → Tumblr API パラメータ変換 ---

def markdown_to_tumblr_params(post_obj: frontmatter.Post, base_dir: Path) -> tuple[dict, dict]:
    """
    frontmatter + body から Tumblr API 用の data と files を生成する。
    Returns: (data_dict, files_dict)
    """
    meta = post_obj.metadata
    post_type = meta.get("type", "text")
    state = meta.get("state", "published")
    tags = meta.get("tags", [])
    tag_str = ",".join(str(t) for t in tags) if tags else ""

    data: dict = {
        "type": post_type,
        "state": state,
    }
    if tag_str:
        data["tags"] = tag_str

    files: dict = {}

    if post_type == "text":
        data["title"] = meta.get("title", "")
        data["body"] = post_obj.content

    elif post_type == "photo":
        caption = post_obj.content.strip()
        if caption:
            data["caption"] = caption
        photos = meta.get("photos", [])
        for i, photo in enumerate(photos):
            if "local_path" in photo:
                img_path = base_dir / photo["local_path"]
                if not img_path.exists():
                    print(f"  警告: 画像ファイルが見つかりません: {img_path}")
                    continue
                mime = "image/jpeg" if img_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
                files[f"data[{i}]"] = (img_path.name, open(img_path, "rb"), mime)
            elif "url" in photo:
                # URL の場合は source パラメータ（1枚目のみ）
                if i == 0:
                    data["source"] = photo["url"]

    elif post_type == "video":
        data["caption"] = post_obj.content.strip()
        if meta.get("video_url"):
            data["embed"] = meta["video_url"]

    elif post_type == "quote":
        data["quote"] = post_obj.content.strip()
        if meta.get("source"):
            data["source"] = meta["source"]

    elif post_type == "link":
        data["url"] = meta.get("url", "")
        data["title"] = meta.get("link_title", "")
        data["description"] = post_obj.content.strip()

    return data, files


# --- API ラッパー ---

def api_get_all_posts(client: httpx.Client) -> list[dict]:
    """全投稿を取得する（ページング自動処理）"""
    all_posts = []
    offset = 0
    while True:
        resp = client.get(
            f"{API_BASE}/blog/{BLOG_IDENTIFIER}/posts",
            params={"limit": 20, "offset": offset},
        )
        resp.raise_for_status()
        posts = resp.json()["response"]["posts"]
        if not posts:
            break
        all_posts.extend(posts)
        print(f"  {len(all_posts)} 件取得中...", end="\r", flush=True)
        offset += len(posts)
        # レート制限対策
        if len(posts) == 20:
            time.sleep(0.2)
    print()
    return all_posts


def api_create_post(client: httpx.Client, data: dict, files: dict) -> str:
    """投稿を作成して新しい ID を返す"""
    resp = client.post(
        f"{API_BASE}/blog/{BLOG_IDENTIFIER}/post",
        data=data,
        files=files if files else None,
    )
    resp.raise_for_status()
    return str(resp.json()["response"]["id"])


def api_edit_post(client: httpx.Client, post_id: str, data: dict, files: dict):
    """投稿を編集する"""
    data["id"] = post_id
    resp = client.post(
        f"{API_BASE}/blog/{BLOG_IDENTIFIER}/post/edit",
        data=data,
        files=files if files else None,
    )
    resp.raise_for_status()


def api_delete_post(client: httpx.Client, post_id: str):
    """投稿を削除する"""
    resp = client.post(
        f"{API_BASE}/blog/{BLOG_IDENTIFIER}/post/delete",
        data={"id": post_id},
    )
    resp.raise_for_status()


# --- コマンド: pull ---

def cmd_pull(args: list[str]):
    """Tumblr → ローカルへ全件同期"""
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()

    print("Tumblr から投稿を取得中...")
    with make_client() as client:
        all_posts = api_get_all_posts(client)
    print(f"合計 {len(all_posts)} 件取得\n")

    # Tumblr 側で削除された投稿をローカルからも削除
    remote_ids = {str(p["id"]) for p in all_posts}
    for post_id in list(manifest["posts"].keys()):
        if post_id not in remote_ids:
            entry = manifest["posts"][post_id]
            file_path = Path(entry["file"])
            if file_path.exists():
                file_path.unlink()
                print(f"削除（Tumblr側でなくなった）: {file_path.name}")
            del manifest["posts"][post_id]

    created = updated = skipped = 0
    for post in all_posts:
        post_id = str(post["id"])
        entry = manifest["posts"].get(post_id)
        tumblr_updated = post.get("date", "")

        # 更新なし → スキップ
        if entry and entry.get("tumblr_updated_at") == tumblr_updated:
            # ファイルが消えていた場合は再生成
            if Path(entry["file"]).exists():
                skipped += 1
                continue

        # ファイルパスの決定
        if entry and Path(entry["file"]).exists():
            file_path = Path(entry["file"])
        else:
            slug = make_slug(post)
            file_path = post_file_path(post_id, post["type"], slug)

        content = tumblr_post_to_markdown(post)
        file_path.write_text(content, encoding="utf-8")

        is_new = entry is None
        manifest["posts"][post_id] = {
            "file": str(file_path),
            "content_hash": compute_hash(content),
            "tumblr_updated_at": tumblr_updated,
            "synced_at": now_iso(),
        }

        label = "新規" if is_new else "更新"
        print(f"  [{label}] {file_path.name}")
        if is_new:
            created += 1
        else:
            updated += 1

    manifest["last_pull"] = now_iso()
    save_manifest(manifest)

    print(f"\n完了: 新規={created} 更新={updated} スキップ={skipped}")


# --- コマンド: push ---

def cmd_push(args: list[str]):
    """ローカル差分を Tumblr へ反映する"""
    dry_run = "--dry-run" in args
    if dry_run:
        print("=== DRY RUN モード（実際の変更はしません）===\n")

    manifest = load_manifest()
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    client = make_client() if not dry_run else None

    # --- 1. 新規投稿（new_*.md） ---
    new_files = sorted(CONTENT_DIR.glob("new_*.md"))
    if new_files:
        print(f"[新規投稿] {len(new_files)} 件")
    for file_path in new_files:
        post_obj = frontmatter.load(str(file_path))
        meta = post_obj.metadata
        post_type = meta.get("type", "text")
        print(f"  {file_path.name} ({post_type})")

        if dry_run:
            continue

        data, files = markdown_to_tumblr_params(post_obj, file_path.parent)
        try:
            post_id = api_create_post(client, data, files)
        finally:
            for f in files.values():
                f[1].close()

        # frontmatter を更新して ID と date を書き込む
        meta["id"] = int(post_id)
        meta["date"] = now_iso()
        meta.pop("local_path", None)
        # photos の local_path を url に書き換え（取得できないため URL は暫定）
        if "photos" in meta:
            for photo in meta["photos"]:
                if "local_path" in photo:
                    photo.pop("local_path")
                    photo["url"] = f"(tumblr:{post_id})"

        new_slug = meta.get("slug") or make_slug({"id": post_id, "title": meta.get("title", ""), "summary": ""})
        new_path = post_file_path(post_id, post_type, slugify(new_slug)[:50] if new_slug else post_id)
        new_post_obj = frontmatter.Post(post_obj.content, **meta)
        new_path.write_text(frontmatter.dumps(new_post_obj) + "\n", encoding="utf-8")
        file_path.unlink()

        content = new_path.read_text(encoding="utf-8")
        manifest["posts"][post_id] = {
            "file": str(new_path),
            "content_hash": compute_hash(content),
            "tumblr_updated_at": meta["date"],
            "synced_at": now_iso(),
        }
        print(f"    → 作成完了 ID:{post_id} → {new_path.name}")

    # --- 2. 既存投稿の変更検出 ---
    local_ids: set[str] = set()
    changed_files = []
    for file_path in sorted(CONTENT_DIR.glob("[0-9]*.md")):
        post_id = extract_id_from_filename(file_path.name)
        if not post_id:
            continue
        local_ids.add(post_id)

        entry = manifest["posts"].get(post_id)
        content = file_path.read_text(encoding="utf-8")
        current_hash = compute_hash(content)

        if entry and entry.get("content_hash") == current_hash:
            continue  # 変更なし

        changed_files.append((post_id, file_path, entry))

    if changed_files:
        print(f"\n[更新] {len(changed_files)} 件")
    for post_id, file_path, entry in changed_files:
        print(f"  {file_path.name}")
        if dry_run:
            continue
        post_obj = frontmatter.load(str(file_path))
        data, files = markdown_to_tumblr_params(post_obj, file_path.parent)
        try:
            api_edit_post(client, post_id, data, files)
        finally:
            for f in files.values():
                f[1].close()
        content = file_path.read_text(encoding="utf-8")
        manifest["posts"][post_id] = {
            "file": str(file_path),
            "content_hash": compute_hash(content),
            "tumblr_updated_at": manifest["posts"].get(post_id, {}).get("tumblr_updated_at", ""),
            "synced_at": now_iso(),
        }
        print(f"    → 更新完了")

    # --- 3. 削除検出 ---
    manifest_ids = set(manifest["posts"].keys())
    deleted_ids = manifest_ids - local_ids
    # new_*.md 由来はスキップ（まだ push 前）
    deleted_ids -= {id for id in deleted_ids if not id.isdigit()}

    if deleted_ids:
        print(f"\n[削除対象] {len(deleted_ids)} 件")
        for post_id in sorted(deleted_ids):
            entry = manifest["posts"][post_id]
            print(f"  ID:{post_id}  {entry['file']}")
            if dry_run:
                continue
            ans = input(f"  Tumblr から削除しますか？ [y/N]: ").strip().lower()
            if ans == "y":
                try:
                    api_delete_post(client, post_id)
                    del manifest["posts"][post_id]
                    print(f"    → 削除完了")
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        del manifest["posts"][post_id]
                        print(f"    → Tumblr 側にすでに存在しないため、マニフェストから削除")
                    else:
                        raise
            else:
                print(f"    → スキップ")

    if not dry_run and client:
        client.close()

    save_manifest(manifest)

    if dry_run:
        print("\n(DRY RUN 完了。実際の変更はありません)")
    else:
        print("\npush 完了")


# --- コマンド: status ---

def cmd_status(_args: list[str]):
    """ローカル差分サマリーを表示する（API不使用）"""
    manifest = load_manifest()

    if manifest.get("last_pull"):
        print(f"最終 pull: {manifest['last_pull']}\n")
    else:
        print("まだ pull を実行していません。\n")

    new_files = sorted(CONTENT_DIR.glob("new_*.md")) if CONTENT_DIR.exists() else []
    changed = []
    local_ids: set[str] = set()

    if CONTENT_DIR.exists():
        for file_path in sorted(CONTENT_DIR.glob("[0-9]*.md")):
            post_id = extract_id_from_filename(file_path.name)
            if not post_id:
                continue
            local_ids.add(post_id)
            entry = manifest["posts"].get(post_id)
            content = file_path.read_text(encoding="utf-8")
            if entry and entry.get("content_hash") != compute_hash(content):
                changed.append(file_path)

    deleted_ids = set(manifest["posts"].keys()) - local_ids

    if not new_files and not changed and not deleted_ids:
        print("差分なし。Tumblr と同期済みです。")
        return

    if new_files:
        print(f"[新規投稿] {len(new_files)} 件")
        for f in new_files:
            print(f"  + {f.name}")

    if changed:
        print(f"\n[変更あり] {len(changed)} 件")
        for f in changed:
            print(f"  M {f.name}")

    if deleted_ids:
        print(f"\n[削除予定] {len(deleted_ids)} 件")
        for post_id in sorted(deleted_ids):
            entry = manifest["posts"][post_id]
            print(f"  - {entry['file']} (ID:{post_id})")

    print(f"\n`uv run scripts/sync.py push --dry-run` で詳細を確認できます。")


# --- エントリポイント ---

COMMANDS = {
    "pull": cmd_pull,
    "push": cmd_push,
    "status": cmd_status,
}


def main():
    args = sys.argv[1:]
    if not args or args[0] not in COMMANDS:
        print(__doc__)
        sys.exit(1)

    cmd = args[0]
    COMMANDS[cmd](args[1:])


if __name__ == "__main__":
    main()
