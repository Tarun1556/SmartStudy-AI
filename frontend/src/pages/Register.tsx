import * as React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Sparkles, UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InputError, Spinner } from "@/components/common/helpers";
import { useAuth } from "@/features/auth/AuthContext";

const schema = z
  .object({
    full_name: z.string().min(1, "Name is required"),
    email: z.string().email("Enter a valid email"),
    password: z.string().min(6, "Password must be at least 6 characters"),
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, {
    message: "Passwords must match",
    path: ["confirm"],
  });

type Form = z.infer<typeof schema>;

export default function Register() {
  const { register: createUser, isAuthenticated, isLoading } = useAuth();
  const nav = useNavigate();
  const [err, setErr] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  const { register, handleSubmit, formState: { errors } } = useForm<Form>({
    resolver: zodResolver(schema),
  });

  React.useEffect(() => {
    if (isAuthenticated) nav("/dashboard", { replace: true });
  }, [isAuthenticated, nav]);

  const onSubmit = async (values: Form) => {
    setErr(null);
    setSubmitting(true);
    try {
      await createUser(values.email, values.password, values.full_name);
      nav("/dashboard", { replace: true });
    } catch (e: any) {
      setErr(e?.response?.data?.detail || "Could not create account");
    } finally {
      setSubmitting(false);
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
          <CardTitle className="text-xl">Create your workspace</CardTitle>
          <CardDescription>
            Your courses, notes, and study guide — all private
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <Label htmlFor="full_name">Full name</Label>
              <Input id="full_name" className="mt-1.5" {...register("full_name")} />
              <InputError>{errors.full_name?.message}</InputError>
            </div>
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="email" className="mt-1.5" {...register("email")} />
              <InputError>{errors.email?.message}</InputError>
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete="new-password" className="mt-1.5" {...register("password")} />
              <InputError>{errors.password?.message}</InputError>
            </div>
            <div>
              <Label htmlFor="confirm">Confirm password</Label>
              <Input id="confirm" type="password" className="mt-1.5" {...register("confirm")} />
              <InputError>{errors.confirm?.message}</InputError>
            </div>
            <InputError>{err}</InputError>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? <Spinner className="h-4 w-4" /> : <UserPlus className="h-4 w-4" />}
              Create account
            </Button>
          </form>
          <div className="mt-5 text-center text-sm text-muted-foreground">
            Already have one?{" "}
            <Link to="/login" className="text-primary font-medium hover:underline">
              Log in
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
