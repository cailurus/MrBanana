/**
 * Player configuration hook
 * Manages player settings with auto-save functionality
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { useToast } from '../components/Toast';
import { stableStringify } from '../utils/appHelpers';

/**
 * Hook for managing player configuration
 * Provides auto-save with debounce to prevent excessive API calls
 * 
 * @returns {Object} Player config state and handlers
 */
export function usePlayerConfig() {
    // Config state
    const [rootDir, setRootDir] = useState('');

    // UI state
    const [saving, setSaving] = useState(false);
    const [loading, setLoading] = useState(true);
    const [showSettings, setShowSettings] = useState(false);

    // Toast hook
    const toast = useToast();

    // Auto-save tracking refs
    const autoSaveReadyRef = useRef(false);
    const autoSaveSkipOnceRef = useRef(false);
    const lastSavedPayloadRef = useRef(null);

    /**
     * Fetch config from server
     */
    const fetchConfig = useCallback(async () => {
        setLoading(true);
        try {
            const res = await axios.get('/api/player/config');
            const cfg = res.data || {};

            if (typeof cfg.player_root_dir === 'string') {
                setRootDir(cfg.player_root_dir || '');
            }
        } catch (err) {
            console.error('Failed to fetch player config:', err);
        } finally {
            setLoading(false);
            autoSaveReadyRef.current = true;
            autoSaveSkipOnceRef.current = true;
        }
    }, []);

    /**
     * Save config to server
     */
    const saveConfig = useCallback(async (overridePayload = null) => {
        setSaving(true);
        try {
            const payload = overridePayload || {
                player_root_dir: String(rootDir || '').trim(),
            };

            lastSavedPayloadRef.current = stableStringify(payload);

            const res = await axios.post('/api/player/config', payload);
            const cfg = res.data || {};

            if (typeof cfg.player_root_dir === 'string') {
                autoSaveSkipOnceRef.current = true;
                setRootDir(cfg.player_root_dir || '');
                lastSavedPayloadRef.current = stableStringify({ player_root_dir: cfg.player_root_dir || '' });
            } else {
                lastSavedPayloadRef.current = stableStringify({ player_root_dir: String(payload.player_root_dir || '') });
            }
        } catch (err) {
            toast.error?.('Failed to save player config: ' + (err.response?.data?.detail || err.message));
        } finally {
            setSaving(false);
        }
    }, [rootDir]);

    // Auto-save effect with debounce
    useEffect(() => {
        if (!autoSaveReadyRef.current) return;
        if (autoSaveSkipOnceRef.current) {
            autoSaveSkipOnceRef.current = false;
            return;
        }

        const payload = {
            player_root_dir: String(rootDir || '').trim(),
        };

        const serialized = stableStringify(payload);
        if (serialized === lastSavedPayloadRef.current) return;

        const timer = window.setTimeout(async () => {
            if (saving) return;
            lastSavedPayloadRef.current = serialized;
            await saveConfig(payload);
        }, 450);

        return () => window.clearTimeout(timer);
    }, [rootDir, saving, saveConfig]);

    // Fetch config on mount
    useEffect(() => {
        fetchConfig();
    }, [fetchConfig]);

    return {
        // State values
        rootDir,

        // Setters
        setRootDir,

        // UI state
        saving,
        loading,
        showSettings,
        setShowSettings,

        // Actions
        fetchConfig,
        saveConfig,
    };
}

export default usePlayerConfig;
