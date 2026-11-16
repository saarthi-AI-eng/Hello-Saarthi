import { useState, useRef, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Play, RotateCcw, Copy, Check, ChevronDown, Terminal, Activity, Square, Loader2, Send, ListChecks, History } from 'lucide-react';
import { api, type CodeProblemResponse, type CodeSubmitResponse, type CodeSubmissionItem } from '../lib/api';
import { useAuthStore } from '../stores/auth.store';
import GraphOutput from '../components/GraphOutput';
import './CodeLab.css';

// ─── Supported languages ─────────────────────────────────────────────────────
const LANGUAGES = [
    { id: 'python', label: 'Python', icon: '🐍' },
    { id: 'c++', label: 'C++', icon: '⚡' },
    { id: 'matlab', label: 'MATLAB', icon: '📐' },
    { id: 'julia', label: 'Julia', icon: '🔬' },
    { id: 'javascript', label: 'JavaScript', icon: '🟨' },
    { id: 'java', label: 'Java', icon: '☕' },
    { id: 'c', label: 'C', icon: '🔧' },
    { id: 'rust', label: 'Rust', icon: '🦀' },
    { id: 'go', label: 'Go', icon: '🐹' },
];

// ─── Starter code per language ───────────────────────────────────────────────
const STARTER_CODE: Record<string, string> = {
    python: `import math
import json

# Butterworth Low-Pass Filter Magnitude Response
def butterworth_mag(f, fc, n):
    return 1.0 / math.sqrt(1.0 + (f / fc) ** (2 * n))

order = 4
cutoff = 1000  # Hz

print("Butterworth Filter Frequency Response")
print("=" * 45)
print(f"{'Freq (Hz)':>10}  {'Magnitude (dB)':>15}")
print("-" * 45)

plot_points = []
for f in range(0, 4500, 50):
    mag = butterworth_mag(f, cutoff, order)
    db = 20 * math.log10(mag) if mag > 0 else -100.0
    if f % 500 == 0:
        print(f"{f:>10}  {db:>15.2f}")
    plot_points.append({"freq": f, "mag": round(db, 4)})

print("\\n✅ Filter design complete!")

# Output plot data tag — the graph panel reads this and renders it dynamically.
# Format: <plot-data>[{"freq": x, "mag": y}, ...]</plot-data>
print(f"<plot-data>{json.dumps(plot_points)}</plot-data>")`,

    matlab: `% Butterworth Low-Pass Filter Frequency Response
order = 4;
cutoff = 1000;  % Hz

fprintf('Butterworth Filter Frequency Response\\n');
fprintf('=============================================\\n');
fprintf('%10s  %15s\\n', 'Freq (Hz)', 'Magnitude (dB)');
fprintf('---------------------------------------------\\n');

for f = 0:500:4000
    mag = 1.0 / sqrt(1.0 + (f / cutoff)^(2 * order));
    db = 20 * log10(mag);
    fprintf('%10d  %15.2f\\n', f, db);
end

fprintf('\\nFilter design complete!\\n');`,

    julia: `# Butterworth Low-Pass Filter Magnitude Response
function butterworth_mag(f, fc, n)
    return 1.0 / sqrt(1.0 + (f / fc)^(2 * n))
end

order = 4
cutoff = 1000  # Hz

println("Butterworth Filter Frequency Response")
println("=" ^ 45)
println(lpad("Freq (Hz)", 10), "  ", lpad("Magnitude (dB)", 15))
println("-" ^ 45)

for f in 0:500:4000
    mag = butterworth_mag(f, cutoff, order)
    db = 20 * log10(mag)
    println(lpad(string(f), 10), "  ", lpad(@sprintf("%.2f", db), 15))
end

println("\\n✅ Filter design complete!")`,

    'c++': `#include <iostream>
#include <cmath>
#include <iomanip>

using namespace std;

// Butterworth filter magnitude response
double butterworth_mag(double f, double fc, int n) {
    return 1.0 / sqrt(1.0 + pow(f / fc, 2.0 * n));
}

int main() {
    int order = 4;
    double cutoff = 1000.0;  // Hz

    cout << "Butterworth Filter Frequency Response" << endl;
    cout << string(45, '=') << endl;
    cout << setw(10) << "Freq (Hz)" << "  " << setw(15) << "Magnitude (dB)" << endl;
    cout << string(45, '-') << endl;

    for (double f = 0; f <= 4000; f += 500) {
        double mag = butterworth_mag(f, cutoff, order);
        double db = 20 * log10(mag);
        cout << setw(10) << fixed << setprecision(0) << f
             << "  " << setw(15) << setprecision(2) << db << endl;
    }

    cout << endl << "Filter design complete!" << endl;
    return 0;
}`,

    javascript: `// Butterworth Low-Pass Filter Magnitude Response
function butterworthMag(f, fc, n) {
    return 1.0 / Math.sqrt(1.0 + Math.pow(f / fc, 2 * n));
}

const order = 4;
const cutoff = 1000;  // Hz

console.log("Butterworth Filter Frequency Response");
console.log("=".repeat(45));
console.log("Freq (Hz)".padStart(10) + "  " + "Magnitude (dB)".padStart(15));
console.log("-".repeat(45));

for (let f = 0; f <= 4000; f += 500) {
    const mag = butterworthMag(f, cutoff, order);
    const db = 20 * Math.log10(mag);
    console.log(f.toString().padStart(10) + "  " + db.toFixed(2).padStart(15));
}

console.log("\\n✅ Filter design complete!");`,

    java: `public class Main {
    static double butterworthMag(double f, double fc, int n) {
        return 1.0 / Math.sqrt(1.0 + Math.pow(f / fc, 2.0 * n));
    }

    public static void main(String[] args) {
        int order = 4;
        double cutoff = 1000.0;

        System.out.println("Butterworth Filter Frequency Response");
        System.out.println("=".repeat(45));
        System.out.printf("%10s  %15s%n", "Freq (Hz)", "Magnitude (dB)");
        System.out.println("-".repeat(45));

        for (double f = 0; f <= 4000; f += 500) {
            double mag = butterworthMag(f, cutoff, order);
            double db = 20 * Math.log10(mag);
            System.out.printf("%10.0f  %15.2f%n", f, db);
        }

        System.out.println("\\nFilter design complete!");
    }
}`,

    c: `#include <stdio.h>
#include <math.h>

double butterworth_mag(double f, double fc, int n) {
    return 1.0 / sqrt(1.0 + pow(f / fc, 2.0 * n));
}

int main() {
    int order = 4;
    double cutoff = 1000.0;

    printf("Butterworth Filter Frequency Response\\n");
    printf("=============================================\\n");
    printf("%10s  %15s\\n", "Freq (Hz)", "Magnitude (dB)");
    printf("---------------------------------------------\\n");

    for (double f = 0; f <= 4000; f += 500) {
        double mag = butterworth_mag(f, cutoff, order);
        double db = 20 * log10(mag);
        printf("%10.0f  %15.2f\\n", f, db);
    }

    printf("\\nFilter design complete!\\n");
    return 0;
}`,

    rust: `fn butterworth_mag(f: f64, fc: f64, n: i32) -> f64 {
    1.0 / (1.0 + (f / fc).powi(2 * n)).sqrt()
}

fn main() {
    let order = 4;
    let cutoff = 1000.0_f64;

    println!("Butterworth Filter Frequency Response");
    println!("{}", "=".repeat(45));
    println!("{:>10}  {:>15}", "Freq (Hz)", "Magnitude (dB)");
    println!("{}", "-".repeat(45));

    let mut f = 0.0;
    while f <= 4000.0 {
        let mag = butterworth_mag(f, cutoff, order);
        let db = 20.0 * mag.log10();
        println!("{:>10.0}  {:>15.2}", f, db);
        f += 500.0;
    }

    println!("\\n✅ Filter design complete!");
}`,

    go: `package main

import (
	"fmt"
	"math"
	"strings"
)

func butterworthMag(f, fc float64, n int) float64 {
	return 1.0 / math.Sqrt(1.0+math.Pow(f/fc, 2.0*float64(n)))
}

func main() {
	order := 4
	cutoff := 1000.0

	fmt.Println("Butterworth Filter Frequency Response")
	fmt.Println(strings.Repeat("=", 45))
	fmt.Printf("%10s  %15s\\n", "Freq (Hz)", "Magnitude (dB)")
	fmt.Println(strings.Repeat("-", 45))

	for f := 0.0; f <= 4000; f += 500 {
		mag := butterworthMag(f, cutoff, order)
		db := 20 * math.Log10(mag)
		fmt.Printf("%10.0f  %15.2f\\n", f, db)
	}

	fmt.Println("\\n✅ Filter design complete!")
}`,
};

