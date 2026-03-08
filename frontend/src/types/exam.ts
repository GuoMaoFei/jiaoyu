/** 题目类型枚举 */
export type QuestionType = 'SINGLE_CHOICE' | 'MULTI_CHOICE' | 'FILL_BLANK' | 'SHORT_ANSWER';

/** 题型显示信息 */
export const QUESTION_TYPE_META: Record<QuestionType, { label: string; icon: string }> = {
    SINGLE_CHOICE: { label: '单选题', icon: '🔘' },
    MULTI_CHOICE: { label: '多选题', icon: '☑️' },
    FILL_BLANK: { label: '填空题', icon: '✏️' },
    SHORT_ANSWER: { label: '简答题', icon: '📝' },
};

/** 单道题目 */
export interface Question {
    id: string;
    type: QuestionType;
    question_md: string;
    options?: string[];        // 选择题选项 A/B/C/D
    correct_answer?: string;   // 正确答案（批改后可见）
    node_id?: string;          // 关联知识节点
    node_title?: string;
}

/** 试卷 */
export interface ExamPaper {
    id: string;
    title: string;
    questions: Question[];
    total_score: number;
    time_limit_min: number;    // 0 = 不限时
}

/** 学生答题记录（单题） */
export interface ExamAnswer {
    question_id: string;
    student_answer: string;
}

/** 单题批改结果 */
export interface QuestionResult {
    question_id: string;
    question_md: string;
    question_type: QuestionType;
    student_answer: string;
    correct_answer: string;
    is_correct: boolean;
    explanation?: string;       // Agent 解析
    node_id?: string;
    node_title?: string;
}

/** 考试总结果 */
export interface ExamResult {
    exam_id: string;
    title: string;
    score: number;
    total_score: number;
    correct_count: number;
    total_count: number;
    accuracy_pct: number;
    time_used_sec: number;
    per_question: QuestionResult[];
    node_changes?: { node_id: string; node_title: string; before: number; after: number }[];
}
