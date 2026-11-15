import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import {
  ACCENT,
  BODY,
  Caption,
  Card,
  CardLabel,
  Chapter,
  Clip,
  DISPLAY,
  INK,
  PANEL,
  PAPER,
  Shot,
  Shots,
  Vignette,
  Wipe,
  Words,
  clamp,
  pop,
  useInOut,
} from "./ui";

/* Section start frames at 30 fps. They match the music's section changes. */
export const T = { open: 0, draw: 540, ttt: 1080, gd: 1650, feed: 2700, close: 3060, end: 3600 };

/* ============ 0:00 cold open and title ============ */

const OPEN_CUTS = 122; // four shots of two beats each at 118 BPM

function TitleCard({ dur }: { dur: number }) {
  const { f, exit } = useInOut(dur, 1, 14);
  const underline = interpolate(f, [16, 34], [0, 1], { ...clamp, easing: Easing.out(Easing.exp) });
  return (
    <AbsoluteFill style={{ opacity: exit, transform: `translateX(${(1 - exit) * -60}px)` }}>
      <AbsoluteFill
        style={{ background: "linear-gradient(100deg, rgba(11,11,16,0.86) 0%, rgba(11,11,16,0.5) 48%, rgba(11,11,16,0) 78%)" }}
      />
      <div style={{ position: "absolute", left: 110, top: 190, color: PAPER }}>
        <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 250, letterSpacing: -10, lineHeight: 1, display: "flex" }}>
          {"RobTop".split("").map((ch, i) => {
            const p = pop(f, 2 + i * 3, 11);
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  opacity: interpolate(p, [0, 0.4], [0, 1], clamp),
                  transform: `translateY(${(1 - p) * 120}px) rotate(${(1 - p) * 8}deg)`,
                }}
              >
                {ch}
              </span>
            );
          })}
        </div>
        <div
          style={{
            width: 700,
            height: 16,
            marginTop: 14,
            borderRadius: 8,
            backgroundColor: ACCENT,
            transform: `scaleX(${underline})`,
            transformOrigin: "0% 50%",
          }}
        />
        <div style={{ marginTop: 34, fontFamily: DISPLAY, fontWeight: 700, fontSize: 40, letterSpacing: 12, color: ACCENT }}>
          <Words text="ROBOT TABLETOP" delay={30} stagger={4} />
        </div>
        <div style={{ marginTop: 14, fontFamily: BODY, fontWeight: 600, fontSize: 58 }}>
          <Words text="A robot arm that sits on your desk." delay={44} />
        </div>
        <div style={{ marginTop: 44, fontFamily: BODY, fontWeight: 600, fontSize: 50 }}>
          <Words text="Built to take on *whatever job* is put in front of it." delay={150} />
        </div>
        <div style={{ marginTop: 22, fontFamily: BODY, fontWeight: 500, fontSize: 44, opacity: 0.95 }}>
          <Words text="Here is some of what it has done *so far.*" delay={278} />
        </div>
      </div>
    </AbsoluteFill>
  );
}

function Open() {
  const titleDur = T.draw - OPEN_CUTS;
  const shots: Shot[] = [
    { src: "o1.mp4", dur: 31, zoom: [1.08, 1.14] },
    { src: "o2.mp4", dur: 30, zoom: [1.1, 1.18], origin: "85% 40%" },
    { src: "o3.mp4", dur: 31, zoom: [1.06, 1.12] },
    { src: "o4.mp4", dur: 30, zoom: [1.04, 1.1] },
    { src: "title.mp4", dur: titleDur, zoom: [1.02, 1.14], dim: 0.12 },
  ];
  return (
    <AbsoluteFill>
      <Shots shots={shots} />
      <Sequence from={OPEN_CUTS} durationInFrames={titleDur}>
        <TitleCard dur={titleDur} />
      </Sequence>
    </AbsoluteFill>
  );
}

/* ============ 0:18 drawing ============ */

