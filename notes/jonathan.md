# Jonathan

## Working on now

- Follower-only Stereo Madness testing on `jonathan/geometry-dash-replay`. The [test instructions](../keypad/geometry_dash/README.md#test-the-follower-on-windows) cover pose teaching, three physical taps, and the first five taps in the game.

## Done and how it was tested

- The included recording has 74 presses and releases. The simulated O3C reproduced all 148 key events within 1.4 ms after simulation timing compensation.
- The standalone Windows CLI was tested with a fake motor bus. The real arm, the SayoDevice and game completion still need an in-person test. The CLI supports the team's C jump key in its tap test and uses Z or F8 to stop.
- Dispatcher integration is still pending. The arm laptop needs to release the follower's COM port from WSL and close other arm controllers before using this standalone script.

## Needs from others

- Daniel: use the follower hardware slot to teach the released and pressed wrist positions, verify stop, and share the measured press and release delays from the tap test.

## Answers to questions other notes asked you

- Daniel: the recording and the follower-only test are available together on the feature branch. No hardware slot was used for the mock checks.
