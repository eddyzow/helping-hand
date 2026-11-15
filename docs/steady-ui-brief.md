# Steady Hand console: UI brief (version 2)

Written Sat Nov 14 for the dashboard redesign. Part A is the product record the impeccable skill
asks for (it would live in `PRODUCT.md`; the repo keeps new `.md` files inside `docs/`, so it lives
here). Part B is the surface brief for `steady_dashboard.html`. The data and commands are in
`docs/steady-contract.md`; the visual system is in `docs/steady-design.md`.

Facts marked *(assumed)* were inferred from the owner's written request and the contract, not
confirmed by him in an interview: the build ran as a subagent with no way to ask.

---

## Part A: product record

<!-- impeccable:product-schema 1 -->

### Platform

web (one page served by `steady.py` on the laptop next to the arms; opened in a desktop browser,
sometimes on a phone)

### Users

1. **A judge at the HackUMass med-tech table**, standing about two metres from a laptop screen,
   for two or three minutes. They must see, without being told, that the hand shakes and the arm
   does not, and they must never see the arm stop without a reason on screen.
2. **In the story: a physiotherapist** setting up a session for a person with a tremor: choosing
   the person's profile, calibrating, adjusting sensitivity and the filter, reading the
   measurements afterwards.
3. **In the story: the person with the tremor**, holding the leader arm. They glance at the screen
   for one thing: is the arm following me, and if not, why, and what do I press.

### Product purpose

Steady Hand is an assistive teleoperation prototype. A person moves a small leader arm; the
follower arm (RobTop) copies the movement with the tremor filtered out, scaled up for people who
move through a small range, and with a grip that stays where the hand squeezed. The page is the
console for it: live state, the measured comparison, controls, per-user calibration, activities
and session records. Success at the demo: a judge understands the comparison in seconds, and
every stop is explained in words.

### Positioning

The comparison is measured on the real arms, both fingertips through the same tremor-band
measurement (RMS of the 3 to 12 Hz movement over the last 4 seconds, in mm), with the filter on
or off on request. The page shows that measurement live; it does not show a claim.

### Operating context

- One laptop on a judging table, 1440x900 or 1280x800, ambient hall light, viewed from two metres
  and from arm's length. A phone (390x844) may open it on the same network.
- The controller is a Python process; the page polls `/state` about ten times a second and sends
  one-line commands to `/cmd`. An older controller may lack every new key.
- The keypad next to the arm has keys for the filter and Hold; the page must agree with them.

### Capabilities and constraints

- Everything in `docs/steady-contract.md`: filter on/off, Hold, cut-off, sensitivity (gain 1.0 to
  3.0), neutral pose, grip hold and release, user profiles, calibration (rest 3 s, move 12 s),
  the 10 s hold-still test, voice report, activities, sessions.
- No network at run time beyond the controller: no CDN, no web fonts. System fonts only.
- The 3D view is a separate module (`dashboard/arm3d.js`, owned by the 3D lane) mounted into
  `#arm3d`; a 2D side view is the fallback.

### Brand commitments (owner's standing taste, binding)

- Light, warm-neutral surfaces; mostly opaque cards.
- One accent, plum `#6b2d5c`, for RobTop's arm and for primary controls. Rust `#b8552f` is
  reserved for the hand's signal.
- No emoji, no decorative dots, no gratuitous gradients.
- CSS names `--paper --card --ink --soft --line --plum --raw --ok` are kept (the 3D view reads them).
- The owner asked for a clinical, medical-device console look, research from Mobbin, and this
  brief before code.

### Evidence on hand

- Live data from the controller (`/state`, `/sessions`). No patient data, no clinical study, no
  testimonials. The prototype was tested with team members shaking the leader on purpose.

### Product principles

1. **State in words first.** What the arm is doing, and why it is not following, is the first
   thing on the page, in a sentence, never in colour alone.
2. **Measurements, labelled as measurements.** Every number has its unit and its method a click
   or a line away. No health status, no diagnosis, no claim that anything improves a tremor.
3. **The comparison is the proof.** Hand and arm on one scale, side by side.
4. **Calm under failure.** A lost connection, an old controller or a page error is said plainly,
   controls that would send commands are disabled, and the reason is next to them.

### Accessibility and inclusion

- Readable from two metres: status sentence at least 22px, primary values at least 40px.
- The users in the story have a tremor: controls are large (at least 44px tall), with generous
  spacing; sliders have wide thumbs and step in useful increments.
- WCAG AA contrast for text; visible keyboard focus; `prefers-reduced-motion` respected; state
  never carried by colour alone (each status has a word and a glyph shape).

---

## Part B: surface brief (`steady_dashboard.html`)

### Mode

Operate. The visitor completes a task (demo, set up, calibrate, read). Familiar affordances win
over expression; the clinical character lives in precise details.

### Jobs, in priority order

1. Know what the system is doing now and, if the arm is still, why and what to press.
2. See the comparison: hand shake vs arm shake vs share removed, measured.
3. Watch the robot (3D view).
4. Change the essentials: tremor filter, Hold, sensitivity, response speed, neutral pose.
5. Manage the grip: see squeeze, held grip and claw opening; let go; grip-hold mode.
6. Choose the user; run calibration step by step.
7. Run and read activities (hold-still test, range, steady time, longest grip).
8. Read the session: this session's summary, trends, observations, voice, past sessions.

### Information hierarchy (top to bottom at 1440x900)

1. **Device bar** (thin): product name, prototype label, current user and calibration state,
   connection and time of the last good update.
