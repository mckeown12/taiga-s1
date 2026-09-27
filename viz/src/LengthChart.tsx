import React from "react";
import data from "./data.json";
import {Frame, fontFamily} from "./Frame";
import {themes} from "./theme";

export const LengthChart: React.FC<{mode: "light" | "dark"}> = ({mode}) => {
  const t = themes[mode];
  const W = 1080, H = 500, L = 64, R = 70, T = 16, B = 70;
  const cats = data.length.categories;
  const x = (i: number) => L + (i + 0.5) * ((W - L - R) / cats.length);
  const y = (v: number) => T + (1 - v / 100) * (H - T - B);
  const band = (W - L - R) / cats.length;
  const [taiga, v2] = data.length.series;
  const colors = [t.s1, t.s2];
  const pts = (vals: (number | null)[]) => vals.map((v, i) => (v == null ? null : ([x(i), y(v)] as const))).filter(Boolean) as (readonly [number, number])[];
  const path = (p: (readonly [number, number])[]) => p.map(([px, py], i) => `${i ? "L" : "M"}${px},${py}`).join(" ");
  return (
    <Frame t={t} title="Parts built correctly vs. goal length"
      subtitle="Clean success in live FreeCAD · 100 goals per point (60 beyond 11 features)"
      legend={[{label: "Taiga-S1", color: t.s1}, {label: "Previous model (v2)", color: t.s2}]}>
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} style={{fontFamily, overflow: "visible"}}>
        <rect x={L} y={T - 8} width={band} height={H - T - B + 8} rx={10} fill={t.band} />
        <text x={L + band / 2} y={y(0) - 14} textAnchor="middle" fontSize={13} fontWeight={600} fill={t.ink3}
          letterSpacing={1.2}>TRAINING</text>
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R + 30} y1={y(v)} y2={y(v)} stroke={t.grid} strokeWidth={1} />
            <text x={L - 14} y={y(v) + 5} textAnchor="end" fontSize={15} fill={t.ink2}>{v}%</text>
          </g>
        ))}
        {cats.map((c, i) => (
          <text key={c} x={x(i)} y={H - B + 32} textAnchor="middle" fontSize={16} fill={t.ink2}>{c}</text>
        ))}
        <text x={(L + W - R) / 2} y={H - 8} textAnchor="middle" fontSize={15} fill={t.ink3}>
          Features in the goal</text>
        {[v2, taiga].map((s) => {
          const k = s === taiga ? 0 : 1;
          const p = pts(s.values);
          return (
            <g key={s.name}>
              <path d={path(p)} fill="none" stroke={colors[k]} strokeWidth={3} strokeLinejoin="round" strokeLinecap="round" />
              {p.map(([px, py], i) => (
                <circle key={i} cx={px} cy={py} r={6} fill={colors[k]} stroke={t.card} strokeWidth={3} />
              ))}
              <text x={p[p.length - 1][0] + 14} y={p[p.length - 1][1] + 6} fontSize={17} fontWeight={600} fill={t.ink}>
                {s.values.filter((v) => v != null).slice(-1)[0]}%</text>
            </g>
          );
        })}
      </svg>
    </Frame>
  );
};
