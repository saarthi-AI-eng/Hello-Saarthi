import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    ArrowLeft, Plus, FileText, Video, BookOpen, Trash2, X, Save, Paperclip,
    Link as LinkIcon, Heading, Pencil, ExternalLink, Send, Sparkles, Users,
    Mail, LogIn, CheckCircle2, XCircle
} from 'lucide-react';
import { useAuthStore } from '../stores/auth.store';
import StreamComments from '../components/StreamComments';
import AssignmentDialog from '../components/AssignmentDialog';
import AuthImage from '../components/AuthImage';
import { formatDue, isClosed, statusLabel, toDateTimeLocal } from '../lib/assignmentStatus';
import { api, authFetch, getAllPages, uploadFile, getUploadFullUrl, getMaterialFileUrl, type CourseResponse, type PaginatedResponse, type AssignmentResponse, type MaterialResponse, type StreamItemResponse, type CoursePersonResponse, type VideoResponse } from '../lib/api';
import Pagination from '../components/Pagination';
import FileDropzone from '../components/FileDropzone';
import ConfirmModal from '../components/ConfirmModal';
import EmptyState from '../components/EmptyState';
import { useToast } from '../components/Toast';
import './CourseDetail.css';

const PAGE_SIZE = 20;

/* ── Types ── */
interface Assignment {
    id: string;
    title: string;
    description: string;
    dueDate: string;
    points: number;
    status: 'pending' | 'submitted' | 'graded';
    grade?: number;
    attachments: string[];
    createdAt: string;
    topic: string;
    submittedAt?: string | null;
    attachmentUrl?: string | null;
    hardDeadline?: boolean;
}

interface Material {
    id: string;
    title: string;
    description: string;
    type: 'pdf' | 'doc' | 'link' | 'slide';
    url: string;
    createdAt: string;
    topic: string;
}

interface VideoLecture {
    id: string;
    title: string;
    description: string;
    duration: string;
    thumbnail: string;
    url: string;
    watched: boolean;
    createdAt: string;
    topic: string;
}

interface StreamItem {
    id: string;
    type: 'assignment' | 'material' | 'video' | 'announcement';
    title: string;
    description: string;
    createdAt: string;
    author: string;
    comments?: { id: string, text: string, author: string, createdAt: string }[];
    // Announcements store a public url; material posts store the material's id.
    attachments?: { name: string, url?: string, materialId?: string }[];
}

type DocChatMessage = { role: 'user' | 'assistant'; content: string };

const tabs = [
    { id: 'stream', label: 'Stream' },
    { id: 'classwork', label: 'Classwork' },
    { id: 'people', label: 'People' },
];

type ModalType = 'assignment' | 'material' | 'video' | 'topic' | null;

function mapAssignment(a: AssignmentResponse): Assignment {
    return {
        id: a.id,
        title: a.title,
        description: a.description ?? '',
        dueDate: a.dueDate,
        points: a.points,
        status: (a.status as Assignment['status']) || 'pending',
        grade: a.grade,
        attachments: a.attachments ? [a.attachments] : [],
        createdAt: a.createdAt,
        topic: a.topic ?? 'No topic',
        submittedAt: a.submittedAt,
        attachmentUrl: a.attachmentUrl,
        hardDeadline: a.hardDeadline,
    };
}

function mapMaterial(m: MaterialResponse): Material {
    const created = new Date(m.createdAt);
    return {
        id: m.id,
        title: m.title,
        description: m.description ?? '',
        type: m.type as Material['type'],
        url: m.url,
        createdAt: Number.isNaN(created.getTime()) ? m.createdAt : created.toLocaleDateString(undefined, { dateStyle: 'medium' }),
        topic: m.topic ?? 'No topic',
    };
}

function mapVideo(v: VideoResponse): VideoLecture {
    const m = Math.floor(v.durationSeconds / 60);
    const s = String(v.durationSeconds % 60).padStart(2, '0');
    return {
        id: v.id,
        title: v.title,
        description: v.description ?? '',
        duration: v.durationSeconds ? `${m}:${s}` : '',
        thumbnail: '🎬',
        url: v.url,
        watched: false,
        createdAt: '',
        topic: 'Video Lectures',  // videos have no topic column yet
    };
}

/** "45:20" or "1:02:03" -> seconds; a bare number is minutes. */
function parseDuration(text: string | undefined): number {
    const parts = (text ?? '').split(':').map((p) => parseInt(p, 10));
    if (parts.length === 0 || parts.some(Number.isNaN)) return 0;
    if (parts.length === 1) return parts[0] * 60;
    return parts.reduce((acc, p) => acc * 60 + p, 0);
}

function mapStreamItem(s: StreamItemResponse): StreamItem {
    let raw = s.description || '';
    let description = raw;
    let comments: { id: string, text: string, author: string, createdAt: string }[] = [];
    let attachments: { name: string, url?: string, materialId?: string }[] = [];

    // Parse out attachments first
    if (description.includes('___ATTACHMENTS___')) {
        const parts = description.split('___ATTACHMENTS___');
        description = parts[0];
        try { attachments = JSON.parse(parts[1]); } catch { /* ignore */ }
    }
    // Then parse comments (which comes after attachments in the stored string)
    if (description.includes('___COMMENTS___')) {
        const parts = description.split('___COMMENTS___');
        description = parts[0];
        try { comments = JSON.parse(parts[1]); } catch { /* ignore */ }
    }

    const created = new Date(s.createdAt);
    return {
        id: s.id,
        type: (s.type as StreamItem['type']) || 'announcement',
        title: s.title ?? '',
        description,
        createdAt: Number.isNaN(created.getTime()) ? s.createdAt : created.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }),
        author: s.author,
        comments,
        attachments,
    };
}

