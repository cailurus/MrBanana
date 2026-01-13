import { useState, useEffect, useCallback } from 'react';

/**
 * Hook for persisted state in localStorage
 * 
 * @param {string} key - Storage key
 * @param {*} defaultValue - Default value if not found
 * @param {Object} [options] - Options
 * @param {string[]} [options.legacyKeys] - Legacy keys to check for migration
 * @returns {[*, function]} - State value and setter
 */
export function usePersistedState(key, defaultValue, options = {}) {
    const { legacyKeys = [] } = options;

    const [value, setValue] = useState(() => {
        try {
            // Check current key first
            const stored = window.localStorage.getItem(key);
            if (stored !== null) {
                return JSON.parse(stored);
            }

            // Check legacy keys for migration
            for (const legacyKey of legacyKeys) {
                const legacyValue = window.localStorage.getItem(legacyKey);
                if (legacyValue !== null) {
                    // Migrate to new key
                    window.localStorage.setItem(key, legacyValue);
                    return JSON.parse(legacyValue);
                }
            }

            return defaultValue;
        } catch {
            return defaultValue;
        }
    });

    useEffect(() => {
        try {
            window.localStorage.setItem(key, JSON.stringify(value));
        } catch {
            // Storage quota exceeded or other error
        }
    }, [key, value]);

    return [value, setValue];
}

/**
 * Hook for string-based persisted state (no JSON parsing)
 * For simple string values like language codes, theme modes
 */
export function usePersistedString(key, defaultValue, legacyKeys = []) {
    const [value, setValue] = useState(() => {
        try {
            const stored = window.localStorage.getItem(key);
            if (stored !== null) return stored;

            for (const legacyKey of legacyKeys) {
                const legacyValue = window.localStorage.getItem(legacyKey);
                if (legacyValue !== null) {
                    window.localStorage.setItem(key, legacyValue);
                    return legacyValue;
                }
            }

            return defaultValue;
        } catch {
            return defaultValue;
        }
    });

    useEffect(() => {
        try {
            window.localStorage.setItem(key, value);
        } catch {
            // ignore
        }
    }, [key, value]);

    return [value, setValue];
}

/**
 * Hook for theme mode management
 * Handles system preference detection and dark class toggling
 * 
 * @param {string} [storageKey='mr-banana-theme-mode'] - Storage key
 * @returns {Object} - Theme state and handlers
 */
export function useTheme(storageKey = 'mr-banana-theme-mode') {
    const [themeMode, setThemeMode] = usePersistedString(storageKey, 'system', [
        'banana-theme-mode',
        'mrjet-theme-mode',
    ]);

    useEffect(() => {
        const root = document.documentElement;
        const mq = window.matchMedia?.('(prefers-color-scheme: dark)') || null;

        const apply = () => {
            const isDark = themeMode === 'dark' || (themeMode === 'system' && mq?.matches);
            root.classList.toggle('dark', isDark);
        };

        apply();

        if (!mq || themeMode !== 'system') return;

        try {
            mq.addEventListener('change', apply);
            return () => mq.removeEventListener('change', apply);
        } catch {
            // Safari < 14
            mq.addListener(apply);
            return () => mq.removeListener(apply);
        }
    }, [themeMode]);

    const isDark = useCallback(() => {
        if (themeMode === 'dark') return true;
        if (themeMode === 'light') return false;
        return window.matchMedia?.('(prefers-color-scheme: dark)')?.matches ?? false;
    }, [themeMode]);

    return {
        themeMode,
        setThemeMode,
        isDark: isDark(),
    };
}

/**
 * Hook for UI language management
 * 
 * @param {function} detectDefault - Function to detect default language
 * @param {string} [storageKey='mr-banana-ui-lang'] - Storage key
 * @returns {Object} - Language state and handlers
 */
export function useLanguage(detectDefault, storageKey = 'mr-banana-ui-lang') {
    const [uiLang, setUiLang] = usePersistedString(storageKey, detectDefault(), [
        'banana-ui-lang',
        'mrjet-ui-lang',
    ]);

    return {
        uiLang,
        setUiLang,
    };
}

/**
 * Hook for active tab management
 * 
 * @param {string} [defaultTab='download'] - Default tab
 * @param {string} [storageKey='mr-banana-active-tab'] - Storage key
 * @returns {[string, function]} - Active tab and setter
 */
export function useActiveTab(defaultTab = 'download', storageKey = 'mr-banana-active-tab') {
    return usePersistedString(storageKey, defaultTab, [
        'banana-active-tab',
        'mrjet-active-tab',
    ]);
}

/**
 * Hook for debounced value
 * 
 * @param {*} value - Value to debounce
 * @param {number} [delay=300] - Debounce delay in ms
 * @returns {*} - Debounced value
 */
export function useDebounce(value, delay = 300) {
    const [debouncedValue, setDebouncedValue] = useState(value);

    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);

        return () => clearTimeout(timer);
    }, [value, delay]);

    return debouncedValue;
}

/**
 * Hook for interval-based polling
 * 
 * @param {function} callback - Function to call on interval
 * @param {number|null} delay - Interval in ms (null to disable)
 */
export function useInterval(callback, delay) {
    const savedCallback = useCallback(callback, [callback]);

    useEffect(() => {
        if (delay === null) return;

        const id = setInterval(savedCallback, delay);
        return () => clearInterval(id);
    }, [savedCallback, delay]);
}

/**
 * Hook for media query detection
 * 
 * @param {string} query - Media query string
 * @returns {boolean} - Whether the query matches
 */
export function useMediaQuery(query) {
    const [matches, setMatches] = useState(() => {
        if (typeof window === 'undefined') return false;
        return window.matchMedia?.(query)?.matches ?? false;
    });

    useEffect(() => {
        const mq = window.matchMedia?.(query);
        if (!mq) return;

        const handler = (e) => setMatches(e.matches);

        try {
            mq.addEventListener('change', handler);
            return () => mq.removeEventListener('change', handler);
        } catch {
            mq.addListener(handler);
            return () => mq.removeListener(handler);
        }
    }, [query]);

    return matches;
}

/**
 * Hook for detecting mobile viewport
 * 
 * @param {number} [breakpoint=768] - Mobile breakpoint in px
 * @returns {boolean} - Whether viewport is mobile
 */
export function useIsMobile(breakpoint = 768) {
    return useMediaQuery(`(max-width: ${breakpoint - 1}px)`);
}

export default {
    usePersistedState,
    usePersistedString,
    useTheme,
    useLanguage,
    useActiveTab,
    useDebounce,
    useInterval,
    useMediaQuery,
    useIsMobile,
};
