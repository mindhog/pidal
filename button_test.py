#!/usr/bin/python3

from time import sleep
from RPi import GPIO

GPIO.setmode(GPIO.BCM)

def on_rising(port):
    print(f'port {port} rising')

def on_falling(port):
    print(f'port {port} falling')

for port in (16, 17, 20, 21, 22, 23, 26, 27):
    GPIO.setup(port, GPIO.IN, pull_up_down=GPIO.PUD_UP)
#    GPIO.add_event_detect(port, GPIO.RISING, callback=on_rising)
    GPIO.add_event_detect(port, GPIO.FALLING, callback=on_falling)

while True:
    sleep(1)

