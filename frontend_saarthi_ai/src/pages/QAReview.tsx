import { useCallback, useEffect, useRef, useState } from 'react';
import { CheckCircle2, XCircle, RotateCcw, ClipboardList, Clock, ThumbsUp, ThumbsDown, Loader2, ChevronDown, ChevronRight, Wand2 } from 'lucide-react';
import { qaReviewApi, type QAStats, type QueueDocument, type ContentDetail } from '../lib/qaReviewApi';
import { usePageTitle } from '../lib/usePageTitle';
import { useToast } from '../components/Toast';
import EmptyState from '../components/EmptyState';
import './QAReview.css';

const PAGE_SIZE = 20;
const LOW_CONFIDENCE_THRESHOLD = 0.7;

type PendingDecision = { contentId: string; sourceJsonlPath: string; decision: 'accept' | 'reject' | 'reprocess' } | null;

export default function QAReviewPage() {
    usePageTitle('QA Review');
    const { showToast } = useToast();

    const [stats, setStats] = useState<QAStats | null>(null);
    const [documents, setDocuments] = useState<QueueDocument[]>([]);
    const [total, setTotal] = useState(0);
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [expanded, setExpanded] = useState<Record<string, boolean>>({});
    const [detailCache, setDetailCache] = useState<Record<string, ContentDetail>>({});
    const [detailLoading, setDetailLoading] = useState<string | null>(null);
    const [editedTextByItem, setEditedTextByItem] = useState<Record<string, string>>({});
    const [imageUrlByItem, setImageUrlByItem] = useState<Record<string, string>>({});
    const textareaRefs = useRef<Record<string, HTMLTextAreaElement | null>>({});

    const [confirming, setConfirming] = useState<PendingDecision>(null);
    const [reason, setReason] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const load = useCallback(async (newOffset: number) => {
        setLoading(true);
        setError(null);
        try {
            const [statsRes, queueRes] = await Promise.all([
                qaReviewApi.stats(),
                qaReviewApi.queue({ limit: PAGE_SIZE, offset: newOffset }),
            ]);
            setStats(statsRes);
            setDocuments(queueRes.documents);
            setTotal(queueRes.total);
            setOffset(newOffset);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load the QA queue.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load(0);
    }, [load]);

    // Revoke object URLs on unmount to avoid leaking blob memory.
    useEffect(() => () => {
        Object.values(imageUrlByItem).forEach((url) => URL.revokeObjectURL(url));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const toggleExpand = async (item: { content_id: string; source_jsonl_path: string }) => {
        const key = item.content_id;
        setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
        if (!detailCache[key]) {
            setDetailLoading(key);
            try {
                const detail = await qaReviewApi.content(item.content_id, item.source_jsonl_path);
                setDetailCache((prev) => ({ ...prev, [key]: detail }));
                setEditedTextByItem((prev) => ({ ...prev, [key]: detail.text }));
                if (detail.hasSourceImage) {
                    qaReviewApi.sourceImageUrl(item.content_id, item.source_jsonl_path)
                        .then((url) => setImageUrlByItem((prev) => ({ ...prev, [key]: url })))
                        .catch(() => { /* image preview is a bonus, not required to review */ });
                }
            } catch {
                showToast('Could not load this item\'s details.', 'error');
            } finally {
                setDetailLoading(null);
            }
        }
    };

    const insertSuggestion = (key: string, suggestion: string) => {
        const el = textareaRefs.current[key];
        const current = editedTextByItem[key] ?? '';
        if (!el) {
            setEditedTextByItem((prev) => ({ ...prev, [key]: current + suggestion }));
            return;
        }
        const start = el.selectionStart ?? current.length;
        const end = el.selectionEnd ?? current.length;
        const next = current.slice(0, start) + suggestion + current.slice(end);
        setEditedTextByItem((prev) => ({ ...prev, [key]: next }));
        requestAnimationFrame(() => {
            el.focus();
            const cursor = start + suggestion.length;
            el.setSelectionRange(cursor, cursor);
        });
    };

    const confirmDecision = async () => {
        if (!confirming) return;
        setSubmitting(true);
        try {
            const key = confirming.contentId;
            const original = detailCache[key]?.text;
            const edited = editedTextByItem[key];
            const editedText = edited != null && edited !== original ? edited : undefined;
            await qaReviewApi.review({ ...confirming, reason: reason.trim() || undefined, editedText });
            showToast(
                confirming.decision === 'accept' ? 'Approved — now eligible for the knowledge base.' :
                confirming.decision === 'reject' ? 'Rejected — excluded from the knowledge base.' :
                'Sent for reprocessing.',
                'success',
            );
            setConfirming(null);
            setReason('');
            await load(offset);
        } catch (e) {
            showToast(e instanceof Error ? e.message : 'Could not submit the decision.', 'error');
        } finally {
            setSubmitting(false);
        }
    };

    const statCards = [
        { label: 'Pending Review', value: stats?.pendingReview, icon: ClipboardList, color: '#B59A63' },
        { label: 'Reviewed Today', value: stats?.reviewedToday, icon: Clock, color: '#0F766E' },
        { label: 'Approved', value: stats?.approved, icon: ThumbsUp, color: '#5FA89C' },
        { label: 'Rejected', value: stats?.rejected, icon: ThumbsDown, color: '#C86F7A' },
    ];

    return (
        <div className="qa-review">
            <div className="dash-welcome animate-fade-in">
                <div>
                    <h1 className="dash-welcome-title">QA Review</h1>
                    <p className="dash-welcome-sub">Review content flagged by Auto-QA as uncertain — the rest moves through automatically.</p>
                </div>
            </div>

            {error && <div className="dash-error" role="alert">{error}</div>}

            <div className="dash-stats animate-fade-in">
                {statCards.map((s) => {
                    const Icon = s.icon;
                    return (
                        <div key={s.label} className="dash-stat-card">
                            <div className="dash-stat-icon" style={{ background: `${s.color}22`, color: s.color }}>
                                <Icon size={24} />
                            </div>
                            <div className="dash-stat-info">
                                {loading ? <div className="skeleton dash-stat-skeleton-value" /> : <span className="dash-stat-value">{s.value ?? '–'}</span>}
                                <span className="dash-stat-label">{s.label}</span>
                            </div>
                        </div>
                    );
                })}
            </div>

            <div className="card qa-queue-card">
                <div className="card-body">
                    <h2 className="qa-queue-title">Pending Review Queue</h2>

                    {loading && <div className="qa-queue-loading"><Loader2 size={20} className="spin" /> Loading…</div>}

                    {!loading && documents.length === 0 && (
                        <EmptyState
                            icon={<CheckCircle2 size={32} />}
                            title="Nothing pending review"
                            description="Everything Auto-QA flagged as uncertain has already been reviewed."
                        />
                    )}

                    {!loading && documents.map((doc) => (
                        <div key={doc.source_file} className="qa-doc-group">
                            <div className="qa-doc-header">
                                <span className="qa-doc-name">{doc.source_file}</span>
                                <span className="qa-doc-count">{doc.items.length} page{doc.items.length === 1 ? '' : 's'} pending</span>
                            </div>
                            {doc.items.map((item) => {
                                const key = item.content_id;
                                const isOpen = !!expanded[key];
                                const detail = detailCache[key];
                                const imageUrl = imageUrlByItem[key];
                                const editedText = editedTextByItem[key] ?? '';
                                const isEdited = detail != null && editedText !== detail.text;
                                return (
                                    <div key={key} className="qa-item">
                                        <button className="qa-item-row" onClick={() => toggleExpand(item)}>
                                            {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                                            <span className="qa-item-label">
                                                {item.page != null ? `Page ${item.page}` : `${item.start_time?.toFixed(1)}s – ${item.end_time?.toFixed(1)}s`}
                                            </span>
                                            <span className="qa-item-score">Score: {item.qa_score ?? '–'}</span>
                                            {item.qa_issues.length > 0 && <span className="qa-item-issues">{item.qa_issues.slice(0, 2).join(', ')}</span>}
                                        </button>

                                        {isOpen && (
                                            <div className="qa-item-detail">
                                                {detailLoading === key && <Loader2 size={16} className="spin" />}
                                                {detail && (
                                                    <>
                                                        <div className="qa-split">
                                                            <div className="qa-split-source">
                                                                {detail.hasSourceImage ? (
                                                                    imageUrl ? (
                                                                        <img src={imageUrl} alt={`Source page ${detail.page}`} className="qa-source-image" />
                                                                    ) : (
                                                                        <div className="qa-image-loading"><Loader2 size={18} className="spin" /> Loading page image…</div>
                                                                    )
                                                                ) : (
                                                                    <div className="qa-image-loading">No page preview available for this content type.</div>
                                                                )}
                                                            </div>
                                                            <div className="qa-split-text">
                                                                {detail.lineConfidences.length > 0 && (
                                                                    <div className="qa-line-confidences" title="Lines PaddleOCR itself scored as low-confidence">
                                                                        {detail.lineConfidences.map((line, i) => (
                                                                            <span
                                                                                key={i}
                                                                                className={line.confidence != null && line.confidence < LOW_CONFIDENCE_THRESHOLD ? 'qa-line-low-confidence' : undefined}
                                                                            >
                                                                                {line.text}
                                                                                {'\n'}
                                                                            </span>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                                <textarea
                                                                    ref={(el) => { textareaRefs.current[key] = el; }}
                                                                    className="qa-item-text-edit"
                                                                    value={editedText}
                                                                    onChange={(e) => setEditedTextByItem((prev) => ({ ...prev, [key]: e.target.value }))}
                                                                />
                                                                {isEdited && <span className="qa-edited-badge">Edited — original preserved in history</span>}
                                                            </div>
                                                        </div>

                                                        {detail.equationSuggestions.length > 0 && (
                                                            <div className="qa-suggestions">
                                                                <h4>Suggested corrections (equation second-opinion)</h4>
                                                                {detail.equationSuggestions.map((s, i) => (
                                                                    <div key={i} className="qa-suggestion-row">
                                                                        <span className="qa-suggestion-original">{s.original}</span>
                                                                        <span className="qa-suggestion-arrow">→</span>
                                                                        <span className="qa-suggestion-text">{s.suggestion}</span>
                                                                        <button
                                                                            className="btn btn-ghost btn-sm"
                                                                            type="button"
                                                                            onClick={() => insertSuggestion(key, s.suggestion)}
                                                                        >
                                                                            <Wand2 size={14} /> Insert at cursor
                                                                        </button>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        )}

                                                        <div className="qa-item-meta">
                                                            {detail.recognitionConfidence != null && (
                                                                <span>Recognition confidence: {(detail.recognitionConfidence * 100).toFixed(0)}%</span>
                                                            )}
                                                            {detail.course && <span>Course: {detail.course}</span>}
                                                        </div>
                                                        <div className="qa-item-actions">
                                                            <button
                                                                className="btn btn-primary btn-sm"
                                                                onClick={() => setConfirming({ contentId: item.content_id, sourceJsonlPath: item.source_jsonl_path, decision: 'accept' })}
                                                            >
                                                                <CheckCircle2 size={16} /> Accept
                                                            </button>
                                                            <button
                                                                className="btn btn-ghost btn-sm"
                                                                onClick={() => setConfirming({ contentId: item.content_id, sourceJsonlPath: item.source_jsonl_path, decision: 'reject' })}
                                                            >
                                                                <XCircle size={16} /> Reject
                                                            </button>
                                                            <button
                                                                className="btn btn-ghost btn-sm"
                                                                onClick={() => setConfirming({ contentId: item.content_id, sourceJsonlPath: item.source_jsonl_path, decision: 'reprocess' })}
                                                            >
                                                                <RotateCcw size={16} /> Send for Reprocessing
                                                            </button>
                                                        </div>
                                                    </>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    ))}

                    {total > PAGE_SIZE && (
                        <div className="qa-pagination">
                            <button className="btn btn-ghost btn-sm" disabled={offset === 0} onClick={() => load(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
                            <span>{offset + 1}-{Math.min(offset + PAGE_SIZE, total)} of {total}</span>
                            <button className="btn btn-ghost btn-sm" disabled={offset + PAGE_SIZE >= total} onClick={() => load(offset + PAGE_SIZE)}>Next</button>
                        </div>
                    )}
                </div>
            </div>

            {confirming && (
                <div className="qa-modal-overlay" onClick={() => !submitting && setConfirming(null)}>
                    <div className="qa-modal" onClick={(e) => e.stopPropagation()}>
                        <h3>Confirm: {confirming.decision === 'accept' ? 'Accept' : confirming.decision === 'reject' ? 'Reject' : 'Send for reprocessing'}</h3>
                        <p>This will update the status of <code>{confirming.contentId}</code>.</p>
                        {editedTextByItem[confirming.contentId] !== detailCache[confirming.contentId]?.text && (
                            <p className="qa-modal-edit-notice">Your text edits will be saved along with this decision.</p>
                        )}
                        {confirming.decision !== 'accept' && (
                            <textarea
                                className="qa-modal-reason"
                                placeholder="Optional reason…"
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                            />
                        )}
                        <div className="qa-modal-actions">
                            <button className="btn btn-ghost btn-sm" disabled={submitting} onClick={() => setConfirming(null)}>Cancel</button>
                            <button className="btn btn-primary btn-sm" disabled={submitting} onClick={confirmDecision}>
                                {submitting ? <Loader2 size={16} className="spin" /> : 'Confirm'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
