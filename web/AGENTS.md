This is an EmDash site -- a CMS built on Astro with a full admin UI.

## Commands

```bash
npx emdash dev        # Start dev server (runs migrations, seeds, generates types)
npx emdash types      # Regenerate TypeScript types from schema
npx emdash seed seed/seed.json --validate  # Validate seed file

pnpm typecheck        # astro check (型検査)
pnpm test             # vitest 単体テスト (src/**/*.test.ts)
pnpm test:e2e         # playwright E2E (e2e/*.spec.ts, dev サーバー自動起動)
```

## CI/CD

workflow はリポジトリルートの `.github/workflows/` にある (`web/` 配下ではない)。

- `web-ci.yml` — `web/**` を変更する PR と main 以外 push で typecheck/test/build/e2e を並列実行
- `web-deploy.yml` — `web/**` を変更する main push で typecheck→test→build→Cloudflare Workers デプロイ
- `web-backup.yml` — 日次 18:00 UTC で D1 の SQL dump と R2 メディアを別 R2 バケット (`puppets-backups` / `puppets-media-backup`) へバックアップ
- `web-link-check.yml` — 日次 00:00 UTC で lychee によるリンク切れチェック、検出時は Issue 作成

## puppets.jp 固有

- コレクション: `posts` (動画は `video_url` フィールド、写真は `photos` json フィールド)、`pages`、`artists` (`tag` が一致するタグの投稿をアーティストページに集約)
- 旧 Tumblr URL (`/post/{id}/…`, `/tagged/…`, `/rss`, `/archive`, `/page/n`) は `src/utils/legacy.ts` で解決して 301。対応表 `src/utils/tumblr-id-map.json` は `scripts/tumblr_to_seed.py` が生成する
- `seed/seed.json` は Tumblr からの移行データ (生成物)。初回セットアップ時に投入され、その後の正本は D1。公開日時は seed に載らないため投入後に `seed/published-at.sql` を流す
- YouTube 埋め込みは Cookie 同意不要にするため `youtube-nocookie.com` を使う
- リンクだけの段落 (Spotify / Apple Music / YouTube) は表示時にプレイヤーへ変換する (`src/utils/embed.ts`)
- OGP 画像・カードのサムネイルは `featured_image` (EmDash メディア) → 写真 → YouTube サムネイル → `public/og.png`。外部取得はしない (`scripts/backfill_og_images.py` が featured_image を埋める)

The admin UI is at `http://localhost:4321/_emdash/admin`.

## Key Files

| File                     | Purpose                                                                            |
| ------------------------ | ---------------------------------------------------------------------------------- |
| `astro.config.mjs`       | Astro config with `emdash()` integration, database, and storage                    |
| `src/live.config.ts`     | EmDash loader registration (boilerplate -- don't modify)                           |
| `seed/seed.json`         | Schema definition + demo content (collections, fields, taxonomies, menus, widgets) |
| `emdash-env.d.ts`        | Generated types for collections (auto-regenerated on dev server start)             |
| `src/layouts/Base.astro` | Base layout with EmDash wiring (menus, search, page contributions)                 |
| `src/pages/`             | Astro pages -- all server-rendered                                                 |

## Skills

Agent skills are in `.agents/skills/`. Load them when working on specific tasks:

- **building-emdash-site** -- Querying content, rendering Portable Text, schema design, seed files, site features (menus, widgets, search, SEO, comments, bylines). Start here.
- **creating-plugins** -- Building EmDash plugins with hooks, storage, admin UI, API routes, and Portable Text block types.
- **emdash-cli** -- CLI commands for content management, seeding, type generation, and visual editing flow.
- **check-404-links** -- Check all links in the site's content for 404 errors and broken links.

## Rules

- All content pages must be server-rendered (`output: "server"`). No `getStaticPaths()` for CMS content.
- Image fields are objects (`{ src, alt }`), not strings. Use `<Image image={...} />` from `"emdash/ui"`.
- `entry.id` is the slug (for URLs). `entry.data.id` is the database ULID (for API calls like `getEntryTerms`).
- Always call `Astro.cache.set(cacheHint)` on pages that query content.
- Taxonomy names in queries must match the seed's `"name"` field exactly (e.g., `"category"` not `"categories"`).
