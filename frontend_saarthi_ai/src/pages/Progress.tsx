import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
    Award, BarChart3, BookOpen, Calendar, CheckCircle2, Circle, Code2, Flame, Lightbulb, Lock, Target,
    TerminalSquare, TrendingUp, TriangleAlert, Trophy, Users,
} from 'lucide-react';
import './Progress.css';
import { api } from '../lib/api';
import { useAuthStore } from '../stores/auth.store';
import TeacherAnalytics from './TeacherAnalytics';

interface TopicStat { topic: string; courseId: string; course: string; correct: number; total: number; accuracy: number }
interface WeakTopic extends TopicStat {
    materials: { id: string; title: string; type: string; courseId: string }[];
    retryQuiz: { id: string; title: string } | null;
}
interface CourseProgress {
    id: string; title: string; code: string;
    myAvg: number | null; classMedian: number | null; classmates: number; attempts: number;
    modules: { title: string; covered: boolean }[]; coverage: number | null;
}
interface StudentAnalytics {
    summary: {
        courses: number; quizzesTaken: number; attempts: number; avgScore: number | null; accuracy: number | null;
        codeSolved: number; streakDays: number; activeDays30: number;
    };
    topics: TopicStat[];
    difficulty: { level: string; correct: number; total: number; accuracy: number | null }[];
    weakTopics: WeakTopic[];
    trend: { date: string; avgScore: number | null; attempts: number }[];
    courses: CourseProgress[];
    badges: { id: string; title: string; description: string; earned: boolean }[];
    recent: { type: 'quiz' | 'code'; title: string; at: string }[];
    nextResource: { reason: string; title: string; type: string; id: string | null; courseId: string } | null;
}

const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${Math.round(v)}%`);
const barColor = (v: number) => (v >= 80 ? '#6EAFA4' : v >= 60 ? '#B59A63' : '#C26A6A');

function timeAgo(iso: string): string {
    const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins} min ago`;
    const h = Math.round(mins / 60);
    if (h < 24) return `${h} hour${h > 1 ? 's' : ''} ago`;
    const d = Math.round(h / 24);
    return d === 1 ? 'Yesterday' : `${d} days ago`;
}

export default function ProgressPage() {
    const role = useAuthStore((s) => s.user?.role);
    if (role === 'teacher' || role === 'admin') return <TeacherAnalytics />;
    return <StudentProgress />;
}

