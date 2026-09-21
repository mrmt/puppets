# puppets

[puppets.jp](https://puppets.jp) (puppets records) のサイト実装と運営リポジトリ。

Astro + [EmDash](https://github.com/emdash-cms/emdash) を Cloudflare Workers で配信している。2026/09 に Tumblr から移行した (経緯は [migration/README.md](migration/README.md))。

## 投稿の管理

投稿・アーティスト・タグは EmDash の管理画面で編集する: https://puppets.jp/_emdash/admin

記事本文はこのリポジトリには無い (Cloudflare D1 / R2 に格納)。

## 開発

```bash
cd web
pnpm install
pnpm exec astro dev
```

詳細は [web/README.md](web/README.md) を参照。`main` に push するとデプロイされる。
