import * as React from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft, Upload, BookMarked, Sparkles, Search, MessageCircle, FileQuestion,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState, Spinner } from "@/components/common/helpers";
import {
  useCourse, useCourseTopics, useLectures, useKnowledgeMap, useCourseStats,
} from "@/lib/api/hooks";
import { useAuth } from "@/features/auth/AuthContext";
import { cn, coverageBadge, coverageLabel, formatCoverage, formatDate } from "@/lib/utils";
import KnowledgeMapView from "@/components/charts/KnowledgeMapView";
import TopicTimelineView from "@/components/charts/TopicTimelineView";

export default function CourseDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const courseId = id ? Number(id) : null;
  const { isDemo } = useAuth();

  const { data: course, isLoading: loadingCourse } = useCourse(courseId);
  const { data: stats } = useCourseStats(courseId);
  const { data: lectures } = useLectures(courseId);
  const { data: topics, isLoading: loadingTopics } = useCourseTopics(courseId);
  const { data: kmap } = useKnowledgeMap(courseId);
  const [selectedTopicId, setSelectedTopicId] = React.useState<number | null>(null);

  if (loadingCourse || !course) {
    return <div className="flex items-center justify-center py-24"><Spinner /></div>;
  }

  const topTopics = [...(topics || [])].sort((a, b) => b.coverage_score - a.coverage_score).slice(0, 10);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to="/courses" className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Courses
        </Link>
      </div>

      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="h-14 w-2 rounded-full shrink-0" style={{ background: course.color }} />
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{course.name}</h1>
            {course.description && (
              <p className="text-muted-foreground mt-1 text-sm max-w-2xl">{course.description}</p>
            )}
            {stats && (
              <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                <Badge variant="outline" className="font-normal">{stats.lecture_count} lectures</Badge>
                <Badge variant="outline" className="font-normal">{stats.topic_count} topics</Badge>
                <span>Updated {formatDate(stats.last_updated)}</span>
              </div>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={`/courses/${courseId}/study-guide`}>
            <Button variant="secondary">
              <BookMarked className="h-4 w-4" />
              Study Guide
            </Button>
          </Link>
          <Link to={`/ask/${courseId}`}>
            <Button variant="secondary">
              <MessageCircle className="h-4 w-4" />
              Ask Notes
            </Button>
          </Link>
          <Link to={`/quiz/${courseId}`}>
            <Button variant="outline">
              <FileQuestion className="h-4 w-4" />
              Practice
            </Button>
          </Link>
          <Link to={`/upload`}>
            <Button disabled={isDemo}>
              <Upload className="h-4 w-4" />
              {isDemo ? "Demo — read only" : "Add lecture"}
            </Button>
          </Link>
        </div>
      </div>

      <Tabs defaultValue="lectures" className="w-full">
        <TabsList className="flex gap-1 w-full max-w-xl">
          <TabsTrigger value="lectures">Lectures</TabsTrigger>
          <TabsTrigger value="topics">Topics</TabsTrigger>
          <TabsTrigger value="map">Knowledge map</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
        </TabsList>

        <TabsContent value="lectures" className="mt-5">
          {!lectures || lectures.length === 0 ? (
            <EmptyState
              icon={Upload}
              title="No lectures yet"
              description="Upload PDF, slides, audio or paste a transcript to get structured notes and topics."
              action={!isDemo ? <Link to="/upload"><Button><Upload className="h-4 w-4" />Upload lecture</Button></Link> : null}
            />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {lectures.map((l) => (
                <Link key={l.id} to={`/lectures/${l.id}`}>
                  <Card className="h-full hover:border-primary/40 transition-colors">
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                            {l.lecture_number && (
                              <Badge variant="outline" className="font-normal">L{l.lecture_number}</Badge>
                            )}
                            {l.lecture_date && <span>{formatDate(l.lecture_date)}</span>}
                            <StatusBadge status={l.status} />
                          </div>
                          <div className="font-semibold truncate">{l.title}</div>
                          {l.description && (
                            <p className="mt-1.5 text-sm text-muted-foreground line-clamp-2">{l.description}</p>
                          )}
                          {l.latest_job && l.latest_job.status !== "completed" && (
                            <div className="mt-3">
                              <Progress value={l.latest_job.progress} />
                              <div className="mt-1 text-[11px] text-muted-foreground flex justify-between">
                                <span>{l.latest_job.current_step || "Processing"}</span>
                                <span>{l.latest_job.progress}%</span>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="topics" className="mt-5">
          {loadingTopics || !topics ? (
            <div className="flex py-16 justify-center"><Spinner /></div>
          ) : topics.length === 0 ? (
            <EmptyState
              icon={Sparkles}
              title="No topics yet"
              description="Process lectures to extract and merge recurring concepts across this course."
            />
          ) : (
            <div>
              <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
                {topTopics.map((t) => (
                  <Card
                    key={t.id}
                    className={cn(
                      "cursor-pointer transition-colors",
                      selectedTopicId === t.id && "border-primary ring-2 ring-primary/20"
                    )}
                    onClick={() => setSelectedTopicId(selectedTopicId === t.id ? null : t.id)}
                  >
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between gap-3 mb-3">
                        <div>
                          <div className="font-semibold">{t.canonical_name}</div>
                          {t.description && (
                            <div className="mt-1 text-sm text-muted-foreground line-clamp-2">{t.description}</div>
                          )}
                        </div>
                        <Badge variant="outline" className={cn("shrink-0 border", coverageBadge(t.coverage_score))}>
                          {coverageLabel(t.coverage_score)}
                        </Badge>
                      </div>
                      <Progress value={t.coverage_score * 100} />
                      <div className="mt-2 text-xs text-muted-foreground flex justify-between">
                        <span>{formatCoverage(t.coverage_score)} coverage</span>
                        <span>{t.lecture_count} lectures · {t.evidence_count} pieces of evidence</span>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
              {topTopics.length < topics.length && (
                <div className="mt-4 text-center text-xs text-muted-foreground">
                  Showing top {topTopics.length} of {topics.length} topics
                </div>
              )}
            </div>
          )}
        </TabsContent>

        <TabsContent value="map" className="mt-5">
          {kmap && kmap.nodes.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Semester knowledge map</CardTitle>
                <CardDescription>Node size = coverage · edges = related concepts</CardDescription>
              </CardHeader>
              <CardContent>
                <KnowledgeMapView data={kmap} />
              </CardContent>
            </Card>
          ) : (
            <EmptyState
              icon={Sparkles}
              title="Knowledge map will appear here"
              description="Process at least 2 lectures to see relationships between topics."
            />
          )}
        </TabsContent>

        <TabsContent value="timeline" className="mt-5">
          {topTopics.length > 0 ? (
            <TopicTimelineView topics={topTopics.slice(0, 5)} lectures={lectures || []} />
          ) : (
            <EmptyState
              icon={Sparkles}
              title="Timeline will appear here"
              description="Topics show when each concept was introduced, revisited, and expanded across lectures."
            />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const m: Record<string, any> = {
    processed: { cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30", label: "Processed" },
    pending: { cls: "bg-muted text-muted-foreground border-border", label: "Pending" },
    error: { cls: "bg-rose-500/10 text-rose-400 border-rose-500/30", label: "Error" },
  };
  const s = m[status] || { cls: "bg-muted text-muted-foreground", label: status };
  return <Badge variant="outline" className={cn("font-normal ml-1 border", s.cls)}>{s.label}</Badge>;
}
