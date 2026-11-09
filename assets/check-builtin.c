/*
 * check-builtin.c — report whether each active display is built-in.
 *
 * Build:  clang -framework CoreGraphics -framework CoreFoundation check-builtin.c -o check-builtin
 * Run:    ./check-builtin
 *
 * A Hackintosh internal panel that prints builtin=0 is being treated as an
 * external sink, which prevents AppleBacklightDisplay from attaching.
 */

#include <CoreGraphics/CoreGraphics.h>
#include <stdio.h>

int main(void)
{
    uint32_t ids[16];
    uint32_t count = 16;

    if (CGGetActiveDisplayList(count, ids, &count) != kCGErrorSuccess || count == 0) {
        fprintf(stderr, "no active displays reported\n");
        return 1;
    }

    for (uint32_t i = 0; i < count; i++) {
        CGDirectDisplayID display = ids[i];
        printf("display 0x%x builtin=%d main=%d online=%d vendor=%u model=%u\n",
               display,
               CGDisplayIsBuiltin(display),
               CGDisplayIsMain(display),
               CGDisplayIsOnline(display),
               CGDisplayVendorNumber(display),
               CGDisplayModelNumber(display));
    }

    return 0;
}
