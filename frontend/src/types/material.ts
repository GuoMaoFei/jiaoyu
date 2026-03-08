/** 知识节点 — 对应后端 KnowledgeNodeResponse */
export interface KnowledgeNode {
    id: string;
    title: string;
    level: number;
    seq_num: number;
    parent_id: string | null;
    content_preview: string | null;
    children_count: number;
    /** 前端运行时构建的子节点数组 */
    children?: KnowledgeNode[];
}

/** 知识树响应 */
export interface KnowledgeTreeResponse {
    material_id: string;
    material_title: string;
    nodes: KnowledgeNode[];
    total_nodes: number;
}

/** 教材 — 对应后端 MaterialResponse */
export interface Material {
    id: string;
    title: string;
    grade: string;
    subject: string;
    version: string;
    publisher: string;
    material_type: string;
    created_at: string;
    node_count: number;
}

export interface MaterialListResponse {
    materials: Material[];
    total: number;
}
