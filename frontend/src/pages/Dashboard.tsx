import * as React from "react";
import { Link } from "react-router-dom";
import {
  BookOpen, Lightbulb, Upload, Search, Sparkles, Clock,
  CheckCircle2, AlertCircle, Loader2,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { EmptyState, Spinner } from "@/components/common/helpers";
import { useDashboard } from "@/lib/api/hooks";
import { cn, coverageBadge, coverageLabel, formatCoverage } from "@/lib/utils";
import type { ProcessingJob, Topic } from "@/types";

function JobStatusBadge({ job }: { job: ProcessingJob }) {
  const map: Record<string, { cls: string; label: string; icon: any }> = {
    queued: { cls: "bg-muted text-muted-foreground border-border", label: "Queued", icon: Clock },
    processing: { cls: "bg-sky-500/10 text-sky-400 border-sky-500/30", label: "Processing", icon: Loader2 },
    completed: { cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30", label: "Complete", icon: CheckCircle2 },
    failed: { cls: "bg-rose-500/10 text-rose-400 border-rose-500/30", label: "Failed", icon: AlertCircle },
  };
  const s = map[job.status] || map.queued;
  const Icon = s.icon;
  return (
    <Badge className={cn(s.cls, "border")}>
      <Icon className={cn("h-3 w-3 mr-1", job.status === "processing" && "animate-spin")} />
      {s.label}
    </Badge>
  );
}

export default function Dashboard() {
  const { data, isLoading } = useDashboard();

  if (isLoading || !data) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="h-8 w-8 text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Overview of your workspace and processing activity
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/upload">
            <Button>
              <Upload className="h-4 w-4" />
              Upload lecture
            </Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Courses", value: data.total_courses, icon: BookOpen, tint: "bg-indigo-500/10 text-indigo-400" },
          { label: "Lectures", value: data.total_lectures, icon: Lightbulb, tint: "bg-violet-500/10 text-violet-400" },
          { label: "Topics found", value: data.total_topics, icon: Sparkles, tint: "bg-fuchsia-500/10 text-fuchsia-400" },
          { label: "Active jobs", value: data.processing_jobs, icon: Loader2, tint: "bg-sky-500/10 text-sky-400" },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="p-5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs font-medium text-muted-foreground">{s.label}</div>
                  <div className="mt-2 text-3xl font-bold tracking-tight">{s.value}</div>
                </div>
                <div className={cn("h-9 w-9 rounded-lg flex items-center justify-center", s.tint)}>
                  <s.icon className="h-4.5 w-4.5" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base">Frequently covered topics</CardTitle>
              <CardDescription>Ranked by cross-lecture recurrence</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {data.frequently_covered.length === 0 ? (
              <EmptyState
                icon={Sparkles}
                title="No topics yet"
                description="Upload and process a lecture to begin extracting recurring concepts."
                action={<Link to="/upload"><Button size="sm">Upload lecture</Button></Link>}
              />
            ) : (
              <ul className="divide-y">
                {data.frequently_covered.map((t: Topic) => (
                  <li key={t.id} className="py-3 flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Link to={`/courses/${t.course_id}/study-guide`} className="font-medium hover:underline truncate">
                          {t.canonical_name}
                        </Link>
                        <Badge variant="outline" className={cn("border shrink-0", coverageBadge(t.coverage_score))}>
                          {coverageLabel(t.coverage_score)}
                        </Badge>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {t.lecture_count} lecture{t.lecture_count === 1 ? "" : "s"} · {t.evidence_count} evidence pieces
                      </div>
                    </div>
                    <div className="w-32 shrink-0">
                      <div className="flex items-center justify-between text-xs mb-1 text-muted-foreground">
                        <span>Coverage</span>
                        <span className="font-medium text-foreground">{formatCoverage(t.coverage_score)}</span>
                      </div>
                      <Progress value={t.coverage_score * 100} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent processing</CardTitle>
            <CardDescription>Lecture processing jobs</CardDescription>
          </CardHeader>
          <CardContent>
            {data.recent_jobs.length === 0 ? (
              <EmptyState
                icon={Clock}
                title="No jobs yet"
                description="Your first upload will appear here with live progress."
              />
            ) : (
              <ul className="space-y-3">
                {data.recent_jobs.slice(0, 8).map((j) => (
                  <li key={j.id} className="rounded-lg border p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <Link to={`/lectures/${j.lecture_id}`} className="text-sm font-medium hover:underline truncate block">
                          Job #{j.id}
                        </Link>
                        <div className="mt-0.5 text-xs text-muted-foreground truncate">
                          {j.current_step || "Waiting…"}
                        </div>
                      </div>
                      <JobStatusBadge job={j} />
                    </div>
                    <div className="mt-3">
                      <Progress value={j.progress} />
                      <div className="mt-1 text-[11px] text-muted-foreground text-right">{j.progress}%</div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base">Your courses</CardTitle>
            <CardDescription>Jump into a course to view its study guide</CardDescription>
          </div>
          <Link to="/courses">
            <Button variant="outline" size="sm">All courses</Button>
          </Link>
        </CardHeader>
        <CardContent>
          {data.course_stats.length === 0 ? (
            <EmptyState
              icon={BookOpen}
              title="No courses yet"
              description="Create a course, then upload lectures to start building your study guide."
              action={<Link to="/courses"><Button size="sm">Create course</Button></Link>}
            />
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.course_stats.map((c) => (
                <Link key={c.id} to={`/courses/${c.id}`}>
                  <Card className="h-full border hover:border-primary/40 transition-colors">
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between">
                        <div className="h-10 w-1.5 rounded-full" style={{ background: c.color || "#4f46e5" }} />
                        <div className="flex-1 ml-3 min-w-0">
                          <div className="font-semibold truncate">{c.name}</div>
                          <div className="mt-0.5 text-xs text-muted-foreground flex gap-3">
                            <span>{c.lecture_count} lectures</span>
                            <span>·</span>
                            <span>{c.topic_count} topics</span>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
