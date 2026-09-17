#!/bin/sh
# Inject WalnutPi 1B H616 extras into a mainline kernel tree.
set -eu
LINUX_DIR="${1:?linux dir}"
HERE="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
python3 "${HERE}/inject-h616.py" "${LINUX_DIR}" "${HERE}"
