import { useEffect, useRef, useState } from 'react';
import { FileText, X, Paperclip, Plus, Lock } from 'lucide-react';
import { api, getUploadFullUrl, uploadFile, type SubmissionResponse } from '../lib/api';
import { formatDue, isClosed, parseFiles, statusLabel, dueTime } from '../lib/assignmentStatus';
import { useToast } from './Toast';

export interface AssignmentDialogItem {
    id: string;
    title: string;
    description: string;
    dueDate: string;
    points: number;
    hardDeadline?: boolean;
    status: 'pending' | 'submitted' | 'graded';
    grade?: number | null;
    submittedAt?: string | null;
    attachmentUrl?: string | null;
}

interface Props {
    courseId: string;
    assignment: AssignmentDialogItem;
    isInstructor: boolean;
    onClose: () => void;
    /** The student's own work changed (turned in or unsubmitted). */
    onWorkChanged: (changes: Pick<AssignmentDialogItem, 'status' | 'submittedAt' | 'attachmentUrl'>) => void;
}

function formatDate(iso?: string | null): string {
    if (!iso) return '';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function fileUrl(url: string): string {
    return url.startsWith('/') ? getUploadFullUrl(url) : url;
}

function fileName(url: string): string {
    return decodeURIComponent(url.split('/').pop() || url);
}

export default function AssignmentDialog({ courseId, assignment, isInstructor, onClose, onWorkChanged }: Props) {
    const toast = useToast();
    const fileInput = useRef<HTMLInputElement>(null);
    const [subs, setSubs] = useState<SubmissionResponse[]>([]);
    const [grades, setGrades] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(isInstructor);
    const [error, setError] = useState<string | null>(null);
    const [savingId, setSavingId] = useState<string | null>(null);
    // Student's files: kept after unsubmitting, editable until turned in.
    const [files, setFiles] = useState<string[]>(() => parseFiles(assignment.attachmentUrl));
    const [uploading, setUploading] = useState(false);
    const [working, setWorking] = useState(false);

    useEffect(() => {
        if (!isInstructor) return;
        let cancelled = false;
        api.get<SubmissionResponse[]>(`/courses/${courseId}/assignments/${assignment.id}/submissions`)
            .then((rows) => {
                if (cancelled) return;
                setSubs(rows);
                setGrades(Object.fromEntries(rows.map((r) => [r.userId, r.grade != null ? String(r.grade) : ''])));
            })
            .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load student work'); })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [isInstructor, courseId, assignment.id]);

    const saveGrade = async (row: SubmissionResponse) => {
        const raw = (grades[row.userId] ?? '').trim();
        const grade = raw === '' ? null : Number(raw);
        if (grade !== null && (Number.isNaN(grade) || grade < 0 || grade > assignment.points)) {
            toast.showToast(`Enter a grade from 0 to ${assignment.points}`, 'error');
            return;
        }
        setSavingId(row.userId);
        try {
            const updated = await api.put<SubmissionResponse>(
                `/courses/${courseId}/assignments/${assignment.id}/submissions/${row.userId}/grade`,
                { grade },
            );
            setSubs((prev) => prev.map((s) => (s.userId === row.userId ? updated : s)));
            toast.showToast(grade === null ? `Grade removed for ${row.studentName}` : `Graded ${row.studentName}: ${grade}/${assignment.points}`);
        } catch (e) {
            toast.showToast(e instanceof Error ? e.message : 'Could not save grade', 'error');
        } finally {
            setSavingId(null);
        }
    };

    const addFiles = async (picked: FileList | null) => {
        if (!picked || picked.length === 0) return;
        setUploading(true);
        try {
            const urls: string[] = [];
            for (const f of Array.from(picked)) {
                const { url } = await uploadFile(f);
                urls.push(url);
            }
            setFiles((prev) => [...prev, ...urls]);
        } catch (e) {
            toast.showToast(e instanceof Error ? e.message : 'Upload failed', 'error');
        } finally {
            setUploading(false);
            if (fileInput.current) fileInput.current.value = '';
        }
    };

    const turnIn = async () => {
        setWorking(true);
        try {
            const attachmentUrl = files.length ? JSON.stringify(files) : null;
            await api.post(`/courses/${courseId}/assignments/${assignment.id}/submit`, { attachmentUrl });
            onWorkChanged({ status: 'submitted', submittedAt: new Date().toISOString(), attachmentUrl });
            toast.showToast(files.length ? 'Work turned in' : 'Marked as done');
        } catch (e) {
            toast.showToast(e instanceof Error ? e.message : 'Could not turn in', 'error');
        } finally {
            setWorking(false);
        }
    };

    const unsubmit = async () => {
        setWorking(true);
        try {
            await api.post(`/courses/${courseId}/assignments/${assignment.id}/unsubmit`);
            onWorkChanged({ status: 'pending', submittedAt: null, attachmentUrl: assignment.attachmentUrl });
            toast.showToast('Unsubmitted. Add or change your work, then turn it in again.');
        } catch (e) {
            toast.showToast(e instanceof Error ? e.message : 'Could not unsubmit', 'error');
        } finally {
            setWorking(false);
        }
    };

    const turnedIn = subs.filter((s) => s.status !== 'pending').length;
    const graded = subs.filter((s) => s.status === 'graded').length;
    const mine = statusLabel(assignment.status, assignment.submittedAt, assignment.dueDate, assignment.grade, assignment.points);
    const closed = isClosed(assignment.dueDate, assignment.hardDeadline);
    const pastDue = Date.now() > dueTime(assignment.dueDate);
    const editable = assignment.status === 'pending' && !closed;

    return (
        <div className="cd-modal-overlay" onClick={onClose}>
            <div className="cd-modal cd-modal-wide cd-assignment-dialog animate-scale-in" role="dialog" aria-modal="true" aria-labelledby="cd-assignment-title" onClick={(e) => e.stopPropagation()}>
                <div className="cd-modal-header">
                    <h2 id="cd-assignment-title"><FileText size={18} /> {assignment.title}</h2>
                    <button className="cd-modal-close" onClick={onClose} aria-label="Close"><X size={20} /></button>
                </div>
                <div className="cd-modal-body">
                    <p className="cd-assignment-meta">
                        Due {formatDue(assignment.dueDate)} · {assignment.points} points
                        {assignment.hardDeadline ? ' · No late work accepted' : ' · Late work accepted'}
                    </p>
                    {assignment.description
                        ? <p className="cd-assignment-desc">{assignment.description}</p>
                        : <p className="cd-assignment-meta">No instructions.</p>}

                    {!isInstructor && (
                        <section className="cd-assignment-work">
                            <div className="cd-assignment-work-head">
                                <span className="cd-invite-section-label">Your work</span>
                                <span className={`cd-status cd-status-${mine.tone}`}>{mine.text}</span>
                            </div>

                            {files.length > 0 ? (
                                <ul className="cd-work-files">
                                    {files.map((f) => (
                                        <li key={f}>
                                            <a href={fileUrl(f)} target="_blank" rel="noopener noreferrer" className="cd-assignment-file"><Paperclip size={14} /> {fileName(f)}</a>
                                            {editable && (
                                                <button type="button" className="btn-icon" aria-label={`Remove ${fileName(f)}`} onClick={() => setFiles((prev) => prev.filter((x) => x !== f))}><X size={14} /></button>
                                            )}
                                        </li>
                                    ))}
                                </ul>
                            ) : assignment.status !== 'pending' ? (
                                <p className="cd-assignment-meta">Marked as done without files.</p>
                            ) : null}

                            {assignment.submittedAt && <p className="cd-assignment-meta">Turned in {formatDate(assignment.submittedAt)}</p>}

                            {closed && assignment.status === 'pending' && (
                                <p className="cd-work-closed"><Lock size={14} /> The due time has passed. This assignment no longer accepts work.</p>
                            )}
                            {editable && pastDue && (
                                <p className="cd-assignment-meta">The due time has passed. Work turned in now is marked late.</p>
                            )}

                            {editable && (
                                <div className="cd-work-actions">
                                    <input ref={fileInput} type="file" multiple hidden onChange={(e) => addFiles(e.target.files)} />
                                    <button type="button" className="btn btn-outline btn-sm" disabled={uploading || working} onClick={() => fileInput.current?.click()}>
                                        <Plus size={14} /> {uploading ? 'Uploading…' : 'Add file'}
                                    </button>
                                    <button type="button" className="btn btn-primary btn-sm" disabled={uploading || working} onClick={turnIn}>
                                        {working ? 'Turning in…' : files.length ? 'Turn in' : 'Mark as done'}
                                    </button>
                                </div>
                            )}
                            {assignment.status === 'submitted' && !closed && (
                                <div className="cd-work-actions">
                                    <button type="button" className="btn btn-outline btn-sm" disabled={working} onClick={unsubmit}>
                                        {working ? 'Unsubmitting…' : 'Unsubmit'}
                                    </button>
                                </div>
                            )}
                        </section>
                    )}

                    {isInstructor && (
                        <section className="cd-assignment-work">
                            <div className="cd-assignment-work-head">
                                <span className="cd-invite-section-label">Student work</span>
                                {!loading && !error && <span className="cd-assignment-meta">{turnedIn} turned in · {graded} graded · {subs.length} students</span>}
                            </div>
                            {loading ? (
                                <p className="cd-assignment-meta">Loading…</p>
                            ) : error ? (
                                <p className="cd-assignment-error">{error}</p>
                            ) : subs.length === 0 ? (
                                <p className="cd-assignment-meta">No students in this course yet.</p>
                            ) : (
                                <div className="cd-grade-table">
                                    {subs.map((s) => {
                                        const st = statusLabel(s.status, s.submittedAt, assignment.dueDate, s.grade, assignment.points);
                                        const work = parseFiles(s.attachmentUrl);
                                        return (
                                            <div key={s.userId} className="cd-grade-row">
                                                <div className="cd-grade-student">
                                                    <span className="cd-grade-name">{s.studentName}</span>
                                                    <span className={`cd-status cd-status-${st.tone}`}>{st.text}</span>
                                                    {work.map((f, i) => (
                                                        <a key={f} href={fileUrl(f)} target="_blank" rel="noopener noreferrer" className="cd-assignment-file">
                                                            <Paperclip size={13} /> {work.length > 1 ? `File ${i + 1}` : 'View work'}
                                                        </a>
                                                    ))}
                                                    {work.length === 0 && s.submittedAt && <span className="cd-assignment-meta">Marked as done</span>}
                                                </div>
                                                <div className="cd-grade-input">
                                                    <input
                                                        className="input"
                                                        type="number"
                                                        min={0}
                                                        max={assignment.points}
                                                        step="any"
                                                        placeholder="—"
                                                        aria-label={`Grade for ${s.studentName}`}
                                                        value={grades[s.userId] ?? ''}
                                                        onChange={(e) => setGrades((prev) => ({ ...prev, [s.userId]: e.target.value }))}
                                                        onKeyDown={(e) => e.key === 'Enter' && saveGrade(s)}
                                                    />
                                                    <span className="cd-assignment-meta">/{assignment.points}</span>
                                                    <button className="btn btn-outline btn-sm" disabled={savingId === s.userId} onClick={() => saveGrade(s)}>
                                                        {savingId === s.userId ? 'Saving…' : 'Return'}
                                                    </button>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </section>
                    )}
                </div>
                <div className="cd-modal-footer">
                    <button className="btn btn-outline" onClick={onClose}>Close</button>
                </div>
            </div>
        </div>
    );
}
