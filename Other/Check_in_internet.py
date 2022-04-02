from global_hotkeys import *
import time
from tkinter import Tk  # Python 3
import webbrowser
from tkinter import Tk
import sys


print(sys.executable)
# Flag to indicate the program whether should continue running.
is_alive = True

print("Установите курсор на строку браузера ПОСЛЕ знака \" ")
print("Отсчет времени: ")
for i in range(5, 0, -1):
    print("{} сек...\r".format(i), end="")
    time.sleep(1)

BROWSER_X, BROWSER_Y = gui.position()


print("Установите курсор на строку карточки")
print("Отсчет времени: ")
for i in range(5, 0, -1):
    print("{} сек...\r".format(i), end="")
    time.sleep(1)

CARD_X, CARD_Y = gui.position()


# Our keybinding event handlers.
def insert_in_browser():
    # x, y = gui.position()
    gui.click(BROWSER_X, BROWSER_Y)
    gui.hotkey("end")
    gui.hotkey("ctrl", 'backspace')
    gui.hotkey("ctrl", "v")
    gui.hotkey("enter")
    
    gui.click(CARD_X, CARD_Y)
    gui.hotkey("ctrl", "a")
    gui.hotkey("backspace")
    gui.hotkey("ctrl", "v")
    
    # gui.moveTo(x, y)
    

def exit_application():
    global is_alive
    stop_checking_hotkeys()
    is_alive = False


# Declare some key bindings.
# These take the format of [<key list>, <keydown handler callback>, <keyup handler callback>]

binds = [[["control", "c", "space"], "insert_in_browser"]]

bindings = [
    [binds[0][0], None, insert_in_browser]
]
# Register all of our keybindings
register_hotkeys(bindings)

# Finally, start listening for keypresses
start_checking_hotkeys()

# Keep waiting until the user presses the exit_application keybinding.
# Note that the hotkey listener will exit when the main thread does.

print(f"Current_binds:")
for binding in binds: 
    print(binding)

# while is_alive:
#     time.sleep(0.1)