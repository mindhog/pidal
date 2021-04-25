
import abc
from midi import ControlChange, ProgramChange
from modhost import ModHost
from subprocess import Popen
import threading
from typing import Callable, List, Optional
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
zyn_port = engine.seq.createOutputPort('to_zyn')


# Start by loading guitarix.
gtx = ProcessManager(Popen(['guitarix', '-N']))
engine.wait_for_jack('gx_head_amp:in_0')
engine.wait_for_jack('gx_head_fx:out_0')
engine.wait_for_jack('gx_head_fx:out_1')

# Load mod-host
modd = ProcessManager(Popen(['mod-host', '-n']))
engine.wait_for_jack('mod-host:midi_in')
mod_host = ModHost()

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


class ModConfig(Config):
    """

    Commands are:
        name <words>...
        pedal <index> <name> <action>
    """

    def __init__(self, name: str, buttons: List[str],
                 actions: List[Optional[str]],
                 on_enter: Optional[str],
                 on_leave: Optional[str]) -> None:
        super().__init__(name)
        self.buttons = buttons
        self.actions = actions
        self.button_states = [False] * 4
        self.on_enter_block = on_enter
        self.on_leave_block = on_leave

    def on_button(self, index: int, pressed: bool) -> None:
        # Currently assuming that actions are just effect identifiers to
        # toggle on and off.
        if pressed and self.actions[index]:
            if self.button_states[index]:
                mod_host.bypass(int(self.actions[index]), True)
                self.button_states[index] = False
            else:
                mod_host.bypass(int(self.actions[index]), False)
                self.button_states[index] = True
            engine.notify('pedal_button_status', index,
                          self.button_states[index])

    def on_enter(self):
        if self.on_enter_block:
            mod_host.send_block(self.on_enter_block)

        engine.register_footswitch(0, lambda x: self.on_button(0, x))
        engine.register_footswitch(1, lambda x: self.on_button(1, x))
        engine.register_footswitch(
            2,
            double_press(lambda x: self.on_button(2, x),
                         show_config_list,
                         3
                         )
        )
        engine.register_footswitch(
            3,
            double_press(lambda x: self.on_button(3, x),
                         show_config_list,
                         2
                         )
        )

    def on_leave(self):
        if self.on_leave_block:
            mod_host.send_block(self.on_leave_block)

    @classmethod
    def read_file(self, filename: str) -> 'ModConfig':
        src = open(filename)

        name = None
        buttons = ['1', '2', '3', '4']
        actions = [None] * 4
        on_enter = None
        on_leave = None

        def read_block():
            result = []
            for line in src:
                if line.strip() == '}':
                    return ''.join(result)
                result.append(line)
            raise Exception('End of line encountered in block')

        def parse_cmd_or_block(args):
            if args[0] == '{':
                return read_block()
            else:
                return ' '.join(args)

        for line in src:
            cmd = line.rstrip().split()
            if not cmd or cmd[0].startswith('#'):
                continue

            if cmd[0] == 'name':
                name = ' '.join(cmd[1:])
            elif cmd[0] == 'pedal':
                num = int(cmd[1])
                button_name = cmd[2]
                action = parse_cmd_or_block(cmd[3:])
                buttons[num] = button_name
                actions[num] = action
            elif cmd[0] == 'on_enter':
                on_enter = parse_cmd_or_block(cmd[1:])
            elif cmd[0] == 'on_leave':
                on_leave = parse_cmd_or_block(cmd[1:])
            else:
                raise Exception(f'Unknown command: {cmd[0]}')

        return ModConfig(name, buttons, actions, on_enter, on_leave)

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

class RakStdConfig(RakConfig):
    """Normal rak configuration.

    Derived classes must specify a constant PRESETS containing a list of
    (name, bank, program, volume) tuples.

    They may also override INITIAL_PRESET to indicate the index of the preset
    configured upon entry.
    """

    INITIAL_PRESET = 0

    def __init__(self):
        super().__init__(self.NAME)
        self.buttons = [p[0] for p in self.PRESETS]

    def set_presets(self):
        for (fs, (bank, prog)) in \
                enumerate([(p[1], p[2]) for p in self.PRESETS]):
            engine.register_footswitch(
                fs, self.make_program_switcher(bank, prog, fs)
            )

        b2 = self.PRESETS[2]
        b3 = self.PRESETS[3]
        engine.register_footswitch(
            2,
            double_press(self.make_program_switcher(b2[1], b2[2], 2),
                         show_config_list,
                         3
                         )
        )
        engine.register_footswitch(
            3,
            double_press(self.make_program_switcher(b3[1], b3[2], 3),
                         show_config_list,
                         2
                         )
        )
        self.controller.activate(engine, 0)
        initial = self.PRESETS[self.INITIAL_PRESET]
        engine.set_program(rak_port, initial[1], initial[2])
        engine.seq.sendEvent(ControlChange(0, 0, 7, initial[3]), rak_port)

