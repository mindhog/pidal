"""Hog 1 Pidal User interface."""

import attr
from engine import Config, Engine
from typing import Callable, List, Optional
from tkinter import Button, Frame, Label, Listbox, Tk, Toplevel, BOTH, END, \
    NSEW, W
from tkinter.font import Font

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
        engine.register_microswitch(1, self.select_last)
        engine.register_microswitch(2, self.select_next)
        engine.register_microswitch(3, self.selected)

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
        self.selection_clear(cur)
        self.selection_set(cur + 1)

    def select_last(self):
        cur = self.__get_selection()
        self.selection_clear(cur)
        self.selection_set(cur - 1)

    def close(self):
        Engine.get_instance().pop_switch_configs()
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

    def show_menu(self, *args):
        items = [MenuItem('Edit Config', edit_config_selected),
                MenuItem('List Configs', list_configs_selected)
                ]
        menu = Menu(self.winfo_toplevel(), items)

    def on_config_change(self, config: Config) -> None:
        self.title.configure(text=config.name)
        for i, button_name in enumerate(config.buttons):
            self.buttons[i].set_title(button_name)

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
