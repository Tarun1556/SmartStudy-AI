import * as React from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, BookOpen, Trash2, Edit3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose,
} from "@/components/ui/dialog";
import { EmptyState, Spinner, InputError } from "@/components/common/helpers";
import {
  useCourses, useCreateCourse, useDeleteCourse, useUpdateCourse,
} from "@/lib/api/hooks";
import { useAuth } from "@/features/auth/AuthContext";
import { formatDate } from "@/lib/utils";
import type { Course } from "@/types";

const COLORS = ["#4338ca", "#7c3aed", "#2563eb", "#0891b2", "#059669", "#ea580c", "#db2777", "#6d28d9"];

export default function Courses() {
  const nav = useNavigate();
  const { isDemo } = useAuth();
  const { data, isLoading } = useCourses();
  const createMut = useCreateCourse();
  const deleteMut = useDeleteCourse();
  const updateMut = useUpdateCourse();

  const [editing, setEditing] = React.useState<Course | null>(null);
  const [open, setOpen] = React.useState(false);

  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [color, setColor] = React.useState(COLORS[0]);
  const [err, setErr] = React.useState<string | null>(null);

  const startCreate = () => {
    setEditing(null);
    setName("");
    setDescription("");
    setColor(COLORS[Math.floor(Math.random() * COLORS.length)]);
    setErr(null);
    setOpen(true);
  };

  const startEdit = (c: Course) => {
    setEditing(c);
    setName(c.name);
    setDescription(c.description || "");
    setColor(c.color);
    setErr(null);
    setOpen(true);
  };

  const submit = async () => {
    setErr(null);
    if (!name.trim()) {
      setErr("Name is required");
      return;
    }
    try {
      if (editing) {
        await updateMut.mutateAsync({ id: editing.id, name, description, color });
      } else {
        const created = await createMut.mutateAsync({ name, description, color });
        nav(`/courses/${created.id}`);
      }
      setOpen(false);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || "Something went wrong");
    }
  };

  const onDelete = async (c: Course, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(`Delete course "${c.name}"? This cannot be undone.`)) return;
    await deleteMut.mutateAsync(c.id);
  };

  if (isLoading || !data) {
    return <div className="flex items-center justify-center py-24"><Spinner /></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Courses</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {data.length} course{data.length === 1 ? "" : "s"} in your workspace
          </p>
        </div>
        <Button disabled={isDemo} onClick={startCreate}>
          <Plus className="h-4 w-4" />
          {isDemo ? "Demo mode — read only" : "New course"}
        </Button>
      </div>

      {data.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title="No courses yet"
          description="Create a course to group related lectures and build a cross-lecture study guide."
          action={!isDemo ? <Button onClick={startCreate}><Plus className="h-4 w-4" />New course</Button> : null}
        />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {data.map((c) => (
            <Link key={c.id} to={`/courses/${c.id}`}>
              <Card className="h-full hover:border-primary/40 transition-colors group">
                <CardContent className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="h-12 w-1.5 rounded-full shrink-0" style={{ background: c.color }} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <CardTitle className="text-lg truncate">{c.name}</CardTitle>
                        {!isDemo && (
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={(e) => { e.preventDefault(); e.stopPropagation(); startEdit(c); }}
                            >
                              <Edit3 className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-rose-400 hover:text-rose-400 hover:bg-rose-500/10"
                              onClick={(e) => onDelete(c, e)}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        )}
                      </div>
                      {c.description && (
                        <p className="mt-2 text-sm text-muted-foreground line-clamp-2">{c.description}</p>
                      )}
                      <div className="mt-4 text-xs text-muted-foreground">
                        Updated {formatDate(c.updated_at)}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit course" : "Create course"}</DialogTitle>
            <DialogDescription>
              {editing ? "Update course details." : "Group your lectures into courses (e.g., Data Structures 101)."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Name</Label>
              <Input className="mt-1.5" value={name} onChange={(e) => setName(e.target.value)} placeholder="Data Structures 101" />
            </div>
            <div>
              <Label>Description (optional)</Label>
              <Textarea className="mt-1.5 min-h-[90px]" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="A semester-long introduction to…" />
            </div>
            <div>
              <Label>Color</Label>
              <div className="mt-2 flex flex-wrap gap-2">
                {COLORS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setColor(c)}
                    className={`h-8 w-8 rounded-full ring-offset-2 transition-all ${color === c ? "ring-2 ring-ring scale-110" : ""}`}
                    style={{ background: c }}
                    aria-label={`Pick ${c}`}
                  />
                ))}
              </div>
            </div>
            <InputError>{err}</InputError>
          </div>
          <DialogFooter>
            <DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose>
            <Button onClick={submit} disabled={createMut.isPending || updateMut.isPending}>
              {(createMut.isPending || updateMut.isPending) && <Spinner className="h-4 w-4" />}
              {editing ? "Save changes" : "Create course"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