function StudentProgress() {
    const [data, setData] = useState<StudentAnalytics | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [range, setRange] = useState<7 | 30>(7);

    useEffect(() => {
        api.get<StudentAnalytics>('/progress/me')
            .then(setData)
            .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load analytics'));
    }, []);

    if (error) return <div className="progress-page"><p role="alert">{error}</p></div>;
    if (!data) return <div className="progress-page"><p>Loading…</p></div>;

    const { summary, topics, difficulty, weakTopics, courses, badges, recent, nextResource } = data;
    const trend = data.trend.slice(-range);
    const stats = [
        { icon: BookOpen, label: 'Courses', val: summary.courses, color: '#8FA3C2' },
        { icon: Award, label: 'Quizzes Taken', val: summary.quizzesTaken, color: '#6EAFA4' },
        { icon: Target, label: 'Avg Score', val: pct(summary.avgScore), color: '#B59A63' },
        { icon: CheckCircle2, label: 'Question Accuracy', val: pct(summary.accuracy), color: '#7B93B4' },
        { icon: Flame, label: 'Day Streak', val: summary.streakDays, color: '#B59A63' },
    ];
    const noQuizzes = summary.attempts === 0;

    return (
        <div className="progress-page">
            <div className="progress-header animate-fade-in">
                <h1>Learning Analytics</h1>
                <p>Your progress from quizzes, Code Lab and study activity</p>
            </div>

            <div className="progress-stats animate-fade-in delay-100">
                {stats.map(({ icon: Icon, label, val, color }) => (
                    <div key={label} className="progress-stat-card">
                        <div className="progress-stat-icon" style={{ background: `${color}24`, color }}><Icon size={22} /></div>
                        <div><span className="progress-stat-val">{val}</span><span className="progress-stat-lbl">{label}</span></div>
                    </div>
                ))}
            </div>

            {nextResource && (
                <div className="progress-next animate-fade-in delay-100">
                    <Lightbulb size={20} />
                    <div>
                        <span className="progress-next-reason">{nextResource.reason}</span>
                        <span className="progress-next-title">Next: {nextResource.title}</span>
                    </div>
                    <Link
                        className="btn btn-primary btn-sm"
                        to={nextResource.type === 'quiz' ? '/quiz' : `/courses/${nextResource.courseId}`}
                    >
                        {nextResource.type === 'quiz' ? 'Practise' : 'Open notes'}
                    </Link>
                </div>
            )}

            {noQuizzes && (
                <div className="progress-section animate-fade-in" style={{ marginBottom: '1.5rem' }}>
                    <p className="progress-activity-time">
                        Take a quiz in <Link to="/quiz">Exam Practice</Link> to see your accuracy per topic, trend and weak topics here.
                    </p>
                </div>
            )}

            <div className="progress-grid">
                {/* Score trend */}
                <div className="progress-section animate-fade-in delay-200">
                    <div className="progress-section-head">
                        <h3><BarChart3 size={18} /> Quiz Score Trend</h3>
                        <div className="progress-toggle" role="group" aria-label="Trend range">
                            {([7, 30] as const).map((r) => (
                                <button key={r} type="button" className={range === r ? 'active' : ''} onClick={() => setRange(r)}>
                                    {r} days
                                </button>
                            ))}
                        </div>
                    </div>
                    <div className={`progress-chart ${range === 30 ? 'progress-chart-dense' : ''}`}>
                        {trend.map((d) => (
                            <div key={d.date} className="progress-chart-col" title={`${d.date}: ${d.attempts} attempt(s)`}>
                                <div className="progress-chart-bar-wrapper">
                                    {d.avgScore !== null ? (
                                        <div className="progress-chart-bar" style={{ height: `${Math.max(d.avgScore, 4)}%` }}>
                                            {range === 7 && <span className="progress-chart-value">{Math.round(d.avgScore)}%</span>}
                                        </div>
                                    ) : (
                                        <div className="progress-chart-empty" />
                                    )}
                                </div>
                                <span className="progress-chart-label">
                                    {range === 7
                                        ? new Date(d.date).toLocaleDateString([], { weekday: 'short' })
                                        : new Date(d.date).getDate()}
                                </span>
                            </div>
                        ))}
                    </div>
                    <div className="progress-chart-summary">
                        <span><TrendingUp size={14} /> {trend.reduce((s, d) => s + d.attempts, 0)} attempts in the last {range} days</span>
                        <span><Calendar size={14} /> Active {summary.activeDays30} of the last 30 days</span>
                    </div>
                </div>

                {/* Recent activity */}
                <div className="progress-section animate-fade-in delay-300">
                    <h3><Calendar size={18} /> Recent Activity</h3>
                    {recent.length === 0 ? (
                        <p className="progress-activity-time">No quiz or Code Lab submissions yet.</p>
                    ) : (
                        <div className="progress-activity-list">
                            {recent.map((a, i) => (
                                <div key={i} className="progress-activity-item">
                                    <span className="progress-activity-icon">{a.type === 'quiz' ? <Trophy size={16} /> : <TerminalSquare size={16} />}</span>
                                    <div className="progress-activity-info">
                                        <span className="progress-activity-title">{a.title}</span>
                                        <span className="progress-activity-time">{timeAgo(a.at)}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Topic accuracy */}
            <div className="progress-section animate-fade-in delay-300" style={{ marginBottom: '1.5rem' }}>
                <h3><Target size={18} /> Accuracy by Topic</h3>
                {topics.length === 0 ? (
                    <p className="progress-activity-time">No answered questions yet.</p>
                ) : (
                    <div className="progress-mastery-list">
                        {topics.map((t) => (
                            <div key={`${t.courseId}-${t.topic}`} className="progress-mastery-item">
                                <div className="progress-mastery-info">
                                    <div className="progress-mastery-color" style={{ background: barColor(t.accuracy) }} />
                                    <span className="progress-mastery-name">{t.topic}</span>
                                </div>
                                <div className="progress-mastery-bar-wrapper">
                                    <div className="progress-bar" style={{ flex: 1 }}>
                                        <div className="progress-bar-fill" style={{ width: `${t.accuracy}%`, background: barColor(t.accuracy) }} />
                                    </div>
                                    <span className="progress-mastery-pct">{pct(t.accuracy)}</span>
                                </div>
                                <div className="progress-mastery-stats">
                                    <span>{t.course}</span>
                                    <span>{t.correct}/{t.total} correct</span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
                {difficulty.some((d) => d.total > 0) && (
                    <div className="progress-difficulty">
                        {difficulty.map((d) => (
                            <div key={d.level} className="progress-difficulty-item">
                                <span className="progress-difficulty-level">{d.level}</span>
                                <span className="progress-difficulty-val">{pct(d.accuracy)}</span>
                                <span className="progress-activity-time">{d.correct}/{d.total} correct</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div className="progress-grid">
                {/* Weak topics */}
                <div className="progress-section animate-fade-in">
                    <h3><TriangleAlert size={18} /> Weak Topics</h3>
                    {weakTopics.length === 0 ? (
                        <p className="progress-activity-time">
                            {noQuizzes ? 'Weak topics appear after your first quiz.' : 'No topic below 70%. Keep it up!'}
                        </p>
                    ) : (
                        <div className="progress-weak-list">
                            {weakTopics.map((w) => (
                                <div key={`${w.courseId}-${w.topic}`} className="progress-weak-item">
                                    <div className="progress-weak-head">
                                        <span className="progress-mastery-name">{w.topic}</span>
                                        <span className="progress-weak-pct">{pct(w.accuracy)}</span>
                                    </div>
                                    <div className="progress-weak-links">
                                        {w.materials.map((m) => (
                                            <Link key={m.id} to={`/courses/${m.courseId}`} className="progress-weak-link">
                                                <BookOpen size={13} /> {m.title}
                                            </Link>
                                        ))}
                                        {w.retryQuiz && (
                                            <Link to="/quiz" className="progress-weak-link"><Award size={13} /> Retry {w.retryQuiz.title}</Link>
                                        )}
                                        {w.materials.length === 0 && !w.retryQuiz && (
                                            <span className="progress-activity-time">Ask the AI Tutor about {w.topic}.</span>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Badges */}
                <div className="progress-section animate-fade-in">
                    <h3><Trophy size={18} /> Badges</h3>
                    <div className="progress-badges">
                        {badges.map((b) => (
                            <div key={b.id} className={`progress-badge ${b.earned ? 'earned' : ''}`} title={b.description}>
                                <span className="progress-badge-icon">{b.earned ? <Award size={20} /> : <Lock size={18} />}</span>
                                <span className="progress-badge-title">{b.title}</span>
                                <span className="progress-badge-desc">{b.description}</span>
                            </div>
                        ))}
                    </div>
                    <p className="progress-activity-time" style={{ marginTop: '0.75rem' }}>
                        <Code2 size={13} /> {summary.codeSolved} Code Lab problem{summary.codeSolved === 1 ? '' : 's'} solved
                    </p>
                </div>
            </div>

            {/* Syllabus coverage and class comparison */}
            <div className="progress-section animate-fade-in">
                <h3><BookOpen size={18} /> Syllabus Coverage</h3>
                {courses.length === 0 ? (
                    <p className="progress-activity-time">Join a course to track coverage.</p>
                ) : (
                    <div className="progress-coverage-list">
                        {courses.map((c) => (
                            <div key={c.id} className="progress-coverage-item">
                                <div className="progress-coverage-head">
                                    <Link to={`/courses/${c.id}`} className="progress-mastery-name">{c.title} <small>({c.code})</small></Link>
                                    <span className="progress-mastery-pct">{pct(c.coverage)}</span>
                                </div>
                                <div className="progress-bar">
                                    <div className="progress-bar-fill" style={{ width: `${c.coverage ?? 0}%` }} />
                                </div>
                                <div className="progress-modules">
                                    {c.modules.map((m) => (
                                        <span key={m.title} className={`progress-module ${m.covered ? 'covered' : 'uncovered'}`}>
                                            {m.covered ? <CheckCircle2 size={12} /> : <Circle size={12} />} {m.title}
                                        </span>
                                    ))}
                                    {c.modules.length === 0 && <span className="progress-activity-time">No modules yet.</span>}
                                </div>
                                <div className="progress-mastery-stats">
                                    <span><Target size={12} /> Your average: {pct(c.myAvg)}</span>
                                    <span><Users size={12} /> Class median: {pct(c.classMedian)} ({c.classmates} student{c.classmates === 1 ? '' : 's'} with scores)</span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
