import React from 'react';
import { LESSON_STEP_META, type LessonStep } from '../../types/lesson';

interface LessonProgressProps {
    currentStep: LessonStep | null;
}

const STEPS_ORDER: LessonStep[] = ['IMPORT', 'EXPLAIN', 'EXAMPLE', 'PRACTICE', 'SUMMARY'];

const LessonProgress: React.FC<LessonProgressProps> = ({ currentStep }) => {
    if (!currentStep) return null;

    const currentOrder = currentStep === 'COMPLETED' ? 5 : (LESSON_STEP_META[currentStep]?.order ?? 0);

    return (
        <div className="flex items-center gap-1 px-4 py-2">
            {STEPS_ORDER.map((step, idx) => {
                const meta = LESSON_STEP_META[step];
                const isCompleted = currentOrder > meta.order;
                const isCurrent = currentStep === step;

                return (
                    <React.Fragment key={step}>
                        {/* 步骤节点 */}
                        <div className="flex flex-col items-center gap-0.5">
                            <div
                                className={`
                  w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300
                  ${isCompleted
                                        ? 'bg-green-500 text-white shadow-sm'
                                        : isCurrent
                                            ? 'bg-blue-500 text-white shadow-md ring-2 ring-blue-200 scale-110'
                                            : 'bg-slate-100 text-slate-400'
                                    }
                `}
                            >
                                {isCompleted ? '✓' : meta.icon}
                            </div>
                            <span
                                className={`text-[10px] whitespace-nowrap transition-colors ${isCurrent ? 'text-blue-600 font-semibold' : 'text-slate-400'
                                    }`}
                            >
                                {meta.label}
                            </span>
                        </div>

                        {/* 连接线 */}
                        {idx < STEPS_ORDER.length - 1 && (
                            <div
                                className={`flex-1 h-0.5 min-w-3 mx-0.5 rounded-full transition-colors duration-300 ${currentOrder > meta.order ? 'bg-green-400' : 'bg-slate-200'
                                    }`}
                            />
                        )}
                    </React.Fragment>
                );
            })}
        </div>
    );
};

export default LessonProgress;
