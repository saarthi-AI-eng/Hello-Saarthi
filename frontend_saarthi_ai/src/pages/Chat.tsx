import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Sparkles, User, Bot, Loader2, BookOpen, Lightbulb, Code2, GraduationCap, Plus, Pencil, Trash2, Check, X } from 'lucide-react';
import { api, type ConversationResponse, type ConversationDetailResponse, type SendMessageResponse, type PaginatedResponse } from '../lib/api';
import ConfirmModal from '../components/ConfirmModal';
import EmptyState from '../components/EmptyState';
import './Chat.css';

const GREETING = "Hello! I'm Saarthi, your AI learning companion. I specialize in:\n\n• **Digital Signal Processing** - FFT, filters, transforms\n• **Machine Learning** - Neural networks, optimization\n• **Data Structures** - Trees, graphs, algorithms\n• **Pattern Recognition** - Classification, feature extraction\n\nHow can I help you today?";

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

const suggestedTopics = [
    { icon: BookOpen, label: 'Explain Fourier Transform' },
    { icon: Code2, label: 'Binary Search implementation' },
    { icon: Lightbulb, label: 'What is gradient descent?' },
    { icon: GraduationCap, label: 'DSP exam preparation tips' },
];

function messageFromApi(m: { id: string; role: 'user' | 'assistant'; content: string; createdAt: string }): Message {
    return { id: m.id, role: m.role, content: m.content, timestamp: new Date(m.createdAt) };
}

