import { apiClient } from './client';
import type { LessonStatusResponse } from '../types/lesson';

/** 开始/恢复闯关学习 */
export const startLesson = (studentId: string, nodeId: string) =>
    apiClient.post<LessonStatusResponse>('/lessons/start', {
        student_id: studentId,
        node_id: nodeId,
    });

/** 推进闯关步骤 */
export const advanceLesson = (studentId: string, nodeId: string) =>
    apiClient.post<LessonStatusResponse>('/lessons/advance', {
        student_id: studentId,
        node_id: nodeId,
    });

/** 获取学习计划 */
export const getStudyPlans = (studentId: string) =>
    apiClient.get<any, import('../types/lesson').PlanListResponse>(`/lessons/plans/${studentId}`);

/** 生成新学习计划 */
export const generateStudyPlan = (studentId: string, materialId: string, startDate?: string, sessionsPerWeek?: number) =>
    apiClient.post<any, { status: string; message: string }>('/lessons/plans/generate', {
        student_id: studentId,
        material_id: materialId,
        start_date: startDate,
        sessions_per_week: sessionsPerWeek,
    });

/** 清除学习计划 */
export const clearStudyPlans = (studentId: string) =>
    apiClient.delete<any, { status: string; message: string }>(`/lessons/plans/${studentId}`);
