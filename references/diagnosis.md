# Diagnosis notes — Intel iGPU backlight on macOS 26 Tahoe

## Symptom set

- Control Center has no usable brightness control for the internal panel.
- `Fn` brightness keys do nothing (no OSD, no level change).
- `ioreg` class counts: `AppleBacklightDisplay` = 0, `IOBacklightDisplay` = 0.
- `AppleDisplay` (subclass of `IODisplay`, probe score 2000) is attached under
  `AppleIntelFramebuffer@0/display0`.
- `AppleIntelPanelA` from `com.apple.driver.AppleBacklight` matches the ACPI
  `backlight` device (PNLF), but its `IODisplayParameters` holds only
  `{"commit": {"reg": 0}}` — no brightness parameters were ever published.

## Why it happens

`AppleBacklightDisplay::probe` requires three conditions:

1. the global `gIOFBHaveBacklight` is not 0; the first `IOFramebuffer::open()`
   sets it from `IOService::nameMatching("backlight")` results;
2. `IODisplay::probe` succeeds for the same provider;
3. for at least one connection, `getAttributeForConnection(i, 'flgs')` returns
   `kIOConnectionBuiltIn` (`0x00000800`, bit 11), and a second per-connection
   query returns an accepted value (`0x4`).

The Intel framebuffer reports `kIOConnectionBuiltIn` only when its own
connector flags carry `CNConnectorAlwaysConnected` (`0x08`). WhateverGreen's
`ConnectorFlags` union documents that bit as "normally set for LVDS displays
(i.e. built-in displays)". A connector declared as LVDS (`type 0x200`) without
`0x08` is therefore described by IOGraphics as an external sink.

When probe fails, IOKit instantiates `AppleDisplay` (score 2000) instead of
`AppleBacklightDisplay` (score 3000). `AppleDisplay` never becomes an
`IOBacklightDisplay`, so:

- `IODisplay::start` skips its `nameMatching("backlight")` subtree search,
  because that whole block is guarded by
  `OSDynamicCast(IOBacklightDisplay, this)`. `AppleIntelPanelA::setDisplay`
  is never called.
- No brightness parameter handler is registered, so CoreBrightness has
  nothing to drive. The slider disappears and ACPI brightness notifications
  are routed into a void.

## Fix

In `DeviceProperties/Add/<IGPU path>`:

```
framebuffer-con0-alldata = 00000000 00020000 87010000
                                             ^^ flags dword 0x00000187
```

Change the flags dword to `0x0000018F` (adds `0x08`). Keep the connector
declared as LVDS (`type 0x200`), index 0, bus 0, pipe 0, and keep
`framebuffer-con0-enable` and `framebuffer-patch-enable` set to 1.

The same rule applies to whichever connector carries the internal panel on
other platforms: `type` must be LVDS/eDP and its flags must include `0x08`.

## Verification

After reboot:

- the built-in detector (`assets/check-builtin.c`) reports `builtin=1`;
- `AppleBacklightDisplay` exists and `AppleIntelPanelA` exposes brightness
  parameters;
- the Control Center slider changes the panel brightness and the OSD appears.

## Key routing (second stage)

Only relevant once the slider works.

- WhateverGreen wraps `AppleIntelPanel::setDisplay`, clones the `ApplePanels`
  dictionary, injects generic entries (`F14Txxxx`, `F15Txxxx`, …), and patches
  the `F%uT%04x` lookup format string to `F%uTxxxx` so unknown panels still
  get a usable curve.
- `BrightnessKeys` converts ACPI `Notify` `0x86`/`0x87` from the panel device
  into `kPS2K_notifyKeystroke` with ADB `0x71` (up) and `0x6b` (down). The
  PS2 keyboard eats the keystroke and dispatches those ADB codes, but its
  keymap defines `0x71`/`0x6b` as F15/F14 — dead keys on macOS.
- VoodooPS2's brightness special keys are ADB `0x90` (up) and `0x91` (down).
- Therefore, for machines whose EC emits PS2 scan codes (`e0f1`/`e0f2` on
  Dell-class firmware), remap them to `90`/`91` in the active
  `VoodooPS2Keyboard` profile's `Custom ADB Map` and reboot.
- If the EC emits only ACPI notifications, the keyboard never sees a scan
  code; the injected keystroke itself must be mapped to `0x90`/`0x91`
  instead of relying on the profile map.

## Guardrails

- Never reset NVRAM on a machine with a generated SystemUUID: it breaks
  iCloud/iMessage activation.
- On shared EFI volumes (multi-boot with Limine/GRUB), modify only
  `EFI/OC/config.plist`; never rewrite bootloader files or kext trees.
- Keep kexts and WhateverGreen current: the panel-injection path is version
  specific, and older builds silently skip the `ApplePanels` merge.
