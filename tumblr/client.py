#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx",
#   "keyring",
# ]
# ///
"""
Tumblr API クライアント
keyring に保存されたトークンを使って Tumblr API を操作する。

使い方:
  uv run tumblr/client.py posts          # 投稿一覧
  uv run tumblr/client.py post <id>      # 投稿詳細
  uv run tumblr/client.py create-text    # テキスト投稿（対話形式）
  uv run tumblr/client.py create-photo   # 画像投稿（対話形式）
  uv run tumblr/client.py delete <id>    # 投稿削除
"""

import json
import sys
from pathlib import Path

import httpx
import keyring

KEYRING_SERVICE = "puppets-tumblr"
BLOG_IDENTIFIER = "puppets.jp"
API_BASE = "https://api.tumblr.com/v2"


def load_token() -> dict:
    token_json = keyring.get_password(KEYRING_SERVICE, "token_json")
    if not token_json:
        print("トークンが見つかりません。先に auth.py を実行してください。")
        sys.exit(1)
    return json.loads(token_json)


def make_client() -> httpx.Client:
    token = load_token()
    access_token = token["access_token"]
    return httpx.Client(
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )


def cmd_posts(client: httpx.Client, args: list[str]):
    """投稿一覧を表示する"""
    limit = int(args[0]) if args else 20
    resp = client.get(f"{API_BASE}/blog/{BLOG_IDENTIFIER}/posts", params={"limit": limit})
    resp.raise_for_status()
    data = resp.json()

    posts = data["response"]["posts"]
    print(f"投稿数: {len(posts)} 件\n")
    for p in posts:
        print(f"[{p['id']}] {p['type']:10s} {p.get('date','')[:10]}  {_post_summary(p)}")


def _post_summary(p: dict) -> str:
    if p["type"] == "text":
        return p.get("title") or (p.get("body", "")[:50].replace("\n", " "))
    if p["type"] == "photo":
        return p.get("caption", "")[:50].replace("\n", " ") or "(画像)"
    return p.get("summary", "")[:50]


def cmd_post(client: httpx.Client, args: list[str]):
    """投稿詳細を表示する"""
    if not args:
        print("使い方: post <id>")
        sys.exit(1)
    post_id = args[0]
    resp = client.get(f"{API_BASE}/blog/{BLOG_IDENTIFIER}/posts", params={"id": post_id})
    resp.raise_for_status()
    posts = resp.json()["response"]["posts"]
    if not posts:
        print(f"投稿 {post_id} が見つかりません。")
        sys.exit(1)
    print(json.dumps(posts[0], ensure_ascii=False, indent=2))


def cmd_create_text(client: httpx.Client, _args: list[str]):
    """テキスト投稿を作成する"""
    title = input("タイトル（省略可）: ").strip()
    print("本文（空行で終了）:")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    body = "\n".join(lines)
    tags_input = input("タグ（カンマ区切り、省略可）: ").strip()
    tags = [t.strip() for t in tags_input.split(",") if t.strip()]

    payload: dict = {"type": "text", "body": body}
    if title:
        payload["title"] = title
    if tags:
        payload["tags"] = ",".join(tags)

    resp = client.post(f"{API_BASE}/blog/{BLOG_IDENTIFIER}/post", data=payload)
    resp.raise_for_status()
    post_id = resp.json()["response"]["id"]
    print(f"\n投稿しました！ ID: {post_id}")
    print(f"URL: https://{BLOG_IDENTIFIER}/post/{post_id}")


def cmd_create_photo(client: httpx.Client, _args: list[str]):
    """画像投稿を作成する"""
    path_str = input("画像ファイルパス: ").strip()
    path = Path(path_str)
    if not path.exists():
        print(f"ファイルが見つかりません: {path}")
        sys.exit(1)

    caption = input("キャプション（省略可）: ").strip()
    tags_input = input("タグ（カンマ区切り、省略可）: ").strip()
    tags = [t.strip() for t in tags_input.split(",") if t.strip()]

    token = load_token()
    with httpx.Client(headers={"Authorization": f"Bearer {token['access_token']}"}, timeout=60) as upload_client:
        with open(path, "rb") as f:
            files = {"data[0]": (path.name, f, "image/jpeg")}
            data: dict = {"type": "photo"}
            if caption:
                data["caption"] = caption
            if tags:
                data["tags"] = ",".join(tags)
            resp = upload_client.post(
                f"{API_BASE}/blog/{BLOG_IDENTIFIER}/post",
                data=data,
                files=files,
            )
    resp.raise_for_status()
    post_id = resp.json()["response"]["id"]
    print(f"\n投稿しました！ ID: {post_id}")
    print(f"URL: https://{BLOG_IDENTIFIER}/post/{post_id}")


def cmd_delete(client: httpx.Client, args: list[str]):
    """投稿を削除する"""
    if not args:
        print("使い方: delete <id>")
        sys.exit(1)
    post_id = args[0]
    confirm = input(f"投稿 {post_id} を削除しますか？ [y/N]: ").strip().lower()
    if confirm != "y":
        print("キャンセルしました。")
        return
    resp = client.post(f"{API_BASE}/blog/{BLOG_IDENTIFIER}/post/delete", data={"id": post_id})
    resp.raise_for_status()
    print(f"削除しました。ID: {post_id}")


COMMANDS = {
    "posts": cmd_posts,
    "post": cmd_post,
    "create-text": cmd_create_text,
    "create-photo": cmd_create_photo,
    "delete": cmd_delete,
}


def main():
    args = sys.argv[1:]
    if not args or args[0] not in COMMANDS:
        print("使い方:")
        for cmd in COMMANDS:
            print(f"  uv run tumblr/client.py {cmd}")
        sys.exit(1)

    cmd = args[0]
    with make_client() as client:
        COMMANDS[cmd](client, args[1:])


if __name__ == "__main__":
    main()
