import React from "react";
import { AbsoluteFill, Audio, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";
import { ACCENT, BigTitle, Clip, Dip, INK, Label, MONO, PAPER, Rise, SERIF, SHADOW, Shade, Shot, Shots, Subtitles, clamp, ramp } from "./ui";

/* Section start frames at 30 fps. They match the music's section changes. */
export const T = { open: 0, draw: 540, ttt: 1260, gd: 1830, feed: 2508, close: 2868, end: 3288 };

/*
 * Voiceover captions: [start s, end s, text]. The voice is not recorded yet, so each
 * line is given words / 2.5 seconds (150 words a minute, 1.3 s at least), with a short
 * pause between sentences. Retime them to the recording when it exists.
 */
const CUES: Array<[number, number, string]> = [
  [0.5, 1.8, "This is RobTop."],
  [2.1, 5.7, "It's a robot arm that sits on your desk,"],
  [5.7, 11.7, "and we built it to take on whatever job is put in front of it."],
  [12.1, 16.1, "Here is some of what it has done so far."],

  [19.9, 24.3, "Tell it what to draw and an AI sketches the plan."],
  [24.6, 27.0, "Here we asked for a house."],
  [27.3, 32.5, "On this house the lines sit about a millimetre from the planned shape."],
  [32.8, 38.8, "A camera checks each drawing against the plan, and the arm corrects its next attempt."],
  [39.1, 41.5, "Then we asked for a flower."],

  [43.9, 46.7, "Draw an X and it plays you."],
  [47.0, 49.8, "It sees your move on the paper,"],
  [49.8, 51.8, "thinks through every possible game,"],
  [51.8, 53.4, "and draws its reply."],
  [56.0, 60.8, "Play it right and the best you can do is a draw."],

  [62.9, 67.3, "Give it a key to press and it plays a video game."],
  [67.6, 70.0, "This one is called Geometry Dash."],
  [70.3, 75.1, "It has one button, and a single press that comes a moment late"],
  [75.1, 77.5, "sends you back to the start."],
  [77.9, 80.3, "RobTop has cleared the whole level:"],
  [80.3, 83.1, "about ninety seconds of presses, from memory."],

  [85.5, 89.9, "Take the second arm in your hand and RobTop follows you."],
  [90.3, 92.7, "Here it's feeding Daniel a snack."],

  [96.4, 99.6, "Everything you just saw was the same arm."],
];

/* ============ 0:00 cold open ============ */

const BEATS = 36; // two beats at 100 BPM
const LONG = (T.draw - BEATS * 4) / 6; // six longer shots fill the rest of the opening

function Wordmark({ dur }: { dur: number }) {
  const f = useCurrentFrame();
  const out = interpolate(f, [dur - 14, dur], [1, 0], clamp);
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <AbsoluteFill style={{ backgroundColor: "rgba(12,12,14,0.28)" }} />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", color: PAPER, textShadow: SHADOW }}>
        <div style={{ display: "flex", fontFamily: SERIF, fontSize: 380, lineHeight: 1, letterSpacing: -8 }}>
          {"RobTop".split("").map((ch, i) => (
            <Rise key={i} at={i * 2}>
              {ch}
            </Rise>
          ))}
        </div>
        <div style={{ marginTop: 6, fontFamily: MONO, fontWeight: 500, fontSize: 34, letterSpacing: 18, opacity: ramp(f, 22, 20) }}>
          ROBOT TABLETOP
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

function Open() {
  const shots: Shot[] = [
    { src: "o1.mp4", dur: BEATS, speed: "2×", zoom: [1.08, 1.13] },
    { src: "o2.mp4", dur: BEATS, zoom: [1.1, 1.16], origin: "85% 40%" },
    { src: "o3.mp4", dur: BEATS, speed: "3×", zoom: [1.06, 1.11] },
    { src: "o4.mp4", dur: BEATS, speed: "2×", zoom: [1.04, 1.09] },
    { src: "oa.mp4", dur: LONG, zoom: [1.0, 1.07] },
    { src: "ob.mp4", dur: LONG, speed: "6×" },
    { src: "oc.mp4", dur: LONG, speed: "6×" },
    { src: "od.mp4", dur: LONG, zoom: [1.0, 1.08] },
    { src: "oe.mp4", dur: LONG, speed: "0.6×" },
    { src: "of.mp4", dur: LONG, speed: "9×" },
  ];
  return (
    <AbsoluteFill>
      <Shots shots={shots} />
      <Shade />
      <Sequence from={6} durationInFrames={196}>
        <Wordmark dur={196} />
      </Sequence>
    </AbsoluteFill>
  );
}

/* ============ 0:18 drawing ============ */

const PLAN_AT = 66; // section frame where the plan panel appears

/** The request that produced the drawing, as a small tag under the speed label. */
function Prompt({ text, dur }: { text: string; dur: number }) {
  const f = useCurrentFrame();
  const opacity = Math.min(ramp(f, 0, 12), interpolate(f, [dur - 10, dur], [1, 0], clamp));
  return (
    <div style={{ position: "absolute", right: 64, top: 118, fontFamily: MONO, fontWeight: 500, fontSize: 22, letterSpacing: 5, color: PAPER, textShadow: SHADOW, opacity }}>
      PROMPT: "{text}"
    </div>
  );
}

/** The plan the arm follows, drawn in step with the footage (drawings/simple_a_house.json, x100). */
function Plan({ dur }: { dur: number }) {
  const f = useCurrentFrame();
  const strokes: Array<[string, number, number]> = [
    ["M19 48 H81 V92 H19 Z", 25, 125],
    ["M8 51 L50 8 L92 51", 150, 225],
    ["M42 92 V65 H58 V92", 250, 325],
    ["M67 58 H75 V71 H67 Z", 341, 379],
    ["M25 58 H33 V71 H25 Z", 388, 425],
  ];
  const opacity = Math.min(ramp(f, 0, 12), interpolate(f, [dur - 12, dur], [1, 0], clamp));
  return (
    <div style={{ position: "absolute", right: 64, top: 118, width: 250, opacity }}>
      <div style={{ padding: 20, borderRadius: 6, backgroundColor: "rgba(12,12,14,0.62)" }}>
        <svg viewBox="0 0 100 100" width={210} height={210}>
          {strokes.map(([d, a, b]) => (
            <path
              key={d}
              d={d}
              fill="none"
              stroke={PAPER}
              strokeWidth={2.2}
              strokeLinecap="round"
              strokeLinejoin="round"
              pathLength={1}
              strokeDasharray={1}
              strokeDashoffset={1 - interpolate(f + PLAN_AT, [a, b], [0, 1], clamp)}
            />
          ))}
        </svg>
      </div>
      <div style={{ position: "absolute", right: 0, marginTop: 10, whiteSpace: "nowrap", fontFamily: MONO, fontWeight: 500, fontSize: 22, letterSpacing: 5, color: PAPER, textShadow: SHADOW }}>
        PROMPT: "A HOUSE"
      </div>
    </div>
  );
}

function Draw() {
  const dur = T.ttt - T.draw;
  const shots: Shot[] = [
    { src: "d1.mp4", dur: 455, speed: "2.4×" },
    { src: "d2.mp4", dur: 111, zoom: [1.0, 1.04] },
    { src: "d3.mp4", dur: 90, speed: "14×" },
    { src: "d4.mp4", dur: 64, zoom: [1.0, 1.04] },
  ];
  return (
    <AbsoluteFill>
      <Shots shots={shots} />
      <Shade />
      <Label text="Drawing" dur={dur} at={60} />
      <BigTitle text="Drawing" />
      <Sequence from={PLAN_AT} durationInFrames={566 - PLAN_AT} layout="none">
        <Plan dur={566 - PLAN_AT} />
      </Sequence>
      <Sequence from={572} durationInFrames={144} layout="none">
        <Prompt text="A FLOWER" dur={144} />
      </Sequence>
    </AbsoluteFill>
  );
}

/* ============ 0:36 tic-tac-toe ============ */

function TicTacToe() {
  const shots: Shot[] = [
    { src: "t1.mp4", dur: 83, speed: "8×" },
    { src: "t2.mp4", dur: 108, speed: "1.5×" },
    { src: "t3.mp4", dur: 82, speed: "4×" },
    { src: "t4.mp4", dur: 60, speed: "2.5×" },
    { src: "t5.mp4", dur: 45, speed: "4×" },
    { src: "t6.mp4", dur: 30, speed: "2.5×" },
    { src: "t7.mp4", dur: 68, speed: "6×" },
    { src: "t8.mp4", dur: 94, zoom: [1.0, 1.04] },
  ];
  return (
    <AbsoluteFill>
      <Shots shots={shots} />
      <Shade />
      <Label text="Tic-tac-toe" dur={T.gd - T.ttt} at={60} />
      <BigTitle text="Tic-tac-toe" />
    </AbsoluteFill>
  );
}

/* ============ 0:55 Geometry Dash ============ */

const GD = { g1: 0, g2: 132, key: 252, g3: 324, g4a: 431, g4: 491, clear: 589, freeze: 596, end: 678 };
/** Position in the level, as a thin line along the bottom edge. */
function LevelLine() {
  const f = useCurrentFrame();
  const pct = interpolate(f, [GD.g1, GD.g2, GD.key, GD.g3, GD.g4a, GD.g4, GD.clear], [0.1, 5.2, 42.5, 45.3, 86.8, 96.2, 100], clamp);
  const opacity = Math.min(ramp(f, 20, 14), interpolate(f, [GD.clear + 2, GD.clear + 14], [1, 0], clamp));
  return (
    <AbsoluteFill style={{ opacity }}>
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 8, backgroundColor: "rgba(246,242,234,0.22)" }} />
      <div style={{ position: "absolute", left: 0, bottom: 0, height: 8, width: `${pct}%`, backgroundColor: ACCENT }} />
      <div
        style={{
          position: "absolute",
          right: 64,
          bottom: 30,
          fontFamily: MONO,
          fontWeight: 500,
          fontSize: 34,
          color: PAPER,
          textShadow: SHADOW,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {Math.floor(pct)}%
      </div>
    </AbsoluteFill>
  );
}

function Cleared() {
  const f = useCurrentFrame();
  const ring = ramp(f, 0, 40);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ backgroundColor: `rgba(12,12,14,${0.5 * ramp(f, 0, 10)})` }} />
      <AbsoluteFill style={{ backgroundColor: PAPER, opacity: interpolate(f, [0, 10], [0.55, 0], clamp) }} />
      <svg viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
        <circle cx={960} cy={470} r={240 + 520 * ring} fill="none" stroke={PAPER} strokeWidth={3} opacity={1 - ring} />
      </svg>
      <AbsoluteFill style={{ alignItems: "center", color: PAPER, textShadow: SHADOW }}>
        <Rise at={0} style={{ marginTop: 250, fontFamily: SERIF, fontSize: 420, lineHeight: 1, letterSpacing: -10 }}>
          100%
        </Rise>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

function GeometryDash() {
  const shots: Shot[] = [
    { src: "g1.mp4", dur: GD.g2 - GD.g1, speed: "REAL TIME", zoom: [1.0, 1.05], origin: "35% 55%" },
    { src: "g2.mp4", dur: GD.key - GD.g2, speed: "8×", zoom: [1.02, 1.02] },
    { src: "gk.mp4", dur: GD.g3 - GD.key, speed: "REAL TIME", zoom: [1.0, 1.08], origin: "45% 55%" },
    { src: "g3.mp4", dur: GD.g4a - GD.g3, speed: "10×", zoom: [1.0, 1.0] },
    { src: "g4a.mp4", dur: GD.g4 - GD.g4a, speed: "4×", zoom: [1.0, 1.0] },
    { src: "g4.mp4", dur: GD.freeze - GD.g4, speed: "REAL TIME", zoom: [1.0, 1.0] },
    { src: "g_end.jpg", dur: GD.end - GD.freeze, still: true, zoom: [1.0, 1.04], origin: "40% 50%" },
  ];
  return (
    <AbsoluteFill>
      <Shots shots={shots} />
      <Shade />
      <Label text="Geometry Dash" dur={T.feed - T.gd} at={60} />
      <BigTitle text="Geometry Dash" size={250} />
      <LevelLine />
      <Sequence from={GD.clear} durationInFrames={GD.end - GD.clear}>
        <Cleared />
      </Sequence>
    </AbsoluteFill>
  );
}

/* ============ 1:30 feeding ============ */

function Feeding() {
  const dur = T.close - T.feed;
  return (
    <AbsoluteFill>
      <Shots shots={[{ src: "f1.mp4", dur, speed: "1.4×", zoom: [1.0, 1.05] }]} />
      <Shade />
      <Label text="Feeding" dur={dur} at={60} />
      <BigTitle text="Feeding" />
    </AbsoluteFill>
  );
}

/* ============ 1:42 close ============ */

const TILES = ["gr1.mp4", "gr2.mp4", "gr3.mp4", "gr4.mp4", "gr5.mp4", "gr6.mp4"];
const GRID_DUR = 180;

function Grid() {
  const f = useCurrentFrame();
  const gap = 14;
  const w = (1920 - gap * 4) / 3;
  const h = (w * 9) / 16;
  const top = (1080 - (h * 2 + gap)) / 2 - 40;
  return (
    <AbsoluteFill style={{ backgroundColor: INK }}>
      {TILES.map((src, i) => {
        const p = ramp(f, i * 4, 22);
        const out = interpolate(f, [GRID_DUR - 14, GRID_DUR - 2], [1, 0], clamp);
        return (
          <div
            key={src}
            style={{
              position: "absolute",
              left: gap + (i % 3) * (w + gap),
              top: top + Math.floor(i / 3) * (h + gap),
              width: w,
              height: h,
              overflow: "hidden",
              borderRadius: 4,
              opacity: Math.min(p, out),
              transform: `translateY(${(1 - p) * 60}px)`,
            }}
          >
            <OffthreadVideo
              muted
              src={staticFile(src)}
              style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${1.12 - 0.12 * p})` }}
            />
          </div>
        );
      })}
    </AbsoluteFill>
  );
}

function EndCard({ dur }: { dur: number }) {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Clip src="rest.mp4" dur={dur} zoom={[1.0, 1.1]} origin="55% 40%" dim={0.5} />
      <AbsoluteFill style={{ alignItems: "center", color: PAPER, textShadow: SHADOW }}>
        <div style={{ marginTop: 300, fontFamily: SERIF, fontSize: 190, lineHeight: 1.02, letterSpacing: -4, textAlign: "center" }}>
          <Rise at={16}>What would you</Rise>
          <Rise at={24} style={{ fontStyle: "italic" }}>
            teach it?
          </Rise>
        </div>
        <div style={{ marginTop: 56, fontFamily: MONO, fontWeight: 500, fontSize: 30, letterSpacing: 10, opacity: ramp(f, 70, 20) }}>
          ROBTOP · HACKUMASS XIV
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ backgroundColor: "#000", opacity: interpolate(f, [dur - 22, dur - 2], [0, 1], clamp) }} />
    </AbsoluteFill>
  );
}

function Close() {
  const restDur = T.end - T.close - GRID_DUR;
  return (
    <AbsoluteFill style={{ backgroundColor: INK }}>
      <Sequence durationInFrames={GRID_DUR}>
        <Grid />
      </Sequence>
      <Sequence from={GRID_DUR} durationInFrames={restDur}>
        <EndCard dur={restDur} />
      </Sequence>
    </AbsoluteFill>
  );
}

/* ============ timeline ============ */

export function Demo() {
  const sections: Array<[number, number, React.ReactNode]> = [
    [T.open, T.draw, <Open />],
    [T.draw, T.ttt, <Draw />],
    [T.ttt, T.gd, <TicTacToe />],
    [T.gd, T.feed, <GeometryDash />],
    [T.feed, T.close, <Feeding />],
    [T.close, T.end, <Close />],
  ];
  return (
    <AbsoluteFill style={{ backgroundColor: INK }}>
      {sections.map(([from, to, node]) => (
        <Sequence key={from} from={from} durationInFrames={to - from}>
          {node}
        </Sequence>
      ))}
      {[T.draw, T.ttt, T.gd, T.feed, T.close].map((at) => (
        <Dip key={at} at={at} />
      ))}
      <Subtitles cues={CUES} />
      {/* Music sits at bed level so a voice can go on top. */}
      <Audio src={staticFile("music.mp3")} volume={(f) => 0.5 * interpolate(f, [T.end - 40, T.end - 2], [1, 0], clamp)} />
    </AbsoluteFill>
  );
}
