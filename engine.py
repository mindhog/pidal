"""Hog 1 Pidal engine."""

from __future__ import annotations

import abc
import amidi
import asyncio
from importlib import import_module
import jack
from midi import ControlChange, Event, ProgramChange
from subprocess import Popen
import threading
import time
from typing import Callable, List, Optional, Tuple, Union
from RPi import GPIO

class ProcessManager:

    def __init__(self, proc: Popen):
        self.__proc = proc

    def __del__(self):
        self.__proc.kill()
        self.__proc.wait()

_engine : Engine = None

class Config:

    def __init__(self, name: str):
        self.name = name
        self.buttons = ['1', '2', '3', '4']

    def on_enter(self):
        """Called when the config is selected.

        Note that this is probably temporary: I really want there to be an
        engine state vector where the individual items are
        activated/deactivated when we enter or leave.
        """
        pass

    def on_leave(self):
        """Called when the config is active and a different config is selected.

        Note that this is probably temporary: I really want there to be an
        engine state vector where the individual items are
        activated/deactivated when we enter or leave.
        """
        pass

    def set_controller(self, controller: str, value: int) -> None:
        """Called by extensions to set the value of a controller.

        Controller names are specific to the extension.
        """
        pass

class ExtensionConfig(metaclass=abc.ABCMeta):
    """Interface for extensions."""

    @abc.abstractmethod
    def init(self, config: Config):
        """Initialize the extension.

        This should be called once at the initialization of the Config, before
        it is registered with the Engine.
        """

class InvalidPortError(Exception):
    """Raised when a specified port does not exist."""

# Footswitch GPIO port numbers.
FSIO = [16, 20, 21, 26]

