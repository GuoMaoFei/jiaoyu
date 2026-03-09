import { apiClient } from './client';
import type { QuizPaper, QuizPaperWithAnswers, QuizAnswer, QuizResult, QuizHistoryItem } from '../types/quiz';

export const generateQuiz = (studentId: string, nodeId: string) =>
  apiClient.post<QuizPaper>('/quizzes/generate', {
    student_id: studentId,
    node_id: nodeId,
  });

export const submitQuiz = (
  quizId: string,
  studentId: string,
  answers: QuizAnswer[],
  timeUsedSec: number
) =>
  apiClient.post<QuizResult>('/quizzes/submit', {
    quiz_id: quizId,
    student_id: studentId,
    answers,
    time_used_sec: timeUsedSec,
  });

export const getQuizHistory = (studentId: string, nodeId: string) =>
  apiClient.get<QuizHistoryItem[]>(`/quizzes/history/${studentId}/${nodeId}`);

export const getQuizDetail = (quizId: string) =>
  apiClient.get<QuizPaperWithAnswers>(`/quizzes/${quizId}`);

export const getUnfinishedQuiz = (studentId: string, nodeId: string) =>
  apiClient.get<QuizPaper>(`/quizzes/unfinished/${studentId}/${nodeId}`);

export const saveQuizProgress = (
  quizId: string,
  answers: Record<number, string>,
  currentIndex: number
) =>
  apiClient.post<{ status: string; message: string }>('/quizzes/save-progress', {
    quiz_id: quizId,
    answers: Object.entries(answers).map(([idx, ans]) => ({
      question_index: parseInt(idx),
      answer: ans,
    })),
    current_index: currentIndex,
  });
