import * as React from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, TrendingUp, Sparkles, FileQuestion } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState, Spinner } from "@/components/common/helpers";
import { useCourse, useExamInsights } from "@/lib/api/hooks";
import { cn, formatCoverage, priorityBadge, priorityLabel, trendIcon } from "@/lib/utils";
import type { ExamTopicInsight } from "@/types";

export default function ExamInsightsPage() {
  const { id } = useParams();
  const courseId = id ? Number(id) : null;

  const { data: course, isLoading: loadingCourse } = useCourse(courseId);
  const { data: insights, isLoading: loadingInsights } = useExamInsights(courseId);
  const [whyTopic, setWhyTopic] = React.useState<ExamTopicInsight | null>(null);

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

      <div className="flex items-start gap-4">
        <div className="h-14 w-2 rounded-full shrink-0" style={{ background: course.color }} />
        <div>
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">Exam Insights</h1>
          </div>
          <p className="text-muted-foreground mt-1 text-sm max-w-2xl">
            Evidence-based historical patterns from your uploaded question papers, combined with
            lecture coverage. Factual counts, not predictions.
          </p>
        </div>
      </div>

      {loadingInsights ? (
        <div className="flex items-center justify-center py-20"><Spinner /></div>
      ) : !insights || !insights.has_historical_patterns ? (
        <EmptyState
          icon={FileQuestion}
          title="No historical patterns yet"
          description="Upload at least one previous question paper to see which topics have historically been asked most often."
          action={
            <Link to={`/courses/${courseId}/question-papers`}>
              <Button>Upload Question Paper</Button>
            </Link>
          }
        />
      ) : (
        <>
          <Card className="bg-gradient-to-br from-primary/10 via-card to-neon-cyan/5 border-primary/20">
            <CardContent className="pt-6">
              <div className="grid md:grid-cols-3 gap-5">
                <div>
                  <div className="text-xs uppercase tracking-wider text-muted-foreground">Papers analyzed</div>
                  <div className="mt-1 text-2xl font-semibold">{insights.papers_analyzed}</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wider text-muted-foreground">Topics identified</div>
                  <div className="mt-1 text-2xl font-semibold">{insights.topics_identified}</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wider text-muted-foreground">High priority topics</div>
                  <div className="mt-1 text-2xl font-semibold text-rose-400">
                    {insights.topics.filter((t) => t.priority_label === "high").length}
                  </div>
                </div>
              </div>
              <Separator className="my-5" />
              <p className="text-sm text-muted-foreground leading-relaxed">
                <Sparkles className="h-4 w-4 inline -mt-0.5 mr-1 text-amber-500" />
                Priority combines lecture coverage, how many of your {insights.papers_analyzed} analyzed papers
                a topic appeared in, how many academic years it recurred across, its recent trend, and marks
                weightage. This describes what has historically been asked — it is not a prediction of your
                next exam.
              </p>
            </CardContent>
          </Card>

          <div className="space-y-4">
            {insights.topics.map((t) => (
              <TopicInsightCard key={t.topic_id} insight={t} onWhy={() => setWhyTopic(t)} />
            ))}
          </div>
        </>
      )}

      <WhyDialog insight={whyTopic} onClose={() => setWhyTopic(null)} />
    </div>
  );
}

function TopicInsightCard({ insight, onWhy }: { insight: ExamTopicInsight; onWhy: () => void }) {
  const freqPct = Math.round(insight.frequency_score * 100);
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex flex-col md:flex-row md:items-start gap-5">
          <div className="md:w-32 shrink-0">
            <Badge variant="outline" className={cn("border", priorityBadge(insight.priority_label))}>
              {priorityLabel(insight.priority_label)}
            </Badge>
            <div className="mt-2 text-xs text-muted-foreground flex items-center gap-1">
              <span className="text-sm">{trendIcon(insight.recent_trend)}</span>
              <span className="capitalize">{insight.recent_trend.replace("_", " ")}</span>
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold tracking-tight">{insight.topic_name}</h3>
            <div className="mt-2">
              <Progress value={freqPct} />
              <div className="mt-1.5 flex flex-wrap justify-between gap-3 text-xs text-muted-foreground">
                <span>Appeared in {insight.papers_appeared_in} of {insight.total_papers_analyzed} analyzed papers ({freqPct}%)</span>
                <span>Lecture coverage {formatCoverage(insight.lecture_coverage)}</span>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span>{insight.years_appeared_in} academic year(s) observed</span>
              <span>{insight.question_count} question(s) identified</span>
              {insight.avg_marks != null && <span>~{insight.avg_marks} marks avg.</span>}
            </div>
            <div className="mt-4">
              <Button size="sm" variant="secondary" onClick={onWhy}>Why this topic matters</Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function WhyDialog({ insight, onClose }: { insight: ExamTopicInsight | null; onClose: () => void }) {
  if (!insight) return null;
  return (
    <Dialog open={!!insight} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Why {insight.topic_name} matters</DialogTitle>
          <DialogDescription>Every point below traces back to a stored count — nothing here is a guess.</DialogDescription>
        </DialogHeader>
        <ul className="space-y-2 text-sm">
          <li>• Appeared in {insight.papers_appeared_in} of {insight.total_papers_analyzed} previous papers</li>
          <li>• Covered in lectures at {formatCoverage(insight.lecture_coverage)} coverage</li>
          <li>• Appeared across {insight.years_appeared_in} of {insight.total_years_analyzed} analyzed academic year(s)</li>
          <li>• {insight.question_count} total question(s) identified for this topic</li>
          {insight.total_marks != null && <li>• {insight.total_marks} total marks associated across analyzed papers</li>}
          <li>• Recent trend: <span className="capitalize">{insight.recent_trend.replace("_", " ")}</span></li>
        </ul>
        {insight.evidence.papers.length > 0 && (
          <div className="pt-2">
            <div className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">Appeared in</div>
            <div className="flex flex-wrap gap-1.5">
              {insight.evidence.papers.map((p) => (
                <Badge key={p.id} variant="outline" className="font-normal">
                  {p.title}{p.academic_year ? ` (${p.academic_year})` : ""}
                </Badge>
              ))}
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
