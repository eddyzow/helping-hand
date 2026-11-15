import React from "react";
import { AbsoluteFill, Easing, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";
import { loadFont as loadSerif } from "@remotion/google-fonts/InstrumentSerif";
import { loadFont as loadSans } from "@remotion/google-fonts/HankenGrotesk";
import { loadFont as loadMono } from "@remotion/google-fonts/IBMPlexMono";

loadSerif("italic", { weights: ["400"], subsets: ["latin"] });
export const SERIF = loadSerif("normal", { weights: ["400"], subsets: ["latin"] }).fontFamily;
export const SANS = loadSans("normal", { weights: ["500", "600"], subsets: ["latin"] }).fontFamily;
export const MONO = loadMono("normal", { weights: ["500"], subsets: ["latin"] }).fontFamily;

export const FPS = 30;
export const INK = "#0C0C0E";
export const PAPER = "#F6F2EA";
export const ACCENT = "#F2B544";
export const SHADOW = "0 2px 16px rgba(0,0,0,0.8), 0 0 3px rgba(0,0,0,0.7)";
export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const easeOut = Easing.out(Easing.cubic);

/** 0 to 1 over `length` frames starting at `start`, eased. */
export const ramp = (f: number, start: number, length = 14) =>
  interpolate(f, [start, start + length], [0, 1], { ...clamp, easing: easeOut });

/* ---------- footage ---------- */

export type Shot = {
  src: string;
  dur: number;
  speed?: string; // "4×" or "REAL TIME"
  zoom?: [number, number];
  origin?: string;
  dim?: number;
  still?: boolean;
};

export function Clip({ src, dur, zoom = [1.0, 1.05], origin = "50% 50%", dim = 0, still }: Shot) {
  const f = useCurrentFrame();
  const push = interpolate(f, [0, 8], [0.025, 0], { ...clamp, easing: easeOut });
  const scale = interpolate(f, [0, dur], zoom, clamp) + push;
  const style: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "cover",
    transform: `scale(${scale})`,
    transformOrigin: origin,
  };
  return (
    <AbsoluteFill style={{ backgroundColor: INK, overflow: "hidden" }}>
      {still ? <img src={staticFile(src)} style={style} /> : <OffthreadVideo muted src={staticFile(src)} style={style} />}
      {dim > 0 ? <AbsoluteFill style={{ backgroundColor: `rgba(12,12,14,${dim})` }} /> : null}
    </AbsoluteFill>
  );
}

function Speed({ label, dur }: { label: string; dur: number }) {
  const f = useCurrentFrame();
  const opacity = Math.min(ramp(f, 2, 8), interpolate(f, [dur - 6, dur], [1, 0], clamp));
  const live = label === "REAL TIME";
  return (
    <div
      style={{
        position: "absolute",
        right: 64,
        top: 56,
        display: "flex",
        alignItems: "center",
        gap: 12,
        fontFamily: MONO,
        fontWeight: 500,
        fontSize: 30,
        letterSpacing: live ? 4 : 1,
        color: PAPER,
        textShadow: SHADOW,
        opacity,
      }}
    >
      {live ? (
        <div style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: "#E5484D", opacity: 0.6 + 0.4 * Math.sin(f / 5) }} />
      ) : null}
      {live ? label : `▸▸ ${label}`}
    </div>
  );
}

/** Plays shots back to back, each with its speed label. */
export function Shots({ shots }: { shots: Shot[] }) {
  let from = 0;
  return (
    <>
      {shots.map((shot) => {
        const start = from;
        from += shot.dur;
        return (
          <Sequence key={shot.src + start} from={start} durationInFrames={shot.dur}>
            <Clip {...shot} />
            {shot.speed ? <Speed label={shot.speed} dur={shot.dur} /> : null}
          </Sequence>
        );
      })}
    </>
  );
}

/* ---------- text ---------- */

/** One line that rises out of a mask. */
export function Rise({ at, children, style }: { at: number; children: React.ReactNode; style?: React.CSSProperties }) {
  const f = useCurrentFrame();
  const p = ramp(f, at, 18);
  return (
    <div style={{ overflow: "hidden", paddingBottom: "0.12em", ...style }}>
      <div style={{ transform: `translateY(${(1 - p) * 105}%)`, opacity: interpolate(p, [0, 0.3], [0, 1], clamp) }}>{children}</div>
    </div>
  );
}

/** Small clip name in the top-left corner. */
export function Label({ text, dur }: { text: string; dur: number }) {
  const f = useCurrentFrame();
  const p = ramp(f, 8, 16);
  const out = interpolate(f, [dur - 10, dur - 2], [1, 0], clamp);
  return (
    <div
      style={{
        position: "absolute",
        left: 64,
        top: 56,
        display: "flex",
        alignItems: "center",
        gap: 18,
        fontFamily: MONO,
        fontWeight: 500,
        fontSize: 28,
        letterSpacing: 6,
        color: PAPER,
        textShadow: SHADOW,
        opacity: Math.min(p, out),
      }}
    >
      <div style={{ width: 56 * p, height: 3, backgroundColor: PAPER }} />
      {text.toUpperCase()}
    </div>
  );
}

/** Captions for the voiceover. Each cue is [start s, end s, text]. */
export function Subtitles({ cues }: { cues: Array<[number, number, string]> }) {
  const f = useCurrentFrame();
  const t = f / FPS;
  const cue = cues.find(([a, b]) => t >= a && t < b);
  if (!cue) return null;
  const [a, b, text] = cue;
  const opacity = Math.min(interpolate(t, [a, a + 0.12], [0, 1], clamp), interpolate(t, [b - 0.1, b], [1, 0], clamp));
  return (
    <div
      style={{
        position: "absolute",
        left: 260,
        right: 260,
        bottom: 74,
        textAlign: "center",
        fontFamily: SANS,
        fontWeight: 600,
        fontSize: 46,
        lineHeight: 1.25,
        color: PAPER,
        textShadow: SHADOW,
        textWrap: "balance",
        opacity,
      }}
    >
      {text}
    </div>
  );
}

/* ---------- finishing ---------- */

/** Quick dip to black that hides the cut between two sections at frame `at`. */
export function Dip({ at }: { at: number }) {
  const f = useCurrentFrame();
  const opacity = interpolate(f, [at - 7, at, at + 7], [0, 1, 0], clamp);
  return opacity > 0 ? <AbsoluteFill style={{ backgroundColor: "#000", opacity }} /> : null;
}

/** Darkens the bottom so the captions stay readable. */
export function Shade() {
  return (
    <AbsoluteFill
      style={{ background: "linear-gradient(to top, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0) 30%), linear-gradient(to bottom, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0) 16%)" }}
    />
  );
}
