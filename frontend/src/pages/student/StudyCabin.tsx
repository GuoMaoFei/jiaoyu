import React, { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { Breadcrumb, Button, message } from 'antd';
import { ArrowRightOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useAuthStore } from '../../stores/useAuthStore';
import { useChatStore } from '../../stores/useChatStore';
import { useLessonStore } from '../../stores/useLessonStore';
import { useSSE } from '../../hooks/useSSE';
import { advanceLesson } from '../../api/lessons';
import ChatBubble from '../../components/chat/ChatBubble';
import ChatInput from '../../components/chat/ChatInput';
import AgentIndicator from '../../components/chat/AgentIndicator';
import LessonProgress from '../../components/chat/LessonProgress';
import { LESSON_STEP_META, type LessonStep } from '../../types/lesson';
import type { ChatMessage } from '../../types/chat';

const StudyCabin: React.FC = () => {
    const { sessionId } = useParams<{ sessionId: string }>();
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const {
        messages,
        currentAgent,
        addMessage,
        appendStreamToLastMessage,
        setCurrentAgent,
        setSessionId,
        clearMessages,
    } = useChatStore();
    const { currentStep, materialId, nodeId, nodeTitle, isCompleted, setLesson } = useLessonStore();
    const { isStreaming, startStream, stopStream } = useSSE('/chat/stream');

    const intent = searchParams.get('intent') || 'tutor';
    const urlNodeId = searchParams.get('nodeId') || nodeId;
    const urlMaterialId = searchParams.get('materialId') || materialId;

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const [toolName, setToolName] = useState<string | undefined>();
    const [advancing, setAdvancing] = useState(false);

    const welcomeAddedRef = useRef(false);
    const lastSessionRef = useRef<string | undefined>(undefined);

    // 初始化 session
    useEffect(() => {
        // 切换到新的 session 时，清空旧消息
        if (sessionId !== lastSessionRef.current) {
            lastSessionRef.current = sessionId;
            clearMessages();
            welcomeAddedRef.current = false;
        }

        if (sessionId) {
            setSessionId(sessionId);
        }
        // 如果首次进入空会话，发一条欢迎消息
        if (!welcomeAddedRef.current) {
            welcomeAddedRef.current = true;
            let welcomeContent = '你好！👋 我是你的 AI 伴读神仙。\n\n选择一个知识点，我会用苏格拉底式引导帮你理解它。我们开始吧！';
            let agentId: ChatMessage['agentId'] = 'tutor';
            
            if (intent === 'variant') {
                welcomeContent = '你好！📝 我是变式出卷机。\n\n我将针对这个知识点为你生成几道变式练习题，帮助你巩固所学。准备好了吗？';
                agentId = 'variant';
            }
            
            addMessage({
                id: 'welcome',
                role: 'assistant',
                content: welcomeContent,
                agentId,
                timestamp: Date.now(),
            });
        }
        return () => {
            stopStream();
        };
    }, [sessionId, intent]);

    // 自动滚动到底部
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isStreaming]);

    const handleSend = useCallback(
        async (text: string) => {
            if (!user?.id) {
                message.error('请先登录');
                return;
            }

            // Always get the freshest state to avoid stale closures in setTimeout/useCallback
            const currentState = useLessonStore.getState();

            // 添加用户消息
            const userMsg: ChatMessage = {
                id: `user-${Date.now()}`,
                role: 'user',
                content: text,
                timestamp: Date.now(),
            };
            addMessage(userMsg);

            // 预添加空白 assistant 消息用于流式追加
            const assistantMsg: ChatMessage = {
                id: `assistant-${Date.now()}`,
                role: 'assistant',
                content: '',
                agentId: 'tutor',
                timestamp: Date.now(),
            };
            addMessage(assistantMsg);

            setToolName(undefined);

            // 启动 SSE 流
            await startStream(
                {
                    student_id: user.id,
                    material_id: urlMaterialId || currentState.materialId || sessionId,
                    node_id: urlNodeId || currentState.nodeId || undefined,
                    lesson_step: currentState.currentStep || undefined,
                    message: text,
                    session_id: sessionId || undefined,
                    current_intent: intent,
                },
                {
                    onMessage: (ev) => {
                        try {
                            const data = JSON.parse(ev.data);
                            switch (ev.event) {
                                case 'token':
                                    appendStreamToLastMessage(data.content || '');
                                    break;
                                case 'node':
                                    setCurrentAgent(data.node || 'tutor');
                                    break;
                                case 'tool':
                                    setToolName(data.name);
                                    break;
                                case 'done':
                                    setToolName(undefined);
                                    if (data.session_id) {
                                        setSessionId(data.session_id);
                                    }
                                    break;
                                case 'error':
                                    message.error(data.message || 'Agent 处理出错');
                                    break;
                            }
                        } catch {
                            // 非 JSON 数据忽略
                        }
                    },
                    onClose: () => {
                        setToolName(undefined);
                    },
                    onError: () => {
                        setToolName(undefined);
                        message.error('连接中断，请重试');
                    },
                }
            );
        },
        [user?.id, sessionId, startStream, addMessage, appendStreamToLastMessage, setCurrentAgent, setSessionId]
    );

    return (
        <div className="flex flex-col h-full bg-white">
            {/* 顶部栏 */}
            <div className="border-b border-slate-100">
                <div className="px-4 pt-3 pb-1 flex items-center justify-between">
                    <div>
                        <Breadcrumb items={[
                            { title: '书架', href: '/bookshelf' },
                            { title: nodeTitle || '学习舱' },
                        ]} />
                    </div>
                    {/* 推进按钮 */}
                    {currentStep && currentStep !== 'COMPLETED' && !isCompleted ? (
                        <Button
                            type="primary"
                            icon={<ArrowRightOutlined />}
                            loading={advancing}
                            disabled={isStreaming}
                            onClick={async () => {
                                if (!user?.id || !nodeId) return;
                                setAdvancing(true);
                                try {
                                    const res: any = await advanceLesson(user.id, nodeId);
                                    setLesson(res);
                                    const nextStep = res.current_step as LessonStep;
                                    const stepMeta = LESSON_STEP_META[nextStep];
                                    if (nextStep === 'COMPLETED') {
                                        message.success('🎉 恭喜！本节学习已全部完成！');
                                        addMessage({
                                            id: `sys-complete-${Date.now()}`,
                                            role: 'assistant',
                                            content: '🎉 **恭喜你完成了本节的全部学习！**\n\n你可以返回课程大纲继续学习下一节，或在知识书林中查看你的学习进度。',
                                            agentId: 'tutor',
                                            timestamp: Date.now(),
                                        });
                                    } else {
                                        message.info(`进入 ${stepMeta.icon} ${stepMeta.label} 阶段`);
                                        addMessage({
                                            id: `sys-step-${Date.now()}`,
                                            role: 'assistant',
                                            content: `${stepMeta.icon} **${stepMeta.label}**\n\n${res.step_prompt || ''}`,
                                            agentId: 'tutor',
                                            timestamp: Date.now(),
                                        });

                                        // Auto-trigger the Agent to start talking in the new step
                                        // Use setTimeout to ensure the state update (currentStep) has propagated to handleSend
                                        setTimeout(() => {
                                            handleSend(`我已经准备好进入【${stepMeta.label}】阶段了！请根据现在的新阶段要求开始吧，不用再纠结上一个阶段的问题了。`);
                                        }, 100);
                                    }
                                } catch (err: any) {
                                    message.error('推进失败: ' + (err.message || '未知错误'));
                                } finally {
                                    setAdvancing(false);
                                }
                            }}
                            className="rounded-lg shadow-sm"
                        >
                            进入下一阶段
                        </Button>
                    ) : isCompleted || currentStep === 'COMPLETED' ? (
                        <Button
                            type="default"
                            icon={<CheckCircleOutlined />}
                            onClick={() => navigate(`/outline/${materialId}`)}
                            className="rounded-lg border-green-400 text-green-600"
                        >
                            返回大纲
                        </Button>
                    ) : null}
                </div>

                {/* 五步闯关进度条 */}
                <LessonProgress currentStep={currentStep} />

                {/* Agent 指示器 */}
                <AgentIndicator agentId={currentAgent} toolName={toolName} />
            </div>

            {/* 对话消息区 */}
            <div className="flex-1 overflow-auto px-4 py-4 space-y-1 bg-gradient-to-b from-slate-50/50 to-white">
                {messages.map((msg, idx) => (
                    <ChatBubble
                        key={msg.id}
                        message={msg}
                        isStreaming={isStreaming && idx === messages.length - 1 && msg.role === 'assistant'}
                    />
                ))}
                <div ref={messagesEndRef} />
            </div>

            {/* 输入区 */}
            <ChatInput
                onSend={handleSend}
                disabled={isStreaming}
                placeholder={isStreaming ? '智树正在思考…' : '输入你的问题…'}
            />
        </div>
    );
};

export default StudyCabin;
