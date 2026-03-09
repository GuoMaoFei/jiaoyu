import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Card, Tag, Spin, message } from 'antd';
import { ArrowLeftOutlined, ReloadOutlined, HistoryOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { getQuizDetail } from '../../api/quiz';
import type { QuizPaperWithAnswers, QuestionResult } from '../../types/quiz';

const TYPE_LABELS: Record<string, string> = {
    SINGLE_CHOICE: '单选题',
    MULTI_CHOICE: '多选题',
    FILL_BLANK: '填空题',
    SHORT_ANSWER: '简答题',
};

const QuizResult: React.FC = () => {
    const { quizId } = useParams<{ quizId: string }>();
    const navigate = useNavigate();
    const [paper, setPaper] = useState<QuizPaperWithAnswers | null>(null);
    const [result, setResult] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [expandedAnswers, setExpandedAnswers] = useState<Set<number>>(new Set());

    useEffect(() => {
        if (!quizId) return;
        
        const stored = sessionStorage.getItem('quiz_result');
        if (stored) {
            setResult(JSON.parse(stored));
        }
        
        getQuizDetail(quizId)
            .then(setPaper)
            .catch(err => message.error('获取详情失败：' + err.message))
            .finally(() => setLoading(false));
    }, [quizId]);

    const toggleExpand = (index: number) => {
        setExpandedAnswers(prev => {
            const next = new Set(prev);
            if (next.has(index)) {
                next.delete(index);
            } else {
                next.add(index);
            }
            return next;
        });
    };

    const formatTime = (seconds: number) => {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}分${s}秒`;
    };

    if (loading || !paper || !result) {
        return (
            <div className="flex items-center justify-center h-screen">
                <Spin size="large" tip="加载成绩单..." />
            </div>
        );
    }

    const { score, accuracy_pct, time_used_sec, per_question, node_health_change } = result;

    return (
        <div className="min-h-screen bg-slate-50 p-6">
            <div className="max-w-3xl mx-auto">
                <div className="flex items-center justify-between mb-6">
                    <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
                        返回
                    </Button>
                    <h1 className="text-xl font-bold text-slate-800">📊 微测成绩单</h1>
                    <div />
                </div>

                <Card className="mb-6 text-center">
                    <div className="flex items-center justify-center gap-8 mb-6">
                        <div className="text-center">
                            <div className="text-5xl font-bold text-blue-600">{score}/{paper.question_count}</div>
                            <div className="text-slate-500">正确题数</div>
                        </div>
                        <div className="text-center">
                            <div className={`text-5xl font-bold ${accuracy_pct >= 60 ? 'text-green-600' : 'text-red-500'}`}>
                                {Math.round(accuracy_pct)}%
                            </div>
                            <div className="text-slate-500">正确率</div>
                        </div>
                        <div className="text-center">
                            <div className="text-3xl font-bold text-slate-700">{formatTime(time_used_sec)}</div>
                            <div className="text-slate-500">用时</div>
                        </div>
                    </div>
                    
                    {node_health_change && (
                        <div className="bg-gradient-to-r from-blue-50 to-green-50 rounded-xl p-4">
                            <span className="text-slate-700">
                                📈 知识点健康度：{node_health_change.before} → {node_health_change.after} 
                                {node_health_change.change >= 0 ? (
                                    <span className="text-green-600 ml-2">(+{node_health_change.change}) 🎉</span>
                                ) : (
                                    <span className="text-red-500 ml-2">({node_health_change.change})</span>
                                )}
                            </span>
                        </div>
                    )}
                </Card>

                <h2 className="text-lg font-bold text-slate-800 mb-4">📝 逐题解析</h2>
                
                <div className="space-y-4">
                    {per_question.map((q: QuestionResult, index: number) => (
                        <Card 
                            key={index} 
                            className={`border-l-4 ${q.is_correct ? 'border-l-green-500' : 'border-l-red-500'}`}
                        >
                            <div className="flex items-center gap-2 mb-3">
                                {q.is_correct ? (
                                    <Tag color="green">✅ 正确</Tag>
                                ) : (
                                    <Tag color="red">❌ 错误</Tag>
                                )}
                                <Tag>{TYPE_LABELS[q.type] || q.type}</Tag>
                            </div>

                            <div className="prose prose-slate max-w-none mb-4">
                                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                    {q.question_md}
                                </ReactMarkdown>
                            </div>

                            <div className="bg-slate-50 rounded-lg p-3 mb-3">
                                <div className="text-sm">
                                    <span className="text-slate-500">你的答案：</span>
                                    <span className={q.is_correct ? 'text-green-600' : 'text-red-500'}>
                                        {q.student_answer || '(未作答)'}
                                    </span>
                                </div>
                                {!q.is_correct && (
                                    <div className="text-sm mt-1">
                                        <span className="text-slate-500">正确答案：</span>
                                        <span className="text-green-600">{q.correct_answer}</span>
                                    </div>
                                )}
                            </div>

                            <Button 
                                type="link" 
                                onClick={() => toggleExpand(index)}
                                className="p-0 h-auto font-medium text-blue-600"
                            >
                                {expandedAnswers.has(index) ? '▼ 收起解题思路' : '▶ 查看解题思路'}
                            </Button>

                            {expandedAnswers.has(index) && (
                                <div className="mt-3 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                                    <div className="text-sm font-medium text-yellow-800 mb-2">💡 解题思路：</div>
                                    <div className="prose prose-sm max-w-none">
                                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                            {q.solution_steps}
                                        </ReactMarkdown>
                                    </div>
                                </div>
                            )}

                            {!q.is_correct && (
                                <div className="mt-3 text-sm text-orange-500">
                                    ⚠️ 已自动加入错题复习队列
                                </div>
                            )}
                        </Card>
                    ))}
                </div>

                <div className="flex justify-center gap-4 mt-8">
                    <Button icon={<HistoryOutlined />} onClick={() => navigate(-1)}>
                        查看历史记录
                    </Button>
                    <Button 
                        type="primary" 
                        icon={<ReloadOutlined />}
                        onClick={() => navigate(`/quiz/${paper.node_id}`)}
                    >
                        再测一次
                    </Button>
                </div>
            </div>
        </div>
    );
};

export default QuizResult;