// ─── API response shape (POST /code/execute) ─────────────────────────────────
interface CodeExecuteResponse {
    result: {
        stdout: string;
        stderr: string;
        exitCode: number;
        language: string;
        runtime: string;
        executionMs?: number | null;
    };
}

const DIFFICULTY_BADGE: Record<string, string> = { easy: 'badge-success', medium: 'badge-warning', hard: 'badge-error' };

// ─── Component ───────────────────────────────────────────────────────────────
export default function CodeLabPage() {
    const isTeacher = useAuthStore((st) => st.user?.role === 'teacher' || st.user?.role === 'admin');
    const [params, setParams] = useSearchParams();
    const [problems, setProblems] = useState<CodeProblemResponse[]>([]);
    const [problemsError, setProblemsError] = useState<string | null>(null);
    const problem = problems.find((pr) => String(pr.id) === params.get('problem')) ?? problems[0] ?? null;
    const [submissions, setSubmissions] = useState<CodeSubmissionItem[]>([]);
    const [testResult, setTestResult] = useState<CodeSubmitResponse | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [language, setLanguage] = useState('python');
    const [code, setCode] = useState(STARTER_CODE['python']);
    const [output, setOutput] = useState('Click "Run Code" to execute...');
    const [isRunning, setIsRunning] = useState(false);
    const [copied, setCopied] = useState(false);
    const [showLangDropdown, setShowLangDropdown] = useState(false);
    const [activeTab, setActiveTab] = useState<'console' | 'graph' | 'tests'>('console');
    const [showGraph, setShowGraph] = useState(false);
    const [graphData, setGraphData] = useState<{ freq: number; mag: number }[]>([]);
    const [executionTime, setExecutionTime] = useState<number | null>(null);
    const abortRef = useRef<AbortController | null>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);

    const starterFor = useCallback((lang: string, pr: CodeProblemResponse | null) =>
        pr?.starterCode?.[lang] ?? STARTER_CODE[lang] ?? `// ${lang} code here\n`, []);

    useEffect(() => {
        api.get<CodeProblemResponse[]>('/code/problems')
            .then(setProblems)
            .catch((e) => setProblemsError(e instanceof Error ? e.message : 'Could not load problems'));
    }, []);

    // A new problem: load its starter code, its submissions and clear old results.
    const problemId = problem?.id;
    useEffect(() => {
        if (!problemId) return;
        const pr = problems.find((x) => x.id === problemId) ?? null;
        setCode(starterFor(language, pr));
        setTestResult(null);
        setOutput('Click "Run Code" to execute...');
        setShowGraph(false);
        setExecutionTime(null);
        api.get<CodeSubmissionItem[]>(`/code/problems/${problemId}/submissions`).then(setSubmissions).catch(() => setSubmissions([]));
        // eslint-disable-next-line react-hooks/exhaustive-deps -- only when the problem changes
    }, [problemId]);

    const submitSolution = async () => {
        if (!problem || isSubmitting) return;
        setIsSubmitting(true);
        setActiveTab('tests');
        try {
            const res = await api.post<CodeSubmitResponse>(`/code/problems/${problem.id}/submit`, { language, code });
            setTestResult(res);
            const mine = await api.get<CodeSubmissionItem[]>(`/code/problems/${problem.id}/submissions`).catch(() => null);
            if (mine) setSubmissions(mine);
        } catch (e) {
            setTestResult(null);
            setOutput(`❌ Could not submit:\n\n${e instanceof Error ? e.message : 'Network error'}`);
            setActiveTab('console');
        } finally {
            setIsSubmitting(false);
        }
    };

    // Close dropdown when clicking outside
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setShowLangDropdown(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    const generateGraphData = () => {
        const data = [];
        const cutoff = 1000;
        const order = 4;
        for (let f = 0; f <= 4000; f += 50) {
            const mag = 1 / Math.sqrt(1 + Math.pow(f / cutoff, 2 * order));
            const db = 20 * Math.log10(mag);
            data.push({ freq: f, mag: db });
        }
        return data;
    };

    /**
     * Parse dynamic plot data from console stdout.
     * The code must print:  <plot-data>[{"freq":x,"mag":y}, ...]</plot-data>
     * Also accepts {"x":x, "y":y} for generic x/y data.
     * Returns null when no valid tag is found.
     */
    const parsePlotData = (stdout: string): { freq: number; mag: number }[] | null => {
        const match = stdout.match(/<plot-data>([\/\S\s]*?)<\/plot-data>/);
        if (!match) return null;
        try {
            const raw: any[] = JSON.parse(match[1].trim());
            if (!Array.isArray(raw) || raw.length === 0) return null;
            return raw.map((item) => ({
                freq: Number(item.freq ?? item.x ?? 0),
                mag: Number(item.mag ?? item.y ?? 0)
            })).filter((pt) => isFinite(pt.freq) && isFinite(pt.mag));
        } catch {
            return null;
        }
    };

    // ─── Real code execution via backend → Judge0 API ────────────────────────
    const runCode = useCallback(async () => {
        if (isRunning) return;

        setIsRunning(true);
        setExecutionTime(null);
        setActiveTab('console');

        const langLabel = LANGUAGES.find(l => l.id === language)?.label ?? language;
        setOutput(`⏳ Submitting ${langLabel} code to compiler...\n`);

        const startTime = performance.now();

        try {
            abortRef.current = new AbortController();

            // explainOnError needs the AI key; the console shows the raw error instead.
            const { result } = await api.post<CodeExecuteResponse>('/code/execute', {
                language,
                code,
                explainOnError: false,
            });
            const success = result.exitCode === 0;

            const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
            setExecutionTime(parseFloat(elapsed));

            // Build output string
            let out = '';

            // Show runtime info
            out += `🔧 Runtime: ${result.runtime || result.language}\n`;
            if (result.executionMs != null) out += `⏱ Time: ${(result.executionMs / 1000).toFixed(2)}s\n`;
            out += `${'─'.repeat(50)}\n`;

            if (!success) {
                if (result.stdout) {
                    out += result.stdout;
                    if (!result.stdout.endsWith('\n')) out += '\n';
                }
                out += `\n❌ Error (exit code ${result.exitCode}):\n`;
                out += result.stderr || 'Unknown error';
            } else {
                out += result.stdout || '(no output)';
                if (result.stderr) {
                    out += `\n\n⚠️ Warnings:\n${result.stderr}`;
                }
                if (!out.endsWith('\n')) out += '\n';
                out += `\n✅ Execution completed successfully (${elapsed}s total)`;
            }

            setOutput(out);

            if (success) {
                // Prefer dynamic plot data embedded in stdout; fall back to hardcoded template
                const rawOutput = result.stdout || '';
                const dynamic = parsePlotData(rawOutput);
                setGraphData(dynamic && dynamic.length > 0 ? dynamic : generateGraphData());
                setShowGraph(true);
            }
        } catch (err: any) {
            const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
            setExecutionTime(parseFloat(elapsed));

            if (err.name === 'AbortError') {
                setOutput('⚠️ Execution cancelled by user.');
            } else {
                setOutput(`❌ Failed to execute code:\n\n${err.message || 'Network error. Is the backend running?'}\n\nMake sure the backend server is running on port 8000.`);
            }
        } finally {
            setIsRunning(false);
            abortRef.current = null;
        }
    }, [language, code, isRunning]);

    const stopExecution = () => {
        abortRef.current?.abort();
    };

    const copyCode = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const changeLang = (langId: string) => {
        setLanguage(langId);
        setCode(starterFor(langId, problem));
        setShowLangDropdown(false);
        setOutput('Click "Run Code" to execute...');
        setShowGraph(false);
        setActiveTab('console');
        setExecutionTime(null);
    };

    const currentLang = LANGUAGES.find(l => l.id === language);

    return (
        <div className="codelab-page">
            {/* Problem Panel */}
            <div className="codelab-problem">
                <div className="codelab-problem-header">
                    <div className="codelab-problem-picker">
                        <label htmlFor="codelab-problem-select" className="text-xs text-gray-500">Problem</label>
                        <select
                            id="codelab-problem-select"
                            className="input"
                            value={problem?.id ?? ''}
                            onChange={(e) => setParams({ problem: e.target.value })}
                        >
                            {problems.map((pr) => <option key={pr.id} value={pr.id}>{pr.title}</option>)}
                        </select>
                    </div>
                </div>
                <div className="codelab-problem-body">
                    {problemsError && <p>{problemsError}</p>}
                    {!problem && !problemsError && <p>Loading problems…</p>}
                    {problem && (
                        <>
                            <h2 className="codelab-problem-title">{problem.title}</h2>
                            <div className="problem-meta">
                                <span className={`badge ${DIFFICULTY_BADGE[problem.difficulty] ?? 'badge-warning'}`}>{problem.difficulty}</span>
                                <span className="text-xs text-gray-500">Points: {problem.points}</span>
                                {problem.topics && <span className="text-xs text-gray-500">{problem.topics}</span>}
                            </div>

                            <p>{problem.description}</p>

                            {problem.requirements.length > 0 && (
                                <>
                                    <h4>Requirements:</h4>
                                    <ul>{problem.requirements.map((r) => <li key={r}>{r}</li>)}</ul>
                                </>
                            )}

                            {problem.testCases.length > 0 && (
                                <>
                                    <h4><ListChecks size={14} /> Test cases ({problem.testCases.length}):</h4>
                                    {problem.testCases.map((tc, i) => (
                                        <div key={i} className="codelab-testcase">
                                            {tc.hidden ? <em>Test {i + 1}: hidden</em> : (
                                                <>
                                                    {tc.input ? <p><strong>Input:</strong></p> : null}
                                                    {tc.input ? <pre>{tc.input}</pre> : null}
                                                    <p><strong>Expected output:</strong></p>
                                                    <pre>{tc.expectedOutput}</pre>
                                                </>
                                            )}
                                        </div>
                                    ))}
                                </>
                            )}

                            <div className="codelab-buttons-stack">
                                {problem.title.toLowerCase().includes('butterworth') && (
                                    <button className="btn btn-outline btn-sm w-full gap-2" onClick={() => {
                                        setGraphData(generateGraphData());
                                        setShowGraph(true);
                                        setActiveTab('graph');
                                    }}>
                                        <Activity size={14} /> Show Graph Template
                                    </button>
                                )}
                            </div>

                            {problem.hints.length > 0 && (
                                <details className="codelab-hint">
                                    <summary>Hints ({problem.hints.length})</summary>
                                    <ul>{problem.hints.map((h) => <li key={h}>{h}</li>)}</ul>
                                </details>
                            )}

                            <h4><History size={14} /> {isTeacher ? 'Student submissions' : 'Your submissions'}</h4>
                            {submissions.length === 0 ? (
                                <p className="text-xs text-gray-500">{isTeacher ? 'No submissions from your students yet.' : 'Submit your code to run the tests and send it to your teacher.'}</p>
                            ) : (
                                <ul className="codelab-submissions">
                                    {submissions.map((sub) => (
                                        <li key={sub.id}>
                                            <button
                                                type="button"
                                                title="Open this code in the editor"
                                                onClick={() => { setLanguage(sub.language); setCode(sub.code); setActiveTab('console'); }}
                                            >
                                                <span className={sub.passed === sub.total ? 'codelab-pass' : 'codelab-fail'}>{sub.passed}/{sub.total}</span>
                                                {isTeacher && <span className="codelab-sub-name">{sub.studentName}</span>}
                                                <span className="codelab-sub-meta">{sub.language} · {new Date(sub.createdAt).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</span>
                                            </button>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </>
                    )}

                    <h4>Supported Languages:</h4>
                    <div className="codelab-supported-langs">
                        {LANGUAGES.map(l => (
                            <span key={l.id} className="codelab-lang-badge" title={l.label}>
                                {l.icon} {l.label}
                            </span>
                        ))}
                    </div>
                    <p className="text-xs text-gray-500">MATLAB code runs on GNU Octave when it is installed on the server.</p>
                </div>
            </div>

            {/* Editor Panel */}
            <div className="codelab-editor-panel">
                {/* Toolbar */}
                <div className="codelab-toolbar">
                    <div className="codelab-lang-selector" ref={dropdownRef}>
                        <button className="codelab-lang-btn" onClick={() => setShowLangDropdown(!showLangDropdown)}>
                            <span className="codelab-lang-icon">{currentLang?.icon}</span>
                            {currentLang?.label ?? language} <ChevronDown size={14} />
                        </button>
                        {showLangDropdown && (
                            <div className="codelab-lang-dropdown animate-scale-in">
                                {LANGUAGES.map((l) => (
                                    <button
                                        key={l.id}
                                        className={l.id === language ? 'active' : ''}
                                        onClick={() => changeLang(l.id)}
                                    >
                                        <span className="codelab-dropdown-icon">{l.icon}</span>
                                        {l.label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                    <div className="codelab-toolbar-actions">
                        {executionTime !== null && (
                            <span className="codelab-exec-time">⏱ {executionTime}s</span>
                        )}
                        <button className="btn btn-ghost btn-sm" onClick={copyCode}>
                            {copied ? <Check size={14} /> : <Copy size={14} />}
                            {copied ? 'Copied' : 'Copy'}
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => { setCode(starterFor(language, problem)); setOutput('Click "Run Code" to execute...'); setShowGraph(false); setExecutionTime(null); }}>
                            <RotateCcw size={14} /> Reset
                        </button>
                        {isRunning ? (
                            <button className="btn btn-danger btn-sm" onClick={stopExecution}>
                                <Square size={14} /> Stop
                            </button>
                        ) : (
                            <button className="btn btn-success btn-sm" onClick={runCode}>
                                <Play size={14} /> Run Code
                            </button>
                        )}
                        {problem && !isTeacher && (
                            <button className="btn btn-primary btn-sm" disabled={isSubmitting || isRunning} onClick={submitSolution}>
                                {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} {isSubmitting ? 'Testing…' : 'Submit'}
                            </button>
                        )}
                    </div>
                </div>

                {/* Editor Area */}
                <div className="codelab-editor">
                    <div className="codelab-line-numbers">
                        {code.split('\n').map((_, i) => <span key={i}>{i + 1}</span>)}
                    </div>
                    <textarea
                        value={code}
                        onChange={(e) => setCode(e.target.value)}
                        className="codelab-textarea"
                        spellCheck={false}
                    />
                </div>

                {/* Output Area */}
                <div className={`codelab-output-section ${activeTab === 'graph' ? 'expanded' : ''}`}>
                    <div className="codelab-output-tabs">
                        <button
                            className={`output-tab ${activeTab === 'console' ? 'active' : ''}`}
                            onClick={() => setActiveTab('console')}
                        >
                            <Terminal size={14} /> Console
                            {isRunning && <Loader2 size={14} className="animate-spin" style={{ marginLeft: 6 }} />}
                        </button>
                        <button
                            className={`output-tab ${activeTab === 'graph' ? 'active' : ''}`}
                            onClick={() => setActiveTab('graph')}
                        >
                            <Activity size={14} /> Graph Output
                            {showGraph && <span className="w-2 h-2 rounded-full bg-green-500 ml-2 animate-pulse"></span>}
                        </button>
                        <button
                            className={`output-tab ${activeTab === 'tests' ? 'active' : ''}`}
                            onClick={() => setActiveTab('tests')}
                        >
                            <ListChecks size={14} /> Test Results
                            {testResult && <span className={testResult.passed === testResult.total ? 'codelab-pass' : 'codelab-fail'}>{testResult.passed}/{testResult.total}</span>}
                        </button>
                    </div>

                    <div className="codelab-output-content">
                        {activeTab === 'tests' ? (
                            isSubmitting ? (
                                <pre className="codelab-console-text">⏳ Running your code against each test case…</pre>
                            ) : testResult ? (
                                <div className="codelab-test-results">
                                    <p className={testResult.passed === testResult.total ? 'codelab-pass' : 'codelab-fail'}>
                                        {testResult.passed === testResult.total ? '✅ All tests passed.' : `❌ ${testResult.passed} of ${testResult.total} tests passed.`} Your teacher has been notified.
                                    </p>
                                    {testResult.results.map((r) => (
                                        <div key={r.index} className="codelab-test-result">
                                            <strong>{r.passed ? '✅' : '❌'} Test {r.index}{r.hidden ? ' (hidden)' : ''}</strong>
                                            {!r.hidden && !r.passed && (
                                                <div className="codelab-test-diff">
                                                    <div><span>Expected</span><pre>{r.expectedOutput}</pre></div>
                                                    <div><span>Your output</span><pre>{r.actualOutput || '(no output)'}{r.stderr ? `\n${r.stderr}` : ''}</pre></div>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <pre className="codelab-console-text">Click "Submit" to run your code against the test cases.</pre>
                            )
                        ) : activeTab === 'console' ? (
                            <pre className="codelab-console-text">{output}</pre>
                        ) : (
                            showGraph ? (
                                <GraphOutput data={graphData} cutoff={1000} />
                            ) : (
                                <div className="graph-placeholder">
                                    <Activity size={48} className="text-gray-700 mb-4" />
                                    <p className="text-gray-500">Run the code to generate visualization</p>
                                </div>
                            )
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
