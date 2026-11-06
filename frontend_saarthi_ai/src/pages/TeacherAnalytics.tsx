import { useEffect, useState } from 'react';
import { BookOpen, Target, TriangleAlert, Users, Award } from 'lucide-react';
import { api } from '../lib/api';
import './Progress.css';

interface CourseStat {
    id: string;
    title: string;
    code: string;
    enrollments: number;
    quizAttempts: number;
    avgQuizScore: number | null;
    quizzes: { title: string; attempts: number; avgScore: number | null; passingScore: number }[];
}

interface WeakTopic {
    topic: string;
    course: string;
    avgPercent: number;
    samples: number;
    source: 'assignment' | 'quiz';
}

interface TeacherAnalyticsResponse {
    summary: { courses: number; students: number; quizAttempts: number; avgQuizScore: number | null };
    courses: CourseStat[];
    weakTopics: WeakTopic[];
}

const pct = (v: number | null) => (v === null ? '—' : `${Math.round(v)}%`);

export default function TeacherAnalytics() {
    const [data, setData] = useState<TeacherAnalyticsResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        api.get<TeacherAnalyticsResponse>('/teacher/analytics')
            .then(setData)
            .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load analytics'));
    }, []);

    if (error) return <div className="progress-page"><p role="alert">{error}</p></div>;
    if (!data) return <div className="progress-page"><p>Loading…</p></div>;

    const { summary, courses, weakTopics } = data;
    const stats = [
        { icon: BookOpen, label: 'Courses', val: summary.courses },
        { icon: Users, label: 'Students', val: summary.students },
        { icon: Award, label: 'Quiz Attempts', val: summary.quizAttempts },
        { icon: Target, label: 'Avg Quiz Score', val: pct(summary.avgQuizScore) },
    ];

    return (
        <div className="progress-page">
            <div className="progress-header animate-fade-in">
                <h1>Class Analytics</h1>
                <p>Enrollments, quiz performance and weak topics across your courses</p>
            </div>

            <div className="progress-stats animate-fade-in delay-100">
                {stats.map(({ icon: Icon, label, val }) => (
                    <div key={label} className="progress-stat-card">
                        <div className="progress-stat-icon" style={{ background: 'rgba(143, 163, 194, 0.14)', color: '#8FA3C2' }}><Icon size={22} /></div>
                        <div><span className="progress-stat-val">{val}</span><span className="progress-stat-lbl">{label}</span></div>
                    </div>
                ))}
            </div>

            <div className="progress-section animate-fade-in delay-200" style={{ marginBottom: '1.5rem' }}>
                <h3><TriangleAlert size={18} /> Weak Topics</h3>
                {weakTopics.length === 0 ? (
                    <p className="progress-activity-time">No graded assignments or quiz attempts yet — weak topics appear once students have scores.</p>
                ) : (
                    <div className="progress-mastery-list">
                        {weakTopics.map((w, i) => (
                            <div key={i} className="progress-mastery-item">
                                <div className="progress-mastery-info">
                                    <span className="progress-mastery-name">{w.topic}</span>
                                </div>
                                <div className="progress-mastery-bar-wrapper">
                                    <div className="progress-bar" style={{ flex: 1 }}>
                                        <div className="progress-bar-fill" style={{ width: `${Math.min(w.avgPercent, 100)}%`, background: w.avgPercent < 50 ? '#C26A6A' : '#B59A63' }} />
                                    </div>
                                    <span className="progress-mastery-pct">{pct(w.avgPercent)}</span>
                                </div>
                                <div className="progress-mastery-stats">
                                    <span>{w.course}</span>
                                    <span>{w.samples} {w.source === 'quiz' ? 'attempts' : 'grades'}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div className="progress-section animate-fade-in delay-300">
                <h3><BookOpen size={18} /> Courses</h3>
                {courses.length === 0 ? (
                    <p className="progress-activity-time">You haven't created any courses yet.</p>
                ) : (
                    <div className="progress-mastery-list">
                        {courses.map((c) => (
                            <div key={c.id} className="progress-mastery-item">
                                <div className="progress-mastery-info">
                                    <span className="progress-mastery-name">{c.title} <small>({c.code})</small></span>
                                </div>
                                <div className="progress-mastery-bar-wrapper">
                                    <span className="progress-mastery-pct">{c.enrollments}</span>
                                    <span>enrolled</span>
                                </div>
                                <div className="progress-mastery-stats">
                                    <span>Quiz avg: {pct(c.avgQuizScore)} ({c.quizAttempts})</span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
