import { useState, useEffect, useMemo, useCallback } from 'react';
import {
    FolderOpen, FileText, ChevronRight, ChevronLeft, BookOpen,
    Search, Tag, Layers, ArrowLeft, Hash, ChevronDown, ChevronUp,
    Loader2, AlertCircle, BookMarked, Plus, Clock, Grid, List, X,
    Pencil, Trash2, Save
} from 'lucide-react';
import { useAuthStore } from '../stores/auth.store';
import { api, type NoteResponse, type PaginatedResponse } from '../lib/api';
import Pagination from '../components/Pagination';
import ConfirmModal from '../components/ConfirmModal';
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';
import './StudyMaterial.css';

/* ── Types ── */
interface PageMeta {
    page_no: string;
    type: string;
    subject: string;
    title: string;
    section: string;
    all_explained_topics: string[];
}
interface NotePage {
    id: string;
    text: string;
    metadata: PageMeta;
}
interface NoteDocument {
    document_title: string;
    subject: string;
    pages: NotePage[];
}

/* ── manifest of available note files ── */
const NOTE_FILES = [
    { file: 'Digital_Signal_Processing.json', label: 'Digital Signal Processing', icon: '📡' },
    { file: 'Laplace.json', label: 'Laplace Transform', icon: '📐' },
    { file: 'Z-Transform.json', label: 'Z-Transform', icon: '🔢' },
];

/* ── helpers ── */

/** Parse a text string and render inline math segments using KaTeX */
function renderInlineMath(text: string): React.ReactNode[] {
    const nodes: React.ReactNode[] = [];
    let cursor = 0;

    while (cursor < text.length) {
        const start = text.indexOf('( ', cursor);
        if (start === -1) {
            if (cursor < text.length) nodes.push(<span key={`t${cursor}`}>{text.slice(cursor)}</span>);
            break;
        }

        // Find matching " )" scanning forward
        let end = -1;
        for (let j = start + 2; j < text.length; j++) {
            if (text[j] === ')' && j > 0 && text[j - 1] === ' ') {
                end = j + 1;
                break;
            }
        }

        if (end === -1) {
            nodes.push(<span key={`t${cursor}`}>{text.slice(cursor, start + 2)}</span>);
            cursor = start + 2;
            continue;
        }

        if (start > cursor) {
            nodes.push(<span key={`t${cursor}`}>{text.slice(cursor, start)}</span>);
        }

        const mathStr = text.slice(start + 2, end - 2).trim();
        if (mathStr.length > 0) {
            try {
                nodes.push(<InlineMath key={`m${start}`} math={mathStr} />);
            } catch {
                nodes.push(<code key={`m${start}`} className="sm-math-fallback">{mathStr}</code>);
            }
        }
        cursor = end;
    }

    return nodes.length > 0 ? nodes : [<span key="empty">{text}</span>];
}

