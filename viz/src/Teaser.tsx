import React from "react";
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {fontFamily} from "./Frame";
import STEPS from "./buildSteps.json";

// ~9 s teaser: title -> the model building a flange live in FreeCAD -> end card.
// Build frames are real FreeCAD renders, one per command (scripts/gui_demo.py --frames-dir).

export const TEASER = {fps: 30, durationInFrames: 270, width: 1920, height: 1080};

const ACCENT = "#2f7d5b";
const INK = "#111614";
const INK2 = "#4d5a54";
const BG = "radial-gradient(1400px 900px at 78% 18%, #e3eee8 0%, #eef2ef 45%, #f7f7f4 100%)";

const BUILD_START = 72;
const PER_STEP = 4;
const BUILD_END = BUILD_START + STEPS.length * PER_STEP; // 180
const RESULT_START = 198;

const GOAL = [
  {label: "Disc Ø72 × 8", upto: 8},
  {label: "Boss Ø30 × 12", upto: 15},
  {label: "Hole Ø6.4", upto: 22},
  {label: "Polar pattern × 6", upto: 24},
  {label: "Chamfer 1.5", upto: 26},
];

const pretty = (a: string) =>
  a === "Done" ? "Done" : a.replace(/^(PartDesign|Sketcher|Std)_/, "").replace(/^Select:/, "Select ").replace(/:/g, " ");

const fade = (f: number, a: number, b: number) =>
  interpolate(f, [a, b], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});

const Title: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = (d: number) => spring({frame: f - d, fps, config: {damping: 200}});
  const out = 1 - fade(f, 58, 72);
  return (
    <AbsoluteFill style={{justifyContent: "center", alignItems: "center", opacity: out}}>
      <div style={{textAlign: "center", transform: `scale(${1 + 0.04 * (1 - out)})`}}>
        <div style={{opacity: s(0), transform: `translateY(${(1 - s(0)) * 20}px)`, color: ACCENT, fontSize: 26,
          fontWeight: 600, letterSpacing: 4, display: "flex", gap: 14, alignItems: "center", justifyContent: "center"}}>
          <span style={{width: 40, height: 5, borderRadius: 3, background: ACCENT}} />SYSTEM-1 MODEL FOR CAD
        </div>
        <div style={{opacity: s(5), transform: `translateY(${(1 - s(5)) * 30}px)`, fontSize: 168, fontWeight: 800,
          color: INK, letterSpacing: -5, marginTop: 10}}>Taiga-S1</div>
        <div style={{opacity: s(14), transform: `translateY(${(1 - s(14)) * 20}px)`, fontSize: 40, color: INK2,
          fontWeight: 500, marginTop: 6}}>A 1.2M-parameter model that builds CAD parts in FreeCAD</div>
      </div>
    </AbsoluteFill>
  );
};

