/**
 * Player Store - manages player-related state
 * Includes: config, library items, player detail modal
 */
import { create } from 'zustand';
import axios from 'axios';

/**
 * Default player configuration
 */
const DEFAULT_PLAYER_CONFIG = {
    player_root_dir: '',
};

/**
 * Player Store
 */
export const usePlayerStore = create((set, get) => ({
    // Config
    config: { ...DEFAULT_PLAYER_CONFIG },
    configSaving: false,
    configReady: false,

    // Library items
    libraryItems: [],
    libraryLoading: false,

    // Detail modal
    detail: { open: false, item: null, playing: false },

    // Config actions
    setConfig: (config) => set({ config: { ...get().config, ...config } }),
    setConfigField: (field, value) => set({ config: { ...get().config, [field]: value } }),
    setConfigSaving: (saving) => set({ configSaving: saving }),
    setConfigReady: (ready) => set({ configReady: ready }),

    // Library actions
    setLibraryItems: (items) => set({ libraryItems: Array.isArray(items) ? items : [] }),
    setLibraryLoading: (loading) => set({ libraryLoading: loading }),

    // Detail modal actions
    openDetail: (item) => set({ detail: { open: true, item, playing: false } }),
    closeDetail: () => set({ detail: { open: false, item: null, playing: false } }),
    startPlaying: () => set((state) => ({ detail: { ...state.detail, playing: true } })),
    stopPlaying: () => set((state) => ({ detail: { ...state.detail, playing: false } })),

    // API actions
    fetchConfig: async () => {
        try {
            const res = await axios.get('/api/player/config');
            const cfg = res.data || {};
            set({
                config: {
                    player_root_dir: typeof cfg.player_root_dir === 'string' ? cfg.player_root_dir : '',
                },
                configReady: true,
            });
        } catch (err) {
            console.error('Failed to fetch player config', err);
            set({ configReady: true });
        }
    },

    saveConfig: async () => {
        const { config, configSaving } = get();
        if (configSaving) return;

        set({ configSaving: true });
        try {
            await axios.post('/api/player/config', {
                player_root_dir: String(config.player_root_dir || ''),
            });
        } catch (err) {
            console.error('Failed to save player config', err);
            throw err;
        } finally {
            set({ configSaving: false });
        }
    },

    fetchLibrary: async () => {
        const { libraryLoading, config } = get();
        if (libraryLoading) return;

        const playerRootDir = String(config.player_root_dir || '').trim();
        if (!playerRootDir) {
            set({ libraryItems: [] });
            return;
        }

        set({ libraryLoading: true });
        try {
            const res = await axios.get('/api/library/items');
            set({ libraryItems: Array.isArray(res.data) ? res.data : [] });
        } catch (err) {
            console.error('Failed to fetch library', err);
            set({ libraryItems: [] });
        } finally {
            set({ libraryLoading: false });
        }
    },
}));

export default usePlayerStore;
