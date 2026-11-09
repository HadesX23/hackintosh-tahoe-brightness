#!/usr/bin/env python3
"""Add CNConnectorAlwaysConnected (0x08) to the internal LVDS/eDP connector.

The Intel framebuffer only reports kIOConnectionBuiltIn to IOGraphics when its
connector flags contain 0x08. Without that bit, AppleBacklightDisplay::probe
fails, IOKit falls back to AppleDisplay, and the system publishes no brightness
parameters at all: the Control Center slider disappears and brightness keys
have nothing to drive.

Usage:
    patch-con-flags.py --config /Volumes/EFI/EFI/OC/config.plist
    patch-con-flags.py --config <path> --dry-run

The script backs up the plist, changes exactly one 12-byte connector record,
reloads the file to prove no other value moved, and runs plutil -lint.
"""

from __future__ import annotations

import argparse
import datetime
import plistlib
import struct
import subprocess
import sys

LVDS_TYPE = 0x00000200
ALWAYS_CONNECTED = 0x00000008


def iter_connectors(props: dict):
    for key, value in props.items():
        if not key.startswith("framebuffer-con") or not key.endswith("-alldata"):
            continue
        if isinstance(value, bytes) and len(value) == 12:
            yield key, value


def parse(record: bytes) -> tuple[int, int, int, int]:
    _, conn_type, flags = struct.unpack("<3I", record)
    return conn_type, flags, 0, 0


def find_igpu(add: dict, device: str | None) -> str:
    if device:
        if device not in add:
            sys.exit(f"device not found: {device}")
        return device

    matches = [key for key, props in add.items() if any(True for _ in iter_connectors(props))]
    if not matches:
        sys.exit("no IGPU entry with framebuffer-conN-alldata found under DeviceProperties/Add")
    if len(matches) > 1:
        sys.exit("multiple IGPU candidates found; pass --device explicitly:\n  " + "\n  ".join(matches))
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--device", default=None)
    parser.add_argument("--connector", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(args.config, "rb") as handle:
        document = plistlib.load(handle)
    try:
        add = document["DeviceProperties"]["Add"]
    except KeyError:
        sys.exit("DeviceProperties/Add missing from config.plist")

    device = find_igpu(add, args.device)
    props = add[device]

    target = None
    for key, record in iter_connectors(props):
        conn_type, flags, _, _ = parse(record)
        if args.connector and key != args.connector:
            continue
        if conn_type == LVDS_TYPE and not flags & ALWAYS_CONNECTED:
            target = (key, record, flags)
            break

    if target is None:
        print(f"{device}: no LVDS connector needing the built-in flag (nothing to do)")
        return 0

    key, record, flags = target
    new_flags = flags | ALWAYS_CONNECTED
    new_record = record[:8] + struct.pack("<I", new_flags)
    print(f"device   : {device}")
    print(f"connector: {key}")
    print(f"flags    : 0x{flags:08x} -> 0x{new_flags:08x}")

    if args.dry_run:
        print("dry run: no file written")
        return 0

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{args.config}.bak-{stamp}"
    with open(args.config, "rb") as src, open(backup, "wb") as dst:
        dst.write(src.read())
    print(f"backup   : {backup}")

    props[key] = new_record
    with open(args.config, "wb") as handle:
        plistlib.dump(document, handle, fmt=plistlib.FMT_XML, sort_keys=False)

    with open(args.config, "rb") as handle:
        check = plistlib.load(handle)
    reloaded = check["DeviceProperties"]["Add"][device][key]
    if reloaded != new_record:
        sys.exit("verification failed: written value does not round-trip")

    if plistlib.load(open(backup, "rb")) == check:
        sys.exit("verification failed: reloaded plist equals the backup")

    lint = subprocess.run(["plutil", "-lint", args.config], capture_output=True, text=True)
    sys.stdout.write(lint.stdout)
    if lint.returncode != 0:
        sys.exit("plutil -lint failed; restore the backup before rebooting")

    print("ok: single connector record updated; reboot to apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