function PlanHouse() {
  const f = useCurrentFrame();
  // Strokes are the plan in drawings/simple_a_house.json (x100). Each one appears
  // roughly when the arm draws it in the 4x footage.
  const strokes: Array<[string, number, number]> = [
    ["M19 48 H81 V92 H19 Z", 0, 60],
    ["M8 51 L50 8 L92 51", 75, 120],
    ["M42 92 V65 H58 V92", 135, 180],
    ["M67 58 H75 V71 H67 Z", 190, 215],
    ["M25 58 H33 V71 H25 Z", 220, 245],
  ];
  const gap = pop(f, 258);
  return (
    <div style={{ width: 300 }}>
      <CardLabel>THE PLAN</CardLabel>
      <svg viewBox="0 0 100 100" width={300} height={262} style={{ marginTop: 6 }}>
        {strokes.map(([d, a, b]) => (
          <path
            key={d}
            d={d}
            fill="none"
            stroke={PAPER}
            strokeWidth={2.6}
            strokeLinecap="round"
            strokeLinejoin="round"
            pathLength={1}
            strokeDasharray={1}
            strokeDashoffset={1 - interpolate(f, [a, b], [0, 1], clamp)}
          />
        ))}
      </svg>
      <div
        style={{
          marginTop: 4,
          fontFamily: BODY,
          fontWeight: 600,
          fontSize: 26,
          opacity: gap,
          transform: `translateY(${(1 - gap) * 16}px)`,
        }}
      >
        Ink to plan: <span style={{ color: ACCENT, fontWeight: 700 }}>about 1 mm</span>
      </div>
    </div>
  );
}

function Draw() {
  const dur = T.ttt - T.draw;
  const shots: Shot[] = [
    { src: "d1.mp4", dur: 270, badge: "4×" },
    { src: "d2.mp4", dur: 105, zoom: [1.0, 1.04] },
    { src: "d3.mp4", dur: 105, badge: "12×" },
    { src: "d4.mp4", dur: 60, zoom: [1.0, 1.05] },
  ];
  return (
    <AbsoluteFill>
      <Shots shots={shots} />
      <Vignette />
      <Chapter text="Give it a pen." dur={dur} />
      <Card from={16} dur={356} style={{ right: 56, top: 136 }}>
        <PlanHouse />
      </Card>
      <Caption from={62} dur={206} text="It draws. A webcam photographs the page and compares the ink with *the plan.*" />
      <Caption from={274} dur={98} text="On this house the ink landed about *1 mm* from the plan, on average." />
      <Caption from={380} dur={154} text="Then it drew *a flower.*" />
    </AbsoluteFill>
  );
}

/* ============ 0:36 tic-tac-toe ============ */

const TURNS: Array<[number, number, "you" | "robtop"]> = [
  [62, 83, "robtop"],
  [83, 191, "you"],
  [191, 273, "robtop"],
  [273, 333, "you"],
  [333, 378, "robtop"],
  [378, 408, "you"],
  [408, 476, "robtop"],
];

function TurnChip() {
  const f = useCurrentFrame();
  const turn = TURNS.find(([a, b]) => f >= a && f < b);
  if (!turn) return null;
  const [start, , who] = turn;
  const p = pop(f, start, 12);
  const you = who === "you";
  return (
    <div
      style={{
        position: "absolute",
        right: 56,
        top: 136,
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "12px 26px 12px 18px",
        borderRadius: 18,
        backgroundColor: you ? PAPER : INK,
        color: you ? INK : PAPER,
        border: `4px solid ${you ? PAPER : ACCENT}`,
        fontFamily: DISPLAY,
        fontWeight: 700,
        fontSize: 34,
        transform: `scale(${0.7 + 0.3 * p}) rotate(${(1 - p) * (you ? -6 : 6)}deg)`,
        transformOrigin: "100% 0%",
        boxShadow: "0 12px 32px rgba(0,0,0,0.4)",
      }}
    >
      <span style={{ fontSize: 46, lineHeight: 1, color: you ? INK : ACCENT }}>{you ? "✕" : "◯"}</span>
      {you ? "Your move" : "RobTop's move"}
    </div>
  );
}

