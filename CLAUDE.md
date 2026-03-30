# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

静的HTMLベースのイベント告知サイト。ビルドツール・パッケージマネージャー・テストフレームワークは存在しない。

## 構造

```
puppets.jp/
├── fa/index.html   # Fourier Analyzeイベント告知ページ
└── assets/         # 画像アセット（JPG, PSD）
```

## ローカル確認

```bash
python -m http.server 8000
# ブラウザで http://localhost:8000/puppets.jp/fa/ を開く
```

## デプロイ

静的ファイルをそのままWebサーバーに配置する。`puppets.jp` ドメインで公開。

## Tumblr コンテンツ管理

`content/posts/` に Markdown + YAML frontmatter 形式で投稿を管理する。

### 初回セットアップ

```bash
uv run scripts/auth.py   # 1Password から OAuth 認証（初回・トークン期限切れ時）
uv run scripts/sync.py pull  # Tumblr から全件ダウンロード
```

### 日常の操作

```bash
uv run scripts/sync.py status         # ローカルの変更状況を確認
uv run scripts/sync.py push --dry-run # 反映内容のプレビュー
uv run scripts/sync.py push           # Tumblr へ反映
uv run scripts/sync.py pull           # Tumblr の最新状態をローカルへ同期
```

### 新規投稿の作り方

`content/posts/new_ファイル名.md` を作成する（`new_` プレフィックスが必須）。

**テキスト投稿:**
```markdown
---
id: null
type: text
title: タイトル
tags: [tag1, tag2]
state: published
---

本文を Markdown で書く
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

`push` 後にファイルは `{id}_{type}_{slug}.md` にリネームされる。

### 既存投稿の編集・削除

- **編集**: `content/posts/*.md` を直接編集 → `push`
- **削除**: ファイルを削除 → `push`（確認プロンプトあり）
