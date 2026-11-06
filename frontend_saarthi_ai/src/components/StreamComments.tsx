import { useState } from 'react';
import { MessageSquare, Trash2 } from 'lucide-react';
import { api } from '../lib/api';
import { useAuthStore } from '../stores/auth.store';
import { useToast } from './Toast';

interface Comment {
    id: string;
    userId: string;
    author: string;
    body: string;
    createdAt: string;
}

interface Props {
    courseId: string;
    itemId: string;
    /** Teachers/admins can remove anyone's comment. */
    canModerate: boolean;
}

/** Class comments under one stream post. Loaded when first opened. */
export default function StreamComments({ courseId, itemId, canModerate }: Props) {
    const userId = useAuthStore((s) => s.user?.id);
    const { showToast } = useToast();
    const [comments, setComments] = useState<Comment[] | null>(null);
    const [open, setOpen] = useState(false);
    const [text, setText] = useState('');
    const [busy, setBusy] = useState(false);
    const base = `/courses/${courseId}/stream/${itemId}/comments`;

    const toggle = async () => {
        setOpen((o) => !o);
        if (comments === null) {
            try {
                setComments(await api.get<Comment[]>(base));
            } catch (e) {
                showToast(e instanceof Error ? e.message : 'Failed to load comments', 'error');
            }
        }
    };

    const send = async () => {
        if (!text.trim()) return;
        setBusy(true);
        try {
            const c = await api.post<Comment>(base, { body: text.trim() });
            setComments((prev) => [...(prev ?? []), c]);
            setText('');
        } catch (e) {
            showToast(e instanceof Error ? e.message : 'Failed to post comment', 'error');
        } finally {
            setBusy(false);
        }
    };

    const remove = async (id: string) => {
        try {
            await api.delete(`${base}/${id}`);
            setComments((prev) => (prev ?? []).filter((c) => c.id !== id));
        } catch (e) {
            showToast(e instanceof Error ? e.message : 'Failed to delete comment', 'error');
        }
    };

    return (
        <div style={{ width: '100%' }}>
            <button className="btn btn-ghost btn-sm" onClick={toggle}>
                <MessageSquare size={14} /> {open ? 'Hide class comments' : `Class comments${comments ? ` (${comments.length})` : ''}`}
            </button>
            {open && (
                <div style={{ marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {(comments ?? []).map((c) => (
                        <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', fontSize: '0.875rem' }}>
                            <div>
                                <strong>{c.author}</strong>{' '}
                                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{new Date(c.createdAt).toLocaleString()}</span>
                                <div>{c.body}</div>
                            </div>
                            {(canModerate || c.userId === userId) && (
                                <button className="btn-icon" aria-label="Delete comment" onClick={() => remove(c.id)}><Trash2 size={14} /></button>
                            )}
                        </div>
                    ))}
                    <form style={{ display: 'flex', gap: '0.5rem' }} onSubmit={(e) => { e.preventDefault(); void send(); }}>
                        <input className="input" placeholder="Add class comment…" value={text} maxLength={2000} onChange={(e) => setText(e.target.value)} />
                        <button className="btn btn-primary btn-sm" type="submit" disabled={busy || !text.trim()}>Post</button>
                    </form>
                </div>
            )}
        </div>
    );
}