export default function ChatPage() {
    const [conversations, setConversations] = useState<ConversationResponse[]>([]);
    const [currentId, setCurrentId] = useState<string | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [loadingList, setLoadingList] = useState(true);
    const [loadingChat, setLoadingChat] = useState(false);
    const [sending, setSending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editTitle, setEditTitle] = useState('');
    const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
    const endRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const renameInputRef = useRef<HTMLInputElement>(null);

    const fetchConversations = useCallback(async () => {
        setLoadingList(true);
        setError(null);
        try {
            const res = await api.get<PaginatedResponse<ConversationResponse>>('/chat/conversations', { limit: 50, offset: 0 });
            setConversations(res.items || []);
        } catch (e) {
            const msg = e instanceof Error ? e.message : 'Failed to load conversations';
            setError(msg);
            if (msg.includes('401') || msg.toLowerCase().includes('unauthorized')) setError('Please log in to use chat.');
        } finally {
            setLoadingList(false);
        }
    }, []);

    useEffect(() => { fetchConversations(); }, [fetchConversations]);

    const loadConversation = useCallback(async (id: string) => {
        setEditingId(null);
        setCurrentId(id);
        setLoadingChat(true);
        setError(null);
        try {
            const res = await api.get<ConversationDetailResponse>(`/chat/conversations/${id}`);
            setMessages((res.messages || []).map(messageFromApi));
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load conversation');
            setMessages([]);
        } finally {
            setLoadingChat(false);
        }
    }, []);

    const startRename = (e: React.MouseEvent, c: ConversationResponse) => {
        e.stopPropagation();
        setEditingId(c.id);
        setEditTitle(c.title || 'New Chat');
        setTimeout(() => renameInputRef.current?.focus(), 0);
    };

    const submitRename = async (id: string) => {
        const title = editTitle.trim() || 'New Chat';
        setError(null);
        try {
            await api.patch<ConversationResponse>(`/chat/conversations/${id}`, { title });
            setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title } : c)));
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to rename');
        }
        setEditingId(null);
    };

    const cancelRename = () => {
        setEditingId(null);
        setEditTitle('');
    };

    const handleDeleteClick = (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        setDeleteConfirmId(id);
    };

    const handleDeleteConfirm = async () => {
        if (!deleteConfirmId) return;
        const id = deleteConfirmId;
        setDeleteConfirmId(null);
        setError(null);
        try {
            await api.delete(`/chat/conversations/${id}`);
            setConversations((prev) => prev.filter((c) => c.id !== id));
            if (currentId === id) {
                setCurrentId(null);
                setMessages([]);
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to delete');
        }
    };

    const handleNewChat = async () => {
        setError(null);
        setSending(true);
        try {
            const conv = await api.post<ConversationResponse>('/chat/conversations', { title: 'New Chat' });
            setConversations((prev) => [conv, ...prev]);
            setCurrentId(conv.id);
            setMessages([]);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to create chat');
        } finally {
            setSending(false);
        }
    };

    const sendMessage = async () => {
        if (!input.trim() || sending) return;
        const q = input.trim();
        setInput('');
        setError(null);

        let conversationId = currentId;
        if (!conversationId) {
            setSending(true);
            try {
                const conv = await api.post<ConversationResponse>('/chat/conversations', { title: 'New Chat' });
                setConversations((prev) => [conv, ...prev]);
                setCurrentId(conv.id);
                conversationId = conv.id;
                setMessages([]);
            } catch (e) {
                setError(e instanceof Error ? e.message : 'Failed to create chat');
                setSending(false);
                return;
            }
            setSending(false);
        }

        const optimisticUser: Message = { id: `t-${Date.now()}`, role: 'user', content: q, timestamp: new Date() };
        setMessages((prev) => [...prev, optimisticUser]);
        setSending(true);
        try {
            const data = await api.post<SendMessageResponse>(`/chat/conversations/${conversationId}/messages`, { message: q });
            setMessages((prev) => {
                const withoutOptimistic = prev.filter((m) => m.id !== optimisticUser.id);
                return [...withoutOptimistic, messageFromApi(data.userMessage), messageFromApi(data.assistantMessage)];
            });
            fetchConversations();
        } catch (e) {
            setMessages((prev) => prev.filter((m) => m.id !== optimisticUser.id));
            setError(e instanceof Error ? e.message : 'Failed to send message');
        } finally {
            setSending(false);
        }
    };

    useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    };

    const displayMessages = messages.length === 0 && !loadingChat ? [{ id: 'greeting', role: 'assistant' as const, content: GREETING, timestamp: new Date() }] : messages;

    return (
        <div className="chat-page">
            <div className="chat-sidebar">
                <button
                    type="button"
                    className="btn btn-primary chat-new-btn"
                    onClick={handleNewChat}
                    disabled={sending || loadingList}
                >
                    {sending && !currentId ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                    {' '}New Chat
                </button>
                <div className="chat-history">
                    <p className="chat-history-label">Recent Conversations</p>
                    {loadingList ? (
                        <div className="chat-history-loading"><Loader2 size={14} className="animate-spin" /> Loading...</div>
                    ) : conversations.length === 0 ? (
                        <EmptyState
                            icon={<Sparkles size={28} />}
                            title="No conversations yet"
                            description="Start a new chat to get help from Saarthi."
                        />
                    ) : (
                        conversations.map((c) => (
                            <div
                                key={c.id}
                                className={`chat-history-item-wrap ${currentId === c.id ? 'active' : ''}`}
                            >
                                <button
                                    type="button"
                                    className="chat-history-item"
                                    onClick={() => loadConversation(c.id)}
                                >
                                    {editingId === c.id ? (
                                        <input
                                            ref={renameInputRef}
                                            className="chat-history-rename-input"
                                            value={editTitle}
                                            onChange={(e) => setEditTitle(e.target.value)}
                                            onKeyDown={(e) => {
                                                e.stopPropagation();
                                                if (e.key === 'Enter') submitRename(c.id);
                                                if (e.key === 'Escape') cancelRename();
                                            }}
                                            onClick={(e) => e.stopPropagation()}
                                        />
                                    ) : (
                                        <>
                                            <Sparkles size={14} className="chat-history-icon" />
                                            <span className="chat-history-title">{c.title || 'New Chat'}</span>
                                        </>
                                    )}
                                </button>
                                {editingId === c.id ? (
                                    <div className="chat-history-actions">
                                        <button type="button" className="chat-history-action" onClick={() => submitRename(c.id)} aria-label="Save"><Check size={14} /></button>
                                        <button type="button" className="chat-history-action" onClick={cancelRename} aria-label="Cancel"><X size={14} /></button>
                                    </div>
                                ) : (
                                    <div className="chat-history-actions">
                                        <button type="button" className="chat-history-action" onClick={(e) => startRename(e, c)} aria-label="Rename"><Pencil size={14} /></button>
                                        <button type="button" className="chat-history-action chat-history-action-delete" onClick={(e) => handleDeleteClick(e, c.id)} aria-label="Delete"><Trash2 size={14} /></button>
                                    </div>
                                )}
                            </div>
                        ))
                    )}
                </div>
            </div>

            <div className="chat-main">
                {error && <div className="chat-error" role="alert">{error}</div>}
                {loadingChat && messages.length === 0 ? (
                    <div className="chat-loading-state"><Loader2 size={24} className="animate-spin" /> Loading conversation...</div>
                ) : (
                    <>
                        <div className="chat-messages">
                            {displayMessages.map((msg) => (
                                <div key={msg.id} className={`chat-msg ${msg.role}`}>
                                    <div className={`chat-msg-avatar ${msg.role}`}>
                                        {msg.role === 'user' ? <User size={18} /> : <Bot size={18} />}
                                    </div>
                                    <div className="chat-msg-content">
                                        <div className="chat-msg-header">
                                            <span className="chat-msg-name">{msg.role === 'user' ? 'You' : 'Saarthi AI'}</span>
                                            <span className="chat-msg-time">{msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                        </div>
                                        <div className="chat-msg-text">
                                            {msg.content.split(/```/).map((part, i) => {
                                                if (i % 2 === 1) {
                                                    return (
                                                        <pre key={i} className="chat-code-block">
                                                            <code>{part}</code>
                                                        </pre>
                                                    );
                                                }
                                                return (
                                                    <div key={i}>
                                                        {part.split('\n').map((line, k) => (
                                                            <p key={k} className="chat-msg-p">
                                                                {line.split(/(\[Source: .*?\]|\*\*.*?\*\*)/g).map((subPart, j) => {
                                                                    if (subPart.startsWith('[Source:')) {
                                                                        const source = subPart.match(/\[Source: (.*?)\]/)?.[1];
                                                                        return (
                                                                            <span key={j} className="badge badge-success badge-sm chat-source">
                                                                                📚 {source}
                                                                            </span>
                                                                        );
                                                                    }
                                                                    if (subPart.startsWith('**') && subPart.endsWith('**')) {
                                                                        return <strong key={j}>{subPart.slice(2, -2)}</strong>;
                                                                    }
                                                                    return subPart;
                                                                })}
                                                            </p>
                                                        ))}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                </div>
                            ))}
                            {sending && (
                                <div className="chat-msg assistant">
                                    <div className="chat-msg-avatar assistant"><Bot size={18} /></div>
                                    <div className="chat-msg-content">
                                        <div className="chat-typing">
                                            <Loader2 size={16} className="animate-spin" />
                                            <span>Saarthi is thinking...</span>
                                        </div>
                                    </div>
                                </div>
                            )}
                            <div ref={endRef} />
                        </div>

                        {displayMessages.length <= 1 && (
                            <div className="chat-suggestions">
                                {suggestedTopics.map((topic, i) => {
                                    const Icon = topic.icon;
                                    return (
                                        <button key={i} type="button" className="chat-suggestion-btn" onClick={() => setInput(topic.label)}>
                                            <Icon size={16} /> {topic.label}
                                        </button>
                                    );
                                })}
                            </div>
                        )}

                        <div className="chat-input-area">
                            <div className="chat-input-wrapper">
                                <textarea
                                    ref={inputRef}
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    placeholder="Ask Saarthi anything about your subjects..."
                                    rows={1}
                                    disabled={sending}
                                />
                                <button type="button" className="chat-send-btn" onClick={sendMessage} disabled={!input.trim() || sending}>
                                    <Send size={18} />
                                </button>
                            </div>
                            <p className="chat-input-hint">Press Enter to send • Shift+Enter for new line</p>
                        </div>
                    </>
                )}
            </div>

            <ConfirmModal
                open={deleteConfirmId !== null}
                title="Delete conversation"
                message="This conversation will be permanently deleted. This cannot be undone."
                confirmLabel="Delete"
                variant="danger"
                onConfirm={handleDeleteConfirm}
                onCancel={() => setDeleteConfirmId(null)}
            />
        </div>
    );
}
