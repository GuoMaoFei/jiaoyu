import { apiClient } from './client';

/** 生成学情周报 */
export const generateReport = (studentId: string, materialId: string) =>
    apiClient.post('/reports/generate', { student_id: studentId, material_id: materialId });

/** 获取到期复习项 */
export const getDueReviews = (studentId: string) =>
    apiClient.get(`/reviews/due/${studentId}`);

/** 注入复习计划 */
export const injectReviews = (studentId: string) =>
    apiClient.post('/reviews/inject', { student_id: studentId });

/** OCR 图片识别 */
export const ocrExtract = (imageSource: string) =>
    apiClient.post('/ocr/extract', { image_source: imageSource });
