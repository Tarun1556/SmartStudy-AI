import * as React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Sparkles, LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InputError, Spinner } from "@/components/common/helpers";
import { useAuth } from "@/features/auth/AuthContext";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(6, "Password must be at least 6 characters"),
});

type Form = z.infer<typeof schema>;

export default function Login() {
  const { login, isAuthenticated, isLoading, enterDemo } = useAuth();
  const nav = useNavigate();
  const [err, setErr] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [enteringDemo, setEnteringDemo] = React.useState(false);

  const {
    register, handleSubmit, formState: { errors },
  } = useForm<Form>({ resolver: zodResolver(schema) });

  React.useEffect(() => {
    if (isAuthenticated) nav("/dashboard", { replace: true });
  }, [isAuthenticated, nav]);

  const onSubmit = async (values: Form) => {
    setErr(null);
    setSubmitting(true);
    try {
      await login(values.email, values.password);
      nav("/dashboard", { replace: true });
    } catch (e: any) {
      setErr(e?.response?.data?.detail || "Invalid email or password");
    } finally {
      setSubmitting(false);
    }
  };

  const onDemo = async () => {
    setEnteringDemo(true);
    try {
      await enterDemo();
      nav("/dashboard", { replace: true });
    } finally {
      setEnteringDemo(false);
    }
  };

  if (isLoading && isAuthenticated) {
    return <div className="min-h-screen flex items-center justify-center"><Spinner /></div>;
  }

  return (
    <div className="min-h-screen grid-bg flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-3 h-10 w-10 rounded-xl bg-gradient-to-br from-neon-violet to-neon-cyan shadow-glow flex items-center justify-center text-white">
            <Sparkles className="h-5 w-5" />
          </div>
          <CardTitle className="text-xl">Welcome back</CardTitle>
          <CardDescription>
            Log in to your StudyAI workspace
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="email" className="mt-1.5" {...register("email")} />
              <InputError>{errors.email?.message}</InputError>
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete="current-password" className="mt-1.5" {...register("password")} />
              <InputError>{errors.password?.message}</InputError>
            </div>
            <InputError>{err}</InputError>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? <Spinner className="h-4 w-4" /> : <LogIn className="h-4 w-4" />}
              Log in
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full"
              disabled={enteringDemo}
              onClick={onDemo}
            >
              {enteringDemo ? <Spinner className="h-4 w-4" /> : null}
              Continue with Demo (no signup)
            </Button>
          </form>
          <div className="mt-5 text-center text-sm text-muted-foreground">
            Don't have an account?{" "}
            <Link to="/register" className="text-primary font-medium hover:underline">
              Create one
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
