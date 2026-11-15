---
name: Steady Hand console
description: The operator console for the Steady Hand tremor-filtering arm, drawn as a live clinical record sheet.
colors:
  paper: "#ece6db"
  card: "#fbf9f5"
  panel: "#f4efe6"
  ink: "#231d21"
  soft: "#5b5256"
  line: "#d8cebf"
  rule: "#a99d8c"
  plum: "#6b2d5c"
  plum-deep: "#4f1f43"
  plum-wash: "#f0e5ec"
  raw: "#b8552f"
  raw-wash: "#f6e7de"
  ok: "#2f6b4f"
  ok-wash: "#e2eee6"
  warn: "#7f5306"
  warn-wash: "#f6ead0"
  warn-line: "#d6b064"
  stop: "#2a2227"
typography:
  value-xl:
    fontFamily: "Segoe UI Variable Display, Segoe UI, system-ui, sans-serif"
    fontSize: "56px"
    fontWeight: 600
    lineHeight: 1
  value-l:
    fontFamily: "Segoe UI Variable Display, Segoe UI, system-ui, sans-serif"
    fontSize: "40px"
    fontWeight: 600
    lineHeight: 1
  status:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.25
  title:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 650
    lineHeight: 1.3
  body:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.3
rounded:
  field: "4px"
  sheet: "6px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  xxl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.plum}"
    textColor: "{colors.card}"
    rounded: "{rounded.field}"
    height: "44px"
  button-secondary:
    backgroundColor: "{colors.card}"
    textColor: "{colors.plum-deep}"
    rounded: "{rounded.field}"
    height: "44px"
  option-selected:
    backgroundColor: "{colors.plum}"
    textColor: "{colors.card}"
    rounded: "{rounded.field}"
    height: "48px"
---

# Design System: Steady Hand console

## Overview

**Creative North Star: "The live record sheet"**

The console is drawn the way a clinical case report form is drawn: a sheet of form stock with a
header row of identifying fields, ruled sections, labels printed small above or beside a value
box, units printed outside the box, and tick-box options where a choice is made. The difference
is that this form fills itself in ten times a second. That world brings the trust of a clinical
record (every value has a label, a unit and a method) without the startup-dashboard furniture of
floating rounded cards and hero statistics.

Above the sheet runs one device status strip, the only loud element: it says in words what the
arm is doing and, when it is not following, why and what to press.

**Key Characteristics:**
- Flat sheets on a darker form-stock ground; hairline rules, no drop shadows.
- Values in ruled boxes with the unit outside; tabular figures everywhere.
- Choices drawn as two visible options with a filled tick square on the selected one.
- One status strip with a word, a glyph shape and a sentence; colour is the third cue, never the only one.

## Colors

Restrained: warm neutral form stock, ink, one plum accent, rust for the hand's signal, and a
three-step clinical status palette.

### Primary
- **Plum** (`plum`): RobTop's arm in every chart and the 3D view; selected options and primary buttons. Never decoration.

### Secondary
- **Rust** (`raw`): the hand's signal only (its trace, its value, its marker on the comparison scale).

### Neutral
- **Form stock** (`paper`): the page ground.
- **Sheet** (`card`): every section.
- **Rail** (`panel`): the control rail, a second neutral layer.
- **Ink** (`ink`), **soft ink** (`soft`): text; soft is for labels and methods, at least 4.5:1 on sheet.
- **Hairline** (`line`), **rule** (`rule`): field borders and section rules.

### Status
- **Normal** (`ok`, `ok-wash`): following. Tick glyph, word "Following".
- **Attention** (`warn`, `warn-wash`, `warn-line`): filter off, at a limit, easing in. Triangle glyph.
- **Stopped** (`stop`, text in `card`): holding, calibrating, not connected, not updating. Pause or slashed-circle glyph. Red is not used because rust is the hand.

**The Hand Is Rust Rule.** Rust appears only where the hand's own signal is drawn or quoted.

**The Word First Rule.** No state is shown by colour alone: every status has a word and a glyph shape.

## Typography

**Body Font:** Segoe UI Variable / Segoe UI (system stack; no web fonts at run time).

One family. Values use the Display optical size and tabular figures; labels are sentence case at
13px weight 600 in soft ink. The only uppercase is the status word in the strip.

### Hierarchy
- **Value XL** (600, 56px, 1): the two measured shakes.
- **Value L** (600, 40px, 1): share removed, test countdown, calibration countdown.
- **Status** (600, 24px): the status sentence.
- **Title** (650, 17px): section titles.
- **Body** (400, 15px, 1.45): instructions and notes, 65ch at most.
- **Label** (600, 13px): field labels, units, axis labels.

## Layout

12px gutter grid inside a 1480px sheet. At 1240px and wider: measurement | 3D view | control
rail (340px), then the 30 s chart beneath the first two; procedure panel full width under the
status strip while calibration runs. 760 to 1239px: two columns, rail beneath. Under 760px: one
column, status strip and controls first. Spacing steps 4 / 8 / 12 / 16 / 24 / 32.

## Elevation & Depth

Flat. Depth is tonal: form stock ground, sheet panels with a 1px hairline, the rail one step
darker. The status strip is the only filled band.

## Shapes

Small, square-ish corners: 6px on sheets, 4px on fields and buttons. Section titles sit on a
1px ink rule. Value boxes are 1px hairline rectangles.

## Components

### Buttons
- **Shape:** 4px corners, 44px tall at least.
- **Primary:** plum fill, sheet-coloured text. **Secondary:** sheet fill, plum-deep text, plum hairline.
- **Hover:** primary deepens to plum-deep; secondary takes the plum wash. **Focus:** 3px plum outline offset 2px. **Disabled:** soft text on panel, hairline border, reason printed beside it.

### Option pair (toggles)
- Two options side by side inside one ruled field (for example "On" / "Off"); the selected one
  is plum-filled with a filled tick square, the other shows an empty square. `aria-pressed` on each.

### Value box
- Label above, value in a hairline box, unit printed to the right of the box, method line below in soft ink.

### Meter
- 10px hairline track with tick marks at 25 / 50 / 75; fill in plum (or rust for the hand's squeeze).

### Status strip
- Full width; colour wash per class, glyph, uppercase status word, sentence, one action button.

## Do's and Don'ts

### Do:
- **Do** print the unit and the method next to every measurement.
- **Do** show both options of a two-way choice, with the selected one ticked.
- **Do** disable command controls with the reason printed beside them when the data is stale.

### Don't:
- **Don't** use soft drop shadows or floating rounded cards.
- **Don't** make a derived figure (share removed) larger than the measurements it comes from.
- **Don't** use rust for anything but the hand, or red for the stopped state.
- **Don't** show a health status; show measurements labelled as measurements.
