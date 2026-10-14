#!/usr/bin/env python3
"""Build platform CLI archives and an allowlisted three-host plugin package."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ("darwin-amd64", "darwin-arm64", "linux-amd64", "linux-arm64")
PLUGIN_FILES = (
    "plugin.json",
    "mcp.json",
    ".mcp.json",
    ".codex-plugin/plugin.json",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".cursor-plugin/plugin.json",
    ".agents/plugins/marketplace.json",
    "scripts/plugin_bootstrap.py",
    "docs/INSTALL.md",
)


def plugin_files():
    files = [ROOT / name for name in PLUGIN_FILES]
    files += sorted((ROOT / "skills").rglob("*"))
    files += [ROOT / "internal/cloud/runtime/LICENSE", ROOT / "internal/cloud/runtime/THIRD_PARTY_NOTICES.md"]
    return [p for p in files if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]


def build(platform):
    goos, architecture = platform.split("-")
    binary = ROOT / "bin" / ("things-cli-" + platform)
    binary.parent.mkdir(exist_ok=True)
    env = {**os.environ, "GOOS": goos, "GOARCH": architecture, "CGO_ENABLED": "0"}
    subprocess.run(["go", "build", "-trimpath", "-ldflags=-s -w", "-o", str(binary), "./cmd/things"], cwd=ROOT, env=env, check=True)
    return platform, binary


def add_bytes(archive, name, body, mode=0o644):
    info = tarfile.TarInfo(name)
    info.mode, info.size = mode, len(body)
    archive.addfile(info, io.BytesIO(body))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=PLATFORMS, action="append", help="Repeat to select targets; defaults to all four.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    version = json.loads((ROOT / "plugin.json").read_text())["version"]
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    files = plugin_files()
    paths = []
    plugin = output / ("things-plugin-" + version + ".zip")
    with zipfile.ZipFile(plugin, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, "things/" + path.relative_to(ROOT).as_posix())
    paths.append(plugin)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for platform, binary in pool.map(build, args.platform or PLATFORMS):
            path = output / ("things-cli-" + version + "-" + platform + ".tar.gz")
            with tarfile.open(path, "w:gz") as archive:
                archive.add(binary, arcname="things-cli")
                archive.add(ROOT / "scripts/install-binary.sh", arcname="install.sh")
                add_bytes(archive, "VERSION", (version + "\n").encode())
                add_bytes(archive, "INSTALL.md", (ROOT / "docs/INSTALL.md").read_bytes())
                for source in files:
                    archive.add(source, arcname="plugin/" + source.relative_to(ROOT).as_posix())
            paths.append(path)
    checksums = output / "SHA256SUMS"
    checksums.write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in paths))
    for path in paths + [checksums]:
        print(path)


if __name__ == "__main__":
    main()
