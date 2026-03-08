import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Radio, Checkbox, Input, Card, Tag, Modal, Spin, message } from 'antd';
import { LeftOutlined, RightOutlined, CheckCircleOutlined, ClockCircleOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import type { ExamPaper } from '../../types/exam';
import { useAuthStore } from '../../stores/useAuthStore';
import { generateExam, submitExam } from '../../api/exam';

function formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

const Exam: React.FC = () => {
    // We treat examId in the route as materialId for generating material-based test papers
    const { examId } = useParams<{ examId: string }>();
    const navigate = useNavigate();
    const { user } = useAuthStore();

    const [paper, setPaper] = useState<ExamPaper | null>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    const [currentIndex, setCurrentIndex] = useState(0);
    const [answers, setAnswers] = useState<Record<string, string>>({});
    const [timeLeft, setTimeLeft] = useState(0);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Initial load
    useEffect(() => {
        if (!user?.id || !examId) return;
        generateExam({ student_id: user.id, material_id: examId, exam_type: 'unit_test' })
            .then(res => {
                setPaper(res.paper);
                setTimeLeft(res.paper.time_limit_min * 60);
            })
            .catch(err => message.error('获取试卷失败：' + err.message))
            .finally(() => setLoading(false));
    }, [user?.id, examId]);

    // Timer logic
    const handleAutoSubmit = useCallback(() => {
        Modal.warning({
            title: '⏰ 时间到！',
            content: '考试时间已用完，系统自动提交试卷。',
            onOk: () => doSubmit(),
        });
    }, [paper, answers, user]);

    useEffect(() => {
        if (!paper || paper.time_limit_min <= 0) return;

        // Clear existing interval if any
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

    const doSubmit = async () => {
        if (timerRef.current) clearInterval(timerRef.current);
        if (!paper || !user) return;

        setSubmitting(true);
        const timeUsed = paper.time_limit_min * 60 - timeLeft;
        const formattedAnswers = Object.entries(answers).map(([qid, ans]) => ({
            question_id: qid, student_answer: ans as string
        }));

        try {
            const res = await submitExam({
                student_id: user.id,
                exam_id: paper.id,
                paper_metadata: paper,
                answers: formattedAnswers,
                time_used_sec: timeUsed
            });
            // Store the result grading provided by backend
            const result = res.exam_result;
            // Also stash the paper so ScoreReport can use it if needed
            sessionStorage.setItem('exam_result', JSON.stringify({ ...result, paper }));
            message.success('交卷成功！');
            navigate(`/score/${examId}`);
        } catch (err: any) {
            message.error('提交失败：' + err.message);
            setSubmitting(false);
        }
    };

    const handleSubmit = () => {
        if (!paper) return;
        const unanswered = paper.questions.filter((q) => !answers[q.id]).length;
        Modal.confirm({
            title: '确认提交试卷',
            content: unanswered > 0
                ? `还有 ${unanswered} 道题未作答，确认提交吗？`
                : '所有题目已作答，确认提交？',
            okText: '提交',
            cancelText: '继续答题',
            onOk: () => doSubmit(),
        });
    };

    const handleAnswer = (value: string) => {
        if (!paper) return;
        setAnswers((prev) => ({ ...prev, [paper.questions[currentIndex].id]: value }));
    };

    const handleMultiAnswer = (values: string[]) => {
        if (!paper) return;
        setAnswers((prev) => ({ ...prev, [paper.questions[currentIndex].id]: values.sort().join('') }));
    };

    if (loading || !paper) {
        return <div className="flex items-center justify-center h-full"><Spin size="large" tip="正在组织试卷..." /></div>;
    }

    const currentQ = paper.questions[currentIndex];
    const totalQ = paper.questions.length;
    const timeColor = timeLeft < 60 ? '#ef4444' : timeLeft < 300 ? '#eab308' : '#3b82f6';

    if (!currentQ) return null;

    return (
        <div className="flex flex-col h-full bg-slate-50">
            {/* 顶部信息栏 */}
            <div className="px-6 pt-4 pb-3 border-b border-slate-200 bg-white">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-lg font-bold text-slate-800">📝 {paper.title}</h1>
                        <span className="text-sm text-slate-500">共 {totalQ} 题 · 满分 {paper.total_score} 分</span>
                    </div>
                    <div className="flex items-center gap-2 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100" style={{ color: timeColor }}>
                        <ClockCircleOutlined />
                        <span className="text-xl font-mono font-bold">{formatTime(timeLeft)}</span>
                    </div>
                </div>

                {/* 题号导航 */}
                <div className="flex gap-1.5 mt-4 flex-wrap">
                    {paper.questions.map((q, i) => (
                        <button
                            key={q.id}
                            onClick={() => setCurrentIndex(i)}
                            className={`w-8 h-8 rounded-lg text-xs font-medium transition-all cursor-pointer border shadow-sm ${i === currentIndex
                                ? 'bg-blue-500 text-white border-blue-500'
                                : answers[q.id]
                                    ? 'bg-green-50 text-green-700 border-green-300'
                                    : 'bg-white text-slate-500 border-slate-200 hover:border-blue-300'
                                }`}
                        >
                            {i + 1}
                        </button>
                    ))}
                </div>
            </div>

            {/* 题目区 */}
            <div className="flex-1 overflow-auto px-6 py-6">
                <Card className="rounded-xl max-w-3xl mx-auto shadow-sm border-0">
                    <div className="flex items-center gap-2 mb-5 pb-3 border-b border-slate-100">
                        <Tag color="blue" className="rounded-full px-3">第 {currentIndex + 1} 题</Tag>
                        <Tag className="rounded-full">
                            {currentQ.type === 'SINGLE_CHOICE' ? '单选' : currentQ.type === 'MULTI_CHOICE' ? '多选' : currentQ.type === 'FILL_BLANK' ? '填空' : '简答'}
                        </Tag>
                        {currentQ.node_title && (
                            <span className="text-xs text-slate-400 bg-slate-50 px-2 py-1 rounded-md">📍 {currentQ.node_title}</span>
                        )}
                    </div>

                    <div className="prose prose-slate max-w-none text-base leading-relaxed mb-8">
                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                            {currentQ.question_md}
                        </ReactMarkdown>
                    </div>

                    {/* 单选 */}
                    {currentQ.type === 'SINGLE_CHOICE' && currentQ.options && (
                        <Radio.Group
                            value={answers[currentQ.id]}
                            onChange={(e) => handleAnswer(e.target.value)}
                            className="w-full"
                        >
                            <div className="space-y-3">
                                {currentQ.options.map((opt) => (
                                    <div key={opt} className={`p-4 rounded-xl border transition-all cursor-pointer ${answers[currentQ.id] === opt ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-100' : 'border-slate-200 hover:border-blue-300 hover:shadow-sm bg-white'
                                        }`}>
                                        <Radio value={opt} className="w-full"><span className="text-base ml-1">{opt}</span></Radio>
                                    </div>
                                ))}
                            </div>
                        </Radio.Group>
                    )}

                    {/* 多选 */}
                    {currentQ.type === 'MULTI_CHOICE' && currentQ.options && (
                        <Checkbox.Group
                            value={(answers[currentQ.id] || '').split('')}
                            onChange={(vals) => handleMultiAnswer(vals as string[])}
                            className="w-full"
                        >
                            <div className="space-y-3">
                                {currentQ.options.map((opt) => (
                                    <div key={opt} className={`p-4 rounded-xl border transition-all cursor-pointer ${(answers[currentQ.id] || '').includes(opt) ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-100' : 'border-slate-200 hover:border-blue-300 hover:shadow-sm bg-white'
                                        }`}>
                                        <Checkbox value={opt} className="w-full"><span className="text-base ml-1">{opt}</span></Checkbox>
                                    </div>
                                ))}
                            </div>
                        </Checkbox.Group>
                    )}

                    {/* 填空 */}
                    {currentQ.type === 'FILL_BLANK' && (
                        <Input
                            size="large"
                            placeholder="请输入答案…"
                            value={answers[currentQ.id] || ''}
                            onChange={(e) => handleAnswer(e.target.value)}
                            className="rounded-xl shadow-sm text-base py-3"
                        />
                    )}

                    {/* 简答 */}
                    {currentQ.type === 'SHORT_ANSWER' && (
                        <Input.TextArea
                            rows={6}
                            placeholder="请输入你的解答步骤或思路…"
                            value={answers[currentQ.id] || ''}
                            onChange={(e) => handleAnswer(e.target.value)}
                            className="rounded-xl shadow-sm text-base p-4"
                        />
                    )}
                </Card>
            </div>

            {/* 底部导航 */}
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

export default Exam;
