import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { usePageTitle } from '../lib/usePageTitle';
import {
    Search, Grid3X3, List, BookOpen,
    Plus, Edit3, Trash2, X, Save, LogIn
} from 'lucide-react';
import { useAuthStore } from '../stores/auth.store';
import { api, type CourseResponse, type PaginatedResponse, type EnrollmentWithCourseResponse, type MyInviteResponse } from '../lib/api';
import Pagination from '../components/Pagination';
import { useToast } from '../components/Toast';
import './Courses.css';

// Only fields the backend stores. Category, difficulty, duration and lesson count were
// form-only values that the API dropped, so they are not shown or edited.
interface CourseItem {
    id: string;
    title: string;
    code: string;
    instructor: string;
    progress: number;
    thumbnail: string;
    description: string;
}

function mapCourse(c: CourseResponse, progressPercent = 0): CourseItem {
    return {
        id: c.id,
        title: c.title,
        code: c.code,
        instructor: c.instructor,
        progress: progressPercent,
        thumbnail: c.thumbnailEmoji || '📚',
        description: c.description || '',
    };
}

const PAGE_SIZE = 20;

export default function CoursesPage() {
    usePageTitle('Courses');
    const { user } = useAuthStore();
    const isAdmin = user?.role === 'admin';
    const isInstructor = isAdmin || user?.role === 'teacher';

    const [courses, setCourses] = useState<CourseItem[]>([]);
    const [total, setTotal] = useState(0);
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [enrolledIds, setEnrolledIds] = useState<Record<string, number>>({});
    const [search, setSearch] = useState('');
    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
    const [invites, setInvites] = useState<MyInviteResponse[]>([]);
    const [inviteBusyId, setInviteBusyId] = useState<string | null>(null);
    const [reloadKey, setReloadKey] = useState(0); // bumped after accepting an invite to refresh the list
    const navigate = useNavigate();
    const toast = useToast();
    const [searchParams, setSearchParams] = useSearchParams();

    useEffect(() => {
        let cancelled = false;
        (async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await api.get<PaginatedResponse<CourseResponse>>('/courses', { limit: PAGE_SIZE, offset });
                if (cancelled) return;
                const progressMap: Record<string, number> = {};
                const enrollmentsRes = await api.get<PaginatedResponse<EnrollmentWithCourseResponse>>('/courses/my/enrollments', { limit: 100, offset: 0 });
                (enrollmentsRes.items || []).forEach((e) => { progressMap[e.courseId] = e.progressPercent; });
                setEnrolledIds(progressMap);
                setCourses((res.items || []).map((c) => mapCourse(c, progressMap[c.id] ?? 0)));
                setTotal(res.total ?? 0);
            } catch (e) {
                if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load courses');
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [offset, reloadKey]);

    // Email invites from teachers, shown to students as cards they can accept or reject.
    useEffect(() => {
        if (isInstructor) return;
        let cancelled = false;
        api.get<MyInviteResponse[]>('/courses/my/invites')
            .then((items) => { if (!cancelled) setInvites(items); })
            .catch(() => { /* the course list still works without invites */ });
        return () => { cancelled = true; };
    }, [isInstructor]);

    const acceptInvite = async (invite: MyInviteResponse) => {
        setInviteBusyId(invite.id);
        try {
            await api.post('/courses/join', { inviteCode: invite.inviteCode });
            setInvites((prev) => prev.filter((i) => i.id !== invite.id));
            setReloadKey((k) => k + 1);
            toast.showToast(`You joined ${invite.courseTitle}`);
        } catch (e) {
            toast.showToast(e instanceof Error ? e.message : 'Could not join the course', 'error');
        } finally {
            setInviteBusyId(null);
        }
    };

    const rejectInvite = async (invite: MyInviteResponse) => {
        setInviteBusyId(invite.id);
        try {
            await api.post(`/courses/invites/${invite.id}/decline`);
            setInvites((prev) => prev.filter((i) => i.id !== invite.id));
            toast.showToast(`Invite to ${invite.courseTitle} declined`);
        } catch (e) {
            toast.showToast(e instanceof Error ? e.message : 'Could not decline the invite', 'error');
        } finally {
            setInviteBusyId(null);
        }
    };

    // Modal state
    const [showModal, setShowModal] = useState(false);
    const [editingCourse, setEditingCourse] = useState<CourseItem | null>(null);
    const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

    // Join with code (student)
    const [showJoinModal, setShowJoinModal] = useState(false);
    const [joinCode, setJoinCode] = useState('');
    const [joinLoading, setJoinLoading] = useState(false);
    const [joinError, setJoinError] = useState('');
    const [joinSuccess, setJoinSuccess] = useState('');

    // Invite links land here as /courses?code=XXXX: open the join dialog with the code filled in.
    useEffect(() => {
        const code = searchParams.get('code');
        if (!code || isInstructor) return;
        setJoinCode(code);
        setShowJoinModal(true);
        setSearchParams({}, { replace: true });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleJoinCourse = async () => {
        if (!joinCode.trim()) return;
        setJoinLoading(true);
        setJoinError('');
        setJoinSuccess('');
        try {
            const res = await api.post<{ courseId: string; courseTitle: string; message: string }>('/courses/join', { inviteCode: joinCode.trim() });
            setJoinSuccess(`You joined "${res.courseTitle}"! Refreshing...`);
            setJoinCode('');
            setTimeout(() => { setShowJoinModal(false); setJoinSuccess(''); window.location.reload(); }, 1800);
        } catch (e) {
            setJoinError(e instanceof Error ? e.message : 'Invalid or expired invite code.');
        } finally {
            setJoinLoading(false);
        }
    };

    // Form state
    const [formData, setFormData] = useState<Partial<CourseItem>>({});

    const filtered = courses.filter((c) => {
        if (!isInstructor && enrolledIds[c.id] === undefined) return false;
        return !search.trim() || c.title.toLowerCase().includes(search.toLowerCase()) || c.code.toLowerCase().includes(search.toLowerCase());
    });

    // Admin CRUD
    const openCreate = () => {
        setEditingCourse(null);
        setFormData({ title: '', code: '', instructor: '', description: '', thumbnail: '📚' });
        setShowModal(true);
    };

    const openEdit = (course: CourseItem) => {
        setEditingCourse(course);
        setFormData({ ...course });
        setShowModal(true);
    };

    const handleSave = async () => {
        const title = (formData.title || '').trim();
        const code = (formData.code || '').trim();
        const instructor = (formData.instructor || user?.name || 'Instructor').trim();
        if (!title || !code || !instructor) {
            return;
        }
        const payload = {
            title,
            code,
            instructor,
            description: (formData.description || '').trim() || undefined,
            thumbnailEmoji: (formData.thumbnail || '📚').trim() || undefined,
        };
        try {
            if (editingCourse) {
                const updated = await api.patch<CourseResponse>(`/courses/${editingCourse.id}`, payload);
                setCourses((prev) => prev.map((c) => (c.id === updated.id ? mapCourse(updated, c.progress) : c)));
                toast.showToast('Course updated');
            } else {
                const created = await api.post<CourseResponse>('/courses', payload);
                setCourses((prev) => [mapCourse(created), ...prev]);
                setTotal((t) => t + 1);
            }
            setShowModal(false);
        } catch (e) {
            const msg = e instanceof Error ? e.message : 'Failed to save course';
            setError(msg);
            toast.showToast(msg, 'error');
        }
    };

    const handleDelete = async (id: string) => {
        const prevCourses = courses;
        setCourses((prev) => prev.filter((c) => c.id !== id));
        setDeleteConfirm(null);
        try {
            await api.delete(`/courses/${id}`);
            setTotal((t) => Math.max(0, t - 1));
            toast.showToast('Course deleted successfully');
        } catch (e) {
            setCourses(prevCourses);
            const msg = e instanceof Error ? e.message : 'Failed to delete course';
            setError(msg);
            toast.showToast(msg, 'error');
        }
    };

    return (
        <div className="courses-page">
            {error && <div className="courses-error" role="alert">{error}</div>}
            {/* Header */}
            <div className="courses-header">
                <div>
                    <h1>Courses</h1>
                    <p>{isInstructor ? 'Manage and create courses' : 'Your courses — join a new one with a class code'}</p>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {!isInstructor && (
                        <button className="btn btn-outline" onClick={() => { setShowJoinModal(true); setJoinError(''); setJoinSuccess(''); }}>
                            <LogIn size={18} /> Join with Code
                        </button>
                    )}
                    {isInstructor && (
                        <button className="btn btn-primary" onClick={openCreate}>
                            <Plus size={18} /> Create Course
                        </button>
                    )}
                </div>
            </div>

            {/* Toolbar */}
            <div className="courses-toolbar">
                <div className="courses-search">
                    <Search size={18} />
                    <input placeholder="Search courses..." value={search} onChange={(e) => setSearch(e.target.value)} />
                </div>
                <div className="courses-toolbar-right">
                    <div className="courses-view-toggle">
                        <button className={viewMode === 'grid' ? 'active' : ''} onClick={() => setViewMode('grid')}><Grid3X3 size={16} /></button>
                        <button className={viewMode === 'list' ? 'active' : ''} onClick={() => setViewMode('list')}><List size={16} /></button>
                    </div>
                </div>
            </div>

            {/* Grid / List */}
            {loading && filtered.length === 0 ? (
                <div className={`courses-grid ${viewMode} courses-skeleton-grid`}>
                    {Array.from({ length: 6 }).map((_, i) => (
                        <div key={i} className={`course-card-skeleton ${viewMode}`}>
                            <div className="skeleton course-card-skeleton-thumb" />
                            <div className="course-card-skeleton-body">
                                <div className="skeleton course-card-skeleton-line" style={{ width: '40%' }} />
                                <div className="skeleton course-card-skeleton-line" style={{ width: '90%' }} />
                                <div className="skeleton course-card-skeleton-line" style={{ width: '60%' }} />
                                <div className="course-card-skeleton-meta">
                                    <div className="skeleton course-card-skeleton-chip" />
                                    <div className="skeleton course-card-skeleton-chip" />
                                </div>
                                <div className="skeleton course-card-skeleton-btn" />
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
            <div className={`courses-grid ${viewMode}`}>
                {invites.map((inv) => (
                    <div key={`invite-${inv.id}`} className={`course-card course-card-invite ${viewMode}`}>
                        <div className="course-card-thumb">
                            <span className="course-card-emoji">{inv.thumbnailEmoji || '📚'}</span>
                            <span className="course-card-badge course-card-badge-invite">Invitation</span>
                        </div>
                        <div className="course-card-body">
                            <div className="course-card-top">
                                <span className="course-card-code">{inv.courseCode}</span>
                            </div>
                            <h3 className="course-card-title">{inv.courseTitle}</h3>
                            <p className="course-card-instructor">{inv.instructor}</p>
                            <div className="course-card-footer">
                                <div className="course-card-admin-actions">
                                    <button className="btn btn-primary btn-sm" disabled={inviteBusyId === inv.id} onClick={() => acceptInvite(inv)}>Accept</button>
                                    <button className="btn btn-outline btn-sm" disabled={inviteBusyId === inv.id} onClick={() => rejectInvite(inv)}>Reject</button>
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
                {filtered.map((course) => (
                    <div key={course.id} className={`course-card ${viewMode}`} onClick={() => navigate(`/courses/${course.id}`)} style={{ cursor: 'pointer' }}>
                        <div className="course-card-thumb">
                            <span className="course-card-emoji">{course.thumbnail}</span>
                        </div>
                        <div className="course-card-body">
                            <div className="course-card-top">
                                <span className="course-card-code">{course.code}</span>
                            </div>
                            <h3 className="course-card-title">{course.title}</h3>
                            <p className="course-card-instructor">{course.instructor}</p>
                            {viewMode === 'list' && <p className="course-card-desc">{course.description}</p>}
                            <div className="course-card-footer">
                                {isInstructor ? (
                                    <div className="course-card-admin-actions">
                                        <button className="btn btn-outline btn-sm" onClick={(ev) => { ev.stopPropagation(); openEdit(course); }}><Edit3 size={14} /> Edit</button>
                                        {deleteConfirm === course.id ? (
                                            <div className="course-card-delete-confirm">
                                                <span>Delete?</span>
                                                <button className="btn btn-sm" style={{ background: 'var(--error)', color: 'white' }} onClick={(ev) => { ev.stopPropagation(); void handleDelete(course.id); }}>Yes</button>
                                                <button className="btn btn-outline btn-sm" onClick={(ev) => { ev.stopPropagation(); setDeleteConfirm(null); }}>No</button>
                                            </div>
                                        ) : (
                                            <button className="btn btn-outline btn-sm" style={{ borderColor: 'var(--error)', color: 'var(--error)' }} onClick={(ev) => { ev.stopPropagation(); setDeleteConfirm(course.id); }}><Trash2 size={14} /> Delete</button>
                                        )}
                                    </div>
                                ) : (
                                    <button
                                        className="btn btn-primary btn-sm"
                                        onClick={(ev) => { ev.stopPropagation(); navigate(`/courses/${course.id}`); }}
                                    >
                                        Continue
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
            )}

            {!loading && filtered.length === 0 && invites.length === 0 && (
                <div className="courses-empty">
                    <BookOpen size={48} />
                    <h3>No courses found</h3>
                    <p>{isInstructor ? 'Try adjusting your search or filters' : 'Enter the class code from your teacher above to join a course'}</p>
                </div>
            )}
            {!loading && total > 0 && (
                <Pagination total={total} limit={PAGE_SIZE} offset={offset} onPageChange={setOffset} />
            )}

            {/* Create / Edit Modal */}
            {showModal && (
                <div className="course-modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="course-modal animate-scale-in" onClick={(e) => e.stopPropagation()}>
                        <div className="course-modal-header">
                            <h2>{editingCourse ? 'Edit Course' : 'Create New Course'}</h2>
                            <button className="course-modal-close" onClick={() => setShowModal(false)}><X size={20} /></button>
                        </div>
                        <div className="course-modal-body">
                            <div className="course-modal-field">
                                <label>Course Title *</label>
                                <input className="input" placeholder="e.g. Machine Learning Fundamentals" value={formData.title || ''} onChange={(e) => setFormData({ ...formData, title: e.target.value })} />
                            </div>
                            <div className="course-modal-row">
                                <div className="course-modal-field">
                                    <label>Course Code *</label>
                                    <input className="input" placeholder="e.g. CS401" value={formData.code || ''} onChange={(e) => setFormData({ ...formData, code: e.target.value })} />
                                </div>
                                <div className="course-modal-field">
                                    <label>Emoji Icon</label>
                                    <input className="input" value={formData.thumbnail || ''} onChange={(e) => setFormData({ ...formData, thumbnail: e.target.value })} />
                                </div>
                            </div>
                            <div className="course-modal-field">
                                <label>Instructor</label>
                                <input className="input" placeholder="e.g. Dr. Sharma" value={formData.instructor || ''} onChange={(e) => setFormData({ ...formData, instructor: e.target.value })} />
                            </div>
                            <div className="course-modal-field">
                                <label>Description</label>
                                <textarea className="input" rows={3} placeholder="Course description..." value={formData.description || ''} onChange={(e) => setFormData({ ...formData, description: e.target.value })} />
                            </div>
                        </div>
                        <div className="course-modal-footer">
                            <button className="btn btn-outline" onClick={() => setShowModal(false)}>Cancel</button>
                            <button className="btn btn-primary" onClick={handleSave}>
                                <Save size={16} /> {editingCourse ? 'Update Course' : 'Create Course'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
            {/* Join with Code Modal (student) */}
            {showJoinModal && (
                <div className="course-modal-overlay" onClick={() => setShowJoinModal(false)}>
                    <div className="course-modal animate-scale-in" onClick={e => e.stopPropagation()} style={{ maxWidth: '420px' }}>
                        <div className="course-modal-header">
                            <h2><LogIn size={18} /> Join with Invite Code</h2>
                            <button className="course-modal-close" onClick={() => setShowJoinModal(false)}><X size={20} /></button>
                        </div>
                        <div className="course-modal-body">
                            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                                Enter the invite code your teacher shared with you.
                            </p>
                            <div className="course-modal-field">
                                <label>Invite Code</label>
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <input
                                        className="input"
                                        placeholder="e.g. aB3xYz9Qr1"
                                        value={joinCode}
                                        onChange={e => setJoinCode(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && handleJoinCourse()}
                                        autoFocus
                                    />
                                    <button className="btn btn-primary" onClick={handleJoinCourse} disabled={joinLoading || !joinCode.trim()}>
                                        {joinLoading ? <span className="loading loading-spinner loading-sm"></span> : 'Join'}
                                    </button>
                                </div>
                            </div>
                            {joinError && <p style={{ color: 'var(--error)', fontSize: '0.8125rem', marginTop: '0.5rem' }}>{joinError}</p>}
                            {joinSuccess && <p style={{ color: 'var(--accent)', fontSize: '0.875rem', fontWeight: 600, marginTop: '0.5rem' }}>{joinSuccess}</p>}
                        </div>
                        <div className="course-modal-footer">
                            <button className="btn btn-outline" onClick={() => setShowJoinModal(false)}>Cancel</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
