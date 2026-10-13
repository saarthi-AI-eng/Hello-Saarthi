import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, Clock, BookOpen, Search, Plus, X, Save, Trash2 } from 'lucide-react';
import { useAuthStore } from '../stores/auth.store';
import { api, getUploadFullUrl, type VideoResponse, type PaginatedResponse, type CourseResponse } from '../lib/api';
import Pagination from '../components/Pagination';
import FileDropzone from '../components/FileDropzone';
import ConfirmModal from '../components/ConfirmModal';
import './Videos.css';

const PAGE_SIZE = 20;

function formatDuration(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return s ? `${m}:${s.toString().padStart(2, '0')}` : `${m} min`;
}

/** Extract YouTube video ID from watch or embed URL; return null if not YouTube. */
function youtubeEmbedUrl(watchOrEmbedUrl: string): string | null {
    const u = watchOrEmbedUrl.trim();
    const m = u.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/);
    return m ? `https://www.youtube.com/embed/${m[1]}` : null;
}

export default function VideosPage() {
    const { user } = useAuthStore();
    const isInstructor = user?.role === 'admin' || user?.role === 'teacher';

    const [search, setSearch] = useState('');
    const [videos, setVideos] = useState<VideoResponse[]>([]);
    const [total, setTotal] = useState(0);
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showAddModal, setShowAddModal] = useState(false);
    const [courses, setCourses] = useState<CourseResponse[]>([]);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [deleting, setDeleting] = useState(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const navigate = useNavigate();

    const toggleSelect = (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const toggleSelectAll = () => {
        if (selectedIds.size === filtered.length) setSelectedIds(new Set());
        else setSelectedIds(new Set(filtered.map((v) => v.id)));
    };

    const handleDeleteSelected = async () => {
        if (selectedIds.size === 0) return;
        setShowDeleteConfirm(true);
    };

    const confirmDeleteVideos = async () => {
        if (selectedIds.size === 0) return;
        setDeleting(true);
        setError(null);
        try {
            await Promise.all(Array.from(selectedIds).map((id) => api.delete(`/videos/${id}`)));
            setSelectedIds(new Set());
            await fetchVideos();
            setShowDeleteConfirm(false);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to delete some videos');
        } finally {
            setDeleting(false);
        }
    };

    const fetchVideos = useCallback(() => {
        return api.get<PaginatedResponse<VideoResponse>>('/videos', { limit: PAGE_SIZE, offset })
            .then((r) => {
                setVideos(r.items || []);
                setTotal(r.total ?? 0);
            });
    }, [offset]);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        fetchVideos()
            .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load videos'); })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [fetchVideos]);

    useEffect(() => {
        if (!isInstructor || !showAddModal) return;
        api.get<PaginatedResponse<CourseResponse>>('/courses', { limit: 100, offset: 0 })
            .then((r) => setCourses(r.items || []))
            .catch(() => setCourses([]));
    }, [isInstructor, showAddModal]);

    const filtered = videos.filter((v) =>
        !search.trim() ||
        v.title.toLowerCase().includes(search.toLowerCase())
    );

    return (
        <div className="videos-page">
            {error && <div className="videos-error" role="alert">{error}</div>}
            <div className="videos-header animate-fade-in">
                <div>
                    <h1>Video Library</h1>
                    <p>{isInstructor ? 'Manage and add videos' : 'Watch annotated lectures with integrated quizzes'}</p>
                </div>
                {isInstructor && (
                    <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
                        <Plus size={18} /> Add Video
                    </button>
                )}
            </div>
            <div className="videos-toolbar animate-fade-in delay-100">
                <div className="courses-search">
                    <Search size={18} />
                    <input type="text" placeholder="Filter videos..." value={search} onChange={(e) => setSearch(e.target.value)} />
                </div>
                {isInstructor && filtered.length > 0 && (
                    <div className="videos-toolbar-actions">
                        <label className="videos-select-all">
                            <input type="checkbox" checked={selectedIds.size === filtered.length && filtered.length > 0} onChange={toggleSelectAll} />
                            <span>Select all</span>
                        </label>
                    </div>
                )}
            </div>
            {isInstructor && selectedIds.size > 0 && (
                <div className="videos-selection-bar">
                    <span>{selectedIds.size} selected</span>
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => setSelectedIds(new Set())}>Clear</button>
                    <button type="button" className="btn btn-danger btn-sm" onClick={handleDeleteSelected} disabled={deleting}>
                        <Trash2 size={14} /> Delete
                    </button>
                </div>
            )}

            {loading && videos.length === 0 ? (
                <div className="videos-loading">Loading videos…</div>
            ) : !loading && filtered.length === 0 ? (
                <div className="videos-empty">
                    <div className="videos-empty-icon">🎬</div>
                    <h3>No videos found</h3>
                    <p>Try adjusting your search or filters</p>
                    {isInstructor && (
                        <button type="button" className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={() => setShowAddModal(true)}>
                            <Plus size={18} /> Add your first video
                        </button>
                    )}
                </div>
            ) : (
                <>
                    <div className="videos-grid animate-fade-in delay-200">
                        {filtered.map((video) => (
                            <div
                                key={video.id}
                                className={`video-card ${selectedIds.has(video.id) ? 'video-card-selected' : ''}`}
                            >
                                {isInstructor && (
                                    <div className="video-card-checkbox" onClick={(e) => toggleSelect(e, video.id)}>
                                        <input type="checkbox" checked={selectedIds.has(video.id)} readOnly />
                                    </div>
                                )}
                                <div className="video-card-clickable" onClick={() => navigate(`/videos/${video.id}`)}>
                                    <div className="video-card-thumb">
                                    {video.thumbnailUrl ? (
                                        <img src={video.thumbnailUrl} alt="" className="video-card-thumb-img" />
                                    ) : (
                                        <span className="video-card-emoji">🎬</span>
                                    )}
                                    <div className="video-card-overlay">
                                        <Play size={32} fill="white" />
                                    </div>
                                    <span className="video-card-duration"><Clock size={12} /> {formatDuration(video.durationSeconds)}</span>
                                </div>
                                <div className="video-card-body">
                                    <h3>{video.title}</h3>
                                    <div className="video-card-meta">
                                        {video.courseId && <span><BookOpen size={13} /> Course {video.courseId}</span>}
                                    </div>
                                </div>
                                </div>
                            </div>
                        ))}
                    </div>
                    {total > PAGE_SIZE && (
                        <Pagination total={total} limit={PAGE_SIZE} offset={offset} onPageChange={setOffset} />
                    )}
                </>
            )}

            {showAddModal && (
                <AddVideoModal
                    courses={courses}
                    onClose={() => setShowAddModal(false)}
                    onSaved={() => { setShowAddModal(false); fetchVideos(); }}
                    youtubeEmbedUrl={youtubeEmbedUrl}
                />
            )}

            <ConfirmModal
                open={showDeleteConfirm}
                title="Delete videos"
                message={`${selectedIds.size} video(s) will be permanently deleted. This cannot be undone.`}
                confirmLabel="Delete"
                variant="danger"
                onConfirm={confirmDeleteVideos}
                onCancel={() => setShowDeleteConfirm(false)}
                loading={deleting}
            />
        </div>
    );
}

