/**
 * API client: sends the access token as a Bearer header and renews it once on a 401.
 * Base URL: VITE_API_URL or http://localhost:8000/api
 */

import { useAuthStore } from '../stores/auth.store';

const getBaseUrl = () => {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  if (import.meta.env.DEV) {
    if (typeof window !== 'undefined') return `http://${window.location.hostname}:8000/api`;
    return 'http://localhost:8000/api';
  }
  return '/api';
};

function clearPersistedAuthState() {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem('saarthi-auth');
  } catch {
    // ignore storage errors
  }
  window.dispatchEvent(new Event('saarthi:auth-expired'));
}

export function attemptRefresh(): Promise<boolean> {
  return useAuthStore.getState().refreshSession();
}

function authHeaders(): Record<string, string> {
  const token = useAuthStore.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Run a fetch; on 401, renew the access token once and retry. Signs out if renewal fails. */
async function fetchWithRefresh(doFetch: () => Promise<Response>): Promise<Response> {
  let res = await doFetch();
  if (res.status === 401) {
    if (await attemptRefresh()) res = await doFetch();
    if (res.status === 401) clearPersistedAuthState();
  }
  return res;
}

/** Raw fetch with the auth header and token renewal, for non-JSON responses such as file downloads. */
export function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
  return fetchWithRefresh(() =>
    fetch(url, { ...init, headers: { ...(init.headers as Record<string, string>), ...authHeaders() } })
  );
}

/** Turn upload path (e.g. /uploads/xxx) into full URL for storing in DB. */
export function getUploadFullUrl(path: string): string {
    const base = getBaseUrl();
    const origin = base.replace(/\/api\/?$/, '');
    const p = path.startsWith('/') ? path : '/' + path;
    return origin + p;
}

/** URL for viewing a course material file (PDF etc.) with auth. Use in iframe or new tab. */
export function getMaterialFileUrl(courseId: string, materialId: string): string {
    const base = getBaseUrl();
    return `${base}/courses/${courseId}/materials/${materialId}/file`;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface MyInviteResponse {
  id: string;
  inviteCode: string;
  courseId: string;
  courseTitle: string;
  courseCode: string;
  instructor: string;
  thumbnailEmoji?: string | null;
  expiresAt: string;
}

export interface NotificationResponse {
  id: string;
  type: string;
  title: string;
  body: string;
  link?: string | null;
  readAt?: string | null;
  createdAt: string;
}

export interface ProgressResponse {
  coursesEnrolled: number;
  pendingAssignments: number;
  avgQuizScorePercent: number;
  studyTimeHours: number;
  streakDays: number;
}

export interface CourseResponse {
  id: string;
  title: string;
  code: string;
  instructor: string;
  description?: string;
  thumbnailEmoji?: string;
  color?: string;
}

export interface EnrollmentWithCourseResponse {
  id: string;
  courseId: string;
  progressPercent: number;
  lastAccessedAt?: string;
  course: CourseResponse;
}

export interface AssignmentResponse {
  id: string;
  courseId: string;
  title: string;
  description?: string;
  dueDate: string;
  points: number;
  topic?: string;
  attachments?: string;
  hardDeadline?: boolean;
  createdAt: string;
  status?: string;
  grade?: number;
  submittedAt?: string | null;
  attachmentUrl?: string | null;
}

/** One enrolled student's work on an assignment (teacher view). */
export interface SubmissionResponse {
  userId: string;
  studentName: string;
  studentEmail: string;
  status: 'pending' | 'submitted' | 'graded';
  submittedAt?: string | null;
  attachmentUrl?: string | null;
  grade?: number | null;
}

export interface MaterialResponse {
  id: string;
  courseId: string;
  title: string;
  description?: string;
  type: string;
  url: string;
  topic?: string;
  createdAt: string;
}

export interface StreamItemResponse {
  id: string;
  courseId: string;
  type: string;
  title?: string;
  description: string;
  author: string;
  createdAt: string;
}

export interface CoursePersonResponse {
  userId: string;
  fullName: string;
  progressPercent: number;
}

export interface SearchItem {
  type: string;
  id: string;
  title: string;
  subtitle?: string;
  link?: string;
}

export interface ConversationResponse {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface ChatMessageItemResponse {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
}

export interface ConversationDetailResponse {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessageItemResponse[];
}

export interface SendMessageResponse {
  userMessage: ChatMessageItemResponse;
  assistantMessage: ChatMessageItemResponse;
}

export interface SearchResponse {
  courses: SearchItem[];
  materials: SearchItem[];
  videos: SearchItem[];
  totalCourses: number;
  totalMaterials: number;
  totalVideos: number;
  limit: number;
  offset: number;
}

export interface VideoResponse {
  id: string;
  courseId?: string;
  title: string;
  description?: string;
  durationSeconds: number;
  thumbnailUrl?: string;
  url: string;
  embedUrl?: string;
  chaptersJson?: string;
  sortOrder: number;
}

export interface VideoNoteResponse {
  id: string;
  videoId: string;
  timeSeconds: number;
  text: string;
  createdAt: string;
}

export interface NoteResponse {
  id: string;
  title: string;
  content: string;
  courseId?: string;
  topic?: string;
  createdAt: string;
  updatedAt: string;
}

async function request<T>(
  path: string,
  options: RequestInit & { params?: Record<string, string | number | undefined> } = {}
): Promise<T> {
  const { params, ...init } = options;
  const base = getBaseUrl();
  let url = path.startsWith('http') ? path : `${base}${path.startsWith('/') ? path : `/${path}`}`;
  if (params) {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== '') search.set(k, String(v));
    });
    const q = search.toString();
    if (q) url += (url.includes('?') ? '&' : '?') + q;
  }
  const doFetch = () =>
    fetch(url, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers, ...authHeaders() } as Record<string, string>,
    });

  const res = await fetchWithRefresh(doFetch);
  // 204 No Content has no body - do not parse JSON
  if (res.status === 204) {
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return undefined as T;
  }

  const contentType = res.headers.get('content-type');
  if (!contentType?.includes('application/json')) {
    throw new Error(res.ok ? 'Invalid response' : `Request failed: ${res.status}`);
  }
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const msg = data?.error?.message ?? data?.message ?? `Request failed: ${res.status}`;
    throw new Error(msg);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | undefined>) =>
    request<T>(path, { method: 'GET', params }),

  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),

  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),

  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),

  delete: (path: string) => request<void>(path, { method: 'DELETE' }),
};

/** Load every page of a paginated list (the backend caps a page at 100 items). */
export async function getAllPages<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T[]> {
  const limit = 100;
  const items: T[] = [];
  for (let offset = 0; ; offset += limit) {
    const page = await api.get<PaginatedResponse<T>>(path, { ...params, limit, offset });
    items.push(...(page.items || []));
    if (items.length >= page.total || (page.items || []).length < limit) return items;
  }
}

/** Upload file (course domain); returns { url: string } for assignment attachments etc. */
export async function uploadFile(file: File): Promise<{ url: string }> {
  const base = getBaseUrl();
  const form = new FormData();
  form.append('file', file);

  const res = await fetchWithRefresh(() =>
    fetch(`${base}/courses/upload`, {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    })
  );
  const data = await res.json();
  if (!res.ok) throw new Error(data?.error?.message ?? data?.message ?? 'Upload failed');
  return data;
}
