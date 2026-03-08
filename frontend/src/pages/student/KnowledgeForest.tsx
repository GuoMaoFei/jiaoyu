import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Spin, Alert, Breadcrumb } from 'antd';
import { getMaterialTree } from '../../api/materials';
import { getNodeStates } from '../../api/students';
import { startLesson } from '../../api/lessons';
import { useAuthStore } from '../../stores/useAuthStore';
import { useLessonStore } from '../../stores/useLessonStore';
import TreeChart from '../../components/tree/TreeChart';
import NodeDetailPanel from '../../components/tree/NodeDetailPanel';
import type { KnowledgeNode } from '../../types/material';
import type { NodeState } from '../../types/student';

const KnowledgeForest: React.FC = () => {
    const { materialId } = useParams<{ materialId: string }>();
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const setLesson = useLessonStore((s) => s.setLesson);

    const [loading, setLoading] = useState(true);
    const [nodes, setNodes] = useState<KnowledgeNode[]>([]);
    const [materialTitle, setMaterialTitle] = useState('知识书林');
    const [nodeStates, setNodeStates] = useState<Record<string, NodeState>>({});
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
    const [panelOpen, setPanelOpen] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!materialId || !user?.id) return;
        setLoading(true);

        Promise.all([
            getMaterialTree(materialId),
            getNodeStates(user.id, materialId)
        ])
            .then(([treeRes, statesRes]: [any, any]) => {
                setNodes(treeRes.nodes || []);
                setMaterialTitle(treeRes.material_title || '知识书林');

                // Convert list of states to a dict for the chart
                const statesMap: Record<string, NodeState> = {};
                if (statesRes.node_states) {
                    statesRes.node_states.forEach((s: any) => {
                        statesMap[s.node_id] = {
                            node_id: s.node_id,
                            is_unlocked: s.is_unlocked,
                            health_score: s.health_score,
                        } as NodeState;
                    });
                }
                setNodeStates(statesMap);
                setError(null);
            })
            .catch((e: any) => {
                console.error(e);
                setError('加载知识书林失败，请检查网络或后端服务');
            })
            .finally(() => setLoading(false));
    }, [materialId, user?.id]);

    const selectedNode = useMemo(
        () => nodes.find((n) => n.id === selectedNodeId) || null,
        [nodes, selectedNodeId]
    );

    const selectedState = useMemo(
        () => (selectedNodeId ? nodeStates[selectedNodeId] || null : null),
        [nodeStates, selectedNodeId]
    );

    const handleNodeClick = useCallback((nodeId: string) => {
        setSelectedNodeId(nodeId);
        setPanelOpen(true);
    }, []);

    const handleStartLearn = useCallback(
        async (nodeId: string) => {
            if (!user?.id) return;
            try {
                const res: any = await startLesson(user.id, nodeId);
                setLesson(res);
                navigate(`/cabin/${res.session_id}?intent=tutor`);
            } catch {
                navigate(`/cabin/${materialId || 'demo'}-${nodeId}?intent=tutor`);
            }
        },
        [user?.id, navigate, setLesson, materialId]
    );

    const handleStartVariant = useCallback(
        async (nodeId: string) => {
            if (!user?.id || !materialId) return;
            const sessionId = `${materialId}-variant-${nodeId}`;
            setLesson({
                session_id: sessionId,
                node_id: nodeId,
                material_id: materialId,
                current_step: 'PRACTICE',
                lesson_id: sessionId,
                node_title: '变式练习',
            });
            navigate(`/cabin/${sessionId}?intent=variant&nodeId=${nodeId}&materialId=${materialId}`);
        },
        [user?.id, materialId, navigate, setLesson]
    );

    if (loading) {
        return (
            <div className="flex items-center justify-center h-96">
                <Spin size="large" tip="加载知识书林…" />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            {/* 顶部 */}
            <div className="px-6 pt-4 pb-3 border-b border-slate-100">
                <Breadcrumb items={[
                    { title: '书架', href: '/bookshelf' },
                    { title: materialTitle },
                    { title: '知识书林' },
                ]} />
                <div className="flex items-center justify-between mt-2">
                    <h1 className="text-xl font-bold text-slate-800">🌳 {materialTitle}</h1>
                    <div className="flex items-center gap-4">
                        {/* 图例 */}
                        <div className="flex items-center gap-3 text-xs text-slate-500">
                            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-green-500 inline-block" /> 掌握</span>
                            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-yellow-500 inline-block" /> 巩固</span>
                            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-red-500 inline-block" /> 薄弱</span>
                            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-slate-300 inline-block" /> 锁定</span>
                        </div>
                    </div>
                </div>
            </div>

            {error && (
                <div className="mx-6 mt-3">
                    <Alert type="info" showIcon message={error} closable />
                </div>
            )}

            {/* 树图主体 */}
            <div className="flex-1 overflow-hidden p-4">
                <TreeChart
                    nodes={nodes}
                    nodeStates={nodeStates}
                    onNodeClick={handleNodeClick}
                />
            </div>

            {/* 节点详情侧边栏 */}
            <NodeDetailPanel
                open={panelOpen}
                onClose={() => setPanelOpen(false)}
                node={selectedNode}
                nodeState={selectedState}
                onStartLearn={handleStartLearn}
                onStartVariant={handleStartVariant}
            />
        </div>
    );
};

export default KnowledgeForest;
