import * as React from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Search as SearchIcon, BookOpen, Sparkles, Hash, ArrowUpRight, Filter,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { EmptyState, Spinner } from "@/components/common/helpers";
import { useCourses, useSearch } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import type { SearchResult } from "@/types";

export default function SearchPage() {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const initialQ = params.get("q") || "";
  const initialMode = (params.get("mode") as string) || "hybrid";
  const initialCourseId = params.get("course_id") ? Number(params.get("course_id")) : undefined;

  const [query, setQuery] = React.useState(initialQ);
  const [mode, setMode] = React.useState(initialMode);
  const [courseFilter, setCourseFilter] = React.useState<number | undefined>(initialCourseId);
  const [submittedQ, setSubmittedQ] = React.useState(initialQ);

  const { data: courses } = useCourses();
  const { data: results, isLoading } = useSearch({
    q: submittedQ,
    courseId: courseFilter,
    mode,
  });

  const submit = (e?: React.FormEvent) => {
    e?.preventDefault();
    setSubmittedQ(query);
    const np = new URLSearchParams();
    np.set("q", query);
    np.set("mode", mode);
    if (courseFilter) np.set("course_id", String(courseFilter));
    setParams(np, { replace: true });
  };

  const onModeChange = (m: string) => {
    setMode(m);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <SearchIcon className="h-6 w-6 text-primary" />
          Search your archive
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Find concepts, snippets, definitions, and topics across all your processed lectures.
        </p>
      </div>

      <form onSubmit={submit} className="space-y-3">
        <div className="flex flex-col md:flex-row gap-2">
          <div className="relative flex-1">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. What is the time complexity of binary search?"
              className="pl-9 h-11"
            />
          </div>
          <Button type="submit" disabled={!query.trim()} className="h-11 px-5">
            Search
          </Button>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <Tabs value={mode} onValueChange={onModeChange} className="w-full sm:w-auto">
            <TabsList className="w-full sm:w-auto">
              <TabsTrigger value="hybrid">Hybrid</TabsTrigger>
              <TabsTrigger value="keyword">Keyword</TabsTrigger>
              <TabsTrigger value="semantic">Semantic</TabsTrigger>
            </TabsList>
          </Tabs>
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <select
              className="text-sm h-9 rounded-md border border-input bg-background px-3 py-1 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={courseFilter ?? ""}
              onChange={(e) =>
                setCourseFilter(e.target.value ? Number(e.target.value) : undefined)
              }
            >
              <option value="">All courses</option>
              {(courses || []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </form>

      {isLoading ? (
        <div className="flex items-center justify-center py-16"><Spinner /></div>
      ) : !submittedQ ? (
        <EmptyState
          icon={SearchIcon}
          title="Start searching"
          description="Try a concept (like 'Big O'), a question ('how does a hash table work?'), or a keyword like 'Dijkstra'."
        />
      ) : !results || results.results.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title={`No results for "${submittedQ}"`}
          description={
            courseFilter
              ? "Try removing the course filter or switching to Hybrid / Semantic mode for broader matches."
              : "Try rephrasing, or switch to Semantic mode for concept-based matches."
          }
        />
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <div>
              <span className="font-medium text-foreground">{results.total}</span> results · mode:{" "}
              <span className="capitalize">{results.search_mode}</span>
            </div>
            <div>Query: <span className="font-medium text-foreground">{results.query}</span></div>
          </div>
          {results.results.map((r, i) => (
            <ResultRow
              key={`${r.document_id}-${i}`}
              result={r}
              rank={i + 1}
              onOpen={() => {
                if (r.lecture_id) nav(`/lectures/${r.lecture_id}`);
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ResultRow({
  result,
  rank,
  onOpen,
}: {
  result: SearchResult;
  rank: number;
  onOpen: () => void;
}) {
  return (
    <Card className="hover:border-primary/30 transition-colors cursor-pointer" onClick={onOpen}>
      <CardContent className="p-5">
        <div className="flex items-start gap-4">
          <div className="shrink-0 text-xs font-medium text-muted-foreground w-6 pt-0.5 text-right">
            {rank}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <TypeBadge type={result.doc_type} />
              <span className="font-semibold truncate min-w-0 flex-1">{result.title}</span>
              <Badge variant="outline" className="font-normal text-[11px] shrink-0 border">
                Relevance {(result.relevance_score * 100).toFixed(0)}%
              </Badge>
            </div>
            <p className={cn(
              "text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap"
            )}>
              {result.snippet}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              {result.lecture_title && (
                <span className="inline-flex items-center gap-1">
                  <BookOpen className="h-3.5 w-3.5" />
                  {result.lecture_title.length > 48
                    ? result.lecture_title.slice(0, 46) + "…"
                    : result.lecture_title}
                </span>
              )}
              {result.source_reference && (
                <span className="inline-flex items-center gap-1">
                  <Hash className="h-3.5 w-3.5" />
                  {result.source_reference}
                </span>
              )}
              <span className="ml-auto inline-flex items-center gap-1 text-primary font-medium">
                Open source
                <ArrowUpRight className="h-3.5 w-3.5" />
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function TypeBadge({ type }: { type: string }) {
  const map: Record<string, { cls: string; label: string }> = {
    topic: { cls: "bg-indigo-500/10 text-indigo-400 border-indigo-500/30", label: "Topic" },
    note: { cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30", label: "Notes" },
    segment: { cls: "bg-sky-500/10 text-sky-400 border-sky-500/30", label: "Transcript" },
    chunk: { cls: "bg-muted text-muted-foreground border-border", label: "Snippet" },
  };
  const s = map[type.toLowerCase()] || {
    cls: "bg-muted text-muted-foreground border-border",
    label: type,
  };
  return (
    <Badge variant="outline" className={cn("border text-[11px]", s.cls)}>
      {s.label}
    </Badge>
  );
}
