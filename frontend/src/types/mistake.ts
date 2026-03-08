/** 错题状态枚举 — 对应后端 MistakeStatus */
export type MistakeStatus = 'ACTIVE' | 'REVIEWING' | 'MASTERED';

/** 错题状态显示映射 */
export const MISTAKE_STATUS_META: Record<MistakeStatus, { label: string; color: string; icon: string }> = {
    ACTIVE: { label: '未解决', color: '#ef4444', icon: '❌' },
    REVIEWING: { label: '复习中', color: '#eab308', icon: '🔄' },
    MASTERED: { label: '已攻克', color: '#22c55e', icon: '✅' },
};

/** 学生错题 — 对应后端 StudentMistake ORM */
export interface StudentMistake {
    id: string;
    student_id: string;
    node_id: string;
    node_title?: string;
    original_question_id?: string;
    error_reason?: string;
    consecutive_correct_count: number;
    status: MistakeStatus;
    next_review_date?: string;
    created_at: string;
    updated_at: string;
}

/** 错题列表响应 */
export interface MistakeListResponse {
    student_id: string;
    mistakes: StudentMistake[];
    total: number;
}
