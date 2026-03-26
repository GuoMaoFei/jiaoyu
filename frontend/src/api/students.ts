import { apiClient } from './client';
import type { StudentProfile, BookshelfResponse } from '../types/student';
import type { MistakeListResponse, MistakeStatus } from '../types/mistake';

/** 获取学生档案（含记忆覆写层数据） */
export const getStudentProfile = (studentId: string) =>
    apiClient.get<StudentProfile>(`/students/${studentId}/profile`);

/** 获取书架 */
export const getBookshelf = (studentId: string) =>
    apiClient.get<BookshelfResponse, BookshelfResponse>(`/students/${studentId}/bookshelf`);

/** 激活教材（加入书架） */
export const activateBook = (studentId: string, materialId: string) =>
    apiClient.post('/students/activate-book', { student_id: studentId, material_id: materialId });

/** 注册学生 */
export const createStudent = (nickname: string, grade: string, parentId?: string) =>
    apiClient.post<StudentProfile>('/students/', { nickname, grade, parent_id: parentId });

/** 获取错题列表（按教材/状态筛选） */
export const getStudentMistakes = (studentId: string, materialId?: string, status?: MistakeStatus) => {
    const params = new URLSearchParams();
    if (materialId) params.set('material_id', materialId);
    if (status) params.set('status', status);
    return apiClient.get<MistakeListResponse>(`/students/${studentId}/mistakes?${params.toString()}`);
};

/** 获取学生在某教材下全部节点状态 */
export const getNodeStates = (studentId: string, materialId: string) =>
    apiClient.get(`/students/${studentId}/materials/${materialId}/nodes`);
