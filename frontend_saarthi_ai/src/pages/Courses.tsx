import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePageTitle } from '../lib/usePageTitle';
import {
    Search, Filter, Grid3X3, List, BookOpen, Clock, Users, Star,
    ChevronDown, Plus, Edit3, Trash2, X, Save, BarChart3, LogIn
} from 'lucide-react';
import { useAuthStore } from '../stores/auth.store';
import { api, type CourseResponse, type PaginatedResponse, type EnrollmentWithCourseResponse } from '../lib/api';
import Pagination from '../components/Pagination';
import { useToast } from '../components/Toast';
import './Courses.css';

interface CourseItem {
    id: string;
    title: string;
    code: string;
    instructor: string;
    category: string;
    difficulty: 'Beginner' | 'Intermediate' | 'Advanced';
    duration: string;
    lessons: number;
    rating: number;
    students: number;
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
        category: 'Course',
        difficulty: 'Intermediate',
        duration: '',
        lessons: 0,
        rating: 0,
        students: 0,
        progress: progressPercent,
        thumbnail: c.thumbnailEmoji || '📚',
        description: c.description || '',
    };
}

const categories = ['All', 'Computer Science', 'Electronics', 'Mathematics'];
const difficulties = ['All', 'Beginner', 'Intermediate', 'Advanced'];
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
    const [category, setCategory] = useState('All');
    const [difficulty, setDifficulty] = useState('All');
    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
    const [showFilters, setShowFilters] = useState(false);
    const navigate = useNavigate();
    const toast = useToast();

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
    }, [offset]);

    const handleEnroll = async (courseId: string) => {
        try {
            await api.post(`/courses/${courseId}/enroll`);
            setEnrolledIds((prev) => ({ ...prev, [courseId]: 0 }));
            setCourses((prev) => prev.map((c) => (c.id === courseId ? { ...c, progress: 0 } : c)));
            toast.showToast('Enrolled successfully');
        } catch (e) {
            toast.showToast(e instanceof Error ? e.message : 'Enroll failed', 'error');
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
        const matchSearch = !search.trim() || c.title.toLowerCase().includes(search.toLowerCase()) || c.code.toLowerCase().includes(search.toLowerCase());
        const matchCat = category === 'All' || c.category === category;
        const matchDiff = difficulty === 'All' || c.difficulty === difficulty;
        return matchSearch && matchCat && matchDiff;
    });

    const diffColor = (d: string) => {
        if (d === 'Beginner') return '#5E8D83';
        if (d === 'Intermediate') return '#8C7A4A';
        return '#7A5A6E';
    };

    // Admin CRUD
    const openCreate = () => {
        setEditingCourse(null);
        setFormData({ title: '', code: '', instructor: '', category: 'Computer Science', difficulty: 'Beginner', duration: '', lessons: 0, description: '', thumbnail: '📚' });
        setShowModal(true);
    };

    const openEdit = (course: CourseItem) => {
        setEditingCourse(course);
        setFormData({ ...course });
        setShowModal(true);
    };

    const handleSave = async () => {
        if (editingCourse) {
            setCourses((prev) => prev.map((c) => (c.id === editingCourse.id ? { ...c, ...formData } as CourseItem : c)));
            setShowModal(false);
            return;
        }
        const title = (formData.title || '').trim();
        const code = (formData.code || '').trim();
        const instructor = (formData.instructor || user?.name || 'Instructor').trim();
        if (!title || !code || !instructor) {
            return;
        }
        try {
            const created = await api.post<CourseResponse>('/courses', {
                title,
                code,
                instructor,
                description: (formData.description || '').trim() || undefined,
                thumbnailEmoji: (formData.thumbnail || '📚').trim() || undefined,
                color: undefined,
            });
            const newCourse: CourseItem = {
                id: created.id,
                title: created.title,
                code: created.code,
                instructor: created.instructor,
                category: formData.category || 'Computer Science',
                difficulty: (formData.difficulty as CourseItem['difficulty']) || 'Beginner',
                duration: formData.duration || '12 weeks',
                lessons: formData.lessons || 0,
                rating: 0,
                students: 0,
                progress: 0,
                thumbnail: created.thumbnailEmoji || '📚',
                description: created.description || '',
            };
            setCourses((prev) => [newCourse, ...prev]);
            setTotal((t) => t + 1);
            setShowModal(false);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to create course');
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
                    <p>{isInstructor ? 'Manage and create courses' : 'Browse and enroll in courses'}</p>
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
                    <button className={`courses-filter-toggle ${showFilters ? 'active' : ''}`} onClick={() => setShowFilters(!showFilters)}>
                        <Filter size={16} /> Filters <ChevronDown size={14} />
                    </button>
                    <div className="courses-view-toggle">
                        <button className={viewMode === 'grid' ? 'active' : ''} onClick={() => setViewMode('grid')}><Grid3X3 size={16} /></button>
                        <button className={viewMode === 'list' ? 'active' : ''} onClick={() => setViewMode('list')}><List size={16} /></button>
                    </div>
                </div>
            </div>

            {/* Filters */}
            {showFilters && (
                <div className="courses-filters animate-fade-in">
                    <div className="courses-filter-group">
                        <label>Category</label>
                        <select value={category} onChange={(e) => setCategory(e.target.value)}>
                            {categories.map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                    </div>
                    <div className="courses-filter-group">
                        <label>Difficulty</label>
                        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                            {difficulties.map((d) => <option key={d} value={d}>{d}</option>)}
                        </select>
                    </div>
                    <span className="courses-result-count">{filtered.length} courses found</span>
                </div>
            )}

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
                {filtered.map((course) => (
                    <div key={course.id} className={`course-card ${viewMode}`} onClick={() => navigate(`/courses/${course.id}`)} style={{ cursor: 'pointer' }}>
                        <div className="course-card-thumb">
                            <span className="course-card-emoji">{course.thumbnail}</span>
                            <span className="course-card-badge" style={{ background: diffColor(course.difficulty) }}>{course.difficulty}</span>
                        </div>
                        <div className="course-card-body">
                            <div className="course-card-top">
                                <span className="course-card-code">{course.code}</span>
                                <div className="course-card-rating"><Star size={12} fill="var(--text-muted)" stroke="var(--text-muted)" /> {course.rating}</div>
                            </div>
                            <h3 className="course-card-title">{course.title}</h3>
                            <p className="course-card-instructor">{course.instructor}</p>
                            {viewMode === 'list' && <p className="course-card-desc">{course.description}</p>}
                            <div className="course-card-meta">
                                <span><BookOpen size={14} /> {course.lessons} lessons</span>
                                <span><Clock size={14} /> {course.duration}</span>
                                <span><Users size={14} /> {course.students}</span>
                            </div>
                            {/* Progress bar for students */}
                            {!isInstructor && course.progress > 0 && (
                                <div className="course-card-progress">
                                    <div className="course-card-progress-bar">
                                        <div className="course-card-progress-fill" style={{ width: `${course.progress}%` }} />
                                    </div>
                                    <span>{course.progress}%</span>
                                </div>
                            )}
                            {/* Student stats for admin */}
                            {isInstructor && (
                                <div className="course-card-admin-stats">
                                    <span><BarChart3 size={14} /> {course.students} enrolled</span>
                                    <span>⭐ {course.rating}/5</span>
                                </div>
                            )}
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
                                        onClick={(ev) => {
                                            ev.stopPropagation();
                                            if (enrolledIds[course.id] !== undefined) navigate(`/courses/${course.id}`);
                                            else handleEnroll(course.id);
                                        }}
                                    >
                                        {enrolledIds[course.id] !== undefined ? 'Continue' : 'Enroll'}
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
            )}

            {!loading && filtered.length === 0 && (
                <div className="courses-empty">
                    <BookOpen size={48} />
                    <h3>No courses found</h3>
                    <p>Try adjusting your search or filters</p>
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
                            <div className="course-modal-row">
                                <div className="course-modal-field">
                                    <label>Category</label>
                                    <select className="input" value={formData.category || ''} onChange={(e) => setFormData({ ...formData, category: e.target.value })}>
                                        {categories.filter(c => c !== 'All').map((c) => <option key={c} value={c}>{c}</option>)}
                                    </select>
                                </div>
                                <div className="course-modal-field">
                                    <label>Difficulty</label>
                                    <select className="input" value={formData.difficulty || ''} onChange={(e) => setFormData({ ...formData, difficulty: e.target.value as CourseItem['difficulty'] })}>
                                        {difficulties.filter(d => d !== 'All').map((d) => <option key={d} value={d}>{d}</option>)}
                                    </select>
                                </div>
                            </div>
                            <div className="course-modal-row">
                                <div className="course-modal-field">
                                    <label>Instructor</label>
                                    <input className="input" placeholder="e.g. Dr. Sharma" value={formData.instructor || ''} onChange={(e) => setFormData({ ...formData, instructor: e.target.value })} />
                                </div>
                                <div className="course-modal-field">
                                    <label>Duration</label>
                                    <input className="input" placeholder="e.g. 12 weeks" value={formData.duration || ''} onChange={(e) => setFormData({ ...formData, duration: e.target.value })} />
                                </div>
                            </div>
                            <div className="course-modal-field">
                                <label>Number of Lessons</label>
                                <input className="input" type="number" value={formData.lessons || 0} onChange={(e) => setFormData({ ...formData, lessons: parseInt(e.target.value) || 0 })} />
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
