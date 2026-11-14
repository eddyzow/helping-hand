"""Shared by the dispatcher and the skills. They live here, not in core/dispatcher.py, because
`python -m core.dispatcher` runs that file as __main__: a skill importing core.dispatcher would
get a second copy of the module, with its own events that nobody sets."""
import threading

cue = threading.Event()      # 'start now' from outside, such as the game's restart key
waiting = threading.Event()  # set while a skill is waiting for that cue
key_down = threading.Event()  # the keypad's jump key is held down right now (reported by keypad/listen.py)
key_events = [0]              # how many such reports have arrived; 0 means no listener is feeding us
