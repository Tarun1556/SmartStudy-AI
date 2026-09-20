import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api/client";
import type {
  Course, CourseStats, DashboardStats, Lecture, LectureNote,
  Topic, TopicDetail, TopicTimeline, TopicMention, StudyGuide,
  SearchResponse, AskResponse, Quiz, QuizAttempt, ProcessingJob, KnowledgeMap,
} from "@/types";

export const useCourses = () =>
  useQuery({
    queryKey: ["courses"],
    queryFn: async () => {
      const res = await api.get("/api/courses");
      return res.data as Course[];
    },
  });

export const useCourse = (id: number | null | undefined) =>
  useQuery({
    queryKey: ["course", id],
    enabled: !!id,
    queryFn: async () => {
      const res = await api.get(`/api/courses/${id}`);
      return res.data as Course;
    },
  });

export const useCourseStats = (id: number | null | undefined) =>
  useQuery({
    queryKey: ["course-stats", id],
    enabled: !!id,
    queryFn: async () => {
      const res = await api.get(`/api/courses/${id}/stats`);
      return res.data as CourseStats;
    },
  });

export const useCreateCourse = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string; color?: string }) =>
      api.post("/api/courses", data).then((r) => r.data as Course),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["courses", "dashboard"] }),
  });
};

export const useUpdateCourse = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: number } & any) =>
      api.put(`/api/courses/${id}`, data).then((r) => r.data as Course),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["courses", "course", "dashboard"] }),
  });
};

export const useDeleteCourse = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/api/courses/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["courses", "dashboard"] }),
  });
};

export const useLectures = (courseId?: number | null) =>
  useQuery({
    queryKey: ["lectures", courseId ?? "all"],
    queryFn: async () => {
      const params = courseId ? { params: { course_id: courseId } } : {};
      const res = await api.get("/api/lectures", params);
      return res.data as Lecture[];
    },
  });

export const useLecture = (id: number | null | undefined) =>
  useQuery({
    queryKey: ["lecture", id],
    enabled: !!id,
    queryFn: async () => {
      const res = await api.get(`/api/lectures/${id}`);
      return res.data as Lecture;
    },
  });

export const useLectureStatus = (id: number | null | undefined, refetchInterval = 2000) =>
  useQuery({
    queryKey: ["lecture-status", id],
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data as ProcessingJob | undefined;
      if (!data) return refetchInterval;
      if (data.status === "completed" || data.status === "failed") return false;
      return refetchInterval;
    },
    queryFn: async () => {
      const res = await api.get(`/api/lectures/${id}/status`);
      return res.data as ProcessingJob;
    },
  });

export const useLectureNotes = (id: number | null | undefined) =>
  useQuery({
    queryKey: ["lecture-notes", id],
    enabled: !!id,
    queryFn: async () => {
      const res = await api.get(`/api/lectures/${id}/notes`);
      return res.data as LectureNote;
    },
    retry: 1,
  });

export const useUploadLecture = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (form: FormData) =>
      api
        .post("/api/lectures/upload", form, {
          headers: { "Content-Type": "multipart/form-data" },
        })
        .then((r) => r.data as { lecture_id: number; job_id: number; message: string }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lectures", "dashboard"] }),
  });
};

export const useCreateLecture = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: any) =>
      api.post("/api/lectures", data).then((r) => r.data as Lecture),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lectures", "dashboard"] }),
  });
};

export const useRetryLectureProcessing = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (lectureId: number) =>
      api.post(`/api/lectures/${lectureId}/retry`).then((r) => r.data as ProcessingJob),
    onSuccess: (_data, lectureId) => {
      qc.invalidateQueries({ queryKey: ["lecture-status", lectureId] });
      qc.invalidateQueries({ queryKey: ["lecture", lectureId] });
      qc.invalidateQueries({ queryKey: ["lectures", "dashboard"] });
    },
  });
};

export const useCourseTopics = (courseId: number | null | undefined, minCoverage = 0) =>
  useQuery({
    queryKey: ["topics", courseId, minCoverage],
    enabled: !!courseId,
    queryFn: async () => {
      const res = await api.get(`/api/courses/${courseId}/topics`, {
        params: { min_coverage: minCoverage, limit: 100 },
      });
      return res.data as Topic[];
    },
  });

export const useTopicDetail = (topicId: number | null | undefined) =>
  useQuery({
    queryKey: ["topic-detail", topicId],
    enabled: !!topicId,
    queryFn: async () => {
      const res = await api.get(`/api/topics/${topicId}`);
      return res.data as TopicDetail;
    },
  });

