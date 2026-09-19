import * as React from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft, RefreshCcw, FileQuestion, CheckCircle2, XCircle, BookOpen,
  ChevronRight, Trophy, Target, Award, Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { EmptyState, Spinner } from "@/components/common/helpers";
import {
  useCourse, useGenerateQuiz, useCourseTopics,
  useCourseQuizzes, useQuizAttempts, useSubmitQuizAttempt,
} from "@/lib/api/hooks";
import { useAuth } from "@/features/auth/AuthContext";
import { cn, formatCoverage, formatDate } from "@/lib/utils";
import type { Quiz, QuizQuestion } from "@/types";

export default function QuizPage() {
  const { courseId: rawId } = useParams();
  const courseId = rawId ? Number(rawId) : null;
  const { isDemo } = useAuth();

  const { data: course, isLoading: loadingCourse } = useCourse(courseId);
  const { data: topics } = useCourseTopics(courseId);
  const generate = useGenerateQuiz();
  const submitAttempt = useSubmitQuizAttempt();
  const { data: pastQuizzes } = useCourseQuizzes(courseId);
  const lastQuizId = pastQuizzes && pastQuizzes.length > 0 ? pastQuizzes[0].id : null;
  const { data: lastAttempts } = useQuizAttempts(lastQuizId);

  const [quiz, setQuiz] = React.useState<Quiz | null>(null);
  const [answers, setAnswers] = React.useState<Record<number, number | null>>({});
  const [graded, setGraded] = React.useState(false);
  const [questionCursor, setQuestionCursor] = React.useState(0);

  const begin = async () => {
    if (!courseId) return;
    const res = await generate.mutateAsync({
      courseId,
      numQuestions: 10,
    });
    setQuiz(res);
    const blank: Record<number, number | null> = {};
    res.questions.forEach((q, i) => (blank[i] = null));
    setAnswers(blank);
    setGraded(false);
    setQuestionCursor(0);
  };

  React.useEffect(() => {
    if (courseId && topics && topics.length > 0) {
      begin();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseId, topics?.length]);

  if (loadingCourse || !course) {
    return <div className="flex items-center justify-center py-24"><Spinner /></div>;
  }

  if (!quiz) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Link to={`/courses/${courseId}`} className="inline-flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            {course.name}
          </Link>
        </div>
        <div className="max-w-xl mx-auto text-center py-10">
          <div className="mx-auto h-14 w-14 rounded-2xl bg-primary/10 text-primary flex items-center justify-center">
            <FileQuestion className="h-7 w-7" />
          </div>
          <h1 className="mt-5 text-2xl font-bold tracking-tight">Practice questions</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Generate a short quiz sourced directly from your lecture material. Each question
            links back to the specific lecture where the answer lives.
          </p>
          <div className="mt-7">
            <Button
              onClick={begin}
              disabled={generate.isPending || isDemo}
              size="lg"
              className="px-6"
            >
              {generate.isPending ? (
                <>
                  <Sparkles className="h-4 w-4 mr-2 animate-spin" />
                  Generating…
                </>
              ) : (
                <>
                  <Target className="h-4 w-4 mr-2" />
                  {isDemo ? "Demo — read only" : "Start 10-question quiz"}
                </>
              )}
            </Button>
          </div>
          {(topics || []).length === 0 && (
            <p className="mt-6 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded-md px-3 py-2 inline-block">
              You need at least one processed lecture in this course to generate questions.
            </p>
          )}
          {lastAttempts && lastAttempts.length > 0 && (
            <div className="mt-8 inline-flex items-center gap-2 rounded-lg border border-border bg-card/50 px-4 py-2.5 text-sm">
              <Trophy className="h-4 w-4 text-primary" />
              <span className="text-muted-foreground">Last attempt:</span>
              <span className="font-semibold text-foreground">
                {lastAttempts[0].score} / {lastAttempts[0].total_questions}
              </span>
              <span className="text-muted-foreground">
                ({Math.round((lastAttempts[0].score / lastAttempts[0].total_questions) * 100)}%) —{" "}
                {formatDate(lastAttempts[0].completed_at)}
              </span>
            </div>
          )}
        </div>
      </div>
    );
  }

  const answeredCount = Object.values(answers).filter((a) => a != null).length;
  const correct = graded
    ? quiz.questions.reduce((acc, q, i) => {
        const picked = answers[i];
        const ok = picked != null && q.options?.[picked] === q.correct_answer;
        return acc + (ok ? 1 : 0);
      }, 0)
    : 0;
  const pct = graded ? (correct / quiz.questions.length) * 100 : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to={`/courses/${courseId}`} className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          {course.name}
        </Link>
      </div>

      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">{quiz.title}</h1>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <Badge variant="outline" className="font-normal capitalize">
              {quiz.quiz_type}
            </Badge>
            <span>{quiz.questions.length} questions</span>
            <span>Generated {formatDate(quiz.generated_at)}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={begin}
            disabled={generate.isPending || isDemo}
          >
            <RefreshCcw className={cn("h-4 w-4", generate.isPending && "animate-spin")} />
            {isDemo ? "Demo — read only" : "New quiz"}
          </Button>
        </div>
      </div>

      {!graded ? (
        <QuizProgress
          answered={answeredCount}
          total={quiz.questions.length}
          cursor={questionCursor}
          onJump={setQuestionCursor}
          answers={answers}
        />
      ) : (
        <ScoreCard correct={correct} total={quiz.questions.length} pct={pct} />
      )}

      <div className="space-y-4">
        {quiz.questions.map((q, i) => (
          <QuestionRow
            key={i}
            q={q}
            index={i}
            selected={answers[i] ?? null}
            onSelect={(opt) => {
              setAnswers((a) => ({ ...a, [i]: opt }));
              if (!graded && i === questionCursor && i < quiz.questions.length - 1) {
                setQuestionCursor(i + 1);
              }
            }}
            showHidden={questionCursor >= i || graded}
            graded={graded}
          />
        ))}
      </div>

      {!graded ? (
        <div className="sticky bottom-0 bg-background/80 backdrop-blur py-3 border-t mt-6">
          <div className="flex items-center justify-between gap-3">
            <Button
              variant="ghost"
              onClick={() => setQuestionCursor((c) => Math.max(0, c - 1))}
              disabled={questionCursor === 0}
            >
              Previous
            </Button>
            <div className="text-xs text-muted-foreground">
              Question {questionCursor + 1} of {quiz.questions.length}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                onClick={() =>
                  setQuestionCursor((c) =>
                    Math.min(quiz.questions.length - 1, c + 1)
                  )
                }
                disabled={questionCursor >= quiz.questions.length - 1}
              >
                Next
              </Button>
              <Button
                disabled={answeredCount < quiz.questions.length}
                onClick={() => {
                  setGraded(true);
                  const byQuestionId: Record<number, number> = {};
                  quiz.questions.forEach((q, i) => {
                    const picked = answers[i];
                    if (picked != null) byQuestionId[q.id] = picked;
                  });
                  submitAttempt.mutate({ quizId: quiz.id, answers: byQuestionId });
                }}
              >
                Submit answers
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex justify-end">
          <Button onClick={() => { setGraded(false); setQuestionCursor(0); }} variant="secondary">
            Review answers
          </Button>
        </div>
      )}
    </div>
  );
}

