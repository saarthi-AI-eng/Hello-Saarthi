import { useEffect, useState } from 'react';
import { BookOpenCheck, ChevronDown, ChevronUp, Loader2, Send } from 'lucide-react';
import { api } from '../lib/api';
import { usePageTitle } from '../lib/usePageTitle';
import { renderAnswer } from '../lib/renderAnswer';
import './AskNotes.css';

interface KBSource {
    n: number;
    sourceFile?: string | null;
    page?: number | string | null;
    topic?: string | null;
    sourceType?: string | null;
    score: number;
    text: string;
}

interface KBAnswer {
    question: string;
    answer: string;
    sources: KBSource[];
}

const EXAMPLES = [
    'How does the FFT reduce the number of computations?',
    'What is a perceptron?',
    'What is a non-linear transformation of a random variable?',
];

/** "folder/sub/File Name.pdf" -> "File Name.pdf" */
function shortName(path?: string | null): string {
    return (path ?? 'Notes').split('/').pop() || 'Notes';
}

export default function AskNotesPage() {
    usePageTitle('Ask the Notes');
    const [question, setQuestion] = useState('');
    const [asking, setAsking] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<KBAnswer | null>(null);
    const [openSource, setOpenSource] = useState<number | null>(null);
    const [ready, setReady] = useState<{ ready: boolean; chunks: number; message?: string } | null>(null);

    useEffect(() => {
        api.get<{ ready: boolean; chunks: number; message?: string }>('/kb/status')
            .then(setReady)
            .catch(() => setReady(null));
    }, []);

    const ask = async (q: string) => {
        const text = q.trim();
        if (text.length < 2 || asking) return;
        setAsking(true);
        setError(null);
        setOpenSource(null);
        try {
            const r = await api.post<Omit<KBAnswer, 'question'>>('/kb/ask', { question: text, topK: 5 });
            setResult({ question: text, ...r });
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Could not get an answer');
        } finally {
            setAsking(false);
        }
    };

    return (
        <div className="an-page">
            <div className="an-header">
                <h1><BookOpenCheck size={22} /> Ask the Notes</h1>
                <p>
                    Answers come only from the course knowledge base{ready?.ready ? ` (${ready.chunks} sections of lecture notes)` : ''},
                    with the source of each fact.
                </p>
                {ready && !ready.ready && <p className="an-error">{ready.message}</p>}
            </div>

            <form className="an-ask" onSubmit={(e) => { e.preventDefault(); ask(question); }}>
                <textarea
                    className="input"
                    rows={2}
                    placeholder="Ask a question about the lecture notes…"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(question); } }}
                    disabled={asking}
                />
                <button type="submit" className="btn btn-primary" disabled={asking || question.trim().length < 2}>
                    {asking ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />} {asking ? 'Searching…' : 'Ask'}
                </button>
            </form>

            {!result && !asking && (
                <div className="an-examples">
                    {EXAMPLES.map((q) => (
                        <button key={q} type="button" className="an-example" onClick={() => { setQuestion(q); ask(q); }}>{q}</button>
                    ))}
                </div>
            )}

            {error && <p className="an-error" role="alert">{error}</p>}

            {result && (
                <div className="an-result">
                    <p className="an-question">{result.question}</p>
                    <div className="an-answer">{renderAnswer(result.answer)}</div>

                    <h3 className="an-sources-title">Sources from the notes</h3>
                    <ol className="an-sources">
                        {result.sources.map((s) => (
                            <li key={s.n} className="an-source">
                                <button
                                    type="button"
                                    className="an-source-head"
                                    aria-expanded={openSource === s.n}
                                    onClick={() => setOpenSource(openSource === s.n ? null : s.n)}
                                >
                                    <span className="an-source-n">[{s.n}]</span>
                                    <span className="an-source-file">{shortName(s.sourceFile)}{s.page ? `, page ${s.page}` : ''}</span>
                                    <span className="an-source-score" title="How closely this section matches your question">{Math.round(s.score * 100)}% match</span>
                                    {openSource === s.n ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                                </button>
                                {openSource === s.n && <pre className="an-source-text">{s.text}</pre>}
                            </li>
                        ))}
                    </ol>
                </div>
            )}
        </div>
    );
}
