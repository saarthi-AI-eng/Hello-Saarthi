import { useEffect, useState } from 'react';
import { BarChart3, Download, HelpCircle, Loader2, Target, TriangleAlert, Users } from 'lucide-react';
import { api, apiUrl, authFetch } from '../lib/api';
import './Progress.css';

interface StudentRow {
    id: string; name: string; email: string; attempts: number; quizzesTaken: number; totalQuizzes: number;
    avgScore: number | null; bestScore: number | null; lastActive: string | null;
    status: 'at_risk' | 'on_track' | 'not_started';
}

interface ClassPerformanceResponse {
    courses: { id: string; title: string; code: string }[];
    performance: {
        course: { id: string; title: string; code: string };
        threshold: number;
        summary: { students: number; active: number; atRisk: number; notStarted: number; mean: number | null; median: number | null; attempts: number };
        histogram: { range: string; students: number }[];
        students: StudentRow[];
        topics: { topic: string; correct: number; total: number; accuracy: number }[];
        mostMissed: { question: string; topic: string | null; missed: number; answered: number; missRate: number }[];
    } | null;
}

const pct = (v: number | null) => (v === null ? '—' : `${Math.round(v)}%`);
const STATUS_LABEL: Record<StudentRow['status'], string> = { at_risk: 'At risk', on_track: 'On track', not_started: 'Not started' };