function QuizProgress({
  answered,
  total,
  cursor,
  onJump,
  answers,
}: {
  answered: number;
  total: number;
  cursor: number;
  onJump: (i: number) => void;
  answers: Record<number, number | null>;
}) {
  return (
    <Card>
      <CardContent className="py-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex-1 min-w-[200px]">
            <div className="flex justify-between text-xs mb-1.5 text-muted-foreground">
              <span>Progress</span>
              <span className="font-medium text-foreground">{answered} / {total} answered</span>
            </div>
            <Progress value={(answered / total) * 100} />
          </div>
          <div className="flex flex-wrap gap-1 max-w-md">
            {Array.from({ length: total }).map((_, i) => {
              const done = answers[i] != null;
              const isCur = i === cursor;
              return (
                <button
                  key={i}
                  onClick={() => onJump(i)}
                  className={cn(
                    "h-7 w-7 rounded-md text-xs font-medium transition-colors border",
                    done
                      ? "bg-primary/10 border-primary/40 text-primary"
                      : "bg-card border-border text-muted-foreground hover:bg-muted",
                    isCur && "ring-2 ring-offset-1 ring-primary/40"
                  )}
                >
                  {i + 1}
                </button>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ScoreCard({ correct, total, pct }: { correct: number; total: number; pct: number }) {
  const level =
    pct >= 85 ? { label: "Mastered", cls: "text-emerald-400", icon: Award } :
    pct >= 60 ? { label: "Solid progress", cls: "text-sky-400", icon: Target } :
    { label: "Keep reviewing", cls: "text-amber-400", icon: Sparkles };
  const Icon = level.icon;
  return (
    <Card className={cn(
      "bg-gradient-to-br from-primary/10 via-card to-neon-cyan/5 border-primary/20"
    )}>
      <CardContent className="pt-6">
        <div className="grid md:grid-cols-3 gap-6 items-center">
          <div className="flex items-center gap-4">
            <div className="h-14 w-14 rounded-2xl bg-card border border-border flex items-center justify-center text-primary">
              <Icon className="h-7 w-7" />
            </div>
            <div>
              <div className="text-xs uppercase tracking-wider text-muted-foreground">Your result</div>
              <div className={cn("text-lg font-semibold", level.cls)}>{level.label}</div>
            </div>
          </div>
          <div className="md:text-center">
            <div className="text-4xl font-bold tracking-tight">
              {correct}
              <span className="text-lg text-muted-foreground font-medium"> / {total}</span>
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              Correct answers
            </div>
          </div>
          <div>
            <Progress value={pct} />
            <div className="mt-1.5 text-xs text-muted-foreground flex justify-between">
              <span>Score</span>
              <span className="font-medium text-foreground">{pct.toFixed(0)}%</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function QuestionRow({
  q,
  index,
  selected,
  onSelect,
  showHidden,
  graded,
}: {
  q: QuizQuestion;
  index: number;
  selected: number | null;
  onSelect: (opt: number) => void;
  showHidden: boolean;
  graded: boolean;
}) {
  if (!showHidden) {
    return null;
  }
  const correctIdx = q.options?.findIndex((o) => o === q.correct_answer) ?? -1;
  return (
    <Card id={`q-${index}`}>
      <CardHeader>
        <div className="flex items-start gap-3">
          <div className="h-8 w-8 shrink-0 rounded-lg bg-primary/10 text-primary flex items-center justify-center text-sm font-semibold">
            {index + 1}
          </div>
          <div className="min-w-0 flex-1">
            <CardTitle className="text-base leading-relaxed">{q.question_text}</CardTitle>
            <CardDescription className="mt-1.5 text-[11px] uppercase tracking-wider">
              {q.question_type.toUpperCase()}
            </CardDescription>
          </div>
          {graded && (
            <div className="shrink-0">
              {selected === correctIdx ? (
                <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 border">
                  <CheckCircle2 className="h-3 w-3 mr-1" /> Correct
                </Badge>
              ) : (
                <Badge className="bg-rose-500/10 text-rose-400 border-rose-500/30 border">
                  <XCircle className="h-3 w-3 mr-1" /> Incorrect
                </Badge>
              )}
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          {(q.options || []).map((opt, i) => {
            const isPicked = selected === i;
            let stateCls =
              "bg-card border-border hover:border-primary/40 hover:bg-muted";
            if (isPicked && !graded)
              stateCls = "bg-primary/10 border-primary ring-2 ring-primary/20";
            if (graded) {
              if (i === correctIdx)
                stateCls = "bg-emerald-500/10 border-emerald-500/40 text-emerald-300";
              else if (isPicked)
                stateCls = "bg-rose-500/10 border-rose-500/40 text-rose-300";
              else stateCls = "bg-card border-border text-muted-foreground";
            }
            return (
              <button
                key={i}
                disabled={graded}
                onClick={() => onSelect(i)}
                className={cn(
                  "w-full text-left rounded-lg border px-4 py-3 flex items-start gap-3 transition-colors text-sm",
                  stateCls,
                  !graded && "cursor-pointer"
                )}
              >
                <span
                  className={cn(
                    "h-5 w-5 shrink-0 rounded-full border text-[11px] font-semibold inline-flex items-center justify-center mt-0.5",
                    isPicked && !graded && "bg-primary border-primary text-primary-foreground",
                    graded && i === correctIdx && "bg-emerald-500 border-emerald-500 text-white",
                    graded && isPicked && i !== correctIdx && "bg-rose-500 border-rose-500 text-white"
                  )}
                >
                  {String.fromCharCode(65 + i)}
                </span>
                <span className="leading-relaxed">{opt}</span>
                {graded && i === correctIdx && (
                  <CheckCircle2 className="h-4 w-4 text-emerald-400 ml-auto shrink-0 mt-0.5" />
                )}
                {graded && isPicked && i !== correctIdx && (
                  <XCircle className="h-4 w-4 text-rose-400 ml-auto shrink-0 mt-0.5" />
                )}
              </button>
            );
          })}
        </div>

        {graded && (q.correct_answer || q.explanation || q.source_lecture_id) && (
          <>
            <Separator />
            <div className="space-y-2">
              {q.explanation && (
                <div className="text-sm leading-relaxed text-muted-foreground bg-muted border border-border rounded-lg px-4 py-3">
                  <span className="font-semibold text-foreground">Explanation — </span>
                  {q.explanation}
                </div>
              )}
              {q.source_lecture_id && (
                <div className="text-xs text-muted-foreground flex items-center gap-1.5">
                  <BookOpen className="h-3.5 w-3.5" />
                  Source lecture:{" "}
                  <Link
                    to={`/lectures/${q.source_lecture_id}`}
                    className="text-primary hover:underline inline-flex items-center gap-0.5"
                  >
                    Open lecture
                    <ChevronRight className="h-3 w-3" />
                  </Link>
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
