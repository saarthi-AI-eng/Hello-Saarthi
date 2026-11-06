import { useNavigate } from 'react-router-dom';
import {
    Sparkles, Code2, Award, BookOpen, Brain, BarChart3,
    Play, ArrowRight, Star, CheckCircle2, ChevronRight,
    Zap, Users, GraduationCap, Shield, Sun, Moon
} from 'lucide-react';
import { useSettingsStore } from '../stores/settings.store';
import './Landing.css';
import { LogoIcon } from '../components/LogoIcon';

const features = [
    {
        icon: Brain,
        title: 'AI Tutor Chat',
        desc: 'Ask complex doubts and get instant, accurate explanations with source citations. Better than ChatGPT for technical subjects.',
        color: '#4F46E5',
        bg: '#EEF2FF',
    },
    {
        icon: Code2,
        title: 'Interactive Coding Lab',
        desc: 'Practice algorithms and DSP implementations in an integrated code editor with instant feedback and test cases.',
        color: '#10B981',
        bg: '#D1FAE5',
    },
    {
        icon: Award,
        title: 'Exam Practice',
        desc: 'Real exam questions with detailed solutions. Track your progress and identify weak areas with AI-powered analytics.',
        color: '#8B5CF6',
        bg: '#EDE9FE',
    },
    {
        icon: Play,
        title: 'Annotated Videos',
        desc: 'Timestamped video lectures with associated quizzes, practice problems, and searchable transcripts.',
        color: '#F59E0B',
        bg: '#FEF3C7',
    },
    {
        icon: BookOpen,
        title: 'Digitized Notes',
        desc: 'Handwritten notes converted to searchable digital format, organized by modules and difficulty levels.',
        color: '#EF4444',
        bg: '#FEE2E2',
    },
    {
        icon: BarChart3,
        title: 'Progress Analytics',
        desc: 'Mastery tracking, performance dashboards, weak area identification, and personalized recommendations.',
        color: '#3B82F6',
        bg: '#DBEAFE',
    },
];

const subjects = [
    'Digital Signal Processing', 'Machine Learning', 'Data Structures & Algorithms',
    'Pattern Recognition', 'Signal & Systems', 'Computer Vision',
];

const testimonials = [
    { name: 'Priya Sharma', role: 'B.Tech CSE, IIT Delhi', text: 'Saarthi helped me score 95% in my DSP exam. The AI explanations are so much better than generic chatbots!', rating: 5 },
    { name: 'Rahul Verma', role: 'M.Tech ECE, NIT Trichy', text: 'The coding lab is incredibly powerful. I practiced all my algorithms here and got placed at Google!', rating: 5 },
    { name: 'Ananya Gupta', role: 'Working Professional', text: 'As a working professional, the micro-learning approach and mobile access saved me so much time.', rating: 5 },
];

