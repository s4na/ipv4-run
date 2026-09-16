#!/bin/bash
set -euo pipefail
# A fresh runner uses this tap for both CI and generated release formulae.
tap=codex/ipv4-run-ci
if [ ! -d "$(brew --repository "$tap")/Formula" ]; then
  brew tap-new --no-git "$tap"
fi
cp Formula/*.rb "$(brew --repository "$tap")/Formula/"
version=$(python3 -c 'import re; from pathlib import Path; print(re.search(r"/tags/v([0-9]+\.[0-9]+\.[0-9]+)\.tar\.gz", Path("Formula/ipv4-run.rb").read_text())[1])')
# Reinstall because a single release run may process several merged PRs.
if brew list --versions "$tap/ipv4-run" >/dev/null 2>&1; then
  brew reinstall --build-from-source "$tap/ipv4-run"
else
  brew install --build-from-source "$tap/ipv4-run"
fi
brew test "$tap/ipv4-run"
brew install --build-from-source "$tap/ipv4-run@$version"
brew test "$tap/ipv4-run@$version"
