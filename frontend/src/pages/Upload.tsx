import * as React from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Upload as UploadIcon, FileText, FileAudio, Presentation, Loader2, CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState, Spinner, InputError } from "@/components/common/helpers";
import { useCourses, useUploadLecture, useCreateLecture, useLectureStatus } from "@/lib/api/hooks";
import { useAuth } from "@/features/auth/AuthContext";
import { cn } from "@/lib/utils";

const schema = z.object({
  course_id: z.coerce.number({ required_error: "Select a course" }).min(1),
  title: z.string().min(1, "Lecture title is required"),
  lecture_number: z.union([z.string(), z.number()]).optional(),
  lecture_date: z.string().optional(),
  description: z.string().optional(),
  transcript_text: z.string().optional(),
});

type Form = z.infer<typeof schema>;

export default function Upload() {
  const nav = useNavigate();
  const { isDemo } = useAuth();
  const { data: courses, isLoading: loadingCourses } = useCourses();
  const uploadMut = useUploadLecture();
  const pasteMut = useCreateLecture();

  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { description: "", transcript_text: "" },
  });
  const courseId = watch("course_id");
  const transcript_text = watch("transcript_text") || "";

  const [file, setFile] = React.useState<File | null>(null);
  const [dragOver, setDragOver] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);
  const [created, setCreated] = React.useState<{ lecture_id: number; job_id: number } | null>(null);
  const [tab, setTab] = React.useState<"file" | "paste">("file");

  const { data: jobStatus } = useLectureStatus(created?.job_id ? null : null, 1500);

  React.useEffect(() => {
    if (courses && courses.length > 0 && !courseId) {
      setValue("course_id", courses[0].id as any);
    }
  }, [courses, courseId, setValue]);

  if (isDemo) {
    return (
      <div className="py-20">
        <EmptyState
          icon={UploadIcon}
          title="Demo workspace is read-only"
          description="Create your own workspace to upload lectures and process your material."
          action={
            <Button onClick={() => nav("/register")}>
              Create Workspace
            </Button>
          }
        />
      </div>
    );
  }

  if (loadingCourses || !courses) {
    return <div className="flex items-center justify-center py-24"><Spinner /></div>;
  }

  if (courses.length === 0) {
    return (
      <div className="py-20">
        <EmptyState
          icon={UploadIcon}
          title="Create a course first"
          description="Organize lectures into courses before uploading material."
          action={
            <Button onClick={() => nav("/courses")}>
              Create course
            </Button>
          }
        />
      </div>
    );
  }

  const onFileDrop = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const f = files[0];
    const ext = f.name.split(".").pop()?.toLowerCase() || "";
    const allowed = ["pdf", "pptx", "ppt", "txt", "md", "mp3", "wav", "m4a", "mp4", "webm", "ogg", "flac", "aac", "rtf"];
    if (!allowed.includes(ext)) {
      setErr("Unsupported file type. Supported: PDF, PPTX, TXT, MD, audio/video.");
      return;
    }
    setErr(null);
    setFile(f);
  };

  const fileClass = (file?.name.split(".").pop()?.toLowerCase() || "");
  const iconForExt = () => {
    if (["pdf"].includes(fileClass)) return FileText;
    if (["pptx", "ppt"].includes(fileClass)) return Presentation;
    if (["mp3", "wav", "m4a", "mp4", "webm", "ogg", "flac", "aac"].includes(fileClass)) return FileAudio;
    return FileText;
  };
  const FileIcon = iconForExt();

  const onSubmit = async (values: Form) => {
    setErr(null);
    try {
      if (tab === "file" && !file) {
        setErr("Please choose a file or switch to 'Paste transcript'.");
        return;
      }
      if (tab === "paste" && !(values.transcript_text && values.transcript_text.trim().length > 50)) {
        setErr("Paste at least 50 characters of transcript.");
        return;
      }

      if (tab === "file" && file) {
        const fd = new FormData();
        fd.append("course_id", String(values.course_id));
        fd.append("title", values.title);
        if (values.lecture_number) fd.append("lecture_number", String(values.lecture_number));
        if (values.lecture_date) fd.append("lecture_date", values.lecture_date);
        if (values.description) fd.append("description", values.description);
        fd.append("file", file);
        const r = await uploadMut.mutateAsync(fd);
        setCreated({ lecture_id: r.lecture_id, job_id: r.job_id });
      } else {
        const r: any = await pasteMut.mutateAsync({
          course_id: values.course_id,
          title: values.title,
          lecture_number: values.lecture_number ? Number(values.lecture_number) : null,
          lecture_date: values.lecture_date ? new Date(values.lecture_date) : null,
          description: values.description,
          transcript_text: values.transcript_text,
        });
        const jobId = (r as any).latest_job?.id;
        if (jobId) setCreated({ lecture_id: r.id, job_id: jobId });
        else setTimeout(() => nav(`/lectures/${r.id}`), 300);
      }
    } catch (e: any) {
      setErr(e?.response?.data?.detail || "Upload failed");
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Upload lecture material</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Upload files or paste a transcript — we'll structure notes, extract topics, and add them to the course study guide.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Lecture details</CardTitle>
          <CardDescription>Basic info + material input</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <Label>Course</Label>
                <select
                  className={cn(
                    "mt-1.5 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  )}
                  {...register("course_id")}
                >
                  <option value="">Select course…</option>
                  {courses.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <InputError>{errors.course_id?.message as any}</InputError>
              </div>
              <div>
                <Label>Lecture title</Label>
                <Input className="mt-1.5" placeholder="Lecture 3: Stacks & Queues" {...register("title")} />
                <InputError>{errors.title?.message}</InputError>
              </div>
              <div>
                <Label>Lecture number (optional)</Label>
                <Input className="mt-1.5" placeholder="3" {...register("lecture_number")} />
              </div>
              <div>
                <Label>Date (optional)</Label>
                <Input className="mt-1.5" type="date" {...register("lecture_date")} />
              </div>
            </div>
            <div>
              <Label>Description (optional)</Label>
              <Textarea className="mt-1.5 min-h-[60px]" placeholder="Short summary of the lecture's focus" {...register("description")} />
            </div>

            <div className="space-y-3 pt-2">
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant={tab === "file" ? "default" : "outline"}
                  onClick={() => setTab("file")}
                >
                  <UploadIcon className="h-4 w-4" />
                  Upload file
                </Button>
                <Button
                  type="button"
                  variant={tab === "paste" ? "default" : "outline"}
                  onClick={() => setTab("paste")}
                >
                  <FileText className="h-4 w-4" />
                  Paste transcript
                </Button>
              </div>

              {tab === "file" && (
                <div
                  className={cn(
                    "mt-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors cursor-pointer",
                    dragOver
                      ? "border-primary bg-primary/10"
                      : "border-border hover:border-primary/60 hover:bg-muted/30"
                  )}
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(e) => { e.preventDefault(); setDragOver(false); onFileDrop(e.dataTransfer.files); }}
                  onClick={() => (document.getElementById("file-picker") as HTMLInputElement)?.click()}
                >
                  <input
                    id="file-picker"
                    type="file"
                    className="hidden"
                    accept=".pdf,.pptx,.ppt,.txt,.md,.rtf,.mp3,.wav,.m4a,.mp4,.webm,.ogg,.flac,.aac"
                    onChange={(e) => onFileDrop(e.target.files)}
                  />
                  {!file ? (
                    <div className="pointer-events-none">
                      <div className="mx-auto h-12 w-12 rounded-full bg-muted flex items-center justify-center text-muted-foreground mb-3">
                        <UploadIcon className="h-5 w-5" />
                      </div>
                      <div className="text-sm font-medium">Drop a file here, or click to browse</div>
                      <div className="text-xs text-muted-foreground mt-1">
                        PDF · PPTX · TXT · audio/video · up to ~100MB
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center gap-3 pointer-events-none">
                      <div className="h-12 w-12 rounded-lg bg-primary/10 text-primary border border-primary/20 flex items-center justify-center">
                        <FileIcon className="h-5 w-5" />
                      </div>
                      <div className="text-left">
                        <div className="font-medium">{file.name}</div>
                        <div className="text-xs text-muted-foreground">{(file.size / 1024 / 1024).toFixed(2)} MB · {fileClass.toUpperCase()}</div>
                      </div>
                      <Badge variant="success" className="ml-4"><CheckCircle2 className="h-3 w-3 mr-1" />Attached</Badge>
                    </div>
                  )}
                </div>
              )}

              {tab === "paste" && (
                <div>
                  <Label>Paste raw transcript / notes text</Label>
                  <Textarea
                    className="mt-1.5 min-h-[220px] font-mono text-[13px]"
                    placeholder="Professor: Today we're going to talk about..."
                    {...register("transcript_text")}
                  />
                  <div className="mt-1 text-xs text-muted-foreground flex justify-between">
                    <span>Paste the full transcript; we'll chunk and analyze it.</span>
                    <span>{transcript_text.length} chars</span>
                  </div>
                  <InputError>{errors.transcript_text?.message}</InputError>
                </div>
              )}
            </div>

            <InputError>{err}</InputError>

            <div className="flex justify-end gap-2">
              <Button
                type="submit"
                disabled={uploadMut.isPending || pasteMut.isPending}
                size="lg"
              >
                {(uploadMut.isPending || pasteMut.isPending) && <Spinner className="h-4 w-4" />}
                Process lecture
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Dialog open={!!created} onOpenChange={(v) => !v && setCreated(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Processing started</DialogTitle>
            <DialogDescription>
              You can watch progress here or close this and continue working.
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
            <div className="rounded-lg border p-3 text-xs text-muted-foreground">
              <div>Validating → Extracting/Transcribing → Structured notes → Topics → Merging → Study guide update</div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreated(null)}>Keep working</Button>
            <Button onClick={() => created && nav(`/lectures/${created.lecture_id}`)}>
              {jobStatus?.status === "completed" ? "View notes" : "Open lecture"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
