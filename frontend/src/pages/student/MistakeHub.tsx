import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tag, Segmented, Button, Empty, Spin, Alert, message, Card } from 'antd';
import { ExperimentOutlined, NodeIndexOutlined } from '@ant-design/icons';
import { useAuthStore } from '../../stores/useAuthStore';
import { useMistakeStore } from '../../stores/useMistakeStore';
import { useBookshelfStore } from '../../stores/useBookshelfStore';
import { getStudentMistakes } from '../../api/students';
import { MISTAKE_STATUS_META, type MistakeStatus, type StudentMistake } from '../../types/mistake';



/** 单张错题卡片 */
function MistakeCard({
    mistake,
    onNavigateToNode,
    onGenerateVariant,
}: {
    mistake: StudentMistake;
    onNavigateToNode: (nodeId: string) => void;
    onGenerateVariant: (mistake: StudentMistake) => void;
}) {
    const statusMeta = MISTAKE_STATUS_META[mistake.status];
    const isOverdue = mistake.next_review_date && new Date(mistake.next_review_date) <= new Date();

    return (
        <Card
            hoverable
            className="mb-3 rounded-xl transition-all hover:shadow-md"
            styles={{ body: { padding: '16px 20px' } }}
        >
            {/* 顶部行 */}
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <Tag color={statusMeta.color} className="rounded-full text-xs">
                        {statusMeta.icon} {statusMeta.label}
                    </Tag>
                    {isOverdue && mistake.status !== 'MASTERED' && (
                        <Tag color="red" className="rounded-full text-xs animate-pulse">⏰ 今日待复习</Tag>
                    )}
                </div>
                <span className="text-xs text-slate-400">
                    {new Date(mistake.created_at).toLocaleDateString('zh-CN')}
                </span>
            </div>

            {/* 错误原因 */}
            <p className="text-sm text-slate-700 leading-relaxed mb-3">
                {mistake.error_reason || '暂无错因分析'}
            </p>

            {/* 知识点溯源 */}
            <div className="flex items-center justify-between">
                <button
                    onClick={() => onNavigateToNode(mistake.node_id)}
                    className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 transition-colors cursor-pointer bg-blue-50 px-2.5 py-1 rounded-full"
                >
                    <NodeIndexOutlined />
                    {mistake.node_title || mistake.node_id}
                </button>

                <div className="flex items-center gap-2">
                    {mistake.status !== 'MASTERED' && (
                        <>
                            <span className="text-xs text-slate-400">
                                连续正确 {mistake.consecutive_correct_count}/3
                            </span>
                            <Button
                                type="primary"
                                size="small"
                                icon={<ExperimentOutlined />}
                                onClick={() => onGenerateVariant(mistake)}
                                className="rounded-lg"
                            >
                                生成变式题
                            </Button>
                        </>
                    )}
                </div>
            </div>
        </Card>
    );
}

const MistakeHub: React.FC = () => {
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const {
        mistakes,
        filterStatus,
        isLoading,
        setMistakes,
        setFilterStatus,
        setLoading,
    } = useMistakeStore();

    const { currentMaterialId } = useBookshelfStore();
    const [error, setError] = useState<string | null>(null);

    // 加载错题
    useEffect(() => {
        if (!user?.id) return;
        setLoading(true);
        getStudentMistakes(user.id)
            .then((data: any) => {
                setMistakes(data.mistakes || []);
                setError(null);
            })
            .catch(() => {
                setMistakes([]);
                setError('获取错题记录失败，请稍后重试');
            })
            .finally(() => setLoading(false));
    }, [user?.id]);

    // 根据筛选条件过滤
    const filteredMistakes = useMemo(() => {
        if (filterStatus === 'ALL') return mistakes;
        return mistakes.filter((m) => m.status === filterStatus);
    }, [mistakes, filterStatus]);

    // 统计
    const stats = useMemo(() => {
        const active = mistakes.filter((m) => m.status === 'ACTIVE').length;
        const reviewing = mistakes.filter((m) => m.status === 'REVIEWING').length;
        const mastered = mistakes.filter((m) => m.status === 'MASTERED').length;
        const dueToday = mistakes.filter(
            (m) => m.next_review_date && new Date(m.next_review_date) <= new Date() && m.status !== 'MASTERED'
        ).length;
        return { active, reviewing, mastered, dueToday, total: mistakes.length };
    }, [mistakes]);

    const handleNavigateToNode = (nodeId: string) => {
        // Find a way to route to the node's cabin
        const mId = currentMaterialId || 'demo';
        navigate(`/forest/${mId}?nodeId=${nodeId}`);
    };

    const handleGenerateVariant = (mistake: StudentMistake) => {
        navigate(`/cabin/variant-${mistake.node_id}`);
        message.info(`正在为"${mistake.node_title}"生成变式题…`);
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-96">
                <Spin size="large" tip="加载错题本…" />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            {/* 顶部标题 + 统计 */}
            <div className="px-6 pt-4 pb-3 border-b border-slate-100">
                <h1 className="text-xl font-bold text-slate-800">🔴 错题枢纽</h1>
                <div className="flex items-center gap-4 mt-2 text-sm">
                    <span className="text-slate-500">共 <b className="text-slate-800">{stats.total}</b> 道错题</span>
                    <span className="text-red-500 font-medium">❌ {stats.active} 未解决</span>
                    <span className="text-yellow-600">🔄 {stats.reviewing} 复习中</span>
                    <span className="text-green-600">✅ {stats.mastered} 已攻克</span>
                    {stats.dueToday > 0 && (
                        <Tag color="red" className="rounded-full animate-pulse">
                            ⏰ {stats.dueToday} 道今日待复习
                        </Tag>
                    )}
                </div>
            </div>

            {/* 筛选栏 */}
            <div className="px-6 py-3 flex items-center gap-4 border-b border-slate-50 bg-slate-50/50">
                <Segmented
                    value={filterStatus}
                    onChange={(val) => setFilterStatus(val as MistakeStatus | 'ALL')}
                    options={[
                        { label: '全部', value: 'ALL' },
                        { label: '❌ 未解决', value: 'ACTIVE' },
                        { label: '🔄 复习中', value: 'REVIEWING' },
                        { label: '✅ 已攻克', value: 'MASTERED' },
                    ]}
                    className="rounded-lg"
                />
            </div>

            {error && (
                <div className="mx-6 mt-3">
                    <Alert type="info" showIcon message={error} closable />
                </div>
            )}

            {/* 错题列表 */}
            <div className="flex-1 overflow-auto px-6 py-4">
                {filteredMistakes.length === 0 ? (
                    <Empty
                        description={filterStatus === 'ALL' ? '暂无错题记录，继续加油！🎉' : `暂无${MISTAKE_STATUS_META[filterStatus as MistakeStatus]?.label || ''}的错题`}
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                    />
                ) : (
                    filteredMistakes.map((m) => (
                        <MistakeCard
                            key={m.id}
                            mistake={m}
                            onNavigateToNode={handleNavigateToNode}
                            onGenerateVariant={handleGenerateVariant}
                        />
                    ))
                )}
            </div>
        </div>
    );
};

export default MistakeHub;
