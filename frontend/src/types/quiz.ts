export type QuestionType = 'SINGLE_CHOICE' | 'MULTI_CHOICE' | 'FILL_BLANK' | 'SHORT_ANSWER';

export interface QuestionGenerate {
  type: QuestionType;
  question_md: string;
  options?: string[];
  knowledge_points: string[];
  difficulty: number;
}

export interface QuestionWithAnswer {
  type: QuestionType;
  question_md: string;
  options?: string[];
  correct_answer: string;
  solution_steps: string;
  knowledge_points: string[];
  difficulty: number;
}

export interface QuestionResult {
  question_index: number;
  type: QuestionType;
  question_md: string;
  options?: string[];
  student_answer: string;
  correct_answer: string;
  is_correct: boolean;
  solution_steps: string;
  knowledge_points: string[];
}

export interface QuizPaper {
  id: string;
  node_id: string;
  node_title: string;
  is_key_node: boolean;
  question_count: number;
  time_limit_min: number;
  difficulty_level: string;
  questions: QuestionGenerate[];
  created_at: string;
}

export interface QuizPaperWithAnswers {
  id: string;
  node_id: string;
  node_title: string;
  is_key_node: boolean;
  question_count: number;
  time_limit_min: number;
  difficulty_level: string;
  questions: QuestionWithAnswer[];
  created_at: string;
}

export interface QuizAnswer {
  question_index: number;
  answer: string;
}

export interface NodeHealthChange {
  before: number;
  after: number;
  change: number;
}

export interface QuizResult {
  quiz_id: string;
  score: number;
  accuracy_pct: number;
  time_used_sec: number;
  per_question: QuestionResult[];
  node_health_change: NodeHealthChange;
}

export interface QuizHistoryItem {
  id: string;
  score: number | null;
  accuracy_pct: number | null;
  question_count: number;
  time_used_sec: number | null;
  created_at: string;
}

export const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  SINGLE_CHOICE: '单选题',
  MULTI_CHOICE: '多选题',
  FILL_BLANK: '填空题',
  SHORT_ANSWER: '简答题',
};

export const QUESTION_TYPE_ICONS: Record<QuestionType, string> = {
  SINGLE_CHOICE: '🔘',
  MULTI_CHOICE: '☑️',
  FILL_BLANK: '✏️',
  SHORT_ANSWER: '📝',
};
