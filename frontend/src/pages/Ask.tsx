import * as React from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft, Send, MessageCircle, Sparkles, BookOpen, AlertCircle,
  FileText, ChevronRight, Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { EmptyState, Spinner } from "@/components/common/helpers";
import {
  useCourse, useAskQuestion,
} from "@/lib/api/hooks";
import { cn, formatDate } from "@/lib/utils";
import type { AskResponse, Citation } from "@/types";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  found?: boolean;
  sessionId?: number;
}

const SUGGESTIONS = [
  "What is Big O Notation and why does it matter?",
  "Explain how Dijkstra's algorithm works step by step.",
  "Compare arrays vs linked lists with examples.",
  "When should I use a stack instead of a queue?",
  "What is the difference between BFS and DFS?",
];

export default function AskPage() {
  const { courseId: rawId } = useParams();
  const courseId = rawId ? Number(rawId) : null;
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const [input, setInput] = React.useState("");
  const [sessionId, setSessionId] = React.useState<number | undefined>(undefined);
  const [messages, setMessages] = React.useState<Message[]>([]);

  const { data: course, isLoading: loadingCourse } = useCourse(courseId);
  const ask = useAskQuestion();

  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, ask.isPending]);

  const send = async (textOverride?: string) => {
    const q = (textOverride ?? input).trim();
    if (!q || !courseId || ask.isPending) return;
    const userMsg: Message = { role: "user", content: q };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    try {
      const res: AskResponse = await ask.mutateAsync({
        courseId,
        question: q,
        sessionId,
      });
      if (typeof res.session_id === "number") setSessionId(res.session_id);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: res.answer,
          citations: res.citations,
          found: res.found_in_material,
          sessionId: res.session_id,
        },
      ]);
    } catch (e: any) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content:
            e?.response?.data?.detail?.toString() ||
            "Sorry, something went wrong. Please try again.",
          found: false,
        },
      ]);
    }
  };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  if (loadingCourse || !course) {
    return <div className="flex items-center justify-center py-24"><Spinner /></div>;
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] min-h-[600px]">
      <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
        <Link to={`/courses/${courseId}`} className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          {course.name}
        </Link>
      </div>

      <div className="mb-3 flex items-center gap-3">
        <div className="h-11 w-11 shrink-0 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
          <MessageCircle className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <h1 className="text-xl font-bold tracking-tight">Ask your notes</h1>
          <p className="text-sm text-muted-foreground truncate">
            Answers are grounded only in your processed lecture material — with cited sources.
          </p>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto pr-1 space-y-4 scroll-smooth pb-4"
      >
        {messages.length === 0 ? (
          <EmptyState
            icon={Sparkles}
            title="Ask anything about this course"
            description="Questions are answered only from your processed lectures — if the info isn't there, we'll tell you."
            action={
              <div className="mt-5 grid sm:grid-cols-2 gap-2 max-w-2xl mx-auto w-full">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left text-sm rounded-lg border border-border hover:border-primary/40 hover:bg-muted p-3 transition-colors"
                >
                  <div className="flex items-start gap-2">
                    <ChevronRight className="h-4 w-4 mt-0.5 shrink-0 text-primary" />
                    <span className="leading-relaxed">{s}</span>
                  </div>
                </button>
              ))}
              </div>
            }
          />
        ) : (
          messages.map((m, i) => (
            <MessageBubble key={i} msg={m} courseId={courseId!} />
          ))
        )}
        {ask.isPending && (
          <div className="flex gap-3">
            <div className="h-8 w-8 shrink-0 rounded-full bg-primary/10 text-primary flex items-center justify-center">
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
            <div className="rounded-2xl rounded-tl-sm bg-muted border border-border px-4 py-3 text-sm text-muted-foreground">
              Searching your material and drafting an answer…
            </div>
          </div>
        )}
      </div>

      <div className="pt-3 mt-auto">
        <Separator className="mb-3" />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="flex items-center gap-2"
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder="Ask a question like: what is time complexity of quicksort?"
            className="h-11"
            disabled={ask.isPending}
          />
          <Button
            type="submit"
            size="icon"
            className="h-11 w-11 shrink-0"
            disabled={!input.trim() || ask.isPending}
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
        <div className="mt-2 text-[11px] text-muted-foreground">
          The assistant only uses your uploaded material. Press <kbd className="rounded border bg-muted px-1">Enter</kbd> to send.
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ msg, courseId }: { msg: Message; courseId: number }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] md:max-w-[70%] rounded-2xl rounded-tr-sm bg-primary text-primary-foreground px-4 py-3 text-sm leading-relaxed">
          {msg.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex gap-3">
      <div className="h-8 w-8 shrink-0 rounded-full bg-primary/10 text-primary flex items-center justify-center">
        <MessageCircle className="h-4 w-4" />
      </div>
      <div className="max-w-[90%] md:max-w-[80%] rounded-2xl rounded-tl-sm bg-muted border border-border px-4 py-3 text-sm leading-relaxed">
        {msg.found === false ? (
          <div className="flex items-start gap-2 text-amber-400">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <div>
              <div className="font-medium">Not found in your material</div>
              <div className="mt-1 text-amber-400/80">{msg.content}</div>
            </div>
          </div>
        ) : (
          <p className="whitespace-pre-wrap text-foreground">{msg.content}</p>
        )}

        {msg.citations && msg.citations.length > 0 && (
          <div className="mt-4">
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground mb-2">
              Cited sources
            </div>
            <div className="flex flex-wrap gap-1.5">
              {msg.citations.map((c, i) => (
                <CitationBadge key={i} index={i + 1} citation={c} courseId={courseId} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function CitationBadge({
  index,
  citation,
  courseId,
}: {
  index: number;
  citation: Citation;
  courseId: number;
}) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2 py-1 text-xs text-muted-foreground hover:border-primary/40 hover:bg-accent"
          )}
        >
          <span className="h-4 w-4 shrink-0 rounded-full bg-primary/10 text-primary text-[10px] font-semibold inline-flex items-center justify-center">
            {index}
          </span>
          <BookOpen className="h-3 w-3 text-muted-foreground" />
          <span className="max-w-[180px] truncate">
            {citation.lecture_number ? `L${citation.lecture_number} ` : ""}
            {citation.lecture_title}
          </span>
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <FileText className="h-4 w-4 text-primary" />
            Source citation #{index}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 mt-1">
          <div className="flex flex-wrap gap-2 text-xs">
            {citation.lecture_number && (
              <Badge variant="outline" className="border">L{citation.lecture_number}</Badge>
            )}
            <div className="font-medium">{citation.lecture_title}</div>
            {citation.start_time != null && (
              <span className="text-muted-foreground">
                · {formatTimestamp(citation.start_time)}
              </span>
            )}
          </div>
          <Card className="bg-muted border-border">
            <CardContent className="p-4 text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap">
              “{citation.snippet}”
            </CardContent>
          </Card>
          <div className="flex justify-end">
            <Link
              to={`/lectures/${citation.lecture_id}`}
              className="text-xs text-primary hover:underline inline-flex items-center gap-1"
            >
              Open full lecture
              <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