2. **Status strip** (full width, the loudest element): status class word, glyph, one sentence,
   and the one action that resolves it (for example a Resume button when holding).
3. **First viewport body**, three columns: measurement panel (comparison) | 3D robot view |
   control rail (filter, Hold, sensitivity, response, neutral pose; grip below).
4. **Procedure panel** (calibration), inserted directly under the status strip while it runs.
5. Below the fold: profile and calibration, activities with the test runner, this session,
   30 s chart, trend, observations, voice, past sessions, footer.

### Tone

Clinical, calm, trustworthy: a device console, the register of a patient monitor or a rehab
device's operator screen, not a startup landing page. Short declarative labels, sentence case,
units always. No exclamation marks, no hype, no "AI".

### Visual system (summary; tokens in `docs/steady-design.md`)

- **Type:** system UI stack (Segoe UI Variable / Segoe UI on the demo laptop), one family.
  Scale 12 / 13 / 15 / 17 / 22 / 28 / 44 / 64 px; tabular figures for every number. Labels are
  sentence case at 13px weight 600, never tracked uppercase micro-labels.
- **Spacing:** 4px base: 4, 8, 12, 16, 24, 32, 48.
- **Shape:** 6px radius on panels, 6px on controls. Hairline borders define panels; no soft drop
  shadows.
- **Colour roles:** paper (ground), card (panel), panel-2 (control rail, slightly darker
  neutral), ink, soft, line; plum = RobTop's arm and primary controls; rust = the hand's signal
  only; status palette below.
- **Clinical status palette** (each pairs a colour with a word and a glyph shape):
  - *Normal* (green `--ok`, tick glyph): word "Following".
  - *Attention* (amber, triangle glyph): "Filter off", "At a limit", "Easing in".
  - *Stopped* (ink-filled strip, white text, two-bar pause glyph): "Holding", "Calibrating",
    "Not connected", "Not updating". Red is avoided because rust is the hand's colour.

### Components and their states

| Component | States |
|---|---|
| Status strip | following, filter off, easing, at limit, holding, calibrating, not connected, not updating (render failed), unknown (old controller: no `why_still`) |
| Device bar connection | live (last update time), stale, never connected |
| Measurement channel (hand, arm) | live value, no tremor found (< 0.3 mm), holding (arm row says "held"), no data |
| Reduction readout | value, "not measured while holding", "too little shake to measure" (< 0.15 mm) |
| Toggle (filter, Hold, grip hold) | on, off, hover, focus, pressed, disabled with reason |
| Slider (sensitivity, response) | idle, dragging (local value), sent, server value, disabled, missing key (control hidden with note) |
| Action button (neutral, let go, calibrate, test, cancel, add user) | default, hover, focus, active, disabled with reason, busy |
| Grip meters | live, missing `grip` (falls back to the claw from `follower[5]`), disconnected |
| User picker | list, adding (input with validation), calibrated / not calibrated, missing `user` |
| Calibration procedure | idle (hidden), rest (countdown), move (countdown + per-joint coverage), done (gains and ranges), cancelled |
| Activities | none, list with last / best / runs, test running (countdown, progress), test done |
| Charts | empty (teaching text), live, stale (dimmed) |
| 3D view | 3D, 2D fallback with note |

### Anti-goals (what made version 1 read as generic; taken from its screenshot)

1. **A landing-page header.** Big title, a slogan ("Your hand shakes, the arm does not."), and a
   paragraph under it. A console has a device bar, not a hero.
2. **State hidden in a button label.** "Hold: off" in a small pill top right, and "Live from the
   arm" in 13px grey. When Hold was on, nothing large said so. That is the failure from the test.
3. **Ten identical soft cards.** Every section the same rounded cream card with the same blurred
   drop shadow in an alternating 7/5 grid: no hierarchy, every section equally loud.
4. **Marketing stat numerals.** "91 %" at 76px bold, with "2.0 mm" and "0.2 mm" at 62px: the
   share removed is louder than the measurements it comes from, with no method or window.
5. **Grey explanatory prose everywhere.** A soft-grey sentence under every heading; the eye
   cannot find labels, values or actions.
6. **Charts as decoration.** A 30 s sine wave filling the biggest panel, axis labels floating,
   no units on the time axis.
7. **Toy naming in data labels.** "RobTop's arm" as a data series name; in the console the series
   is "Arm (follower)" and RobTop appears where the robot speaks.

### Constraints and open decisions

- Files: `steady_dashboard.html` (markup), `dashboard/app.css`, `dashboard/app.js`. Do not edit
  `dashboard/arm3d.js` or `dashboard/vendor/`.
- *(assumed)* `calibration.phase` stays `"done"` until the next command; the page shows the result
  until it changes or the person closes it.
- *(assumed)* `gain` is the global sensitivity; `user.gains` are per joint from calibration and
  shown read-only.
- *(assumed)* `limits` names are free text like `"elbow"`; the page shows them as given.
- *(assumed)* `activities` without a command (range, steady time, grip hold) are read-only.

### Research (Mobbin)

Mobbin was not available to this build: the MCP server stayed unauthenticated for the whole run
(only its `authenticate` tools were listed at each of four checks: start, before layout, before
the critique, before the polish pass). No Mobbin screens were used. The
patterns above come from general knowledge of patient-monitor and infusion-pump operator screens
(status bar with a mode word, parameter readouts as label / value / unit, waveform channels on a
shared scale) and of device setup wizards (numbered steps, one instruction at a time, a progress
indicator per measured quantity), not from specific Mobbin screens.
