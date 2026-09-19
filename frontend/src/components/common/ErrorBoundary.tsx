import * as React from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: React.ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("Unhandled UI error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center p-6">
          <div className="max-w-md w-full rounded-2xl border border-border bg-card p-8 text-center space-y-4">
            <div className="mx-auto h-12 w-12 rounded-full bg-rose-500/10 text-rose-400 flex items-center justify-center">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Something went wrong</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                This page hit an unexpected error. You can go back to the dashboard and try again.
              </p>
            </div>
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="secondary"
                onClick={() => {
                  this.setState({ error: null });
                  window.location.href = "/dashboard";
                }}
              >
                Back to dashboard
              </Button>
              <Button onClick={() => window.location.reload()}>Reload page</Button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
