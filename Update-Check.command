#!/usr/bin/env bash
dir="$(cd -- "$(dirname "$0")" >/dev/null 2>&1; pwd -P)"
git pull 2>/dev/null
"$dir"/Lavalink.command -c