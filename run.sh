#!/bin/sh

export DISPLAY=:0

# Wait for the xserver to come up.
while ! xset q >/dev/null 2>&1; do
    sleep 1
done

# disable screen blanking.
setterm -blank 0 -powersave off -powerdown 0 </dev/tty1
(
    # for some reason, the xset -dpms s off only works when I do it from a
    # subshell forked into the background! (Note: this was true for the zbox,
    # don't know if it's true for the pi, don't care)
    while xset q | grep 'DPMS is Enabled'; do
        xset -dpms s off
        sleep 1;
    done
)&

# We have to start jack before the engine.  We may want to move this out of
# here when we deal with multiple devices, buf for now this is expedient.
jackd -d alsa -d hw:CARD=S3,DEV=0 -p 128 &
jack_pid=$?

while true; do
    python3 main.py
done
