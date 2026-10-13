import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Mail, Lock, Eye, EyeOff, User, Building2, Brain, Code2, BarChart3, GraduationCap, ArrowLeft } from 'lucide-react';
import { useAuthStore } from '../../stores/auth.store';
import { LogoIcon } from '../../components/LogoIcon';
import './Auth.css';

export default function SignupPage() {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [institute, setInstitute] = useState('');
    const [isTeacher, setIsTeacher] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [agreed, setAgreed] = useState(false);
    const [error, setError] = useState('');
    const { signup, isLoading } = useAuthStore();
    const navigate = useNavigate();

    const getPasswordStrength = () => {
        if (!password) return { level: 0, label: '', color: '' };
        let score = 0;
        if (password.length >= 8) score++;
        if (/[A-Z]/.test(password)) score++;
        if (/[0-9]/.test(password)) score++;
        if (/[^A-Za-z0-9]/.test(password)) score++;
        const levels = [
            { level: 1, label: 'Weak', color: 'var(--error)' },
            { level: 2, label: 'Fair', color: 'var(--warning)' },
            { level: 3, label: 'Good', color: 'var(--info)' },
            { level: 4, label: 'Strong', color: 'var(--success)' },
        ];
        return levels[score - 1] || levels[0];
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        if (password !== confirmPassword) {
            setError('Passwords do not match');
            return;
        }
        if (!agreed) {
            setError('Please accept the terms and conditions');
            return;
        }
        try {
            await signup({
                name,
                email,
                password,
                confirmPassword,
                institute: institute || undefined,
                role: isTeacher ? 'teacher' : undefined,
            });
            navigate('/dashboard');
        } catch (err: any) {
            setError(err.message || 'Signup failed. Please try again.');
        }
    };

    const strength = getPasswordStrength();

    return (
        <div className="auth-page">
            {/* Left Panel */}
            <div className="auth-left">
                <div className="auth-left-content">
                    <div className="auth-left-brand">
                        <div className="landing-logo-icon"><LogoIcon size={24} /></div>
                        <span className="auth-left-logo">Saarthi.ai</span>
                    </div>
                    <p className="auth-left-tagline">Your Agentic AI Teaching Assistant</p>
                    <div className="auth-left-illustration">
                        <div className="auth-illustration-orb auth-orb-1" />
                        <div className="auth-illustration-orb auth-orb-2" />
                        <div className="auth-illustration-orb auth-orb-3" />
                        <div className="auth-illustration-center"><Brain size={64} /></div>
                    </div>
                    <div className="auth-left-features">
                        <div className="auth-feature-item">
                            <div className="auth-feature-icon"><Brain size={18} /></div>
                            <span>Domain-Specific AI</span>
                        </div>
                        <div className="auth-feature-item">
                            <div className="auth-feature-icon"><Code2 size={18} /></div>
                            <span>Integrated Coding Lab</span>
                        </div>
                        <div className="auth-feature-item">
                            <div className="auth-feature-icon"><BarChart3 size={18} /></div>
                            <span>Progress Analytics</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Right Panel */}
            <div className="auth-right">
                <div className="auth-form-container animate-fade-in">
                    <Link to="/" className="auth-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', marginBottom: '1.5rem', color: 'var(--text-muted)' }}>
                        <ArrowLeft size={16} /> Back to home
                    </Link>
                    <h1 className="auth-title">Create your account</h1>
                    <p className="auth-subtitle">Start mastering technical subjects with AI</p>

                    {error && (
                        <div className="auth-error animate-scale-in"><span>{error}</span></div>
                    )}

                    <form onSubmit={handleSubmit} className="auth-form">
                        <div className="auth-field">
                            <label>Full Name</label>
                            <div className="auth-input-wrapper">
                                <User size={18} className="auth-input-icon" />
                                <input type="text" placeholder="Enter your full name" value={name}
                                    onChange={(e) => setName(e.target.value)} className="input auth-input-with-icon" required />
                            </div>
                        </div>

                        <div className="auth-field">
                            <label>Institute Email</label>
                            <div className="auth-input-wrapper">
                                <Mail size={18} className="auth-input-icon" />
                                <input type="email" placeholder="you@university.edu" value={email}
                                    onChange={(e) => setEmail(e.target.value)} className="input auth-input-with-icon" required />
                            </div>
                        </div>

                        <div className="auth-field">
                            <label>Institute (Optional)</label>
                            <div className="auth-input-wrapper">
                                <Building2 size={18} className="auth-input-icon" />
                                <input type="text" placeholder="Your university/college" value={institute}
                                    onChange={(e) => setInstitute(e.target.value)} className="input auth-input-with-icon" />
                            </div>
                        </div>

                        <div className="auth-field">
                            <label className="auth-checkbox-label auth-role-label">
                                <input type="checkbox" checked={isTeacher} onChange={(e) => setIsTeacher(e.target.checked)} className="auth-checkbox" />
                                <span className="auth-role-text"><GraduationCap size={18} className="auth-role-icon" /> I'm a teacher / instructor — sign me up with teacher access</span>
                            </label>
                            <p className="auth-role-hint">Teachers can create courses, add videos, manage assignments, and create quizzes. If you already have an account with this email, sign in instead — your role was set when you first signed up.</p>
                        </div>

                        <div className="auth-field">
                            <label>Password</label>
                            <div className="auth-input-wrapper">
                                <Lock size={18} className="auth-input-icon" />
                                <input type={showPassword ? 'text' : 'password'} placeholder="Create a password" value={password}
                                    onChange={(e) => setPassword(e.target.value)} className="input auth-input-with-icon" required minLength={8} />
                                <button type="button" className="auth-eye-btn" onClick={() => setShowPassword(!showPassword)}>
                                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                                </button>
                            </div>
                            {password && (
                                <div className="auth-password-strength">
                                    <div className="auth-strength-bar">
                                        <div className="auth-strength-fill" style={{ width: `${strength.level * 25}%`, background: strength.color }} />
                                    </div>
                                    <span style={{ color: strength.color, fontSize: '0.75rem', fontWeight: 600 }}>{strength.label}</span>
                                </div>
                            )}
                        </div>

                        <div className="auth-field">
                            <label>Confirm Password</label>
                            <div className="auth-input-wrapper">
                                <Lock size={18} className="auth-input-icon" />
                                <input type="password" placeholder="Confirm your password" value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    className={`input auth-input-with-icon ${confirmPassword && confirmPassword !== password ? 'input-error' : ''}`}
                                    required />
                            </div>
                            {confirmPassword && confirmPassword !== password && (
                                <span className="auth-field-error">Passwords don't match</span>
                            )}
                        </div>

                        <label className="auth-checkbox-label">
                            <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="auth-checkbox" />
                            I agree to the <a href="#" className="auth-link">Terms of Service</a> and <a href="#" className="auth-link">Privacy Policy</a>
                        </label>

                        <button type="submit" className="btn btn-primary btn-lg auth-submit" disabled={isLoading || !agreed}>
                            {isLoading ? <span className="auth-spinner" /> : 'Create Account'}
                        </button>
                    </form>

                    <p className="auth-footer-text">
                        Already have an account? <Link to="/login" className="auth-link-bold">Sign In</Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
