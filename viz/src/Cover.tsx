import React from "react";
import {Img, staticFile} from "remotion";
import {fontFamily} from "./Frame";

const PARTS = ["L3_comp3_5", "L3_iid_7", "L4_len_44", "L3_iid_37"];
const ACCENT = "#5bb38a";

export const Cover: React.FC = () => (
  <div style={{width: "100%", height: "100%", position: "relative", overflow: "hidden", fontFamily,
    background: "radial-gradient(1200px 700px at 78% 30%, #1d2b27 0%, #121716 55%, #0b0e0d 100%)"}}>
    {/* faint engineering grid */}
    <div style={{position: "absolute", inset: 0, opacity: 0.35,
      backgroundImage: "linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px)",
      backgroundSize: "60px 60px", maskImage: "linear-gradient(180deg, transparent 0%, #000 35%, #000 70%, transparent 100%)"}} />
    <div style={{position: "absolute", left: 140, top: 130}}>
      <div style={{display: "flex", alignItems: "center", gap: 14, color: ACCENT, fontSize: 26, fontWeight: 600,
        letterSpacing: 3}}>
        <span style={{width: 44, height: 5, borderRadius: 3, background: ACCENT}} />
        SYSTEM-1 MODEL FOR CAD
      </div>
      <div style={{fontSize: 176, fontWeight: 800, color: "#f3f5f3", letterSpacing: -5, lineHeight: 1.05, marginTop: 18}}>
        Taiga-S1</div>
      <div style={{fontSize: 44, color: "#aab5b0", marginTop: 14, fontWeight: 500, letterSpacing: -0.5}}>
        A 1.2M-parameter model that drives FreeCAD, one command at a time</div>
      <div style={{display: "flex", gap: 16, marginTop: 38}}>
        {["1.2M parameters", "~1 ms per decision", "No LLM · no screenshots"].map((c) => (
          <div key={c} style={{padding: "12px 22px", borderRadius: 999, border: "1.5px solid rgba(255,255,255,0.14)",
            color: "#dfe6e2", fontSize: 26, fontWeight: 500, background: "rgba(255,255,255,0.04)"}}>{c}</div>
        ))}
      </div>
    </div>
    <div style={{position: "absolute", left: 70, right: 70, bottom: 80, display: "flex", justifyContent: "space-between",
      alignItems: "flex-end"}}>
      {PARTS.map((p, i) => (
        <Img key={p} src={staticFile(`parts/${p}.png`)}
          style={{width: 520, height: 480, objectFit: "contain",
            transform: `translateY(${i % 2 ? -18 : 0}px)`,
            filter: "drop-shadow(0 36px 40px rgba(0,0,0,0.55)) drop-shadow(0 6px 10px rgba(0,0,0,0.35))"}} />
      ))}
    </div>
  </div>
);
