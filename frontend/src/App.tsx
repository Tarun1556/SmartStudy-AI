import * as React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import Courses from "@/pages/Courses";
import CourseDetail from "@/pages/CourseDetail";
import Upload from "@/pages/Upload";
import LectureDetail from "@/pages/LectureDetail";
import StudyGuide from "@/pages/StudyGuide";
import Search from "@/pages/Search";
import Ask from "@/pages/Ask";
import QuizPage from "@/pages/QuizPage";
import AppLayout from "@/components/layout/AppLayout";
import { useAuth } from "@/features/auth/AuthContext";
import { Spinner } from "@/components/common/helpers";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner className="h-8 w-8 text-primary" />
      </div>
    );
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/courses" element={<Courses />} />
        <Route path="/courses/:id" element={<CourseDetail />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/lectures/:id" element={<LectureDetail />} />
        <Route path="/courses/:id/study-guide" element={<StudyGuide />} />
        <Route path="/search" element={<Search />} />
        <Route path="/ask/:courseId" element={<Ask />} />
        <Route path="/quiz/:courseId" element={<QuizPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}
