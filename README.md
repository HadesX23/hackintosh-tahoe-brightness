# hackintosh-tahoe-brightness

Agent skill + tooling to restore **internal panel brightness** on Intel iGPU
laptops running **macOS 26 Tahoe** with an OpenCore Legacy Patcher root patch.

If the Control Center brightness control is gone and `Fn` brightness keys do
nothing, the cause is usually not the keyboard and not CoreBrightness: the
internal LVDS/eDP connector is being reported as an external sink, so macOS
never attaches `AppleBacklightDisplay` and publishes no brightness parameters.

## The fix in one line

Add `0x08` (`CNConnectorAlwaysConnected`) to the internal connector's flags:

```
framebuffer-conN-alldata: ... 00020000 87010000
                                     ^^ type  ^^ flags -> 8f010000
```

`type` must be `0x200` (LVDS/eDP) and the connector must be the one the panel
is attached to (usually `con0`).

## Quick start

```bash
# 1. Confirm the panel is not reported as built-in (expect builtin=0 when broken)
clang -framework CoreGraphics -framework CoreFoundation assets/check-builtin.c -o check-builtin
./check-builtin

# 2. Inspect what would change
python3 assets/patch-con-flags.py --config /Volumes/EFI/EFI/OC/config.plist --dry-run

# 3. Apply (creates a timestamped backup, verifies the diff, runs plutil -lint)
python3 assets/patch-con-flags.py --config /Volumes/EFI/EFI/OC/config.plist

# 4. Reboot, then re-run the detector (expect builtin=1)
```

## Repository layout

```
SKILL.md                  # agent skill contract
references/diagnosis.md   # probe internals, panel data lookup, key routing
assets/check-builtin.c    # CoreGraphics built-in detector
assets/patch-con-flags.py # connector flag patcher with backup + verification
```

## Safety rules

- Never reset NVRAM on a machine with a generated SystemUUID: activation breaks.
- On multi-boot EFI volumes, touch only `EFI/OC/config.plist`.
- Back up first; the patcher does it for you with a timestamp.
- Reboot is always a human decision.

## Scope

Applies to Intel iGPU platforms where the internal panel is LVDS/eDP and the
brightness stack is otherwise present (`AppleBacklight`, `AppleBacklightExpert`,
WhateverGreen, an ACPI `backlight`/PNLF device). It does not cover AMD or
NVIDIA backlight control, external monitors, or Apple hardware.

## License

MIT. See `LICENSE`.
