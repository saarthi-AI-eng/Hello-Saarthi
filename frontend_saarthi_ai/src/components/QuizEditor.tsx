import { useState } from 'react';
import { ListChecks, Plus, Trash2, X } from 'lucide-react';
import { api, type QuizDetailResponse, type QuizDifficulty } from '../lib/api';
import { useToast } from './Toast';

interface DraftQuestion {
    questionText: string;
    options: string[];
    correctIndex: number;
    topic: string;
    difficulty: QuizDifficulty;
    explanation: string;
}

interface Props {
    courseId: string;
    topics: string[];
    onClose: () => void;
    onCreated: (quiz: QuizDetailResponse) => void;
}

const emptyQuestion = (topic: string): DraftQuestion => ({
    questionText: '', options: ['', '', '', ''], correctIndex: 0, topic, difficulty: 'recall', explanation: '',
});

/** Teacher form: a quiz with multiple-choice questions, saved in one request. */
export default function QuizEditor({ courseId, topics, onClose, onCreated }: Props) {
    const toast = useToast();
    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [topic, setTopic] = useState(topics[0] ?? '');
    const [duration, setDuration] = useState(15);
    const [passing, setPassing] = useState(60);
    const [questions, setQuestions] = useState<DraftQuestion[]>([emptyQuestion('')]);
    const [error, setError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);

    const update = (i: number, change: Partial<DraftQuestion>) =>
        setQuestions((prev) => prev.map((q, j) => (j === i ? { ...q, ...change } : q)));

    const save = async () => {
        setError(null);
        if (!title.trim()) { setError('Give the quiz a title.'); return; }
        for (const [i, q] of questions.entries()) {
            const filled = q.options.filter((o) => o.trim());
            if (!q.questionText.trim()) { setError(`Question ${i + 1}: write the question.`); return; }
            if (filled.length < 2) { setError(`Question ${i + 1}: give at least two options.`); return; }
            if (!q.options[q.correctIndex]?.trim()) { setError(`Question ${i + 1}: the correct answer is empty.`); return; }
        }
        setSaving(true);
        try {
            const created = await api.post<QuizDetailResponse>('/quizzes', {
                courseId: Number(courseId),
                title: title.trim(),
                description: description.trim() || undefined,
                durationMinutes: duration,
                passingScore: passing,
                topic: topic || undefined,
                questions: questions.map((q, i) => {
                    // Drop empty options; keep the correct one's position among the rest.
                    const kept = q.options.map((o, idx) => ({ o: o.trim(), idx })).filter((x) => x.o);
                    return {
                        questionText: q.questionText.trim(),
                        optionsJson: JSON.stringify(kept.map((x) => x.o)),
                        correctIndex: kept.findIndex((x) => x.idx === q.correctIndex),
                        sortOrder: i,
                        topic: q.topic.trim() || undefined,
                        difficulty: q.difficulty,
                        explanation: q.explanation.trim() || undefined,
                    };
                }),
            });
            toast.showToast(`Quiz "${created.title}" posted`);
            onCreated(created);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Could not save the quiz');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="cd-modal-overlay" onClick={onClose}>
            <div className="cd-modal cd-modal-wide cd-quiz-editor animate-scale-in" role="dialog" aria-modal="true" aria-labelledby="cd-quiz-editor-title" onClick={(e) => e.stopPropagation()}>
                <div className="cd-modal-header">
                    <h2 id="cd-quiz-editor-title"><ListChecks size={18} /> New quiz</h2>
                    <button className="cd-modal-close" onClick={onClose} aria-label="Close"><X size={20} /></button>
                </div>
                <div className="cd-modal-body">
                    <div className="cd-modal-field">
                        <label>Title *</label>
                        <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Sampling and aliasing" />
                    </div>
                    <div className="cd-modal-field">
                        <label>Instructions</label>
                        <textarea className="input" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
                    </div>
                    <div className="cd-modal-row">
                        <div className="cd-modal-field">
                            <label>Topic</label>
                            <select className="input" value={topic} onChange={(e) => setTopic(e.target.value)}>
                                <option value="">No topic</option>
                                {topics.map((t) => <option key={t} value={t}>{t}</option>)}
                            </select>
                        </div>
                        <div className="cd-modal-field">
                            <label>Time (minutes)</label>
                            <input className="input" type="number" min={1} max={300} value={duration} onChange={(e) => setDuration(Math.max(1, parseInt(e.target.value) || 1))} />
                        </div>
                        <div className="cd-modal-field">
                            <label>Pass mark (%)</label>
                            <input className="input" type="number" min={0} max={100} value={passing} onChange={(e) => setPassing(Math.min(100, Math.max(0, parseInt(e.target.value) || 0)))} />
                        </div>
                    </div>

                    {questions.map((q, i) => (
                        <fieldset key={i} className="cd-quiz-question">
                            <legend>Question {i + 1}</legend>
                            {questions.length > 1 && (
                                <button type="button" className="btn-icon cd-quiz-question-remove" aria-label={`Remove question ${i + 1}`} onClick={() => setQuestions((prev) => prev.filter((_, j) => j !== i))}>
                                    <Trash2 size={15} />
                                </button>
                            )}
                            <textarea className="input" rows={2} placeholder="Question" value={q.questionText} onChange={(e) => update(i, { questionText: e.target.value })} />
                            <div className="cd-quiz-options">
                                {q.options.map((opt, k) => (
                                    <label key={k} className="cd-quiz-option">
                                        <input type="radio" name={`correct-${i}`} checked={q.correctIndex === k} onChange={() => update(i, { correctIndex: k })} aria-label={`Option ${String.fromCharCode(65 + k)} is correct`} />
                                        <input className="input" placeholder={`Option ${String.fromCharCode(65 + k)}`} value={opt} onChange={(e) => update(i, { options: q.options.map((o, j) => (j === k ? e.target.value : o)) })} />
                                    </label>
                                ))}
                            </div>
                            <p className="cd-quiz-hint">Select the circle next to the correct answer. Empty options are left out.</p>
                            <div className="cd-modal-row">
                                <div className="cd-modal-field">
                                    <label>Concept</label>
                                    <input className="input" placeholder="e.g. Nyquist rate" value={q.topic} onChange={(e) => update(i, { topic: e.target.value })} />
                                </div>
                                <div className="cd-modal-field">
                                    <label>Level</label>
                                    <select className="input" value={q.difficulty} onChange={(e) => update(i, { difficulty: e.target.value as QuizDifficulty })}>
                                        <option value="recall">Recall</option>
                                        <option value="application">Application</option>
                                        <option value="analysis">Analysis</option>
                                    </select>
                                </div>
                            </div>
                            <div className="cd-modal-field">
                                <label>Explanation (shown after submitting)</label>
                                <textarea className="input" rows={2} value={q.explanation} onChange={(e) => update(i, { explanation: e.target.value })} />
                            </div>
                        </fieldset>
                    ))}
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => setQuestions((prev) => [...prev, emptyQuestion(prev[prev.length - 1]?.topic ?? '')])}>
                        <Plus size={14} /> Add question
                    </button>
                    {error && <p className="cd-assignment-error">{error}</p>}
                </div>
                <div className="cd-modal-footer">
                    <button className="btn btn-outline" onClick={onClose}>Cancel</button>
                    <button className="btn btn-primary" disabled={saving} onClick={save}>{saving ? 'Posting…' : `Post quiz (${questions.length})`}</button>
                </div>
            </div>
        </div>
    );
}
