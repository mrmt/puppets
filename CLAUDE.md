# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

[puppets.jp](https://puppets.jp) の運営リポジトリ。静的HTMLのイベント告知ページと、TumblrブログのMarkdownベースコンテンツ管理の2軸で構成される。ビルドツール・テストフレームワークは存在しない。

## 構造

```
puppets/
├── content/
│   └── posts/              # Tumblr投稿のMarkdownファイル（YAML frontmatter付き）
├── custom-pages/
│   └── fa/index.html       # Fourier Analyzeイベント告知ページ（静的HTML）
├── scripts/
│   ├── auth.py             # OAuth 2.0認証（初回・トークン期限切れ時のみ実行）
│   ├── client.py           # Tumblr API直接操作CLI（デバッグ・確認用）
│   └── sync.py             # Tumblr ↔ ローカルの双方向同期エンジン
└── .tumblr-manifest.json   # 同期状態トラッキング（手動編集不可）
```

## ローカル確認（静的サイト）

```bash
python -m http.server 8000
# ブラウザで http://localhost:8000/custom-pages/fa/ を開く
```

## Tumblr コンテンツ管理

### 初回セットアップ

```bash
uv run scripts/auth.py       # 1Password CLI経由でOAuth認証、トークンをKeychain保存
uv run scripts/sync.py pull  # Tumblrから全件ダウンロード
```

`auth.py` はポート3000でローカルHTTPサーバーを起動してOAuthコールバックを受け取る。PKCE方式。

### 日常の操作

```bash
uv run scripts/sync.py status         # ローカルの変更状況を確認（API呼び出しなし）
uv run scripts/sync.py push --dry-run # 反映内容のプレビュー
uv run scripts/sync.py push           # Tumblrへ反映
uv run scripts/sync.py pull           # Tumblrの最新状態をローカルへ同期
```

### 新規投稿の作り方

`content/posts/new_ファイル名.md` を作成する（`new_` プレフィックスが必須）。`push` 後に `{id}_{type}_{slug}.md` へ自動リネームされる。

**テキスト投稿:**
```markdown
---
id: null
type: text
title: タイトル
tags: [tag1, tag2]
state: published
---

本文をMarkdownで書く
```

**画像投稿:**
```markdown
---
id: null
type: photo
tags: [photo]
state: published
photos:
  - local_path: "images/photo.jpg"
    alt_text: ""
---

キャプション
```

対応投稿タイプ: `text` / `photo` / `video` / `quote` / `link`

### 既存投稿の編集・削除

- **編集**: `content/posts/*.md` を直接編集 → `push`
- **削除**: ファイルを削除 → `push`（確認プロンプトあり）

## スクリプトアーキテクチャ

スクリプトはPEP 723形式（ファイル先頭に `# /// script` でインライン依存定義）。`pyproject.toml` は存在しない。

**同期の仕組み（sync.py）**

- `.tumblr-manifest.json` がすべての同期状態を管理する。スキーマ: `{ schema_version, last_pull, posts: { post_id: { file, content_hash, tumblr_updated_at, synced_at } } }`
- `status` / `push` はマニフェストのcontent_hashと現在のファイルを比較してdiffを検出（API不要）
- `push` 時に401が返るとrefresh_tokenで自動再認証
- API呼び出しは0.2秒インターバルでレート制限

**認証（auth.py）**

- Consumer Key/Secretは1Password CLI（`op`）から取得
- アクセストークンはmacOSのKeychainに保存（`keyring` ライブラリ経由）
