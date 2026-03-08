import React from 'react';
import { Tag } from 'antd';

/** Agent 信息映射 */
const AGENT_MAP: Record<string, { label: string; color: string; emoji: string }> = {
    tutor: { label: '伴读神仙', color: '#3b82f6', emoji: '🧙' },
    assessor: { label: '铁血阅卷人', color: '#f97316', emoji: '📝' },
    planner: { label: '规划统筹师', color: '#22c55e', emoji: '📋' },
    variant: { label: '变式出卷机', color: '#a855f7', emoji: '🎲' },
    reporter: { label: '学情观察员', color: '#eab308', emoji: '📊' },
};

interface AgentIndicatorProps {
    agentId: string;
    toolName?: string;
}

const AgentIndicator: React.FC<AgentIndicatorProps> = ({ agentId, toolName }) => {
    const agent = AGENT_MAP[agentId] || AGENT_MAP.tutor;

    return (
        <div className="flex items-center gap-2 px-4 py-2 bg-slate-50/80 backdrop-blur-sm border-b border-slate-100 transition-all duration-300">
            <div
                className="w-2 h-2 rounded-full animate-pulse"
                style={{ backgroundColor: agent.color }}
            />
            <Tag
                color={agent.color}
                className="rounded-full text-xs font-medium border-0"
            >
                {agent.emoji} {agent.label}
            </Tag>
            {toolName && (
                <span className="text-xs text-slate-400 animate-pulse">
                    正在调用 {toolName}…
                </span>
            )}
        </div>
    );
};

export default AgentIndicator;
