"""FCB1010 Foot Controller module.
"""

from __future__ import annotations

from engine import Config, Engine, ExtensionConfig
from midi import ControlChange, Event, ProgramChange
import os
from typing import Callable, List

def footswitch_actuator(index: int) -> Callable[[Config], None]:
    """Returns a footswitch actuator which can be used as the action in a
    ProgramConfig, causing the specified footswitch to be virtually pressed
    and released when the program event comes in.
    """

    def func(config: Config):
        eng = Engine.get_instance()
        eng.set_config(config)
        eng.emulate_footswitch(index, True)
        eng.emulate_footswitch(index, False)

    func.__name__ = f'actuator{index}'
    return func

def config_change(config: Config):
    """Actuator that can be used to just switch to the associated config."""
    eng = Engine.get_instance()
    eng.set_config(config)

class ProgramConfig:
    def __init__(self, program: int, action: Callable[[Config], None]):
        """

        Args:
            program: Midi program number of the pedal that activates this
                action.
            action: Function to call when the midi program message is
                received.  The function will be called with the Config in
                which it was defined.
        """
        self.program = program
        self.action = action

class FCB1010Config(ExtensionConfig):

    def __init__(self, programs: List[ProgramConfig]):
        self.programs = programs

    def init(self, config: Config):
        for pc in self.programs:
            _program_map[pc.program] = lambda pc=pc: pc.action(config)

    def offset(self, offset: int) -> FCB1010Config:
        """Returns a config with program numbers incremented by the given
        offset.
        """
        return FCB1010Config([
            ProgramConfig(program.program + offset, program.action)
            for program in self.programs
        ])

_program_map : Dict[int, Callable[[Config], None]] = {}

def input_handler(event: Event) -> bool:
    if isinstance(event, ProgramChange) and event.program in _program_map:
        _program_map[event.program]()
        return True
    elif isinstance(event, ControlChange):
        controller_name = {
            7: 'RightPedal',
            27: 'LeftPedal'
        }.get(event.controller)
        if controller_name:
            Engine.get_instance().set_controller(controller_name, event.value)
    else:
        return False

def init():
    # Make sure we have a midi soundcard defined.
    sc_midi = os.environ.get('SOUNDCARD_MIDI')
    if not sc_midi:
        print('Error: no soundcard midi interface defined')
        return

    engine = Engine.get_instance()
    port = engine.seq.createInputPort('fcb1010_in')
    engine.midi_connect(sc_midi, 'pidal/fcb1010_in')
    engine.add_midi_input_handler(input_handler)
