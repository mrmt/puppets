# puppets-web

[puppets.jp](https://puppets.jp) の実装。Astro + [EmDash](https://github.com/emdash-cms/emdash) を Cloudflare Workers (D1 / R2 / KV) にデプロイする。

## 開発

```bash
pnpm install
pnpm exec astro dev   # http://localhost:4321 (バックグラウンド起動。停止は astro dev stop)
```

初回はローカル D1 にスキーマだけが入る。移行データ (seed) を入れるには dev-bypass でセットアップを完了させ、公開日時を反映する:

```bash
curl -s "http://localhost:4321/_emdash/api/setup/dev-bypass?redirect=/" > /dev/null
npx wrangler d1 execute puppets-web --local --file seed/published-at.sql
```

## ページ

| ページ | ルート |
|---|---|
| トップ (アーティスト + 最新投稿) | `/` |
| アーティスト | `/artists`, `/artists/:slug` |
| 投稿 | `/posts`, `/posts/:slug` |
| タグ | `/tag/:slug` |
| 検索 | `/search` |
| Fourier Analyze 2025 | `/fa` |
| RSS / サイトマップ | `/rss.xml`, `/sitemap.xml` |
| 旧 Tumblr URL | `/post/*`, `/tagged/*`, `/rss`, `/archive`, `/page/*` → 301 |

## テスト

```bash
pnpm typecheck
pnpm test        # vitest
pnpm test:e2e    # playwright (dev サーバーを自動起動)
```

## デプロイ

`main` への push (`web/**`) で `.github/workflows/web-deploy.yml` が Cloudflare Workers へデプロイする。
