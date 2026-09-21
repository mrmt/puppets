#!/usr/bin/env python3
"""
wrangler d1 export の出力を、外部キーの参照先テーブルが先に作られる順へ並べ替える

wrangler d1 export はテーブルを名前順に出力するため、media → media_folders のような
参照があると空の D1 への import が "no such table" で失敗する。

使い方: python3 scripts/order_d1_dump.py dump.sql > dump-ordered.sql
"""

import re
import sys


def table_name(line: str) -> str:
    return re.match(r'CREATE TABLE (?:IF NOT EXISTS )?"?([^"( ]+)"?', line).group(1)


def main():
    lines = open(sys.argv[1], encoding="utf-8").read().split("\n")
    creates = {table_name(l): l for l in lines if l.startswith("CREATE TABLE")}
    deps = {n: set(re.findall(r'references "?([A-Za-z_0-9]+)"?', l, re.I)) - {n} for n, l in creates.items()}

    order: list[str] = []
    seen: set[str] = set()

    def visit(n: str):
        if n in seen:
            return
        seen.add(n)
        for d in sorted(deps.get(n, ())):
            visit(d)
        order.append(n)

    for n in creates:
        visit(n)

    pragmas = [l for l in lines if l.startswith("PRAGMA")]
    rest = [l for l in lines if not l.startswith(("PRAGMA", "CREATE TABLE"))]
    print("\n".join(pragmas + [creates[n] for n in order if n in creates] + rest))


if __name__ == "__main__":
    main()
