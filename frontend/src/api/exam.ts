import { apiClient } from './client';
import type { ExamPaper, ExamResult } from '../types/exam';

export interface GenerateExamRequest {
    student_id: string;
    material_id: string;
    exam_type?: 'diagnostic' | 'unit_test';
}

export interface GenerateExamResponse {
    status: string;
    paper: ExamPaper;
}

export interface SubmitExamRequest {
    student_id: string;
    exam_id: string;
    paper_metadata: any;
    answers: { question_id: string; student_answer: string }[];
    time_used_sec: number;
}

export interface SubmitExamResponse {
    status: string;
    exam_result: ExamResult;
}

export const generateExam = async (req: GenerateExamRequest): Promise<GenerateExamResponse> => {
    const data = await apiClient.post<GenerateExamResponse>('/exams/generate', req) as unknown as GenerateExamResponse;
    return data;
};

export const submitExam = async (req: SubmitExamRequest): Promise<SubmitExamResponse> => {
    const data = await apiClient.post<SubmitExamResponse>('/exams/submit', req) as unknown as SubmitExamResponse;
    return data;
};

export const getExamResult = async (examId: string): Promise<SubmitExamResponse> => {
    const data = await apiClient.get<SubmitExamResponse>(`/exams/${examId}/result`) as unknown as SubmitExamResponse;
    return data;
};
