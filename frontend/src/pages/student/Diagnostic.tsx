import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Progress, Card, Radio, Input, Modal, message, Spin } from 'antd';
import { CheckCircleOutlined, RightOutlined, ForwardOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import type { ExamPaper, ExamResult } from '../../types/exam';
import { useAuthStore } from '../../stores/useAuthStore';
import { generateExam, submitExam } from '../../api/exam';

const Diagnostic: React.FC = () => {
    const { materialId } = useParams<{ materialId: string }>();
    const navigate = useNavigate();
    const { user } = useAuthStore();

    const [paper, setPaper] = useState<ExamPaper | null>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    const [currentIndex, setCurrentIndex] = useState(0);
    const [answers, setAnswers] = useState<Record<string, string>>({});
    const [showResult, setShowResult] = useState(false);
    const [examResult, setExamResult] = useState<ExamResult | null>(null);

    useEffect(() => {
        if (!user?.id || !materialId) return;
        generateExam({ student_id: user.id, material_id: materialId, exam_type: 'diagnostic' })
            .then(res => setPaper(res.paper))
            .catch(err => message.error('获取试卷失败：' + err.message))
            .finally(() => setLoading(false));
    }, [user?.id, materialId]);

    const questions = paper?.questions || [];
    const totalQuestions = questions.length;
    const currentQ = questions[currentIndex];
    const answeredCount = Object.keys(answers).length;

    // 覆盖节点统计
    const coveredNodes = useMemo(() => {
        const nodes = new Set<string>();
        Object.keys(answers).forEach((qId) => {
            const q = questions.find((q) => q.id === qId);
            if (q?.node_id) nodes.add(q.node_id);
        });
        return nodes.size;
    }, [answers, questions]);

    const totalNodes = useMemo(() => {
        return new Set(questions.map((q) => q.node_id).filter(Boolean)).size;
    }, [questions]);

    const handleAnswer = (value: string) => {
        setAnswers((prev) => ({ ...prev, [currentQ.id]: value }));
    };

    const handleNext = () => {
        if (currentIndex < totalQuestions - 1) {
            setCurrentIndex((i) => i + 1);
        }
    };

    const handleSkip = () => {
        handleNext();
    };

    const handleSubmit = () => {
        Modal.confirm({
            title: '确认提交诊断',
            content: `你已作答 ${answeredCount}/${totalQuestions} 题，确认提交吗？`,
            okText: '提交',
            cancelText: '继续答题',
            onOk: async () => {
                if (!user?.id || !paper) return;
                setSubmitting(true);
                try {
                    const formattedAnswers = Object.entries(answers).map(([qid, ans]) => ({
                        question_id: qid, student_answer: ans as string
                    }));
                    const res = await submitExam({
                        student_id: user.id,
                        exam_id: paper.id,
                        paper_metadata: paper,
                        answers: formattedAnswers,
                        time_used_sec: 120
                    });
                    setExamResult(res.exam_result);
                    setShowResult(true);
                } catch (err: any) {
                    message.error('提交失败：' + err.message);
                } finally {
                    setSubmitting(false);
                }
            },
        });
    };

    const handleFinish = () => {
        message.success('诊断完成！知识树相关节点的健康度已根据批阅结果更新');
        navigate(`/outline/${materialId}`);
    };

    if (loading || !paper) {
        return <div className="flex items-center justify-center h-full"><Spin size="large" tip="正在生成诊断问卷..." /></div>;
    }

    // 结果页面
    if (showResult && examResult) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8">
                <Card className="rounded-2xl shadow-lg max-w-lg w-full text-center p-6">
                    <div className="text-6xl mb-4">🎯</div>
                    <h2 className="text-2xl font-bold text-slate-800 mb-2">诊断完成！</h2>
                    <p className="text-slate-500 mb-6">AI 学情评估已自动处理完毕，知识薄弱点已记录</p>

                    <div className="grid grid-cols-3 gap-4 mb-6">
                        <div className="bg-blue-50 rounded-xl p-3">
                            <div className="text-2xl font-bold text-blue-600">{examResult.correct_count}/{examResult.total_count}</div>
                            <div className="text-xs text-slate-500">正确/总题</div>
                        </div>
                        <div className="bg-green-50 rounded-xl p-3">
                            <div className="text-2xl font-bold text-green-600">{examResult.accuracy_pct}%</div>
                            <div className="text-xs text-slate-500">正确率</div>
                        </div>
                        <div className="bg-purple-50 rounded-xl p-3">
                            <div className="text-2xl font-bold text-purple-600">{coveredNodes}/{totalNodes}</div>
                            <div className="text-xs text-slate-500">覆盖节点</div>
                        </div>
                    </div>

                    <Button type="primary" size="large" block onClick={handleFinish} className="rounded-xl h-12">
                        查看课程大纲 →
                    </Button>
                </Card>
            </div>
        );
    }

    if (!currentQ) return null;

    return (
        <div className="flex flex-col h-full">
            {/* 顶部进度 */}
            <div className="px-6 pt-4 pb-3 border-b border-slate-100">
                <div className="flex items-center justify-between mb-2">
                    <h1 className="text-lg font-bold text-slate-800">🏥 {paper.title}</h1>
                    <span className="text-sm text-slate-500">
                        覆盖章节：{coveredNodes}/{totalNodes}
                    </span>
                </div>
                <div className="flex items-center gap-3">
                    <Progress
                        percent={Math.round(((currentIndex + 1) / totalQuestions) * 100)}
                        format={() => `${currentIndex + 1}/${totalQuestions}`}
                        strokeColor={{ '0%': '#3b82f6', '100%': '#22c55e' }}
                        className="flex-1"
                    />
                </div>
            </div>

            {/* 题目区 */}
            <div className="flex-1 overflow-auto px-6 py-6">
                <Card className="rounded-xl max-w-3xl mx-auto border shadow-sm">
                    {/* 题型标签 */}
                    <div className="flex items-center gap-2 mb-4">
                        <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-medium">
                            第 {currentIndex + 1} 题
                        </span>
                        <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">
                            {currentQ.type === 'SINGLE_CHOICE' ? '单选题' : currentQ.type === 'FILL_BLANK' ? '填空题' : '简答题'}
                        </span>
                        {currentQ.node_title && (
                            <span className="text-xs text-slate-400">📍 {currentQ.node_title}</span>
                        )}
                    </div>

                    {/* 题面 */}
                    <div className="prose prose-slate max-w-none mb-6">
                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                            {currentQ.question_md}
                        </ReactMarkdown>
                    </div>

                    {/* 答题区 */}
                    {currentQ.type === 'SINGLE_CHOICE' && currentQ.options && (
                        <Radio.Group
                            value={answers[currentQ.id]}
                            onChange={(e) => handleAnswer(e.target.value)}
                            className="w-full"
                        >
                            <div className="space-y-2">
                                {currentQ.options.map((opt) => (
                                    <div
                                        key={opt}
                                        className={`p-3 rounded-lg border transition-all cursor-pointer ${answers[currentQ.id] === opt
                                            ? 'border-blue-400 bg-blue-50'
                                            : 'border-slate-200 hover:border-blue-200'
                                            }`}
                                    >
                                        <Radio value={opt} className="w-full">
                                            <span className="text-sm text-slate-700">{opt}</span>
                                        </Radio>
                                    </div>
                                ))}
                            </div>
                        </Radio.Group>
                    )}

                    {currentQ.type === 'FILL_BLANK' && (
                        <Input
                            size="large"
                            placeholder="请输入答案…"
                            value={answers[currentQ.id] || ''}
                            onChange={(e) => handleAnswer(e.target.value)}
                            className="rounded-lg"
                        />
                    )}

                    {currentQ.type === 'SHORT_ANSWER' && (
                        <Input.TextArea
                            rows={4}
                            placeholder="请输入你的回答…"
                            value={answers[currentQ.id] || ''}
                            onChange={(e) => handleAnswer(e.target.value)}
                            className="rounded-lg"
                        />
                    )}
                </Card>
            </div>

            {/* 底部操作 */}
            <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-white z-10">
                <Button
                    icon={<ForwardOutlined />}
                    onClick={handleSkip}
                    disabled={currentIndex >= totalQuestions - 1}
                >
                    跳过此题
                </Button>
                <div className="flex gap-2">
                    {currentIndex < totalQuestions - 1 ? (
                        <Button
                            type="primary"
                            icon={<RightOutlined />}
                            onClick={handleNext}
                            className="rounded-lg"
                        >
                            下一题
                        </Button>
                    ) : (
                        <Button
                            type="primary"
                            icon={<CheckCircleOutlined />}
                            onClick={handleSubmit}
                            loading={submitting}
                            className="rounded-lg bg-green-500 hover:bg-green-600 border-0 shadow-sm"
                        >
                            提交诊断
                        </Button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default Diagnostic;
