/** 知识点树节点 */
export interface KnowledgePointNode {
    id: string;
    title: string;
    summary: string | null;
    keywords: string | null;
    level: number;
    source_count: number;
    children?: KnowledgePointNode[];
}

/** 学科知识点树响应 */
export interface KnowledgePointTreeResponse {
    subject: string;
    total_points: number;
    tree: KnowledgePointNode[];
}

/** 知识点映射信息 */
export interface KnowledgePointMapping {
    knowledge_node_id: string;
    knowledge_node_title: string;
    material_id: string;
    material_title: string;
    relevance_score: number | null;
    context_snippet: string | null;
}

/** 知识点详情 */
export interface KnowledgePointDetail {
    id: string;
    title: string;
    summary: string | null;
    keywords: string | null;
    level: number;
    subject: string;
    source_count: number;
    parent_id: string | null;
    mappings: KnowledgePointMapping[];
}

/** 知识点搜索结果项 */
export interface KnowledgePointSearchItem {
    id: string;
    title: string;
    summary: string | null;
    level: number;
    source_count: number;
}

/** 知识点搜索响应 */
export interface KnowledgePointSearchResponse {
    subject: string;
    query: string;
    results: KnowledgePointSearchItem[];
}

/** 知识点关联教材项 */
export interface KnowledgePointMaterialItem {
    material_id: string;
    material_title: string;
    node_title: string;
    content_preview: string | null;
}

/** 知识点关联教材响应 */
export interface KnowledgePointMaterialsResponse {
    knowledge_point_id: string;
    knowledge_point_title: string;
    materials: KnowledgePointMaterialItem[];
}
