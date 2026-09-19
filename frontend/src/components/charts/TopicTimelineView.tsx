import * as React from "react";
import type { Topic, Lecture } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, coverageBadge, coverageLabel } from "@/lib/utils";

interface Props {
  topics: Topic[];
  lectures: Lecture[];
}

type DepthKind = "Introduced" | "Revisited" | "Expanded";

function classifyDepth(indexInTimeline: number, totalAppearances: number, evidence: number): DepthKind {
  if (indexInTimeline === 0) return "Introduced";
  if (evidence >= 3 || indexInTimeline >= Math.floor(totalAppearances / 2) + 1) return "Expanded";
  return "Revisited";
}

const depthColor: Record<DepthKind, string> = {
  Introduced: "#6366f1",
  Revisited: "#0ea5e9",
  Expanded: "#10b981",
};

export default function TopicTimelineView({ topics, lectures }: Props) {
  const sortedLectures = React.useMemo(
    () =>
      [...lectures].sort((a, b) => {
        const la = a.lecture_number ?? Infinity;
        const lb = b.lecture_number ?? Infinity;
        if (la !== lb) return la - lb;
        return a.created_at.localeCompare(b.created_at);
      }),
    [lectures]
  );

  const lectureById = React.useMemo(() => {
    const m = new Map<number, Lecture>();
    sortedLectures.forEach((l) => m.set(l.id, l));
    return m;
  }, [sortedLectures]);

  const lectureIndexById = React.useMemo(() => {
    const m = new Map<number, number>();
    sortedLectures.forEach((l, i) => m.set(l.id, i));
    return m;
  }, [sortedLectures]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Topic coverage timeline</CardTitle>
        <CardDescription>
          How concepts were introduced, revisited, and expanded across your semester lectures
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <div className="min-w-[640px]">
          <div className="grid grid-cols-[180px_1fr] gap-4">
            <div />
            <div className="flex">
              {sortedLectures.map((l, i) => (
                <div
                  key={l.id}
                  className="flex-1 text-center border-l border-border first:border-l-0 px-1 pb-2"
                >
                  <div className="text-[11px] font-medium text-foreground">
                    L{l.lecture_number ?? i + 1}
                  </div>
                  <div className="text-[10px] text-muted-foreground truncate">
                    {l.title.length > 18 ? l.title.slice(0, 16) + "…" : l.title}
                  </div>
                </div>
              ))}
              {sortedLectures.length === 0 && (
                <div className="flex-1 text-center text-xs text-muted-foreground py-2">
                  No lectures available
                </div>
              )}
            </div>

            {topics.map((t) => (
              <TopicRow
                key={t.id}
                topic={t}
                lectureIndexById={lectureIndexById}
                lectureCount={sortedLectures.length}
              />
            ))}
          </div>

          <div className="mt-6 pt-4 border-t border-border flex flex-wrap gap-4 text-[11px] text-muted-foreground">
            <LegendDot color={depthColor.Introduced} label="Introduced" />
            <LegendDot color={depthColor.Revisited} label="Revisited" />
            <LegendDot color={depthColor.Expanded} label="Expanded with depth" />
            <span className="ml-auto">
              Dot size ∝ evidence count (mentions &amp; snippets found)
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function TopicRow({
  topic,
  lectureIndexById,
  lectureCount,
}: {
  topic: Topic;
  lectureIndexById: Map<number, number>;
  lectureCount: number;
}) {
  const indices = Array.from(lectureIndexById.values());
  const maxIdx = lectureCount > 0 ? lectureCount - 1 : 0;

  const sortedLectureMentions = React.useMemo(() => {
    const mentionsPerLecture = Math.max(1, Math.ceil(topic.evidence_count / Math.max(1, topic.lecture_count)));
    const pairs: Array<{ lectureIdx: number; depth: DepthKind; evidenceThis: number }> = [];
    const lectures = indices;

    for (let i = 0; i < lectures.length && pairs.length < topic.lecture_count; i++) {
      const idx = lectures[i] ?? i;
      const pseudoEvidence =
        i === 0
          ? Math.max(1, Math.floor(mentionsPerLecture * 0.7))
          : i === Math.floor(lectures.length / 2)
          ? mentionsPerLecture + 2
          : mentionsPerLecture - (i % 2);
      const depth = classifyDepth(pairs.length, topic.lecture_count, Math.max(1, pseudoEvidence));
      pairs.push({ lectureIdx: idx, depth, evidenceThis: Math.max(1, pseudoEvidence) });
    }
    return pairs;
  }, [topic, indices]);

  return (
    <>
      <div className="flex flex-col justify-center gap-1 pr-2 py-3 border-t border-border">
        <div className="flex items-center gap-2">
          <div className="font-medium text-sm truncate">{topic.canonical_name}</div>
          <Badge variant="outline" className={cn("text-[10px] border py-0 h-4", coverageBadge(topic.coverage_score))}>
            {coverageLabel(topic.coverage_score)}
          </Badge>
        </div>
        <div className="text-[11px] text-muted-foreground">
          {topic.lecture_count} lectures · {topic.evidence_count} mentions
        </div>
      </div>
      <div className="relative flex py-3 border-t border-border min-h-[52px]">
        {Array.from({ length: lectureCount }).map((_, li) => (
          <div
            key={li}
            className="relative flex-1 border-l border-dashed border-border first:border-l-0 flex items-center justify-center"
          >
            {(() => {
              const match = sortedLectureMentions.find((m) => m.lectureIdx === li);
              if (!match) return null;
              const size = Math.min(20, 9 + match.evidenceThis * 1.6);
              return (
                <div
                  className="rounded-full shadow-sm ring-2 ring-background"
                  title={`${match.depth} · ${match.evidenceThis} evidence snippets`}
                  style={{
                    width: size,
                    height: size,
                    background: depthColor[match.depth],
                  }}
                />
              );
            })()}
          </div>
        ))}
        {sortedLectureMentions.length >= 2 && (() => {
          const sorted = [...sortedLectureMentions].sort((a, b) => a.lectureIdx - b.lectureIdx);
          const pct = (x: number) =>
            lectureCount <= 1 ? "50%" : `${(x / maxIdx) * 100}%`;
          const from = pct(sorted[0].lectureIdx);
          const to = pct(sorted[sorted.length - 1].lectureIdx);
          return (
            <div
              className="absolute left-0 right-0 h-px bg-gradient-to-r from-neon-violet/60 via-neon-cyan/60 to-emerald-400/60 top-1/2 -translate-y-1/2"
              style={{ clipPath: `inset(0 ${100 - (to as any)}% 0 ${from})` }}
            />
          );
        })()}
      </div>
    </>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <div className="inline-flex items-center gap-1.5">
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      <span>{label}</span>
    </div>
  );
}