function SearchTree() {
  const f = useCurrentFrame();
  const root = { x: 170, y: 22 };
  const mids = [0, 1, 2].map((i) => ({ x: 55 + i * 115, y: 96 }));
  const leaves = Array.from({ length: 9 }, (_, i) => ({ x: 18 + i * 38, y: 172, parent: Math.floor(i / 3) }));
  const best = pop(f, 78);
  const edge = (a: { x: number; y: number }, b: { x: number; y: number }, start: number, lit: boolean, key: string) => (
    <line
      key={key}
      x1={a.x}
      y1={a.y}
      x2={b.x}
      y2={b.y}
      stroke={lit ? ACCENT : "rgba(255,255,255,0.55)"}
      strokeWidth={lit ? 4 + 2 * best : 3}
      pathLength={1}
      strokeDasharray={1}
      strokeDashoffset={1 - interpolate(f, [start, start + 10], [0, 1], clamp)}
    />
  );
  const node = (p: { x: number; y: number }, start: number, lit: boolean, key: string, r = 11) => (
    <circle key={key} cx={p.x} cy={p.y} r={r * pop(f, start)} fill={lit ? ACCENT : PAPER} />
  );
  return (
    <div style={{ width: 340 }}>
      <CardLabel>EVERY POSSIBLE GAME</CardLabel>
      <svg viewBox="0 0 340 196" width={340} height={196} style={{ marginTop: 12 }}>
        {mids.map((m, i) => edge(root, m, 6 + i * 4, i === 1 && best > 0.1, `rm${i}`))}
        {leaves.map((l, i) => edge(mids[l.parent], l, 26 + i * 4, i === 4 && best > 0.1, `ml${i}`))}
        {node(root, 2, true, "root", 13)}
        {mids.map((m, i) => node(m, 14 + i * 4, i === 1 && best > 0.1, `m${i}`))}
        {leaves.map((l, i) => node(l, 34 + i * 4, i === 4 && best > 0.1, `l${i}`, 8))}
      </svg>
    </div>
  );
}

function TicTacToe() {
  const dur = T.gd - T.ttt;
  const shots: Shot[] = [
    { src: "t1.mp4", dur: 83, badge: "8×" },
    { src: "t2.mp4", dur: 108, badge: "1.5×" },
    { src: "t3.mp4", dur: 82, badge: "4×" },
    { src: "t4.mp4", dur: 60, badge: "2.5×" },
    { src: "t5.mp4", dur: 45, badge: "4×" },
    { src: "t6.mp4", dur: 30, badge: "2.5×" },
    { src: "t7.mp4", dur: 68, badge: "6×" },
    { src: "t8.mp4", dur: 94, zoom: [1.0, 1.05] },
  ];
  return (
    <AbsoluteFill>
      <Shots shots={shots} />
      <Vignette />
      <Chapter text="Draw an X." dur={dur} />
      <TurnChip />
      <Card from={338} dur={136} style={{ right: 56, top: 236 }}>
        <SearchTree />
      </Card>
      <Caption from={62} dur={126} text="RobTop draws the grid. You draw an *X* with your own pen." />
      <Caption from={194} dur={138} text="The webcam spots your X, and RobTop draws *its O.*" />
      <Caption from={338} dur={134} text="Before each move it searches *every possible game.*" />
      <Caption from={480} dur={86} text="The best you can do against it is *a draw.*" />
    </AbsoluteFill>
  );
}

/* ============ 0:55 Geometry Dash ============ */

const GD = { g1: 0, g2: 132, g3: 311, g4: 611, clear: 950, freeze: 956, end: 1050 };
// Where the keypad sits in the cropped g3/g4 footage, for the zoomed lens.
const KEY = { x: 1555, y: 460 };

function Lens({ src, enterAt }: { src: string; enterAt: number }) {
  const f = useCurrentFrame();
  const R = 200;
  const zoom = 1.5;
  const p = pop(f, enterAt, 12);
  return (
    <div style={{ position: "absolute", left: 1440, top: 590, width: R * 2, transform: `scale(${p})`, transformOrigin: "50% 50%" }}>
      <div
        style={{
          width: R * 2,
          height: R * 2,
          borderRadius: R,
          overflow: "hidden",
          position: "relative",
          border: `8px solid ${ACCENT}`,
          boxSizing: "border-box",
          boxShadow: "0 20px 50px rgba(0,0,0,0.55)",
          backgroundColor: INK,
        }}
      >
        <OffthreadVideo
          muted
          src={staticFile(src)}
          style={{
            position: "absolute",
            width: 1920 * zoom,
            height: 1080 * zoom,
            maxWidth: "none",
            left: R - KEY.x * zoom,
            top: R - KEY.y * zoom,
          }}
        />
      </div>
      <div
        style={{
          margin: "-26px auto 0",
          width: "fit-content",
          position: "relative",
          padding: "8px 22px",
          borderRadius: 999,
          backgroundColor: ACCENT,
          color: INK,
          fontFamily: DISPLAY,
          fontWeight: 700,
          fontSize: 30,
        }}
      >
        A real key
      </div>
    </div>
  );
}

