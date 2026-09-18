#!/bin/bash
# Compatibility entry point: the Google-only installer has been retired.
set -euo pipefail
exec bash "$(dirname "$0")/install-server-mail.sh" "$@"
