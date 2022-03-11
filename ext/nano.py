"""Korg Nano Module.
"""
from engine import Engine
from midi import Event, ControlChange

def event_handler(event: Event):
    if isinstance(event, ControlChange):
        engine = Engine.get_instance()
        engine.get_config().set_controller(f'nano.{event.controller}',
                                           event.value)

def init():
    engine = Engine.get_instance()
    for port_info in engine.seq.iterPortInfos():
        if port_info.fullName == 'nanoKONTROL/nanoKONTROL MIDI 1':
            break
    else:
        return

    port = engine.seq.createInputPort('nano_in')
    engine.midi_connect(port_info.fullName, 'pidal/nano_in')
    engine.add_midi_input_handler(input_handler)
