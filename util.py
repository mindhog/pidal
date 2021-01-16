import abc
import attr
from engine import Config, Engine
import itertools
from typing import Any, Callable, List

engine = Engine.get_instance()

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

class Button:
    """Should have a text attribute and a make_callback method?"""
    def __init__(self, text: str,
                 make_callback: Callable[[int], Callable[[bool], Any]]):
        self.text = text
        self.make_callback = make_callback

class ButtonGroup(abc.ABC):
    """A group of buttons or a single button that work together."""

    @abc.abstractmethod
    def make_button_callback(self, index: int) -> None:
        pass

    @abc.abstractmethod
    def expand_buttons(self) -> List[Button]:
        pass

class ToggleButton(ButtonGroup):
    def __init__(self, text: str, enable: Callable[[], Any],
                 disable: Callable[[], Any],
                 enabled: bool = False):
        self.text = text
        self.enable = enable
        self.disable = disable
        self.enabled = enabled

    def make_callback(self, index: int) -> None:
        def button_callback(pressed: bool) -> None:
            if pressed:
                if self.enabled:
                    self.disable()
                    engine.notify('pedal_button_status', index, False)
                else:
                    self.enable()
                    engine.notify('pedal_button_status', index, True)
        return button_callback

    def expand_buttons(self):
        return [self]

class RadioButton:
    def __init__(self, text: str, enable: Callable[[], Any],
                 disable: Callable[[], Any],
                 active=False):
        self.text = text
        self.enable = enable
        self.disable = disable

class RadioController(ButtonGroup):
    """Manages the button interfaces radio-button style.

    This class basically keeps track of the currently active button and when a
    new button is activated (see activate()) it notifies the engine to
    activate the new button and deactivate the old one.
    """

    def __init__(self, buttons: List[RadioButton], active: int = 0):
        """
        Args:
            active: The active button number.
        """
        self.buttons = buttons
        self.active = active

    def make_button_callback(self, index: int) -> None:
        def button_callback(pressed: bool) -> None:
            if pressed:
                self.buttons[self.active].disable()
                self.buttons[index].enable()
                engine.notify('pedal_button_status', self.active, False)
                engine.notify('pedal_button_status', index, True)
                self.active = index

        return button_callback

    def expand_buttons(self):
        return [Button(button.text, self.make_button_callback)
                for button in self.buttons]

class ConfigFramework(Config):
    """Config base class that lets you define a config in terms of a
    standardized set of button behaviors and a standardized set of actions.
    """

    def __init__(self, name: str, *button_groups: List[ButtonGroup]):
        """
        Args:
            buttons: An array of exactly four buttons.
        """
        super().__init__(name)
        buttons = list(itertools.chain.from_iterable(
            group.expand_buttons() for group in button_groups))
        assert(len(buttons) == 4)
        self.buttons = [button.text for button in buttons]

    def on_enter(self):
        for index, button in enumerate(buttons):
            callback = button.make_callback(index)
            if index == 2:
                callback = double_press(callback, show_config_list, 3)
            elif index == 3:
                callback = double_press(callback, show_config_list, 2)
            engine.register_footswitch(index, callback)

@attr.s
class Actuator:
    enable : Callable[[], Any] = attr.ib()
    disable : Callable[[], Any] = attr.ib()

class FlagSetController(ButtonGroup):
    """Manages a set of buttons, the permutations of whose states map to
    discrete configuration states.

    For example, two buttons would map to up to 8 different configuration
    states as follows:

        first button active | second button active | state
        ==================================================
        false               | false                | 0
        true                | false                | 1
        false               | true                 | 2
        true                | true                 | 3
    """

    def __init__(self, button_names: List[str], states: List[Actuator],
                 state: int = 0
                 ):
        """
        Args:
            active: The active button number.
        """
        self.button_names = button_names
        self.states = states
        self.state = state
        self.first = None

    def make_button_callback(self, index: int) -> None:
        # Compute the "relative index" -- index relative to the start of
        # the flag set buttons.
        if self.first is None:
            self.first = index
        rel_index = index - self.first

        def button_callback(pressed: bool) -> None:
            if pressed:
                # Calculate the new state index.
                mask = 1 << rel_index
                enable = not self.state & mask
                new_state = self.state ^ mask
                new_state = min(new_state, len(self.states))

                if new_state != self.state:
                    self.states[self.state].disable()
                    self.states[new_state].enable()
                    engine.notify('pedal_button_status', index, enable)
                    self.state = new_state

        return button_callback

    def expand_buttons(self):
        return [Button(name, self.make_button_callback)
                for name in self.button_names]
