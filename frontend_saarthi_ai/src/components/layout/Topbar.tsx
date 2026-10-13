import { useState } from 'react';
import { Search, Bell, ChevronDown, Menu, LogOut, User, Settings, Sun, Moon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/auth.store';
import { useSettingsStore } from '../../stores/settings.store';
import { getInitials } from '../../lib/utils';
import './Topbar.css';

export default function Topbar() {
    const [showProfile, setShowProfile] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const { user, isAuthenticated, logout } = useAuthStore();
    const { theme, setTheme } = useSettingsStore();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const toggleTheme = () => {
        const isDark = theme === 'dark' || (theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);
        setTheme(isDark ? 'light' : 'dark');
    };

    return (
        <header className="topbar">
            <div className="topbar-left">
                <button className="topbar-menu-btn" aria-label="Menu">
                    <Menu size={20} />
                </button>
            </div>

            {/* Search */}
            <div className="topbar-search">
                <Search size={18} className="topbar-search-icon" />
                <input
                    type="text"
                    placeholder="Search courses, materials, videos... (min 2 chars)"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && searchQuery.trim()) {
                            navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
                        }
                    }}
                    className="topbar-search-input"
                />
                <kbd className="topbar-search-kbd">⌘K</kbd>
            </div>

            {/* Right Actions */}
            <div className="topbar-actions">
                {/* Theme Toggle */}
                <button className="topbar-icon-btn" aria-label="Toggle theme" onClick={toggleTheme} title="Toggle Dark/Light Mode">
                    {theme === 'dark' || (theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches) ? (
                        <Sun size={20} />
                    ) : (
                        <Moon size={20} />
                    )}
                </button>
                {/* Notifications */}
                <button className="topbar-icon-btn" aria-label="Notifications">
                    <Bell size={20} />
                    <span className="topbar-notif-badge">3</span>
                </button>

                {/* Profile Dropdown */}
                <div className="topbar-profile-wrapper">
                    <button
                        className="topbar-profile"
                        onClick={() => setShowProfile(!showProfile)}
                    >
                        <div className="avatar avatar-md">
                            {user?.avatar ? (
                                <img src={user.avatar} alt={user.name} />
                            ) : (
                                getInitials(user?.name || 'User')
                            )}
                        </div>
                        <div className="topbar-profile-info">
                            <span className="topbar-profile-name">{isAuthenticated ? (user?.name || 'User') : 'Not signed in'}</span>
                            <span className="topbar-profile-role">{isAuthenticated ? (user?.role || 'user') : 'guest'}</span>
                        </div>
                        <ChevronDown size={16} />
                    </button>

                    {showProfile && (
                        <div className="topbar-dropdown animate-scale-in">
                            <div className="topbar-dropdown-header">
                                <div className="avatar avatar-lg">
                                    {getInitials(user?.name || 'User')}
                                </div>
                                <div>
                                    <p className="topbar-dropdown-name">{isAuthenticated ? (user?.name || 'User') : 'Not signed in'}</p>
                                    <p className="topbar-dropdown-email">{user?.email || '—'}</p>
                                </div>
                            </div>
                            <div className="topbar-dropdown-divider" />
                            <button className="topbar-dropdown-item" onClick={() => { navigate('/settings'); setShowProfile(false); }}>
                                <User size={16} /> Profile
                            </button>
                            <button className="topbar-dropdown-item" onClick={() => { navigate('/settings'); setShowProfile(false); }}>
                                <Settings size={16} /> Settings
                            </button>
                            <div className="topbar-dropdown-divider" />
                            <button className="topbar-dropdown-item topbar-dropdown-danger" onClick={handleLogout}>
                                <LogOut size={16} /> Sign Out
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </header>
    );
}
