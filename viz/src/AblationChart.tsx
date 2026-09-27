import React from "react";
import data from "./data.json";
import {Frame, fontFamily} from "./Frame";
import {themes} from "./theme";

type Row = {label: string; sublabel?: string; seeds: number[]; mean: number; final?: boolean};

export const AblationChart: React.FC<{mode: "light" | "dark"}> = ({mode}) => {
  const t = themes[mode];
  const rows = data.ablation as Row[];
  const W = 1080, H = 500, L = 300, R = 70, T = 10, B = 44;
  const rowH = (H - T - B) / rows.length;
  const x = (v: number) => L + (v / 100) * (W - L - R);
  return (
    <Frame t={t} title="What made it generalize"
      subtitle="Parts built correctly on 11-feature goals · average of the training runs for each step">
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} style={{fontFamily, overflow: "visible"}}>
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line x1={x(v)} x2={x(v)} y1={T} y2={H - B} stroke={t.grid} strokeWidth={1} />
            <text x={x(v)} y={H - B + 28} textAnchor="middle" fontSize={15} fill={t.ink2}>{v}%</text>
          </g>
        ))}
        {rows.map((r, i) => {
          const cy = T + rowH * (i + 0.5);
          const h = 26;
          const w = Math.max(x(r.mean) - L, 0);
          return (
            <g key={r.label}>
              <text x={L - 20} y={cy + (r.sublabel ? -3 : 6)} textAnchor="end" fontSize={18}
                fontWeight={r.final ? 700 : 500} fill={t.ink}>{r.label}</text>
              {r.sublabel && <text x={L - 20} y={cy + 19} textAnchor="end" fontSize={14} fill={t.ink3}>{r.sublabel}</text>}
              {w > 0 ? (
                <path d={`M${L},${cy - h / 2} H${L + w - 6} a6,6 0 0 1 6,6 V${cy + h / 2 - 6} a6,6 0 0 1 -6,6 H${L} Z`}
                  fill={t.s1} opacity={r.final ? 1 : 0.78} />
              ) : null}
              <text x={x(r.mean) + 16} y={cy + 6} fontSize={17} fontWeight={600} fill={t.ink}>
                {Math.round(r.mean)}%</text>
            </g>
          );
        })}
      </svg>
    </Frame>
  );
};
