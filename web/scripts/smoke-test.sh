#!/usr/bin/env bash
# ビルド済み Worker を wrangler dev (ローカル) で起動し、リクエストが例外にならないことを確認する。
# バンドル時の __require 化など、typecheck / build では検出できない実行時エラー (本番 error 1101) を防ぐ。
set -euo pipefail

PORT=8799
LOG=$(mktemp)
BODY=$(mktemp)

# 前回の wrangler dev が残っていると別ビルドを検査してしまうため、ポート使用中は失敗させる
if curl -s -o /dev/null "http://localhost:$PORT/"; then
  echo "::error::ポート $PORT が使用中"; exit 1
fi

kill_tree() {
  local child
  for child in $(pgrep -P "$1" 2>/dev/null || true); do kill_tree "$child"; done
  kill "$1" 2>/dev/null || true
}

pnpm exec wrangler dev --local --port "$PORT" >"$LOG" 2>&1 &
PID=$!
trap 'kill_tree "$PID"' EXIT

# 起動待ち
status=000
for _ in $(seq 1 30); do
  status=$(curl -s -o "$BODY" -w "%{http_code}" "http://localhost:$PORT/" || true)
  [ "$status" != "000" ] && break
  sleep 2
done
if [ "$status" = "000" ]; then
  echo "::error::Worker が起動しなかった"; cat "$LOG"; exit 1
fi

# 遅延 import される chunk の例外は初回以降のリクエストで出るため、複数パスを複数回叩く
fail=0
# 空DB (CI) では / と /posts は setup への 302 になるため、SSR される setup 画面も叩く
for path in / /posts /_emdash/admin/setup / /posts /_emdash/admin/setup; do
  status=$(curl -s -o "$BODY" -w "%{http_code}" "http://localhost:$PORT$path" || true)
  echo "GET $path -> $status"
  # 空DB のローカル環境では emdash が 503 (migration 必須) を返す。これは Worker が正常に動いている証拠
  if [ "$status" -ge 500 ] && ! grep -q "Database migrations are required" "$BODY"; then
    head -c 500 "$BODY"; echo
    fail=1
  fi
done

# wrangler のログに実行時例外が出ていないか
sleep 1
if grep -qE "Exception Thrown|\[ERROR\]" "$LOG"; then
  grep -E "Exception Thrown|\[ERROR\]" "$LOG" | head -5
  fail=1
fi

if [ "$fail" != 0 ]; then
  echo "::error::Worker が実行時例外を起こした (本番 error 1101 の疑い)"
  exit 1
fi