export const useTopicTimeline = (topicId: number | null | undefined) =>
  useQuery({
    queryKey: ["topic-timeline", topicId],
    enabled: !!topicId,
    queryFn: async () => {
      const res = await api.get(`/api/topics/${topicId}/timeline`);
      return res.data as TopicTimeline;
    },
  });

export const useTopicEvidence = (topicId: number | null | undefined) =>
  useQuery({
    queryKey: ["topic-evidence", topicId],
    enabled: !!topicId,
    queryFn: async () => {
      const res = await api.get(`/api/topics/${topicId}/evidence`);
      return res.data as TopicMention[];
    },
  });

export const useKnowledgeMap = (courseId: number | null | undefined) =>
  useQuery({
    queryKey: ["knowledge-map", courseId],
    enabled: !!courseId,
    queryFn: async () => {
      const res = await api.get(`/api/courses/${courseId}/knowledge-map`);
      return res.data as KnowledgeMap;
    },
  });

export const useStudyGuide = (courseId: number | null | undefined) =>
  useQuery({
    queryKey: ["study-guide", courseId],
    enabled: !!courseId,
    queryFn: async () => {
      const res = await api.get(`/api/courses/${courseId}/study-guide`);
      return res.data as StudyGuide;
    },
  });

export const useRegenerateStudyGuide = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (courseId: number) =>
      api.post(`/api/courses/${courseId}/study-guide/regenerate`).then((r) => r.data as StudyGuide),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["study-guide"] }),
  });
};

export const studyGuidePdfUrl = (courseId: number) => {
  const token = localStorage.getItem("studyai_token");
  return `${api.defaults.baseURL}/api/courses/${courseId}/study-guide/pdf${token ? `?auth=${encodeURIComponent(token)}` : ""}`;
};

export const useSearch = (params: { q: string; courseId?: number; mode?: string; enabled?: boolean }) => {
  const { q, courseId, mode = "hybrid", enabled = true } = params;
  return useQuery({
    queryKey: ["search", q, courseId, mode],
    enabled: enabled && !!q && q.length > 0,
    queryFn: async () => {
      const query: any = { q, mode, limit: 30 };
      if (courseId) query.course_id = courseId;
      const res = await api.get("/api/search", { params: query });
      return res.data as SearchResponse;
    },
  });
};

export const useAskQuestion = () =>
  useMutation({
    mutationFn: ({ courseId, question, sessionId }: { courseId: number; question: string; sessionId?: number }) =>
      api
        .post("/api/ask", { course_id: courseId, question, session_id: sessionId })
        .then((r) => r.data as AskResponse),
  });

export const useGenerateQuiz = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ courseId, numQuestions, topicIds, quizType }: any) =>
      api
        .post("/api/quiz/generate", {
          course_id: courseId,
          num_questions: numQuestions ?? 10,
          topic_ids: topicIds,
          quiz_type: quizType ?? "mcq",
        })
        .then((r) => r.data as Quiz),
  });
};

export const useQuiz = (id: number | null | undefined) =>
  useQuery({
    queryKey: ["quiz", id],
    enabled: !!id,
    queryFn: async () => {
      const res = await api.get(`/api/quiz/${id}`);
      return res.data as Quiz;
    },
  });

export const useCourseQuizzes = (courseId: number | null | undefined) =>
  useQuery({
    queryKey: ["quizzes", courseId],
    enabled: !!courseId,
    queryFn: async () => {
      const res = await api.get(`/api/quiz/list/${courseId}`);
      return res.data as Quiz[];
    },
  });

export const useQuizAttempts = (quizId: number | null | undefined) =>
  useQuery({
    queryKey: ["quiz-attempts", quizId],
    enabled: !!quizId,
    queryFn: async () => {
      const res = await api.get(`/api/quiz/${quizId}/attempts`);
      return res.data as QuizAttempt[];
    },
  });

export const useSubmitQuizAttempt = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ quizId, answers }: { quizId: number; answers: Record<number, number> }) =>
      api.post(`/api/quiz/${quizId}/attempts`, { answers }).then((r) => r.data as QuizAttempt),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["quiz-attempts", vars.quizId] });
      qc.invalidateQueries({ queryKey: ["quizzes"] });
    },
  });
};

export const useDashboard = () =>
  useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => {
      const res = await api.get("/api/dashboard");
      return res.data as DashboardStats;
    },
  });