function renderMathText(raw: string) {
    const paragraphs = raw.split('\n\n');
    return paragraphs.map((p, i) => {
        const trimmed = p.trim();
        if (!trimmed) return null;

        // ── Block math: entire paragraph is "( ... )" ──
        if (trimmed.startsWith('( ') && trimmed.endsWith(' )')) {
            const mathStr = trimmed.slice(2, -2).trim();
            try {
                return (
                    <div key={i} className="sm-math-block">
                        <BlockMath math={mathStr} />
                    </div>
                );
            } catch {
                return (
                    <div key={i} className="sm-math-block">
                        <code className="sm-math-fallback">{trimmed}</code>
                    </div>
                );
            }
        }

        // ── Topic heading ──
        if (i === 0 && /^Topic:/i.test(trimmed)) {
            return <h3 key={i} className="sm-heading">{trimmed}</h3>;
        }

        // ── Section headings ──
        if (/^(Topic:|Step \d)/i.test(trimmed) && trimmed.split('\n').length === 1) {
            return <h3 key={i} className="sm-heading">{trimmed}</h3>;
        }

        // ── Sub-headings: short single-line labels ──
        const isSingleLine = trimmed.split('\n').length === 1;
        const isShort = trimmed.length < 100;
        const hasNoMath = !trimmed.includes('( ');
        const matchesHeading = /^(Example|Conclusion|Summary|Proof|Definition|Important|Key |Case |Property|Goal|Method|Remark|Brief|Effect|General|Interpretation|Special case|Note|Recall|Observation|Result)/i.test(trimmed);

        if (isSingleLine && isShort && hasNoMath && matchesHeading) {
            if (/^(Definition|Important|Key Concept)/i.test(trimmed) && trimmed.includes(':')) {
                const colonIdx = trimmed.indexOf(':');
                const title = trimmed.substring(0, colonIdx);
                const body = trimmed.substring(colonIdx + 1).trim();
                return (
                    <div key={i} className="sm-definition-card">
                        <h4 className="sm-definition-title">{title}</h4>
                        <div className="sm-definition-body">{renderInlineMath(body)}</div>
                    </div>
                );
            }
            return <h4 key={i} className="sm-subheading">{trimmed}</h4>;
        }

        // ── Short label lines ending with ":" that introduce the next section ──
        if (isSingleLine && isShort && hasNoMath && trimmed.endsWith(':')) {
            return <h4 key={i} className="sm-subheading">{trimmed}</h4>;
        }

        // ── Numbered list ──
        if (/^\d+\.\s/.test(trimmed)) {
            const items = trimmed.split(/\n/).filter(Boolean);
            return (
                <ol key={i} className="sm-list">
                    {items.map((item, j) => (
                        <li key={j}>{renderInlineMath(item.replace(/^\d+\.\s*/, ''))}</li>
                    ))}
                </ol>
            );
        }

        // ── Regular paragraph with possible inline math ──
        if (trimmed.includes('( ')) {
            return <p key={i} className="sm-paragraph">{renderInlineMath(trimmed)}</p>;
        }

        return <p key={i} className="sm-paragraph">{trimmed}</p>;
    });
}

