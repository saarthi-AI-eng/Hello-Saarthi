import { useState, useRef, useCallback, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
    LayoutDashboard, BookOpen, MessageSquare, Code2,
    BarChart3, Settings, ChevronLeft, ChevronRight,
    GraduationCap, Eye, Flame, BookMarked, GripVertical
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import './Sidebar.css';
import { LogoIcon } from '../LogoIcon';

interface NavItem {
    path: string;
    label: string;
    icon: LucideIcon;
    badge?: string;
}

const DEFAULT_NAV_ITEMS: NavItem[] = [
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/courses', label: 'My Courses', icon: BookOpen },
    { path: '/chat', label: 'AI Tutor Chat', icon: MessageSquare, badge: 'AI' },
    { path: '/quiz', label: 'Exam Practice', icon: GraduationCap },
    { path: '/code-lab', label: 'Coding Lab', icon: Code2 },
    { path: '/videos', label: 'Video Library', icon: Eye },
    { path: '/progress', label: 'Analytics', icon: BarChart3 },
    { path: '/study-material', label: 'Study Materials', icon: BookMarked },
];

const ICON_MAP: Record<string, LucideIcon> = {
    '/dashboard': LayoutDashboard,
    '/courses': BookOpen,
    '/chat': MessageSquare,
    '/quiz': GraduationCap,
    '/code-lab': Code2,
    '/videos': Eye,
    '/progress': BarChart3,
    '/study-material': BookMarked,
};

const STORAGE_KEY = 'saarthi-sidebar-order';

function loadOrder(): NavItem[] {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return DEFAULT_NAV_ITEMS;
        const paths: string[] = JSON.parse(raw);
        if (!Array.isArray(paths) || paths.length === 0) return DEFAULT_NAV_ITEMS;

        const itemMap = new Map(DEFAULT_NAV_ITEMS.map((it) => [it.path, it]));
        const ordered: NavItem[] = [];
        for (const p of paths) {
            const item = itemMap.get(p);
            if (item) {
                ordered.push(item);
                itemMap.delete(p);
            }
        }
        // Append any new items that weren't in stored order
        for (const remaining of itemMap.values()) {
            ordered.push(remaining);
        }
        return ordered;
    } catch {
        return DEFAULT_NAV_ITEMS;
    }
}

function saveOrder(items: NavItem[]) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(items.map((i) => i.path)));
    } catch {
        // ignore storage errors
    }
}

const bottomItems = [
    { path: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
    const [collapsed, setCollapsed] = useState(false);
    const location = useLocation();

    // Draggable nav items
    const [navItems, setNavItems] = useState<NavItem[]>(loadOrder);
    const dragIdx = useRef<number | null>(null);
    const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);

    // Persist whenever navItems changes
    useEffect(() => {
        saveOrder(navItems);
    }, [navItems]);

    const handleDragStart = useCallback((idx: number) => {
        dragIdx.current = idx;
    }, []);

    const handleDragOver = useCallback((e: React.DragEvent, idx: number) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        setDragOverIdx(idx);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent, dropIdx: number) => {
        e.preventDefault();
        const fromIdx = dragIdx.current;
        if (fromIdx === null || fromIdx === dropIdx) {
            setDragOverIdx(null);
            return;
        }
        setNavItems((prev) => {
            const next = [...prev];
            const [moved] = next.splice(fromIdx, 1);
            next.splice(dropIdx, 0, moved);
            return next;
        });
        dragIdx.current = null;
        setDragOverIdx(null);
    }, []);

    const handleDragEnd = useCallback(() => {
        dragIdx.current = null;
        setDragOverIdx(null);
    }, []);

    return (
        <aside className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}>
            {/* Brand */}
            <div className="sidebar-brand">
                <div className="sidebar-logo">
                    <LogoIcon size={24} />
                </div>
                {!collapsed && <span className="sidebar-brand-text">Saarthi.ai</span>}
                <button
                    className="sidebar-toggle"
                    onClick={() => setCollapsed(!collapsed)}
                    aria-label="Toggle sidebar"
                >
                    {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
                </button>
            </div>

            {/* Navigation */}
            <nav className="sidebar-nav">
                <div className="sidebar-nav-group">
                    {navItems.map((item, idx) => {
                        const Icon = ICON_MAP[item.path] || item.icon;
                        const isActive = location.pathname.startsWith(item.path);
                        const isDragOver = dragOverIdx === idx;
                        return (
                            <div
                                key={item.path}
                                className={`sidebar-drag-wrapper ${isDragOver ? 'sidebar-drag-over' : ''}`}
                                draggable={!collapsed}
                                onDragStart={() => handleDragStart(idx)}
                                onDragOver={(e) => handleDragOver(e, idx)}
                                onDrop={(e) => handleDrop(e, idx)}
                                onDragEnd={handleDragEnd}
                            >
                                {!collapsed && (
                                    <span className="sidebar-drag-handle" aria-hidden="true">
                                        <GripVertical size={14} />
                                    </span>
                                )}
                                <NavLink
                                    to={item.path}
                                    className={`sidebar-link ${isActive ? 'active' : ''}`}
                                    title={collapsed ? item.label : undefined}
                                >
                                    <Icon size={20} />
                                    {!collapsed && <span>{item.label}</span>}
                                    {!collapsed && item.badge && (
                                        <span className="sidebar-badge">{item.badge}</span>
                                    )}
                                </NavLink>
                            </div>
                        );
                    })}
                </div>

                {/* Bottom nav */}
                <div className="sidebar-nav-bottom">
                    {!collapsed && (
                        <div className="sidebar-study-card">
                            <div className="sidebar-study-icon"><Flame size={18} /></div>
                            <div>
                                <p className="sidebar-study-title">5 Day Streak!</p>
                                <p className="sidebar-study-sub">Keep learning daily</p>
                            </div>
                        </div>
                    )}
                    {bottomItems.map((item) => {
                        const Icon = item.icon;
                        const isActive = location.pathname.startsWith(item.path);
                        return (
                            <NavLink
                                key={item.path}
                                to={item.path}
                                className={`sidebar-link ${isActive ? 'active' : ''}`}
                                title={collapsed ? item.label : undefined}
                            >
                                <Icon size={20} />
                                {!collapsed && <span>{item.label}</span>}
                            </NavLink>
                        );
                    })}
                </div>
            </nav>
        </aside>
    );
}

