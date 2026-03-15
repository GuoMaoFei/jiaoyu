import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Radio, Checkbox, Input, Card, Tag, Modal, Spin, message } from 'antd';
import { LeftOutlined, RightOutlined, CheckCircleOutlined, ClockCircleOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { useAuthStore } from '../../stores/useAuthStore';
import { generateQuiz, submitQuiz, getUnfinishedQuiz, saveQuizProgress } from '../../api/quiz';
import type { QuizPaper, QuizAnswer } from '../../types/quiz';

function formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

const TYPE_LABELS: Record<string, string> = {
    SINGLE_CHOICE: '单选题',
    MULTI_CHOICE: '多选题',
    FILL_BLANK: '填空题',
    SHORT_ANSWER: '简答题',
};

const TYPE_ICONS: Record<string, string> = {
    SINGLE_CHOICE: '🔘',
    MULTI_CHOICE: '☑️',
    FILL_BLANK: '✏️',
    SHORT_ANSWER: '📝',
};

const NodeQuiz: React.FC = () => {
    const { nodeId } = useParams<{ nodeId: string }>();
    const navigate = useNavigate();
    const { user } = useAuthStore();

    const [paper, setPaper] = useState<QuizPaper | null>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [quizId, setQuizId] = useState<string>('');

    const [currentIndex, setCurrentIndex] = useState(0);
    const [answers, setAnswers] = useState<Record<number, string>>({});
    const [timeLeft, setTimeLeft] = useState(0);
    const [startTime] = useState(Date.now());
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // 检查是否有未完成的测试
    useEffect(() => {
        if (!user?.id || !nodeId) return;
        
        const checkUnfinished = async () => {
            try {
                const unfinished = await getUnfinishedQuiz(user.id, nodeId);
                if (unfinished) {
                    Modal.confirm({
                        title: '检测到未完成的测试',
                        content: '是否继续上次的答题进度？',
                        okText: '继续答题',
                        cancelText: '重新开始',
                        onOk: () => {
                            // 继续未完成的测试
                            setPaper(unfinished);
                            setQuizId(unfinished.id);
                            setTimeLeft(unfinished.time_limit_min * 60);
                            
                            // 从 localStorage 恢复进度
                            const saved = localStorage.getItem(`quiz_progress_${unfinished.id}`);
                            if (saved) {
                                const progress = JSON.parse(saved);
                                setAnswers(progress.answers || {});
                                setCurrentIndex(progress.currentIndex || 0);
                            }
                        },
                        onCancel: () => {
                            // 重新生成新测试
                            loadNewQuiz();
                        },
                    });
                } else {
                    loadNewQuiz();
                }
            } catch {
                loadNewQuiz();
            }
        };
        
        checkUnfinished();
    }, [user?.id, nodeId]);

    const loadNewQuiz = () => {
        if (!user?.id || !nodeId) return;
        generateQuiz(user.id, nodeId)
            .then(res => {
                setPaper(res);
                setQuizId(res.id);
                setTimeLeft(res.time_limit_min * 60);
                localStorage.removeItem(`quiz_progress_${res.id}`);
            })
            .catch(err => {
                const errMsg = err.message || '';
                if (errMsg.includes('未完成的测试')) {
                    message.warning('已有未完成的测试，正在加载...');
                    getUnfinishedQuiz(user.id, nodeId)
                        .then(unfinished => {
                            if (unfinished) {
                                setPaper(unfinished);
                                setQuizId(unfinished.id);
                                setTimeLeft(unfinished.time_limit_min * 60);
                                const saved = localStorage.getItem(`quiz_progress_${unfinished.id}`);
                                if (saved) {
                                    const progress = JSON.parse(saved);
                                    setAnswers(progress.answers || {});
                                    setCurrentIndex(progress.currentIndex || 0);
                                }
                            }
                        })
                        .finally(() => setLoading(false));
                } else {
                    message.error('获取题目失败：' + errMsg);
                    navigate(-1);
                }
            })
            .finally(() => setLoading(false));
    };

    // 自动保存进度（切题时）
    const autoSaveProgress = useCallback(async () => {
        if (!quizId || Object.keys(answers).length === 0) return;
        
        try {
            await saveQuizProgress(quizId, answers, currentIndex);
            // 同时保存到 localStorage 作为备份
            localStorage.setItem(`quiz_progress_${quizId}`, JSON.stringify({
                answers,
                currentIndex,
                savedAt: new Date().toISOString()
            }));
        } catch (err) {
            console.error('保存进度失败:', err);
        }
    }, [quizId, answers, currentIndex]);

    // 切题时自动保存
    useEffect(() => {
        if (paper && quizId) {
            autoSaveProgress();
        }
    }, [currentIndex, autoSaveProgress]);

    const handleAutoSubmit = useCallback(() => {
        Modal.warning({
            title: '⏰ 时间到！',
            content: '考试时间已用完，系统自动提交。',
            onOk: () => doSubmit(),
        });
    }, [paper, answers, user]);

    useEffect(() => {
        if (!paper || paper.time_limit_min <= 0) return;
        if (timerRef.current) clearInterval(timerRef.current);

        timerRef.current = setInterval(() => {
            setTimeLeft((prev) => {
                if (prev <= 1) {
                    clearInterval(timerRef.current!);
                    handleAutoSubmit();
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, [paper, handleAutoSubmit]);

    // 离开页面时保存进度
    useEffect(() => {
        const handleBeforeUnload = () => {
            if (quizId && Object.keys(answers).length > 0) {
                autoSaveProgress();
            }
        };
        
        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => {
            window.removeEventListener('beforeunload', handleBeforeUnload);
        };
    }, [quizId, answers, autoSaveProgress]);

    const doSubmit = async () => {
        if (timerRef.current) clearInterval(timerRef.current);
        if (!paper || !user) return;

        setSubmitting(true);
        const timeUsed = Math.floor((Date.now() - startTime) / 1000);
        const formattedAnswers: QuizAnswer[] = Object.entries(answers).map(([idx, ans]) => ({
            question_index: parseInt(idx),
            answer: ans,
        }));

        try {
            const res = await submitQuiz(paper.id, user.id, formattedAnswers, timeUsed);
            sessionStorage.setItem('quiz_result', JSON.stringify(res));
            // 清除进度记录
            localStorage.removeItem(`quiz_progress_${paper.id}`);
            navigate(`/quiz-result/${paper.id}`);
        } catch (err: any) {
            message.error('提交失败：' + err.message);
            setSubmitting(false);
        }
    };

    const handleSubmit = () => {
        if (!paper) return;
        const unanswered = paper.questions.filter((_, i) => !answers[i]).length;
        Modal.confirm({
            title: '确认提交',
            content: unanswered > 0
                ? `还有 ${unanswered} 道题未作答，确认提交吗？`
                : '所有题目已作答，确认提交？',
            okText: '提交',
            cancelText: '继续答题',
            onOk: () => doSubmit(),
        });
    };

    const handleAnswer = (value: string) => {
        setAnswers((prev) => ({ ...prev, [currentIndex]: value }));
    };

    const handleMultiAnswer = (values: string[]) => {
        setAnswers((prev) => ({ ...prev, [currentIndex]: values.sort().join('') }));
    };

    if (loading || !paper) {
        return (
            <div className="flex items-center justify-center h-screen">
                <Spin size="large" tip="正在生成微测题目..." />
            </div>
        );
    }

    const currentQ = paper.questions[currentIndex];
    const totalQ = paper.questions.length;
    const timeColor = timeLeft < 60 ? '#ef4444' : timeLeft < 300 ? '#eab308' : '#3b82f6';

    return (
        <div className="flex flex-col h-screen bg-slate-50">
            <div className="px-6 pt-4 pb-3 border-b border-slate-200 bg-white">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} />
                        <div>
                            <h1 className="text-lg font-bold text-slate-800">📝 知识点微测</h1>
                            <span className="text-sm text-slate-500">{paper.node_title}</span>
                        </div>
                    </div>
                    {paper.is_key_node && (
                        <Tag color="gold" className="rounded-full">⭐ 重点章节</Tag>
                    )}
                    <div className="flex items-center gap-2 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100" style={{ color: timeColor }}>
                        <ClockCircleOutlined />
                        <span className="text-xl font-mono font-bold">{formatTime(timeLeft)}</span>
                    </div>
                </div>

                <div className="flex gap-1.5 mt-4 flex-wrap">
                    {paper.questions.map((q, i) => (
                        <button
                            key={i}
                            onClick={() => setCurrentIndex(i)}
                            className={`w-8 h-8 rounded-lg text-xs font-medium transition-all cursor-pointer border shadow-sm ${
                                i === currentIndex
                                    ? 'bg-blue-500 text-white border-blue-500'
                                    : answers[i]
                                        ? 'bg-green-50 text-green-700 border-green-300'
                                        : 'bg-white text-slate-500 border-slate-200 hover:border-blue-300'
                            }`}
                        >
                            {i + 1}
                        </button>
                    ))}
                </div>
            </div>

            <div className="flex-1 overflow-auto px-6 py-6">
                <Card className="rounded-xl max-w-3xl mx-auto shadow-sm border-0">
                    <div className="flex items-center gap-2 mb-5 pb-3 border-b border-slate-100">
                        <Tag color="blue" className="rounded-full px-3">第 {currentIndex + 1} 题</Tag>
                        <Tag className="rounded-full">{TYPE_LABELS[currentQ.type] || currentQ.type}</Tag>
                        <span className="text-xs text-slate-400">难度：{'⭐'.repeat(Math.min(currentQ.difficulty, 5))}</span>
                    </div>

                    <div className="prose prose-slate max-w-none text-base leading-relaxed mb-8">
                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                            {currentQ.question_md}
                        </ReactMarkdown>
                    </div>

                    {currentQ.type === 'SINGLE_CHOICE' && currentQ.options && (
                        <Radio.Group
                            value={answers[currentIndex]}
                            onChange={(e) => handleAnswer(e.target.value)}
                            className="w-full"
                        >
                            <div className="space-y-3">
                                {currentQ.options.map((opt) => (
                                    <div
                                        key={opt}
                                        className={`p-4 rounded-xl border transition-all cursor-pointer ${
                                            answers[currentIndex] === opt
                                                ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-100'
                                                : 'border-slate-200 hover:border-blue-300 hover:shadow-sm bg-white'
                                        }`}
                                    >
                                        <Radio value={opt} className="w-full">
                                            <span className="text-base ml-1">{opt}</span>
                                        </Radio>
                                    </div>
                                ))}
                            </div>
                        </Radio.Group>
                    )}

                    {currentQ.type === 'MULTI_CHOICE' && currentQ.options && (
                        <Checkbox.Group
                            value={(answers[currentIndex] || '').split('')}
                            onChange={(vals) => handleMultiAnswer(vals as string[])}
                            className="w-full"
                        >
                            <div className="space-y-3">
                                {currentQ.options.map((opt) => (
                                    <div
                                        key={opt}
                                        className={`p-4 rounded-xl border transition-all cursor-pointer ${
                                            (answers[currentIndex] || '').includes(opt)
                                                ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-100'
                                                : 'border-slate-200 hover:border-blue-300 hover:shadow-sm bg-white'
                                        }`}
                                    >
                                        <Checkbox value={opt} className="w-full">
                                            <span className="text-base ml-1">{opt}</span>
                                        </Checkbox>
                                    </div>
                                ))}
                            </div>
                        </Checkbox.Group>
                    )}

                    {currentQ.type === 'FILL_BLANK' && (
                        <Input
                            size="large"
                            placeholder="请输入答案…"
                            value={answers[currentIndex] || ''}
                            onChange={(e) => handleAnswer(e.target.value)}
                            className="rounded-xl shadow-sm text-base py-3"
                        />
                    )}

                    {currentQ.type === 'SHORT_ANSWER' && (
                        <Input.TextArea
                            rows={6}
                            placeholder="请输入你的解答步骤或思路…"
                            value={answers[currentIndex] || ''}
                            onChange={(e) => handleAnswer(e.target.value)}
                            className="rounded-xl shadow-sm text-base p-4"
                        />
                    )}
                </Card>
            </div>

            <div className="px-6 py-4 border-t border-slate-200 bg-white flex items-center justify-between shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)] z-10">
                <Button
                    size="large"
                    icon={<LeftOutlined />}
                    disabled={currentIndex === 0}
                    onClick={() => setCurrentIndex((i) => i - 1)}
                    className="rounded-xl"
                >
                    上一题
                </Button>
                <span className="text-sm font-medium text-slate-500 bg-slate-100 px-3 py-1 rounded-full">
                    已答 {Object.keys(answers).length} / {totalQ}
                </span>
                {currentIndex < totalQ - 1 ? (
                    <Button
                        type="primary"
                        size="large"
                        icon={<RightOutlined />}
                        onClick={() => setCurrentIndex((i) => i + 1)}
                        className="rounded-xl shadow-md shadow-blue-500/20"
                    >
                        下一题
                    </Button>
                ) : (
                    <Button
                        type="primary"
                        size="large"
                        icon={<CheckCircleOutlined />}
                        onClick={handleSubmit}
                        loading={submitting}
                        className="rounded-xl bg-gradient-to-r from-red-500 to-rose-500 border-0 shadow-md shadow-red-500/20"
                    >
                        交卷
                    </Button>
                )}
            </div>
        </div>
    );
};

export default NodeQuiz;
