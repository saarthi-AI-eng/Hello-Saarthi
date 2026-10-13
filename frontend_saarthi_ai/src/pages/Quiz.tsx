import { useState } from 'react';
import { Clock, Flag, ChevronLeft, ChevronRight, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';
import './Quiz.css';

const quizData = {
    title: 'Digital Signal Processing - Module 1 Quiz',
    totalQuestions: 10,
    timeLimit: 15,
    questions: [
        { id: 1, text: 'What is the Nyquist rate for a signal with maximum frequency component of 4 kHz?', options: ['4 kHz', '8 kHz', '2 kHz', '16 kHz'], correct: 1, explanation: 'The Nyquist rate is twice the maximum frequency. For f_max = 4 kHz, Nyquist rate = 2 × 4 = 8 kHz.', difficulty: 'Easy' },
        { id: 2, text: 'Which of the following is a property of the Discrete Fourier Transform (DFT)?', options: ['It is aperiodic', 'It produces continuous output', 'It has circular convolution property', 'It requires infinite computation time'], correct: 2, explanation: 'The DFT has circular (cyclic) convolution property, where multiplication in frequency domain corresponds to circular convolution in time domain.', difficulty: 'Medium' },
        { id: 3, text: 'The Z-transform of the unit step signal u[n] is:', options: ['1/(1-z)', '1/(1-z⁻¹)', 'z/(z-1)', 'Both B and C'], correct: 3, explanation: 'The Z-transform of u[n] = 1/(1-z⁻¹) = z/(z-1). Both forms are equivalent representations.', difficulty: 'Medium' },
        { id: 4, text: 'What is the time complexity of the FFT algorithm?', options: ['O(N²)', 'O(N log N)', 'O(N)', 'O(log N)'], correct: 1, explanation: 'The Fast Fourier Transform reduces the DFT computation from O(N²) to O(N log N) by exploiting symmetry and periodicity.', difficulty: 'Easy' },
        { id: 5, text: 'An FIR filter has which of the following properties?', options: ['Infinite impulse response', 'Always unstable', 'Linear phase response possible', 'Requires feedback'], correct: 2, explanation: 'FIR filters can achieve exact linear phase response, which is important for applications requiring no phase distortion.', difficulty: 'Medium' },
    ],
};

export default function QuizPage() {
    const [currentQ, setCurrentQ] = useState(0);
    const [answers, setAnswers] = useState<(number | null)[]>(new Array(quizData.questions.length).fill(null));
    const [flagged, setFlagged] = useState<Set<number>>(new Set());
    const [submitted, setSubmitted] = useState(false);
    const [showExplanation, setShowExplanation] = useState(false);

    const question = quizData.questions[currentQ];
    const answered = answers.filter((a) => a !== null).length;

    const selectAnswer = (optionIdx: number) => {
        if (submitted) return;
        const newAnswers = [...answers];
        newAnswers[currentQ] = optionIdx;
        setAnswers(newAnswers);
    };

    const toggleFlag = () => {
        const newFlags = new Set(flagged);
        if (newFlags.has(currentQ)) newFlags.delete(currentQ);
        else newFlags.add(currentQ);
        setFlagged(newFlags);
    };

    const handleSubmit = () => { setSubmitted(true); setShowExplanation(true); setCurrentQ(0); };

    const score = submitted ? answers.reduce((s: number, a, i) => s + (a === quizData.questions[i].correct ? 1 : 0), 0) : 0;

    const diffColor = (d: string) => {
        if (d === 'Easy') return { bg: '#D1FAE5', color: '#059669' };
        if (d === 'Medium') return { bg: '#FEF3C7', color: '#D97706' };
        return { bg: '#FEE2E2', color: '#DC2626' };
    };

    return (
        <div className="quiz-page">
            {/* Header */}
            <div className="quiz-header">
                <div className="quiz-header-left">
                    <h2>{quizData.title}</h2>
                </div>
                <div className="quiz-header-center">
                    <Clock size={18} />
                    <span className="quiz-timer">{submitted ? 'Completed' : '12:45'}</span>
                </div>
                <div className="quiz-header-right">
                    <span>Question {currentQ + 1} of {quizData.questions.length}</span>
                    <div className="progress-bar" style={{ width: '120px' }}>
                        <div className="progress-bar-fill" style={{ width: `${((currentQ + 1) / quizData.questions.length) * 100}%` }} />
                    </div>
                </div>
            </div>

            {/* Score Banner */}
            {submitted && (
                <div className="quiz-score-banner animate-scale-in">
                    <div className="quiz-score-circle">
                        <span className="quiz-score-value">{score}/{quizData.questions.length}</span>
                        <span className="quiz-score-pct">{Math.round((score / quizData.questions.length) * 100)}%</span>
                    </div>
                    <div className="quiz-score-info">
                        <h3>Quiz Completed!</h3>
                        <p>You scored {score} out of {quizData.questions.length} questions correctly.</p>
                    </div>
                </div>
            )}

            {/* Content */}
            <div className="quiz-content">
                <div className="quiz-question-area">
                    {/* Question Card */}
                    <div className="quiz-question-card animate-fade-in">
                        <div className="quiz-question-header">
                            <span className="badge badge-primary">Question {currentQ + 1}</span>
                            <span className="badge" style={diffColor(question.difficulty)}>{question.difficulty}</span>
                            <button className={`quiz-flag-btn ${flagged.has(currentQ) ? 'flagged' : ''}`} onClick={toggleFlag}>
                                <Flag size={16} /> {flagged.has(currentQ) ? 'Flagged' : 'Flag for review'}
                            </button>
                        </div>
                        <p className="quiz-question-text">{question.text}</p>

                        <div className="quiz-options">
                            {question.options.map((opt, i) => {
                                const isSelected = answers[currentQ] === i;
                                const isCorrect = submitted && i === question.correct;
                                const isWrong = submitted && isSelected && i !== question.correct;
                                return (
                                    <button
                                        key={i}
                                        className={`quiz-option ${isSelected ? 'selected' : ''} ${isCorrect ? 'correct' : ''} ${isWrong ? 'wrong' : ''}`}
                                        onClick={() => selectAnswer(i)}
                                    >
                                        <span className="quiz-option-letter">{String.fromCharCode(65 + i)}</span>
                                        <span className="quiz-option-text">{opt}</span>
                                        {isCorrect && <CheckCircle2 size={18} />}
                                        {isWrong && <XCircle size={18} />}
                                    </button>
                                );
                            })}
                        </div>

                        {/* Explanation */}
                        {submitted && showExplanation && (
                            <div className="quiz-explanation animate-fade-in">
                                <AlertCircle size={18} />
                                <div>
                                    <strong>Explanation:</strong>
                                    <p>{question.explanation}</p>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Navigation Grid */}
                <div className="quiz-nav-sidebar">
                    <h4>Questions</h4>
                    <div className="quiz-nav-grid">
                        {quizData.questions.map((_, i) => {
                            let cls = 'quiz-nav-item';
                            if (i === currentQ) cls += ' current';
                            else if (submitted && answers[i] === quizData.questions[i].correct) cls += ' correct';
                            else if (submitted && answers[i] !== null) cls += ' wrong';
                            else if (answers[i] !== null) cls += ' answered';
                            if (flagged.has(i)) cls += ' flagged';
                            return (
                                <button key={i} className={cls} onClick={() => setCurrentQ(i)}>
                                    {i + 1}
                                </button>
                            );
                        })}
                    </div>
                    <div className="quiz-nav-legend">
                        <span><span className="legend-dot current" /> Current</span>
                        <span><span className="legend-dot answered" /> Answered</span>
                        <span><span className="legend-dot flagged" /> Flagged</span>
                    </div>
                </div>
            </div>

            {/* Bottom Bar */}
            <div className="quiz-bottom-bar">
                <button className="btn btn-ghost" disabled={currentQ === 0} onClick={() => setCurrentQ(currentQ - 1)}>
                    <ChevronLeft size={16} /> Previous
                </button>
                <span className="quiz-bottom-info">{answered} of {quizData.questions.length} answered</span>
                {currentQ < quizData.questions.length - 1 ? (
                    <button className="btn btn-primary" onClick={() => setCurrentQ(currentQ + 1)}>
                        Next <ChevronRight size={16} />
                    </button>
                ) : !submitted ? (
                    <button className="btn btn-success" onClick={handleSubmit}>Submit Quiz</button>
                ) : (
                    <button className="btn btn-primary" onClick={() => { setSubmitted(false); setAnswers(new Array(quizData.questions.length).fill(null)); setCurrentQ(0); }}>Retake Quiz</button>
                )}
            </div>
        </div>
    );
}
