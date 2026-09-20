# Controller not detected

## Trigger

Video is healthy but a browser controller does not control its assigned player slot.

## Diagnose

1. Confirm the browser Gamepad API sees the device after a button press and the player
   page has focus.
2. Check session diagnostics for the expected active slot and healthy runtime.
3. Use the Selkies gamepad overlay. If needed, run the accepted in-stream diagnostic
   `JS_LOG=1 od -v -An -w8 -t x1 /dev/input/js0`; do not wrap it in `stdbuf`.
4. Compare the core profile's documented controller topology and player maximum.

## Recover

Reconnect the physical controller, reload the scoped player, then leave/rejoin if the
browser mapping remains stale. Do not grant host input-device access or bypass Selkies'
unprivileged joystick interposer.