export default function LandingPage() {
    const navigate = useNavigate();
    const { theme, setTheme } = useSettingsStore();

    const toggleTheme = () => {
        const isDark = theme === 'dark' || (theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);
        setTheme(isDark ? 'light' : 'dark');
    };

    return (
        <div className="landing">
            {/* Navbar */}
            <nav className="landing-nav">
                <div className="container landing-nav-inner">
                    <div className="landing-nav-brand">
                        <div className="landing-logo-icon">
                            <LogoIcon size={22} />
                        </div>
                        <span className="landing-logo-text">Saarthi.ai</span>
                    </div>
                    <div className="landing-nav-links">
                        <a href="#features">Features</a>
                        <a href="#subjects">Subjects</a>
                        <a href="#testimonials">Reviews</a>
                    </div>
                    <div className="landing-nav-actions" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <button
                            className="btn btn-ghost"
                            aria-label="Toggle theme"
                            onClick={toggleTheme}
                            title="Toggle Dark/Light Mode"
                            style={{ padding: '0.5rem', borderRadius: '50%' }}
                        >
                            {theme === 'dark' || (theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches) ? (
                                <Sun size={20} />
                            ) : (
                                <Moon size={20} />
                            )}
                        </button>
                        <button className="btn btn-ghost" onClick={() => navigate('/login')}>Login</button>
                        <button className="btn btn-primary" onClick={() => navigate('/signup')}>
                            Get Started <ArrowRight size={16} />
                        </button>
                    </div>
                </div>
            </nav>

            {/* Hero */}
            <section className="landing-hero">
                <div className="landing-hero-bg" />
                <div className="container landing-hero-content">
                    <div className="landing-hero-text animate-fade-in-up">
                        <div className="landing-hero-badge">
                            <Zap size={14} />
                            <span>AI-Powered Learning Platform</span>
                        </div>
                        <h1 className="landing-hero-title">
                            Master Technical Subjects
                            <br />
                            with <span className="landing-hero-gradient">Saarthi AI</span>
                        </h1>
                        <p className="landing-hero-desc">
                            Your personal Agentic AI tutor for Digital Signal Processing, Machine Learning,
                            and Algorithms. Learn 10x faster with intelligent tutoring, interactive
                            code labs, and instant doubt solving.
                        </p>
                        <div className="landing-hero-ctas">
                            <button className="btn btn-primary btn-lg" onClick={() => navigate('/signup')}>
                                <Sparkles size={18} />
                                Start Learning Free
                            </button>
                            <button className="btn btn-secondary btn-lg" onClick={() => navigate('/login')}>
                                <Play size={18} />
                                Watch Demo
                            </button>
                        </div>
                        <div className="landing-hero-trust">
                            <div className="landing-trust-item">
                                <CheckCircle2 size={16} />
                                <span>10,000+ Students</span>
                            </div>
                            <div className="landing-trust-item">
                                <CheckCircle2 size={16} />
                                <span>94% Success Rate</span>
                            </div>
                            <div className="landing-trust-item">
                                <CheckCircle2 size={16} />
                                <span>4.9/5 Rating</span>
                            </div>
                        </div>
                    </div>
                    <div className="landing-hero-visual animate-fade-in-up delay-200">
                        <div className="landing-hero-mockup">
                            <div className="mockup-header">
                                <div className="mockup-dots">
                                    <span /><span /><span />
                                </div>
                                <span className="mockup-title">Saarthi AI Tutor</span>
                            </div>
                            <div className="mockup-body">
                                <div className="mockup-msg mockup-msg-user">Explain Fourier Transform intuitively</div>
                                <div className="mockup-msg mockup-msg-ai">
                                    <div className="mockup-ai-header"><Brain size={14} /> Saarthi AI</div>
                                    Think of the Fourier Transform like a prism splitting white light into its component colors. Similarly, it decomposes a complex signal into its constituent frequencies...
                                </div>
                                <div className="mockup-typing">
                                    <span /><span /><span />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Features */}
            <section id="features" className="landing-features">
                <div className="container">
                    <div className="landing-section-header animate-fade-in-up">
                        <span className="badge badge-primary">Features</span>
                        <h2>Everything You Need to Excel</h2>
                        <p>Built specifically for technical education with AI that understands your subjects deeply</p>
                    </div>
                    <div className="landing-features-grid">
                        {features.map((f, i) => {
                            const Icon = f.icon;
                            return (
                                <div key={i} className={`landing-feature-card animate-fade-in-up delay-${(i % 3 + 1) * 100}`}>
                                    <div className="landing-feature-icon" style={{ background: f.bg, color: f.color }}>
                                        <Icon size={24} />
                                    </div>
                                    <h3>{f.title}</h3>
                                    <p>{f.desc}</p>
                                    <button className="landing-feature-link">
                                        Learn more <ChevronRight size={14} />
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* Differentiator */}
            <section className="landing-differ">
                <div className="container">
                    <div className="landing-differ-content animate-fade-in-up">
                        <div className="landing-differ-text">
                            <span className="badge badge-info">Why Saarthi?</span>
                            <h2>Better Than Generic AI for Technical Subjects</h2>
                            <p>Saarthi.ai is purpose-built for technical education, trained on curated academic content including lab datasets, handwritten notes, solved exercises, and 500+ video lectures.</p>
                            <div className="landing-differ-list">
                                <div className="landing-differ-item">
                                    <Shield size={20} style={{ color: 'var(--primary)' }} />
                                    <div>
                                        <strong>Domain-Specific AI</strong>
                                        <span>Deep knowledge in DSP, ML, CS</span>
                                    </div>
                                </div>
                                <div className="landing-differ-item">
                                    <GraduationCap size={20} style={{ color: 'var(--primary)' }} />
                                    <div>
                                        <strong>Structured Learning Paths</strong>
                                        <span>Modular, progressive curriculum</span>
                                    </div>
                                </div>
                                <div className="landing-differ-item">
                                    <BarChart3 size={20} style={{ color: 'var(--primary)' }} />
                                    <div>
                                        <strong>Comprehensive Analytics</strong>
                                        <span>Track mastery per concept</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div className="landing-differ-table">
                            <table>
                                <thead>
                                    <tr><th>Feature</th><th>ChatGPT</th><th>Saarthi.ai</th></tr>
                                </thead>
                                <tbody>
                                    <tr><td>Domain Knowledge</td><td>Broad, shallow</td><td className="highlight">Deep, specialized</td></tr>
                                    <tr><td>Problem Solving</td><td>Generic</td><td className="highlight">Subject-specific</td></tr>
                                    <tr><td>Learning Path</td><td>Random</td><td className="highlight">Structured</td></tr>
                                    <tr><td>Progress Tracking</td><td>None</td><td className="highlight">Comprehensive</td></tr>
                                    <tr><td>Content Source</td><td>Internet</td><td className="highlight">Curated academic</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </section>

            {/* Subjects */}
            <section id="subjects" className="landing-subjects">
                <div className="container">
                    <div className="landing-section-header animate-fade-in-up">
                        <span className="badge badge-primary">Subjects</span>
                        <h2>Specialized in Technical Education</h2>
                        <p>Trained on curated content from leading institutions</p>
                    </div>
                    <div className="landing-subjects-grid">
                        {subjects.map((s, i) => (
                            <div key={i} className="landing-subject-chip animate-fade-in-up delay-100">
                                <GraduationCap size={18} />
                                {s}
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Testimonials */}
            <section id="testimonials" className="landing-testimonials">
                <div className="container">
                    <div className="landing-section-header animate-fade-in-up">
                        <span className="badge badge-primary">Testimonials</span>
                        <h2>Loved by Students</h2>
                        <p>See what our learners have to say</p>
                    </div>
                    <div className="landing-testimonials-grid">
                        {testimonials.map((t, i) => (
                            <div key={i} className="landing-testimonial-card animate-fade-in-up delay-200">
                                <div className="landing-testimonial-stars">
                                    {Array.from({ length: t.rating }, (_, j) => (
                                        <Star key={j} size={16} fill="#F59E0B" color="#F59E0B" />
                                    ))}
                                </div>
                                <p className="landing-testimonial-text">"{t.text}"</p>
                                <div className="landing-testimonial-author">
                                    <div className="avatar avatar-md">{t.name.split(' ').map(n => n[0]).join('')}</div>
                                    <div>
                                        <p className="landing-testimonial-name">{t.name}</p>
                                        <p className="landing-testimonial-role">{t.role}</p>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* CTA */}
            <section className="landing-cta">
                <div className="container landing-cta-content animate-fade-in-up">
                    <h2>Ready to Transform Your Learning?</h2>
                    <p>Join thousands of students already mastering technical subjects with AI</p>
                    <button className="btn btn-lg landing-cta-btn" onClick={() => navigate('/signup')}>
                        Get Started Free <ArrowRight size={18} />
                    </button>
                </div>
            </section>

            {/* Footer */}
            <footer className="landing-footer">
                <div className="container">
                    <div className="landing-footer-grid">
                        <div className="landing-footer-brand">
                            <div className="landing-nav-brand">
                                <div className="landing-logo-icon"><LogoIcon size={20} /></div>
                                <span className="landing-logo-text" style={{ color: 'white' }}>Saarthi.ai</span>
                            </div>
                            <p>Your AI-powered learning companion for technical subjects. Empowering students with personalized AI tutoring.</p>
                            <div className="landing-footer-social">
                                <Users size={18} />
                                <span>50,000+ students & growing</span>
                            </div>
                        </div>
                        <div>
                            <h4>Platform</h4>
                            <a href="#features">Browse Courses</a>
                            <a href="#features">Exam Practice</a>
                            <a href="#features">Coding Lab</a>
                            <a href="#features">Video Library</a>
                        </div>
                        <div>
                            <h4>Company</h4>
                            <a href="#">About Us</a>
                            <a href="#">Our Story</a>
                            <a href="#">Careers</a>
                            <a href="#">Contact</a>
                        </div>
                        <div>
                            <h4>Support</h4>
                            <a href="#">Help Center</a>
                            <a href="#">FAQs</a>
                            <a href="#">Privacy Policy</a>
                            <a href="#">Terms of Service</a>
                        </div>
                    </div>
                    <div className="landing-footer-bottom">
                        <p>© 2026 Saarthi.ai. All rights reserved.</p>
                    </div>
                </div>
            </footer>
        </div>
    );
}
