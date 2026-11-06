import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
    id: string;
    email: string;
    fullName: string;
    name?: string;
    role: string;
    institute?: string;
    avatar?: string;
}

interface AuthState {
    user: User | null;
    token: string | null;
    refreshToken: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    isRestoring: boolean;
    login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
    signup: (data: { name: string; email: string; password: string; confirmPassword: string; institute?: string; role?: string }) => Promise<void>;
    logout: () => Promise<void>;
    restoreSession: () => Promise<void>;
    refreshSession: () => Promise<boolean>;
    setUser: (user: User) => void;
    clearSession: () => void;
}

const API_URL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? (typeof window !== 'undefined' ? `http://${window.location.hostname}:8000/api` : 'http://localhost:8000/api') : '/api');

// The backend rotates refresh tokens (each one works once), so concurrent 401s must share one refresh.
let refreshInFlight: Promise<boolean> | null = null;

/** Backend returns { success, error: { code, message, details } }. Extract message string. */
function getErrorMessage(data: any, fallback: string): string {
    if (data?.error && typeof data.error === 'object' && typeof data.error.message === 'string') {
        return data.error.message;
    }
    if (typeof data?.message === 'string') return data.message;
    if (Array.isArray(data?.details) && data.details.length) {
        return data.details.map((d: any) => d?.msg ?? d?.message ?? String(d)).join('. ');
    }
    return fallback;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set, get) => ({
            user: null,
            token: null,
            refreshToken: null,
            isAuthenticated: false,
            isLoading: false,
            isRestoring: true,

            login: async (email: string, password: string, rememberMe = false) => {
                set({ isLoading: true });
                try {
                    const res = await fetch(`${API_URL}/auth/signin`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password, remember_me: rememberMe }),
                    });
                    const contentType = res.headers.get('content-type');
                    if (!contentType || !contentType.includes('application/json')) {
                        throw new Error('Server error. Please try again later.');
                    }
                    const data = await res.json();
                    if (!res.ok) throw new Error(getErrorMessage(data, 'Login failed'));
                    const userData = data.data || data;
                    const user = userData.user;
                    if (user && !user.name) user.name = user.fullName || user.full_name || 'User';
                    set({ user, token: userData.token, refreshToken: userData.refresh_token ?? null, isAuthenticated: true, isLoading: false });
                } catch (error) {
                    set({ isLoading: false });
                    throw error;
                }
            },

            signup: async (formData) => {
                set({ isLoading: true });
                try {
                    const res = await fetch(`${API_URL}/auth/signup`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            fullName: formData.name,
                            email: formData.email,
                            password: formData.password,
                            confirmPassword: formData.confirmPassword,
                            institute: formData.institute || undefined,
                            role: formData.role === 'teacher' ? 'teacher' : 'student',
                        }),
                    });
                    const contentType = res.headers.get('content-type');
                    if (!contentType || !contentType.includes('application/json')) {
                        throw new Error('Server error. Please try again later.');
                    }
                    const data = await res.json();
                    if (!res.ok) {
                        const msg = getErrorMessage(data, 'Signup failed');
                        if (msg.toLowerCase().includes('already exists') && formData.role === 'teacher') {
                            throw new Error('An account with this email already exists. Sign in above, or use a different email to create a teacher account.');
                        }
                        throw new Error(msg);
                    }
                    const userData = data.data || data;
                    const user = userData.user;
                    if (user) {
                        if (!user.name) user.name = user.fullName || user.full_name || 'User';
                        const requestedRole = formData.role === 'teacher' ? 'teacher' : 'student';
                        user.role = (user.role === 'teacher' || user.role === 'admin') ? user.role : requestedRole;
                    }
                    set({ user, token: userData.token, refreshToken: userData.refresh_token ?? null, isAuthenticated: true, isLoading: false });
                } catch (error) {
                    set({ isLoading: false });
                    throw error;
                }
            },

            logout: async () => {
                try {
                    const token = get().token;
                    const headers: Record<string, string> = {};
                    if (token) headers['Authorization'] = `Bearer ${token}`;
                    await fetch(`${API_URL}/auth/logout`, { method: 'POST', headers });
                } finally {
                    set({ user: null, token: null, refreshToken: null, isAuthenticated: false });
                }
            },

            restoreSession: async () => {
                set({ isRestoring: true });
                if (!get().token) {
                    set({ user: null, token: null, refreshToken: null, isAuthenticated: false, isRestoring: false });
                    return;
                }
                try {
                    const fetchMe = () => fetch(`${API_URL}/auth/me`, {
                        headers: { 'Authorization': `Bearer ${get().token}` }
                    });
                    let res = await fetchMe();
                    // The access token lasts minutes; after a longer break, renew it before giving up.
                    if (res.status === 401 && await get().refreshSession()) {
                        res = await fetchMe();
                    }
                    if (res.status === 401 || res.status === 403) {
                        set({ user: null, token: null, refreshToken: null, isAuthenticated: false, isRestoring: false });
                        return;
                    }
                    // Other failures (server error) are not the user's fault: keep the saved session.
                    if (!res.ok) {
                        set({ isRestoring: false });
                        return;
                    }
                    const data = await res.json();
                    const user = data.data?.user || data;
                    if (user && !user.name) user.name = user.fullName || user.full_name || 'User';
                    set({ user, isAuthenticated: true, isRestoring: false });
                } catch {
                    // Server unreachable: keep the saved session instead of signing the user out.
                    set({ isRestoring: false });
                }
            },

            /** Swap the refresh token for a new access token. Returns false if the session cannot be renewed. */
            refreshSession: () => {
                if (refreshInFlight) return refreshInFlight;
                refreshInFlight = (async () => {
                    const refreshToken = get().refreshToken;
                    if (!refreshToken) return false;
                    try {
                        const res = await fetch(`${API_URL}/auth/refresh`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ refresh_token: refreshToken }),
                        });
                        if (!res.ok) return false;
                        const data = await res.json();
                        set({ token: data.token ?? data.access_token, refreshToken: data.refresh_token ?? null });
                        return true;
                    } catch {
                        return false;
                    }
                })();
                return refreshInFlight.finally(() => { refreshInFlight = null; });
            },

            setUser: (user: User) => {
                set({ user });
            },
            clearSession: () => {
                set({ user: null, token: null, refreshToken: null, isAuthenticated: false, isRestoring: false, isLoading: false });
            },
        }),
        {
            name: 'saarthi-auth',
            partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated, token: state.token, refreshToken: state.refreshToken }),
        }
    )
);
