
import abc
from midi import ControlChange, ProgramChange
from subprocess import Popen
import threading
from engine import Config, Engine, ProcessManager

print('in custom')

def make_program_switcher(bank, program) -> None:
    def switcher(pressed: bool) -> None:
        if pressed:
            engine.set_program(gtx_port, bank, program)
    return switcher

engine = Engine.get_instance()

gtx_port = engine.seq.createOutputPort('to_gtx')
rak_port = engine.seq.createOutputPort('to_rak')

# Start by loading guitarix.
gtx = ProcessManager(Popen(['guitarix', '-N']))
engine.wait_for_jack('gx_head_amp:in_0')
engine.wait_for_jack('gx_head_fx:out_0')
engine.wait_for_jack('gx_head_fx:out_1')

# load Rakarrack and disconnect it from input.  The "-p 1" combined with -n
# brings jack up in "FX On" mode.
rak = ProcessManager(Popen(['rakarrack-plus', '-n', '-p', '6']))

# Load a2jmidid so we can control it.
GTX_JACK_PORT = 'a2j:pidal (capture): to_gtx'
a2j = ProcessManager(Popen(['a2jmidid', '-eu']))
engine.wait_for_jack(GTX_JACK_PORT)

import time
time.sleep(1)
engine.jack_disconnect_all('system:capture_1', True)
engine.jack_disconnect_all('gx_head_amp:in_0', False)
engine.jack_disconnect_all(GTX_JACK_PORT, True)
engine.jack_disconnect_all('gx_head_amp:midi_in_1', False)
engine.jack_connect(GTX_JACK_PORT, 'gx_head_amp:midi_in_1')
#engine.jack_disconnect_all('rakarrack-plus:in_1', False)
#engine.jack_disconnect_all('rakarrack-plus:in_2', False)

class FirstConfig(Config):

    def __init__(self):
        super().__init__('First Config')
        self.buttons = ['Cln', 'Dist', 'Wah', 'Over']

    def on_enter(self):
        engine.jack_connect('system:capture_1', 'gx_head_amp:in_0')
        engine.set_program(gtx_port, 0, 0)
        for bank, prog in ((0, 0), (0, 1), (0, 2), (0, 3)):
            engine.register_footswitch(prog, make_program_switcher(bank, prog))

    def on_leave(self):
        engine.jack_disconnect_all('gx_head_amp:in_0', False)

class RakConfig(Config, metaclass=abc.ABCMeta):

    def make_program_switcher(self, bank, program):
        def switcher(pressed: bool) -> None:
            if pressed:
                engine.set_program(rak_port, bank, program)
        return switcher

    def on_enter(self):
        engine.midi_connect('pidal/to_rak',
                            'rakarrack-plus/rakarrack-plus IN')

        engine.jack_connect('system:capture_1', 'rakarrack-plus:in_1')
        engine.jack_connect('system:capture_1', 'rakarrack-plus:in_2')
        self.set_presets()

    @abc.abstractmethod
    def set_presets(self):
        raise NotImplementedError()

    def on_leave(self):
        engine.jack_disconnect_all('rakarrack-plus:in_1', False)
        engine.jack_disconnect_all('rakarrack-plus:in_2', False)

#class RakBizConfig(RakConfig):
#    # Pedal 1 - Distortion
#    # Pedal 2 - Chorus
#    # Pedal 3 - Wah
#    # 23 - Acoustic Sparkle
#    # 6 - Tight Rock
#    # 2, 59 - Trigger Chorus  (or just 51 - Classic Chorus)
#    # 52 - Trash Chorus (dist + chorus + reverb)
#
#    # 33 - Funk Wah (at volume 67/100)
#    # 43 - Dist Wah (at vol 61/100)
#    def __init__(self):
#        super().__init__('Rak Legit')
#        self.buttons = ['Dist', 'Chor', 'Wah', 'Out']
#
#    def set_presets(self):

class RakFunConfig(RakConfig):
    def __init__(self):
        super().__init__('Rak Fun')
        self.buttons = ['Fuzz', 'Bass', 'Angl', 'Pit']

    def set_presets(self):
        # 6 - tight rock
        # 29 - bass
        # 32 - Angel's chorus,
        # 8 - Summer by the pit
        for (fs, prog) in enumerate([6, 29, 32, 8]):
            engine.register_footswitch(fs, self.make_program_switcher(0, prog))

    def __init__(self):
        super().__init__('Rak Fun')

first = FirstConfig()
engine.add_config(first)
engine.set_config(first)

# Wait for rakarrack asynchronously (since for some reason it takes a really
# long time to start) and then register the configs for it.

def wait_for_rak():
    engine.wait_for_jack('rakarrack-plus:in_1', timeout=600)
    engine.wait_for_jack('rakarrack-plus:in_2')
    engine.wait_for_jack('rakarrack-plus:out_1')
    engine.wait_for_jack('rakarrack-plus:out_2')
    engine.add_config(RakFunConfig())

thread = threading.Thread(target=wait_for_rak)
thread.setDaemon(True)
thread.start()


