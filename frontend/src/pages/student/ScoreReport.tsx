import React, { useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Button, Tag, Progress, Empty } from 'antd';
import { HomeOutlined, RedoOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import type { ExamResult, ExamPaper } from '../../types/exam';

function formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m} 分 ${s} 秒`;
}

// Extend ExamResult to include the paper optionally passed from Exam.tsx
type StorageResult = ExamResult & { paper?: ExamPaper };

const ScoreReport: React.FC = () => {
    const { examId } = useParams<{ examId: string }>();
    const navigate = useNavigate();

    // Read grading result from sessionStorage which is provided by the Assessor Agent
    const examData = useMemo<StorageResult | null>(() => {
        try {
            const raw = sessionStorage.getItem('exam_result');
            if (!raw) return null;
            return JSON.parse(raw);
        } catch {
            return null;
        }
    }, []);

    if (!examData) {
        return (
            <div className="flex flex-col items-center justify-center h-full gap-4">
                <Empty description="暂无考试数据，请先完成考试" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                <Button type="primary" onClick={() => navigate('/today')}>返回学习舱</Button>
            </div>
        );
    }

    const { title, score, total_score, accuracy_pct, correct_count, total_count, time_used_sec, per_question } = examData;

    // Simulate node changes visually if backend didn't supply it yet
    const nodeChanges = useMemo(() => {
        if (examData.node_changes && examData.node_changes.length > 0) return examData.node_changes;

        const map = new Map<string, { title: string; scoreDelta: number }>();
        per_question.forEach((r) => {
            if (!r.node_id) return;
            const existing = map.get(r.node_id) || { title: r.node_title || r.node_id, scoreDelta: 0 };
            existing.scoreDelta += r.is_correct ? 10 : -5;
            map.set(r.node_id, existing);
        });

        return Array.from(map.entries()).map(([nodeId, data]) => ({
            node_id: nodeId,
            node_title: data.title,
            before: 60, // visual default
            after: Math.max(0, Math.min(100, 60 + data.scoreDelta)),
        }));
    }, [per_question, examData.node_changes]);

    return (
        <div className="flex flex-col h-full overflow-auto bg-slate-50">
            {/* 顶部总评 */}
            <div className="px-6 pt-6 pb-4">
                <Card className="rounded-2xl bg-gradient-to-r from-blue-50 to-indigo-50 border-0 shadow-sm relative overflow-hidden">
                    {/* Decorative Background */}
                    <div className="absolute top-0 right-0 -mr-8 -mt-8 w-48 h-48 bg-white opacity-20 rounded-full blur-2xl"></div>
                    <div className="absolute bottom-0 left-0 -ml-8 -mb-8 w-32 h-32 bg-indigo-500 opacity-10 rounded-full blur-xl"></div>

                    <div className="text-center mb-6 relative z-10">
                        <h1 className="text-xl font-bold text-slate-800 mb-1">📋 {title}</h1>
                        <p className="text-sm text-slate-500">TreeEdu AI Assessor 评测报告</p>
                    </div>

                    <div className="grid grid-cols-4 gap-4 relative z-10">
                        <div className="text-center bg-white/60 p-3 rounded-xl backdrop-blur-sm border border-white">
                            <div className="text-3xl font-bold text-blue-600">{score}</div>
                            <div className="text-xs text-slate-500 mt-1">得分 / {total_score}</div>
                        </div>
                        <div className="text-center bg-white/60 p-3 rounded-xl backdrop-blur-sm border border-white">
                            <Progress
                                type="circle"
                                percent={accuracy_pct}
                                size={48}
                                strokeColor={accuracy_pct >= 80 ? '#22c55e' : accuracy_pct >= 60 ? '#eab308' : '#ef4444'}
                                format={(pct) => <span className="text-xs font-bold">{pct}%</span>}
                            />
                            <div className="text-xs text-slate-500 mt-1">正确率</div>
                        </div>
                        <div className="text-center bg-white/60 p-3 rounded-xl backdrop-blur-sm border border-white flex flex-col justify-center">
                            <div className="text-2xl font-bold text-green-600">
                                {correct_count}<span className="text-base text-slate-400">/{total_count}</span>
                            </div>
                            <div className="text-xs text-slate-500 mt-1">做对题数</div>
                        </div>
                        <div className="text-center bg-white/60 p-3 rounded-xl backdrop-blur-sm border border-white flex flex-col justify-center">
                            <div className="text-lg font-bold text-slate-700">{formatTime(time_used_sec)}</div>
                            <div className="text-xs text-slate-500 mt-1">交卷用时</div>
                        </div>
                    </div>
                </Card>
            </div>

            {/* 知识树变化 */}
            {nodeChanges.length > 0 && (
                <div className="px-6 pb-2">
                    <Card title="🌳 知识掌握度动态变化" size="small" className="rounded-xl shadow-sm border-0 bg-white">
                        {nodeChanges.map((nc) => {
                            const isUp = nc.after > nc.before;
                            return (
                                <div key={nc.node_id} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                                    <span className="text-sm font-medium text-slate-700 flex items-center gap-1.5">
                                        <div className={`w-2 h-2 rounded-full ${nc.after >= 80 ? 'bg-green-500' : nc.after >= 50 ? 'bg-yellow-400' : 'bg-red-500'}`}></div>
                                        {nc.node_title}
                                    </span>
                                    <div className="flex items-center gap-2 text-sm bg-slate-50 px-2 py-1 rounded-md">
                                        <span className="text-slate-400">{nc.before}</span>
                                        <span className={`font-bold ${isUp ? 'text-green-500' : 'text-red-500'}`}>
                                            {isUp ? '↑' : '↓'}
                                        </span>
                                        <span className={`font-bold ${isUp ? 'text-green-600' : 'text-red-600'}`}>{nc.after}</span>
                                    </div>
                                </div>
                            );
                        })}
                    </Card>
                </div>
            )}

            {/* 逐题详情 */}
            <div className="px-6 pb-6 mt-4">
                <div className="flex items-center gap-2 mb-3 px-1">
                    <span className="text-base">📄</span>
                    <h3 className="text-base font-bold text-slate-800">AI 阅卷详情</h3>
                </div>
                {per_question.map((r, i) => (
                    <Card key={r.question_id || i} className="rounded-xl mb-4 shadow-sm border-0 bg-white overflow-hidden">
                        <div className={`h-1 w-full absolute top-0 left-0 ${r.is_correct ? 'bg-green-400' : 'bg-red-400'}`}></div>

                        <div className="flex items-start justify-between mb-3 pt-1">
                            <div className="flex items-center gap-2">
                                <Tag color={r.is_correct ? 'green' : 'red'} className="rounded-md border-0 m-0 px-2 font-medium">
                                    第 {i + 1} 题
                                </Tag>
                                <span className={`font-bold text-sm ${r.is_correct ? 'text-green-600' : 'text-red-500'}`}>
                                    {r.is_correct ? '✓ 答对了' : '✗ 答错了'}
                                </span>
                            </div>
                            {r.node_title && (
                                <span className="text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded-md">📍 {r.node_title}</span>
                            )}
                        </div>

                        {/* 原题 */}
                        <div className="prose prose-sm prose-slate max-w-none mb-4 bg-slate-50/80 p-3.5 rounded-xl border border-slate-100">
                            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                {r.question_md}
                            </ReactMarkdown>
                        </div>

                        {/* 答案对比 */}
                        <div className="grid grid-cols-2 gap-3 mb-3">
                            <div className={`p-3 rounded-xl border ${r.is_correct ? 'bg-green-50/50 border-green-100' : 'bg-red-50/50 border-red-100'}`}>
                                <div className="flex items-center gap-1.5 mb-1 text-xs font-semibold text-slate-500">
                                    <span>👤</span> 你的回答
                                </div>
                                <div className={`font-medium text-base ${r.is_correct ? 'text-green-700' : 'text-red-700'}`}>
                                    {r.student_answer || <span className="text-slate-300 italic">未作答</span>}
                                </div>
                            </div>
                            <div className="p-3 rounded-xl bg-blue-50/50 border border-blue-100">
                                <div className="flex items-center gap-1.5 mb-1 text-xs font-semibold text-slate-500">
                                    <span>🎯</span> 标准答案
                                </div>
                                <div className="font-medium text-base text-blue-700 whitespace-pre-wrap">{r.correct_answer}</div>
                            </div>
                        </div>

                        {/* AI 评析 (If provided by backend) */}
                        {r.explanation && (
                            <div className="mt-3 p-3 bg-indigo-50/50 border border-indigo-100 rounded-xl">
                                <div className="flex items-center gap-1.5 mb-1 text-xs font-bold text-indigo-600">
                                    <span>🤖</span> 阅卷意见 (AI Assessor)
                                </div>
                                <div className="text-sm text-indigo-900 leading-relaxed">
                                    {r.explanation}
                                </div>
                            </div>
                        )}
                    </Card>
                ))}
            </div>

            {/* 底部按钮 */}
            <div className="px-6 py-4 border-t border-slate-200 bg-white flex items-center justify-center gap-4 sticky bottom-0 z-20">
                <Button size="large" icon={<HomeOutlined />} onClick={() => navigate('/today')} className="rounded-xl w-32 border-slate-300 text-slate-600">
                    返回学习
                </Button>
                <Button size="large" type="primary" icon={<RedoOutlined />} onClick={() => navigate(`/exam/${examId || 'demo'}`)} className="rounded-xl w-32 bg-blue-600 shadow-md shadow-blue-500/20">
                    错题强固
                </Button>
            </div>
        </div>
    );
};

export default ScoreReport;