function LevelBar() {
  const f = useCurrentFrame();
  const pct = interpolate(f, [GD.g1, GD.g2, GD.g3, GD.g4, GD.clear], [0.1, 5.2, 40, 86.8, 100], clamp);
  const show = Math.min(interpolate(f, [58, 70], [0, 1], clamp), interpolate(f, [GD.clear + 4, GD.clear + 16], [1, 0], clamp));
  const x = (pct / 100) * 1920;
  return (
    <AbsoluteFill style={{ opacity: show }}>
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 16, backgroundColor: "rgba(11,11,16,0.75)" }} />
      <div
        style={{
          position: "absolute",
          left: 0,
          bottom: 0,
          height: 16,
          width: x,
          background: `linear-gradient(90deg, ${ACCENT}, #FF5C8A)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 24,
          left: Math.min(Math.max(x - 62, 12), 1920 - 140),
          padding: "4px 14px",
          borderRadius: 10,
          backgroundColor: INK,
          color: PAPER,
          fontFamily: DISPLAY,
          fontWeight: 700,
          fontSize: 30,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {Math.floor(pct)}%
      </div>
    </AbsoluteFill>
  );
}

function PressTiming() {
  const f = useCurrentFrame();
  const loop = (f % 45) / 45;
  const dot = interpolate(loop, [0.1, 0.75], [0, 1], clamp);
  const hit = interpolate(loop, [0.75, 0.82, 1], [0, 1, 0], clamp);
  return (
    <div style={{ width: 520 }}>
      <CardLabel>PRESS SENT EARLY</CardLabel>
      <svg viewBox="0 0 520 96" width={520} height={96} style={{ marginTop: 8 }}>
        <line x1={20} y1={56} x2={500} y2={56} stroke="rgba(255,255,255,0.35)" strokeWidth={4} />
        <line x1={150} y1={30} x2={150} y2={82} stroke={ACCENT} strokeWidth={6} strokeLinecap="round" />
        <line x1={400} y1={30} x2={400} y2={82} stroke={PAPER} strokeWidth={6} strokeLinecap="round" />
        <circle cx={150 + 250 * dot} cy={56} r={11} fill={ACCENT} />
        <circle cx={400} cy={56} r={12 + 22 * hit} fill="none" stroke={PAPER} strokeWidth={4} opacity={hit} />
        <text x={150} y={20} textAnchor="middle" fill={ACCENT} fontFamily={BODY} fontWeight={700} fontSize={22}>
          send
        </text>
        <text x={400} y={20} textAnchor="middle" fill={PAPER} fontFamily={BODY} fontWeight={700} fontSize={22}>
          key goes down
        </text>
        <text x={275} y={92} textAnchor="middle" fill={PAPER} fontFamily={BODY} fontWeight={600} fontSize={22}>
          about 0.1 s
        </text>
      </svg>
    </div>
  );
}

function ClearBurst() {
  const f = useCurrentFrame();
  const p = pop(f, 0, 9);
  const rays = interpolate(f, [0, 34], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const flash = interpolate(f, [0, 12], [0.7, 0], clamp);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ backgroundColor: "rgba(11,11,16,0.38)" }} />
      <AbsoluteFill style={{ backgroundColor: PAPER, opacity: flash }} />
      <svg viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
        {Array.from({ length: 18 }, (_, i) => {
          const a = (i / 18) * Math.PI * 2 + f * 0.004;
          const r0 = 250 + 330 * rays;
          const r1 = r0 + 150 * (1 - rays) + 30;
          return (
            <line
              key={i}
              x1={960 + Math.cos(a) * r0}
              y1={430 + Math.sin(a) * r0}
              x2={960 + Math.cos(a) * r1}
              y2={430 + Math.sin(a) * r1}
              stroke={i % 2 ? ACCENT : PAPER}
              strokeWidth={12}
              strokeLinecap="round"
              opacity={1 - rays * 0.75}
            />
          );
        })}
      </svg>
      <div style={{ position: "absolute", left: 0, right: 0, top: 250, textAlign: "center", transform: `scale(${0.5 + 0.5 * p})` }}>
        <div
          style={{
            fontFamily: DISPLAY,
            fontWeight: 700,
            fontSize: 330,
            lineHeight: 1,
            letterSpacing: -12,
            color: ACCENT,
            textShadow: `0 10px 0 ${INK}, 0 24px 60px rgba(0,0,0,0.6)`,
          }}
        >
          100%
        </div>
        <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 64, letterSpacing: 14, color: PAPER, marginTop: 6 }}>
          <Words text="LEVEL CLEARED" delay={8} stagger={5} />
        </div>
      </div>
    </AbsoluteFill>
  );
}

function GeometryDash() {
  const dur = T.feed - T.gd;
  const shots: Shot[] = [
    { src: "g1.mp4", dur: GD.g2 - GD.g1, badge: "REAL TIME", zoom: [1.0, 1.05], origin: "35% 55%" },
    { src: "g2.mp4", dur: GD.g3 - GD.g2, badge: "5×", zoom: [1.02, 1.02] },
    { src: "g3.mp4", dur: GD.g4 - GD.g3, badge: "4×", zoom: [1.0, 1.0] },
    { src: "g4.mp4", dur: GD.freeze - GD.g4, badge: "REAL TIME", zoom: [1.0, 1.0] },
    { src: "g_end.jpg", dur: GD.end - GD.freeze, still: true, zoom: [1.0, 1.05], origin: "40% 50%" },
  ];
  return (
    <AbsoluteFill>
      <Shots shots={shots} />
      <Vignette />
      <Sequence from={GD.g3} durationInFrames={GD.g4 - GD.g3} layout="none">
        <Lens src="g3.mp4" enterAt={4} />
      </Sequence>
      <Sequence from={GD.g4} durationInFrames={GD.clear - GD.g4} layout="none">
        <Lens src="g4.mp4" enterAt={-100} />
      </Sequence>
      <Chapter text="Give it a key." dur={dur} />
      <LevelBar />
      <Card from={470} dur={136} style={{ left: 80, bottom: 290 }}>
        <PressTiming />
      </Card>
      <Caption from={48} dur={94} text="This is Geometry Dash. It has *one button:* press it to jump." />
      <Caption from={148} dur={158} text="One press that comes *a moment late* sends you back to the start." />
      <Caption from={316} dur={140} text="RobTop presses a *real key.* It never looks at the screen." />
      <Caption from={462} dur={144} text="Every press is planned in advance and sent about *0.1 s early* to cancel the arm's own delay." />
      <Caption from={616} dur={150} text="The last stretch of the level, *at real speed.*" />
      <Sequence from={GD.clear} durationInFrames={GD.end - GD.clear}>
        <ClearBurst />
      </Sequence>
      <Caption from={GD.clear + 10} dur={GD.end - GD.clear - 12} text="The whole level: *1 minute 24 seconds* of presses, from memory." />
    </AbsoluteFill>
  );
}

/* ============ 1:30 feeding ============ */

function FollowChip({ dur }: { dur: number }) {
  const { f, exit } = useInOut(dur, 8, 8);
  const p = pop(f, 0, 12);
  return (
    <div
      style={{
        position: "absolute",
        right: 56,
        top: 136,
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "14px 26px",
        borderRadius: 18,
        backgroundColor: PANEL,
        border: `3px solid ${ACCENT}`,
        color: PAPER,
        fontFamily: DISPLAY,
        fontWeight: 700,
        fontSize: 34,
        opacity: exit,
        transform: `scale(${0.7 + 0.3 * p})`,
        transformOrigin: "100% 0%",
      }}
    >
      Your hand
      <div style={{ display: "flex", gap: 7 }}>
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            style={{
              width: 13,
              height: 13,
              borderRadius: 7,
              backgroundColor: ACCENT,
              opacity: 0.25 + 0.75 * Math.max(0, Math.sin(f / 3.2 - i * 0.9)),
            }}
          />
        ))}
      </div>
      RobTop
    </div>
  );
}

function Feeding() {
  const dur = T.close - T.feed;
  return (
    <AbsoluteFill>
      <Shots shots={[{ src: "f1.mp4", dur, badge: "1.4×", zoom: [1.0, 1.05] }]} />
      <Vignette />
      <Chapter text="Hold its second arm." dur={dur} />
      <Sequence from={62} durationInFrames={dur - 70} layout="none">
        <FollowChip dur={dur - 70} />
      </Sequence>
      <Caption from={62} dur={140} text="Move the small second arm with your hand, and RobTop *copies you.*" />
      <Caption from={208} dur={144} text="Here it is feeding someone *a snack.*" />
    </AbsoluteFill>
  );
}

/* ============ 1:42 close ============ */

const TILES = [
  ["gr1.mp4", "House"],
  ["gr2.mp4", "Flower"],
  ["gr3.mp4", "Tic-tac-toe"],
  ["gr4.mp4", "Geometry Dash"],
  ["gr5.mp4", "Level cleared"],
  ["gr6.mp4", "Snack"],
] as const;
const GRID_DUR = 240;

function Grid() {
  const f = useCurrentFrame();
  const w = 576;
  const h = 324;
  const gap = 18;
  return (
    <AbsoluteFill style={{ backgroundColor: INK }}>
      {TILES.map(([src, label], i) => {
        const col = i % 3;
        const row = Math.floor(i / 3);
        const p = pop(f, 2 + i * 4, 12);
        const out = interpolate(f, [GRID_DUR - 22 + i * 2, GRID_DUR - 8 + i * 2], [1, 0], clamp);
        const float = Math.sin(f / 22 + i) * 4;
        return (
          <div
            key={src}
            style={{
              position: "absolute",
              left: 78 + col * (w + gap),
              top: 64 + row * (h + gap),
              width: w,
              height: h,
              borderRadius: 20,
              overflow: "hidden",
              border: `4px solid ${i === 4 ? ACCENT : "rgba(255,255,255,0.18)"}`,
              boxSizing: "border-box",
              opacity: Math.min(interpolate(p, [0, 0.4], [0, 1], clamp), out),
              transform: `translateY(${(1 - p) * 90 + float}px) scale(${(0.8 + 0.2 * p) * (0.9 + 0.1 * out)})`,
            }}
          >
            <OffthreadVideo muted src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            <div
              style={{
                position: "absolute",
                left: 14,
                bottom: 14,
                padding: "6px 16px",
                borderRadius: 999,
                backgroundColor: PANEL,
                color: PAPER,
                fontFamily: DISPLAY,
                fontWeight: 700,
                fontSize: 26,
              }}
            >
              {label}
            </div>
          </div>
        );
      })}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 776,
          textAlign: "center",
          color: PAPER,
          fontFamily: DISPLAY,
          fontWeight: 700,
          opacity: interpolate(f, [GRID_DUR - 16, GRID_DUR - 4], [1, 0], clamp),
        }}
      >
        <div style={{ fontSize: 76, letterSpacing: -2 }}>
          <Words text="Everything you just saw was *the same arm.*" delay={26} />
        </div>
        <div style={{ fontSize: 60, marginTop: 14, fontWeight: 500 }}>
          <Words text="It is less than *two days old.*" delay={112} />
        </div>
      </div>
    </AbsoluteFill>
  );
}

function EndCard({ dur }: { dur: number }) {
  const f = useCurrentFrame();
  const lockup = pop(f, 128);
  const line = interpolate(f, [120, 146], [0, 1], { ...clamp, easing: Easing.out(Easing.exp) });
  const black = interpolate(f, [dur - 20, dur - 2], [0, 1], clamp);
  return (
    <AbsoluteFill>
      <Clip src="rest.mp4" dur={dur} zoom={[1.0, 1.12]} origin="55% 40%" dim={0.46} />
      <div style={{ position: "absolute", left: 0, right: 0, top: 300, textAlign: "center", color: PAPER }}>
        <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 168, letterSpacing: -7, lineHeight: 1.02 }}>
          <Words text="What would you" delay={14} stagger={4} />
          <br />
          <Words text="*teach it?*" delay={32} stagger={5} />
        </div>
        <div
          style={{
            width: 420,
            height: 10,
            borderRadius: 5,
            backgroundColor: ACCENT,
            margin: "56px auto 34px",
            transform: `scaleX(${line})`,
          }}
        />
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "baseline",
            gap: 28,
            opacity: lockup,
            transform: `translateY(${(1 - lockup) * 30}px)`,
          }}
        >
          <span style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 84, letterSpacing: -3 }}>RobTop</span>
          <span style={{ fontFamily: BODY, fontWeight: 600, fontSize: 40, opacity: 0.92 }}>
            HackUMass XIV
          </span>
        </div>
      </div>
      <AbsoluteFill style={{ backgroundColor: "#000", opacity: black }} />
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
        <Wipe key={at} at={at} />
      ))}
      <Audio
        src={staticFile("music.mp3")}
        volume={(f) => 0.7 * interpolate(f, [T.end - 36, T.end - 2], [1, 0], clamp)}
      />
    </AbsoluteFill>
  );
}
