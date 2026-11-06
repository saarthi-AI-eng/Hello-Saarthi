import { useState, useRef, useEffect, useCallback } from 'react';
import { Play, RotateCcw, Copy, Check, ChevronDown, Terminal, Activity, FileText, Square, Loader2 } from 'lucide-react';
import { api } from '../lib/api';
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

// ─── API response shape ──────────────────────────────────────────────────────
interface CodeExecuteResponse {
    success: boolean;
    language: string;
    stage: string;
    stdout: string;
    stderr: string;
    exitCode: number;
    output: string;
    error?: string;
    status?: string;
    time?: string;
    memory?: number;
}

// ─── Component ───────────────────────────────────────────────────────────────
export default function CodeLabPage() {
    const [language, setLanguage] = useState('python');
    const [code, setCode] = useState(STARTER_CODE['python']);
    const [output, setOutput] = useState('Click "Run Code" to execute...');
    const [isRunning, setIsRunning] = useState(false);
    const [copied, setCopied] = useState(false);
    const [showLangDropdown, setShowLangDropdown] = useState(false);
    const [activeTab, setActiveTab] = useState<'console' | 'graph'>('console');
    const [showGraph, setShowGraph] = useState(false);
    const [graphData, setGraphData] = useState<{ freq: number; mag: number }[]>([]);
    const [executionTime, setExecutionTime] = useState<number | null>(null);
    const abortRef = useRef<AbortController | null>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);

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

            const result = await api.post<CodeExecuteResponse>('/code/execute', {
                language,
                code,
            });

            const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
            setExecutionTime(parseFloat(elapsed));

            if (result.error) {
                setOutput(`❌ Error: ${result.error}\n`);
                return;
            }

            // Build output string
            let out = '';

            // Show runtime info
            out += `🔧 Runtime: ${result.language}\n`;
            if (result.time) out += `⏱ CPU Time: ${result.time}s`;
            if (result.memory) out += `  |  💾 Memory: ${(result.memory / 1024).toFixed(1)} MB`;
            if (result.time || result.memory) out += '\n';
            out += `${'─'.repeat(50)}\n`;

            if (result.stage === 'compile' && !result.success) {
                out += `❌ Compilation Error:\n\n`;
                out += result.stderr || result.output || 'Unknown compilation error';
            } else if (!result.success) {
                if (result.stdout) {
                    out += result.stdout;
                    if (!result.stdout.endsWith('\n')) out += '\n';
                }
                out += `\n❌ ${result.status || 'Runtime Error'}:\n`;
                out += result.stderr || result.output || 'Unknown error';
            } else {
                out += result.stdout || result.output || '(no output)';
                if (result.stderr) {
                    out += `\n\n⚠️ Warnings:\n${result.stderr}`;
                }
                if (!out.endsWith('\n')) out += '\n';
                out += `\n✅ Execution completed successfully (${elapsed}s total)`;
            }

            setOutput(out);

            if (result.success) {
                // Prefer dynamic plot data embedded in stdout; fall back to hardcoded template
                const rawOutput = result.stdout || result.output || '';
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
        setCode(STARTER_CODE[langId] || `// ${langId} code here\n`);
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
                    <div>
                        <h2>Filter Design</h2>
                        <span className="text-xs text-gray-500">DSP Module 3</span>
                    </div>
                </div>
                <div className="codelab-problem-body">
                    <div className="problem-meta">
                        <span className="badge badge-warning">Medium</span>
                        <span className="text-xs text-gray-500">Points: 50</span>
                    </div>

                    <p>Create a program to compute the frequency response of a low-pass Butterworth filter.</p>

                    <h4>Requirements:</h4>
                    <ul>
                        <li><strong>Order:</strong> 4</li>
                        <li><strong>Cutoff Frequency:</strong> 1000 Hz</li>
                        <li><strong>Sampling Rate:</strong> 8000 Hz</li>
                        <li><strong>Output:</strong> Magnitude Response (dB vs Hz)</li>
                    </ul>

                    <h4>Expected Output:</h4>
                    <ul>
                        <li>Table of magnitude vs frequency</li>
                        <li>-3dB point exactly at 1000 Hz</li>
                        <li>-20dB/decade roll-off after cutoff</li>
                    </ul>

                    <div className="codelab-buttons-stack">
                        <button className="btn btn-outline btn-sm w-full gap-2">
                            <FileText size={14} /> Read Solution
                        </button>
                        <button className="btn btn-outline btn-sm w-full gap-2" onClick={() => {
                            setGraphData(generateGraphData());
                            setShowGraph(true);
                            setActiveTab('graph');
                        }}>
                            <Activity size={14} /> Show Graph Template
                        </button>
                    </div>

                    <h4>Supported Languages:</h4>
                    <div className="codelab-supported-langs">
                        {LANGUAGES.map(l => (
                            <span key={l.id} className="codelab-lang-badge" title={l.label}>
                                {l.icon} {l.label}
                            </span>
                        ))}
                    </div>

                    <h4>Hints:</h4>
                    <div className="codelab-hint">
                        <p>Write your code in <strong>any supported language</strong>. The compiler will detect and run it using the correct runtime. MATLAB code runs on <strong>GNU Octave</strong>.</p>
                    </div>
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
                        <button className="btn btn-ghost btn-sm" onClick={() => { setCode(STARTER_CODE[language] || ''); setOutput('Click "Run Code" to execute...'); setShowGraph(false); setExecutionTime(null); }}>
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
                    </div>

                    <div className="codelab-output-content">
                        {activeTab === 'console' ? (
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
