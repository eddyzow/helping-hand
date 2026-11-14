"""Shared by the dispatcher and the skills. They live here, not in core/dispatcher.py, because
`python -m core.dispatcher` runs that file as __main__: a skill importing core.dispatcher would
get a second copy of the module, with its own events that nobody sets."""
import threading

cue = threading.Event()      # 'start now' from outside, such as the game's restart key
waiting = threading.Event()  # set while a skill is waiting for that cue