/** Teacher view of one course: score histogram, at-risk students, topic accuracy, most-missed questions, CSV export. */
export default function ClassPerformance() {
    const [courseId, setCourseId] = useState('');
    const [threshold, setThreshold] = useState(50);
    const [data, setData] = useState<ClassPerformanceResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [exporting, setExporting] = useState(false);

    useEffect(() => {
        const t = setTimeout(() => {
            api.get<ClassPerformanceResponse>('/progress/class', { ...(courseId ? { courseId } : {}), threshold })
                .then((d) => {
                    setData(d);
                    setError(null);
                    if (!courseId && d.performance) setCourseId(d.performance.course.id);
                })
                .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load class performance'));
        }, 250);
        return () => clearTimeout(t);
    }, [courseId, threshold]);

    const exportCsv = async () => {
        const perf = data?.performance;
        if (!perf) return;
        setExporting(true);
        try {
            const res = await authFetch(apiUrl(`/progress/class/export?courseId=${perf.course.id}&threshold=${threshold}`));
            if (!res.ok) throw new Error(`Export failed (${res.status})`);
            const url = URL.createObjectURL(await res.blob());
            const a = document.createElement('a');
            a.href = url;
            a.download = `class_report_${perf.course.code || perf.course.id}.csv`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Export failed');
        } finally {
            setExporting(false);
        }
    };

    if (error && !data) return <div className="progress-section" style={{ marginBottom: '1.5rem' }}><p role="alert">{error}</p></div>;
    if (!data) return <div className="progress-section" style={{ marginBottom: '1.5rem' }}><p>Loading class performance…</p></div>;
    const perf = data.performance;
    if (!perf) return null;
    const maxBin = Math.max(1, ...perf.histogram.map((h) => h.students));
    const s = perf.summary;

    return (
        <>
            <div className="progress-section animate-fade-in delay-200" style={{ marginBottom: '1.5rem' }}>
                <div className="progress-section-head">
                    <h3><Users size={18} /> Class Performance</h3>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={exportCsv} disabled={exporting}>
                        {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />} Export CSV
                    </button>
                </div>
                <div className="progress-toolbar">
                    <label>
                        Course
                        <select className="input" value={perf.course.id} onChange={(e) => setCourseId(e.target.value)}>
                            {data.courses.map((c) => <option key={c.id} value={c.id}>{c.title} ({c.code})</option>)}
                        </select>
                    </label>
                    <label>
                        At risk below
                        <input
                            className="input" type="number" min={0} max={100} step={5} style={{ width: '5rem' }}
                            value={threshold}
                            onChange={(e) => setThreshold(Math.min(100, Math.max(0, Number(e.target.value) || 0)))}
                        />
                        %
                    </label>
                    <span className="progress-activity-time">
                        {s.students} enrolled · {s.active} with scores · mean {pct(s.mean)} · median {pct(s.median)} ·{' '}
                        <strong style={{ color: s.atRisk ? '#C26A6A' : undefined }}>{s.atRisk} at risk</strong> · {s.notStarted} not started
                    </span>
                </div>
                {error && <p role="alert" className="progress-activity-time">{error}</p>}

                <div className="progress-grid" style={{ marginBottom: 0 }}>
                    <div>
                        <h4 className="progress-subhead"><BarChart3 size={15} /> Score distribution (students by average %)</h4>
                        <div className="progress-chart progress-chart-dense" style={{ height: 160 }}>
                            {perf.histogram.map((h) => (
                                <div key={h.range} className="progress-chart-col" title={`${h.range}%: ${h.students} student(s)`}>
                                    <div className="progress-chart-bar-wrapper">
                                        {h.students > 0 ? (
                                            <div
                                                className="progress-chart-bar"
                                                style={{
                                                    height: `${(h.students / maxBin) * 100}%`,
                                                    background: parseInt(h.range, 10) < threshold ? '#C26A6A' : undefined,
                                                }}
                                            >
                                                <span className="progress-chart-value">{h.students}</span>
                                            </div>
                                        ) : <div className="progress-chart-empty" />}
                                    </div>
                                    <span className="progress-chart-label">{h.range.split('-')[0]}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div>
                        <h4 className="progress-subhead"><Target size={15} /> Class accuracy by topic</h4>
                        {perf.topics.length === 0 ? (
                            <p className="progress-activity-time">No quiz answers yet.</p>
                        ) : perf.topics.map((t) => (
                            <div key={t.topic} className="progress-mastery-bar-wrapper" style={{ marginBottom: '0.5rem' }}>
                                <span style={{ minWidth: 120, fontSize: '0.8125rem' }}>{t.topic}</span>
                                <div className="progress-bar" style={{ flex: 1 }}>
                                    <div
                                        className="progress-bar-fill"
                                        style={{ width: `${t.accuracy}%`, background: t.accuracy < threshold ? '#C26A6A' : '#6EAFA4' }}
                                    />
                                </div>
                                <span className="progress-mastery-pct">{pct(t.accuracy)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <div className="progress-grid">
                <div className="progress-section animate-fade-in">
                    <h3><TriangleAlert size={18} /> Students</h3>
                    {perf.students.length === 0 ? (
                        <p className="progress-activity-time">No students enrolled yet.</p>
                    ) : (
                        <div className="progress-table-wrap">
                            <table className="progress-table">
                                <thead>
                                    <tr><th>Student</th><th>Quizzes</th><th>Average</th><th>Best</th><th>Last quiz</th><th>Status</th></tr>
                                </thead>
                                <tbody>
                                    {perf.students.map((st) => (
                                        <tr key={st.id}>
                                            <td title={st.email}>{st.name}</td>
                                            <td>{st.quizzesTaken}/{st.totalQuizzes}</td>
                                            <td>{pct(st.avgScore)}</td>
                                            <td>{pct(st.bestScore)}</td>
                                            <td>{st.lastActive ? new Date(st.lastActive).toLocaleDateString() : '—'}</td>
                                            <td><span className={`progress-status ${st.status}`}>{STATUS_LABEL[st.status]}</span></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                <div className="progress-section animate-fade-in">
                    <h3><HelpCircle size={18} /> Most-missed Questions</h3>
                    {perf.mostMissed.length === 0 ? (
                        <p className="progress-activity-time">No wrong answers recorded yet.</p>
                    ) : perf.mostMissed.map((m, i) => (
                        <div key={i} className="progress-missed-item">
                            <div>{m.question}</div>
                            <div className="progress-mastery-stats">
                                <span style={{ color: '#C26A6A', fontWeight: 600 }}>{pct(m.missRate)} missed</span>
                                <span>{m.missed}/{m.answered} answers</span>
                                {m.topic && <span>{m.topic}</span>}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </>
    );
}
