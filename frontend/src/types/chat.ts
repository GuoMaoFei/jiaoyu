export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    agentId?: 'tutor' | 'assessor' | 'planner' | 'variant' | 'reporter';
    timestamp: number;
}

export interface ChatStoreState {
    sessionId: string | null;
    messages: ChatMessage[];
    currentAgent: string;
    setSessionId: (id: string) => void;
    addMessage: (msg: ChatMessage) => void;
    appendStreamToLastMessage: (chunk: string) => void;
    setCurrentAgent: (agentId: string) => void;
    clearMessages: () => void;
}
