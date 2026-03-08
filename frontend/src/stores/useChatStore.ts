import { create } from 'zustand';
import { type ChatStoreState } from '../types/chat';

export const useChatStore = create<ChatStoreState>((set) => ({
    sessionId: null,
    messages: [],
    currentAgent: 'tutor', // 默认神仙伴读

    setSessionId: (id) => set({ sessionId: id }),

    addMessage: (msg) =>
        set((state) => ({ messages: [...state.messages, msg] })),

    appendStreamToLastMessage: (chunk) =>
        set((state) => {
            const msgs = [...state.messages];
            if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
                msgs[msgs.length - 1] = {
                    ...msgs[msgs.length - 1],
                    content: msgs[msgs.length - 1].content + chunk
                };
            }
            return { messages: msgs };
        }),

    setCurrentAgent: (agentId) => set({ currentAgent: agentId }),

    clearMessages: () => set({ messages: [] }),
}));
