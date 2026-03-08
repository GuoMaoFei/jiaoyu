import { create } from 'zustand';
import { type LessonStep, type LessonStatusResponse } from '../types/lesson';

interface LessonStoreState {
    lessonId: string | null;
    nodeId: string | null;
    materialId: string | null;
    currentStep: LessonStep | null;
    isCompleted: boolean;
    nodeTitle: string | null;
    stepPrompt: string | null;
    setLesson: (res: LessonStatusResponse) => void;
    reset: () => void;
}

export const useLessonStore = create<LessonStoreState>((set) => ({
    lessonId: null,
    nodeId: null,
    materialId: null,
    currentStep: null,
    isCompleted: false,
    nodeTitle: null,
    stepPrompt: null,
    setLesson: (res) =>
        set({
            lessonId: res.lesson_id,
            nodeId: res.node_id || null,
            materialId: res.material_id || null,
            currentStep: res.current_step,
            isCompleted: res.is_completed,
            nodeTitle: res.node_title || null,
            stepPrompt: res.step_prompt || null,
        }),
    reset: () =>
        set({
            lessonId: null,
            nodeId: null,
            materialId: null,
            currentStep: null,
            isCompleted: false,
            nodeTitle: null,
            stepPrompt: null,
        }),
}));
