# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

[puppets.jp](https://puppets.jp) (puppets records) の運営リポジトリ。サイトは Astro + EmDash を Cloudflare Workers (D1 / R2 / KV) で配信している。metafictions.net / sect-commune.com と同じ構成。

2026/09 に Tumblr から移行した。Tumblr ブログは削除済み。

## 構造

```
puppets/
├── web/                    # サイト実装 (Astro + EmDash)。作業時は web/CLAUDE.md (= AGENTS.md) を参照
├── scripts/
│   ├── tumblr_to_seed.py   # Tumblr 投稿アーカイブ → EmDash seed 変換 (移行用、再実行は通常不要)
│   ├── verify_legacy_urls.py  # 旧 Tumblr URL が 301→200 になるかの機械検証
│   └── order_d1_dump.py    # wrangler d1 export の出力を外部キー順に並べ替え
├── migration/              # 移行記録 (README.md)、Tumblr 投稿のアーカイブ、Tumblr ホスト画像の原本
└── .github/workflows/      # web-ci / web-deploy / web-backup / web-link-check
```

## 記事本文はこのリポジトリに無い

投稿・アーティスト・タグの正本は Cloudflare D1 (EmDash CMS)、画像は R2 にある。

- 投稿・編集: https://puppets.jp/_emdash/admin (パスキー認証)
- `web/seed/seed.json` は移行時の初期投入データ。現在の内容とは一致しない
- `migration/tumblr-export/` は Tumblr 時代のアーカイブ (読み取り専用)

## サイト実装 (web/)

```bash
cd web
pnpm install
pnpm exec astro dev   # http://localhost:4321
pnpm typecheck
pnpm test             # vitest
pnpm test:e2e         # playwright
```

- デプロイ: `main` への push (`web/**`) で `.github/workflows/web-deploy.yml` が実行する。ルート直下を変更しても再デプロイされない
- 旧 Tumblr URL (`/post/{id}/…`, `/tagged/…`, `/rss`, `/archive`, `/page/n`) は `web/src/utils/legacy.ts` が 301 で新 URL へ解決する
  - 対応表は `web/src/utils/tumblr-id-map.json`
  - 変更したら `uv run scripts/verify_legacy_urls.py https://puppets.jp` で確認する

## Cloudflare

- アカウント: 852a5c2aca3a6ca2e6258627e78e86c8 (metafictions / sect-commune と共用)
- Worker `puppets-web`、D1 `puppets-web`、R2 `puppets-media`、KV `puppets-web-SESSION`
- DNS: puppets.jp ゾーンは Cloudflare。Worker のカスタムドメインとして割り当てている
- バックアップ: `web-backup.yml` が毎日 D1 dump を `puppets-backups` に保存し、R2 を `puppets-media-backup` にミラーする

## スクリプト

Python スクリプトは PEP 723 形式 (ファイル先頭の `# /// script` で依存を定義) で、`uv run` で実行する。`pyproject.toml` は無い。
