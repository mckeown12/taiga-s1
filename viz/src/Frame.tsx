import React from "react";
import {loadFont} from "@remotion/google-fonts/Inter";
import type {Theme} from "./theme";

export const {fontFamily} = loadFont("normal", {weights: ["400", "500", "600", "700", "800"], subsets: ["latin"]});

export const Frame: React.FC<{t: Theme; title: string; subtitle: string; legend?: {label: string; color: string}[];
  children: React.ReactNode}> = ({t, title, subtitle, legend, children}) => (
  <div style={{width: "100%", height: "100%", background: t.surface, padding: 28, boxSizing: "border-box", fontFamily}}>
    <div style={{width: "100%", height: "100%", background: t.card, borderRadius: 20, padding: "34px 40px 26px",
      boxSizing: "border-box", display: "flex", flexDirection: "column",
      boxShadow: "0 1px 2px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.06)"}}>
      <div style={{display: "flex", justifyContent: "space-between", alignItems: "flex-start"}}>
        <div>
          <div style={{fontSize: 30, fontWeight: 700, color: t.ink, letterSpacing: -0.5}}>{title}</div>
          <div style={{fontSize: 16, color: t.ink2, marginTop: 6}}>{subtitle}</div>
        </div>
        {legend && (
          <div style={{display: "flex", gap: 22, marginTop: 8}}>
            {legend.map((l) => (
              <div key={l.label} style={{display: "flex", alignItems: "center", gap: 8, fontSize: 16, color: t.ink}}>
                <span style={{width: 22, height: 3, borderRadius: 2, background: l.color}} />
                {l.label}
              </div>
            ))}
          </div>
        )}
      </div>
      <div style={{flex: 1, position: "relative", marginTop: 12}}>{children}</div>
    </div>
  </div>
);
