/**
 * Download Store - manages download-related state
 * Includes: url input, loading, history, active tasks, config
 */
import { create } from 'zustand';
import axios from 'axios';

/**
 * Default download configuration
 */
const DEFAULT_CONFIG = {
    outputDir: '',
    scrapeAfter: false,
    useProxy: false,
    proxyUrl: '',
    resolution: 'best',
    workers: 16,
    filenameFormat: '{id}',
};

/**
 * Download Store
 */
export const useDownloadStore = create((set, get) => ({
    // Input state
    url: '',
    setUrl: (url) => set({ url }),

    // Loading state
    loading: false,
    setLoading: (loading) => set({ loading }),

    // History & tasks
    history: [],
    activeTasks: [],
    setHistory: (history) => set({ history: Array.isArray(history) ? history : [] }),
    setActiveTasks: (tasks) => set({ activeTasks: Array.isArray(tasks) ? tasks : [] }),

    // Clearing state
    clearingHistory: false,
    setClearingHistory: (clearing) => set({ clearingHistory: clearing }),

    // Config state
    config: { ...DEFAULT_CONFIG },
    configSaving: false,
    configReady: false,

    // Config setters
    setConfig: (config) => set({ config: { ...get().config, ...config } }),
    setConfigField: (field, value) => set({ config: { ...get().config, [field]: value } }),
    setConfigSaving: (saving) => set({ configSaving: saving }),
    setConfigReady: (ready) => set({ configReady: ready }),

    // Actions
    fetchHistory: async () => {
        try {
            const res = await axios.get('/api/history', { params: { limit: 50 } });
            set({ history: Array.isArray(res.data) ? res.data : [] });
        } catch (err) {
            console.error('Failed to fetch history', err);
            set({ history: [] });
        }
    },

    fetchConfig: async () => {
        try {
            const res = await axios.get('/api/download/config');
            const cfg = res.data || {};
            set({
                config: {
                    outputDir: typeof cfg.output_dir === 'string' ? cfg.output_dir || '' : '',
                    scrapeAfter: typeof cfg.download_scrape_after_default === 'boolean' ? cfg.download_scrape_after_default : false,
                    useProxy: typeof cfg.download_use_proxy === 'boolean' ? cfg.download_use_proxy : false,
                    proxyUrl: typeof cfg.download_proxy_url === 'string' ? cfg.download_proxy_url : '',
                    resolution: typeof cfg.download_resolution === 'string' ? cfg.download_resolution || 'best' : 'best',
                    workers: typeof cfg.max_download_workers === 'number' ? Math.max(1, Math.min(128, cfg.max_download_workers)) : 16,
                    filenameFormat: typeof cfg.filename_format === 'string' ? cfg.filename_format || '{id}' : '{id}',
                },
                configReady: true,
            });
        } catch (err) {
            console.error('Failed to fetch download config', err);
            set({ configReady: true });
        }
    },

    saveConfig: async (overrideConfig = null) => {
        const { config: storeConfig, configSaving } = get();
        if (configSaving) return;

        // 使用 override 或当前 store 的配置
        const config = overrideConfig ? { ...storeConfig, ...overrideConfig } : storeConfig;

        set({ configSaving: true });
        try {
            await axios.post('/api/download/config', {
                output_dir: String(config.outputDir || '').trim(),
                download_scrape_after_default: Boolean(config.scrapeAfter),
                download_use_proxy: Boolean(config.useProxy),
                download_proxy_url: String(config.proxyUrl || ''),
                download_resolution: String(config.resolution || 'best'),
                max_download_workers: Number(config.workers || 16),
                filename_format: String(config.filenameFormat || '{id}'),
            });
        } catch (err) {
            console.error('Failed to save download config', err);
        } finally {
            set({ configSaving: false });
        }
    },

    startDownload: async (url, options = {}) => {
        const { loading } = get();
        if (loading) return null;

        set({ loading: true });
        try {
            const res = await axios.post('/api/download', {
                url,
                scrape_after: options.scrapeAfter,
            });
            set({ url: '' });
            return res.data;
        } catch (err) {
            console.error('Failed to start download', err);
            throw err;
        } finally {
            set({ loading: false });
        }
    },

    resumeTask: async (id) => {
        try {
            await axios.post(`/api/download/${id}/resume`);
        } catch (err) {
            console.error('Failed to resume task', err);
            throw err;
        }
    },

    pauseTask: async (id) => {
        try {
            await axios.post(`/api/download/${id}/pause`);
        } catch (err) {
            console.error('Failed to pause task', err);
            throw err;
        }
    },

    deleteTask: async (id) => {
        try {
            await axios.delete(`/api/download/${id}`);
        } catch (err) {
            console.error('Failed to delete task', err);
            throw err;
        }
    },

    clearHistory: async () => {
        const { clearingHistory } = get();
        if (clearingHistory) return;

        set({ clearingHistory: true });
        try {
            await axios.post('/api/download/history/clear');
            set({ history: [] });
        } catch (err) {
            console.error('Failed to clear history', err);
            throw err;
        } finally {
            set({ clearingHistory: false });
        }
    },

    // Search state
    searchQuery: '',
    setSearchQuery: (query) => set({ searchQuery: query }),

    searchResult: null,
    setSearchResult: (result) => set({ searchResult: result }),

    searching: false,
    setSearching: (searching) => set({ searching }),

    searchError: null,
    setSearchError: (error) => set({ searchError: error }),

    // Search action
    search: async (code) => {
        const { searching } = get();
        if (searching) return null;

        if (!code || !code.trim()) {
            set({ searchResult: null, searchError: null });
            return null;
        }

        set({ searching: true, searchError: null });
        try {
            const res = await axios.get(`/api/search/${encodeURIComponent(code.trim())}`);
            set({ searchResult: res.data });
            return res.data;
        } catch (err) {
            console.error('Failed to search', err);
            set({
                searchError: err.response?.data?.detail || err.message,
                searchResult: null
            });
            throw err;
        } finally {
            set({ searching: false });
        }
    },

    clearSearchResult: () => set({ searchResult: null, searchError: null, searchQuery: '' }),
}));

export default useDownloadStore;
