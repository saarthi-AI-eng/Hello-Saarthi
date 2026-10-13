import { useEffect, useState } from 'react';
import {
    BookOpen, ClipboardList, BarChart3, Clock, Flame,
    ChevronRight, CalendarDays, Loader2, RefreshCw,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/auth.store';
import { api, type ProgressResponse, type EnrollmentWithCourseResponse, type PaginatedResponse, type CourseResponse } from '../lib/api';
import { usePageTitle } from '../lib/usePageTitle';
import EmptyState from '../components/EmptyState';
import './Dashboard.css';


function getUrgencyInfo(urgency: string) {
    switch (urgency) {
        case 'high': return { color: '#C86F7A', bg: 'rgba(200, 111, 122, 0.14)', label: 'Due Soon' };
        case 'medium': return { color: '#B59A63', bg: 'rgba(181, 154, 99, 0.14)', label: 'This Week' };
        case 'low': return { color: '#5FA89C', bg: 'rgba(95, 168, 156, 0.14)', label: 'Upcoming' };
        default: return { color: '#94A3B8', bg: 'rgba(148, 163, 184, 0.14)', label: '' };
    }
}

interface StudyPlanDay { day: string; sessions: string[]; totalHours: number; }
interface StudyPlan { weekPlan: StudyPlanDay[]; summary: string; priorityTopics: string[]; generatedAt: string; }

export default function DashboardPage() {
    usePageTitle('Dashboard');
    const { user } = useAuthStore();
    const navigate = useNavigate();
    const [progress, setProgress] = useState<ProgressResponse | null>(null);
    const [continueCourses, setContinueCourses] = useState<EnrollmentWithCourseResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [studyPlan, setStudyPlan] = useState<StudyPlan | null>(null);
    const [planLoading, setPlanLoading] = useState(false);
    const [planExpanded, setPlanExpanded] = useState(false);
    const [totalCourses, setTotalCourses] = useState(0);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            setLoading(true);
            setError(null);
            try {
                const isInst = user?.role === 'admin' || user?.role === 'teacher';
                const progressPromise = api.get<ProgressResponse>('/users/me/progress');
                
                let coursesList: EnrollmentWithCourseResponse[] = [];
                let tCourses = 0;
                
                if (isInst) {
                    const coursesRes = await api.get<PaginatedResponse<CourseResponse>>('/courses', { limit: 5, offset: 0 });
                    tCourses = coursesRes.total || coursesRes.items?.length || 0;
                    coursesList = (coursesRes.items || []).map(c => ({
                        id: c.id,
                        courseId: c.id,
                        progressPercent: 0,
                        course: c
                    } as EnrollmentWithCourseResponse));
                } else {
                    const enrollmentsRes = await api.get<PaginatedResponse<EnrollmentWithCourseResponse>>('/courses/my/enrollments', { limit: 5, offset: 0 });
                    tCourses = enrollmentsRes.total || enrollmentsRes.items?.length || 0;
                    coursesList = enrollmentsRes.items || [];
                }
                
                const progressRes = await progressPromise;

                if (!cancelled) {
                    setProgress(progressRes);
                    setContinueCourses(coursesList);
                    setTotalCourses(tCourses);
                }
            } catch (e) {
                if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load dashboard');
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [user?.role]);

    const generateStudyPlan = async () => {
        setPlanLoading(true);
        try {
            const courses = continueCourses.map((e) => ({
                title: e.course.title,
                code: e.course.code,
                progressPercent: e.progressPercent,
            }));
            const plan = await api.post<StudyPlan>('/chat/study-plan', {
                courses,
                deadlines: [],
                recentQuizScores: [],
                hoursPerDay: 3,
            });
            setStudyPlan(plan);
            setPlanExpanded(true);
        } catch {
            // silently fail — don't break the dashboard
        } finally {
            setPlanLoading(false);
        }
    };

    const isInstructor = user?.role === 'admin' || user?.role === 'teacher';

    const statsCards = progress
        ? [
            { label: isInstructor ? 'Courses Created' : 'Courses Enrolled', value: isInstructor ? String(totalCourses) : String(progress.coursesEnrolled), icon: BookOpen, color: '#0F766E', bg: 'rgba(15, 118, 110, 0.1)', change: '' },
            { label: isInstructor ? 'Pending Grades' : 'Pending Assignments', value: isInstructor ? '–' : String(progress.pendingAssignments), icon: ClipboardList, color: '#9AA8BD', bg: 'rgba(154, 168, 189, 0.12)', change: (!isInstructor && progress.pendingAssignments > 0) ? 'Due' : '' },
            { label: 'Avg Quiz Score', value: `${progress.avgQuizScorePercent}%`, icon: BarChart3, color: '#0F766E', bg: 'rgba(15, 118, 110, 0.1)', change: '' },
            { label: 'Study Time', value: `${progress.studyTimeHours}h`, icon: Clock, color: '#9AA8BD', bg: 'rgba(154, 168, 189, 0.12)', change: 'Total' },
        ]
        : [
            { label: isInstructor ? 'Courses Created' : 'Courses Enrolled', value: '–', icon: BookOpen, color: '#0F766E', bg: 'rgba(15, 118, 110, 0.1)', change: '' },
            { label: isInstructor ? 'Pending Grades' : 'Pending Assignments', value: '–', icon: ClipboardList, color: '#9AA8BD', bg: 'rgba(154, 168, 189, 0.12)', change: '' },
            { label: 'Avg Quiz Score', value: '–', icon: BarChart3, color: '#0F766E', bg: 'rgba(15, 118, 110, 0.1)', change: '' },
            { label: 'Study Time', value: '–', icon: Clock, color: '#9AA8BD', bg: 'rgba(154, 168, 189, 0.12)', change: '' },
        ];

    return (
        <div className="dashboard">
            {error && (
                <div className="dash-error" role="alert">
                    {error}
                </div>
            )}
            {/* Welcome Header */}
            <div className="dash-welcome animate-fade-in">
                <div>
                    <h1 className="dash-welcome-title">Welcome back, {user?.name || 'Student'}</h1>
                    <p className="dash-welcome-sub">Here's your learning overview for today</p>
                </div>
                <div className="dash-streak-card">
                    <Flame size={20} className="dash-streak-icon" />
                    <div>
                        <span className="dash-streak-value">{progress ? `${progress.streakDays} Day Streak` : '–'}</span>
                        <span className="dash-streak-label">{progress?.streakDays ? 'Current streak' : 'Start studying to build a streak'}</span>
                    </div>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="dash-stats animate-fade-in delay-100">
                {statsCards.map((stat, i) => {
                    const Icon = stat.icon;
                    return (
                        <div key={i} className="dash-stat-card">
                            <div className="dash-stat-icon" style={{ background: stat.bg, color: stat.color }}>
                                <Icon size={24} />
                            </div>
                            <div className="dash-stat-info">
                                {loading ? (
                                    <div className="skeleton dash-stat-skeleton-value" />
                                ) : (
                                    <span className="dash-stat-value">{stat.value}</span>
                                )}
                                <span className="dash-stat-label">{stat.label}</span>
                                {stat.change && <span className="dash-stat-change">{stat.change}</span>}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Content Grid */}
            <div className="dash-grid">
                {/* Continue Learning */}
                <div className="dash-section animate-fade-in delay-200">
                    <div className="dash-section-header">
                        <h2>{isInstructor ? 'Your Courses' : 'Continue Learning'}</h2>
                        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/courses')}>
                            View All <ChevronRight size={14} />
                        </button>
                    </div>
                    <div className="dash-courses">
                        {loading ? (
                            Array.from({ length: 3 }).map((_, i) => (
                                <div key={i} className="dash-course-card dash-course-skeleton">
                                    <div className="skeleton dash-course-skeleton-thumb" />
                                    <div className="dash-course-info">
                                        <div className="skeleton dash-course-skeleton-title" />
                                        <div className="skeleton dash-course-skeleton-code" />
                                        <div className="skeleton dash-course-skeleton-bar" />
                                    </div>
                                    <div className="skeleton dash-course-skeleton-btn" />
                                </div>
                            ))
                        ) : continueCourses.length === 0 ? (
                            <EmptyState
                                icon={<BookOpen size={28} />}
                                title={isInstructor ? "No courses yet" : "No enrollments yet"}
                                description={isInstructor ? "Create a course to get started." : "Enroll in a course to continue your learning."}
                                action={
                                    <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate('/courses')}>
                                        {isInstructor ? "Manage courses" : "Browse courses"}
                                    </button>
                                }
                            />
                        ) : (
                            continueCourses.map((e) => (
                                <div key={e.id} className="dash-course-card" onClick={() => navigate(`/courses/${e.courseId}`)}>
                                    <div className="dash-course-thumb">{e.course.thumbnailEmoji || '📚'}</div>
                                    <div className="dash-course-info">
                                        <h4>{e.course.title}</h4>
                                        <span className="dash-course-code">{e.course.code}</span>
                                        {!isInstructor && (
                                            <>
                                                <div className="progress-bar" style={{ marginTop: '0.5rem' }}>
                                                    <div className="progress-bar-fill" style={{ width: `${e.progressPercent}%` }} />
                                                </div>
                                                <div className="dash-course-meta">
                                                    <span>{e.progressPercent}% complete</span>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                    <button className="btn btn-primary btn-sm" onClick={(ev) => { ev.stopPropagation(); navigate(`/courses/${e.courseId}`); }}>
                                        {isInstructor ? 'Manage' : 'Resume'}
                                    </button>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Deadlines */}
                <div className="dash-section animate-fade-in delay-300">
                    <div className="dash-section-header">
                        <h2>Upcoming Deadlines</h2>
                    </div>
                    <div className="dash-deadlines">
                        <EmptyState
                            icon={<CalendarDays size={28} />}
                            title="No upcoming deadlines"
                            description="Deadlines from your enrolled courses will appear here."
                        />
                    </div>
                </div>
            </div>

            {/* Study Plan */}
            <div className="dash-section dash-study-plan animate-fade-in delay-350">
                <div className="dash-section-header">
                    <h2><CalendarDays size={20} style={{ color: 'var(--accent)' }} /> Study Plan</h2>
                    <button
                        className="btn btn-ghost btn-sm"
                        onClick={generateStudyPlan}
                        disabled={planLoading}
                    >
                        {planLoading
                            ? <><Loader2 size={14} className="animate-spin" /> Generating...</>
                            : studyPlan
                                ? <><RefreshCw size={14} /> Regenerate</>
                                : <><CalendarDays size={14} /> Generate Plan</>
                        }
                    </button>
                </div>

                {!studyPlan && !planLoading && (
                    <div className="dash-plan-empty">
                        <CalendarDays size={32} strokeWidth={1.2} />
                        <p>Get a personalized 7-day study schedule based on your courses, deadlines, and quiz performance.</p>
                        <button className="btn btn-primary btn-sm" onClick={generateStudyPlan}>
                            <CalendarDays size={14} /> Generate My Study Plan
                        </button>
                    </div>
                )}

                {planLoading && (
                    <div className="dash-plan-loading">
                        <Loader2 size={20} className="animate-spin" />
                        <span>Analyzing your progress and generating a personalized plan...</span>
                    </div>
                )}

                {studyPlan && !planLoading && (
                    <>
                        {studyPlan.priorityTopics.length > 0 && (
                            <div className="dash-plan-priorities">
                                <span className="dash-plan-priority-label">Priority topics:</span>
                                {studyPlan.priorityTopics.map((t, i) => (
                                    <span key={i} className="badge badge-warning">{t}</span>
                                ))}
                            </div>
                        )}
                        <div className="dash-plan-days">
                            {(planExpanded ? studyPlan.weekPlan : studyPlan.weekPlan.slice(0, 3)).map((day) => (
                                <div key={day.day} className="dash-plan-day">
                                    <div className="dash-plan-day-header">
                                        <span className="dash-plan-day-name">{day.day}</span>
                                        <span className="dash-plan-day-hours">{day.totalHours}h</span>
                                    </div>
                                    <ul className="dash-plan-sessions">
                                        {day.sessions.map((s, i) => (
                                            <li key={i}>{s}</li>
                                        ))}
                                    </ul>
                                </div>
                            ))}
                        </div>
                        {studyPlan.weekPlan.length > 3 && (
                            <button className="btn btn-ghost btn-sm dash-plan-toggle" onClick={() => setPlanExpanded((p) => !p)}>
                                {planExpanded ? 'Show less' : `Show all ${studyPlan.weekPlan.length} days`} <ChevronRight size={14} style={{ transform: planExpanded ? 'rotate(270deg)' : 'rotate(90deg)', transition: 'transform 0.2s' }} />
                            </button>
                        )}
                        {studyPlan.summary && (
                            <p className="dash-plan-summary">{studyPlan.summary}</p>
                        )}
                    </>
                )}
            </div>

            {/* Study Plan */}

        </div>
    );
}
