import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Clock, Flag, ChevronLeft, ChevronRight, CheckCircle2, XCircle, AlertCircle, GraduationCap, ListChecks } from 'lucide-react';
import {
    api, getAllPages,
    type EnrollmentWithCourseResponse, type QuizAttemptResponse, type QuizDetailResponse, type QuizDifficulty, type QuizResponse,
} from '../lib/api';
import { usePageTitle } from '../lib/usePageTitle';
import './Quiz.css';

const DIFFICULTY: Record<QuizDifficulty, { label: string; bg: string; color: string }> = {
    recall: { label: 'Recall', bg: '#D1FAE5', color: '#059669' },
    application: { label: 'Application', bg: '#FEF3C7', color: '#D97706' },
    analysis: { label: 'Analysis', bg: '#FEE2E2', color: '#DC2626' },
};

function parseOptions(json: string): string[] {
    try {
        const v = JSON.parse(json);
        return Array.isArray(v) ? v.map(String) : [];
    } catch {
        return [];
    }
}

function formatClock(seconds: number): string {
    const s = Math.max(0, seconds);
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/** List of quizzes from the student's courses. */
function QuizList({ onStart }: { onStart: (id: string) => void }) {
    const [quizzes, setQuizzes] = useState<QuizResponse[]>([]);
    const [courseNames, setCourseNames] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        Promise.all([
            getAllPages<QuizResponse>('/quizzes'),
            getAllPages<EnrollmentWithCourseResponse>('/courses/my/enrollments').catch(() => []),
        ])
            .then(([qs, enrollments]) => {
                if (cancelled) return;
                setQuizzes(qs);
                setCourseNames(Object.fromEntries(enrollments.map((e) => [e.courseId, e.course.title])));
            })
            .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load quizzes'); })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, []);

    return (
        <div className="quiz-list-page">
            <div className="quiz-list-header">
                <h1><GraduationCap size={22} /> Exam Practice</h1>
                <p>Quizzes from your courses. Your answers are checked when you submit, with an explanation for each question.</p>
            </div>
            {loading ? (
                <p className="quiz-list-empty">Loading quizzes…</p>
            ) : error ? (
                <p className="quiz-list-empty">{error}</p>
            ) : quizzes.length === 0 ? (
                <div className="quiz-list-empty">
                    <ListChecks size={32} />
                    <p>No quizzes yet. Your teachers' quizzes will appear here.</p>
                </div>
            ) : (
                <div className="quiz-list-grid">
                    {quizzes.map((q) => (
                        <div key={q.id} className="quiz-list-card">
                            <div className="quiz-list-card-top">
                                {q.courseId && courseNames[q.courseId] && <span className="quiz-list-course">{courseNames[q.courseId]}</span>}
                                {q.topic && <span className="badge badge-info">{q.topic}</span>}
                            </div>
                            <h3>{q.title}</h3>
                            {q.description && <p className="quiz-list-desc">{q.description}</p>}
                            <p className="quiz-list-meta">
                                {q.questionCount} questions · {q.durationMinutes} min · pass {Math.round(q.passingScore)}%
                            </p>
                            <div className="quiz-list-card-bottom">
                                <span className="quiz-list-best">
                                    {q.attemptCount > 0 ? `Best ${Math.round(q.bestScore ?? 0)}% · ${q.attemptCount} attempt${q.attemptCount > 1 ? 's' : ''}` : 'Not attempted'}
                                </span>
                                <button className="btn btn-primary btn-sm" disabled={q.questionCount === 0} onClick={() => onStart(q.id)}>
                                    {q.attemptCount > 0 ? 'Retake' : 'Start'}
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

/** One attempt: timer, answers, server-graded review. */
function QuizAttempt({ quizId, onExit }: { quizId: string; onExit: () => void }) {
    const [quiz, setQuiz] = useState<QuizDetailResponse | null>(null);
    const [attemptId, setAttemptId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [currentQ, setCurrentQ] = useState(0);
    const [answers, setAnswers] = useState<(number | null)[]>([]);
    const [flagged, setFlagged] = useState<Set<number>>(new Set());
    const [result, setResult] = useState<QuizAttemptResponse | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [secondsLeft, setSecondsLeft] = useState(0);
    const [round, setRound] = useState(0);
    const submittedRef = useRef(false);

    useEffect(() => {
        let cancelled = false;
        submittedRef.current = false;
        setQuiz(null);
        setResult(null);
        setError(null);
        (async () => {
            try {
                const q = await api.get<QuizDetailResponse>(`/quizzes/${quizId}`);
                const a = await api.post<QuizAttemptResponse>(`/quizzes/${quizId}/attempts`);
                if (cancelled) return;
                setQuiz(q);
                setAttemptId(a.id);
                setAnswers(new Array(q.questions.length).fill(null));
                setFlagged(new Set());
                setCurrentQ(0);
                setSecondsLeft(q.durationMinutes * 60);
            } catch (e) {
                if (!cancelled) setError(e instanceof Error ? e.message : 'Could not start the quiz');
            }
        })();
        return () => { cancelled = true; };
    }, [quizId, round]);

    const submit = useCallback(async () => {
        if (!quiz || !attemptId || submittedRef.current) return;
        submittedRef.current = true;
        setSubmitting(true);
        try {
            const res = await api.post<QuizAttemptResponse>(`/quizzes/${quizId}/attempts/${attemptId}/submit`, {
                answers: quiz.questions.map((q, i) => ({ questionId: q.id, selectedIndex: answers[i] })),
            });
            setResult(res);
            setCurrentQ(0);
        } catch (e) {
            submittedRef.current = false;
            setError(e instanceof Error ? e.message : 'Could not submit');
        } finally {
            setSubmitting(false);
        }
    }, [quiz, attemptId, quizId, answers]);

    // Countdown; submits automatically when time runs out.
    useEffect(() => {
        if (!quiz || result) return;
        if (secondsLeft <= 0) { submit(); return; }
        const t = setTimeout(() => setSecondsLeft((s) => s - 1), 1000);
        return () => clearTimeout(t);
    }, [quiz, result, secondsLeft, submit]);

    if (error && !quiz) {
        return (
            <div className="quiz-list-page">
                <p className="quiz-list-empty">{error}</p>
                <button className="btn btn-outline" onClick={onExit}><ChevronLeft size={16} /> Back to quizzes</button>
            </div>
        );
    }
    if (!quiz) return <div className="quiz-list-page"><p className="quiz-list-empty">Loading quiz…</p></div>;

    const total = quiz.questions.length;
    const question = quiz.questions[currentQ];
    const options = parseOptions(question.optionsJson);
    const answered = answers.filter((a) => a !== null).length;
    const byId = new Map((result?.results ?? []).map((r) => [r.questionId, r]));
    const qResult = byId.get(question.id);
    const submitted = !!result;
    const score = result?.score ?? 0;
    const passed = score >= quiz.passingScore;
    const diff = DIFFICULTY[question.difficulty] ?? DIFFICULTY.recall;

    // Accuracy per topic, shown after submitting.
    const topicStats: Record<string, { right: number; all: number }> = {};
    if (submitted) {
        quiz.questions.forEach((q) => {
            const t = q.topic || 'General';
            topicStats[t] ??= { right: 0, all: 0 };
            topicStats[t].all += 1;
            if (byId.get(q.id)?.isCorrect) topicStats[t].right += 1;
        });
    }

    const toggleFlag = () => {
        const next = new Set(flagged);
        if (next.has(currentQ)) next.delete(currentQ); else next.add(currentQ);
        setFlagged(next);
    };

    return (
        <div className="quiz-page">
            <div className="quiz-header">
                <div className="quiz-header-left">
                    <button className="btn btn-ghost btn-sm" onClick={onExit} aria-label="Back to quizzes"><ChevronLeft size={16} /></button>
                    <h2>{quiz.title}</h2>
                </div>
                <div className={`quiz-header-center ${!submitted && secondsLeft <= 60 ? 'quiz-timer-low' : ''}`}>
                    <Clock size={18} />
                    <span className="quiz-timer">{submitted ? 'Completed' : formatClock(secondsLeft)}</span>
                </div>
                <div className="quiz-header-right">
                    <span>Question {currentQ + 1} of {total}</span>
                    <div className="progress-bar" style={{ width: '120px' }}>
                        <div className="progress-bar-fill" style={{ width: `${((currentQ + 1) / total) * 100}%` }} />
                    </div>
                </div>
            </div>

            {submitted && (
                <div className="quiz-score-banner animate-scale-in">
                    <div className="quiz-score-circle">
                        <span className="quiz-score-value">{result.correctCount ?? 0}/{total}</span>
                        <span className="quiz-score-pct">{Math.round(score)}%</span>
                    </div>
                    <div className="quiz-score-info">
                        <h3>{passed ? 'Passed' : 'Not passed yet'}</h3>
                        <p>You answered {result.correctCount ?? 0} of {total} correctly. Pass mark: {Math.round(quiz.passingScore)}%.</p>
                        <p className="quiz-topic-stats">
                            {Object.entries(topicStats).map(([t, s]) => (
                                <span key={t} className={s.right === s.all ? 'good' : s.right === 0 ? 'weak' : ''}>{t}: {s.right}/{s.all}</span>
                            ))}
                        </p>
                    </div>
                </div>
            )}
            {error && <p className="quiz-error">{error}</p>}

            <div className="quiz-content">
                <div className="quiz-question-area">
                    <div className="quiz-question-card animate-fade-in">
                        <div className="quiz-question-header">
                            <span className="badge badge-primary">Question {currentQ + 1}</span>
                            <span className="badge" style={{ background: diff.bg, color: diff.color }}>{diff.label}</span>
                            {question.topic && <span className="badge badge-info">{question.topic}</span>}
                            {!submitted && (
                                <button className={`quiz-flag-btn ${flagged.has(currentQ) ? 'flagged' : ''}`} onClick={toggleFlag}>
                                    <Flag size={16} /> {flagged.has(currentQ) ? 'Flagged' : 'Flag for review'}
                                </button>
                            )}
                        </div>
                        <p className="quiz-question-text">{question.questionText}</p>

                        <div className="quiz-options">
                            {options.map((opt, i) => {
                                const isSelected = answers[currentQ] === i;
                                const isCorrect = submitted && qResult?.correctIndex === i;
                                const isWrong = submitted && isSelected && qResult?.correctIndex !== i;
                                return (
                                    <button
                                        key={i}
                                        className={`quiz-option ${isSelected ? 'selected' : ''} ${isCorrect ? 'correct' : ''} ${isWrong ? 'wrong' : ''}`}
                                        disabled={submitted}
                                        onClick={() => setAnswers((prev) => prev.map((a, j) => (j === currentQ ? i : a)))}
                                    >
                                        <span className="quiz-option-letter">{String.fromCharCode(65 + i)}</span>
                                        <span className="quiz-option-text">{opt}</span>
                                        {isCorrect && <CheckCircle2 size={18} />}
                                        {isWrong && <XCircle size={18} />}
                                    </button>
                                );
                            })}
                        </div>

                        {submitted && (
                            <div className="quiz-explanation animate-fade-in">
                                <AlertCircle size={18} />
                                <div>
                                    <strong>{qResult?.isCorrect ? 'Correct.' : answers[currentQ] === null ? 'Not answered.' : 'Incorrect.'}</strong>
                                    <p>{qResult?.explanation || 'No explanation was added for this question.'}</p>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                <div className="quiz-nav-sidebar">
                    <h4>Questions</h4>
                    <div className="quiz-nav-grid">
                        {quiz.questions.map((q, i) => {
                            let cls = 'quiz-nav-item';
                            if (i === currentQ) cls += ' current';
                            else if (submitted && byId.get(q.id)?.isCorrect) cls += ' correct';
                            else if (submitted) cls += ' wrong';
                            else if (answers[i] !== null) cls += ' answered';
                            if (flagged.has(i)) cls += ' flagged';
                            return <button key={q.id} className={cls} onClick={() => setCurrentQ(i)}>{i + 1}</button>;
                        })}
                    </div>
                    <div className="quiz-nav-legend">
                        <span><span className="legend-dot current" /> Current</span>
                        <span><span className="legend-dot answered" /> Answered</span>
                        <span><span className="legend-dot flagged" /> Flagged</span>
                    </div>
                </div>
            </div>

            <div className="quiz-bottom-bar">
                <button className="btn btn-ghost" disabled={currentQ === 0} onClick={() => setCurrentQ(currentQ - 1)}>
                    <ChevronLeft size={16} /> Previous
                </button>
                <span className="quiz-bottom-info">{submitted ? `Score ${Math.round(score)}%` : `${answered} of ${total} answered`}</span>
                <div className="quiz-bottom-actions">
                    {!submitted && (
                        <button className="btn btn-success" disabled={submitting} onClick={submit}>
                            {submitting ? 'Submitting…' : 'Submit Quiz'}
                        </button>
                    )}
                    {submitted && <button className="btn btn-outline" onClick={() => setRound((r) => r + 1)}>Retake</button>}
                    {currentQ < total - 1 && (
                        <button className="btn btn-primary" onClick={() => setCurrentQ(currentQ + 1)}>
                            Next <ChevronRight size={16} />
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}

export default function QuizPage() {
    usePageTitle('Exam Practice');
    const [params, setParams] = useSearchParams();
    const navigate = useNavigate();
    const quizId = params.get('id');

    if (quizId) {
        return <QuizAttempt key={quizId} quizId={quizId} onExit={() => (params.get('from') ? navigate(-1) : setParams({}))} />;
    }
    return <QuizList onStart={(id) => setParams({ id })} />;
}
