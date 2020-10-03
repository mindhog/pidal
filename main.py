from ui import Screen
from engine import Engine

engine = Engine.get_instance()
main_screen = Screen()
engine.initialize()

main_screen.mainloop()
