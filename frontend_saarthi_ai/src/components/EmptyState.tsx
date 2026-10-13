import './EmptyState.css';

interface EmptyStateProps {
    icon: React.ReactNode;
    title: string;
    description?: string;
    action?: React.ReactNode;
    className?: string;
}

export default function EmptyState({ icon, title, description, action, className = '' }: EmptyStateProps) {
    return (
        <div className={`empty-state ${className}`.trim()} role="status" aria-label={title}>
            <div className="empty-state-icon">{icon}</div>
            <h3 className="empty-state-title">{title}</h3>
            {description && <p className="empty-state-desc">{description}</p>}
            {action && <div className="empty-state-action">{action}</div>}
        </div>
    );
}
