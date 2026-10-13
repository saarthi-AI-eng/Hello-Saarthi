import { createContext, useCallback, useContext, useState } from 'react';
import { CheckCircle, X, AlertCircle } from 'lucide-react';
import './Toast.css';

export type ToastType = 'success' | 'error';

export interface ToastItem {
    id: number;
    message: string;
    type: ToastType;
}

interface ToastContextValue {
    showToast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const AUTO_DISMISS_MS = 4500;

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<ToastItem[]>([]);
    const [nextId, setNextId] = useState(0);

    const showToast = useCallback((message: string, type: ToastType = 'success') => {
        const id = nextId;
        setNextId((n) => n + 1);
        setToasts((prev) => [...prev, { id, message, type }]);
        setTimeout(() => {
            setToasts((prev) => prev.filter((t) => t.id !== id));
        }, AUTO_DISMISS_MS);
    }, [nextId]);

    const dismiss = useCallback((id: number) => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
    }, []);

    return (
        <ToastContext.Provider value={{ showToast }}>
            {children}
            <div className="toast-container" role="region" aria-label="Notifications">
                {toasts.map((t) => (
                    <div
                        key={t.id}
                        className={`toast toast-${t.type} animate-fade-in-up`}
                        role="alert"
                    >
                        {t.type === 'success' ? (
                            <CheckCircle size={20} className="toast-icon" aria-hidden />
                        ) : (
                            <AlertCircle size={20} className="toast-icon" aria-hidden />
                        )}
                        <span className="toast-message">{t.message}</span>
                        <button
                            type="button"
                            className="toast-dismiss"
                            onClick={() => dismiss(t.id)}
                            aria-label="Dismiss"
                        >
                            <X size={16} />
                        </button>
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
}

export function useToast() {
    const ctx = useContext(ToastContext);
    if (!ctx) throw new Error('useToast must be used within ToastProvider');
    return ctx;
}
