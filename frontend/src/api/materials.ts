import { apiClient } from './client';
import type { Material, MaterialListResponse, KnowledgeTreeResponse } from '../types/material';

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

/** 上传教材 PDF 并构建知识树 */
export const uploadMaterialPdf = (materialId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post(`/materials/${materialId}/upload`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
        timeout: 0, // 0 表示不设置超时时间，防止本地大文件解析时间过长被前端掐断
    });
};
