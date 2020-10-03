
class GPIO:

    PUD_UP = 0
    BCM = 1000
    FALLING = 2000
    IN = 3000

    @classmethod
    def setup(cls, port, mode, pull_up_down):
        pass

    @classmethod
    def setmode(cls, mode):
        pass

    @classmethod
    def add_event_detect(cls, port, edge, callback):
        pass