const Build: React.FC = () => {
  const f = useCurrentFrame();
  const inOp = fade(f, BUILD_START - 6, BUILD_START + 6);
  const outOp = 1 - fade(f, RESULT_START - 12, RESULT_START);
  const step = Math.max(1, Math.min(STEPS.length, Math.floor((f - BUILD_START) / PER_STEP) + 1));
  const active = GOAL.findIndex((g) => step <= g.upto);
  const finished = step === STEPS.length;
  const pop = finished ? 1 + 0.03 * Math.sin(Math.min(1, (f - (BUILD_END - PER_STEP)) / 10) * Math.PI) : 1;
  const visible = STEPS.slice(Math.max(0, step - 8), step);
  return (
    <AbsoluteFill style={{opacity: Math.min(inOp, outOp), flexDirection: "row", padding: "90px 110px", gap: 70}}>
      {/* live FreeCAD render */}
      <div style={{width: 860, display: "flex", flexDirection: "column"}}>
        <div style={{fontSize: 24, color: INK2, fontWeight: 600, letterSpacing: 3}}>LIVE IN FREECAD</div>
        <div style={{flex: 1, display: "flex", alignItems: "center", justifyContent: "center"}}>
          <Img src={staticFile(`build/step_${String(step).padStart(3, "0")}.png`)}
            style={{width: 780, height: 780, objectFit: "contain", transform: `scale(${pop})`,
              filter: "drop-shadow(0 30px 34px rgba(20,40,30,0.20)) drop-shadow(0 6px 10px rgba(20,40,30,0.14))"}} />
        </div>
      </div>
      {/* goal + command stream */}
      <div style={{flex: 1, display: "flex", flexDirection: "column", paddingTop: 20}}>
        <div style={{fontSize: 24, color: INK2, fontWeight: 600, letterSpacing: 3}}>GOAL</div>
        <div style={{display: "flex", flexWrap: "wrap", gap: 12, marginTop: 16}}>
          {GOAL.map((g, i) => {
            const done = i < active || finished;
            const cur = i === active && !finished;
            return (
              <div key={g.label} style={{padding: "10px 18px", borderRadius: 999, fontSize: 24, fontWeight: 500,
                border: `1.5px solid ${cur ? ACCENT : "rgba(17,22,20,0.12)"}`,
                background: done ? ACCENT : cur ? "rgba(47,125,91,0.10)" : "rgba(255,255,255,0.7)",
                color: done ? "#fff" : INK}}>{done ? "✓ " : ""}{g.label}</div>
            );
          })}
        </div>
        <div style={{display: "flex", justifyContent: "space-between", marginTop: 54, fontSize: 24, color: INK2,
          fontWeight: 600, letterSpacing: 3}}>
          <span>COMMANDS</span>
          <span style={{fontVariantNumeric: "tabular-nums", letterSpacing: 1}}>{step} / {STEPS.length}</span>
        </div>
        <div style={{marginTop: 18, display: "flex", flexDirection: "column", gap: 10}}>
          {visible.map((a, i) => {
            const last = i === visible.length - 1;
            return (
              <div key={step - visible.length + i} style={{display: "flex", justifyContent: "space-between",
                alignItems: "center", padding: "12px 20px", borderRadius: 14, fontSize: 30,
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                background: last ? "#fff" : "transparent", color: last ? INK : "rgba(17,22,20,0.35)",
                boxShadow: last ? "0 8px 24px rgba(20,40,30,0.10)" : "none",
                border: last ? `1.5px solid ${ACCENT}` : "1.5px solid transparent"}}>
                <span>{pretty(a)}</span>
                {last && <span style={{fontSize: 22, color: ACCENT, fontFamily}}>~1 ms</span>}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Result: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = (d: number) => spring({frame: f - RESULT_START - d, fps, config: {damping: 200}});
  return (
    <AbsoluteFill style={{flexDirection: "row", alignItems: "center", padding: "0 140px", gap: 60,
      opacity: fade(f, RESULT_START, RESULT_START + 8)}}>
      <Img src={staticFile(`build/step_${String(STEPS.length).padStart(3, "0")}.png`)}
        style={{width: 700, height: 700, objectFit: "contain", opacity: s(0), transform: `scale(${0.94 + 0.06 * s(0)})`,
          filter: "drop-shadow(0 30px 34px rgba(20,40,30,0.20)) drop-shadow(0 6px 10px rgba(20,40,30,0.14))"}} />
      <div>
        <div style={{opacity: s(4), transform: `translateY(${(1 - s(4)) * 24}px)`, fontSize: 150, fontWeight: 800,
          color: INK, letterSpacing: -5}}>Taiga-S1</div>
        <div style={{display: "flex", flexDirection: "column", gap: 14, marginTop: 20}}>
          {["1.2M parameters", "~1 ms per decision", "No LLM · no screenshots"].map((c, i) => (
            <div key={c} style={{opacity: s(10 + 4 * i), transform: `translateX(${(1 - s(10 + 4 * i)) * 20}px)`,
              fontSize: 38, color: INK2, fontWeight: 500, display: "flex", alignItems: "center", gap: 16}}>
              <span style={{width: 10, height: 10, borderRadius: 5, background: ACCENT}} />{c}</div>
          ))}
        </div>
        <div style={{opacity: s(30), transform: `translateY(${(1 - s(30)) * 16}px)`, marginTop: 48, display: "inline-flex",
          padding: "16px 30px", borderRadius: 999, background: INK, color: "#fff", fontSize: 30, fontWeight: 600}}>
          huggingface.co/shhivv/taiga-s1</div>
      </div>
    </AbsoluteFill>
  );
};

export const Teaser: React.FC = () => (
  <AbsoluteFill style={{background: BG, fontFamily}}>
    <AbsoluteFill style={{opacity: 0.35,
      backgroundImage: "linear-gradient(rgba(20,40,30,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(20,40,30,0.06) 1px, transparent 1px)",
      backgroundSize: "60px 60px"}} />
    <Title />
    <Build />
    <Result />
  </AbsoluteFill>
);
