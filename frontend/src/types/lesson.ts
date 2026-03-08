/** 五步闯关步骤枚举 */
export type LessonStep =
    | 'IMPORT'
    | 'EXPLAIN'
    | 'EXAMPLE'
    | 'PRACTICE'
    | 'SUMMARY'
    | 'COMPLETED';

/** 闯关步骤显示信息 */
export const LESSON_STEP_META: Record<LessonStep, { label: string; icon: string; order: number }> = {
    IMPORT: { label: '基础预热', icon: '🔥', order: 0 },
    EXPLAIN: { label: '深入讲解', icon: '📖', order: 1 },
    EXAMPLE: { label: '典型例题', icon: '✏️', order: 2 },
    PRACTICE: { label: '上手实操', icon: '🎯', order: 3 },
    SUMMARY: { label: '总结复盘', icon: '🏆', order: 4 },
    COMPLETED: { label: '已完成', icon: '✅', order: 5 },
};

/** 闯关状态响应 — 对齐后端 LessonStatusResponse */
export interface LessonStatusResponse {
    lesson_id: string;
    student_id?: string;
    node_id?: string;
    material_id?: string;
    current_step: LessonStep;
    is_completed: boolean;
    node_title?: string;
    content_preview?: string;
    step_prompt?: string;
    message?: string;
    error?: string;
}

/** 学习计划任务类型 */
export type TaskType = 'LEARN_NEW' | 'DO_QUIZ' | 'REVIEW_VARIANT';

export interface PlanItem {
    id: string;
    type: TaskType;
    title: string;
    completed: boolean;
    duration_min: number;
    date: string; // YYYY-MM-DD
}

export interface PlanListResponse {
    student_id: string;
    items: PlanItem[];
}
