"""Text through the actual controller with fake speech/send; no APIs, sockets or audio."""
from unittest.mock import patch

import robtop_voice as voice
import steady


def test_off_routes():
    for filtered in (False, True):
        for phrase in ("steady off", "filter off", "turn off the filter", "stop the steadying"):
            with patch.dict(steady.state, steady=filtered, hold=False), \
                    patch.object(voice, "tell", steady.command), patch.object(voice, "speak", lambda _: None):
                voice.exchange(phrase)
                assert steady.state["hold"] and steady.state["steady"] == filtered, (phrase, steady.state)


def test_negated_actions():
    failures = []
    for phrase in ("don't release", "don't drop it", "do not go home", "don't steady on"):
        line, _ = voice.understand(phrase)
        if line not in (None, "stop", "steady off", "hold on"):
            failures.append((phrase, line))
    assert not failures, ("negated action became a command", failures)


if __name__ == "__main__":
    test_off_routes()
    print("off phrases hold the actual controller in both filter states")
    test_negated_actions()
    print("negated action checks pass")
