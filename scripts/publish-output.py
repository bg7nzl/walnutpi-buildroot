#!/usr/bin/env python3
"""Publish the SD image into output/ as a zip. Raw .img does not stay there."""
from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="HTTP output directory")
    parser.add_argument("--img", required=True, type=Path, help="built .img (not left in --out)")
    parser.add_argument("--flash", type=Path, default=None)
    parser.add_argument("--uboot", type=Path, default=None)
    args = parser.parse_args()

    img = args.img.resolve()
    out = args.out.resolve()
    if not img.is_file():
        print(f"missing image: {img}", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)

    zip_path = out / "walnutpi-1b.img.zip"
    partial = out / "walnutpi-1b.img.zip.partial"
    if partial.exists():
        partial.unlink()

    members: list[tuple[Path, str]] = [(img, "walnutpi-1b.img")]
    flash = args.flash.resolve() if args.flash else None
    if flash and flash.is_file():
        members.append((flash, "FLASH.md"))
        # Small text copy for the HTTP listing without unzipping.
        dest_flash = out / "FLASH.md"
        dest_flash.write_bytes(flash.read_bytes())
        dest_flash.chmod(0o644)
    uboot = args.uboot.resolve() if args.uboot else None
    if uboot and uboot.is_file():
        members.append((uboot, "u-boot-sunxi-with-spl.bin"))

    print(f"zipping {img} -> {zip_path}", flush=True)
    with zipfile.ZipFile(
        partial,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=1,
        allowZip64=True,
    ) as zf:
        for src, name in members:
            zf.write(src, arcname=name)
            print(f"  added {name} ({src.stat().st_size} bytes)", flush=True)

    os.replace(partial, zip_path)
    zip_path.chmod(0o644)

    # Raw image / SPL must not remain in the HTTP folder.
    for leftover in (
        out / "walnutpi-1b.img",
        out / "u-boot-sunxi-with-spl.bin",
        out / "sdcard.img",
    ):
        if leftover.exists() or leftover.is_symlink():
            leftover.unlink()
            print(f"removed {leftover}", flush=True)

    print(f"published {zip_path} ({zip_path.stat().st_size} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
