# puppets

[puppets.jp](https://puppets.jp) のサイトおよびコンテンツ管理リポジトリ。

サイトは Tumblr でホスティング。このリポジトリで投稿コンテンツを Markdown ファイルとして管理し、Tumblr API 経由で同期する。

## セットアップ

[uv](https://docs.astral.sh/uv/) が必要。

```bash
uv run scripts/auth.py       # 初回認証（1Password から OAuth トークン取得）
uv run scripts/sync.py pull  # Tumblr の投稿をローカルへダウンロード
```

## 投稿の管理

```bash
uv run scripts/sync.py status          # ローカルの変更状況を確認
uv run scripts/sync.py push --dry-run  # 反映内容のプレビュー
uv run scripts/sync.py push            # Tumblr へ反映
uv run scripts/sync.py pull            # Tumblr の最新状態をローカルへ同期
```

### 新規投稿

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

`push` 後、ファイルは `{id}_{type}_{slug}.md` に自動リネームされる。

### 既存投稿の編集・削除

- **編集**: `content/posts/*.md` を直接編集 → `push`
- **削除**: ファイルを削除 → `push`（確認プロンプトあり）
