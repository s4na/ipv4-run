#!/bin/sh
# Prefer the active Python, including mise shims, when it meets our minimum.
# A missing, unconfigured, or too-old Python falls back to the brew dependency.
python=$(command -v python3) || python=
if [ -n "$python" ] && "$python" -c 'import sys; sys.exit(sys.version_info < (3, 10))' </dev/null >/dev/null 2>&1; then
    exec "$python" @CLI@ "$@"
fi
exec @FALLBACK_PYTHON@ @CLI@ "$@"
