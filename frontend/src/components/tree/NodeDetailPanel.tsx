import React, { useEffect, useState } from 'react';
import { Drawer, Progress, Button, Tag, Empty } from 'antd';
import { PlayCircleOutlined, ExperimentOutlined, HistoryOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { NodeState } from '../../types/student';
import type { KnowledgeNode } from '../../types/material';
import { getQuizHistory } from '../../api/quiz';
import { useAuthStore } from '../../stores/useAuthStore';

interface NodeDetailPanelProps {
    open: boolean;
    onClose: () => void;
    node: KnowledgeNode | null;
    nodeState: NodeState | null;
    onStartLearn: (nodeId: string) => void;
    onStartVariant: (nodeId: string) => void;
}

function getHealthColor(score: number): string {
    if (score > 85) return '#22c55e';
    if (score >= 60) return '#eab308';
    return '#ef4444';
}

const NodeDetailPanel: React.FC<NodeDetailPanelProps> = ({
    open,
    onClose,
    node,
    nodeState,
    onStartLearn,
    onStartVariant,
}) => {
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const [history, setHistory] = useState<any[]>([]);
    const [loadingHistory, setLoadingHistory] = useState(false);

    useEffect(() => {
        if (!open || !node || !user?.id) return;
        
        setLoadingHistory(true);
        getQuizHistory(user.id, node.id)
            .then(setHistory)
            .catch(() => setHistory([]))
            .finally(() => setLoadingHistory(false));
    }, [open, node?.id, user?.id]);

    if (!node) return null;

    const healthScore = nodeState?.health_score ?? 0;
    const isUnlocked = nodeState?.is_unlocked ?? false;

    return (
        <Drawer
            title={node.title}
            open={open}
            onClose={onClose}
            width={360}
            className="rounded-l-xl"
        >
            <div className="flex flex-col items-center gap-6">
                {/* 健康度仪表 */}
                <div className="text-center">
                    <Progress
                        type="dashboard"
                        percent={healthScore}
                        strokeColor={getHealthColor(healthScore)}
                        format={(pct) => (
                            <div>
                                <div className="text-2xl font-bold" style={{ color: getHealthColor(healthScore) }}>
                                    {pct}
                                </div>
                                <div className="text-xs text-slate-400">健康度</div>
                            </div>
                        )}
                    />
                </div>

                {/* 状态标签 */}
                <div className="flex gap-2">
                    <Tag color={isUnlocked ? 'blue' : 'default'}>
                        {isUnlocked ? '✅ 已解锁' : '🔒 未解锁'}
                    </Tag>
                    {healthScore > 85 && <Tag color="green">已掌握</Tag>}
                    {healthScore >= 60 && healthScore <= 85 && <Tag color="gold">需巩固</Tag>}
                    {healthScore > 0 && healthScore < 60 && <Tag color="red">薄弱</Tag>}
                </div>

                {/* 内容预览 */}
                {node.content_preview && (
                    <div className="w-full bg-slate-50 rounded-lg p-3 text-sm text-slate-600 leading-relaxed">
                        {node.content_preview}
                    </div>
                )}

                {/* 操作按钮 */}
                <div className="w-full flex flex-col gap-3 mt-4">
                    <Button
                        type="primary"
                        icon={<PlayCircleOutlined />}
                        size="large"
                        block
                        onClick={() => onStartLearn(node.id)}
                    >
                        开始学习
                    </Button>
                    <Button
                        icon={<ExperimentOutlined />}
                        size="large"
                        block
                        onClick={() => node && onStartVariant(node.id)}
                    >
                        巩固此节点（变式题）
                    </Button>
                </div>

                {/* 错题列表占位 */}
                <div className="w-full mt-4">
                    <h4 className="text-sm font-semibold text-slate-700 mb-2">关联错题</h4>
                    <Empty description="暂无错题记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                </div>

                {/* 历史微测记录 */}
                <div className="w-full mt-4">
                    <h4 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-1">
                        <HistoryOutlined /> 历史微测
                    </h4>
                    {loadingHistory ? (
                        <div className="text-center text-slate-400 text-sm">加载中...</div>
                    ) : history.length === 0 ? (
                        <Empty description="暂无微测记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    ) : (
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                            {history.slice(0, 5).map((item: any) => (
                                <div
                                    key={item.id}
                                    className="flex items-center justify-between bg-slate-50 rounded-lg p-2 text-sm"
                                >
                                    <div className="flex items-center gap-2">
                                        {item.score !== null ? (
                                            <Tag color={item.accuracy_pct >= 60 ? 'green' : 'red'}>
                                                {Math.round(item.accuracy_pct)}%
                                            </Tag>
                                        ) : (
                                            <Tag>进行中</Tag>
                                        )}
                                        <span className="text-slate-500">
                                            {item.question_count}题
                                        </span>
                                    </div>
                                    <Button
                                        type="link"
                                        size="small"
                                        onClick={() => navigate(`/quiz/${node.id}`)}
                                    >
                                        {item.score !== null ? '查看' : '继续'}
                                    </Button>
                                </div>
                            ))}
                            {history.length > 5 && (
                                <div className="text-center text-xs text-slate-400">
                                    还有 {history.length - 5} 条记录
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </Drawer>
    );
};

export default NodeDetailPanel;
