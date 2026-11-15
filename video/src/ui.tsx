import React from "react";
import {
  AbsoluteFill,
  Easing,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { loadFont as loadDisplay } from "@remotion/google-fonts/SpaceGrotesk";
import { loadFont as loadBody } from "@remotion/google-fonts/Inter";

export const DISPLAY = loadDisplay("normal", { weights: ["500", "700"], subsets: ["latin"] }).fontFamily;
export const BODY = loadBody("normal", { weights: ["500", "600", "700"], subsets: ["latin"] }).fontFamily;

export const FPS = 30;
export const INK = "#0B0B10";
export const PAPER = "#FFFFFF";
export const ACCENT = "#FFC93C"; // the yellow tape on the marker
export const PANEL = "rgba(11,11,16,0.80)";
export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const pop = (frame: number, delay = 0, damping = 14) =>
  spring({ frame: frame - delay, fps: FPS, config: { damping, stiffness: 170, mass: 0.7 } });

/** Fades and slides a block in at `from` and out before `from + dur`. */
export const useInOut = (dur: number, inFrames = 10, outFrames = 8) => {
  const f = useCurrentFrame();
  const enter = interpolate(f, [0, inFrames], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const exit = interpolate(f, [dur - outFrames, dur], [1, 0], { ...clamp, easing: Easing.in(Easing.cubic) });
  return { f, enter, exit, opacity: Math.min(enter, exit) };
};

/* ---------- footage ---------- */

export type Shot = {
  src: string;
  dur: number;
  badge?: string; // "4×" or "REAL TIME"
  zoom?: [number, number];
  origin?: string;
  dim?: number;
  still?: boolean;
};

export const Clip: React.FC<Shot> = ({ src, dur, zoom = [1.0, 1.06], origin = "50% 50%", dim = 0, still }) => {
  const f = useCurrentFrame();
  const punch = interpolate(f, [0, 9], [0.06, 0], { ...clamp, easing: Easing.out(Easing.cubic) });
  const kenBurns = interpolate(f, [0, dur], zoom, clamp);
  const flash = interpolate(f, [0, 6], [0.4, 0], clamp);
  const style: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "cover",
    transform: `scale(${kenBurns + punch})`,
    transformOrigin: origin,
  };
  return (
    <AbsoluteFill style={{ backgroundColor: INK, overflow: "hidden" }}>
      {still ? <img src={staticFile(src)} style={style} /> : <OffthreadVideo muted src={staticFile(src)} style={style} />}
      {dim > 0 ? <AbsoluteFill style={{ backgroundColor: `rgba(11,11,16,${dim})` }} /> : null}
      <AbsoluteFill style={{ backgroundColor: PAPER, opacity: flash }} />
    </AbsoluteFill>
  );
};

export const SpeedBadge: React.FC<{ label: string; dur: number }> = ({ label, dur }) => {
  const { f, exit } = useInOut(dur, 8, 6);
  const scale = pop(f, 3);
  const live = label === "REAL TIME";
  const pulse = 0.55 + 0.45 * Math.sin(f / 4);
  return (
    <div
      style={{
        position: "absolute",
        right: 56,
        top: 48,
        display: "flex",
        alignItems: "center",
        gap: 14,
        padding: "12px 24px",
        borderRadius: 999,
        backgroundColor: live ? "#E5383B" : ACCENT,
        color: live ? PAPER : INK,
        fontFamily: DISPLAY,
        fontWeight: 700,
        fontSize: 38,
        letterSpacing: live ? 3 : 0,
        transform: `scale(${scale})`,
        transformOrigin: "100% 0%",
        opacity: exit,
        boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
      }}
    >
      {live ? (
        <div style={{ width: 18, height: 18, borderRadius: 9, backgroundColor: PAPER, opacity: pulse }} />
      ) : (
        <div style={{ display: "flex", gap: 2 }}>
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              style={{
                width: 0,
                height: 0,
                borderTop: "11px solid transparent",
                borderBottom: "11px solid transparent",
                borderLeft: `15px solid ${INK}`,
                opacity: 0.25 + 0.75 * Math.max(0, Math.sin(f / 3 - i * 0.9)),
              }}
            />
          ))}
        </div>
      )}
      {label}
    </div>
  );
};

