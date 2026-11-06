import { useEffect } from 'react';
import './ConfirmModal.css';

interface ConfirmModalProps {
    open: boolean;
    title: string;
    message: string;
    confirmLabel?: string;
    variant?: 'danger' | 'primary';
    onConfirm: () => void;
    onCancel: () => void;
    loading?: boolean;
}

export default function ConfirmModal({
    open,
    title,
    message,
    confirmLabel = 'Delete',
    variant = 'danger',
    onConfirm,
    onCancel,
    loading = false,
}: ConfirmModalProps) {
    useEffect(() => {
        if (!open) return;
        const handle = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onCancel();
        };
        window.addEventListener('keydown', handle);
        return () => window.removeEventListener('keydown', handle);
    }, [open, onCancel]);

    if (!open) return null;

    return (
        <div className="confirm-modal-overlay" onClick={onCancel}>
            <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
                <div className="confirm-modal-header">
                    <h3 className="confirm-modal-title">{title}</h3>
                </div>
                <p className="confirm-modal-message">{message}</p>
                <div className="confirm-modal-footer">
                    <button type="button" className="btn btn-outline" onClick={onCancel} disabled={loading}>
                        Cancel
                    </button>
                    <button
                        type="button"
                        className={variant === 'danger' ? 'btn btn-danger' : 'btn btn-primary'}
                        onClick={onConfirm}
                        disabled={loading}
                    >
                        {loading ? '…' : confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
