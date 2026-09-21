import * as React from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft, Upload as UploadIcon, FileText, Download, Trash2, Eye, RefreshCw, CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState, Spinner, InputError } from "@/components/common/helpers";
import {
  useCourse, useQuestionPapers, useUploadQuestionPaper, useQuestionPaperStatus,
  useDeleteQuestionPaper, useQuestionPaperQuestions, useRetryQuestionPaperProcessing,
} from "@/lib/api/hooks";
import { useAuth } from "@/features/auth/AuthContext";
import api from "@/lib/api/client";
import { cn, formatDate } from "@/lib/utils";
import type { QuestionPaper } from "@/types";

export default function QuestionPapersPage() {
  const { id } = useParams();
  const courseId = id ? Number(id) : null;
  const { isDemo } = useAuth();

  const { data: course, isLoading: loadingCourse } = useCourse(courseId);
  const { data: list, isLoading: loadingList, refetch } = useQuestionPapers(courseId);
  const uploadMut = useUploadQuestionPaper();

  const [title, setTitle] = React.useState("");
  const [academicYear, setAcademicYear] = React.useState("");
  const [semester, setSemester] = React.useState("");
  const [examType, setExamType] = React.useState("");
  const [file, setFile] = React.useState<File | null>(null);
  const [dragOver, setDragOver] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);
  const [created, setCreated] = React.useState<{ question_paper_id: number; job_id: number } | null>(null);
  const [viewingId, setViewingId] = React.useState<number | null>(null);
  const [deletingId, setDeletingId] = React.useState<number | null>(null);

  const { data: jobStatus } = useQuestionPaperStatus(created?.question_paper_id ?? null, 1500);

  React.useEffect(() => {
    if (jobStatus?.status === "completed" || jobStatus?.status === "failed") {
      refetch();
    }
  }, [jobStatus?.status, refetch]);

  if (loadingCourse || !course) {
    return <div className="flex items-center justify-center py-24"><Spinner /></div>;
  }

  const onFileDrop = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const f = files[0];
    const ext = f.name.split(".").pop()?.toLowerCase() || "";
    if (ext !== "pdf") {
      setErr("Only PDF question papers are supported.");
      return;
    }
    setErr(null);
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.pdf$/i, ""));
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (!file) {
      setErr("Choose a PDF question paper to upload.");
      return;
    }
    if (!title.trim()) {
      setErr("Give this question paper a title (e.g. \"2025 Semester End Examination\").");
      return;
    }
    try {
      const fd = new FormData();
      fd.append("title", title.trim());
      if (academicYear) fd.append("academic_year", academicYear);
      if (semester) fd.append("semester", semester);
      if (examType) fd.append("exam_type", examType);
      fd.append("file", file);
      const r = await uploadMut.mutateAsync({ courseId: courseId!, form: fd });
      setCreated({ question_paper_id: r.question_paper_id, job_id: r.job_id });
      setTitle("");
      setAcademicYear("");
      setSemester("");
      setExamType("");
      setFile(null);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || "Upload failed");
    }
  };

  const papers = list?.papers ?? [];

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
          <h1 className="text-2xl font-bold tracking-tight">Previous Question Papers</h1>
          <p className="text-muted-foreground mt-1 text-sm max-w-2xl">
            Upload previous semester question papers to discover recurring exam topics and patterns
            alongside your lecture coverage.
          </p>
          {list && (
            <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <Badge variant="outline" className="font-normal">Analyzed: {list.papers_analyzed} question papers</Badge>
              <Badge variant="outline" className="font-normal">Topics identified: {list.topics_identified}</Badge>
              {list.papers_analyzed > 0 && (
                <span className="inline-flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />Historical patterns available</span>
              )}
            </div>
          )}
        </div>
      </div>

      {!isDemo && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Upload Question Paper</CardTitle>
            <CardDescription>PDF only. The original file is preserved and can always be downloaded.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="grid md:grid-cols-4 gap-4">
                <div className="md:col-span-2">
                  <Label>Title</Label>
                  <Input
                    className="mt-1.5"
                    placeholder="2025 Semester End Examination"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </div>
                <div>
                  <Label>Academic year</Label>
                  <Input
                    className="mt-1.5"
                    type="number"
                    placeholder="2025"
                    value={academicYear}
                    onChange={(e) => setAcademicYear(e.target.value)}
                  />
                </div>
                <div>
                  <Label>Semester</Label>
                  <Input
                    className="mt-1.5"
                    placeholder="Semester 1"
                    value={semester}
                    onChange={(e) => setSemester(e.target.value)}
                  />
                </div>
              </div>
              <div className="md:w-1/3">
                <Label>Exam type (optional)</Label>
                <Input
                  className="mt-1.5"
                  placeholder="Final / Midterm / Quiz"
                  value={examType}
                  onChange={(e) => setExamType(e.target.value)}
                />
              </div>

              <div
                className={cn(
                  "rounded-xl border-2 border-dashed p-8 text-center transition-colors cursor-pointer",
                  dragOver
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-primary/60 hover:bg-muted/30"
                )}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => { e.preventDefault(); setDragOver(false); onFileDrop(e.dataTransfer.files); }}
                onClick={() => (document.getElementById("qp-file-picker") as HTMLInputElement)?.click()}
              >
                <input
                  id="qp-file-picker"
                  type="file"
                  className="hidden"
                  accept=".pdf"
                  onChange={(e) => onFileDrop(e.target.files)}
                />
                {!file ? (
                  <div className="pointer-events-none">
                    <div className="mx-auto h-12 w-12 rounded-full bg-muted flex items-center justify-center text-muted-foreground mb-3">
                      <UploadIcon className="h-5 w-5" />
                    </div>
                    <div className="text-sm font-medium">Drop a PDF here, or click to browse</div>
                    <div className="text-xs text-muted-foreground mt-1">Supported: PDF</div>
                  </div>
                ) : (
                  <div className="flex items-center justify-center gap-3 pointer-events-none">
                    <div className="h-12 w-12 rounded-lg bg-primary/10 text-primary border border-primary/20 flex items-center justify-center">
                      <FileText className="h-5 w-5" />
                    </div>
                    <div className="text-left">
                      <div className="font-medium">{file.name}</div>
                      <div className="text-xs text-muted-foreground">{(file.size / 1024 / 1024).toFixed(2)} MB</div>
                    </div>
                    <Badge variant="success" className="ml-4"><CheckCircle2 className="h-3 w-3 mr-1" />Attached</Badge>
                  </div>
                )}
              </div>

              <InputError>{err}</InputError>

              <div className="flex justify-end">
                <Button type="submit" disabled={uploadMut.isPending}>
                  {uploadMut.isPending && <Spinner className="h-4 w-4" />}
                  <UploadIcon className="h-4 w-4" />
                  Upload Question Paper
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {loadingList ? (
        <div className="flex items-center justify-center py-20"><Spinner /></div>
      ) : papers.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No previous question papers uploaded yet"
          description="Upload previous semester question papers to discover recurring exam topics and patterns."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {papers.map((p) => (
            <PaperCard
              key={p.id}
              paper={p}
              isDemo={isDemo}
              onView={() => setViewingId(p.id)}
              onDeleteRequested={() => setDeletingId(p.id)}
            />
          ))}
        </div>
      )}

      <Dialog open={!!created} onOpenChange={(v) => !v && setCreated(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Processing started</DialogTitle>
            <DialogDescription>
              Extracting questions, mapping them to your course topics, and analyzing patterns.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <div className="flex justify-between text-sm mb-1.5">
                <span className="text-muted-foreground">{jobStatus?.current_step || "Awaiting processing…"}</span>
                <span className="font-medium">{jobStatus?.progress ?? 0}%</span>
              </div>
              <Progress value={jobStatus?.progress ?? 0} />
            </div>
            {jobStatus?.status === "failed" && (
              <InputError>{jobStatus.error_message || "Processing failed."}</InputError>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreated(null)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <QuestionsDialog paperId={viewingId} onClose={() => setViewingId(null)} />
      <DeleteDialog
        paperId={deletingId}
        courseId={courseId}
        onClose={() => setDeletingId(null)}
      />
    </div>
  );
}

function PaperCard({
  paper, isDemo, onView, onDeleteRequested,
}: {
  paper: QuestionPaper;
  isDemo: boolean;
  onView: () => void;
  onDeleteRequested: () => void;
}) {
  const retryMut = useRetryQuestionPaperProcessing();
  const [downloading, setDownloading] = React.useState(false);

  const download = async () => {
    setDownloading(true);
    try {
      const res = await api.get(`/api/question-papers/${paper.id}/download`, { responseType: "blob" });
      const blob = new Blob([res.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = paper.original_filename || "question-paper.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  const job = paper.latest_job;
  const inProgress = job && (job.status === "queued" || job.status === "processing");

  return (
    <Card className="h-full">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground mb-1">
              {paper.academic_year && <Badge variant="outline" className="font-normal">{paper.academic_year}</Badge>}
              {paper.semester && <Badge variant="outline" className="font-normal">{paper.semester}</Badge>}
              {paper.exam_type && <Badge variant="outline" className="font-normal">{paper.exam_type}</Badge>}
              <PaperStatusBadge status={paper.status} />
            </div>
            <div className="font-semibold truncate">{paper.title}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              PDF · Uploaded {formatDate(paper.created_at)}
              {paper.status === "processed" && ` · ${paper.question_count} questions identified`}
            </div>
            {inProgress && (
              <div className="mt-3">
                <Progress value={job!.progress} />
                <div className="mt-1 text-[11px] text-muted-foreground flex justify-between">
                  <span>{job!.current_step || "Processing"}</span>
                  <span>{job!.progress}%</span>
                </div>
              </div>
            )}
            {paper.status === "error" && job?.error_message && (
              <p className="mt-2 text-xs text-rose-400">{job.error_message}</p>
            )}
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={onView} disabled={paper.status !== "processed"}>
            <Eye className="h-3.5 w-3.5" />
            View
          </Button>
          <Button size="sm" variant="outline" onClick={download} disabled={downloading}>
            <Download className="h-3.5 w-3.5" />
            {downloading ? "Preparing…" : "Download"}
          </Button>
          {paper.status === "error" && !isDemo && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => retryMut.mutate(paper.id)}
              disabled={retryMut.isPending}
            >
              <RefreshCw className={cn("h-3.5 w-3.5", retryMut.isPending && "animate-spin")} />
              Retry
            </Button>
          )}
          {!isDemo && (
            <Button size="sm" variant="ghost" className="text-rose-400 hover:text-rose-400" onClick={onDeleteRequested}>
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function PaperStatusBadge({ status }: { status: string }) {
  const m: Record<string, any> = {
    processed: { cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30", label: "Processed" },
    pending: { cls: "bg-muted text-muted-foreground border-border", label: "Pending" },
    processing: { cls: "bg-sky-500/10 text-sky-400 border-sky-500/30", label: "Processing" },
    error: { cls: "bg-rose-500/10 text-rose-400 border-rose-500/30", label: "Error" },
  };
  const s = m[status] || { cls: "bg-muted text-muted-foreground", label: status };
  return <Badge variant="outline" className={cn("font-normal border", s.cls)}>{s.label}</Badge>;
}

function QuestionsDialog({ paperId, onClose }: { paperId: number | null; onClose: () => void }) {
  const { data: questions, isLoading } = useQuestionPaperQuestions(paperId);
  return (
    <Dialog open={!!paperId} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Identified Questions</DialogTitle>
          <DialogDescription>Extracted from the original PDF and mapped to course topics where confident.</DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <div className="flex justify-center py-10"><Spinner /></div>
        ) : !questions || questions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No questions identified.</p>
        ) : (
          <div className="space-y-3">
            {questions.map((q) => (
              <div key={q.id} className="rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground mb-1.5">
                  {q.question_number && <Badge variant="outline" className="font-normal">Q{q.question_number}</Badge>}
                  {q.section && <Badge variant="outline" className="font-normal">Section {q.section}</Badge>}
                  {q.marks != null && <Badge variant="outline" className="font-normal">{q.marks} marks</Badge>}
                  {q.topic_name ? (
                    <Badge variant="secondary" className="font-normal">{q.topic_name}</Badge>
                  ) : (
                    <Badge variant="outline" className="font-normal text-muted-foreground">Topic uncertain</Badge>
                  )}
                </div>
                <p className="text-sm">{q.question_text}</p>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function DeleteDialog({
  paperId, courseId, onClose,
}: {
  paperId: number | null;
  courseId: number | null;
  onClose: () => void;
}) {
  const deleteMut = useDeleteQuestionPaper();
  const confirmDelete = async () => {
    if (!paperId || !courseId) return;
    await deleteMut.mutateAsync({ paperId, courseId });
    onClose();
  };
  return (
    <Dialog open={!!paperId} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete question paper?</DialogTitle>
          <DialogDescription>
            This removes the original file and its extracted questions from this course. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button variant="destructive" onClick={confirmDelete} disabled={deleteMut.isPending}>
            {deleteMut.isPending && <Spinner className="h-4 w-4" />}
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
