"""Timestamped key events shared by the simulation and physical replay."""

import csv
from dataclasses import dataclass
import math
from pathlib import Path


@dataclass(frozen=True)
class KeyEvent:
    at: float
    down: bool


def read_pattern(path: Path) -> list[KeyEvent]:
    events = []
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != ["time_ms", "state"]:
            raise ValueError("CSV header must be time_ms,state")
        for row in reader:
            try:
                at = float(row["time_ms"]) / 1000
            except (TypeError, ValueError) as error:
                raise ValueError(f"Line {reader.line_num} needs a numeric time_ms") from error
            if not math.isfinite(at) or at < 0 or (events and at <= events[-1].at):
                raise ValueError(f"Line {reader.line_num} needs an increasing, nonnegative time_ms")
            expected = "up" if len(events) % 2 else "down"
            if row["state"] != expected or None in row:
                raise ValueError(f"Line {reader.line_num} must have state {expected!r}")
            events.append(KeyEvent(at, expected == "down"))
    if not events or events[-1].down:
        raise ValueError("The pattern needs at least one full press and release")
    return events


def command_times(events: list[KeyEvent], press_lead_ms: float, release_lead_ms: float) -> list[KeyEvent]:
    leads = {True: press_lead_ms / 1000, False: release_lead_ms / 1000}
    if any(not math.isfinite(lead) or lead < 0 for lead in leads.values()):
        raise ValueError("Timing leads must be finite and nonnegative")
    commands = [KeyEvent(event.at - leads[event.down], event.down) for event in events]
    if any(following.at <= prior.at for prior, following in zip(commands, commands[1:])):
        raise ValueError("Timing leads put commands out of order")
    return commands
