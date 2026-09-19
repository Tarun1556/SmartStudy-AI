import * as React from "react";
import { Link, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, BookMarked, Sparkles, Clock, CheckCircle2, Loader2,
  FileText, Lightbulb, GitBranch, MessageSquare, Quote, AlertCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { EmptyState, Spinner } from "@/components/common/helpers";
import {
  useLecture, useLectureNotes, useLectureStatus, useCourseTopics, useRetryLectureProcessing,
} from "@/lib/api/hooks";
import { cn, formatDate, coverageBadge, coverageLabel, formatCoverage } from "@/lib/utils";
import type { Topic } from "@/types";

export default function LectureDetail() {
  const { id } = useParams();
  const lectureId = id ? Number(id) : null;

  const { data: lecture, isLoading: loadingLecture } = useLecture(lectureId);
  const { data: notes, isLoading: loadingNotes } = useLectureNotes(lectureId);
  const liveStatus = useLectureStatus(lectureId);
  const { data: courseTopics } = useCourseTopics(lecture?.course_id || null);
  const retryMut = useRetryLectureProcessing();

  const status = liveStatus.data || lecture?.latest_job;

  // Polling stops once the job finishes, but `lecture`/`notes` were fetched
  // before that — refetch them once so the page leaves the processing view
  // without needing a manual refresh.
  const qc = useQueryClient();
  const prevStatusRef = React.useRef<string | undefined>(undefined);
  React.useEffect(() => {
    const s = liveStatus.data?.status;
    if (s && s !== prevStatusRef.current && (s === "completed" || s === "failed")) {
      qc.invalidateQueries({ queryKey: ["lecture", lectureId] });
      qc.invalidateQueries({ queryKey: ["lecture-notes", lectureId] });
      qc.invalidateQueries({ queryKey: ["topics", lecture?.course_id] });
    }
    prevStatusRef.current = s;
  }, [liveStatus.data?.status, qc, lectureId, lecture?.course_id]);

  if (loadingLecture || !lecture) {
    return <div className="flex items-center justify-center py-24"><Spinner /></div>;
  }

  const isProcessed = lecture.status === "processed";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to={`/courses/${lecture.course_id}`} className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Course
        </Link>
        <span>/</span>
        <span className="truncate text-foreground/80">{lecture.title}</span>
      </div>

      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            {lecture.lecture_number && (
              <Badge variant="outline" className="font-normal">Lecture {lecture.lecture_number}</Badge>
            )}
            {lecture.lecture_date && <Badge variant="outline" className="font-normal">{formatDate(lecture.lecture_date)}</Badge>}
            <LectureStatusBadge status={lecture.status} />
          </div>
          <h1 className="mt-2 text-2xl font-bold tracking-tight">{lecture.title}</h1>
          {lecture.description && (
            <p className="text-muted-foreground mt-1 text-sm max-w-3xl">{lecture.description}</p>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          <Link to={`/courses/${lecture.course_id}/study-guide`}>
            <Button variant="secondary" size="sm">
              <BookMarked className="h-4 w-4" />
              Open course study guide
            </Button>
          </Link>
        </div>
      </div>

      {status && status.status !== "completed" && (
        <Card className="border-sky-500/30 bg-sky-500/10">
          <CardContent className="p-5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 text-sm font-medium text-sky-200">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {status.current_step || "Processing lecture material…"}
                </div>
                <div className="mt-3">
                  <Progress value={status.progress} />
                </div>
                <div className="mt-1 text-xs text-sky-400/80">
                  Step {status.status === "processing" ? "active" : "queued"} · {status.progress}% complete
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {status?.status === "failed" && (
        <Card className="border-rose-500/30 bg-rose-500/10">
          <CardContent className="p-5 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-rose-400 mt-0.5 shrink-0" />
            <div className="flex-1">
              <div className="text-sm font-medium text-rose-300">Processing failed</div>
              <div className="text-sm text-rose-400/80 mt-1">{status.error_message || "Unknown error"}</div>
              {retryMut.isError && (
                <div className="text-xs text-rose-400/80 mt-1">Retry failed to start. Please try again.</div>
              )}
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={retryMut.isPending}
              onClick={() => lectureId && retryMut.mutate(lectureId)}
            >
              {retryMut.isPending && <Spinner className="h-4 w-4" />}
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="notes" className="w-full">
        <TabsList className="w-full max-w-md">
          <TabsTrigger value="notes">Structured notes</TabsTrigger>
          <TabsTrigger value="topics">Topics</TabsTrigger>
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
        </TabsList>

        <TabsContent value="notes" className="mt-5">
          {!isProcessed ? (
            <ProcessingPlaceholder status={status} />
          ) : loadingNotes ? (
            <div className="flex py-16 justify-center"><Spinner /></div>
          ) : notes ? (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 space-y-6">
                {notes.overview && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base flex items-center gap-2">
                        <FileText className="h-4 w-4" />
                        Overview
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm leading-relaxed text-foreground/90">{notes.overview}</p>
                    </CardContent>
                  </Card>
                )}

                {Array.isArray(notes.key_ideas) && notes.key_ideas.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base flex items-center gap-2">
                        <Lightbulb className="h-4 w-4 text-amber-400" />
                        Key ideas
                      </CardTitle>
                      <CardDescription>{notes.key_ideas.length} core ideas extracted</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-3">
                        {notes.key_ideas.map((k: any, i: number) => (
                          <li key={i} className="flex gap-3">
                            <div className="mt-0.5 h-6 w-6 shrink-0 rounded-full bg-indigo-500/10 text-indigo-400 flex items-center justify-center text-xs font-semibold">
                              {i + 1}
                            </div>
                            <div className="text-sm leading-relaxed">
                              {typeof k === "string" ? k : k?.idea || JSON.stringify(k)}
                              {typeof k !== "string" && k?.source_ref && (
                                <SourceTag srcRef={k.source_ref} />
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}

                {Array.isArray(notes.definitions) && notes.definitions.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base flex items-center gap-2">
                        <BookMarked className="h-4 w-4 text-violet-400" />
                        Definitions
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <dl className="divide-y">
                        {notes.definitions.map((d: any, i: number) => (
                          <div key={i} className="py-3">
                            <dt className="font-semibold inline-flex items-center gap-2">
                              {typeof d === "string" ? d : d?.term}
                              {typeof d !== "string" && d?.source_ref && <SourceTag srcRef={d.source_ref} />}
                            </dt>
                            <dd className="mt-1 text-sm text-muted-foreground leading-relaxed">
                              {typeof d === "string" ? "" : d?.definition}
                            </dd>
                          </div>
                        ))}
                      </dl>
                    </CardContent>
                  </Card>
                )}

                {Array.isArray(notes.examples) && notes.examples.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base flex items-center gap-2">
                        <MessageSquare className="h-4 w-4 text-emerald-400" />
                        Examples
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {notes.examples.map((e: any, i: number) => (
                        <div key={i} className="rounded-lg border bg-emerald-500/10 p-4">
                          {typeof e === "string" ? e : (
                            <>
                              <div className="text-xs font-medium text-emerald-400 mb-1">{e?.description || `Example ${i+1}`}</div>
                              <div className="text-sm leading-relaxed">{e?.text || JSON.stringify(e)}</div>
                            </>
                          )}
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {Array.isArray(notes.relationships) && notes.relationships.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base flex items-center gap-2">
                        <GitBranch className="h-4 w-4 text-fuchsia-400" />
                        Important relationships
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-2 text-sm">
                        {notes.relationships.map((r: any, i: number) => (
                          <li key={i} className="flex items-center gap-2">
                            <Badge variant="secondary" className="font-medium">{r?.from || r?.a || "Concept"}</Badge>
                            <span className="text-xs text-muted-foreground">{r?.relation || "→"}</span>
                            <Badge variant="secondary" className="font-medium">{r?.to || r?.b || "Concept"}</Badge>
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}
              </div>

              <aside className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      Topics in this lecture
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {courseTopics && courseTopics.length > 0 ? (
                      <ul className="space-y-2">
                        {courseTopics.slice(0, 15).map((t) => (
                          <li key={t.id}>
                            <Link to={`/courses/${lecture.course_id}/study-guide`} className="block rounded-lg border p-3 hover:border-primary/40 transition-colors">
                              <div className="flex items-center justify-between gap-2">
                                <div className="font-medium text-sm truncate">{t.canonical_name}</div>
                                <Badge variant="outline" className={cn("border text-[10px]", coverageBadge(t.coverage_score))}>
                                  {coverageLabel(t.coverage_score)}
                                </Badge>
                              </div>
                              <div className="mt-1.5">
                                <Progress value={t.coverage_score * 100} />
                              </div>
                              <div className="mt-1 text-[11px] text-muted-foreground flex justify-between">
                                <span>{formatCoverage(t.coverage_score)}</span>
                                <span>{t.lecture_count} lectures</span>
                              </div>
                            </Link>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className="text-xs text-muted-foreground">Topics are being merged across the course.</div>
                    )}
                  </CardContent>
                </Card>
              </aside>
            </div>
          ) : (
            <EmptyState title="Notes not ready yet" description="Wait for processing to complete or try reprocessing the lecture." />
          )}
        </TabsContent>

        <TabsContent value="topics" className="mt-5">
          {courseTopics && courseTopics.length > 0 ? (
            <TopicGrid topics={courseTopics.slice(0, 20)} />
          ) : (
            <EmptyState icon={Sparkles} title="Topics will appear here" description="Once processing is complete, extracted topics are merged across the course." />
          )}
        </TabsContent>

        <TabsContent value="evidence" className="mt-5">
          {notes?.source_references && Array.isArray(notes.source_references) && notes.source_references.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Quote className="h-4 w-4" />
                  Source references used
                </CardTitle>
                <CardDescription>Every claim links to the exact source snippet</CardDescription>
              </CardHeader>
              <CardContent className="divide-y">
                {notes.source_references.map((r: any, i: number) => (
                  <div key={i} className="py-3">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1.5">
                      <Badge variant="outline" className="font-normal">Segment {r.segment_index ?? i}</Badge>
                      <span>·</span>
                      <span>{r.source_type || "text"}</span>
                      {typeof r.start_time === "number" && (
                        <>
                          <span>·</span>
                          <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" />{formatTime(r.start_time)}</span>
                        </>
                      )}
                    </div>
                    <div className="text-sm leading-relaxed text-foreground/90 border-l-2 border-primary/20 pl-3">
                      {r.snippet || r.text || JSON.stringify(r)}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : (
            <EmptyState icon={Quote} title="Source evidence" description="Notes link every claim to the exact segment that supports it." />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ProcessingPlaceholder({ status }: { status: any }) {
  const steps = [
    { key: "Validat", label: "Validating inputs" },
    { key: "Extract", label: "Extracting text" },
    { key: "Transcri", label: "Transcribing (if audio/video)" },
    { key: "Structured notes", label: "Generating structured notes" },
    { key: "topics", label: "Extracting & merging topics" },
    { key: "search", label: "Indexing for search" },
    { key: "study", label: "Updating course study guide" },
    { key: "Done", label: "Complete" },
  ];
  const progress = status?.progress || 0;
  const step = Math.min(steps.length - 1, Math.floor(progress / 12));
  return (
    <Card>
      <CardContent className="p-6 space-y-5">
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <div className="font-medium">{status?.current_step || "Analyzing lecture…"}</div>
        </div>
        <Progress value={progress} />
        <ol className="grid gap-2">
          {steps.map((s, i) => (
            <li key={s.key} className="flex items-center gap-3 text-sm">
              {i < step ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              ) : i === step ? (
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
              ) : (
                <div className="h-4 w-4 rounded-full border-2 border-muted" />
              )}
              <span className={cn(i <= step ? "text-foreground" : "text-muted-foreground")}>{s.label}</span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

function TopicGrid({ topics }: { topics: Topic[] }) {
  return (
    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
      {topics.map((t) => (
        <Card key={t.id}>
          <CardContent className="p-5">
            <div className="flex items-start justify-between gap-2 mb-2">
              <div className="font-semibold">{t.canonical_name}</div>
              <Badge variant="outline" className={cn("border", coverageBadge(t.coverage_score))}>
                {coverageLabel(t.coverage_score)}
              </Badge>
            </div>
            {t.description && <p className="text-sm text-muted-foreground line-clamp-2">{t.description}</p>}
            <Separator className="my-3" />
            <Progress value={t.coverage_score * 100} />
            <div className="mt-2 text-xs text-muted-foreground flex justify-between">
              <span>{formatCoverage(t.coverage_score)} coverage</span>
              <span>{t.lecture_count} lectures · {t.evidence_count} evidence</span>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function SourceTag({ srcRef }: { srcRef: string }) {
  return (
    <span className="ml-2 inline-flex items-center text-[10px] rounded bg-muted px-1.5 py-0.5 text-muted-foreground">
      src: {srcRef}
    </span>
  );
}

function LectureStatusBadge({ status }: { status: string }) {
  const map: Record<string, any> = {
    processed: { cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30", label: "Processed", icon: CheckCircle2 },
    pending: { cls: "bg-muted text-muted-foreground border-border", label: "Pending", icon: Clock },
    error: { cls: "bg-rose-500/10 text-rose-400 border-rose-500/30", label: "Error", icon: AlertCircle },
  };
  const s = map[status] || { cls: "bg-sky-500/10 text-sky-400 border-sky-500/30", label: status, icon: Loader2 };
  const Icon = s.icon;
  return (
    <Badge variant="outline" className={cn("border", s.cls)}>
      <Icon className={cn("h-3 w-3 mr-1", (status === "pending" || !map[status]) && "animate-spin")} />
      {s.label}
    </Badge>
  );
}

function formatTime(s: number) {
  if (s == null) return "";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}