class RakFunConfig(RakStdConfig):
    NAME = 'Rak Fun'
    PRESETS = [
        ('Fuzz', 0, 6, 63),     # Tight Rock
        ('Bass', 0, 29, 63),    # Bass
        ('Angl', 0, 32, 63),    # Angel's Chorus
        ('Pit', 0, 8, 63),      # Summer by the Pit
    ]

class RakAccConfig(RakStdConfig):
    NAME = 'Rak Acoustic'
    PRESETS = [
        ('12St', 1, 33, 70),    # 12 String
        ('AcBr', 1, 17, 63),    # Acoustic Bright
        ('AcCh', 1, 14, 63),    # Acoustic Chorus
        ('ClCh', 1, 20, 63),    # Clean Chord
    ]

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
        super().on_enter()
        engine.midi_connect('pidal/to_rak',
                            'rakarrack-plus/rakarrack-plus IN')

        engine.jack_connect('system:capture_1', 'rakarrack-plus:in_1')
        engine.jack_connect('system:capture_1', 'rakarrack-plus:in_2')

class ZynConfig(ConfigFramework):
    PRESETS = (
        (0, 33),        # 0 - Arp, Sequence 2

        (10, 2),        # 1 - Space Synth
        (19, 3),        # 2 - DX Rhodes 4
        (4, 26),        # 3 - Sweep Synth
        (4, 39),        # 4 - Master Synth Low
        (4, 40),        # 5 - Master Synth High
        (10, 11),       # 6 - Space Choir 2
        (10, 32),       # 7 - Impossible Dream 1
        (10, 42),       # 8 - Rhodes Space 2
        (13, 1),        # 9 - Bells 1
        (24, 111),      # 10 - Fat Saw
        (9, 64),        # 11 - Dream of the saw

        (15, 10),       # 12 - Organ 11
        (16 , 8),       # 13 - Resonance pad 2
        (8, 0),         # 14 - Drums
        (3, 64),        # 15 - Vocal Morph 1
    )


    def __init__(self):
        def act(bank: int, program: int):
            def enable():
                print(f'setting program bank = {bank}, program = {program}')
                engine.set_program(zyn_port, bank * 128, program)
                engine.seq.sendEvent(ControlChange(0, 0, 7, 64), zyn_port)
            return Actuator(enable, lambda: None)

        super().__init__(
            'ZynConfig',
            FlagSetController(['1', '2', '4', '8'],
                              [act(bank, prog) for bank, prog  in self.PRESETS]
                              )
        )

    def on_enter(self):
        self.zyn_proc = ProcessManager(Popen(['zynaddsubfx', '-U']))
        engine.wait_for_jack('zynaddsubfx:out_1')
        engine.wait_for_jack('zynaddsubfx:out_2')
        engine.wait_for_midi('ZynAddSubFX/ZynAddSubFX')
        engine.midi_connect('pidal/to_zyn', 'ZynAddSubFX/ZynAddSubFX')
        engine.midi_connect('Q25/Q25 MIDI 1', 'ZynAddSubFX/ZynAddSubFX')
        engine.jack_connect('zynaddsubfx:out_1', 'system:playback_1')
        engine.jack_connect('zynaddsubfx:out_2', 'system:playback_2')
        super().on_enter()

    def on_leave(self):
        super().on_leave()
        self.zyn_proc = None

simple = GuitarixSimple()
engine.set_config(simple)
engine.add_config(simple)
engine.add_config(ModConfig.read_file('MesaStomp.modcfg'))
engine.add_config(ModConfig.read_file('SimpleClean.modcfg'))
engine.add_config(ModConfig.read_file('ScreamingBird.modcfg'))
engine.add_config(FirstConfig())
engine.add_config(NewConfig())
engine.add_config(ZynConfig())

# Wait for rakarrack asynchronously (since for some reason it takes a really
# long time to start) and then register the configs for it.

def wait_for_rak():
    engine.wait_for_jack('rakarrack-plus:in_1', timeout=600)
    engine.wait_for_jack('rakarrack-plus:in_2')
    engine.wait_for_jack('rakarrack-plus:out_1')
    engine.wait_for_jack('rakarrack-plus:out_2')
    engine.add_config(RakAccConfig(), index=1)
    engine.add_config(RakFunConfig(), index=2)
    engine.add_config(RakBizConfig())

thread = threading.Thread(target=wait_for_rak)
thread.setDaemon(True)
thread.start()


