/**
 * Scrape Store - manages scrape-related state
 * Includes: config, jobs, history, items, live state, detail modal
 */
import { create } from 'zustand';
import axios from 'axios';

/**
 * Stable JSON.stringify for deep comparison
 */
function stableStringify(obj) {
    if (obj === null || obj === undefined) return String(obj);
    if (typeof obj !== 'object') return JSON.stringify(obj);
    if (Array.isArray(obj)) return '[' + obj.map(stableStringify).join(',') + ']';
    const keys = Object.keys(obj).sort();
    return '{' + keys.map((k) => JSON.stringify(k) + ':' + stableStringify(obj[k])).join(',') + '}';
}

/**
 * Clean config payload - remove legacy keys
 */
function cleanConfigPayload(config) {
    const payload = { ...config };
    delete payload.scrape_sources_fallback;
    delete payload.scrape_sources_directors;
    delete payload.scrape_sources_series;
    delete payload.scrape_sources_want;
    return payload;
}

/**
 * Default scrape configuration
 * Note: Simplified sources - only JavTrailers for most fields, DMM for plot, Jav321 for rating
 */
export const DEFAULT_SCRAPE_CONFIG = {
    scrape_dir: '',
    scrape_output_dir: '',
    scrape_structure: '',
    scrape_rename: true,
    scrape_copy_source: false,
    scrape_existing_action: 'skip',

    scrape_threads: 1,
    scrape_thread_delay_sec: 0,

    scrape_use_proxy: false,
    scrape_proxy_url: '',

    scrape_sources_title: ['javtrailers'],
    scrape_sources_plot: ['dmm'],
    scrape_sources_actors: ['javtrailers'],
    scrape_sources_fanart: ['javtrailers'],
    scrape_sources_poster: ['javtrailers'],
    scrape_sources_previews: ['javtrailers'],
    scrape_sources_trailer: ['javtrailers'],
    scrape_sources_tags: ['javtrailers'],
    scrape_sources_release: ['javtrailers'],
    scrape_sources_runtime: ['javtrailers'],
    scrape_sources_studio: ['javtrailers'],
    scrape_sources_publisher: ['javtrailers'],
    scrape_sources_rating: ['jav321'],

    scrape_download_poster: true,
    scrape_download_fanart: true,
    scrape_download_previews: true,
    scrape_download_trailer: true,
    scrape_download_subtitle: true,
    scrape_preview_limit: 8,
    scrape_write_nfo: true,
    scrape_nfo_fields: [
        'title',
        'originaltitle',
        'id',
        'website',
        'plot',
        'release',
        'studio',
        'actors',
        'tags',
        'runtime',
        'resolution',
        'artwork',
    ],

    scrape_translate_enabled: true,
    scrape_translate_provider: 'google',
    scrape_translate_target_lang: 'zh-CN',
    scrape_translate_base_url: '',
    scrape_translate_api_key: '',
    scrape_translate_email: '',

    scrape_trigger_mode: 'manual',
    scrape_trigger_interval_sec: 3600,
    scrape_trigger_watch_poll_sec: 10,
    scrape_trigger_watch_min_age_sec: 300,
    scrape_trigger_watch_quiet_sec: 30,
};

/**
 * Scrape Store
 */
