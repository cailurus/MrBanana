/**
 * Shared animation and audio hooks
 * Extracted from App.jsx for reuse across Tab components
 */
import { useRef, useCallback, useEffect, useState } from 'react';
import settingsOpenSfxUrl from '../assets/gear_11.m4a';
import brushCleanSfxUrl from '../assets/brush-clean.m4a';

/**
 * Audio instance management
 */
const audioInstances = {
    settingsOpen: null,
    brushClean: null,
    initialized: false,
};

function initAudio() {
    if (audioInstances.initialized) return;
    audioInstances.initialized = true;

    try {
        audioInstances.settingsOpen = new Audio(settingsOpenSfxUrl);
        audioInstances.settingsOpen.preload = 'auto';
        audioInstances.settingsOpen.volume = 0.35;
    } catch {
        audioInstances.settingsOpen = null;
    }

    try {
        audioInstances.brushClean = new Audio(brushCleanSfxUrl);
        audioInstances.brushClean.preload = 'auto';
        audioInstances.brushClean.volume = 0.35;
    } catch {
        audioInstances.brushClean = null;
    }
}

export function playSettingsOpenSfx() {
    initAudio();
    try {
        const a = audioInstances.settingsOpen;
        if (!a) return;
        a.currentTime = 0;
        const p = a.play();
        if (p && typeof p.catch === 'function') p.catch(() => { });
    } catch {
        // ignore
    }
}

export function stopSettingsOpenSfx() {
    try {
        const a = audioInstances.settingsOpen;
        if (!a) return;
        a.pause();
        a.currentTime = 0;
    } catch {
        // ignore
    }
}

export function playBrushCleanSfx() {
    initAudio();
    try {
        const a = audioInstances.brushClean;
        if (!a) return;
        a.currentTime = 0;
        const p = a.play();
        if (p && typeof p.catch === 'function') p.catch(() => { });
    } catch {
        // ignore
    }
}

/**
 * Gear spin animation hook
 */
export function useGearAnimation() {
    const [spinning, setSpinning] = useState(false);
    const animatingRef = useRef(false);
    const timerRef = useRef(null);

    const start = useCallback(() => {
        animatingRef.current = true;
        setSpinning(false);
        window.requestAnimationFrame(() => setSpinning(true));

        if (timerRef.current) {
            window.clearTimeout(timerRef.current);
            timerRef.current = null;
        }

        timerRef.current = window.setTimeout(() => {
            setSpinning(false);
            animatingRef.current = false;
            timerRef.current = null;
        }, 1000);
    }, []);

    const isAnimating = useCallback(() => animatingRef.current, []);

    useEffect(() => {
        return () => {
            if (timerRef.current) {
                window.clearTimeout(timerRef.current);
                timerRef.current = null;
            }
        };
    }, []);

    return { spinning, start, isAnimating };
}

/**
 * Broom sweep animation hook
 */
export function useBroomAnimation() {
    const [sweeping, setSweeping] = useState(false);
    const animatingRef = useRef(false);
    const timerRef = useRef(null);

    const start = useCallback(() => {
        if (animatingRef.current) return;
        animatingRef.current = true;
        setSweeping(false);
        window.requestAnimationFrame(() => setSweeping(true));

        if (timerRef.current) {
            window.clearTimeout(timerRef.current);
            timerRef.current = null;
        }

        timerRef.current = window.setTimeout(() => {
            setSweeping(false);
            animatingRef.current = false;
            timerRef.current = null;
        }, 650);
    }, []);

    const isAnimating = useCallback(() => animatingRef.current, []);

    useEffect(() => {
        return () => {
            if (timerRef.current) {
                window.clearTimeout(timerRef.current);
                timerRef.current = null;
            }
        };
    }, []);

    return { sweeping, start, isAnimating };
}

/**
 * Auto-save hook for config changes
 */
export function useAutoSave(config, saveFn, options = {}) {
    const { delay = 450, enabled = true } = options;
    const readyRef = useRef(false);
    const skipOnceRef = useRef(false);
    const lastSavedRef = useRef('');
    const savingRef = useRef(false);

    const markReady = useCallback(() => {
        readyRef.current = true;
        skipOnceRef.current = true;
    }, []);

    useEffect(() => {
        if (!enabled || !readyRef.current) return;
        if (skipOnceRef.current) {
            skipOnceRef.current = false;
            return;
        }

        const serialized = JSON.stringify(config);
        if (serialized === lastSavedRef.current) return;

        const t = window.setTimeout(async () => {
            if (savingRef.current) return;
            savingRef.current = true;
            lastSavedRef.current = serialized;
            try {
                await saveFn(config);
            } catch {
                // ignore
            } finally {
                savingRef.current = false;
            }
        }, delay);

        return () => window.clearTimeout(t);
    }, [config, saveFn, delay, enabled]);

    return { markReady };
}
