#!/usr/bin/env bash
# W3-058: git hook'larini aktive et (commit-oncesi test kapisi).
set -e
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true
echo "OK: core.hooksPath=.githooks aktif. Commit oncesi ilgili testler kosar."
echo "Atlama (WIP): git commit --no-verify"
