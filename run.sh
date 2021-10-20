#!/bin/bash

export DISPLAY=:0

# Number of jack periods (frames between process calls) to use.
# 128 would be better, but that doesn't work well with multiple effects on
# mod-host.
export PERIODS=256

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

# Source all of the scripts in the init.d directory.
for file in init.d/*; do
    . $file
done

# If we haven't yet initialized jackd, do so now with the S3 Card.
echo "jack pid before ours is $jack_pid"
if [ -z "$jack_pid" ]; then
    start_jack() {
        jackd -d alsa -d hw:CARD=S3,DEV=0 -p $PERIODS &
        jack_pid=$!
    }
    start_jack
fi

# Start rak (since it takes a really long time to startup)
if ! jack_lsp | grep rakarrack >/dev/null; then
    rakarrack-plus -n -p 6 &
fi

echo "jack pid is $jack_pid"
while true; do
    python3 main.py
    echo "killing $jack_pid"
    kill -9 $jack_pid
    sleep 1
    start_jack
done
