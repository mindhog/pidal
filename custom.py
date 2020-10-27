
import abc
from midi import ControlChange, ProgramChange
from subprocess import Popen
import threading
from typing import Callable
from engine import Config, Engine, ProcessManager
from util import Actuator, ConfigFramework, FlagSetController

print('in custom')

class RadioController:
    """Manages the button interfaces radio-button style.

    This class basically keeps track of the currently active button and when a
    new button is activated (see activate()) it notifies the engine to
    activate the new button and deactivate the old one.
    """

    def __init__(self, active: int = 0):
        """
        Args:
            active: The active button number.
        """
        self.active = active

    def activate(self, engine: Engine, index: int) -> None:
        """Activate a different button."""
        engine.notify('pedal_button_status', self.active, False)
        engine.notify('pedal_button_status', index, True)
        self.active = index

def double_press(func: Callable[[bool], None],
                 alt_func: Callable[[bool], None],
                 other: int
                 ) -> Callable[[bool], None]:
    """Returns a footswitch-press handler to handle simultaneous depress of two
    footswitches.

    Returns a handler that calls alt_func() if footswitch 'other' is also
    depressed and calls func() if not.  This has the effect of binding the
    press of both footswitches to alt_func.

    Note that this isn't perfect, as triggering the first footswitch will
    still result in a "pressed" event being passed through to func().
    Furthermore, all footswitch released events will continue to be passed to
    func.
    """
    def handler(pressed: bool) -> None:
        if pressed:
            engine = Engine.get_instance()
            if engine.is_fs_pressed(other):
                alt_func(pressed)
                return
        func(pressed)

    return handler

def show_config_list(pressed: bool) -> None:
    if pressed:
        engine.notify('config_list')

def make_program_switcher(controller: RadioController, bank, program) -> None:
    def switcher(pressed: bool) -> None:
        if pressed:
            engine.set_program(gtx_port, bank, program)
            controller.activate(engine, program)
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
# XXX Starting this in the outer run.sh script, makes things easier for
# development.
#rak = ProcessManager(Popen(['rakarrack-plus', '-n', '-p', '6']))

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
        self.controller = RadioController()

    def on_enter(self):
        engine.jack_connect('system:capture_1', 'gx_head_amp:in_0')
        engine.set_program(gtx_port, 1, 0)
        for bank, prog in ((1, 0), (1, 1), (1, 2), (1, 3)):
            engine.register_footswitch(
                prog,
                make_program_switcher(self.controller, bank, prog)
            )
        self.controller.activate(engine, 0)

    def on_leave(self):
        engine.jack_disconnect_all('gx_head_amp:in_0', False)

class GuitarixSimple(Config):

    def __init__(self):
        super().__init__('Gtx Simple')
        self.buttons = ['Dist', 'Chorus', 'Wah', 'Over']
        self.states = {11: False, 13: False, 14: False, 12: False}

    def switch(self, pressed: bool, cc: int, index: int) -> None:
        if pressed:
            self.states[cc] = not self.states[cc]
            engine.seq.sendEvent(ControlChange(0, 0, cc,
                                               0x7f if self.states[cc] else 0
                                               ),
                                 gtx_port
                                 )
            engine.notify('pedal_button_status', index, self.states[cc])

    def on_enter(self):
        engine.jack_connect('system:capture_1', 'gx_head_amp:in_0')
        engine.set_program(gtx_port, 0, 0)
        engine.register_footswitch(0, lambda x: self.switch(x, 13, 0))
        engine.register_footswitch(1, lambda x: self.switch(x, 14, 1))
        engine.register_footswitch(
            2,
            double_press(lambda x: self.switch(x, 11, 2),
                         show_config_list,
                         3
                         )
        )
        engine.register_footswitch(
            3,
            double_press(lambda x: self.switch(x, 12, 3),
                         show_config_list,
                         2
                         )
        )

        # Reset all of the pedals.
        for cc in (11, 12, 13, 14):
            engine.seq.sendEvent(ControlChange(0, 0, cc, 0), gtx_port)
        self.states = {11: False, 13: False, 14: False, 12: False}

    def on_leave(self):
        engine.jack_disconnect_all('gx_head_amp:in_0', False)