export const useScrapeStore = create((set, get) => ({
    // Config
    config: { ...DEFAULT_SCRAPE_CONFIG },
    configSaving: false,
    autoSaveReady: false,
    autoSaveSkipOnce: false,
    lastSavedPayload: '',

    // Jobs & History
    jobs: [],
    history: [],
    items: [],

    // Fetch timestamps (for throttling)
    lastJobsFetchAt: 0,
    lastHistoryFetchAt: 0,

    // Status
    loading: false,
    clearingHistory: false,
    pendingCount: null,
    pendingChecking: false,

    // Live state (for progress tracking)
    liveState: { jobId: null, state: {} },
    logOffset: 0,
    lastPreviewFile: '',

    // Detail modal
    detail: { open: false, item: null },

    // Settings panel UI state
    showSettings: false,
    showAdvanced: false,
    advancedTab: 'trigger',

    // Source test state
    sourceTestState: {},

    // Config actions
    setConfig: (config) => set({ config: { ...get().config, ...config } }),
    setConfigField: (field, value) => set({ config: { ...get().config, [field]: value } }),
    setConfigSaving: (saving) => set({ configSaving: saving }),
    setAutoSaveReady: (ready) => set({ autoSaveReady: ready }),
    setAutoSaveSkipOnce: (skip) => set({ autoSaveSkipOnce: skip }),
    setLastSavedPayload: (payload) => set({ lastSavedPayload: payload }),

    // Data setters
    setJobs: (jobs) => set({ jobs: Array.isArray(jobs) ? jobs : [] }),
    setHistory: (history) => set({ history: Array.isArray(history) ? history : [] }),
    setItems: (items) => set({ items: Array.isArray(items) ? items : [] }),
    setLoading: (loading) => set({ loading }),
    setClearingHistory: (clearing) => set({ clearingHistory: clearing }),
    setPendingCount: (count) => set({ pendingCount: count }),
    setPendingChecking: (checking) => set({ pendingChecking: checking }),
    setLiveState: (stateOrUpdater) => {
        if (typeof stateOrUpdater === 'function') {
            set({ liveState: stateOrUpdater(get().liveState) });
        } else {
            set({ liveState: stateOrUpdater });
        }
    },
    setLogOffset: (offset) => set({ logOffset: offset }),
    setLastPreviewFile: (file) => set({ lastPreviewFile: file }),
    setSourceTestState: (stateOrUpdater) => {
        if (typeof stateOrUpdater === 'function') {
            set({ sourceTestState: stateOrUpdater(get().sourceTestState) });
        } else {
            set({ sourceTestState: stateOrUpdater });
        }
    },

    // UI state setters
    setShowSettings: (show) => set({ showSettings: show }),
    setShowAdvanced: (show) => set({ showAdvanced: show }),
    setAdvancedTab: (tab) => set({ advancedTab: tab }),
    toggleSettings: () => set({ showSettings: !get().showSettings }),
    toggleAdvanced: () => set({ showAdvanced: !get().showAdvanced }),

    // Detail modal actions
    openDetail: (item) => set({ detail: { open: true, item } }),
    closeDetail: () => set({ detail: { open: false, item: null } }),

    // Computed values
    hasRunningJob: () => {
        const { jobs } = get();
        return (jobs || []).some((j) => j.status === 'Running' || j.status === 'Starting');
    },

    getLatestJob: () => {
        const { jobs } = get();
        if (!Array.isArray(jobs) || jobs.length === 0) return null;

        const active = jobs
            .filter((j) => j && (j.status === 'Running' || j.status === 'Starting'))
            .sort((a, b) => Number(b.id || 0) - Number(a.id || 0));
        if (active.length) return active[0];

        const sorted = [...jobs].sort((a, b) => Number(b.id || 0) - Number(a.id || 0));
        return sorted[0] || null;
    },

    // Config helpers
    getConfigPayload: () => cleanConfigPayload(get().config),
    getConfigHash: () => stableStringify(cleanConfigPayload(get().config)),

    // API actions
    fetchConfig: async () => {
        try {
            const res = await axios.get('/api/scrape/config');
            const cfg = res.data || {};
            if (cfg && typeof cfg === 'object') {
                const next = cleanConfigPayload(cfg);
                const merged = { ...get().config, ...next };
                set({
                    config: merged,
                    autoSaveReady: true,
                    autoSaveSkipOnce: true,
                    lastSavedPayload: stableStringify(cleanConfigPayload(merged)),
                });
            }
        } catch (err) {
            console.error('Failed to fetch scrape config', err);
            set({ autoSaveReady: true, autoSaveSkipOnce: true });
        }
    },

    saveConfig: async (showToast = false) => {
        const { config, configSaving, lastSavedPayload } = get();
        if (configSaving) return;

        const payload = cleanConfigPayload(config);
        const serialized = stableStringify(payload);

        // Skip if nothing changed
        if (serialized === lastSavedPayload) return;

        set({ configSaving: true, lastSavedPayload: serialized });
        try {
            const res = await axios.post('/api/scrape/config', payload);
            if (res.data && typeof res.data === 'object') {
                const next = cleanConfigPayload(res.data);
                set({
                    config: { ...get().config, ...next },
                    autoSaveSkipOnce: true,
                    lastSavedPayload: stableStringify({ ...payload, ...next }),
                });
            }
        } catch (err) {
            console.error('Failed to save scrape config', err);
            throw err;
        } finally {
            set({ configSaving: false });
        }
    },

    fetchJobs: async (force = false) => {
        const now = Date.now();
        const { lastJobsFetchAt } = get();
        if (!force && now - lastJobsFetchAt < 1500) return;

        set({ lastJobsFetchAt: now });
        try {
            const res = await axios.get('/api/scrape/jobs', { params: { limit: 20 } });
            set({ jobs: Array.isArray(res.data) ? res.data : [] });
        } catch (err) {
            console.error('Failed to fetch scrape jobs', err);
            set({ jobs: [] });
        }
    },

    fetchHistory: async (force = false) => {
        const now = Date.now();
        const { lastHistoryFetchAt } = get();
        if (!force && now - lastHistoryFetchAt < 2500) return;

        set({ lastHistoryFetchAt: now });
        try {
            const res = await axios.get('/api/scrape/history', { params: { limit_jobs: 20, limit_items_per_job: 500 } });
            set({ history: Array.isArray(res.data) ? res.data : [] });
        } catch (err) {
            console.error('Failed to fetch scrape history', err);
            set({ history: [] });
        }
    },

    fetchItems: async (jobId) => {
        if (!jobId) return;
        try {
            const res = await axios.get(`/api/scrape/items/${jobId}`, { params: { limit: 500 } });
            set({ items: Array.isArray(res.data) ? res.data : [] });
        } catch (err) {
            console.error('Failed to fetch scrape items', err);
            set({ items: [] });
        }
    },

    fetchPendingCount: async () => {
        const { config, pendingChecking } = get();
        const dir = String(config.scrape_dir || '').trim();

        if (!dir) {
            set({ pendingCount: null });
            return;
        }
        if (pendingChecking) return;

        set({ pendingChecking: true });
        try {
            const res = await axios.get('/api/scrape/pending_count', { params: { ignore_min_age: true } });
            const data = res.data || {};
            if (data.status === 'success') {
                set({ pendingCount: Number.isFinite(Number(data.count)) ? Number(data.count) : null });
            } else {
                set({ pendingCount: null });
            }
        } catch (err) {
            console.error('Failed to fetch pending count', err);
            set({ pendingCount: null });
        } finally {
            set({ pendingChecking: false });
        }
    },

    startScrape: async () => {
        const { loading, config } = get();
        if (loading) return null;

        const dir = String(config.scrape_dir || '').trim();
        const outDir = String(config.scrape_output_dir || '').trim();
        if (!dir || !outDir) return null;

        set({ loading: true });
        try {
            // Ensure latest settings are applied to the backend runner
            const payload = cleanConfigPayload(config);
            const cfgRes = await axios.post('/api/scrape/config', payload);
            if (cfgRes.data && typeof cfgRes.data === 'object') {
                const next = cleanConfigPayload(cfgRes.data);
                set({ config: { ...get().config, ...next } });
            }

            await axios.post('/api/scrape/start', { directory: dir });
            // Fetch jobs to get the new job
            await get().fetchJobs(true);
            return true;
        } catch (err) {
            console.error('Failed to start scrape', err);
            throw err;
        } finally {
            set({ loading: false });
        }
    },

    testSource: async (sourceId) => {
        const id = String(sourceId || '').toLowerCase();
        if (!id) return;

        set({
            sourceTestState: {
                ...get().sourceTestState,
                [id]: { status: 'testing', at: Date.now() },
            },
        });

        try {
            const res = await axios.get('/api/system/test-source', { params: { source: id } });
            const ok = Boolean(res?.data?.ok);
            set({
                sourceTestState: {
                    ...get().sourceTestState,
                    [id]: {
                        status: ok ? 'ok' : 'fail',
                        at: Date.now(),
                        statusCode: Number(res?.data?.status_code || 0),
                        elapsedMs: Number(res?.data?.elapsed_ms || 0),
                    },
                },
            });
        } catch (e) {
            set({
                sourceTestState: {
                    ...get().sourceTestState,
                    [id]: { status: 'fail', at: Date.now(), statusCode: 0, elapsedMs: 0 },
                },
            });
        }
    },

    clearHistory: async () => {
        const { clearingHistory } = get();
        if (clearingHistory) return;

        set({ clearingHistory: true });
        try {
            await axios.post('/api/scrape/history/clear');
            set({
                jobs: [],
                history: [],
                items: [],
                logOffset: 0,
                liveState: { jobId: null, state: {} },
            });
        } catch (err) {
            console.error('Failed to clear scrape history', err);
            throw err;
        } finally {
            set({ clearingHistory: false });
        }
    },

    // Reset live state for new file
    resetLiveStateForNewFile: (jobId, currentFile, fileIndex, fileTotal, expectedCrawlers) => {
        const currentName = currentFile ? (currentFile.split('/').pop() || currentFile) : '';
        set({
            liveState: {
                jobId,
                state: {
                    fileIndex: fileIndex || 0,
                    fileTotal: fileTotal || 0,
                    currentFileName: currentName,
                    file: currentFile,
                    file_name: currentName,
                    crawlersTried: 0,
                    expectedCrawlers: expectedCrawlers || 1,
                    posterDone: false,
                    fanartDone: false,
                    previewsDone: false,
                    trailerDone: false,
                    translateTitleDone: false,
                    translatePlotDone: false,
                    nfoDone: false,
                    hitCrawler: '',
                    hitTitle: '',
                    hitUrl: '',
                    code: '',
                    title: '',
                    url: '',
                    release: '',
                    runtime: '',
                    studio: '',
                    publisher: '',
                    series: '',
                    rating: '',
                    actors: [],
                    tags: [],
                    poster_url: '',
                    fanart_url: '',
                    plot_len: 0,
                    plot_source: '',
                    plot_preview: '',
                    hit_sources: [],
                    subtitles: [],
                    mini: { key: 'mini.startFile', vars: { file: currentName } },
                    lastUpdateAt: Date.now(),
                },
            },
            lastPreviewFile: currentFile,
        });
    },
}));

export default useScrapeStore;
