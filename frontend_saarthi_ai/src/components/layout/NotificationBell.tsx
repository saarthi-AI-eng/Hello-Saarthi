import { useCallback, useEffect, useRef, useState } from 'react';
import { Bell, CheckCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { api, type NotificationResponse, type PaginatedResponse } from '../../lib/api';
import { useAuthStore } from '../../stores/auth.store';

const LIST_SIZE = 10;
const POLL_MS = 60_000;

/** Old assignment notifications link to /courses/{id}/assignments/{aid}, which has no page; open the course instead. */
function toAppPath(link?: string | null): string | null {
    if (!link || !link.startsWith('/')) return null;
    const assignment = link.match(/^(\/courses\/[^/]+)\/assignments\/[^/]+$/);
    return assignment ? assignment[1] : link;
}

function timeAgo(iso: string): string {
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? '' : formatDistanceToNow(date, { addSuffix: true });
}

export default function NotificationBell() {
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    const navigate = useNavigate();
    const wrapperRef = useRef<HTMLDivElement>(null);
    const [open, setOpen] = useState(false);
    const [items, setItems] = useState<NotificationResponse[]>([]);
    const [unread, setUnread] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        try {
            const [recent, unreadPage] = await Promise.all([
                api.get<PaginatedResponse<NotificationResponse>>('/notifications', { limit: LIST_SIZE, offset: 0 }),
                api.get<PaginatedResponse<NotificationResponse>>('/notifications', { unread_only: 'true', limit: 1, offset: 0 }),
            ]);
            setItems(recent.items || []);
            setUnread(unreadPage.total ?? 0);
            setError(null);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Could not load notifications');
        } finally {
            setLoading(false);
        }
    }, []);

    // Poll so new assignments show up without a reload.
    useEffect(() => {
        if (!isAuthenticated) return;
        setLoading(true);
        void load();
        const timer = window.setInterval(() => { void load(); }, POLL_MS);
        return () => window.clearInterval(timer);
    }, [isAuthenticated, load]);

    useEffect(() => {
        if (!open) return;
        const onClick = (e: MouseEvent) => {
            if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setOpen(false);
        };
        const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
        document.addEventListener('mousedown', onClick);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('mousedown', onClick);
            document.removeEventListener('keydown', onKey);
        };
    }, [open]);

    if (!isAuthenticated) return null;

    const toggle = () => {
        const next = !open;
        setOpen(next);
        if (next) void load();
    };

    const openItem = async (n: NotificationResponse) => {
        setOpen(false);
        if (!n.readAt) {
            const readAt = new Date().toISOString();
            setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, readAt } : x)));
            setUnread((u) => Math.max(0, u - 1));
            api.patch(`/notifications/${n.id}/read`, {}).catch(() => { void load(); });
        }
        const path = toAppPath(n.link);
        if (path) navigate(path);
    };

    const markAllRead = async () => {
        const readAt = new Date().toISOString();
        setItems((prev) => prev.map((x) => (x.readAt ? x : { ...x, readAt })));
        setUnread(0);
        try {
            await api.patch('/notifications/read-all', {});
        } catch {
            void load();
        }
    };

    return (
        <div className="topbar-notif-wrapper" ref={wrapperRef}>
            <button
                className="topbar-icon-btn"
                aria-label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
                aria-expanded={open}
                onClick={toggle}
            >
                <Bell size={20} />
                {unread > 0 && <span className="topbar-notif-badge">{unread > 9 ? '9+' : unread}</span>}
            </button>

            {open && (
                <div className="topbar-dropdown topbar-notif-panel animate-scale-in" role="menu">
                    <div className="topbar-notif-header">
                        <span className="topbar-notif-heading">Notifications</span>
                        {unread > 0 && (
                            <button className="topbar-notif-markall" onClick={markAllRead}>
                                <CheckCheck size={14} /> Mark all read
                            </button>
                        )}
                    </div>
                    <div className="topbar-dropdown-divider" />
                    <div className="topbar-notif-list">
                        {loading && items.length === 0 ? (
                            <p className="topbar-notif-empty">Loading…</p>
                        ) : error && items.length === 0 ? (
                            <p className="topbar-notif-empty">{error}</p>
                        ) : items.length === 0 ? (
                            <p className="topbar-notif-empty">You're all caught up.</p>
                        ) : (
                            items.map((n) => (
                                <button
                                    key={n.id}
                                    role="menuitem"
                                    className={`topbar-notif-item ${n.readAt ? '' : 'unread'}`}
                                    onClick={() => openItem(n)}
                                >
                                    <span className="topbar-notif-dot" aria-hidden="true" />
                                    <span className="topbar-notif-text">
                                        <span className="topbar-notif-title">{n.title}</span>
                                        <span className="topbar-notif-body">{n.body}</span>
                                        <span className="topbar-notif-time">{timeAgo(n.createdAt)}</span>
                                    </span>
                                </button>
                            ))
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
