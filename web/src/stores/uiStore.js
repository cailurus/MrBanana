/**
 * UI Store - manages UI-related state
 * Includes: language, theme, active tab, pickers, animations
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { detectDefaultUiLang } from '../i18n';

/**
 * UI Store
 */
export const useUIStore = create(
    persist(
        (set, get) => ({
            // Language
            uiLang: detectDefaultUiLang(),
            setUiLang: (lang) => set({ uiLang: lang }),

            // Theme
            themeMode: 'system', // 'light' | 'dark' | 'system'
            setThemeMode: (mode) => set({ themeMode: mode }),

            // Active tab
            activeTab: 'download', // 'download' | 'player' | 'scrape'
            setActiveTab: (tab) => set({ activeTab: tab }),

            // Pickers visibility
            showLangPicker: false,
            showThemePicker: false,
            setShowLangPicker: (show) => set({ showLangPicker: show }),
            setShowThemePicker: (show) => set({ showThemePicker: show }),
            closeAllPickers: () => set({ showLangPicker: false, showThemePicker: false }),

            // Settings panels visibility
            showDownloadSettings: false,
            showDownloadAdvanced: false,
            downloadAdvancedTab: 'download',
            setShowDownloadSettings: (show) => set({ showDownloadSettings: show }),
            setShowDownloadAdvanced: (show) => set({ showDownloadAdvanced: show }),
            setDownloadAdvancedTab: (tab) => set({ downloadAdvancedTab: tab }),
            toggleDownloadSettings: () => set((state) => ({ showDownloadSettings: !state.showDownloadSettings })),

            showScrapeSettings: false,
            showScrapeAdvanced: false,
            scrapeAdvancedTab: 'trigger',
            setShowScrapeSettings: (show) => set({ showScrapeSettings: show }),
            setShowScrapeAdvanced: (show) => set({ showScrapeAdvanced: show }),
            setScrapeAdvancedTab: (tab) => set({ scrapeAdvancedTab: tab }),
            toggleScrapeSettings: () => set((state) => ({ showScrapeSettings: !state.showScrapeSettings })),

            showPlayerSettings: false,
            setShowPlayerSettings: (show) => set({ showPlayerSettings: show }),
            togglePlayerSettings: () => set((state) => ({ showPlayerSettings: !state.showPlayerSettings })),

            // Gear spin animations
            downloadGearSpin: false,
            scrapeGearSpin: false,
            playerGearSpin: false,
            setDownloadGearSpin: (spin) => set({ downloadGearSpin: spin }),
            setScrapeGearSpin: (spin) => set({ scrapeGearSpin: spin }),
            setPlayerGearSpin: (spin) => set({ playerGearSpin: spin }),

            // Broom sweep animations
            downloadBroomSweep: false,
            scrapeBroomSweep: false,
            setDownloadBroomSweep: (sweep) => set({ downloadBroomSweep: sweep }),
            setScrapeBroomSweep: (sweep) => set({ scrapeBroomSweep: sweep }),

            // Directory picker
            dirPickerField: null,
            setDirPickerField: (field) => set({ dirPickerField: field }),

            // Log viewer
            logViewer: { open: false, kind: 'download', id: null, file: null },
            setLogViewer: (viewer) => set({ logViewer: viewer }),
            openLogViewer: (viewer) => set({ logViewer: { ...viewer, open: true } }),
            closeLogViewer: () => set({ logViewer: { open: false, kind: 'download', id: null, file: null } }),

            // Context menu
            contextMenu: null,
            setContextMenu: (menu) => set({ contextMenu: menu }),
            closeContextMenu: () => set({ contextMenu: null }),
        }),
        {
            name: 'mr-banana-ui',
            partialize: (state) => ({
                uiLang: state.uiLang,
                themeMode: state.themeMode,
                activeTab: state.activeTab,
            }),
            // Migrate from legacy keys
            migrate: (persistedState, version) => {
                if (version === 0) {
                    // Check for legacy localStorage keys
                    const legacyLang = localStorage.getItem('banana-ui-lang') || localStorage.getItem('mrjet-ui-lang');
                    const legacyTheme = localStorage.getItem('banana-theme-mode') || localStorage.getItem('mrjet-theme-mode');
                    const legacyTab = localStorage.getItem('banana-active-tab') || localStorage.getItem('mrjet-active-tab');

                    return {
                        ...persistedState,
                        uiLang: legacyLang || persistedState.uiLang,
                        themeMode: legacyTheme || persistedState.themeMode,
                        activeTab: legacyTab || persistedState.activeTab,
                    };
                }
                return persistedState;
            },
            version: 1,
        }
    )
);

/**
 * Apply theme to document
 * Should be called when themeMode changes
 */
export function applyTheme(themeMode) {
    const root = document.documentElement;
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)') || null;
    const isDark = themeMode === 'dark' || (themeMode === 'system' && mq?.matches);
    root.classList.toggle('dark', isDark);
}

/**
 * Subscribe to system theme changes
 * Returns cleanup function
 */
export function subscribeToSystemTheme(themeMode, callback) {
    if (themeMode !== 'system') return () => { };

    const mq = window.matchMedia?.('(prefers-color-scheme: dark)');
    if (!mq) return () => { };

    try {
        mq.addEventListener('change', callback);
        return () => mq.removeEventListener('change', callback);
    } catch {
        // Safari < 14
        mq.addListener(callback);
        return () => mq.removeListener(callback);
    }
}

export default useUIStore;
