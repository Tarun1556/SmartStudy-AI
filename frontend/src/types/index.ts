export interface User {
  id: number;
  email: string;
  full_name: string | null;
  is_demo: boolean;
  created_at: string;
}

export interface Course {
  id: number;
  user_id: number;
  name: string;
  description: string | null;
  color: string;
  created_at: string;
  updated_at: string;
}

export interface CourseStats {
  id: number;
  name: string;
  color: string;
  lecture_count: number;
  topic_count: number;
  last_updated: string;
}

export interface ProcessingJob {
  id: number;
  lecture_id: number;
  job_type: string;
  status: "queued" | "processing" | "completed" | "failed";
  current_step: string | null;
  progress: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface Lecture {
  id: number;
  course_id: number;
  title: string;
  lecture_number: number | null;
  lecture_date: string | null;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  latest_job?: ProcessingJob | null;
}

export interface TranscriptSegment {
  id: number;
  segment_index: number;
  text: string;
  start_time: number | null;
  end_time: number | null;
  source_type: string;
}

export interface LectureNote {
  id: number;
  lecture_id: number;
  title: string | null;
  overview: string | null;
  headings: any[] | null;
  key_ideas: any[] | null;
  definitions: any[] | null;
  examples: any[] | null;
  relationships: any[] | null;
  source_references: any[] | null;
}

export interface Topic {
  id: number;
  course_id: number;
  name: string;
  canonical_name: string;
  description: string | null;
  coverage_score: number;
  lecture_count: number;
  evidence_count: number;
  aliases: string[] | null;
  related_topics: any[] | null;
}

export interface TopicMention {
  id: number;
  topic_id: number;
  lecture_id: number;
  context: string;
  start_time: number | null;
  source_type: string;
  confidence: number;
  lecture_title?: string | null;
  lecture_number?: number | null;
}

export interface EvidenceSnippet {
  lecture_id: number;
  lecture_title: string;
  lecture_number: number | null;
  context: string;
  start_time: number | null;
  source_type: string;
}

export interface TopicDetail {
  topic: Topic;
  evidence: EvidenceSnippet[];
  related: Topic[];
}

export interface TopicTimelineEvent {
  lecture_id: number;
  lecture_number: number | null;
  lecture_title: string;
  lecture_date?: string | null;
  event_type: string;
  context: string;
  evidence_count: number;
}

export interface TopicTimeline {
  topic_id: number;
  topic_name: string;
  events: TopicTimelineEvent[];
}

export interface KnowledgeMapNode {
  id: number;
  label: string;
  size: number;
  coverage_score: number;
  lecture_count: number;
}

export interface KnowledgeMapEdge {
  source: number;
  target: number;
  weight: number;
}

export interface KnowledgeMap {
  nodes: KnowledgeMapNode[];
  edges: KnowledgeMapEdge[];
}

export interface StudyGuideTopic {
  topic_id: number;
  name: string;
  coverage_score: number;
  lecture_count: number;
  evidence_count: number;
  summary: string | null;
  lectures: Array<{ id: number; title: string }>;
}

export interface StudyGuide {
  id: number;
  course_id: number;
  version: number;
  title: string;
  content: any;
  top_topics: StudyGuideTopic[] | null;
  generated_at: string;
}

export interface SearchResult {
  document_id: number;
  doc_type: string;
  lecture_id: number | null;
  lecture_title: string | null;
  title: string;
  snippet: string;
  relevance_score: number;
  source_reference: string | null;
}

export interface SearchResponse {
  query: string;
  search_mode: string;
  results: SearchResult[];
  total: number;
}

export interface Citation {
  lecture_id: number;
  lecture_title: string;
  lecture_number: number | null;
  snippet: string;
  start_time: number | null;
}

export interface AskResponse {
  answer: string;
  citations: Citation[];
  session_id: number;
  found_in_material: boolean;
}

export interface QuizQuestion {
  id: number;
  question_type: string;
  question_text: string;
  options: string[] | null;
  correct_answer: string | null;
  explanation: string | null;
  source_lecture_id: number | null;
  source_context: string | null;
}

export interface Quiz {
  id: number;
  course_id: number;
  title: string;
  quiz_type: string;
  generated_at: string;
  questions: QuizQuestion[];
}

export interface QuizAttempt {
  id: number;
  quiz_id: number;
  score: number;
  total_questions: number;
  answers: Record<string, number> | null;
  completed_at: string;
}

export interface DashboardStats {
  total_courses: number;
  total_lectures: number;
  total_topics: number;
  processing_jobs: number;
  frequently_covered: Topic[];
  recent_jobs: ProcessingJob[];
  course_stats: CourseStats[];
}
