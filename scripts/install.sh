#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_NAME="things"
TARGET_DIR="${1:-}"

choose_target_dir() {
  if [[ -n "$TARGET_DIR" ]]; then
    echo "$TARGET_DIR"
    return
  fi

  IFS=':' read -r -a path_entries <<< "${PATH:-}"
  for dir in "${path_entries[@]}"; do
    [[ -z "$dir" ]] && continue
    [[ ! -d "$dir" ]] && continue
    [[ -w "$dir" ]] || continue
    echo "$dir"
    return
  done

  echo "$HOME/.local/bin"
}

TARGET_DIR="$(choose_target_dir)"
mkdir -p "$TARGET_DIR"

tmp_bin="$(mktemp)"
trap 'rm -f "$tmp_bin"' EXIT

cd "$ROOT_DIR"
go build -trimpath -o "$tmp_bin" ./cmd/things
install -m 0755 "$tmp_bin" "$TARGET_DIR/$BIN_NAME"

echo "Installed $BIN_NAME to $TARGET_DIR/$BIN_NAME"
if ! command -v "$BIN_NAME" >/dev/null 2>&1; then
  echo
  echo "NOTE: '$TARGET_DIR' is not currently in your PATH."
  echo "Add it to your shell profile, for example:"
  echo "  export PATH=\"$TARGET_DIR:\$PATH\""
fi

