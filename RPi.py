
class GPIO:

    PUD_UP = 0
    BCM = 1000
    FALLING = 2000
    IN = 3000

    # This is the GPIO state: add a value [16, 20, 21, 26] to simulate a
    # button that is pressed, remove it to indicate release.
    clear_gpios = set()

    @classmethod
    def setup(cls, port, mode, pull_up_down):
        pass

    @classmethod
    def setmode(cls, mode):
        pass

    @classmethod
    def add_event_detect(cls, port, edge, callback):
        pass

    @classmethod
    def input(cls, gpio):
        return 0 if gpio in GPIO.clear_gpios else 1
