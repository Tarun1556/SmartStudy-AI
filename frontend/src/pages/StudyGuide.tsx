import * as React from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft, Download, RefreshCw, BookMarked, Sparkles, FileText, Lightbulb,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { EmptyState, Spinner } from "@/components/common/helpers";
import {
  useCourse, useStudyGuide, useRegenerateStudyGuide,
} from "@/lib/api/hooks";
import { useAuth } from "@/features/auth/AuthContext";
import api from "@/lib/api/client";
import {
  cn, coverageBadge, coverageLabel, formatCoverage, formatDate,
} from "@/lib/utils";
import type { StudyGuideTopic } from "@/types";

export default function StudyGuidePage() {
  const { id } = useParams();
  const courseId = id ? Number(id) : null;
  const { isDemo } = useAuth();

  const { data: course, isLoading: loadingCourse } = useCourse(courseId);
  const { data: guide, isLoading: loadingGuide, refetch } = useStudyGuide(courseId);
  const regenerate = useRegenerateStudyGuide();
  const [downloading, setDownloading] = React.useState(false);

  const downloadPdf = async () => {
    if (!courseId) return;
    setDownloading(true);
    try {
      const res = await api.get(`/api/courses/${courseId}/study-guide/pdf`, {
        responseType: "blob",
      });
      const blob = new Blob([res.data], { type: "application/pdf" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const safe = (course?.name || "study-guide").replace(/[^\w\s-]/g, "").slice(0, 60);
      a.download = `${safe}-study-guide.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  if (loadingCourse || !course) {
    return <div className="flex items-center justify-center py-24"><Spinner /></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to={`/courses/${courseId}`} className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          {course.name}
        </Link>
      </div>

      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="h-14 w-2 rounded-full shrink-0" style={{ background: course.color }} />
          <div>
            <div className="flex items-center gap-2">
              <BookMarked className="h-5 w-5 text-primary" />
              <h1 className="text-2xl font-bold tracking-tight">Study Guide</h1>
            </div>
            <p className="text-muted-foreground mt-1 text-sm max-w-2xl">
              Your evidence-backed semester overview. Priority topics are ranked by coverage
              across lectures, not guesses.
            </p>
            {guide && (
              <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                <Badge variant="outline" className="font-normal">v{guide.version}</Badge>
                <span>Generated {formatDate(guide.generated_at)}</span>
                {guide.top_topics && (
                  <Badge variant="outline" className="font-normal">
                    {guide.top_topics.length} focus topics
                  </Badge>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={() => regenerate.mutateAsync(courseId!).then(() => refetch())}
            disabled={isDemo || regenerate.isPending || !courseId}
          >
            <RefreshCw className={cn("h-4 w-4", regenerate.isPending && "animate-spin")} />
            {isDemo ? "Demo — read only" : "Regenerate"}
          </Button>
          <Button
            variant="outline"
            onClick={downloadPdf}
            disabled={downloading || !guide}
          >
            <Download className="h-4 w-4" />
            {downloading ? "Preparing…" : "Export PDF"}
          </Button>
        </div>
      </div>

      {loadingGuide ? (
        <div className="flex items-center justify-center py-20"><Spinner /></div>
      ) : !guide || !guide.top_topics || guide.top_topics.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="Study guide not ready yet"
          description="Process your first lecture to generate an initial guide. It updates automatically as you add more material."
          action={
            !isDemo ? (
              <Link to="/upload">
                <Button><FileText className="h-4 w-4" />Upload lecture</Button>
              </Link>
            ) : null
          }
        />
      ) : (
        <>
          <OverviewSummary guide={guide} />

          <div className="space-y-4">
            {guide.top_topics.map((t, i) => (
              <TopicCard key={t.topic_id} rank={i + 1} topic={t} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function OverviewSummary({ guide }: { guide: NonNullable<ReturnType<typeof useStudyGuide>["data"]> }) {
  const total = guide.top_topics?.length ?? 0;
  const high = guide.top_topics?.filter((t) => t.coverage_score >= 0.7).length ?? 0;
  const mid = guide.top_topics?.filter((t) => t.coverage_score >= 0.4 && t.coverage_score < 0.7).length ?? 0;
  return (
    <Card className="bg-gradient-to-br from-primary/10 via-card to-neon-cyan/5 border-primary/20">
      <CardContent className="pt-6">
        <div className="grid md:grid-cols-4 gap-5">
          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Version</div>
            <div className="mt-1 text-2xl font-semibold">v{guide.version}</div>
            <div className="text-xs text-muted-foreground mt-1">{formatDate(guide.generated_at)}</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Focus topics</div>
            <div className="mt-1 text-2xl font-semibold">{total}</div>
            <div className="text-xs text-muted-foreground mt-1">Ranked by evidence coverage</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground">High coverage</div>
            <div className="mt-1 text-2xl font-semibold text-indigo-400">{high}</div>
            <div className="text-xs text-muted-foreground mt-1">Revisited across many lectures</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Medium coverage</div>
            <div className="mt-1 text-2xl font-semibold text-sky-400">{mid}</div>
            <div className="text-xs text-muted-foreground mt-1">Worth reviewing, not top priority</div>
          </div>
        </div>
        <Separator className="my-5" />
        <p className="text-sm text-muted-foreground leading-relaxed">
          <Lightbulb className="h-4 w-4 inline -mt-0.5 mr-1 text-amber-500" />
          This guide is automatically ranked by how often each topic appears, how much evidence
          backs it, and how many source types reference it — never by speculative predictions.
        </p>
      </CardContent>
    </Card>
  );
}

function TopicCard({ rank, topic }: { rank: number; topic: StudyGuideTopic }) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex flex-col md:flex-row md:items-start gap-5">
          <div className="md:w-24 shrink-0">
            <div className="flex items-center gap-3 md:flex-col md:items-start md:gap-2">
              <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center font-semibold">
                #{rank}
              </div>
              <Badge variant="outline" className={cn("border", coverageBadge(topic.coverage_score))}>
                {coverageLabel(topic.coverage_score)}
              </Badge>
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <h3 className="text-lg font-semibold tracking-tight">{topic.name}</h3>
            </div>
            <div className="mt-2">
              <Progress value={topic.coverage_score * 100} />
              <div className="mt-1.5 flex flex-wrap justify-between gap-3 text-xs text-muted-foreground">
                <span>{formatCoverage(topic.coverage_score)} coverage</span>
                <span>{topic.lecture_count} lectures · {topic.evidence_count} evidence snippets</span>
              </div>
            </div>
            {topic.summary && (
              <p className="mt-4 text-sm leading-relaxed text-muted-foreground">{topic.summary}</p>
            )}
            <div className="mt-4">
              <div className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">
                Where this appears
              </div>
              <div className="flex flex-wrap gap-1.5">
                {topic.lectures.map((l) => (
                  <Link
                    key={l.id}
                    to={`/lectures/${l.id}`}
                    className="text-xs inline-flex items-center rounded-md border border-border bg-muted px-2 py-1 hover:bg-muted"
                  >
                    {l.title.length > 28 ? l.title.slice(0, 26) + "…" : l.title}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
