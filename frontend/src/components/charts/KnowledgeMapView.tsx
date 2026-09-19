import * as React from "react";
import type { KnowledgeMap, KnowledgeMapNode, KnowledgeMapEdge } from "@/types";
import { cn } from "@/lib/utils";

interface Props {
  data: KnowledgeMap;
  onNodeClick?: (node: KnowledgeMapNode) => void;
  width?: number;
  height?: number;
}

function layoutCircular(nodes: KnowledgeMapNode[], width: number, height: number) {
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) * 0.38;
  const sorted = [...nodes].sort((a, b) => b.coverage_score - a.coverage_score);
  return sorted.map((n, i) => {
    const angle = (i / sorted.length) * Math.PI * 2 - Math.PI / 2;
    return {
      ...n,
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
    };
  });
}

function coverageColor(score: number) {
  if (score >= 0.7) return "#6366f1";
  if (score >= 0.4) return "#0ea5e9";
  if (score >= 0.2) return "#f59e0b";
  return "#94a3b8";
}

export default function KnowledgeMapView({
  data,
  onNodeClick,
  width = 720,
  height = 480,
}: Props) {
  const [hovered, setHovered] = React.useState<number | null>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [dim, setDim] = React.useState({ w: width, h: height });

  React.useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        const { width: w } = e.contentRect;
        setDim({ w: Math.max(320, w), h: Math.max(320, Math.min(520, w * 0.65)) });
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const laidOut = React.useMemo(
    () => layoutCircular(data.nodes, dim.w, dim.h),
    [data.nodes, dim.w, dim.h]
  );

  const nodeById = React.useMemo(() => {
    const m = new Map<number, (typeof laidOut)[number]>();
    laidOut.forEach((n) => m.set(n.id, n));
    return m;
  }, [laidOut]);

  const visibleEdges = React.useMemo(() => {
    const sorted = [...data.edges].sort((a, b) => b.weight - a.weight);
    return sorted.slice(0, Math.max(20, data.nodes.length * 2));
  }, [data.edges, data.nodes.length]);

  const connectedToHovered = React.useMemo(() => {
    const s = new Set<number>();
    if (hovered == null) return s;
    visibleEdges.forEach((e) => {
      if (e.source === hovered) s.add(e.target);
      if (e.target === hovered) s.add(e.source);
    });
    return s;
  }, [hovered, visibleEdges]);

  return (
    <div ref={containerRef} className="w-full">
      <svg
        viewBox={`0 0 ${dim.w} ${dim.h}`}
        className="w-full h-auto select-none"
        style={{ maxHeight: dim.h }}
      >
        <defs>
          <radialGradient id="nodeGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#6366f1" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
          </radialGradient>
        </defs>

        {visibleEdges.map((e, i) => {
          const a = nodeById.get(e.source);
          const b = nodeById.get(e.target);
          if (!a || !b) return null;
          const dimEdge =
            hovered != null &&
            !(e.source === hovered || e.target === hovered);
          return (
            <line
              key={`e-${i}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="#6b7299"
              strokeWidth={Math.max(0.6, e.weight * 2.2)}
              strokeOpacity={dimEdge ? 0.15 : 0.55}
            />
          );
        })}

        {laidOut.map((n) => {
          const isHovered = hovered === n.id;
          const dim = hovered != null && !isHovered && !connectedToHovered.has(n.id);
          const color = coverageColor(n.coverage_score);
          return (
            <g
              key={n.id}
              className={cn("cursor-pointer")}
              onMouseEnter={() => setHovered(n.id)}
              onMouseLeave={() => setHovered((h) => (h === n.id ? null : h))}
              onClick={() => onNodeClick?.(n)}
              opacity={dim ? 0.35 : 1}
            >
              {isHovered && (
                <circle cx={n.x} cy={n.y} r={n.size + 10} fill="url(#nodeGlow)" />
              )}
              <circle
                cx={n.x}
                cy={n.y}
                r={n.size}
                fill={color}
                fillOpacity={0.18}
                stroke={color}
                strokeWidth={isHovered ? 2.5 : 1.5}
              />
              <text
                x={n.x}
                y={n.y + 4}
                textAnchor="middle"
                fontSize={Math.max(10, Math.min(14, 9 + n.size * 0.4))}
                fontWeight={isHovered ? 600 : 500}
                fill="#e2e8f0"
                style={{ pointerEvents: "none" }}
              >
                {n.label.length > 14 ? n.label.slice(0, 12) + "…" : n.label}
              </text>
            </g>
          );
        })}
      </svg>

      {hovered != null && nodeById.get(hovered) && (
        <div className="mt-3 flex items-center gap-3 text-xs border rounded-lg px-3 py-2 bg-muted border-border">
          <span className="font-semibold">{nodeById.get(hovered)!.label}</span>
          <span className="text-muted-foreground">
            Coverage {(nodeById.get(hovered)!.coverage_score * 100).toFixed(0)}% ·
            appears in {nodeById.get(hovered)!.lecture_count} lectures
          </span>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-3 text-[11px] text-muted-foreground">
        <LegendItem color="#6366f1" label="High coverage (≥70%)" />
        <LegendItem color="#0ea5e9" label="Medium (40–70%)" />
        <LegendItem color="#f59e0b" label="Low (20–40%)" />
        <LegendItem color="#94a3b8" label="Rare (<20%)" />
      </div>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="inline-flex items-center gap-1.5">
      <span
        className="h-2.5 w-2.5 rounded-full"
        style={{ background: color }}
      />
      <span>{label}</span>
    </div>
  );
}
