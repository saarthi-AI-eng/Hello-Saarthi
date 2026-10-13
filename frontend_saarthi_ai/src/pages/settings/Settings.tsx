import { useState } from 'react';
import {
    User, Bell, Palette, Shield, Camera, Save, Moon, Sun, Monitor,
    LogOut, Trash2, Eye, EyeOff, Mail, Lock, Globe
} from 'lucide-react';
import { useAuthStore } from '../../stores/auth.store';
import { useSettingsStore } from '../../stores/settings.store';
import { getInitials } from '../../lib/utils';
import './Settings.css';

const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'appearance', label: 'Appearance', icon: Palette },
    { id: 'privacy', label: 'Privacy & Security', icon: Shield },
];

export default function SettingsPage() {
    const { user, logout } = useAuthStore();
    const { theme, fontSize, setTheme, setFontSize } = useSettingsStore();
    const [activeTab, setActiveTab] = useState('profile');
    const [saved, setSaved] = useState(false);

    // Profile form state
    const [profileName, setProfileName] = useState(user?.name || user?.fullName || '');
    const [profileEmail] = useState(user?.email || '');
    const [profileBio, setProfileBio] = useState('Computer Science Student | AI Enthusiast');
    const [profileInstitute, setProfileInstitute] = useState('NIT Raipur');

    // Notification toggles
    const [notifCourseUpdates, setNotifCourseUpdates] = useState(true);
    const [notifAssignments, setNotifAssignments] = useState(true);
    const [notifQuizReminders, setNotifQuizReminders] = useState(true);
    const [notifMarketing, setNotifMarketing] = useState(false);
    const [notifWeeklyReport, setNotifWeeklyReport] = useState(true);

    // Privacy
    const [profileVisibility, setProfileVisibility] = useState<'public' | 'private'>('public');
    const [showProgress, setShowProgress] = useState(true);

    const handleSave = () => {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
    };

    const initials = getInitials(profileName || 'U');

    return (
        <div className="settings-page">
            <div className="settings-header">
                <h1>Settings</h1>
                <p>Manage your account preferences and configuration</p>
            </div>

            <div className="settings-layout">
                {/* Tab Navigation */}
                <div className="settings-tabs">
                    {tabs.map((tab) => {
                        const Icon = tab.icon;
                        return (
                            <button
                                key={tab.id}
                                className={`settings-tab ${activeTab === tab.id ? 'active' : ''}`}
                                onClick={() => setActiveTab(tab.id)}
                            >
                                <Icon size={18} />
                                <span>{tab.label}</span>
                            </button>
                        );
                    })}
                </div>

                {/* Tab Content */}
                <div className="settings-content">
                    {/* ── Profile Tab ── */}
                    {activeTab === 'profile' && (
                        <div className="settings-panel animate-fade-in">
                            <h2>Profile Information</h2>
                            <p className="settings-panel-desc">Update your personal details and institute info</p>

                            <div className="settings-avatar-section">
                                <div className="settings-avatar">
                                    <span>{initials}</span>
                                </div>
                                <div>
                                    <button className="btn btn-outline btn-sm"><Camera size={14} /> Change Photo</button>
                                    <p className="settings-avatar-hint">JPG, PNG or SVG. Max 2MB</p>
                                </div>
                            </div>

                            <div className="settings-form">
                                <div className="settings-field">
                                    <label>Full Name</label>
                                    <div className="settings-input-wrap">
                                        <User size={16} />
                                        <input className="input" value={profileName} onChange={(e) => setProfileName(e.target.value)} />
                                    </div>
                                </div>
                                <div className="settings-field">
                                    <label>Email</label>
                                    <div className="settings-input-wrap">
                                        <Mail size={16} />
                                        <input className="input" value={profileEmail} disabled style={{ opacity: 0.6 }} />
                                    </div>
                                    <span className="settings-field-hint">Email cannot be changed</span>
                                </div>
                                <div className="settings-field">
                                    <label>Institute</label>
                                    <div className="settings-input-wrap">
                                        <Globe size={16} />
                                        <input className="input" value={profileInstitute} onChange={(e) => setProfileInstitute(e.target.value)} />
                                    </div>
                                </div>
                                <div className="settings-field">
                                    <label>Bio</label>
                                    <textarea className="input settings-textarea" value={profileBio} onChange={(e) => setProfileBio(e.target.value)} rows={3} />
                                </div>
                            </div>

                            <div className="settings-actions">
                                <button className="btn btn-primary" onClick={handleSave}>
                                    <Save size={16} /> {saved ? 'Saved ✓' : 'Save Changes'}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* ── Notifications Tab ── */}
                    {activeTab === 'notifications' && (
                        <div className="settings-panel animate-fade-in">
                            <h2>Notification Preferences</h2>
                            <p className="settings-panel-desc">Choose what notifications you want to receive</p>

                            <div className="settings-toggle-list">
                                <ToggleRow label="Course Updates" desc="Notifications about enrolled course changes" checked={notifCourseUpdates} onChange={setNotifCourseUpdates} />
                                <ToggleRow label="New Assignments" desc="Get notified when new assignments are posted" checked={notifAssignments} onChange={setNotifAssignments} />
                                <ToggleRow label="Quiz Reminders" desc="Reminders for upcoming quizzes and deadlines" checked={notifQuizReminders} onChange={setNotifQuizReminders} />
                                <ToggleRow label="Weekly Report" desc="Summary of your weekly study progress" checked={notifWeeklyReport} onChange={setNotifWeeklyReport} />
                                <ToggleRow label="Marketing Emails" desc="Promotional content and feature announcements" checked={notifMarketing} onChange={setNotifMarketing} />
                            </div>

                            <div className="settings-actions">
                                <button className="btn btn-primary" onClick={handleSave}>
                                    <Save size={16} /> {saved ? 'Saved ✓' : 'Save Preferences'}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* ── Appearance Tab ── */}
                    {activeTab === 'appearance' && (
                        <div className="settings-panel animate-fade-in">
                            <h2>Appearance</h2>
                            <p className="settings-panel-desc">Customize how Saarthi.ai looks and feels</p>

                            <div className="settings-section">
                                <h3>Theme</h3>
                                <div className="settings-theme-options">
                                    <button className={`theme-option ${theme === 'light' ? 'active' : ''}`} onClick={() => setTheme('light')}>
                                        <div className="theme-preview theme-preview-light">
                                            <Sun size={24} />
                                        </div>
                                        <span>Light</span>
                                    </button>
                                    <button className={`theme-option ${theme === 'dark' ? 'active' : ''}`} onClick={() => setTheme('dark')}>
                                        <div className="theme-preview theme-preview-dark">
                                            <Moon size={24} />
                                        </div>
                                        <span>Dark</span>
                                    </button>
                                    <button className={`theme-option ${theme === 'auto' ? 'active' : ''}`} onClick={() => setTheme('auto')}>
                                        <div className="theme-preview theme-preview-auto">
                                            <Monitor size={24} />
                                        </div>
                                        <span>System</span>
                                    </button>
                                </div>
                            </div>

                            <div className="settings-section">
                                <h3>Font Size</h3>
                                <div className="settings-font-options">
                                    {(['small', 'medium', 'large'] as const).map((size) => (
                                        <button
                                            key={size}
                                            className={`font-option ${fontSize === size ? 'active' : ''}`}
                                            onClick={() => setFontSize(size)}
                                        >
                                            <span className={`font-preview font-preview-${size}`}>Aa</span>
                                            <span>{size.charAt(0).toUpperCase() + size.slice(1)}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ── Privacy Tab ── */}
                    {activeTab === 'privacy' && (
                        <div className="settings-panel animate-fade-in">
                            <h2>Privacy & Security</h2>
                            <p className="settings-panel-desc">Control your privacy and account security</p>

                            <div className="settings-section">
                                <h3>Profile Visibility</h3>
                                <div className="settings-radio-group">
                                    <label className={`settings-radio ${profileVisibility === 'public' ? 'active' : ''}`}>
                                        <input type="radio" name="visibility" checked={profileVisibility === 'public'} onChange={() => setProfileVisibility('public')} />
                                        <Eye size={16} />
                                        <div>
                                            <span className="settings-radio-label">Public</span>
                                            <span className="settings-radio-desc">Anyone can see your profile</span>
                                        </div>
                                    </label>
                                    <label className={`settings-radio ${profileVisibility === 'private' ? 'active' : ''}`}>
                                        <input type="radio" name="visibility" checked={profileVisibility === 'private'} onChange={() => setProfileVisibility('private')} />
                                        <EyeOff size={16} />
                                        <div>
                                            <span className="settings-radio-label">Private</span>
                                            <span className="settings-radio-desc">Only you can see your profile</span>
                                        </div>
                                    </label>
                                </div>
                            </div>

                            <div className="settings-toggle-list">
                                <ToggleRow label="Show Progress Publicly" desc="Let others see your learning progress" checked={showProgress} onChange={setShowProgress} />
                            </div>

                            <div className="settings-section">
                                <h3>Change Password</h3>
                                <div className="settings-form" style={{ maxWidth: 400 }}>
                                    <div className="settings-field">
                                        <label>Current Password</label>
                                        <div className="settings-input-wrap">
                                            <Lock size={16} />
                                            <input className="input" type="password" placeholder="Enter current password" />
                                        </div>
                                    </div>
                                    <div className="settings-field">
                                        <label>New Password</label>
                                        <div className="settings-input-wrap">
                                            <Lock size={16} />
                                            <input className="input" type="password" placeholder="Enter new password" />
                                        </div>
                                    </div>
                                    <button className="btn btn-outline">Update Password</button>
                                </div>
                            </div>

                            <div className="settings-danger">
                                <h3>Danger Zone</h3>
                                <p className="settings-danger-desc">These actions are permanent and cannot be undone</p>
                                <div className="settings-danger-actions">
                                    <button className="btn btn-warning btn-sm" onClick={logout}>
                                        <LogOut size={16} /> Logout
                                    </button>
                                    <button className="btn btn-danger btn-sm">
                                        <Trash2 size={16} /> Delete Account
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

/* ── Toggle Row Component ── */
function ToggleRow({ label, desc, checked, onChange }: { label: string; desc: string; checked: boolean; onChange: (v: boolean) => void }) {
    return (
        <div className="settings-toggle-row">
            <div>
                <span className="settings-toggle-label">{label}</span>
                <span className="settings-toggle-desc">{desc}</span>
            </div>
            <button
                type="button"
                role="switch"
                aria-checked={checked}
                className={`settings-toggle ${checked ? 'checked' : ''}`}
                onClick={() => onChange(!checked)}
            >
                <span className="settings-toggle-slider" />
            </button>
        </div>
    );
}
