---
name: hackintosh-tahoe-brightness
description: "Trigger: brightness slider missing, Control Center brightness dead, Fn brightness keys not working, AppleBacklightDisplay absent, Hackintosh internal display brightness on macOS 26 Tahoe. Fix Intel iGPU LVDS/eDP backlight by correcting the built-in connector flag."
license: MIT
metadata:
  author: "hadesx23"
  version: "1.0"
---

# Hackintosh Tahoe Brightness

Restore internal-panel brightness on Intel iGPU laptops running macOS 26 Tahoe with an OCLP root patch: no Control Center slider, dead Fn brightness keys, `AppleBacklightDisplay` class count 0.

## Activation Contract

Use when all hold: Intel iGPU internal panel (LVDS/eDP), macOS 26.x, brightness absent from BOTH Control Center and Fn keys, and `ioreg` shows no `AppleBacklightDisplay`.

Do not use for external monitors, AMD/NVIDIA backlight, Apple hardware, or a working slider with silent keys (follow Key Routing instead).

## Hard Rules

- Never reset NVRAM. Never touch Limine/GRUB files or any shared EFI entry except `OC/config.plist`.
- Back up `config.plist` with a timestamp; the reboot is the user's decision.
- Change exactly one data field and prove the rest is unchanged with a `plutil -p` diff.
- Run `plutil -lint` after writing and keep the plist in XML format.
- Publish no serials, MLB, SystemUUID, hostnames, or user paths.

## Decision Gates

| Evidence | Action |
|---|---|
| `CGDisplayIsBuiltin(CGMainDisplayID())` returns 0 | Apply the LVDS built-in fix |
| Internal connection already reports built-in | Skip the patch; inspect panel data and WEG patches |
| Slider works but Fn keys are silent | Do not edit the connector; fix key routing |
| Internal display missing from `CGGetActiveDisplayList` | Not this skill |

## Execution Steps

1. Confirm read-only: `kmutil showloaded | grep -i backlight` and check `ioreg` counts for `AppleBacklightDisplay` (0 means broken).
2. Compile and run `assets/check-builtin.c`. `builtin=0` on the internal display confirms the root cause: the panel is treated as an external DP sink, so `AppleBacklightDisplay::probe` fails and IOKit falls back to `AppleDisplay`.
3. Read the IGPU entry under `DeviceProperties/Add` and identify the LVDS connector (`type 0x200`, index 0), normally `framebuffer-con0-alldata`.
4. Add `0x08` (`CNConnectorAlwaysConnected`) to that connector's flags dword with `assets/patch-con-flags.py`.
5. Validate: `plutil -lint`, then diff `plutil -p` against the backup and confirm a single changed key.
6. The user reboots; then re-run step 2 (expect `builtin=1`) and verify slider and Fn keys.

## Key Routing

Apply only after the slider works. `BrightnessKeys` forwards ACPI panel notifications to the PS2 keyboard as ADB `0x71`/`0x6b`, which the keyboard keymap decodes as dead F15/F14. VoodooPS2 brightness special keys are `0x90`/`0x91`. Remap the PS2 brightness scan codes (`e0f1`/`e0f2`) to `0x90`/`0x91` in the selected VoodooPS2 keyboard profile, then reboot. See `references/diagnosis.md`.

## Output Contract

Report: root cause, exact connector field changed, backup path, lint result, single-line diff proof, and post-reboot evidence for both slider and keys. State plainly when one of the two still fails.

## References

- `references/diagnosis.md` — probe internals, panel data lookup, key routing detail.
- `assets/check-builtin.c` — CoreGraphics built-in detector.
- `assets/patch-con-flags.py` — connector flag patcher with backup and verification.
