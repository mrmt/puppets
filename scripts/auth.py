#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx",
#   "keyring",
# ]
# ///
"""
Tumblr OAuth 2.0 認証スクリプト
1Password CLI (op) から Consumer Key/Secret を取得し、
アクセストークンを keyring に保存する。

使い方:
  uv run scripts/auth.py
"""

import base64
import hashlib
import json
import secrets
import subprocess
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import httpx
import keyring

KEYRING_SERVICE = "puppets-tumblr"
AUTH_URL = "https://www.tumblr.com/oauth2/authorize"
TOKEN_URL = "https://api.tumblr.com/v2/oauth2/token"
CALLBACK_PORT = 3000
CALLBACK_URL = f"http://localhost:{CALLBACK_PORT}/callback"

OP_ACCOUNT = "CADSSSQC7NBENEMH33SC2BD7QU"
OP_ITEM = "puppets.jp tumblr site"
OP_VAULT = "music"

_auth_code: str | None = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<h1>認証完了！</h1><p>このタブを閉じてください。</p>".encode()
            )
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def op_get_credentials() -> tuple[str, str]:
    """1Password CLI から Consumer Key / Secret を取得する"""
    result = subprocess.run(
        ["op", "item", "get", "--account", OP_ACCOUNT, OP_ITEM,
         "--vault", OP_VAULT, "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)

    # Consumer Key は URL フィールドに格納されている
    consumer_key = next(
        u["href"] for u in data.get("urls", [])
        if u.get("label") == "OAuth Consumer Key"
    )

    # Consumer Secret は通常フィールドに格納されている
    secret_result = subprocess.run(
        ["op", "item", "get", "--account", OP_ACCOUNT, OP_ITEM,
         "--vault", OP_VAULT, "--fields", "OAuth Consumer Secret", "--reveal"],
        capture_output=True,
        text=True,
        check=True,
    )
    consumer_secret = secret_result.stdout.strip()

    return consumer_key, consumer_secret


def generate_pkce() -> tuple[str, str]:
    """PKCE の code_verifier と code_challenge を生成する"""
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


def get_token(consumer_key: str, consumer_secret: str) -> dict:
    """OAuth 2.0 フローでアクセストークンを取得する"""
    verifier, challenge = generate_pkce()
    state = secrets.token_urlsafe(16)

    params = {
        "client_id": consumer_key,
        "response_type": "code",
        "scope": "basic write offline_access",
        "redirect_uri": CALLBACK_URL,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    server = HTTPServer(("localhost", CALLBACK_PORT), CallbackHandler)
    thread = Thread(target=server.handle_request)
    thread.start()

    print("ブラウザを開いて Tumblr にログインしてください...")
    webbrowser.open(auth_url)
    thread.join(timeout=120)

    if _auth_code is None:
        raise RuntimeError("認証コードを取得できませんでした（タイムアウト）")

    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": _auth_code,
            "client_id": consumer_key,
            "client_secret": consumer_secret,
            "redirect_uri": CALLBACK_URL,
            "code_verifier": verifier,
        },
    )
    resp.raise_for_status()
    return resp.json()


def main():
    print("=== Tumblr OAuth 認証 ===\n")

    existing = keyring.get_password(KEYRING_SERVICE, "token_json")
    if existing:
        ans = input("既存のトークンが見つかりました。再取得しますか？ [y/N]: ").strip().lower()
        if ans != "y":
            print("既存のトークンを使用します。")
            return

    print("1Password からクレデンシャルを取得中...")
    consumer_key, consumer_secret = op_get_credentials()
    print("取得完了。\n")

    token = get_token(consumer_key, consumer_secret)

    keyring.set_password(KEYRING_SERVICE, "consumer_key", consumer_key)
    keyring.set_password(KEYRING_SERVICE, "consumer_secret", consumer_secret)
    keyring.set_password(KEYRING_SERVICE, "token_json", json.dumps(token))

    print(f"\n認証成功！トークンを keyring に保存しました。")
    print(f"  scope: {token.get('scope', '')}")
    print(f"  expires_in: {token.get('expires_in', 'N/A')} 秒")


if __name__ == "__main__":
    main()
