import { apiClient } from './client';
import type {
    KnowledgePointTreeResponse,
    KnowledgePointDetail,
    KnowledgePointSearchResponse,
    KnowledgePointMaterialsResponse,
} from '../types/knowledgePoint';

/** 获取学科知识点树 */
export const getKnowledgePointTree = (subject: string) =>
    apiClient.get<KnowledgePointTreeResponse>(`/knowledge-points/subjects/${encodeURIComponent(subject)}/tree`);

/** 获取知识点详情 */
export const getKnowledgePointDetail = (kpId: string) =>
    apiClient.get<KnowledgePointDetail>(`/knowledge-points/${kpId}`);

/** 搜索知识点 */
export const searchKnowledgePoints = (subject: string, query: string, topK: number = 5) =>
    apiClient.get<KnowledgePointSearchResponse>(
        `/knowledge-points/subjects/${encodeURIComponent(subject)}/search`,
        { params: { q: query, top_k: topK } }
    );

/** 获取知识点关联教材 */
export const getKnowledgePointMaterials = (kpId: string) =>
    apiClient.get<KnowledgePointMaterialsResponse>(`/knowledge-points/${kpId}/materials`);
