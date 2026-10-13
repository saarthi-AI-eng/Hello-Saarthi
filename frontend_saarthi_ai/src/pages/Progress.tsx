import { BarChart3, TrendingUp, Target, Clock, Award, BookOpen, Flame, Calendar, Trophy, MonitorPlay, CheckCircle2, TerminalSquare } from 'lucide-react';
import './Progress.css';

const weeklyData = [
    { day: 'Mon', hours: 2.5 }, { day: 'Tue', hours: 3.0 }, { day: 'Wed', hours: 1.5 },
    { day: 'Thu', hours: 4.0 }, { day: 'Fri', hours: 2.0 }, { day: 'Sat', hours: 5.5 }, { day: 'Sun', hours: 3.5 },
];

const subjectMastery = [
    { subject: 'Digital Signal Processing', progress: 72, color: '#6EAFA4', quizAvg: 78, time: '18h' },
    { subject: 'Machine Learning', progress: 55, color: '#8FA3C2', quizAvg: 82, time: '14h' },
    { subject: 'Data Structures', progress: 88, color: '#B59A63', quizAvg: 91, time: '24h' },
    { subject: 'Pattern Recognition', progress: 35, color: '#9AA8BD', quizAvg: 65, time: '8h' },
    { subject: 'Signals & Systems', progress: 60, color: '#7B93B4', quizAvg: 74, time: '12h' },
];

const recentActivity = [
    { type: 'quiz', title: 'Scored 92% on ML Quiz #4', time: '2 hours ago', icon: Trophy },
    { type: 'video', title: 'Watched: Fourier Transform Deep Dive', time: '5 hours ago', icon: MonitorPlay },
    { type: 'course', title: 'Completed DSP Module 4', time: 'Yesterday', icon: CheckCircle2 },
    { type: 'code', title: 'Solved: Binary Search Problem', time: 'Yesterday', icon: TerminalSquare },
    { type: 'streak', title: '5-Day Study Streak!', time: '2 days ago', icon: Flame },
];

const maxHours = Math.max(...weeklyData.map((d) => d.hours));

export default function ProgressPage() {
    return (
        <div className="progress-page">
            <div className="progress-header animate-fade-in">
                <h1>Learning Analytics</h1>
                <p>Track your progress across all subjects</p>
            </div>

            {/* Stats Row */}
            <div className="progress-stats animate-fade-in delay-100">
                <div className="progress-stat-card"><div className="progress-stat-icon" style={{ background: 'rgba(143, 163, 194, 0.14)', color: '#8FA3C2' }}><BookOpen size={22} /></div><div><span className="progress-stat-val">5</span><span className="progress-stat-lbl">Courses</span></div></div>
                <div className="progress-stat-card"><div className="progress-stat-icon" style={{ background: 'rgba(110, 175, 164, 0.14)', color: '#6EAFA4' }}><Award size={22} /></div><div><span className="progress-stat-val">18</span><span className="progress-stat-lbl">Quizzes</span></div></div>
                <div className="progress-stat-card"><div className="progress-stat-icon" style={{ background: 'rgba(181, 154, 99, 0.14)', color: '#B59A63' }}><Target size={22} /></div><div><span className="progress-stat-val">82%</span><span className="progress-stat-lbl">Avg Score</span></div></div>
                <div className="progress-stat-card"><div className="progress-stat-icon" style={{ background: 'rgba(123, 147, 180, 0.14)', color: '#7B93B4' }}><Clock size={22} /></div><div><span className="progress-stat-val">76h</span><span className="progress-stat-lbl">Study Time</span></div></div>
                <div className="progress-stat-card"><div className="progress-stat-icon" style={{ background: 'rgba(181, 154, 99, 0.14)', color: '#B59A63' }}><Flame size={22} /></div><div><span className="progress-stat-val">5</span><span className="progress-stat-lbl">Day Streak</span></div></div>
            </div>

            <div className="progress-grid">
                {/* Weekly Study Chart */}
                <div className="progress-section animate-fade-in delay-200">
                    <h3><BarChart3 size={18} /> Weekly Study Hours</h3>
                    <div className="progress-chart">
                        {weeklyData.map((d, i) => (
                            <div key={i} className="progress-chart-col">
                                <div className="progress-chart-bar-wrapper">
                                    <div className="progress-chart-bar" style={{ height: `${(d.hours / maxHours) * 100}%` }}>
                                        <span className="progress-chart-value">{d.hours}h</span>
                                    </div>
                                </div>
                                <span className="progress-chart-label">{d.day}</span>
                            </div>
                        ))}
                    </div>
                    <div className="progress-chart-summary">
                        <span><TrendingUp size={14} /> Total: {weeklyData.reduce((s, d) => s + d.hours, 0)}h this week</span>
                    </div>
                </div>

                {/* Recent Activity */}
                <div className="progress-section animate-fade-in delay-300">
                    <h3><Calendar size={18} /> Recent Activity</h3>
                    <div className="progress-activity-list">
                        {recentActivity.map((a, i) => {
                            const Icon = a.icon;
                            return (
                            <div key={i} className="progress-activity-item">
                                <span className="progress-activity-icon"><Icon size={16} /></span>
                                <div className="progress-activity-info">
                                    <span className="progress-activity-title">{a.title}</span>
                                    <span className="progress-activity-time">{a.time}</span>
                                </div>
                            </div>
                        );})}
                    </div>
                </div>
            </div>

            {/* Subject Mastery */}
            <div className="progress-section animate-fade-in delay-400">
                <h3><Target size={18} /> Subject Mastery</h3>
                <div className="progress-mastery-list">
                    {subjectMastery.map((s, i) => (
                        <div key={i} className="progress-mastery-item">
                            <div className="progress-mastery-info">
                                <div className="progress-mastery-color" style={{ background: s.color }} />
                                <span className="progress-mastery-name">{s.subject}</span>
                            </div>
                            <div className="progress-mastery-bar-wrapper">
                                <div className="progress-bar" style={{ flex: 1 }}>
                                    <div className="progress-bar-fill" style={{ width: `${s.progress}%`, background: s.color }} />
                                </div>
                                <span className="progress-mastery-pct">{s.progress}%</span>
                            </div>
                            <div className="progress-mastery-stats">
                                <span>Quiz Avg: {s.quizAvg}%</span>
                                <span>Time: {s.time}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