class Engine:


    def __init__(self):
        self.__footswitches : List[Callable[[bool], None]] = \
            [None, None, None, None]
        self.__last_press = [0, 0, 0, 0]
        self.__fs_pressed = [ False, False, False, False]
        self.__microswitches : List[Callable[[], None]] = \
            [None, None, None, None]
        self.__ms_stack = [self.__microswitches]
        self.__fs_stack = [self.__footswitches]

        self.seq = amidi.getSequencer(name = 'pidal')
        self.jack = jack.Client('pidal')
        self.configs = []
        self.cur_config = None
        self.subscriptions = {}
        self.__midi_handlers = []
        self.__async_thread = \
            self.__start_daemon_thread(self.__async_thread_func)
        self.__midi_input_thread = \
            self.__start_daemon_thread(self.__midi_input_thread_func)

    def __start_daemon_thread(self, func):
        thread = threading.Thread(target=func)
        thread.setDaemon(True)
        thread.start()
        return thread

    def __async_thread_func(self):
        asyncio.run(self.__fs_mon())

    async def __fs_mon(self):
        while True:
            await asyncio.sleep(0.1)
            t = time.time()
            for i in range(4):
                if self.__fs_pressed[i] and t - self.__last_press[i] > 0.1:
                    # A value of zero indicates that the button is still
                    # pressed, if it's 1 the button has been released.
                    if GPIO.input(FSIO[i]):
                        # Store the last press time to deal with bounces on
                        # button release.
                        self.__last_press[i] = time.time()
                        self.__fs_pressed[i] = False
                        handler = self.__footswitches[i]
                        if handler:
                            handler(False)

    def __midi_input_thread_func(self):
        """The midi input thread.  We can't do async for this."""
        while True:
            event = self.seq.getEvent()
            for handler in self.__midi_handlers:
                try:
                    if handler(event):
                        break
                except:
                    pass

    def register_footswitch(self, footswitch: int,
                            callback: Callable[[bool], None]
                            ) -> None:
        """

        Args:
            footswitch: Index of the footswitch to bind.  Must be from 0 to 3.
            callback: Function to be called when the footswitch is
                pressed/released.  This is called with True when the switch is
                pressed, False when released.  Debouncing is done by the
                engine.
        """
        print(f'registering {callback} at {footswitch}')
        self.__footswitches[footswitch] = callback

    def footswitch_pressed(self, index: int):
        """Called when a footswitch is pressed.

        Args:
            index: The footswitch index.  Should be 0..3.
        """
        # If the last press was less than a 10th of a second ago, ignore it as
        # it's probably just a bounce.
        t = time.time()
        if not self.__fs_pressed[index] and t - self.__last_press[index] > 0.1:
            print(f'pressing footswitch {index}')
            self.__footswitches[index](True)
            self.__fs_pressed[index] = True
        self.__last_press[index] = t

    def emulate_footswitch(self, index: int, pressed: bool):
        """Call the footswitch callback as if a footswitch had been
        pressed/released.

        Args:
            index: button index
            pressed: True if the button is pressed, false if released.
        """
        self.__footswitches[index](pressed)

    def is_fs_pressed(self, index: int) -> bool:
        """Returns true if the footswitch is currently pressed."""
        return self.__fs_pressed[index]

    def push_switch_configs(self):
        self.__microswitches = [None, None, None, None]
        self.__ms_stack.append(self.__microswitches)

    def pop_switch_configs(self):
        if len(self.__ms_stack) > 1:
            self.__ms_stack.pop()
        else:
            # This is a hack, for some reason we're bottoming out.
            print('hit bottom')
        self.__microswitches = self.__ms_stack[-1]

    def push_fs(self):
        self.__footswitches = [None, None, None, None]
        self.__fs_stack.append(self.__footswitches)

    def pop_fs(self):
        if len(self.__fs_stack) > 1:
            self.__fs_stack.pop()
        else:
            print('hit bottom on footswitch stack')
        self.__footswitches = self.__fs_stack[-1]

    def register_microswitch(self, index: int,
                             callback: Callable[[], None]
                             ) -> None:
        self.__microswitches[index] = callback

    def microswitch_pressed(self, index: int):
        # We don't do debouncing for the microswitches because this doesn't
        # seem to be a problem.
        if self.__microswitches[index]:
            self.__microswitches[index]()

    def initialize(self):
        GPIO.setmode(GPIO.BCM)
        BUTTONS = tuple((io, lambda x, i=i: self.footswitch_pressed(i))
                        for io, i in zip(FSIO, range(4))) + (
            (17, lambda x: self.microswitch_pressed(0)),
            (22, lambda x: self.microswitch_pressed(1)),
            (23, lambda x: self.microswitch_pressed(2)),
            (27, lambda x: self.microswitch_pressed(3)),
        )
        for gpio, callback in BUTTONS:
            GPIO.setup(gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(gpio, GPIO.FALLING, callback=callback)
        import_module('custom')

    def get_port(self, name: str) -> Optional[amidi.PortInfo]:
        """Returns the PortInfo object with the given name.

        Returns None if there is no port of that name.
        """
        return self.seq.getPort(name)

    def __get_port(self, port: Union[amidi.PortInfo, str]) -> amidi.PortInfo:
        """Returns the PortInfo object with the given name.

        Throws a ValueError if the port is undefined.
        """
        if isinstance(port, amidi.PortInfo):
            return port
        else:
            port = self.get_port(port)
            if not port:
                raise ValueError(f'Port {port} does not exist')

    def set_program(self, port: Union[amidi.PortInfo, str], bank: int,
                    program: int
                    ) -> None:
        """Set the bank and program as specified."""
        port = self.__get_port(port)
        self.seq.sendEvent(ControlChange(0, 0, 0, bank >> 7), port)
        self.seq.sendEvent(ControlChange(0, 0, 32, bank & 127), port)
        self.seq.sendEvent(ProgramChange(0, 0, program), port)

    def wait_for_jack(self, port_name: str, timeout: float =3.0):
        end_time = time.time() + timeout
        print(f'xxx time is {time.time()} waiting until {end_time}')
        while time.time() < end_time:
            for port in self.jack.get_ports():
                if port.name == port_name:
                    return
            time.sleep(0.1)
        print(f'xxx timed out at {time.time()}')
        raise Exception('timed out waiting for %s' % port_name)

    def wait_for_midi(self, port_name: str, timeout: float = 5.0):
        end_time = time.time() + timeout
        while time.time() < end_time:
            for port in self.seq.iterPortInfos():
                if port.fullName == port_name:
                    return
            time.sleep(0.1)
        raise Exception('timed out waiting for %s' % port_name)

    def jack_disconnect_all(self, port: str, output_port: bool):
        for con in self.jack.get_all_connections(port):
            if output_port:
                self.jack.disconnect(port, con)
            else:
                self.jack.disconnect(con, port)

    def jack_connect(self, src_port: str, dst_port: str) -> None:
        self.jack.connect(src_port, dst_port)

    def midi_connect(self, src_port: str, dst_port: str) -> None:
        s = self.seq.getPort(src_port)
        d = self.seq.getPort(dst_port)
        if not s:
            raise InvalidPortError(f'port {src_port} does not exist')
        self.seq.connect(s, d)

    def add_config(self, config: Config, index: Optional[int] = None) -> None:
        """Add a new config to the set of configs for the engine."""
        if index is None:
            self.configs.append(config)
        else:
            self.configs.insert(index, config)

    def get_all_configs(self) -> Tuple[Config]:
        """Returns the list of configs."""
        return tuple(self.configs)

    def set_config(self, config: Config) -> None:
        """Set the current config."""
        # Don't bother with this if 'config' is already active.
        if self.cur_config is config:
            return
        if self.cur_config:
            self.cur_config.on_leave()
        self.cur_config = config
        self.cur_config.on_enter()
        self.notify('config_change', config)

    def subscribe(self, event: str, callable: Callable[..., None]) -> None:
        self.subscriptions[event] = callable

    def notify(self, event: str, *args) -> None:
        handler = self.subscriptions.get(event)
        if handler:
            self.subscriptions[event](*args)

    def add_midi_input_handler(self, handler: Callable[[Event],  bool]):
        """Adds a new midi input handler.

        The handler accepts an event and returns true if it has fully
        processed the event, false if the event should be delegated to
        subsequent handlers in the chain.
        """
        self.__midi_handlers.append(handler)

    def remove_midi_input_handler(self, handler: Callable[[Event],  bool]):
        """Remove the specified handler from the handler chain."""
        self.__midi_handlers.remove(handler)

    def set_controller(self, controller: str, value: int):
        """Set the value of a controller.

        This also translates the controller name per the config.
        """
        self.cur_config.set_controller(controller, value)

    @classmethod
    def get_instance(cls):
        global _engine
        if not _engine:
            _engine = cls()
        return _engine
