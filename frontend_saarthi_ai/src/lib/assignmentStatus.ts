/** A date-only due date (older assignments) counts until the end of that day. */
export function dueTime(dueDate: string): number {
    const iso = /^\d{4}-\d{2}-\d{2}$/.test(dueDate) ? `${dueDate}T23:59:59` : dueDate;
    const t = new Date(iso).getTime();
    return Number.isNaN(t) ? Infinity : t;
}

/** "Nov 10, 2026, 5:00 PM", or the date alone for older date-only due dates. */
export function formatDue(dueDate: string): string {
    if (/^\d{4}-\d{2}-\d{2}$/.test(dueDate)) {
        return new Date(`${dueDate}T00:00:00`).toLocaleDateString(undefined, { dateStyle: 'medium' });
    }
    const d = new Date(dueDate);
    return Number.isNaN(d.getTime()) ? dueDate : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

/** Value for an <input type="datetime-local"> in the user's time zone. */
export function toDateTimeLocal(dueDate: string): string {
    if (!dueDate) return '';
    const d = new Date(dueTime(dueDate));
    if (Number.isNaN(d.getTime())) return '';
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** No more work accepted: hard deadline and the due time has passed. */
export function isClosed(dueDate: string, hardDeadline: boolean | undefined): boolean {
    return !!hardDeadline && Date.now() > dueTime(dueDate);
}

/** Files are stored as a JSON list; older submissions hold a single URL. */
export function parseFiles(attachmentUrl: string | null | undefined): string[] {
    if (!attachmentUrl) return [];
    try {
        const parsed = JSON.parse(attachmentUrl);
        if (Array.isArray(parsed)) return parsed.filter((u): u is string => typeof u === 'string');
    } catch { /* a single plain URL */ }
    return [attachmentUrl];
}

/** Status label like Google Classroom: Assigned, Missing, Turned in, Done late, Graded. */
export function statusLabel(status: string, submittedAt: string | null | undefined, dueDate: string, grade: number | null | undefined, points: number) {
    if (status === 'graded' && grade != null) return { text: `Graded ${grade}/${points}`, tone: 'graded' };
    if (status === 'submitted' || submittedAt) {
        const late = submittedAt && new Date(submittedAt).getTime() > dueTime(dueDate);
        return { text: late ? 'Done late' : 'Turned in', tone: 'submitted' };
    }
    return Date.now() > dueTime(dueDate) ? { text: 'Missing', tone: 'missing' } : { text: 'Assigned', tone: 'assigned' };
}