/** Plays shots back to back. Each one gets a punch-in, a flash and its speed badge. */
export const Shots: React.FC<{ shots: Shot[] }> = ({ shots }) => {
  let from = 0;
  return (
    <>
      {shots.map((shot) => {
        const start = from;
        from += shot.dur;
        return (
          <Sequence key={shot.src + start} from={start} durationInFrames={shot.dur}>
            <Clip {...shot} />
            {shot.badge ? <SpeedBadge label={shot.badge} dur={shot.dur} /> : null}
          </Sequence>
        );
      })}
    </>
  );
};

/* ---------- text ---------- */

/** Words rise in one after another. Wrap a phrase in *asterisks* to colour it. */
export const Words: React.FC<{ text: string; stagger?: number; delay?: number; highlight?: string }> = ({
  text,
  stagger = 2,
  delay = 0,
  highlight = ACCENT,
}) => {
  const f = useCurrentFrame();
  let lit = false;
  return (
    <>
      {text.split(" ").map((raw, i) => {
        const opens = raw.startsWith("*");
        const closes = /\*[.,?!]?$/.test(raw);
        if (opens) lit = true;
        const isLit = lit;
        if (closes) lit = false;
        const word = raw.replace(/\*/g, "");
        const p = pop(f, delay + i * stagger, 16);
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              marginRight: "0.26em",
              color: isLit ? highlight : undefined,
              opacity: interpolate(p, [0, 0.6], [0, 1], clamp),
              transform: `translateY(${(1 - p) * 26}px)`,
            }}
          >
            {word}
          </span>
        );
      })}
    </>
  );
};

/** Lower-left caption. One sits on screen for every shot. */
export const Caption: React.FC<{ from: number; dur: number; text: string }> = ({ from, dur, text }) => (
  <Sequence from={from} durationInFrames={dur} layout="none">
    <CaptionBox dur={dur} text={text} />
  </Sequence>
);

const CaptionBox: React.FC<{ dur: number; text: string }> = ({ dur, text }) => {
  const { f, enter, exit } = useInOut(dur, 9, 7);
  return (
    <div
      style={{
        position: "absolute",
        left: 80,
        bottom: 80,
        maxWidth: 1240,
        padding: "22px 34px 24px 44px",
        borderRadius: 20,
        backgroundColor: PANEL,
        color: PAPER,
        fontFamily: BODY,
        fontWeight: 600,
        fontSize: 46,
        lineHeight: 1.24,
        opacity: Math.min(enter, exit),
        transform: `translateY(${(1 - enter) * 30 + (1 - exit) * 14}px)`,
        boxShadow: "0 16px 44px rgba(0,0,0,0.35)",
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 18,
          top: 20,
          bottom: 20,
          width: 8,
          borderRadius: 4,
          backgroundColor: ACCENT,
          transform: `scaleY(${pop(f, 2)})`,
          transformOrigin: "50% 100%",
        }}
      />
      <Words text={text} delay={3} />
    </div>
  );
};

