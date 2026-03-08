/** 节点健康度 — 对应后端 NodeHealthResponse */
export interface NodeState {
    node_id: string;
    node_title?: string;
    is_unlocked: boolean;
    health_score: number;
}

/** 学生档案 — 对应后端 StudentProfileResponse */
export interface StudentProfile {
    id: string;
    nickname: string;
    grade: string;
    avg_health_score?: number;
    weak_nodes?: NodeState[];
    total_nodes_studied?: number;
    active_mistakes_count?: number;
}

/** 书架条目 — 对应后端 BookshelfItemResponse (统一视图) */
export interface BookshelfItem {
    activation_id?: string;
    material_id: string;
    material_title: string;
    grade?: string;
    subject?: string;
    node_count: number;
    progress_pct: number;
    health_score: number;
    activated_at?: string;
    is_activated: boolean;
}

/** 书架响应 */
export interface BookshelfResponse {
    student_id: string;
    books: BookshelfItem[];
}
