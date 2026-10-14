#!/bin/sh
set -eu

package_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target_dir=${1:-"$HOME/.local/bin"}

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "Things Cloud requires Python 3.9+; install python3 first." >&2
  exit 1
fi

if [ ! -f "$package_dir/things-cli" ]; then
  echo "Run this installer from an extracted Things CLI binary package." >&2
  exit 1
fi

# Check the binary's platform before replacing an installed command.
"$package_dir/things-cli" --version >/dev/null
mkdir -p "$target_dir"
install -m 0755 "$package_dir/things-cli" "$target_dir/things-cli"
install -m 0755 "$package_dir/things-cli" "$target_dir/things"
printf 'Installed Things CLI in %s\n' "$target_dir"
printf 'Connect once: "%s/things-cli" login\n' "$target_dir"
printf 'Plugin files: %s/plugin\n' "$package_dir"
