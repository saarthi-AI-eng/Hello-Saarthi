import { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, Loader2, User, Bot } from 'lucide-react';
import { LogoIcon } from './LogoIcon';
import { api } from '../lib/api';
import './AIChatbot.css';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

interface AIChatbotProps {
    position?: 'bottom-right' | 'bottom-left';
}

export default function AIChatbot({ position = 'bottom-right' }: AIChatbotProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState<Message[]>([
        {
            id: '1',
            role: 'assistant',
            content: 'Hello! I\'m Saarthi, your AI learning companion. I can help you with:\n\n• Explaining complex technical concepts\n• Solving doubts in DSP, ML, Algorithms\n• Code debugging and optimization\n• Exam preparation tips\n\nWhat would you like to learn today?',
            timestamp: new Date(),
        },]);
    const [inputValue, setInputValue] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    useEffect(() => {
        if (isOpen && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isOpen]);

    const handleSendMessage = async () => {
        if (!inputValue.trim() || isLoading) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: inputValue,
            timestamp: new Date(),
        };

        setMessages((prev) => [...prev, userMessage]);
        setInputValue('');
        setIsLoading(true);

        try {
            const data = await api.post<{ response?: string }>('/chat/message', {
                message: inputValue,
                conversationHistory: messages.map((m) => ({
                    role: m.role,
                    content: m.content,
                })),
            });

            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: data.response || 'I apologize, but I encountered an error. Please try again.',
                timestamp: new Date(),
            };

            setMessages((prev) => [...prev, assistantMessage]);
        } catch (error) {
            console.error('Chat error:', error);
            const errorMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: 'I\'m having trouble connecting right now. Please check if the backend server is running and try again.',
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };

    const suggestedQuestions = [
        'Explain Nyquist theorem',
        'What is gradient descent?',
        'Help me with binary search',
        'DSP exam tips',
    ];

    return (
        <>
            {/* Floating Action Button */}
            <div
                className="ai-fab-wrap"
                style={{
                    [position === 'bottom-right' ? 'right' : 'left']: '1.5rem',
                    bottom: '1.5rem',
                }}
            >
                <button
                    onClick={() => setIsOpen(!isOpen)}
                    className={`ai-fab-btn ${isOpen ? 'open' : ''}`}
                    aria-label={isOpen ? 'Close AI Chat' : 'Open AI Chat'}
                    title={isOpen ? 'Close Saarthi AI' : 'Ask Saarthi AI'}
                >
                    <span className="ai-fab-ring" />
                    {isOpen ? (
                        <X className="ai-fab-icon" />
                    ) : (
                        <MessageCircle className="ai-fab-icon" />
                    )}
                </button>
                {!isOpen && <div className="ai-fab-tooltip">Ask Saarthi AI</div>}
            </div>

            {/* Chat Window */}
            {isOpen && (
                <div
                    style={{
                        position: 'fixed',
                        [position === 'bottom-right' ? 'right' : 'left']: '1.5rem',
                        bottom: '6rem',
                        width: '100%',
                        maxWidth: 'min(28rem, calc(100vw - 3rem))',
                        height: '600px',
                        backgroundColor: 'var(--card-bg)',
                        borderRadius: '1rem',
                        boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
                        display: 'flex',
                        flexDirection: 'column',
                        zIndex: 50,
                        border: '1px solid var(--border)',
                        animation: 'fadeIn 0.3s ease-out',
                    }}
                >
                    {/* Header */}
                    <div
                        style={{
                            background: 'linear-gradient(to right, var(--primary), var(--accent-dark))',
                            color: 'white',
                            padding: '1.25rem',
                            borderTopLeftRadius: '1rem',
                            borderTopRightRadius: '1rem',
                        }}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                <div
                                    style={{
                                        width: '3rem',
                                        height: '3rem',
                                        borderRadius: '50%',
                                        backgroundColor: 'rgba(255, 255, 255, 0.2)',
                                        backdropFilter: 'blur(4px)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                    }}
                                >
                                    <LogoIcon size={24} style={{ color: 'white' }} />
                                </div>
                                <div>
                                    <h3 style={{ fontWeight: 'bold', fontSize: '1.125rem', margin: 0 }}>Saarthi AI Tutor</h3>
                                    <p style={{ fontSize: '0.75rem', color: '#DBEAFE', margin: 0 }}>Always here to help</p>
                                </div>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                <div
                                    style={{
                                        width: '0.5rem',
                                        height: '0.5rem',
                                        backgroundColor: '#10B981',
                                        borderRadius: '50%',
                                        animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                                    }}
                                />
                                <span style={{ fontSize: '0.75rem', color: '#DBEAFE' }}>Online</span>
                            </div>
                        </div>
                    </div>

                    {/* Messages Area */}
                    <div
                        style={{
                            flex: 1,
                            overflowY: 'auto',
                            padding: '1rem',
                            backgroundColor: 'var(--background)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '1rem',
                        }}
                    >
                        {messages.map((message) => (
                            <div
                                key={message.id}
                                style={{
                                    display: 'flex',
                                    gap: '0.75rem',
                                    flexDirection: message.role === 'user' ? 'row-reverse' : 'row',
                                }}
                            >
                                {/* Avatar */}
                                <div
                                    style={{
                                        width: '2rem',
                                        height: '2rem',
                                        borderRadius: '50%',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        flexShrink: 0,
                                        background: message.role === 'user' ? 'var(--primary)' : 'linear-gradient(to bottom right, #A855F7, #EC4899)',
                                    }}
                                >
                                    {message.role === 'user' ? (
                                        <User style={{ width: '1rem', height: '1rem', color: 'white' }} />
                                    ) : (
                                        <Bot style={{ width: '1rem', height: '1rem', color: 'white' }} />
                                    )}
                                </div>

                                {/* Message Bubble */}
                                <div
                                    style={{
                                        maxWidth: '75%',
                                        borderRadius: '1rem',
                                        padding: '0.75rem 1rem',
                                        backgroundColor: message.role === 'user' ? 'var(--primary)' : 'var(--card-bg)',
                                        color: message.role === 'user' ? 'white' : 'var(--foreground)',
                                        border: message.role === 'user' ? 'none' : '1px solid var(--border)',
                                    }}
                                >
                                    <div style={{ fontSize: '0.875rem', lineHeight: '1.6', margin: 0 }}>
                                        {message.content.split(/```/).map((part, i) => {
                                            if (i % 2 === 1) {
                                                return (
                                                    <pre key={i} style={{
                                                        background: '#1F2937',
                                                        color: '#E5E7EB',
                                                        padding: '0.75rem',
                                                        borderRadius: '0.5rem',
                                                        overflowX: 'auto',
                                                        fontSize: '0.8em',
                                                        margin: '0.5rem 0',
                                                        fontFamily: 'monospace'
                                                    }}>
                                                        <code>{part}</code>
                                                    </pre>
                                                );
                                            }
                                            // Regular text with inline formatting
                                            return (
                                                <span key={i}>
                                                    {part.split(/(\[Source: .*?\]|\*\*.*?\*\*)/g).map((subPart, j) => {
                                                        if (subPart.startsWith('[Source:')) {
                                                            const source = subPart.match(/\[Source: (.*?)\]/)?.[1];
                                                            return (
                                                                <span key={j} style={{
                                                                    display: 'inline-block',
                                                                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                                                    color: '#059669',
                                                                    border: '1px solid rgba(16, 185, 129, 0.2)',
                                                                    borderRadius: '4px',
                                                                    padding: '0 4px',
                                                                    fontSize: '0.75em',
                                                                    fontWeight: 600,
                                                                    margin: '0 2px'
                                                                }}>
                                                                    📚 {source}
                                                                </span>
                                                            );
                                                        }
                                                        if (subPart.startsWith('**') && subPart.endsWith('**')) {
                                                            return <strong key={j}>{subPart.slice(2, -2)}</strong>;
                                                        }
                                                        return subPart;
                                                    })}
                                                </span>
                                            );
                                        })}
                                    </div>
                                    <p
                                        style={{
                                            fontSize: '0.75rem',
                                            marginTop: '0.5rem',
                                            color: message.role === 'user' ? '#DBEAFE' : 'var(--gray-400)',
                                            margin: '0.5rem 0 0 0',
                                        }}
                                    >
                                        {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </p>
                                </div>
                            </div>
                        ))}

                        {isLoading && (
                            <div style={{ display: 'flex', gap: '0.75rem' }}>
                                <div
                                    style={{
                                        width: '2rem',
                                        height: '2rem',
                                        borderRadius: '50%',
                                        background: 'linear-gradient(to bottom right, #A855F7, #EC4899)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        flexShrink: 0,
                                    }}
                                >
                                    <Bot style={{ width: '1rem', height: '1rem', color: 'white' }} />
                                </div>
                                <div
                                    style={{
                                        backgroundColor: 'var(--card-bg)',
                                        border: '1px solid var(--border)',
                                        borderRadius: '1rem',
                                        padding: '0.75rem 1rem',
                                    }}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <Loader2 style={{ width: '1rem', height: '1rem', color: 'var(--primary)', animation: 'spin 1s linear infinite' }} />
                                        <span style={{ fontSize: '0.875rem', color: 'var(--gray-600)' }}>Saarthi is thinking...</span>
                                    </div>
                                </div>
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>

                    {/* Suggested Questions */}
                    {messages.length === 1 && (
                        <div style={{ padding: '0.5rem 1rem', borderTop: '1px solid var(--gray-200)', backgroundColor: 'var(--card-bg)' }}>
                            <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--gray-500)', marginBottom: '0.5rem' }}>
                                Suggested questions:
                            </p>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                {suggestedQuestions.map((question, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => setInputValue(question)}
                                        style={{
                                            fontSize: '0.75rem',
                                            padding: '0.375rem 0.75rem',
                                            backgroundColor: 'var(--gray-100)',
                                            color: 'var(--foreground)',
                                            border: '1px solid var(--border)',
                                            borderRadius: '9999px',
                                            cursor: 'pointer',
                                            transition: 'background-color 0.2s, border-color 0.2s',
                                        }}
                                        onMouseEnter={(e) => {
                                            e.currentTarget.style.backgroundColor = 'var(--gray-200)';
                                            e.currentTarget.style.borderColor = 'var(--gray-300)';
                                        }}
                                        onMouseLeave={(e) => {
                                            e.currentTarget.style.backgroundColor = 'var(--gray-100)';
                                            e.currentTarget.style.borderColor = 'var(--border)';
                                        }}
                                    >
                                        {question}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Input Area */}
                    <div
                        style={{
                            padding: '1rem',
                            borderTop: '1px solid var(--border)',
                            backgroundColor: 'var(--card-bg)',
                            borderBottomLeftRadius: '1rem',
                            borderBottomRightRadius: '1rem',
                        }}
                    >
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <input
                                ref={inputRef}
                                type="text"
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                onKeyDown={handleKeyPress}
                                placeholder="Ask me anything..."
                                disabled={isLoading}
                                style={{
                                    flex: 1,
                                    padding: '0.75rem 1rem',
                                    backgroundColor: 'var(--input-bg)',
                                    border: '1px solid var(--border)',
                                    borderRadius: '0.75rem',
                                    fontSize: '0.875rem',
                                    outline: 'none',
                                    color: 'var(--foreground)',
                                }}
                                onFocus={(e) => {
                                    e.currentTarget.style.borderColor = 'var(--primary)';
                                    e.currentTarget.style.boxShadow = '0 0 0 2px rgba(37, 99, 235, 0.1)';
                                }}
                                onBlur={(e) => {
                                    e.currentTarget.style.borderColor = 'var(--border)';
                                    e.currentTarget.style.boxShadow = 'none';
                                }}
                            />
                            <button
                                onClick={handleSendMessage}
                                disabled={!inputValue.trim() || isLoading}
                                style={{
                                    padding: '0.75rem 1rem',
                                    backgroundColor: 'var(--primary)',
                                    color: 'white',
                                    borderRadius: '0.75rem',
                                    border: 'none',
                                    cursor: !inputValue.trim() || isLoading ? 'not-allowed' : 'pointer',
                                    opacity: !inputValue.trim() || isLoading ? 0.5 : 1,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem',
                                    transition: 'background-color 0.2s',
                                }}
                                onMouseEnter={(e) => {
                                    if (!isLoading && inputValue.trim()) {
                                        e.currentTarget.style.backgroundColor = 'var(--primary-dark)';
                                    }
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.backgroundColor = 'var(--primary)';
                                }}
                            >
                                <Send style={{ width: '1.25rem', height: '1.25rem' }} />
                            </button>
                        </div>
                        <p style={{ fontSize: '0.75rem', color: 'var(--gray-500)', marginTop: '0.5rem', textAlign: 'center', margin: '0.5rem 0 0 0' }}>
                            Press Enter to send • Shift+Enter for new line
                        </p>
                    </div>
                </div>
            )}

            <style>{`
        @keyframes pulse {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.5;
          }
        }
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        @keyframes spin {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
        </>
    );
}
