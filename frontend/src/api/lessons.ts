import { apiClient } from './client';
import type { LessonStatusResponse, PlanListResponse } from '../types/lesson';

/** 开始/恢复闯关学习 */
export const startLesson = (studentId: string, nodeId: string) =>
    apiClient.post('/lessons/start', {
        student_id: studentId,
        node_id: nodeId,
    }) as Promise<LessonStatusResponse>;

/** 推进闯关步骤 */
export const advanceLesson = (studentId: string, nodeId: string) =>
    apiClient.post('/lessons/advance', {
        student_id: studentId,
        node_id: nodeId,
    }) as Promise<LessonStatusResponse>;

/** 获取学习计划 */
export const getStudyPlans = (studentId: string, materialId?: string) => {
    const params = materialId ? `?material_id=${materialId}` : '';
    return apiClient.get(`/lessons/plans/${studentId}${params}`) as Promise<PlanListResponse>;
};

/** 生成新学习计划 */
export const generateStudyPlan = (studentId: string, materialId: string, startDate?: string, sessionsPerWeek?: number) =>
    apiClient.post('/lessons/plans/generate', {
        student_id: studentId,
        material_id: materialId,
        start_date: startDate,
        sessions_per_week: sessionsPerWeek,
    });

/** 清除学习计划 */
export const clearStudyPlans = (studentId: string, materialId?: string) => {
    const params = materialId ? `?material_id=${materialId}` : '';
    return apiClient.delete(`/lessons/plans/${studentId}${params}`);
};
