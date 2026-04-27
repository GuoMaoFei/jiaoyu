import { apiClient } from './client';
import type { Material, MaterialListResponse, KnowledgeTreeResponse, KnowledgePoint } from '../types/material';

/** 获取教材列表 */
export const getMaterials = (grade?: string, subject?: string) => {
    const params = new URLSearchParams();
    if (grade) params.set('grade', grade);
    if (subject) params.set('subject', subject);
    return apiClient.get<MaterialListResponse>(`/materials/?${params.toString()}`);
};

/** 获取单个教材详情 */
export const getMaterial = (materialId: string) =>
    apiClient.get<Material>(`/materials/${materialId}`);

/** 获取教材知识树 */
export const getMaterialTree = (materialId: string) =>
    apiClient.get<KnowledgeTreeResponse>(`/materials/${materialId}/tree`);

/** 触发知识树构建 */
export const buildTree = (materialId: string, pdfUrl: string) =>
    apiClient.post('/materials/build-tree', { material_id: materialId, pdf_url: pdfUrl });

/** 创建教材 */
export const createMaterial = (data: { title: string; grade: string; subject: string; version?: string; publisher?: string }) =>
    apiClient.post<Material>('/materials/', data);

/** 删除教材（含知识树、缓存等所有关联数据） */
export const deleteMaterial = (materialId: string) =>
    apiClient.delete(`/materials/${materialId}`);

/** 上传教材 PDF，后台异步构建知识树 */
export const uploadMaterialPdf = (materialId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post(`/materials/${materialId}/upload`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
        timeout: 120000,
    });
};

/** 查询教材处理状态 */
export const getMaterialStatus = (materialId: string) =>
    apiClient.get<any>(`/materials/${materialId}/status`);

/** 获取教材关联的知识点列表 */
export const getMaterialKnowledgePoints = (materialId: string) =>
    apiClient.get<{ material_id: string; knowledge_points: KnowledgePoint[] }>(`/materials/${materialId}/knowledge-points`);

/** 获取某学科的知识点树 */
export const getSubjectKnowledgeTree = (subject: string) =>
    apiClient.get<{ subject: string; total_points: number; tree: KnowledgePoint[] }>(`/materials/knowledge-points/tree?subject=${encodeURIComponent(subject)}`);
