---
name: check-404-links
description: サイトのコンテンツに含まれるリンクの404をチェックする。リンク切れ確認、ブロークンリンク調査、404監査のリクエスト時に使用する。
---

# 404リンクチェック

本番サイト `https://metafictions.net` をクロールしてブロークンリンク(404等)を検出するスキル。

## 手順

### 1. リンクチェック実行

`linkinator`で本番サイト全体をクロール:

```bash
npx --yes linkinator https://metafictions.net --recurse --format json 2>/dev/null
```

内部リンクのみチェックしたい場合は `--skip` で外部ドメインを除外:

```bash
npx --yes linkinator https://metafictions.net --recurse --skip "^(?!https://metafictions.net)" --format json 2>/dev/null
```

### 2. 結果の解析

JSON出力から`status >= 400`のリンクを抽出して報告:

- 壊れたURL
- そのリンクが存在するページ(parent)
- HTTPステータスコード

### 3. サマリー報告

- チェックした総リンク数
- 壊れたリンク数
- 各ブロークンリンクの詳細一覧(URL、参照元ページ、ステータスコード)

## 注意事項

- YouTube, Twitter, SNS系は403/429を返しやすいのでfalse positiveに注意
- `--concurrency` オプションで並列数を調整可能 (デフォルト: 100、負荷軽減なら10程度)
- 特定ページのみチェックする場合はURLを `https://metafictions.net/path` に変更する
- タイムアウトが多い場合は `--timeout 10000` (ms)を追加する
