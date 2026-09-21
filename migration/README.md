# puppets.jp Tumblr → EmDash 移行

Tumblr (puppetsmedia) から EmDash (Cloudflare Workers) への移行記録。構成は metafictions.net / sect-commune.com と同じ。

## 決定事項 (2026/09/21)

- デザイン: 新規 (レーベルカタログ型、ダーク基調)
- Tumblr ブログは移行・検証完了後に削除
- Cloudflare アカウント: metafictions / sect-commune と同じ (852a5c2aca3a6ca2e6258627e78e86c8)

## Cloudflare リソース (2026/09/21 作成)

| 種別 | 名前 / ID |
| --- | --- |
| Worker | puppets-web (https://puppets-web.exsead.workers.dev) |
| D1 | puppets-web / 099499c3-9a91-4337-b0bf-b542fcff54e7 |
| R2 | puppets-media (+ バックアップ用 puppets-backups / puppets-media-backup) |
| KV | puppets-web-SESSION / ecd374130792456d959b2661b4c8b84d |

## データ変換

```bash
uv run scripts/tumblr_to_seed.py   # tumblr-export/posts → web/seed/seed.json 等
```

- 投稿 107 件 (動画 96 / 写真 6 / テキスト 5)、タグ 132、アーティスト 7
- Tumblr 時代の投稿 Markdown と旧カスタムページは `tumblr-export/` にアーカイブした (旧 `content/`)
- Tumblr ホスト画像の原本は `media/` に保存 (`media-urls.json` が投稿 ID との対応)
- 公開日時は seed に載らないため `web/seed/published-at.sql` で別途反映
- 既知: `701028279411474432` (Dartmoor by Diastereomer) は Tumblr 上でも動画が失われており (embed 無し)、本文のみ移行

## 本番 D1 への投入手順

EmDash の CLI seed はローカル SQLite 専用で、セットアップウィザードは本番ドメインで実行する必要がある (パスキーとサイト URL がドメインに固定されるため)。
そのため、ローカル D1 に seed を適用してから SQL dump を作り、本番 D1 に流し込む。

1. ローカルで seed 適用: `astro dev` → `/_emdash/api/setup/dev-bypass` → `wrangler d1 execute puppets-web --local --file seed/published-at.sql`
2. ローカル D1 から認証系データとセットアップ完了フラグを削除する
   - テーブル: users / credentials / auth_* / oauth* / api_tokens など
   - options: `emdash:site_url` / `emdash:site_title` / `emdash:setup_complete`
3. FTS 以外のテーブルを `wrangler d1 export --local` で書き出し、`scripts/order_d1_dump.py` で外部キーの順に並べ替える
4. **本番 Worker に最初のリクエストが来る前に** `wrangler d1 execute puppets-web --remote --file <dump>` で投入する
   - 先にアクセスされると EmDash がスキーマを自動作成してしまい、CREATE TABLE が衝突する
   - その場合は INSERT 文だけを流す
5. 画像を R2 に投入する: `media.storage_key` ごとに `wrangler r2 object put puppets-media/<key> --remote`
6. FTS インデックスは起動時に自動で再構築される (ローカルのリハーサルで確認済み)

### 実施記録 (2026/09/21)

- 投入前に本番 Worker へのアクセスが発生し、スキーマが自動作成済みだった。そのため手順 4 は INSERT 文だけで実施した
  - 対象: revisions / taxonomies / media / ec_posts / ec_artists / content_taxonomies / media_usage 系 / revision_prune_queue
  - スキーマ系テーブル (collections / fields / taxonomy_defs / menus) はローカルと同じ内容・同じ ID で自動作成されていた
- R2 に 18 ファイルを投入
- workers.dev で旧 URL 検証 120/120 OK、全文検索は動作、`/_emdash/admin` はセットアップへリダイレクトすることを確認

## 切替手順

1. workers.dev で内容を確認 (チェックポイント 1)
2. Cloudflare に puppets.jp ゾーンを追加し、Route 53 のレコード (MX 等) を移す
3. レジストラでネームサーバーを変更 (手動)
4. `wrangler.jsonc` の `routes` を有効化して再デプロイ。Tumblr 側のカスタムドメイン設定を解除
5. https://puppets.jp/_emdash/admin でセットアップウィザードを実行し、パスキーを登録 (手動)
6. `uv run scripts/verify_legacy_urls.py https://puppets.jp` で旧 URL が全件 301 → 200 になることを確認
7. Tumblr ブログを削除 (手動、確認後)

## GitHub Actions のシークレット

- `CLOUDFLARE_API_TOKEN`
  - アカウント権限: Workers Scripts / D1 / Workers R2 Storage / Workers KV Storage (Edit)
  - puppets.jp ゾーン権限: Workers Routes (Edit)
- `CLOUDFLARE_ACCOUNT_ID`
- `PUBLIC_CF_BEACON_TOKEN`: Cloudflare Web Analytics のサイトトークン
- バックアップ用: `CLOUDFLARE_R2_ACCESS_KEY_ID` / `CLOUDFLARE_R2_SECRET_ACCESS_KEY`

## 後片付け (2026/09/21)

- Tumblr 同期ツール (`scripts/sync.py` / `auth.py` / `client.py`、`.tumblr-manifest.json`) を削除した。必要なら git 履歴から参照できる
- `content/` を `migration/tumblr-export/` に移動した
- `scripts/tumblr_to_seed.py` は Tumblr API を使わず、`media-urls.json` と `media/` だけで再生成できるようにした