export default function StudyMaterialPage() {
    const user = useAuthStore((s) => s.user);
    const isAdmin = user?.role === 'admin';
    const isInstructor = isAdmin || user?.role === 'teacher';
    // All roles get full access to notes tab and CRUD
    const hasNotesAccess = !!user;

    // Tabs state
    const [activeTab, setActiveTab] = useState<'materials' | 'notes'>('materials');

    // Notes State
    const [notesSearch, setNotesSearch] = useState('');
    const [notesViewMode, setNotesViewMode] = useState<'grid' | 'list'>('grid');
    const [notes, setNotes] = useState<NoteResponse[]>([]);
    const [notesTotal, setNotesTotal] = useState(0);
    const [notesOffset, setNotesOffset] = useState(0);
    const [notesLoading, setNotesLoading] = useState(false);
    const [notesError, setNotesError] = useState<string | null>(null);
    const [showNoteModal, setShowNoteModal] = useState(false);
    const [editingNote, setEditingNote] = useState<NoteResponse | null>(null);
    const [savingNote, setSavingNote] = useState(false);
    const [deleteNoteId, setDeleteNoteId] = useState<string | null>(null);
    const [deletingNote, setDeletingNote] = useState(false);

    const PAGE_SIZE = 20;

    const fetchNotes = useCallback(() => {
        setNotesLoading(true);
        setNotesError(null);
        return api.get<PaginatedResponse<NoteResponse>>('/notes', { limit: PAGE_SIZE, offset: notesOffset })
            .then((r) => {
                setNotes(r.items || []);
                setNotesTotal(r.total ?? 0);
            })
            .catch((e) => setNotesError(e instanceof Error ? e.message : 'Failed to load notes'))
            .finally(() => setNotesLoading(false));
    }, [notesOffset]);

    useEffect(() => {
        if (hasNotesAccess && activeTab === 'notes') {
            fetchNotes().catch(() => {});
        }
    }, [hasNotesAccess, activeTab, fetchNotes]);

    const filteredNotes = notes.filter((n) =>
        !notesSearch.trim() ||
        n.title.toLowerCase().includes(notesSearch.toLowerCase()) ||
        (n.topic && n.topic.toLowerCase().includes(notesSearch.toLowerCase()))
    );

    const tagsFromNote = (n: NoteResponse) => (n.topic ? [n.topic] : []);

    const openCreateNote = () => {
        setEditingNote(null);
        setShowNoteModal(true);
    };

    const openEditNote = (note: NoteResponse) => {
        setEditingNote(note);
        setShowNoteModal(true);
    };

    const closeNoteModal = () => {
        setShowNoteModal(false);
        setEditingNote(null);
    };

    const handleSaveNote = async (payload: { title: string; content: string; topic?: string }) => {
        setNotesError(null);
        setSavingNote(true);
        try {
            if (editingNote) {
                await api.patch<NoteResponse>(`/notes/${editingNote.id}`, { title: payload.title, content: payload.content });
            } else {
                await api.post<NoteResponse>('/notes', {
                    title: payload.title,
                    content: payload.content,
                    topic: payload.topic || undefined,
                });
            }
            closeNoteModal();
            fetchNotes();
        } catch (e) {
            setNotesError(e instanceof Error ? e.message : 'Failed to save note');
        } finally {
            setSavingNote(false);
        }
    };

    const handleDeleteConfirm = async () => {
        if (!deleteNoteId) return;
        setDeletingNote(true);
        setNotesError(null);
        try {
            await api.delete(`/notes/${deleteNoteId}`);
            setDeleteNoteId(null);
            fetchNotes();
        } catch (e) {
            setNotesError(e instanceof Error ? e.message : 'Failed to delete note');
        } finally {
            setDeletingNote(false);
        }
    };

    const formatDate = (iso: string) => {
        try {
            const d = new Date(iso);
            return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
        } catch {
            return iso;
        }
    };

    const [docs, setDocs] = useState<Map<string, NoteDocument>>(new Map());
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Navigation state
    const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
    const [selectedPageId, setSelectedPageId] = useState<string | null>(null);
    const [search, setSearch] = useState('');
    const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

    // Load all JSON files
    useEffect(() => {
        setLoading(true);
        setError(null);
        Promise.all(
            NOTE_FILES.map(async (nf) => {
                const res = await fetch(`/notes/${nf.file}`);
                if (!res.ok) throw new Error(`Failed to load ${nf.file}`);
                const data: NoteDocument = await res.json();
                return [nf.file, data] as [string, NoteDocument];
            })
        )
            .then((entries) => {
                setDocs(new Map(entries));
            })
            .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load study materials'))
            .finally(() => setLoading(false));
    }, []);

    // Current document & page
    const currentDoc = selectedFolder ? docs.get(selectedFolder) ?? null : null;
    const currentPage = currentDoc && selectedPageId
        ? currentDoc.pages.find((p) => p.id === selectedPageId) ?? null
        : null;

    // Group pages by section for the table-of-contents
    const tocSections = useMemo(() => {
        if (!currentDoc) return [];
        const map = new Map<string, NotePage[]>();
        for (const page of currentDoc.pages) {
            const key = page.metadata.title || 'General';
            if (!map.has(key)) map.set(key, []);
            map.get(key)!.push(page);
        }
        return Array.from(map.entries());
    }, [currentDoc]);

    // Search/filter pages across all docs
    const searchResults = useMemo(() => {
        if (!search.trim()) return null;
        const q = search.toLowerCase();
        const results: { file: string; label: string; page: NotePage }[] = [];
        for (const nf of NOTE_FILES) {
            const doc = docs.get(nf.file);
            if (!doc) continue;
            for (const page of doc.pages) {
                const matchTitle = page.metadata.title.toLowerCase().includes(q);
                const matchSection = page.metadata.section.toLowerCase().includes(q);
                const matchTopics = page.metadata.all_explained_topics.some((t) => t.toLowerCase().includes(q));
                const matchText = page.text.toLowerCase().includes(q);
                if (matchTitle || matchSection || matchTopics || matchText) {
                    results.push({ file: nf.file, label: nf.label, page });
                }
            }
        }
        return results;
    }, [search, docs]);

    const toggleSection = (section: string) => {
        setExpandedSections((prev) => {
            const next = new Set(prev);
            if (next.has(section)) next.delete(section);
            else next.add(section);
            return next;
        });
    };

    const openPage = (file: string, pageId: string) => {
        setSelectedFolder(file);
        setSelectedPageId(pageId);
        setSearch('');
    };

    const goBack = () => {
        if (selectedPageId) {
            setSelectedPageId(null);
        } else if (selectedFolder) {
            setSelectedFolder(null);
            setExpandedSections(new Set());
        }
    };

    // Navigate between pages within the same doc
    const navigatePage = (delta: number) => {
        if (!currentDoc || !selectedPageId) return;
        const idx = currentDoc.pages.findIndex((p) => p.id === selectedPageId);
        const next = currentDoc.pages[idx + delta];
        if (next) setSelectedPageId(next.id);
    };
    const currentPageIdx = currentDoc && selectedPageId
        ? currentDoc.pages.findIndex((p) => p.id === selectedPageId)
        : -1;

    /* ── RENDER ── */

    if (loading) {
        return (
            <div className="sm-page">
                <div className="sm-loading">
                    <Loader2 size={32} className="sm-spinner" />
                    <p>Loading study materials…</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="sm-page">
                <div className="sm-error-state">
                    <AlertCircle size={32} />
                    <p>{error}</p>
                </div>
            </div>
        );
    }

    /* ── PAGE READER VIEW (Split Layout) ── */
    if (currentPage && currentDoc) {
        const meta = currentPage.metadata;
        return (
            <div className="sm-page sm-reader-layout">
                {/* Sidebar TOC */}
                <aside className="sm-sidebar">
                    <div className="sm-sidebar-header">
                        <button className="sm-back-btn" onClick={goBack}>
                            <ArrowLeft size={16} /> All Folders
                        </button>
                        <h3 className="sm-sidebar-title">{currentDoc.document_title}</h3>
                    </div>
                    <div className="sm-sidebar-toc">
                        {tocSections.map(([section, pages]) => {
                            const isOpen = expandedSections.has(section) || tocSections.length <= 5;
                            return (
                                <div key={section} className="sm-sidebar-section">
                                    <button
                                        className="sm-sidebar-section-header"
                                        onClick={() => toggleSection(section)}
                                    >
                                        <div className="sm-sidebar-section-left">
                                            <span>{section}</span>
                                        </div>
                                        {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                    </button>
                                    {isOpen && (
                                        <div className="sm-sidebar-pages">
                                            {pages.map((page) => (
                                                <button
                                                    key={page.id}
                                                    className={`sm-sidebar-page ${page.id === selectedPageId ? 'active' : ''}`}
                                                    onClick={() => setSelectedPageId(page.id)}
                                                >
                                                    <span className="sm-sidebar-page-title">{page.metadata.section}</span>
                                                    <span className="sm-sidebar-page-num">p.{page.metadata.page_no}</span>
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </aside>

                {/* Main Content */}
                <div className="sm-main-content">
                    <div className="sm-reader-topbar animate-fade-in">
                        <div className="sm-page-nav">
                            <button
                                className="sm-nav-btn"
                                disabled={currentPageIdx <= 0}
                                onClick={() => navigatePage(-1)}
                            >
                                <ChevronLeft size={16} /> Prev
                            </button>
                            <span className="sm-page-counter">
                                Page {currentPageIdx + 1} of {currentDoc.pages.length}
                            </span>
                            <button
                                className="sm-nav-btn"
                                disabled={currentPageIdx >= currentDoc.pages.length - 1}
                                onClick={() => navigatePage(1)}
                            >
                                Next <ChevronRight size={16} />
                            </button>
                        </div>
                    </div>

                    <article className="sm-reader animate-fade-in delay-100">
                        <div className="sm-reader-meta">
                            <span className="sm-badge sm-badge-subject"><BookOpen size={12} /> {meta.subject}</span>
                            <span className="sm-badge sm-badge-section"><Layers size={12} /> {meta.section}</span>
                            <span className="sm-badge sm-badge-page"><Hash size={12} /> Page {meta.page_no}</span>
                        </div>
                        <h2 className="sm-reader-title">{meta.title}</h2>
                        <div className="sm-reader-content">
                            {renderMathText(currentPage.text)}
                        </div>
                        <div className="sm-reader-topics">
                            <h4><Tag size={14} /> Topics Covered</h4>
                            <div className="sm-topic-chips">
                                {meta.all_explained_topics.map((t) => (
                                    <span key={t} className="sm-chip">{t}</span>
                                ))}
                            </div>
                        </div>
                    </article>
                </div>
            </div>
        );
    }

    /* ── TABLE OF CONTENTS VIEW ── */
    if (currentDoc && selectedFolder) {
        const folderMeta = NOTE_FILES.find((f) => f.file === selectedFolder);
        return (
            <div className="sm-page">
                <div className="sm-toc-header animate-fade-in">
                    <button className="sm-back-btn" onClick={goBack}>
                        <ArrowLeft size={18} /> All Folders
                    </button>
                    <div className="sm-toc-title-row">
                        <span className="sm-folder-emoji">{folderMeta?.icon}</span>
                        <div>
                            <h1>{currentDoc.document_title}</h1>
                            <p className="sm-toc-subtitle">
                                {currentDoc.subject} • {currentDoc.pages.length} pages
                            </p>
                        </div>
                    </div>
                </div>

                <div className="sm-toc-sections animate-fade-in delay-100">
                    {tocSections.map(([section, pages]) => {
                        const isOpen = expandedSections.has(section) || tocSections.length <= 5;
                        return (
                            <div key={section} className="sm-toc-section">
                                <button
                                    className="sm-toc-section-header"
                                    onClick={() => toggleSection(section)}
                                >
                                    <div className="sm-toc-section-left">
                                        <BookMarked size={16} />
                                        <span>{section}</span>
                                        <span className="sm-toc-count">{pages.length} {pages.length === 1 ? 'page' : 'pages'}</span>
                                    </div>
                                    {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                                </button>
                                {isOpen && (
                                    <div className="sm-toc-pages">
                                        {pages.map((page) => (
                                            <button
                                                key={page.id}
                                                className="sm-toc-page"
                                                onClick={() => setSelectedPageId(page.id)}
                                            >
                                                <FileText size={14} />
                                                <div className="sm-toc-page-info">
                                                    <span className="sm-toc-page-title">{page.metadata.section}</span>
                                                    <span className="sm-toc-page-topics">
                                                        {page.metadata.all_explained_topics.slice(0, 3).join(' · ')}
                                                    </span>
                                                </div>
                                                <span className="sm-toc-page-num">p.{page.metadata.page_no}</span>
                                                <ChevronRight size={14} className="sm-toc-arrow" />
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        );
    }

    /* ── FOLDER BROWSER / NOTES HOME VIEW ── */
    return (
        <div className="sm-page">
            <div className="sm-home-header animate-fade-in">
                <div className="sm-home-title-area">
                    <h1>📚 Study Materials</h1>
                    <p>
                        {hasNotesAccess 
                            ? (isInstructor ? "Browse course materials or manage all study notes" : "Browse course materials or manage your personal study notes")
                            : "Browse your organized course notes by subject folder"}
                    </p>
                </div>
                
                {/* Tab selector for all authenticated users */}
                {hasNotesAccess && (
                    <div className="sm-tabs-container">
                        <button 
                            type="button" 
                            className={`sm-tab-btn ${activeTab === 'materials' ? 'active' : ''}`}
                            onClick={() => {
                                setActiveTab('materials');
                                setSearch(''); // Reset material search
                            }}
                        >
                            <BookMarked size={16} /> Course Materials
                        </button>
                        <button 
                            type="button" 
                            className={`sm-tab-btn ${activeTab === 'notes' ? 'active' : ''}`}
                            onClick={() => {
                                setActiveTab('notes');
                                setNotesSearch(''); // Reset notes search
                            }}
                        >
                            <FileText size={16} /> My Notes
                        </button>
                    </div>
                )}
            </div>

            {hasNotesAccess && activeTab === 'notes' ? (
                /* ── STUDY NOTES SUB-TAB ── */
                <div className="sm-notes-tab-content">
                    <div className="notes-search-and-actions animate-fade-in delay-100">
                        <div className="courses-search" style={{ maxWidth: '400px', flex: 1 }}>
                            <Search size={18} />
                            <input 
                                type="text" 
                                placeholder="Filter notes by title or topic..." 
                                value={notesSearch} 
                                onChange={(e) => setNotesSearch(e.target.value)} 
                            />
                        </div>
                        <div className="notes-header-actions">
                            <div className="courses-view-toggle">
                                <button 
                                    type="button" 
                                    className={`btn btn-icon ${notesViewMode === 'grid' ? 'active' : ''}`} 
                                    onClick={() => setNotesViewMode('grid')}
                                    aria-label="Grid view"
                                >
                                    <Grid size={18} />
                                </button>
                                <button 
                                    type="button" 
                                    className={`btn btn-icon ${notesViewMode === 'list' ? 'active' : ''}`} 
                                    onClick={() => setNotesViewMode('list')}
                                    aria-label="List view"
                                >
                                    <List size={18} />
                                </button>
                            </div>
                            <button type="button" className="btn btn-primary" onClick={openCreateNote}>
                                <Plus size={16} /> New Note
                            </button>
                        </div>
                    </div>

                    {notesError && <div className="notes-error" role="alert">{notesError}</div>}

                    {notesLoading && notes.length === 0 ? (
                        <div className="notes-loading">Loading notes…</div>
                    ) : filteredNotes.length === 0 ? (
                        <div className="notes-empty animate-fade-in delay-100">
                            <div className="notes-empty-icon"><FileText size={48} /></div>
                            <h3>{notes.length === 0 ? 'No notes yet' : 'No matching notes'}</h3>
                            <p>{notes.length === 0 ? 'Create your first study note to get started.' : 'Try a different filter.'}</p>
                            {notes.length === 0 && (
                                <button type="button" className="btn btn-primary" onClick={openCreateNote}>
                                    <Plus size={18} /> Create your first note
                                </button>
                            )}
                        </div>
                    ) : (
                        <>
                            <div className={`notes-grid ${notesViewMode === 'list' ? 'notes-list-view' : ''} animate-fade-in delay-200`}>
                                {filteredNotes.map((note) => (
                                    <div key={note.id} className="note-card">
                                        <div className="note-card-header">
                                            <FileText size={18} className="note-card-icon" />
                                            <div className="note-card-actions">
                                                <button 
                                                    type="button" 
                                                    className="note-action-btn" 
                                                    onClick={(e) => { e.stopPropagation(); openEditNote(note); }} 
                                                    aria-label="Edit"
                                                >
                                                    <Pencil size={14} />
                                                </button>
                                                <button 
                                                    type="button" 
                                                    className="note-action-btn note-action-delete" 
                                                    onClick={(e) => { e.stopPropagation(); setDeleteNoteId(note.id); }} 
                                                    aria-label="Delete"
                                                >
                                                    <Trash2 size={14} />
                                                </button>
                                            </div>
                                        </div>
                                        <div className="note-card-body" onClick={() => openEditNote(note)}>
                                            <h3 className="note-card-title">{note.title}</h3>
                                            {note.courseId && <p className="note-card-course"><BookOpen size={13} /> Course {note.courseId}</p>}
                                            <p className="note-card-preview">{note.content.slice(0, 120)}{note.content.length > 120 ? '…' : ''}</p>
                                            <div className="note-card-tags">
                                                {tagsFromNote(note).map((tag) => (
                                                    <span key={tag} className="note-tag"><Tag size={10} /> {tag}</span>
                                                ))}
                                            </div>
                                        </div>
                                        <div className="note-card-footer">
                                            <span><Clock size={12} /> {formatDate(note.updatedAt)}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            {notesTotal > PAGE_SIZE && (
                                <Pagination total={notesTotal} limit={PAGE_SIZE} offset={notesOffset} onPageChange={setNotesOffset} />
                            )}
                        </>
                    )}
                </div>
            ) : (
                /* ── COURSE MATERIALS SUB-TAB ── */
                <>
                    <div className="sm-search-bar animate-fade-in delay-100">
                        <Search size={18} />
                        <input
                            type="text"
                            placeholder="Search across all notes…"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>

                    {/* Search results */}
                    {searchResults && searchResults.length > 0 && (
                        <div className="sm-search-results animate-fade-in">
                            <h3 className="sm-sr-title">
                                {searchResults.length} result{searchResults.length !== 1 ? 's' : ''} found
                            </h3>
                            <div className="sm-sr-list">
                                {searchResults.slice(0, 20).map((r, i) => (
                                    <button
                                        key={`${r.file}-${r.page.id}-${i}`}
                                        className="sm-sr-item"
                                        onClick={() => openPage(r.file, r.page.id)}
                                    >
                                        <FileText size={16} />
                                        <div className="sm-sr-info">
                                            <span className="sm-sr-page-title">{r.page.metadata.title}</span>
                                            <span className="sm-sr-page-section">{r.label} → {r.page.metadata.section}</span>
                                        </div>
                                        <ChevronRight size={14} />
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {searchResults && searchResults.length === 0 && (
                        <div className="sm-empty-search animate-fade-in">
                            <Search size={32} />
                            <p>No results for "<strong>{search}</strong>"</p>
                        </div>
                    )}

                    {/* Folders grid */}
                    {!searchResults && (
                        <div className="sm-folders-grid animate-fade-in delay-200">
                            {NOTE_FILES.map((nf) => {
                                const doc = docs.get(nf.file);
                                if (!doc) return null;
                                const uniqueTopics = new Set(doc.pages.flatMap((p) => p.metadata.all_explained_topics));
                                return (
                                    <button
                                        key={nf.file}
                                        className="sm-folder-card"
                                        onClick={() => {
                                            setSelectedFolder(nf.file);
                                            setExpandedSections(new Set());
                                        }}
                                    >
                                        <div className="sm-folder-icon">{nf.icon}</div>
                                        <div className="sm-folder-info">
                                            <h3>{nf.label}</h3>
                                            <p className="sm-folder-sub">{doc.subject}</p>
                                        </div>
                                        <div className="sm-folder-stats">
                                            <span><FileText size={13} /> {doc.pages.length} pages</span>
                                            <span><Tag size={13} /> {uniqueTopics.size} topics</span>
                                        </div>
                                        <div className="sm-folder-arrow">
                                            <FolderOpen size={20} />
                                        </div>
                                    </button>
                                );
                            })}
                        </div>
                    )}
                </>
            )}

            {/* Modals for Study Notes */}
            {hasNotesAccess && showNoteModal && (
                <NoteModal
                    note={editingNote}
                    onClose={closeNoteModal}
                    onSave={handleSaveNote}
                    saving={savingNote}
                />
            )}

            {hasNotesAccess && (
                <ConfirmModal
                    open={deleteNoteId !== null}
                    title="Delete note"
                    message="This note will be permanently deleted. This cannot be undone."
                    confirmLabel="Delete"
                    variant="danger"
                    onConfirm={handleDeleteConfirm}
                    onCancel={() => setDeleteNoteId(null)}
                    loading={deletingNote}
                />
            )}
        </div>
    );
}

interface NoteModalProps {
    note: NoteResponse | null;
    onClose: () => void;
    onSave: (payload: { title: string; content: string; topic?: string }) => void;
    saving: boolean;
}

function NoteModal({ note, onClose, onSave, saving }: NoteModalProps) {
    const [title, setTitle] = useState(note?.title ?? '');
    const [content, setContent] = useState(note?.content ?? '');
    const [topic, setTopic] = useState(note?.topic ?? '');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        const t = title.trim();
        const c = content.trim();
        if (!t || !c) return;
        onSave({ title: t, content: c, topic: topic.trim() || undefined });
    };

    return (
        <div className="notes-modal-overlay" onClick={onClose}>
            <div className="notes-modal" onClick={(e) => e.stopPropagation()}>
                <div className="notes-modal-header">
                    <h2>{note ? 'Edit Note' : 'New Note'}</h2>
                    <button type="button" className="notes-modal-close" onClick={onClose} aria-label="Close"><X size={20} /></button>
                </div>
                <form id="notes-modal-form" onSubmit={handleSubmit} className="notes-modal-body">
                    <div className="notes-modal-field">
                        <label>Title *</label>
                        <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Note title" required />
                    </div>
                    <div className="notes-modal-field">
                        <label>Content *</label>
                        <textarea className="input" rows={6} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Write your note..." required />
                    </div>
                    <div className="notes-modal-field">
                        <label>Topic (optional)</label>
                        <input className="input" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. DSP, Algorithms" />
                    </div>
                </form>
                <div className="notes-modal-footer">
                    <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
                    <button type="submit" form="notes-modal-form" className="btn btn-primary" disabled={saving || !title.trim() || !content.trim()}>
                        <Save size={16} /> {saving ? 'Saving…' : (note ? 'Update' : 'Create')}
                    </button>
                </div>
            </div>
        </div>
    );
}