class RakConfig(Config, metaclass=abc.ABCMeta):

    def __init__(self, name: str):
        super().__init__(name)
        self.last_button = 0
        self.controller = RadioController()

    def make_program_switcher(self, bank, program, index):
        def switcher(pressed: bool) -> None:
            if pressed:
                engine.set_program(rak_port, bank, program)
                self.controller.activate(engine, index)
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

class RakBizConfig(RakConfig):
    # Pedal 1 - Distortion
    # Pedal 2 - Chorus
    # Pedal 3 - Wah
    # 23 - Acoustic Sparkle
    # 6 - Tight Rock
    # 2, 59 - Trigger Chorus  (or just 51 - Classic Chorus)
    # 52 - Trash Chorus (dist + chorus + reverb)

    # 33 - Funk Wah (at volume 67/100)
    # 43 - Dist Wah (at vol 61/100)
    # 2, 40 - Talk to Me (at vol 60/100)
    # 2, 7 - Insanity Mojo (at vol 64/100)
    def __init__(self):
        super().__init__('Rak Legit')
        self.buttons = ['Dist', 'Chor', 'Wah', 'Out']
        self.states = 0  # bits 1, 2, and 3 are the pedal states.
        self.map = [
            (0, 23, 70),
            (0, 6, 64),
            (2, 59, 64),
            (0, 52, 64),
            (0, 33, 86),
            (0, 43, 78),
            (2, 40, 77),
            (2, 7, 64),
        ]

    def __on_press(self, fs: int, bit: int, pressed: bool):
        if pressed:
            self.states ^= bit
            bank, prog, vol = self.map[self.states]
            engine.set_program(rak_port, bank, prog)
            engine.seq.sendEvent(ControlChange(0, 0, 7, vol), rak_port)
            engine.notify('pedal_button_status', fs, bool(self.states & bit))

    def set_presets(self):
        for fs in range(3):
            engine.register_footswitch(
                fs,
                lambda p, fs=fs, bit=1 << fs: self.__on_press(fs, bit, p)
            )
        engine.register_footswitch(3, show_config_list)
        bank, prog, vol = self.map[0]
        engine.set_program(rak_port, bank, prog)
        engine.seq.sendEvent(ControlChange(0, 0, 7, vol), rak_port)

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
            engine.register_footswitch(fs,
                                       self.make_program_switcher(0, prog, fs))
        engine.register_footswitch(
            2,
            double_press(self.make_program_switcher(0, 32, 2),
                         show_config_list,
                         3
                         )
        )
        engine.register_footswitch(
            3,
            double_press(self.make_program_switcher(0, 8, 3),
                         show_config_list,
                         2
                         )
        )
        self.controller.activate(engine, 0)
        engine.set_program(rak_port, 0, 6)

def act(program: int) -> None:
    def enable():
        engine.set_program(rak_port, 3, program)
    return Actuator(enable, lambda: None)

class NewConfig(ConfigFramework):

    def __init__(self):
        super().__init__(
            'New Config',
            FlagSetController(['1', '2', '3', '4'],
                              [act(p) for p in range(1, 17)]
                              )
        )

    def on_enter(self):
        engine.midi_connect('pidal/to_rak',
                            'rakarrack-plus/rakarrack-plus IN')

        engine.jack_connect('system:capture_1', 'rakarrack-plus:in_1')
        engine.jack_connect('system:capture_1', 'rakarrack-plus:in_2')

simple = GuitarixSimple()
engine.set_config(simple)
engine.add_config(simple)
engine.add_config(FirstConfig())
engine.add_config(NewConfig())

# Wait for rakarrack asynchronously (since for some reason it takes a really
# long time to start) and then register the configs for it.

def wait_for_rak():
    engine.wait_for_jack('rakarrack-plus:in_1', timeout=600)
    engine.wait_for_jack('rakarrack-plus:in_2')
    engine.wait_for_jack('rakarrack-plus:out_1')
    engine.wait_for_jack('rakarrack-plus:out_2')
    engine.add_config(RakFunConfig())
    engine.add_config(RakBizConfig())

thread = threading.Thread(target=wait_for_rak)
thread.setDaemon(True)
thread.start()


