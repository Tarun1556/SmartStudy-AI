import * as React from "react";
import { MessageCircle } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import {
  Sparkles, Upload, ArrowRight, BookOpen, Search, BrainCircuit,
  FileDown, Play, CheckCircle2, Layers3, Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/AuthContext";
import { Spinner } from "@/components/common/helpers";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

export default function Landing() {
  const { isAuthenticated, isLoading, enterDemo, isDemo } = useAuth();
  const nav = useNavigate();
  const [entering, setEntering] = React.useState(false);

  const onDemo = async () => {
    try {
      setEntering(true);
      await enterDemo();
      nav("/dashboard", { replace: true });
    } finally {
      setEntering(false);
    }
  };

  React.useEffect(() => {
    if (isAuthenticated || isDemo) {
      nav("/dashboard", { replace: true });
    }
  }, [isAuthenticated, isDemo, nav]);

  if (isLoading || isAuthenticated || isDemo) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner className="h-8 w-8 text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 backdrop-blur bg-background/70 border-b">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-neon-violet to-neon-cyan shadow-glow flex items-center justify-center text-white">
              <Sparkles className="h-4 w-4" />
            </div>
            <span className="text-lg font-semibold tracking-tight">StudyAI</span>
          </Link>
          <div className="flex items-center gap-2">
            <Link to="/login">
              <Button variant="ghost" size="sm">Log in</Button>
            </Link>
            <Link to="/register">
              <Button size="sm">Create Workspace</Button>
            </Link>
          </div>
        </div>
      </header>

      <section className="relative grid-bg max-w-6xl mx-auto px-4 pt-20 pb-24 text-center">
        <Badge variant="secondary" className="mb-5">
          <Layers3 className="h-3.5 w-3.5 mr-1" /> Semester-long knowledge consolidation
        </Badge>
        <h1 className="text-4xl md:text-6xl font-bold tracking-tight max-w-4xl mx-auto leading-[1.05]">
          Turn a semester of lectures into{" "}
          <span className="gradient-text">one intelligent study guide.</span>
        </h1>
        <p className="mt-6 text-lg text-muted-foreground max-w-2xl mx-auto">
          Upload PDF, slides, audio, or paste transcripts. StudyAI extracts structured notes,
          merges recurring topics across lectures, and surfaces evidence-backed concepts you need.
        </p>
        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Button size="lg" disabled={entering} onClick={onDemo}>
            {entering ? <Spinner className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            Try Demo — see it in 30 seconds
            <ArrowRight className="h-4 w-4" />
          </Button>
          <Link to="/register">
            <Button size="lg" variant="outline">
              Create Workspace
            </Button>
          </Link>
        </div>

        <div className="mt-10 text-sm text-muted-foreground">
          Pre-loaded: 6 lectures on Data Structures. No signup needed.
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 pb-24">
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { icon: Upload, title: "1. Upload anything", desc: "Drag-and-drop PDF, PPTX, audio/video or paste a transcript. All formats accepted." },
            { icon: BrainCircuit, title: "2. AI structures it", desc: "Notes, key ideas, definitions, and topics are extracted with source context." },
            { icon: BookOpen, title: "3. Study with evidence", desc: "Cross-lecture topic map, grounded Q&A, ranked concepts, and PDF export." },
          ].map((f, i) => (
            <Card key={i} className="border bg-card/50">
              <CardContent className="p-6">
                <div className="h-10 w-10 rounded-lg bg-primary/10 text-primary border border-primary/20 flex items-center justify-center mb-4">
                  <f.icon className="h-5 w-5" />
                </div>
                <h3 className="font-semibold mb-1.5">{f.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 pb-24">
        <h2 className="text-2xl md:text-3xl font-bold tracking-tight mb-10 text-center">
          Everything you need to study smarter
        </h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { icon: BookOpen, text: "Structured lecture notes with headings, key ideas, definitions, and examples" },
            { icon: Layers3, text: "Cross-lecture topic merging — 'BST' and 'Binary Search Trees' become one concept" },
            { icon: Zap, text: "Transparent coverage scores based on recurrence across lectures and source types" },
            { icon: Search, text: "Hybrid search combining keyword match with meaning-based semantic retrieval" },
            { icon: MessageCircle, text: "Grounded 'Ask Your Notes' Q&A — every answer cites source lectures" },
            { icon: FileDown, text: "One-click polished PDF study guide ready for printing or tablet review" },
            { icon: CheckCircle2, text: "Evidence-backed notes — every claim links to the exact snippet and timestamp" },
            { icon: BrainCircuit, text: "Visual knowledge map and topic timeline showing when concepts were introduced" },
          ].map((f, i) => (
            <div key={i} className="flex items-start gap-3 p-4 rounded-lg border bg-card/30 hover:bg-card transition-colors">
              <div className="h-8 w-8 shrink-0 rounded-md bg-neon-cyan/10 text-neon-cyan border border-neon-cyan/20 flex items-center justify-center mt-0.5">
                <f.icon className="h-4 w-4" />
              </div>
              <div className="text-sm leading-relaxed pt-0.5">{f.text}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="max-w-3xl mx-auto px-4 pb-24 text-center">
        <Card className="bg-gradient-to-br from-neon-violet to-neon-cyan shadow-glow text-white border-0">
          <CardContent className="p-10">
            <h2 className="text-2xl md:text-3xl font-bold mb-3">
              Ready to see it?
            </h2>
            <p className="text-white/80 mb-7 max-w-lg mx-auto">
              Open a pre-seeded demo workspace with 6 lectures already processed and explore the study guide, knowledge map, and Q&A.
            </p>
            <Button
              size="lg"
              variant="secondary"
              onClick={onDemo}
              disabled={entering}
              className="text-neon-violet bg-white hover:bg-white/90"
            >
              {entering ? <Spinner className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              Try Demo Now
            </Button>
          </CardContent>
        </Card>
      </section>

      <footer className="border-t">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between text-xs text-muted-foreground">
          <span>© StudyAI — Built for the Ideathon</span>
          <span>React · FastAPI · PostgreSQL + pgvector</span>
        </div>
      </footer>
    </div>
  );
}
