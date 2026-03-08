import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { KnowledgeNode } from '../../types/material';
import type { NodeState } from '../../types/student';

interface TreeChartProps {
    nodes: KnowledgeNode[];
    nodeStates: Record<string, NodeState>;
    onNodeClick?: (nodeId: string) => void;
}

/** 健康度着色 */
function getNodeColor(nodeId: string, nodeStates: Record<string, NodeState>): string {
    const state = nodeStates[nodeId];
    if (!state) return '#94a3b8'; // 未知灰
    if (!state.is_unlocked) return '#cbd5e1'; // 锁定浅灰
    if (state.health_score > 85) return '#22c55e'; // 翠绿
    if (state.health_score >= 60) return '#eab308'; // 黄色
    return '#ef4444'; // 红色
}

/** 将平铺节点数组构建为 ECharts 树形数据 */
function buildTree(
    nodes: KnowledgeNode[],
    nodeStates: Record<string, NodeState>
): any[] {
    const nodeMap = new Map<string, any>();
    const roots: any[] = [];

    // 初始化全部节点
    for (const n of nodes) {
        const color = getNodeColor(n.id, nodeStates);
        const state = nodeStates[n.id];
        const locked = state ? !state.is_unlocked : true;

        nodeMap.set(n.id, {
            name: n.title,
            value: n.id,
            children: [],
            itemStyle: {
                color,
                borderColor: color,
                borderWidth: 1,
            },
            label: {
                color: locked ? '#94a3b8' : '#1e293b',
                fontWeight: state && state.health_score < 60 ? 'bold' : 'normal',
            },
            // 默认展开前两级
            collapsed: n.level >= 2,
        });
    }

    // 构建父子关系
    for (const n of nodes) {
        const treeNode = nodeMap.get(n.id);
        if (n.parent_id && nodeMap.has(n.parent_id)) {
            nodeMap.get(n.parent_id).children.push(treeNode);
        } else {
            roots.push(treeNode);
        }
    }

    return roots;
}

const TreeChart: React.FC<TreeChartProps> = ({ nodes, nodeStates, onNodeClick }) => {
    const option = useMemo(() => {
        const treeData = buildTree(nodes, nodeStates);

        return {
            tooltip: {
                trigger: 'item',
                formatter: (params: any) => {
                    const nodeId = params.data?.value;
                    const state = nodeStates[nodeId];
                    if (!state) return `<b>${params.name}</b><br/>未激活`;
                    return `<b>${params.name}</b><br/>
            健康度：<b style="color:${getNodeColor(nodeId, nodeStates)}">${state.health_score}</b>/100<br/>
            状态：${state.is_unlocked ? '已解锁' : '🔒 未解锁'}`;
                },
            },
            series: [
                {
                    type: 'tree',
                    data: treeData,
                    top: '5%',
                    left: '10%',
                    bottom: '5%',
                    right: '20%',
                    symbolSize: 12,
                    orient: 'LR',
                    layout: 'orthogonal',
                    expandAndCollapse: true,
                    animationDuration: 550,
                    animationDurationUpdate: 750,
                    initialTreeDepth: 2,
                    label: {
                        position: 'right',
                        verticalAlign: 'middle',
                        align: 'left',
                        fontSize: 12,
                        distance: 8,
                    },
                    leaves: {
                        label: {
                            position: 'right',
                            verticalAlign: 'middle',
                            align: 'left',
                        },
                    },
                    lineStyle: {
                        color: '#cbd5e1',
                        width: 1.5,
                        curveness: 0.5,
                    },
                    emphasis: {
                        focus: 'descendant',
                    },
                },
            ],
        };
    }, [nodes, nodeStates]);

    const handleClick = (params: any) => {
        if (params.data?.value && onNodeClick) {
            onNodeClick(params.data.value);
        }
    };

    return (
        <ReactECharts
            option={option}
            style={{ height: '100%', width: '100%', minHeight: 500 }}
            onEvents={{ click: handleClick }}
            notMerge
            lazyUpdate
        />
    );
};

export default TreeChart;