/** Big yellow title that sweeps in at the start of a section, then parks as a small tag. */
export const Chapter: React.FC<{ text: string; dur: number }> = ({ text, dur }) => {
  const f = useCurrentFrame();
  const sweepIn = interpolate(f, [0, 10], [0, 1], { ...clamp, easing: Easing.out(Easing.exp) });
  const sweepOut = interpolate(f, [46, 58], [0, 1], { ...clamp, easing: Easing.in(Easing.cubic) });
  const textIn = interpolate(f, [5, 15], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const tag = pop(f, 54);
  const tagOut = interpolate(f, [dur - 10, dur - 2], [1, 0], clamp);
  return (
    <>
      {f < 60 ? (
        <div
          style={{
            position: "absolute",
            left: 80,
            top: 400,
            clipPath: `inset(0 ${(1 - sweepIn) * 100}% 0 ${sweepOut * 100}%)`,
          }}
        >
          <div
            style={{
              backgroundColor: ACCENT,
              color: INK,
              fontFamily: DISPLAY,
              fontWeight: 700,
              fontSize: 132,
              letterSpacing: -4,
              lineHeight: 1,
              padding: "26px 44px 34px",
              borderRadius: 14,
            }}
          >
            <div style={{ opacity: textIn, transform: `translateX(${(1 - textIn) * -40}px)` }}>{text}</div>
          </div>
        </div>
      ) : null}
      <div
        style={{
          position: "absolute",
          left: 80,
          top: 48,
          display: "flex",
          alignItems: "center",
          gap: 14,
          padding: "12px 26px 12px 20px",
          borderRadius: 999,
          backgroundColor: PANEL,
          color: PAPER,
          fontFamily: DISPLAY,
          fontWeight: 700,
          fontSize: 34,
          opacity: Math.min(tag, tagOut),
          transform: `translateY(${(1 - tag) * -30}px)`,
        }}
      >
        <div style={{ width: 16, height: 16, borderRadius: 8, backgroundColor: ACCENT }} />
        {text}
      </div>
    </>
  );
};

/** Small floating panel for the extra graphics. */
export const Card: React.FC<{
  from: number;
  dur: number;
  style: React.CSSProperties;
  children: React.ReactNode;
}> = ({ from, dur, style, children }) => (
  <Sequence from={from} durationInFrames={dur} layout="none">
    <CardBox dur={dur} style={style}>
      {children}
    </CardBox>
  </Sequence>
);

const CardBox: React.FC<{ dur: number; style: React.CSSProperties; children: React.ReactNode }> = ({
  dur,
  style,
  children,
}) => {
  const { f, exit } = useInOut(dur, 8, 8);
  const p = pop(f, 0, 13);
  return (
    <div
      style={{
        position: "absolute",
        padding: 24,
        borderRadius: 22,
        backgroundColor: PANEL,
        color: PAPER,
        fontFamily: BODY,
        boxShadow: "0 16px 44px rgba(0,0,0,0.4)",
        border: "2px solid rgba(255,255,255,0.14)",
        opacity: Math.min(interpolate(p, [0, 0.5], [0, 1], clamp), exit),
        transform: `scale(${0.8 + 0.2 * p})`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const CardLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 24, letterSpacing: 4, color: ACCENT }}>{children}</div>
);

/* ---------- transitions and finishing ---------- */

/** Two slanted panels sweep across the screen; the cut hides under them at frame `at`. */
export const Wipe: React.FC<{ at: number }> = ({ at }) => {
  const f = useCurrentFrame();
  if (f < at - 12 || f > at + 12) return null;
  const x = (mid: number) => interpolate(f, [mid - 9, mid, mid + 9], [-2900, -390, 2120], clamp);
  const panel = (mid: number, color: string): React.CSSProperties => ({
    position: "absolute",
    top: -40,
    left: 0,
    width: 2700,
    height: 1160,
    backgroundColor: color,
    transform: `translateX(${x(mid)}px) skewX(-12deg)`,
  });
  return (
    <AbsoluteFill>
      <div style={panel(at + 1, ACCENT)} />
      <div style={panel(at - 1, INK)} />
    </AbsoluteFill>
  );
};

export const Vignette: React.FC = () => (
  <AbsoluteFill
    style={{
      background:
        "radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.38) 100%), linear-gradient(to top, rgba(0,0,0,0.42) 0%, rgba(0,0,0,0) 26%)",
    }}
  />
);
