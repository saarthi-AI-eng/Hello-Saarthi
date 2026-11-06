import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Theme = 'light' | 'dark' | 'auto';
type FontSize = 'small' | 'medium' | 'large';

interface SettingsState {
    theme: Theme;
    fontSize: FontSize;
    language: string;
    setTheme: (theme: Theme) => void;
    setFontSize: (size: FontSize) => void;
    setLanguage: (lang: string) => void;
}

function applyTheme(theme: Theme) {
    const root = document.documentElement;
    let effective: 'light' | 'dark' = 'light';

    if (theme === 'auto') {
        effective = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    } else {
        effective = theme;
    }

    root.setAttribute('data-theme', effective);
}

function applyFontSize(size: FontSize) {
    const root = document.documentElement;
    const sizes = { small: '14px', medium: '16px', large: '18px' };
    root.style.fontSize = sizes[size];
}

export const useSettingsStore = create<SettingsState>()(
    persist(
        (set) => ({
            theme: 'light',
            fontSize: 'medium',
            language: 'en',

            setTheme: (theme: Theme) => {
                applyTheme(theme);
                set({ theme });
            },

            setFontSize: (fontSize: FontSize) => {
                applyFontSize(fontSize);
                set({ fontSize });
            },

            setLanguage: (language: string) => {
                set({ language });
            },
        }),
        {
            name: 'saarthi-settings',
            onRehydrateStorage: () => {
                return (state) => {
                    if (state) {
                        applyTheme(state.theme);
                        applyFontSize(state.fontSize);
                    }
                };
            },
        }
    )
);

// Listen for system theme changes when 'auto' is selected
if (typeof window !== 'undefined') {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        const { theme } = useSettingsStore.getState();
        if (theme === 'auto') {
            applyTheme('auto');
        }
    });
}
