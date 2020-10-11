"""Hog 1 Pidal User interface."""

import attr
from engine import Config, Engine, ProcessManager
from typing import Any, Callable, List, Optional
from tkinter import Button, Frame, Label, Listbox, Tk, Toplevel, BOTH, END, \
    NSEW, W
import subprocess
from tkinter.font import Font

def fs_pressed(action: Callable[[], None]) -> Callable[[bool], Any]:
    """Returns a handler that calls 'action' only when the button is pressed.
    """
    def handler(pressed: bool):
        if pressed:
            action()
    return handler

@attr.s
class MenuItem:
    text : str = attr.ib()
    func : Callable[['Screen'], None] = attr.ib()

class Menu(Listbox):

    def __init__(self, parent: Frame, data: List[MenuItem]):
        super().__init__(parent, font=Font(family='Liberation Sans', size=48))
        self.data = data

        for item in data:
            self.insert(END, item.text)

        parent.set_parcel(self)

        self.bind('<Double-Button-1>', self.selected)
        engine = Engine.get_instance()
        engine.push_switch_configs()
        engine.register_microswitch(0, self.close)
        engine.register_microswitch(1, self.select_prev)
        engine.register_microswitch(2, self.select_next)
        engine.register_microswitch(3, self.selected)

        self.selection_set(0)

        engine = Engine.get_instance()
        engine.push_fs()
        engine.register_footswitch(0, fs_pressed(self.select_prev))
        engine.register_footswitch(1, fs_pressed(self.select_next))
        engine.register_footswitch(2, fs_pressed(self.selected))
        engine.register_footswitch(3, fs_pressed(self.close))

        # Just to simplify navigation
        self.bind('<Escape>', self.close)

    def __get_selection(self):
        cur = self.curselection()
        if cur:
            cur = cur[0]
            self.selection_clear(cur)
        else:
            cur = 0
        return cur

    def select_next(self):
        cur = self.__get_selection()
        if cur < len(self.data) - 1:
            self.selection_clear(cur)
            self.selection_set(cur + 1)

    def select_prev(self):
        cur = self.__get_selection()
        if cur:
            self.selection_clear(cur)
            self.selection_set(cur - 1)

    def close(self):
        engine = Engine.get_instance()
        engine.pop_switch_configs()
        engine.pop_fs()
        self.destroy()

    def selected(self, *evt) -> Optional[str]:
        selections = self.curselection()
        if selections:
            item = self.data[selections[0]]
            toplevel = self.winfo_toplevel()
            self.close()
            item.func(toplevel)
        return 'break'

def edit_config_selected(screen: 'Screen') -> None:
    print('got menu')

def list_configs_selected(screen: 'Screen') -> None:
    engine = Engine.get_instance()
    items = [
        MenuItem(config.name, lambda s, cfg=config: engine.set_config(cfg))
        for config in engine.get_all_configs()
    ]
    menu = Menu(screen, items)

def restart_shell_selected(screen: 'Screen') -> None:
    screen.destroy()

def shutdown_selected(screen: 'Screen') -> None:
    subprocess.call(['sudo', 'shutdown', '-h', 'now'])

# XXX Put this in another module.

pre_tuner_config = None
tuner_proc = None

def end_tuner(pressed: bool) -> None:
    global tuner_proc
    tuner_proc = None
    Engine.get_instance().set_config(pre_tuner_config)

def tuner_selected(screen: 'Screen') -> None:
    global pre_tuner_config, tuner_proc
    engine = Engine.get_instance()
    pre_tuner_config = engine.cur_config
    engine.set_config(Config('Tuner'))
    tuner_proc = ProcessManager(subprocess.Popen(['lingot']))
    for i in range(4):
        engine.register_footswitch(i, end_tuner)

class FSButton(Button):
    """Panel to show the state of a footswitch button."""

    def __init__(self, parent: Frame, text: str):
        super().__init__(parent, text=text,
                         anchor=W,
                         font=Font(family='Liberation Sans', size=48),
                         )

    def set_title(self, text: str) -> None:
        self.configure(text=text)

class Home(Frame):

    def __init__(self, top: Toplevel):
        super().__init__(top)
        self.title = Label(self, text='Config Name',
                           font=Font(family='Roboto', size=72)
                           )
        self.title.grid(row=0, column=0, columnspan=4, sticky=NSEW)
        self.rowconfigure(0, weight=1)

        self.buttons = []
        for i, name in enumerate(('Dist', 'Wah', 'Phase', 'Lead')):
            btn = FSButton(self, name)
            self.buttons.append(btn)
            btn.grid(row=1, column=i, sticky=NSEW)
            self.columnconfigure(i, weight=1, uniform=True)

        engine = Engine.get_instance()
        engine.subscribe('config_change', self.on_config_change)
        engine.register_microswitch(0, self.show_menu)

        engine.subscribe('pedal_button_status', self.on_pedal_button_status)
        engine.subscribe('config_list',
                         lambda scr=top: list_configs_selected(scr))

    def show_menu(self, *args):
        items = [MenuItem('Edit Config', edit_config_selected),
                 MenuItem('List Configs', list_configs_selected),
                 MenuItem('Tuner', tuner_selected),
                 MenuItem('Restart Shell', restart_shell_selected),
                 MenuItem('Shutdown', shutdown_selected),
                 ]
        menu = Menu(self.winfo_toplevel(), items)

    def on_config_change(self, config: Config) -> None:
        self.title.configure(text=config.name)
        for i, button_name in enumerate(config.buttons):
            self.buttons[i].set_title(button_name)
            self.buttons[i].configure(foreground='LawnGreen',
                                      background='black'
                                      )

    def on_pedal_button_status(self, pedal: int, active: bool) -> None:
        if active:
            self.buttons[pedal].configure(background='darkgreen',
                                          foreground='yellow'
                                          )
        else:
            self.buttons[pedal].configure(background='black',
                                          foreground='LawnGreen'
                                          )

class Screen(Tk):

    def __init__(self):
        super().__init__()
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.home = Home(self)
        self.set_parcel(self.home)
        self.bind('<Escape>', self.home.show_menu)
#        self.home.grid(row=0, column=0, sticky=NSEW)
#        self.home.pack(expand=True, fill=BOTH)

#        for i, (font, size) in enumerate((('Helvetica', 28),
#                                          ('Liberation Sans', 72),
#                                          ('Liberation Sans', 48),
#                                          ('Liberation Sans', 24),
#                                          ('Roboto', 72),
#                                          ('Roboto', 48),
#                                          ('Roboto', 24),
#                                          )):
#            t = Label(self, text=f'{font} {size}',
#                      font=Font(family=font, size=size))
#            t.grid(row=i, sticky=NSEW)

    def set_parcel(self, win: Frame) -> None:
        win.grid(row=0, column=0, sticky=NSEW)
        win.focus()
        win.tkraise()

if __name__ == '__main__':
    main = Screen()
    main.mainloop()
