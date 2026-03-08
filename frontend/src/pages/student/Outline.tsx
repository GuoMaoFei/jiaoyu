import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Spin, Alert, Button, Breadcrumb, message } from 'antd';
import {
    PlayCircleOutlined
} from '@ant-design/icons';
import { getMaterialTree } from '../../api/materials';
import { startLesson } from '../../api/lessons';
import { useAuthStore } from '../../stores/useAuthStore';
import { useLessonStore } from '../../stores/useLessonStore';
import type { KnowledgeNode, KnowledgeTreeResponse } from '../../types/material';

/** 构建父子嵌套结构 */
function nestNodes(flatNodes: KnowledgeNode[]): KnowledgeNode[] {
    const map = new Map<string, KnowledgeNode>();
    const roots: KnowledgeNode[] = [];

    flatNodes.forEach((n) => map.set(n.id, { ...n, children: [] }));

    flatNodes.forEach((n) => {
        const node = map.get(n.id)!;
        if (n.parent_id && map.has(n.parent_id)) {
            map.get(n.parent_id)!.children!.push(node);
        } else {
            roots.push(node);
        }
    });

    return roots;
}


/** 递归渲染知识树列表 */
function NodeList({
    nodes,
    depth,
    onStartLearn,
}: {
    nodes: KnowledgeNode[];
    depth: number;
    onStartLearn: (nodeId: string) => void;
}) {
    return (
        <div className={depth > 0 ? 'ml-6 border-l border-slate-100' : ''}>
            {nodes.map((node) => {
                const isLeaf = !node.children || node.children.length === 0;
                // Removed mock node state lookup

                return (
                    <div key={node.id}>
                        <div
                            className={`
                flex items-center justify-between py-3 px-4 hover:bg-slate-50 transition-colors cursor-pointer
                ${depth === 0 ? 'border-b border-slate-100' : ''}
              `}
                        >
                            <div className="flex items-center gap-3 flex-1 min-w-0">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span className="font-medium text-slate-800 truncate" title={node.title}>
                                            {node.seq_num ? `${node.seq_num}. ` : ''}{node.title}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {isLeaf && ( // Removed state.is_unlocked condition
                                <Button
                                    type="primary"
                                    size="small"
                                    ghost
                                    icon={<PlayCircleOutlined />}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onStartLearn(node.id);
                                    }}
                                >
                                    学习
                                </Button>
                            )}
                        </div>

                        {node.children && node.children.length > 0 && (
                            <NodeList nodes={node.children} depth={depth + 1} onStartLearn={onStartLearn} />
                        )}
                    </div>
                );
            })}
        </div>
    );
}

const Outline: React.FC = () => {
    const { materialId } = useParams<{ materialId: string }>();
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const setLesson = useLessonStore((s) => s.setLesson);

    const [treeData, setTreeData] = useState<KnowledgeTreeResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!materialId) return;
        setLoading(true);
        getMaterialTree(materialId)
            .then((data: any) => {
                setTreeData(data);
                setError(null);
            })
            .catch((e: any) => setError(e?.message || '加载失败'))
            .finally(() => setLoading(false));
    }, [materialId]);

    const nestedNodes = useMemo(
        () => (treeData?.nodes ? nestNodes(treeData.nodes) : []),
        [treeData]
    );

    const handleStartLearn = async (nodeId: string) => {
        if (!user?.id) return;
        try {
            const res: any = await startLesson(user.id, nodeId);
            setLesson(res);
            navigate(`/cabin/${res.session_id}`);
        } catch (err: any) {
            message.error('启动学习舱失败: ' + (err.message || '未知错误'));
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-96">
                <Spin size="large" tip="加载知识树…" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-6">
                <Alert type="warning" showIcon message="暂时无法加载知识树" description={error} />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            {/* 顶部面包屑 */}
            <div className="px-6 pt-4 pb-2 border-b border-slate-100">
                <Breadcrumb items={[
                    { title: '书架', href: '/bookshelf' },
                    { title: treeData?.material_title || '课程大纲' },
                ]} />
                <h1 className="text-xl font-bold text-slate-800 mt-2">
                    📚 {treeData?.material_title || '课程大纲'}
                </h1>
                <p className="text-sm text-slate-500 mt-1">
                    共 {treeData?.total_nodes ?? 0} 个知识节点
                </p>
            </div>

            {/* 入学诊断横幅 */}
            <div className="mx-6 mt-4 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-100 flex items-center justify-between">
                <div>
                    <p className="font-semibold text-slate-800">🎯 选择你的学习路径</p>
                    <p className="text-sm text-slate-500 mt-1">首次学习建议先进行全量摸底诊断</p>
                </div>
                <div className="flex gap-3">
                    <Button type="primary" onClick={() => navigate(`/diagnostic/${materialId}`)}>全量摸底诊断</Button>
                    <Button onClick={() => nestedNodes[0] && handleStartLearn(nestedNodes[0].id)}>
                        从零开始学
                    </Button>
                </div>
            </div>

            {/* 知识树列表 */}
            <div className="flex-1 overflow-auto mt-2">
                <NodeList nodes={nestedNodes} depth={0} onStartLearn={handleStartLearn} />
            </div>
        </div>
    );
};

export default Outline;
