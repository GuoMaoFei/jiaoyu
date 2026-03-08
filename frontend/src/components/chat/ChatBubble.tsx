import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import type { ChatMessage } from '../../types/chat';

/** Agent 配色系统 */
const AGENT_COLORS: Record<string, { bg: string; border: string; text: string; label: string }> = {
    tutor: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700', label: '🧙 伴读神仙' },
    assessor: { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-700', label: '📝 铁血阅卷人' },
    planner: { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-700', label: '📋 规划统筹师' },
    variant: { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-700', label: '🎲 变式出卷机' },
    reporter: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', label: '📊 学情观察员' },
};

interface ChatBubbleProps {
    message: ChatMessage;
    isStreaming?: boolean;
}

const ChatBubble: React.FC<ChatBubbleProps> = ({ message, isStreaming }) => {
    const isUser = message.role === 'user';

    if (isUser) {
        return (
            <div className="flex justify-end mb-4">
                <div className="max-w-[75%] px-4 py-3 rounded-2xl rounded-tr-sm bg-blue-600 text-white shadow-sm">
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
                </div>
            </div>
        );
    }

    const agentId = message.agentId || 'tutor';
    const agentStyle = AGENT_COLORS[agentId] || AGENT_COLORS.tutor;

    return (
        <div className="flex justify-start mb-4">
            <div className={`max-w-[85%] rounded-2xl rounded-tl-sm shadow-sm border ${agentStyle.bg} ${agentStyle.border}`}>
                {/* Agent 标签 */}
                <div className={`px-4 pt-3 pb-1 text-xs font-medium ${agentStyle.text}`}>
                    {agentStyle.label}
                </div>

                {/* 消息体 — Markdown + LaTeX */}
                <div className="px-4 pb-3 text-sm leading-relaxed text-slate-800 prose prose-sm max-w-none
          prose-p:my-1 prose-headings:mt-3 prose-headings:mb-1 prose-pre:bg-slate-100 prose-pre:text-slate-800
          prose-code:text-blue-600 prose-code:font-mono prose-code:text-xs">
                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                        {message.content}
                    </ReactMarkdown>
                    {isStreaming && (
                        <span className="inline-block w-1.5 h-4 bg-blue-500 rounded-sm animate-pulse ml-0.5 align-middle" />
                    )}
                </div>
            </div>
        </div>
    );
};

export default ChatBubble;
