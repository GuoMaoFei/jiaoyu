import { useState, useRef, useCallback } from 'react';
import { fetchEventSource, type EventSourceMessage } from '@microsoft/fetch-event-source';
import { useAuthStore } from '../stores/useAuthStore';
import { message } from 'antd';

export interface SSEOptions extends Record<string, any> {
    onMessage?: (event: EventSourceMessage) => void;
    onOpen?: () => void;
    onClose?: () => void;
    onError?: (err: any) => void;
}

export function useSSE(endpoint: string) {
    const [isStreaming, setIsStreaming] = useState(false);
    const controllerRef = useRef<AbortController | null>(null);

    const startStream = useCallback(async (body: any, options?: SSEOptions) => {
        const token = useAuthStore.getState().token;

        // 中断前一个请求
        if (controllerRef.current) {
            controllerRef.current.abort();
        }

        controllerRef.current = new AbortController();
        setIsStreaming(true);

        try {
            await fetchEventSource(`/api${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                },
                body: JSON.stringify(body),
                signal: controllerRef.current.signal,

                async onopen(response) {
                    if (response.ok) {
                        options?.onOpen?.();
                        return; // 一切正常
                    }
                    if (response.status === 401) {
                        useAuthStore.getState().logout();
                        message.error('会话已过期，请重新登录');
                        throw new Error('Unauthorized');
                    }
                    throw new Error('SSE Connection failed');
                },

                onmessage(ev) {
                    options?.onMessage?.(ev);
                },

                onclose() {
                    setIsStreaming(false);
                    options?.onClose?.();
                },

                onerror(err) {
                    setIsStreaming(false);
                    options?.onError?.(err);
                    // 抛出异常以停止重试机制
                    throw err;
                }
            });
        } catch (e: any) {
            setIsStreaming(false);
            if (e.name !== 'AbortError') {
                console.error('SSE Error:', e);
            }
        }
    }, [endpoint]);

    const stopStream = useCallback(() => {
        if (controllerRef.current) {
            controllerRef.current.abort();
            controllerRef.current = null;
            setIsStreaming(false);
        }
    }, []);

    return { isStreaming, startStream, stopStream };
}
