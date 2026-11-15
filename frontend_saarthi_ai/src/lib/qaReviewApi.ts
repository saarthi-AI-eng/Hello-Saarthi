/** QA review dashboard API client. Backend returns {success, data} for
 * every endpoint here (see saarthi_backend/routers/qa_review_router.py) —
 * unwrapped to `data` here so page code works with plain typed objects. */

const getBaseUrl = () =>
    import.meta.env.VITE_API_URL ||
    (import.meta.env.DEV
        ? (typeof window !== 'undefined' ? `http://${window.location.hostname}:8000/api` : 'http://localhost:8000/api')
        : '/api');

function getToken(): string | null {
    try {
        return JSON.parse(localStorage.getItem('saarthi-auth') || '{}')?.state?.token ?? null;
    } catch {
        return null;
    }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const token = getToken();
    const res = await fetch(`${getBaseUrl()}${path}`, {
        ...init,
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...init.headers,
        },
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
        throw new Error(body?.error?.message || `Request failed (${res.status})`);
    }
    return body.data as T;
}

export interface QAStats {
    pendingReview: number;
    reviewedToday: number;
    approved: number;
    rejected: number;
}

export interface QueueItem {
    content_id: string;
    source_file: string;
    source_jsonl_path: string;
    content_type: string;
    course: string | null;
    page: number | null;
    start_time: number | null;
    end_time: number | null;
    qa_score: number | null;
    qa_issues: string[];
    qa_timestamp: string | null;
}

export interface QueueDocument {
    source_file: string;
    content_type: string;
    items: QueueItem[];
}

export interface QueueResponse {
    total: number;
    limit: number;
    offset: number;
    documents: QueueDocument[];
}

export interface LineConfidence {
    text: string;
    confidence: number | null;
}

export interface EquationSuggestion {
    original: string;
    suggestion: string;
    quality: string | null;
}

export interface ContentDetail {
    contentId: string;
    sourceFile: string;
    contentType: string;
    course: string | null;
    page: number | null;
    startTime: number | null;
    endTime: number | null;
    text: string;
    qaStatus: string;
    qaScore: number | null;
    qaChecks: Record<string, number>;
    qaIssues: string[];
    recognitionConfidence: number | null;
    qaVersion: string | null;
    qaTimestamp: string | null;
    lineConfidences: LineConfidence[];
    equationSuggestions: EquationSuggestion[];
    hasSourceImage: boolean;
}

export interface ReviewHistoryEntry {
    reviewerId: number | null;
    decision: string;
    previousStatus: string;
    newStatus: string;
    reason: string | null;
    edited: boolean;
    createdAt: string | null;
}

export const qaReviewApi = {
    stats: () => request<QAStats>('/qa-review/stats'),

    queue: (params: { limit?: number; offset?: number; contentType?: string; course?: string } = {}) => {
        const q = new URLSearchParams();
        if (params.limit != null) q.set('limit', String(params.limit));
        if (params.offset != null) q.set('offset', String(params.offset));
        if (params.contentType) q.set('contentType', params.contentType);
        if (params.course) q.set('course', params.course);
        const qs = q.toString();
        return request<QueueResponse>(`/qa-review/queue${qs ? `?${qs}` : ''}`);
    },

    content: (contentId: string, sourceJsonlPath: string) =>
        request<ContentDetail>(`/qa-review/content/${encodeURIComponent(contentId)}?sourceJsonlPath=${encodeURIComponent(sourceJsonlPath)}`),

    history: (contentId: string) =>
        request<ReviewHistoryEntry[]>(`/qa-review/content/${encodeURIComponent(contentId)}/history`),

    review: (body: { contentId: string; sourceJsonlPath: string; decision: 'accept' | 'reject' | 'reprocess'; reason?: string; editedText?: string }) =>
        request<{ content_id: string; previous_status: string; new_status: string; edited: boolean }>('/qa-review/review', {
            method: 'POST',
            body: JSON.stringify(body),
        }),

    /** Fetches the rendered source page as a blob object URL — images need
     * the same Authorization header as everything else, so a plain <img
     * src="..."> won't work; fetch + createObjectURL instead (same
     * pattern already used for PDF materials in CourseDetail.tsx).
     * Caller must URL.revokeObjectURL() the result when done with it. */
    sourceImageUrl: async (contentId: string, sourceJsonlPath: string): Promise<string> => {
        const token = getToken();
        const res = await fetch(
            `${getBaseUrl()}/qa-review/content/${encodeURIComponent(contentId)}/source-image?sourceJsonlPath=${encodeURIComponent(sourceJsonlPath)}`,
            { credentials: 'include', headers: token ? { Authorization: `Bearer ${token}` } : {} },
        );
        if (!res.ok) throw new Error(`Could not load source image (${res.status}).`);
        const blob = await res.blob();
        return URL.createObjectURL(blob);
    },
};