export default function CourseDetailPage() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const { user } = useAuthStore();
    const toast = useToast();
    const isAdmin = user?.role === 'admin';
    const isInstructor = isAdmin || user?.role === 'teacher';
    const courseId = id ?? '';

    const [course, setCourse] = useState<CourseResponse | null>(null);
    const [courseLoading, setCourseLoading] = useState(true);
    const [courseError, setCourseError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState('stream');
    const [assignments, setAssignments] = useState<Assignment[]>([]);
    const [materials, setMaterials] = useState<Material[]>([]);
    const [stream, setStream] = useState<StreamItem[]>([]);
    const [streamTotal, setStreamTotal] = useState(0);
    const [streamOffset, setStreamOffset] = useState(0);
    const [people, setPeople] = useState<CoursePersonResponse[]>([]);
    const [peopleTotal, setPeopleTotal] = useState(0);
    const [peopleOffset, setPeopleOffset] = useState(0);
    const [videos, setVideos] = useState<VideoLecture[]>([]);
    const [topics, setTopics] = useState<string[]>(['Course Materials', 'Class Work', 'Projects', 'Video Lectures', 'Post Exam - Solutions']);

    const courseDisplay = course ? { title: course.title, code: course.code, instructor: course.instructor, emoji: course.thumbnailEmoji || '📚', color: course.color || '#3f4244' } : { title: '…', code: '', instructor: '', emoji: '📚', color: '#3f4244' };
    const userName = user?.name || (isInstructor ? courseDisplay.instructor : 'Student');

    useEffect(() => {
        if (!courseId) return;
        let cancelled = false;
        setCourseLoading(true);
        setCourseError(null);
        api.get<CourseResponse>(`/courses/${courseId}`)
            .then((c) => { if (!cancelled) setCourse(c); })
            .catch((e) => { if (!cancelled) setCourseError(e instanceof Error ? e.message : 'Course not found'); })
            .finally(() => { if (!cancelled) setCourseLoading(false); });
        return () => { cancelled = true; };
    }, [courseId]);

    // Classwork groups assignments and materials by topic, so it needs every item, not one page.
    useEffect(() => {
        if (!courseId) return;
        let cancelled = false;
        getAllPages<AssignmentResponse>(`/courses/${courseId}/assignments`)
            .then((items) => { if (!cancelled) setAssignments(items.map(mapAssignment)); })
            .catch(() => { if (!cancelled) setAssignments([]); });
        return () => { cancelled = true; };
    }, [courseId]);

    useEffect(() => {
        if (!courseId) return;
        let cancelled = false;
        getAllPages<MaterialResponse>(`/courses/${courseId}/materials`)
            .then((items) => { if (!cancelled) setMaterials(items.map(mapMaterial)); })
            .catch(() => { if (!cancelled) setMaterials([]); });
        return () => { cancelled = true; };
    }, [courseId]);

    useEffect(() => {
        if (!courseId) return;
        let cancelled = false;
        api.get<PaginatedResponse<VideoResponse>>('/videos', { course_id: courseId, limit: 100, offset: 0 })
            .then((r) => { if (!cancelled) setVideos((r.items || []).map(mapVideo)); })
            .catch(() => { if (!cancelled) setVideos([]); });
        return () => { cancelled = true; };
    }, [courseId]);

    // Topics live on the items; keep any topic that an item uses so it survives a reload.
    useEffect(() => {
        const used = [...assignments, ...materials].map((i) => i.topic).filter((t) => t && t !== 'No topic');
        setTopics((prev) => {
            const extra = used.filter((t, i) => !prev.includes(t) && used.indexOf(t) === i);
            return extra.length ? [...prev, ...extra] : prev;
        });
    }, [assignments, materials]);

    useEffect(() => {
        if (!courseId) return;
        let cancelled = false;
        api.get<PaginatedResponse<StreamItemResponse>>(`/courses/${courseId}/stream`, { limit: PAGE_SIZE, offset: streamOffset })
            .then((r) => { if (!cancelled) { setStream((r.items || []).map(mapStreamItem)); setStreamTotal(r.total ?? 0); } })
            .catch(() => { if (!cancelled) setStream([]); });
        return () => { cancelled = true; };
    }, [courseId, streamOffset]);

    useEffect(() => {
        if (!courseId || activeTab !== 'people') return;
        let cancelled = false;
        api.get<PaginatedResponse<CoursePersonResponse>>(`/courses/${courseId}/people`, { limit: PAGE_SIZE, offset: peopleOffset })
            .then((r) => { if (!cancelled) { setPeople(r.items || []); setPeopleTotal(r.total ?? 0); } })
            .catch(() => { if (!cancelled) setPeople([]); });
        return () => { cancelled = true; };
    }, [courseId, activeTab, peopleOffset]);

    // Compose Annoucnement
    const [isComposing, setIsComposing] = useState(false);
    const [announcementText, setAnnouncementText] = useState('');

    // Modal
    const [modalType, setModalType] = useState<ModalType>(null);
    const [editItem, setEditItem] = useState<any>(null);
    const [formData, setFormData] = useState<any>({});
    const [createMenuOpen, setCreateMenuOpen] = useState(false);
    const [openAssignmentId, setOpenAssignmentId] = useState<string | null>(null);
    const [showMyWork, setShowMyWork] = useState(false);
    const [viewingMaterial, setViewingMaterial] = useState<Material | null>(null);
    const [savingMaterial, setSavingMaterial] = useState(false);
    const [deletingMaterialId, setDeletingMaterialId] = useState<string | null>(null);
    const [materialToDelete, setMaterialToDelete] = useState<Material | null>(null);
    const [materialFormError, setMaterialFormError] = useState<string | null>(null);
    const [docChatMessages, setDocChatMessages] = useState<DocChatMessage[]>([]);
    const [docChatFollowups, setDocChatFollowups] = useState<string[]>([]);
    const [docChatInput, setDocChatInput] = useState('');
    const [docChatSending, setDocChatSending] = useState(false);
    const [docPdfObjectUrl, setDocPdfObjectUrl] = useState<string | null>(null);
    const [docPdfError, setDocPdfError] = useState<string | null>(null);
    const [docPdfLoading, setDocPdfLoading] = useState(false);

    /** The backend posts to the stream when classwork is created; reload the stream to show it. */
    const refreshStream = async () => {
        try {
            const r = await api.get<PaginatedResponse<StreamItemResponse>>(`/courses/${courseId}/stream`, { limit: PAGE_SIZE, offset: 0 });
            setStream((r.items || []).map(mapStreamItem));
            setStreamTotal(r.total ?? 0);
            setStreamOffset(0);
        } catch {
            // the item itself was saved; the stream catches up on the next load
        }
    };

    // Invite state (teacher)
    const [showInviteModal, setShowInviteModal] = useState(false);
    const [inviteEmail, setInviteEmail] = useState('');
    const [inviteSending, setInviteSending] = useState(false);
    const [invitedEmails, setInvitedEmails] = useState<string[]>([]);
    const [inviteError, setInviteError] = useState('');
    const [csvResults, setCsvResults] = useState<{ email: string; sent: boolean; error?: string }[]>([]);
    const [csvLoading, setCsvLoading] = useState(false);

    // Join state (student)
    const [showJoinModal, setShowJoinModal] = useState(false);
    const [joinCode, setJoinCode] = useState('');
    const [joinLoading, setJoinLoading] = useState(false);
    const [joinError, setJoinError] = useState('');
    const [joinSuccess, setJoinSuccess] = useState('');

    const [showSuccessModal, setShowSuccessModal] = useState(false);
    const [isPostingAnnouncement, setIsPostingAnnouncement] = useState(false);
    const [announcementAttachments, setAnnouncementAttachments] = useState<File[]>([]);
    const [openInviteCode, setOpenInviteCode] = useState<string | null>(null);
    const [generatingOpenCode, setGeneratingOpenCode] = useState(false);

    const handlePostAnnouncement = async () => {
        if (!announcementText.trim() || isPostingAnnouncement) return;
        setIsPostingAnnouncement(true);
        try {
            // Upload any attached files first
            let uploadedAttachments: { name: string, url: string }[] = [];
            if (announcementAttachments.length > 0) {
                const uploads = await Promise.allSettled(
                    announcementAttachments.map(async (file) => {
                        const { url } = await uploadFile(file);
                        return { name: file.name, url: getUploadFullUrl(url) };
                    })
                );
                uploadedAttachments = uploads
                    .filter((r): r is PromiseFulfilledResult<{ name: string, url: string }> => r.status === 'fulfilled')
                    .map(r => r.value);
            }

            // Build description with attachments embedded
            let description = announcementText.trim();
            if (uploadedAttachments.length > 0) {
                description += '___ATTACHMENTS___' + JSON.stringify(uploadedAttachments);
            }

            const payload = {
                type: 'announcement',
                description,
            };
            const created = await api.post<StreamItemResponse>(`/courses/${courseId}/stream`, payload);
            setStream(prev => [mapStreamItem(created), ...prev]);
            setStreamTotal(t => t + 1);
            setAnnouncementText('');
            setAnnouncementAttachments([]);
            setIsComposing(false);
            setShowSuccessModal(true);
            setTimeout(() => setShowSuccessModal(false), 3000);
        } catch (e: any) {
            console.error('Failed to post announcement:', e.response?.data || e.message || e);
            toast.showToast('Failed to post announcement', 'error');
        } finally {
            setIsPostingAnnouncement(false);
        }
    };

    const openModal = (type: ModalType, item?: any) => {
        setCreateMenuOpen(false);
        setModalType(type);
        setEditItem(item || null);
        setMaterialFormError(null);
        if (item) {
            setFormData(type === 'assignment' ? { ...item, dueLocal: toDateTimeLocal(item.dueDate) } : { ...item });
        } else {
            if (type === 'assignment') setFormData({ title: '', description: '', dueLocal: '', hardDeadline: false, points: 100, attachments: [], topic: topics[0] || '' });
            if (type === 'material') setFormData({ title: '', description: '', type: 'pdf', url: '', topic: topics[0] || '' });
            if (type === 'video') setFormData({ title: '', description: '', duration: '', url: '', topic: topics[0] || '' });
            if (type === 'topic') setFormData({ title: '' });
        }
    };

    const handleSave = async () => {
        if (modalType === 'topic') {
            if (formData.title && !topics.includes(formData.title)) {
                setTopics([...topics, formData.title]);
            }
            setModalType(null);
            return;
        }
        if (modalType === 'material' && courseId) {
            setMaterialFormError(null);
            if (!formData.title?.trim()) {
                setMaterialFormError('Title is required.');
                return;
            }
            if (!formData.url?.trim()) {
                setMaterialFormError('Please upload a file or enter a URL.');
                return;
            }
            setSavingMaterial(true);
            try {
                const payload = {
                    title: formData.title.trim(),
                    description: formData.description?.trim() || undefined,
                    type: formData.type || 'pdf',
                    url: formData.url.trim(),
                    topic: formData.topic || undefined,
                };
                if (editItem) {
                    const updated = await api.patch<MaterialResponse>(`/courses/${courseId}/materials/${editItem.id}`, payload);
                    setMaterials((prev) => prev.map((m) => (m.id === editItem.id ? mapMaterial(updated) : m)));
                } else {
                    const created = await api.post<MaterialResponse>(`/courses/${courseId}/materials`, payload);
                    setMaterials((prev) => [mapMaterial(created), ...prev]);
                    void refreshStream();
                }
                setModalType(null);
                setMaterialFormError(null);
            } catch (e) {
                setMaterialFormError(e instanceof Error ? e.message : 'Failed to save material.');
            } finally {
                setSavingMaterial(false);
            }
            return;
        }
        if (modalType === 'assignment' && courseId) {
            if (!formData.title?.trim() || !formData.dueLocal) {
                toast.showToast('Title and due date are required', 'error');
                return;
            }
            try {
                const topic = formData.topic && formData.topic !== 'No topic' ? formData.topic : undefined;
                const payload = {
                    title: formData.title.trim(),
                    description: formData.description?.trim() || undefined,
                    // Store the exact moment (with time zone) so the server can enforce a hard deadline.
                    dueDate: new Date(formData.dueLocal).toISOString(),
                    hardDeadline: !!formData.hardDeadline,
                    points: formData.points || 100,
                    topic,
                };
                const saved = editItem
                    ? await api.patch<AssignmentResponse>(`/courses/${courseId}/assignments/${editItem.id}`, payload)
                    : await api.post<AssignmentResponse>(`/courses/${courseId}/assignments`, payload);
                if (editItem) {
                    setAssignments((prev) => prev.map((a) => (a.id === editItem.id ? mapAssignment(saved) : a)));
                } else {
                    setAssignments((prev) => [mapAssignment(saved), ...prev]);
                    void refreshStream();
                }
            } catch (e) {
                toast.showToast(e instanceof Error ? e.message : 'Failed to save assignment', 'error');
                return;
            }
        }
        else if (modalType === 'video' && courseId) {
            if (!formData.title?.trim() || !formData.url?.trim()) {
                toast.showToast('Title and video URL are required', 'error');
                return;
            }
            try {
                const saved = await api.post<VideoResponse>('/videos', {
                    title: formData.title.trim(),
                    url: formData.url.trim(),
                    description: formData.description?.trim() || undefined,
                    durationSeconds: parseDuration(formData.duration),
                    courseId: Number(courseId),
                });
                setVideos((prev) => [mapVideo(saved), ...prev]);
                void refreshStream();
            } catch (e) {
                toast.showToast(e instanceof Error ? e.message : 'Failed to save video', 'error');
                return;
            }
        }
        setModalType(null);
    };

    const handleDeleteWork = async (item: { id: string; itemType: 'assignment' | 'video'; title: string }) => {
        if (!window.confirm(`Delete "${item.title}"?`)) return;
        try {
            if (item.itemType === 'assignment') {
                await api.delete(`/courses/${courseId}/assignments/${item.id}`);
                setAssignments((prev) => prev.filter((a) => a.id !== item.id));
            } else {
                await api.delete(`/videos/${item.id}`);
                setVideos((prev) => prev.filter((v) => v.id !== item.id));
            }
        } catch (e) {
            toast.showToast(e instanceof Error ? e.message : 'Delete failed', 'error');
        }
    };

    useEffect(() => {
        if (viewingMaterial) {
            setDocChatMessages([]);
            setDocChatInput('');
        }
    }, [viewingMaterial?.id]);

    // The API returns uploaded files as "/courses/{id}/materials/{mid}/file" (members-only route);
    // anything else is an external link. The type dropdown defaults to "pdf" even for images,
    // so the viewer decides by the downloaded file's real content type (docMime).
    const isUploadedMaterial = (m: Material) => /\/materials\/\d+\/file$/.test(m.url) || /\/uploads\//.test(m.url);
    const [docMime, setDocMime] = useState('');

    useEffect(() => {
        if (!viewingMaterial || !courseId || !isUploadedMaterial(viewingMaterial)) {
            setDocPdfObjectUrl((prev) => {
                if (prev) URL.revokeObjectURL(prev);
                return null;
            });
            setDocPdfError(null);
            setDocPdfLoading(false);
            return;
        }
        const url = getMaterialFileUrl(courseId, viewingMaterial.id);
        setDocPdfError(null);
        setDocPdfLoading(true);
        setDocPdfObjectUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev);
            return null;
        });
        const base = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
        authFetch(url, {
            credentials: 'include',
            headers: base.includes('ngrok') ? { 'ngrok-skip-browser-warning': '1' } : {},
        })
            .then((res) => {
                if (!res.ok) throw new Error(res.status === 401 || res.status === 403 ? 'Please sign in again to view this file.' : `Could not load file (${res.status}).`);
                return res.blob();
            })
            .then((blob) => {
                setDocMime(blob.type);
                setDocPdfObjectUrl(URL.createObjectURL(blob));
                setDocPdfError(null);
            })
            .catch((e) => {
                setDocPdfError(e instanceof Error ? e.message : 'Failed to load file.');
            })
            .finally(() => setDocPdfLoading(false));
        return () => {
            setDocPdfObjectUrl((prev) => {
                if (prev) URL.revokeObjectURL(prev);
                return null;
            });
        };
    }, [viewingMaterial?.id, courseId, viewingMaterial?.type, viewingMaterial?.url]);

    const sendDocChatMessage = async () => {
        if (!viewingMaterial || !docChatInput.trim() || docChatSending) return;
        const userContent = docChatInput.trim();
        setDocChatInput('');
        setDocChatFollowups([]);
        setDocChatMessages((prev) => [...prev, { role: 'user', content: userContent }]);
        setDocChatSending(true);
        try {
            const data = await api.post<{ response: string }>('/chat/message', {
                message: userContent,
                conversationHistory: docChatMessages,
                contextMaterialTitle: viewingMaterial.title,
                courseId: courseId ? parseInt(courseId) : undefined,
            });
            const raw = data.response || '';
            const followupMatch = raw.match(/FOLLOWUPS?:\s*(.+)$/im);
            const followups = followupMatch ? followupMatch[1].split('|').map((s: string) => s.trim()).filter(Boolean) : [];
            const clean = raw.replace(/CHECKPOINT\s*/gi, '').replace(/FOLLOWUPS?:.*$/im, '').trim();
            setDocChatFollowups(followups);
            setDocChatMessages((prev: DocChatMessage[]) => [...prev, { role: 'assistant', content: clean }]);
        } catch (e) {
            setDocChatMessages((prev: DocChatMessage[]) => [...prev, { role: 'assistant', content: (e instanceof Error ? e.message : 'Something went wrong. Please try again.') }]);
        } finally {
            setDocChatSending(false);
        }
    };

    const handleDeleteMaterialClick = (material: Material) => {
        setMaterialToDelete(material);
    };

    const handleDeleteMaterialConfirm = async () => {
        if (!courseId || !materialToDelete) return;
        setDeletingMaterialId(materialToDelete.id);
        try {
            await api.delete(`/courses/${courseId}/materials/${materialToDelete.id}`);
            setMaterials((prev) => prev.filter((m) => m.id !== materialToDelete.id));
            setMaterialToDelete(null);
        } catch (e) {
            setMaterialFormError(e instanceof Error ? e.message : 'Failed to delete material.');
        } finally {
            setDeletingMaterialId(null);
        }
    };


    const handleSendInvite = async () => {
        if (!inviteEmail.trim() || !courseId) return;
        setInviteSending(true);
        setInviteError('');
        try {
            await api.post(`/courses/${courseId}/invite`, { email: inviteEmail.trim() });
            setInvitedEmails((prev) => [...prev, inviteEmail.trim()]);
            setInviteEmail('');
        } catch (e) {
            setInviteError(e instanceof Error ? e.message : 'Failed to send invite.');
        } finally {
            setInviteSending(false);
        }
    };

    const handleCsvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file || !courseId) return;
        e.target.value = '';
        const text = await file.text();
        const emails = Array.from(
            new Set(
                text.split(/[\r\n,;\t]+/)
                    .map((s) => s.replace(/^["'\s]+|["'\s]+$/g, '').toLowerCase())
                    .filter((s) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s))
            )
        );
        if (emails.length === 0) {
            setInviteError('No valid email addresses found in the CSV.');
            return;
        }
        setInviteError('');
        setCsvLoading(true);
        setCsvResults([]);
        const results: { email: string; sent: boolean; error?: string }[] = [];
        for (const email of emails) {
            try {
                await api.post(`/courses/${courseId}/invite`, { email });
                results.push({ email, sent: true });
            } catch (err) {
                results.push({ email, sent: false, error: err instanceof Error ? err.message : 'Failed' });
            }
            setCsvResults([...results]);
        }
        setCsvLoading(false);
    };

    const handleJoinCourse = async () => {
        if (!joinCode.trim()) return;
        setJoinLoading(true);
        setJoinError('');
        setJoinSuccess('');
        try {
            const res = await api.post<{ courseTitle: string; message: string }>('/courses/join', { inviteCode: joinCode.trim() });
            setJoinSuccess(res.message || `You joined ${res.courseTitle}!`);
            setJoinCode('');
            // Reload people list
            const r = await api.get<{ items: CoursePersonResponse[]; total: number }>(`/courses/${courseId}/people`, { limit: PAGE_SIZE, offset: 0 });
            setPeople(r.items || []);
            setPeopleTotal(r.total ?? 0);
        } catch (e) {
            setJoinError(e instanceof Error ? e.message : 'Invalid or expired invite code.');
        } finally {
            setJoinLoading(false);
        }
    };

    // ── Stream posts ──
    const [openPostId, setOpenPostId] = useState<string | null>(null);

    /** Open what a post is about: the announcement itself, or the assignment / material / video it announces. */
    const openStreamPost = (item: StreamItem) => {
        if (item.type === 'assignment') {
            const a = assignments.find((x) => x.title === item.description);
            if (a) { setOpenAssignmentId(a.id); return; }
        }
        if (item.type === 'material') {
            const id = item.attachments?.find((att) => att.materialId)?.materialId;
            const m = materials.find((x) => (id ? x.id === id : x.title === item.description));
            if (m) { setViewingMaterial(m); return; }
        }
        if (item.type === 'video') {
            const v = videos.find((x) => x.title === item.description);
            if (v) { navigate(`/videos/${v.id}`); return; }
        }
        // Announcements, and classwork that has since been deleted, open in the post view.
        setOpenPostId(item.id);
    };

    const renderFeedHeader = (item: StreamItem) => (
        <div className="cd-feed-header">
            <div className="cd-feed-icon">
                {item.type === 'announcement' ? (
                    <div className="cd-avatar">{item.author.charAt(0)}</div>
                ) : (
                    <div className="cd-icon-badge" style={{ backgroundColor: item.type === 'assignment' ? 'var(--primary)' : 'var(--gray-500)' }}>
                        {item.type === 'assignment' && <FileText size={16} color="white" />}
                        {item.type === 'material' && <BookOpen size={16} color="white" />}
                        {item.type === 'video' && <Video size={16} color="white" />}
                    </div>
                )}
            </div>
            <div className="cd-feed-meta">
                <p className="cd-feed-author">{item.type === 'announcement' ? item.author : item.title}</p>
                <p className="cd-feed-date">{item.createdAt}</p>
            </div>
        </div>
    );

    const renderAttachments = (item: StreamItem) => {
        // Material posts made before the id was stored: find the material by title.
        const legacy: NonNullable<StreamItem['attachments']> = item.type === 'material' && !item.attachments?.length
            ? materials.filter((m) => m.title === item.description).slice(0, 1).map((m) => ({ name: m.title, materialId: m.id }))
            : [];
        const atts = item.attachments?.length ? item.attachments : legacy;
        if (atts.length === 0) return null;
        return (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.75rem' }}>
                {atts.map((att, i) => {
                    const material = att.materialId ? materials.find((m) => m.id === att.materialId) : undefined;
                    if (material) {
                        return (
                            <button key={i} type="button" className="cd-feed-attachment" onClick={(e) => { e.stopPropagation(); setViewingMaterial(material); }}>
                                {isUploadedMaterial(material) && (
                                    <AuthImage src={getMaterialFileUrl(courseId, material.id)} alt={material.title} className="cd-feed-attachment-img" />
                                )}
                                <span className="cd-feed-attachment-name"><Paperclip size={13} /> {material.title}</span>
                            </button>
                        );
                    }
                    if (!att.url) return null; // material since deleted
                    // Older posts store "/uploads/x" without the API host.
                    const href = att.url.startsWith('/') ? getUploadFullUrl(att.url) : att.url;
                    const isImage = /\.(png|jpe?g|gif|webp)$/i.test(att.url);
                    return (
                        <a key={i} href={href} target="_blank" rel="noopener noreferrer" className="cd-feed-attachment" onClick={(e) => e.stopPropagation()}>
                            {isImage && <img src={href} alt={att.name} className="cd-feed-attachment-img" loading="lazy" />}
                            <span className="cd-feed-attachment-name"><Paperclip size={13} /> {att.name}</span>
                        </a>
                    );
                })}
            </div>
        );
    };

    // Calculate Items by Topic
    const itemsByTopic: Record<string, any[]> = {};
    topics.forEach(t => itemsByTopic[t] = []);
    itemsByTopic['No topic'] = [];

    assignments.forEach(a => {
        const topic = a.topic && topics.includes(a.topic) ? a.topic : 'No topic';
        itemsByTopic[topic].push({ ...a, itemType: 'assignment' });
    });
    materials.forEach(m => {
        const topic = m.topic && topics.includes(m.topic) ? m.topic : 'No topic';
        itemsByTopic[topic].push({ ...m, itemType: 'material' });
    });
    videos.forEach(v => {
        const topic = v.topic && topics.includes(v.topic) ? v.topic : 'No topic';
        itemsByTopic[topic].push({ ...v, itemType: 'video' });
    });

    if (courseLoading && !course) {
        return <div className="cd-page"><div className="cd-loading">Loading course…</div></div>;
    }
    if (courseError || (!courseLoading && courseId && !course)) {
        return (
            <div className="cd-page">
                <div className="cd-error">
                    {courseError || 'Course not found'}
                    <button className="btn btn-outline btn-sm" onClick={() => navigate('/courses')}>Back to Courses</button>
                </div>
            </div>
        );
    }

    return (
        <div className="cd-page">
            {/* Tabs matching Classroom look */}
            <div className="cd-tabs-wrapper">
                <button className="cd-back-btn" onClick={() => navigate('/courses')}>
                    <ArrowLeft size={20} />
                </button>
                <div className="cd-cr-tabs">
                    {tabs.map((tab) => (
                        <button key={tab.id} className={`cd-cr-tab ${activeTab === tab.id ? 'active' : ''}`} onClick={() => setActiveTab(tab.id)}>
                            {tab.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* ── Stream Tab ── */}
            {activeTab === 'stream' && (
                <div className="cd-stream-container">
                    <div className="cd-stream-sidebar">
                        <div className="cd-upcoming-box">
                            <h4>Upcoming</h4>
                            <p>Woohoo, no work due in soon!</p>
                            <a href="#" className="cd-upcoming-link">View all</a>
                        </div>
                    </div>

                    <div className="cd-stream-main">
                        {/* Banner inside stream */}
                        <div className="cd-cr-banner" style={{ backgroundColor: courseDisplay.color }}>
                            <div className="cd-cr-banner-content">
                                <h1>{courseDisplay.title}</h1>
                                <p>{courseDisplay.code}</p>
                            </div>
                        </div>

                        {/* Compose Post */}
                        <div className="cd-compose-card" style={isInstructor ? undefined : { display: 'none' }}>
                            {!isComposing ? (
                                <div className="cd-compose-trigger" onClick={() => setIsComposing(true)}>
                                    <div className="cd-avatar">{userName.charAt(0)}</div>
                                    <span style={{ color: 'var(--primary)' }}>Announce something to your class</span>
                                </div>
                            ) : (
                                <div className="cd-compose-editor animate-fade-in">
                                    <div className="cd-editor-top">
                                        <textarea
                                            placeholder="Announce something to your class"
                                            value={announcementText}
                                            onChange={(e) => setAnnouncementText(e.target.value)}
                                            autoFocus
                                        />
                                    </div>
                                    {/* Attachment preview */}
                                    {announcementAttachments.length > 0 && (
                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', padding: '0.5rem 1rem', borderTop: '1px solid var(--border)' }}>
                                            {announcementAttachments.map((f, i) => (
                                                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', background: 'var(--surface-hover)', borderRadius: '0.4rem', padding: '0.25rem 0.6rem', fontSize: '0.8rem' }}>
                                                    <Paperclip size={12} />
                                                    <span style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                                                    <button type="button" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0, lineHeight: 1 }} onClick={() => setAnnouncementAttachments(prev => prev.filter((_, j) => j !== i))}><X size={12} /></button>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    <div className="cd-editor-tools">
                                        <div className="cd-editor-icons">
                                            <button className="btn-icon" title="Bold text" onClick={() => setAnnouncementText(t => t + ' **bold text**')}>B</button>
                                            <button className="btn-icon" title="Insert link" onClick={() => {
                                                const url = window.prompt('Enter URL:');
                                                if (url) setAnnouncementText(t => t + ` [link](${url})`);
                                            }}><LinkIcon size={15} /></button>
                                            <button className="btn-icon" title="Attach files" onClick={() => {
                                                const inp = document.createElement('input');
                                                inp.type = 'file';
                                                inp.multiple = true;
                                                inp.accept = '.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.png,.jpg,.jpeg,.zip';
                                                inp.onchange = () => {
                                                    const files = Array.from(inp.files || []);
                                                    if (files.length) setAnnouncementAttachments(prev => [...prev, ...files]);
                                                };
                                                inp.click();
                                            }}><Paperclip size={15} /></button>
                                        </div>
                                        <div className="cd-editor-actions">
                                            <button className="btn btn-ghost" onClick={() => { setIsComposing(false); setAnnouncementAttachments([]); setAnnouncementText(''); }}>Cancel</button>
                                            <button className="btn btn-primary" onClick={handlePostAnnouncement} disabled={!announcementText.trim() || isPostingAnnouncement}>
                                                {isPostingAnnouncement ? <><span className="loading loading-spinner loading-sm"></span> Uploading…</> : 'Post'}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Stream Feed */}
                        <div className="cd-feed">
                            {stream.map((item) => (
                                <div key={item.id} className="cd-feed-item">
                                    {/* Clicking a post opens it: an announcement in its own view, classwork in its viewer. */}
                                    <div
                                        className="cd-feed-open"
                                        role="button"
                                        tabIndex={0}
                                        aria-label={`Open post: ${item.type === 'announcement' ? item.description.slice(0, 60) : item.description}`}
                                        onClick={() => openStreamPost(item)}
                                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openStreamPost(item); } }}
                                    >
                                        {renderFeedHeader(item)}
                                        <div className="cd-feed-body">
                                            {item.type === 'announcement' && item.title && <h4>{item.title}</h4>}
                                            <p className="cd-feed-text-clamp">{item.description}</p>
                                            {renderAttachments(item)}
                                        </div>
                                    </div>
                                    <div className="cd-feed-footer">
                                        {courseId && <StreamComments courseId={courseId} itemId={item.id} canModerate={isInstructor} />}
                                    </div>
                                </div>
                            ))}
                        </div>
                        {streamTotal > PAGE_SIZE && (
                            <Pagination total={streamTotal} limit={PAGE_SIZE} offset={streamOffset} onPageChange={setStreamOffset} />
                        )}
                    </div>
                </div>
            )}

            {/* ── Classwork Tab ── */}
            {activeTab === 'classwork' && (
                <div className="cd-classwork-container">
                    <div className="cd-cw-actions">
                        {isInstructor && (
                            <div className="cd-create-dropdown">
                                <button className="btn btn-primary" onClick={() => setCreateMenuOpen(!createMenuOpen)}>
                                    <Plus size={18} /> Create
                                </button>
                                {createMenuOpen && (
                                    <div className="cd-dropdown-menu">
                                        <button onClick={() => openModal('assignment')}><FileText size={16} /> Assignment</button>
                                        <button onClick={() => openModal('material')}><BookOpen size={16} /> Material</button>
                                        <button onClick={() => openModal('video')}><Video size={16} /> Video Lecture</button>
                                        <div className="cd-divider"></div>
                                        <button onClick={() => openModal('topic')}><Heading size={16} /> Topic</button>
                                    </div>
                                )}
                            </div>
                        )}
                        {!isInstructor && (
                            <button className="btn btn-outline" onClick={() => setShowMyWork(true)}><FileText size={16} /> View your work</button>
                        )}
                    </div>

                    <div className="cd-topics-view">
                        {topics.concat('No topic').map(topic => {
                            const items = itemsByTopic[topic];
                            if (!isInstructor && items.length === 0 && topic !== 'No topic') return null; // hide empty topics for students
                            if (topic === 'No topic' && items.length === 0) return null;

                            return (
                                <div key={topic} className="cd-topic-group">
                                    <h2 className="cd-topic-title">{topic}</h2>
                                    <div className="cd-topic-items">
                                        {items.map(item => (
                                            <div key={item.id} className="cd-cw-item">
                                                <div className="cd-cw-item-left">
                                                    <div className="cd-cw-icon" style={{ backgroundColor: item.itemType === 'assignment' ? 'var(--primary)' : 'var(--gray-500)' }}>
                                                        {item.itemType === 'assignment' && <FileText size={18} color="white" />}
                                                        {item.itemType === 'material' && <BookOpen size={18} color="white" />}
                                                        {item.itemType === 'video' && <Video size={18} color="white" />}
                                                    </div>
                                                    {item.itemType === 'material' || item.itemType === 'assignment' ? (
                                                        <button
                                                            type="button"
                                                            className="cd-cw-title cd-cw-title-link"
                                                            onClick={() => (item.itemType === 'assignment' ? setOpenAssignmentId(item.id) : setViewingMaterial(item))}
                                                        >
                                                            {item.title}
                                                        </button>
                                                    ) : (
                                                        <span className="cd-cw-title">{item.title}</span>
                                                    )}
                                                </div>
                                                <div className="cd-cw-item-right">
                                                    {item.itemType === 'assignment' && (
                                                        <>
                                                            <span className="cd-cw-due">Due {formatDue(item.dueDate)}</span>
                                                            {!isInstructor && (() => {
                                                                const st = statusLabel(item.status, item.submittedAt, item.dueDate, item.grade, item.points);
                                                                return <span className={`cd-status cd-status-${st.tone}`}>{st.text}</span>;
                                                            })()}
                                                            {!isInstructor && item.status === 'pending' && !isClosed(item.dueDate, item.hardDeadline) && (
                                                                <button className="btn btn-outline btn-sm" onClick={() => setOpenAssignmentId(item.id)}>
                                                                    Submit
                                                                </button>
                                                            )}
                                                            {isInstructor && (
                                                                <button className="btn btn-outline btn-sm" onClick={() => setOpenAssignmentId(item.id)}>
                                                                    Grade
                                                                </button>
                                                            )}
                                                        </>
                                                    )}
                                                    {item.itemType === 'material' && (
                                                        <>
                                                            <span className="cd-cw-due">Posted {item.createdAt}</span>
                                                            {isInstructor && (
                                                                <>
                                                                    <button
                                                                        type="button"
                                                                        className="btn-icon"
                                                                        onClick={() => openModal('material', item)}
                                                                        title="Edit"
                                                                    >
                                                                        <Pencil size={16} />
                                                                    </button>
                                                                    <button
                                                                        type="button"
                                                                        className="btn-icon"
                                                                        onClick={() => handleDeleteMaterialClick(item)}
                                                                        disabled={deletingMaterialId === item.id}
                                                                        title="Delete"
                                                                    >
                                                                        <Trash2 size={16} />
                                                                    </button>
                                                                </>
                                                            )}
                                                        </>
                                                    )}
                                                    {item.itemType !== 'material' && isInstructor && <button type="button" className="btn-icon" title="Delete" onClick={() => handleDeleteWork(item)}><Trash2 size={16} /></button>}
                                                </div>
                                            </div>
                                        ))}
                                        {isInstructor && items.length === 0 && (
                                            <div className="cd-cw-empty">Students will see this topic once work is added to it</div>
                                        )}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            )}

            {/* ── People Tab ── */}
            {activeTab === 'people' && (
                <div className="cd-people-container">
                    <div className="cd-people-section">
                        <div className="cd-people-header">
                            <h2>Classmates ({peopleTotal})</h2>
                            {/* Students only reach this page once enrolled, so they need no join button here. */}
                            {isInstructor && (
                                <button className="btn btn-primary btn-sm" onClick={() => { setShowInviteModal(true); setInviteError(''); }}>
                                    <Mail size={15} /> Invite Students
                                </button>
                            )}
                        </div>
                        {people.length === 0 && peopleTotal === 0 && (
                            <EmptyState icon={<Users size={28} />} title="No one enrolled yet" description="Enrolled classmates will appear here." />
                        )}
                        {people.map((p) => (
                            <div key={p.userId} className="cd-person">
                                <div className="cd-avatar">{p.fullName.charAt(0).toUpperCase()}</div>
                                <div>
                                    <span>{p.fullName}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                    {peopleTotal > PAGE_SIZE && (
                        <Pagination total={peopleTotal} limit={PAGE_SIZE} offset={peopleOffset} onPageChange={setPeopleOffset} />
                    )}
                </div>
            )}

            {/* ── Modals ── */}
            {modalType && (
                <div className="cd-modal-overlay" onClick={() => setModalType(null)}>
                    <div className="cd-modal animate-scale-in" onClick={(e) => e.stopPropagation()}>
                        <div className="cd-modal-header">
                            <h2>{editItem ? 'Edit' : 'Add'} {modalType.charAt(0).toUpperCase() + modalType.slice(1)}</h2>
                            <button className="cd-modal-close" onClick={() => setModalType(null)}><X size={20} /></button>
                        </div>
                        <div className="cd-modal-body">
                            <div className="cd-modal-field">
                                <label>{modalType === 'topic' ? 'Topic Name' : 'Title *'}</label>
                                <input className="input" placeholder="Enter title..." value={formData.title || ''} onChange={(e) => setFormData({ ...formData, title: e.target.value })} />
                            </div>

                            {modalType !== 'topic' && (
                                <>
                                    <div className="cd-modal-field">
                                        <label>Description</label>
                                        <textarea className="input" rows={3} placeholder="Enter description..." value={formData.description || ''} onChange={(e) => setFormData({ ...formData, description: e.target.value })} />
                                    </div>
                                    <div className="cd-modal-field">
                                        <label>Topic</label>
                                        <select className="input" value={formData.topic || 'No topic'} onChange={(e) => setFormData({ ...formData, topic: e.target.value })}>
                                            <option value="No topic">No topic</option>
                                            {topics.map(t => <option key={t} value={t}>{t}</option>)}
                                        </select>
                                    </div>
                                </>
                            )}

                            {modalType === 'assignment' && (
                                <div className="cd-modal-row">
                                    <div className="cd-modal-field">
                                        <label>Due *</label>
                                        <input className="input" type="datetime-local" value={formData.dueLocal || ''} onChange={(e) => setFormData({ ...formData, dueLocal: e.target.value })} />
                                    </div>
                                    <div className="cd-modal-field">
                                        <label>Points</label>
                                        <input className="input" type="number" value={formData.points || 100} onChange={(e) => setFormData({ ...formData, points: parseInt(e.target.value) || 0 })} />
                                    </div>
                                </div>
                            )}
                            {modalType === 'assignment' && (
                                <label className="cd-checkbox-field">
                                    <input type="checkbox" checked={!!formData.hardDeadline} onChange={(e) => setFormData({ ...formData, hardDeadline: e.target.checked })} />
                                    <span>
                                        Don't accept work after the due time
                                        <small>Off: late work is accepted and marked late.</small>
                                    </span>
                                </label>
                            )}

                            {modalType === 'material' && (
                                <div className="cd-modal-row">
                                    <div className="cd-modal-field">
                                        <label>Type</label>
                                        <select className="input" value={formData.type || 'pdf'} onChange={(e) => setFormData({ ...formData, type: e.target.value })}>
                                            <option value="pdf">PDF</option>
                                            <option value="doc">Document</option>
                                            <option value="slide">Slides</option>
                                        </select>
                                    </div>
                                    <div className="cd-modal-field cd-modal-field-full">
                                        <label>File</label>
                                        <FileDropzone
                                            mode="upload"
                                            onUploaded={(url) => setFormData((prev: Record<string, unknown>) => ({ ...prev, url: getUploadFullUrl(url) }))}
                                            onClear={() => setFormData((prev: Record<string, unknown>) => ({ ...prev, url: '' }))}
                                            currentUrl={formData.url || null}
                                            maxSizeMB={20}
                                        />
                                        <label className="cd-modal-field-label-optional">Or paste URL</label>
                                        <input className="input" placeholder="https://..." value={formData.url || ''} onChange={(e) => setFormData({ ...formData, url: e.target.value })} />
                                    </div>
                                </div>
                            )}

                            {modalType === 'video' && (
                                <div className="cd-modal-row">
                                    <div className="cd-modal-field">
                                        <label>Video URL</label>
                                        <input className="input" placeholder="https://youtube.com/..." value={formData.url || ''} onChange={(e) => setFormData({ ...formData, url: e.target.value })} />
                                    </div>
                                    <div className="cd-modal-field">
                                        <label>Duration</label>
                                        <input className="input" placeholder="e.g. 45:20" value={formData.duration || ''} onChange={(e) => setFormData({ ...formData, duration: e.target.value })} />
                                    </div>
                                </div>
                            )}
                            {modalType === 'material' && materialFormError && (
                                <div className="cd-modal-inline-error">
                                    <span>{materialFormError}</span>
                                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setMaterialFormError(null)}>Close</button>
                                </div>
                            )}
                        </div>
                        <div className="cd-modal-footer">
                            <button className="btn btn-outline" onClick={() => setModalType(null)}>Cancel</button>
                            <button
                                className="btn btn-primary"
                                onClick={handleSave}
                                disabled={modalType === 'material' && savingMaterial}
                            >
                                <Save size={16} /> {modalType === 'material' && savingMaterial ? 'Saving…' : (editItem ? 'Update' : 'Create')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Full-screen document view with PDF + AI sidebar (like reference) */}
            {viewingMaterial && (
                <div className="cd-doc-view-overlay">
                    <div className="cd-doc-view" onClick={(e) => e.stopPropagation()}>
                        <header className="cd-doc-view-header">
                            <div className="cd-doc-view-header-title">
                                <BookOpen size={20} className="cd-doc-view-icon" />
                                <h1 className="cd-doc-view-title">{viewingMaterial.title}</h1>
                            </div>
                            <div className="cd-doc-view-header-actions">
                                {/* The file route needs the login token, which a plain link cannot send,
                                    so open the copy already loaded in the page instead. */}
                                {(docPdfObjectUrl || !isUploadedMaterial(viewingMaterial)) && (
                                    <a
                                        href={docPdfObjectUrl ?? viewingMaterial.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="btn btn-outline btn-sm"
                                    >
                                        <ExternalLink size={16} /> Open in new tab
                                    </a>
                                )}
                                <button type="button" className="btn btn-ghost" onClick={() => setViewingMaterial(null)}>
                                    <X size={20} /> Close
                                </button>
                            </div>
                        </header>
                        <div className="cd-doc-view-main">
                            <div className="cd-doc-view-pdf-wrap">
                                {!isUploadedMaterial(viewingMaterial) ? (
                                    <div className="cd-doc-view-fallback">
                                        <p>This material is a link.</p>
                                        <a href={viewingMaterial.url} target="_blank" rel="noopener noreferrer" className="btn btn-outline btn-sm">Open link</a>
                                    </div>
                                ) : docPdfLoading ? (
                                    <div className="cd-doc-view-loading">
                                        <p>Loading file…</p>
                                    </div>
                                ) : docPdfError ? (
                                    <div className="cd-doc-view-fallback">
                                        <p className="cd-doc-view-error">{docPdfError}</p>
                                    </div>
                                ) : docPdfObjectUrl && docMime.startsWith('image/') ? (
                                    <img src={docPdfObjectUrl} alt={viewingMaterial.title} className="cd-doc-view-image" />
                                ) : docPdfObjectUrl && docMime === 'application/pdf' ? (
                                    <iframe
                                        title={viewingMaterial.title}
                                        src={docPdfObjectUrl}
                                        className="cd-doc-view-iframe"
                                    />
                                ) : docPdfObjectUrl ? (
                                    <div className="cd-doc-view-fallback">
                                        <p>Preview is not available for this file type.</p>
                                        <a href={docPdfObjectUrl} download={viewingMaterial.title} className="btn btn-outline btn-sm">Download</a>
                                    </div>
                                ) : null}
                            </div>
                            <aside className="cd-doc-view-sidebar">
                                <div className="cd-doc-view-sidebar-header">
                                    <Sparkles size={18} className="cd-doc-view-sidebar-icon" />
                                    <h2 className="cd-doc-view-sidebar-title">Summary</h2>
                                </div>
                                <p className="cd-doc-view-sidebar-summary">
                                    Ask questions below to get explanations, summaries, or key points about this document. Our AI will answer in the context of &quot;{viewingMaterial.title}&quot;.
                                </p>
                                <div className="cd-doc-view-sidebar-chat">
                                    <div className="cd-doc-view-messages">
                                        {docChatMessages.length === 0 && (
                                            <p className="cd-doc-view-messages-empty">No messages yet. Ask anything about this document.</p>
                                        )}
                                        {docChatMessages.map((msg, i) => (
                                            <div key={i} className={`cd-doc-view-msg cd-doc-view-msg-${msg.role}`}>
                                                <span className="cd-doc-view-msg-role">{msg.role === 'user' ? 'You' : 'Saarthi'}</span>
                                                <div
                                                    className="cd-doc-view-msg-content"
                                                    dangerouslySetInnerHTML={{
                                                        __html: msg.content
                                                            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                                                            .replace(/\*(.+?)\*/g, '<em>$1</em>')
                                                            .replace(/`(.+?)`/g, '<code>$1</code>')
                                                            .replace(/^#{1,3} (.+)$/gm, '<strong>$1</strong>')
                                                            .replace(/\n/g, '<br/>')
                                                    }}
                                                />
                                            </div>
                                        ))}
                                        {docChatFollowups.length > 0 && !docChatSending && (
                                            <div className="cd-doc-followups">
                                                {docChatFollowups.map((q, i) => (
                                                    <button key={i} className="cd-doc-followup-chip" onClick={() => { setDocChatInput(q); setDocChatFollowups([]); }}>
                                                        {q}
                                                    </button>
                                                ))}
                                            </div>
                                        )}
                                        {docChatSending && (
                                            <div className="cd-doc-view-msg cd-doc-view-msg-assistant">
                                                <span className="cd-doc-view-msg-role">Saarthi</span>
                                                <div className="cd-doc-view-msg-content cd-doc-view-msg-loading">Thinking…</div>
                                            </div>
                                        )}
                                    </div>
                                    <div className="cd-doc-view-input-wrap">
                                        <input
                                            type="text"
                                            className="input cd-doc-view-input"
                                            placeholder="Ask about this document…"
                                            value={docChatInput}
                                            onChange={(e) => setDocChatInput(e.target.value)}
                                            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendDocChatMessage()}
                                            disabled={docChatSending}
                                        />
                                        <button
                                            type="button"
                                            className="btn btn-primary cd-doc-view-send"
                                            onClick={sendDocChatMessage}
                                            disabled={!docChatInput.trim() || docChatSending}
                                            title="Send"
                                        >
                                            <Send size={18} />
                                        </button>
                                    </div>
                                </div>
                            </aside>
                        </div>
                    </div>
                </div>
            )}

            {/* Delete material confirmation (theme-matched modal) */}
            <ConfirmModal
                open={!!materialToDelete}
                title="Delete material"
                message={materialToDelete ? `Delete "${materialToDelete.title}"? This cannot be undone.` : ''}
                confirmLabel="Delete"
                variant="danger"
                onConfirm={handleDeleteMaterialConfirm}
                onCancel={() => setMaterialToDelete(null)}
                loading={!!deletingMaterialId}
            />

            {/* ── Invite Students Modal (teacher) ── */}
            {showInviteModal && (
                <div className="cd-modal-overlay" onClick={() => { setShowInviteModal(false); setCsvResults([]); setInvitedEmails([]); setOpenInviteCode(null); }}>
                    <div className="cd-modal cd-modal-wide animate-scale-in" onClick={(e) => e.stopPropagation()}>
                        <div className="cd-modal-header">
                            <h2><Mail size={18} /> Invite Students</h2>
                            <button className="cd-modal-close" onClick={() => { setShowInviteModal(false); setCsvResults([]); setInvitedEmails([]); }}><X size={20} /></button>
                        </div>
                        <div className="cd-modal-body">

                            {/* Open Invite Code section */}
                            <div className="cd-invite-section" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '0.75rem', padding: '1rem', marginBottom: '0.25rem' }}>
                                <p className="cd-invite-section-label">🔗 Open Invite Code</p>
                                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                                    Generate a universal code. Anyone with it can join — share it on a board or group chat.
                                </p>
                                {openInviteCode ? (
                                    <div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--surface-1)', border: '2px dashed var(--primary)', borderRadius: '0.5rem', padding: '0.75rem 1rem', marginBottom: '0.5rem' }}>
                                            <code style={{ flex: 1, fontSize: '1.1rem', fontFamily: 'monospace', letterSpacing: '0.1em', color: 'var(--primary)', fontWeight: 700 }}>{openInviteCode}</code>
                                            <button className="btn btn-sm btn-outline" onClick={() => { navigator.clipboard.writeText(openInviteCode); toast.showToast('Invite code copied!'); }}>Copy</button>
                                        </div>
                                        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>⏳ Code valid for 7 days. Share this code with students.</p>
                                    </div>
                                ) : (
                                    <button
                                        className="btn btn-outline btn-sm"
                                        disabled={generatingOpenCode}
                                        onClick={async () => {
                                            setGeneratingOpenCode(true);
                                            try {
                                                const res = await api.post<{ inviteCode: string }>(`/courses/${courseId}/invite`, { email: '*' });
                                                setOpenInviteCode(res.inviteCode);
                                            } catch (e) {
                                                setInviteError(e instanceof Error ? e.message : 'Failed to generate code.');
                                            } finally {
                                                setGeneratingOpenCode(false);
                                            }
                                        }}
                                    >
                                        {generatingOpenCode ? <span className="loading loading-spinner loading-sm"></span> : '✨ Generate Open Code'}
                                    </button>
                                )}
                            </div>

                            <div className="cd-invite-divider"><span>or invite a specific student by email</span></div>

                            {/* Single invite */}
                            <div className="cd-invite-section">
                                <p className="cd-invite-section-label">Invite by email</p>
                                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                                    The student will receive an email with a link. One click and they're enrolled — no code needed.
                                </p>
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <input
                                        className="input"
                                        placeholder="student@example.com"
                                        value={inviteEmail}
                                        onChange={(e) => setInviteEmail(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleSendInvite()}
                                    />
                                    <button className="btn btn-primary" onClick={handleSendInvite} disabled={inviteSending || !inviteEmail.trim()}>
                                        {inviteSending ? 'Sending…' : 'Send Invite'}
                                    </button>
                                </div>
                            </div>

                            {/* Sent confirmations */}
                            {invitedEmails.length > 0 && (
                                <div className="cd-invited-list">
                                    {invitedEmails.map((em, i) => (
                                        <div key={i} className="cd-invited-row">
                                            <CheckCircle2 size={15} style={{ color: '#5FA89C', flexShrink: 0 }} />
                                            <span>{em}</span>
                                            <span className="cd-invited-tag">Invite sent</span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Divider */}
                            <div className="cd-invite-divider"><span>or bulk invite</span></div>

                            {/* CSV bulk invite */}
                            <div className="cd-invite-section">
                                <p className="cd-invite-section-label">Bulk invite via CSV</p>
                                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                                    Upload a CSV — all email addresses are detected automatically and each gets an invite email.
                                </p>
                                <label className="cd-csv-upload-btn">
                                    <input type="file" accept=".csv,.txt" onChange={handleCsvUpload} style={{ display: 'none' }} />
                                    <Mail size={15} /> {csvLoading ? `Sending invites… (${csvResults.length} done)` : 'Upload CSV'}
                                </label>
                            </div>

                            {inviteError && <p style={{ color: 'var(--error)', fontSize: '0.8125rem', marginTop: '0.5rem' }}>{inviteError}</p>}

                            {/* CSV results */}
                            {csvResults.length > 0 && (
                                <div className="cd-csv-results">
                                    <div className="cd-csv-results-header">
                                        <span>{csvResults.filter(r => r.sent).length} of {csvResults.length} invites sent</span>
                                    </div>
                                    <div className="cd-csv-table">
                                        {csvResults.map((r, i) => (
                                            <div key={i} className={`cd-csv-row ${r.error ? 'cd-csv-row-error' : ''}`}>
                                                {r.sent
                                                    ? <CheckCircle2 size={14} style={{ color: '#5FA89C', flexShrink: 0 }} />
                                                    : <XCircle size={14} style={{ color: '#C86F7A', flexShrink: 0 }} />
                                                }
                                                <span className="cd-csv-email">{r.email}</span>
                                                {r.error && <span className="cd-csv-err">{r.error}</span>}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                        <div className="cd-modal-footer">
                            <button className="btn btn-outline" onClick={() => { setShowInviteModal(false); setCsvResults([]); setInvitedEmails([]); }}>Done</button>
                        </div>
                    </div>
                </div>
            )}

            {/* ── Join with Code Modal (student) ── */}
            {showJoinModal && (
                <div className="cd-modal-overlay" onClick={() => setShowJoinModal(false)}>
                    <div className="cd-modal animate-scale-in" onClick={(e) => e.stopPropagation()}>
                        <div className="cd-modal-header">
                            <h2><LogIn size={18} /> Join with Code</h2>
                            <button className="cd-modal-close" onClick={() => setShowJoinModal(false)}><X size={20} /></button>
                        </div>
                        <div className="cd-modal-body">
                            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                                Enter the invite code your teacher shared with you.
                            </p>
                            <div className="cd-modal-field">
                                <label>Invite Code</label>
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <input
                                        className="input"
                                        placeholder="e.g. aB3xYz9Qr1"
                                        value={joinCode}
                                        onChange={(e) => setJoinCode(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleJoinCourse()}
                                    />
                                    <button className="btn btn-primary" onClick={handleJoinCourse} disabled={joinLoading || !joinCode.trim()}>
                                        {joinLoading ? 'Joining…' : 'Join'}
                                    </button>
                                </div>
                            </div>
                            {joinError && <p style={{ color: 'var(--error)', fontSize: '0.8125rem' }}>{joinError}</p>}
                            {joinSuccess && <p style={{ color: 'var(--accent)', fontSize: '0.8125rem', fontWeight: 600 }}>{joinSuccess}</p>}
                        </div>
                        <div className="cd-modal-footer">
                            <button className="btn btn-outline" onClick={() => setShowJoinModal(false)}>Close</button>
                        </div>
                    </div>
                </div>
            )}

            {/* Assignment details: instructions, the student's own work, or the teacher's grading list */}
            {(() => {
                const a = assignments.find((x) => x.id === openAssignmentId);
                return a && courseId ? (
                    <AssignmentDialog
                        courseId={courseId}
                        assignment={a}
                        isInstructor={isInstructor}
                        onClose={() => setOpenAssignmentId(null)}
                        onWorkChanged={(changes) => setAssignments((prev) => prev.map((x) => (x.id === a.id ? { ...x, ...changes } : x)))}
                    />
                ) : null;
            })()}

            {/* A stream post opened on its own: full text, attachments and class comments */}
            {(() => {
                const post = stream.find((s) => s.id === openPostId);
                return post && courseId ? (
                    <div className="cd-modal-overlay" onClick={() => setOpenPostId(null)}>
                        <div className="cd-modal cd-modal-wide cd-post-dialog animate-scale-in" role="dialog" aria-modal="true" aria-label="Post" onClick={(e) => e.stopPropagation()}>
                            <div className="cd-modal-header">
                                {renderFeedHeader(post)}
                                <button className="cd-modal-close" onClick={() => setOpenPostId(null)} aria-label="Close"><X size={20} /></button>
                            </div>
                            <div className="cd-modal-body">
                                {post.type === 'announcement' && post.title && <h3>{post.title}</h3>}
                                <p className="cd-assignment-desc">{post.description}</p>
                                {renderAttachments(post)}
                                <StreamComments courseId={courseId} itemId={post.id} canModerate={isInstructor} />
                            </div>
                        </div>
                    </div>
                ) : null;
            })()}

            {/* Student: every assignment with its status and grade */}
            {showMyWork && (
                <div className="cd-modal-overlay" onClick={() => setShowMyWork(false)}>
                    <div className="cd-modal cd-modal-wide cd-assignment-dialog animate-scale-in" role="dialog" aria-modal="true" aria-labelledby="cd-mywork-title" onClick={(e) => e.stopPropagation()}>
                        <div className="cd-modal-header">
                            <h2 id="cd-mywork-title"><FileText size={18} /> Your work</h2>
                            <button className="cd-modal-close" onClick={() => setShowMyWork(false)} aria-label="Close"><X size={20} /></button>
                        </div>
                        <div className="cd-modal-body">
                            {assignments.length === 0 ? (
                                <p className="cd-assignment-meta">No assignments yet.</p>
                            ) : (
                                <div className="cd-grade-table">
                                    {assignments.map((a) => {
                                        const st = statusLabel(a.status, a.submittedAt, a.dueDate, a.grade, a.points);
                                        return (
                                            <button key={a.id} type="button" className="cd-grade-row cd-mywork-row" onClick={() => { setShowMyWork(false); setOpenAssignmentId(a.id); }}>
                                                <span className="cd-grade-student">
                                                    <span className="cd-grade-name">{a.title}</span>
                                                    <span className="cd-assignment-meta">Due {formatDue(a.dueDate)}</span>
                                                </span>
                                                <span className={`cd-status cd-status-${st.tone}`}>{st.text}</span>
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                        <div className="cd-modal-footer">
                            <button className="btn btn-outline" onClick={() => setShowMyWork(false)}>Close</button>
                        </div>
                    </div>
                </div>
            )}

            {showSuccessModal && (
                <div className="cd-modal-overlay" onClick={() => setShowSuccessModal(false)}>
                    <div className="cd-modal animate-scale-in" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '400px', textAlign: 'center' }}>
                        <div className="cd-modal-header" style={{ borderBottom: 'none', justifyContent: 'flex-end', paddingBottom: 0 }}>
                            <button className="cd-modal-close" onClick={() => setShowSuccessModal(false)}><X size={20} /></button>
                        </div>
                        <div className="cd-modal-body" style={{ padding: '0 2rem 2rem' }}>
                            <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>✅</div>
                            <h3 style={{ fontSize: '1.5rem', fontWeight: 'bold', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>Success!</h3>
                            <p style={{ color: 'var(--text-secondary)' }}>Announcement posted successfully.</p>
                            <div style={{ marginTop: '2rem', display: 'flex', justifyContent: 'center' }}>
                                <button className="btn btn-primary" style={{ padding: '0.75rem 2.5rem', borderRadius: '0.75rem' }} onClick={() => setShowSuccessModal(false)}>Great</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
