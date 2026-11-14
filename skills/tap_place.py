"""Hold the fingertip where the jump key should be, so a person can slide the keypad under it.

    run tap_place        the arm goes above its tap spot and stays there, motors holding
    (slide the keypad so the jump key is right under the tip, tape it down, hands away)
    run tap_calibrate    the arm finds the key by touch

This way nobody poses the arm by hand: the arm goes to its spot and the keypad comes to the arm.
It deliberately does not go home at the end; the next skill starts by going home.
"""
NAME = "tap_place"
DESCRIPTION = "Hold the fingertip above the tap spot so the keypad can be placed under it"
PARAMS = {}


def run(arm, params, stop):
    return {"ok": True, "reason": "holding above the tap spot"} if arm.to_key() else {"ok": False, "reason": "stopped"}
