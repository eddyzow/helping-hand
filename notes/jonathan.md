# Jonathan

## Working on now

- Follower-only Stereo Madness testing on `jonathan/geometry-dash-replay`. The [test instructions](../keypad/geometry_dash/README.md#test-the-follower-on-windows) cover pose teaching, three physical taps, and the first five taps in the game.

## Done and how it was tested

- The desktop recording has 74 presses and releases. The simulated O3C reproduced all 148 events within 1.4 ms after timing compensation.
- The browser recording has 73 presses and releases. The simulated O3C reproduced all 146 events within 0.9 ms. One replay reached Level Complete in RobTop's browser demo with a 12 ms offset from the soundtrack cue. The browser tooling cancels failed attempts and resets to the start on retry.
- The standalone Windows CLI was tested with a fake motor bus. The physical follower and desktop game replay still need an in-person test. The standalone CLI needs exclusive access to the follower's Windows COM port. The shared dispatcher has its own replay path on main.

## Needs from others

- Daniel: use the follower hardware slot to teach the released and pressed wrist positions, verify stop, and share the measured press and release delays from the tap test.

## Answers to questions other notes asked you

- Daniel: the recording and the follower-only test are available together on the feature branch. No hardware slot was used for the mock checks.
