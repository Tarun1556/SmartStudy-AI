import * as React from "react";
import { NavLink, Outlet, useNavigate, Link } from "react-router-dom";
import {
  LayoutDashboard, BookOpen, Upload, Search, MessageCircle,
  GraduationCap, LogOut, Sparkles, FileQuestion, Settings
} from "lucide-react";
import { useAuth } from "@/features/auth/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/courses", label: "Courses", icon: BookOpen },
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/search", label: "Search", icon: Search },
];

export default function AppLayout() {
  const { user, logout, isDemo } = useAuth();
  const nav = useNavigate();

  const onLogout = () => {
    logout();
    nav("/", { replace: true });
  };

  return (
    <div className="min-h-screen flex bg-background">
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r bg-card/50">
        <div className="p-5 flex items-center gap-2">
          <Link to="/dashboard" className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-neon-violet to-neon-cyan shadow-glow flex items-center justify-center text-white">
              <Sparkles className="h-4 w-4" />
            </div>
            <span className="font-semibold tracking-tight">StudyAI</span>
          </Link>
        </div>
        <Separator />
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 mt-auto space-y-2">
          {isDemo && (
            <Badge variant="info" className="w-full justify-center">
              Demo Workspace — Read Only
            </Badge>
          )}
          <div className="rounded-lg border p-3 text-sm">
            <div className="font-medium truncate">{user?.full_name || user?.email}</div>
            <div className="text-xs text-muted-foreground truncate">{user?.email}</div>
          </div>
          <Button variant="outline" size="sm" className="w-full" onClick={onLogout}>
            <LogOut className="h-4 w-4" />
            {isDemo ? "Exit Demo" : "Log out"}
          </Button>
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="md:hidden h-14 border-b flex items-center justify-between px-4 bg-card">
          <Link to="/dashboard" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-neon-violet to-neon-cyan shadow-glow flex items-center justify-center text-white">
              <Sparkles className="h-3.5 w-3.5" />
            </div>
            <span className="font-semibold text-sm">StudyAI</span>
          </Link>
          <Button variant="outline" size="sm" onClick={onLogout}>
            <LogOut className="h-3.5 w-3.5" />
          </Button>
        </header>
        <nav className="md:hidden border-b bg-card flex items-center gap-1 overflow-x-auto px-2 py-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "shrink-0 flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium",
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground"
                )
              }
            >
              <item.icon className="h-3.5 w-3.5" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 p-4 md:p-8 max-w-[1400px] w-full mx-auto">
          <div className="fade-in">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