interface AddVideoModalProps {
    courses: CourseResponse[];
    onClose: () => void;
    onSaved: () => void;
    youtubeEmbedUrl: (url: string) => string | null;
}

function AddVideoModal({ courses, onClose, onSaved, youtubeEmbedUrl }: AddVideoModalProps) {
    const [title, setTitle] = useState('');
    const [url, setUrl] = useState('');
    const [courseId, setCourseId] = useState<string>('');
    const [durationSeconds, setDurationSeconds] = useState(0);
    const [description, setDescription] = useState('');
    const [thumbnailUrl, setThumbnailUrl] = useState('');
    const [saving, setSaving] = useState(false);
    const [err, setErr] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setErr('');
        const embed = url.trim() ? youtubeEmbedUrl(url) : null;
        if (!url.trim()) {
            setErr('Please enter a video URL');
            return;
        }
        if (!embed && !url.match(/^https?:\/\//)) {
            setErr('Enter a valid YouTube URL (e.g. https://www.youtube.com/watch?v=...)');
            return;
        }
        if (!title.trim()) {
            setErr('Please enter a title');
            return;
        }
        setSaving(true);
        try {
            await api.post<VideoResponse>('/videos', {
                title: title.trim(),
                url: url.trim(),
                embedUrl: embed || url.trim(),
                durationSeconds: durationSeconds || 0,
                courseId: courseId ? parseInt(courseId, 10) : undefined,
                description: description.trim() || undefined,
                thumbnailUrl: thumbnailUrl.trim() || undefined,
            });
            onSaved();
        } catch (e) {
            setErr(e instanceof Error ? e.message : 'Failed to add video');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="course-modal-overlay" onClick={onClose}>
            <div className="course-modal animate-scale-in" onClick={(e) => e.stopPropagation()}>
                <div className="course-modal-header">
                    <h2>Add Video</h2>
                    <button type="button" className="course-modal-close" onClick={onClose}><X size={20} /></button>
                </div>
                <form onSubmit={handleSubmit} className="course-modal-body" id="add-video-form">
                    {err && <div className="videos-error" style={{ marginBottom: '1rem' }}>{err}</div>}
                    <div className="course-modal-field">
                        <label>Title *</label>
                        <input className="input" placeholder="e.g. Introduction to DSP" value={title} onChange={(e) => setTitle(e.target.value)} required />
                    </div>
                    <div className="course-modal-field">
                        <label>YouTube URL *</label>
                        <input className="input" placeholder="https://www.youtube.com/watch?v=..." value={url} onChange={(e) => setUrl(e.target.value)} />
                    </div>
                    <div className="course-modal-field">
                        <label>Course (optional)</label>
                        <select className="input" value={courseId} onChange={(e) => setCourseId(e.target.value)}>
                            <option value="">— None —</option>
                            {courses.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                        </select>
                    </div>
                    <div className="course-modal-field">
                        <label>Duration (seconds)</label>
                        <input className="input" type="number" min={0} value={durationSeconds || ''} onChange={(e) => setDurationSeconds(parseInt(e.target.value, 10) || 0)} />
                    </div>
                    <div className="course-modal-field">
                        <label>Thumbnail (optional)</label>
                        <FileDropzone
                            mode="upload"
                            onUploaded={(uploadPath) => setThumbnailUrl(getUploadFullUrl(uploadPath))}
                            onClear={() => setThumbnailUrl('')}
                            currentUrl={thumbnailUrl || null}
                            maxSizeMB={5}
                            accept="image/*"
                        />
                        <span className="course-modal-field-hint">Or paste thumbnail URL</span>
                        <input className="input" placeholder="https://..." value={thumbnailUrl} onChange={(e) => setThumbnailUrl(e.target.value)} />
                    </div>
                    <div className="course-modal-field">
                        <label>Description (optional)</label>
                        <textarea className="input" rows={2} placeholder="Short description..." value={description} onChange={(e) => setDescription(e.target.value)} />
                    </div>
                </form>
                <div className="course-modal-footer">
                    <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
                    <button type="submit" form="add-video-form" className="btn btn-primary" disabled={saving}>
                        <Save size={16} /> {saving ? 'Adding…' : 'Add Video'}
                    </button>
                </div>
            </div>
        </div>
    );
}
