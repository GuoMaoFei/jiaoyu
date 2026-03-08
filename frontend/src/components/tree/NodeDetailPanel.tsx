import React from 'react';
import { Drawer, Progress, Button, Tag, Empty } from 'antd';
import { PlayCircleOutlined, ExperimentOutlined } from '@ant-design/icons';
import type { NodeState } from '../../types/student';
import type { KnowledgeNode } from '../../types/material';

interface NodeDetailPanelProps {
    open: boolean;
    onClose: () => void;
    node: KnowledgeNode | null;
    nodeState: NodeState | null;
    onStartLearn: (nodeId: string) => void;
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
}) => {
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
                    >
                        巩固此节点（变式题）
                    </Button>
                </div>

                {/* 错题列表占位 */}
                <div className="w-full mt-4">
                    <h4 className="text-sm font-semibold text-slate-700 mb-2">关联错题</h4>
                    <Empty description="暂无错题记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                </div>
            </div>
        </Drawer>
    );
};

export default NodeDetailPanel;
