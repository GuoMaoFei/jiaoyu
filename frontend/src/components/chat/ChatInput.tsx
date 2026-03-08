import React, { useState, useRef, useEffect } from 'react';
import { Button, Input } from 'antd';
import { SendOutlined } from '@ant-design/icons';

const { TextArea } = Input;

interface ChatInputProps {
    onSend: (message: string) => void;
    disabled?: boolean;
    placeholder?: string;
}

const ChatInput: React.FC<ChatInputProps> = ({
    onSend,
    disabled = false,
    placeholder = '输入你的问题…',
}) => {
    const [text, setText] = useState('');
    const textAreaRef = useRef<any>(null);

    const handleSend = () => {
        const trimmed = text.trim();
        if (!trimmed || disabled) return;
        onSend(trimmed);
        setText('');
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    useEffect(() => {
        if (!disabled) {
            textAreaRef.current?.focus();
        }
    }, [disabled]);

    return (
        <div className="flex items-end gap-2 p-4 border-t border-slate-100 bg-white">
            <TextArea
                ref={textAreaRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={disabled}
                autoSize={{ minRows: 1, maxRows: 4 }}
                className="flex-1 rounded-xl border-slate-200 focus:border-blue-400 resize-none"
            />
            <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                disabled={!text.trim() || disabled}
                loading={disabled}
                className="rounded-xl h-10 w-10 flex items-center justify-center shrink-0"
            />
        </div>
    );
};

export default ChatInput;
