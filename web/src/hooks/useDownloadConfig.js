/**
 * Download configuration hook
 * Manages download settings with auto-save functionality
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { useToast } from '../components/Toast';

/**
 * Default download configuration values
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
 * Hook for managing download configuration
 * Provides auto-save with debounce to prevent excessive API calls
 * 
 * @returns {Object} Download config state and handlers
 */
export function useDownloadConfig() {
    // Toast hook
    const toast = useToast();

    // Config state
    const [outputDir, setOutputDir] = useState(DEFAULT_CONFIG.outputDir);
    const [scrapeAfter, setScrapeAfter] = useState(DEFAULT_CONFIG.scrapeAfter);
    const [useProxy, setUseProxy] = useState(DEFAULT_CONFIG.useProxy);
    const [proxyUrl, setProxyUrl] = useState(DEFAULT_CONFIG.proxyUrl);
    const [resolution, setResolution] = useState(DEFAULT_CONFIG.resolution);
    const [workers, setWorkers] = useState(DEFAULT_CONFIG.workers);
    const [filenameFormat, setFilenameFormat] = useState(DEFAULT_CONFIG.filenameFormat);

    // UI state
    const [saving, setSaving] = useState(false);
    const [loading, setLoading] = useState(true);

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
            const res = await axios.get('/api/download/config');
            const cfg = res.data || {};

            if (typeof cfg.output_dir === 'string') {
                setOutputDir(typeof cfg.output_dir === 'string' ? cfg.output_dir || '' : '');
            }
            if (typeof cfg.download_scrape_after_default === 'boolean') {
                setScrapeAfter(cfg.download_scrape_after_default);
            }
            if (typeof cfg.download_use_proxy === 'boolean') {
                setUseProxy(cfg.download_use_proxy);
            }
            if (typeof cfg.download_proxy_url === 'string') {
                setProxyUrl(cfg.download_proxy_url || '');
            }
            if (typeof cfg.download_resolution === 'string') {
                setResolution(cfg.download_resolution || DEFAULT_CONFIG.resolution);
            }
            if (typeof cfg.max_download_workers === 'number') {
                setWorkers(Math.max(1, Math.min(128, cfg.max_download_workers)));
            }
            if (typeof cfg.filename_format === 'string') {
                setFilenameFormat(cfg.filename_format || DEFAULT_CONFIG.filenameFormat);
            }
        } catch (err) {
            console.error('Failed to fetch download config:', err);
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
                output_dir: String(outputDir || '').trim(),
                download_scrape_after_default: Boolean(scrapeAfter),
                download_use_proxy: Boolean(useProxy),
                download_proxy_url: String(proxyUrl || ''),
                download_resolution: String(resolution || DEFAULT_CONFIG.resolution),
                max_download_workers: Number(workers || DEFAULT_CONFIG.workers),
                filename_format: String(filenameFormat || DEFAULT_CONFIG.filenameFormat),
            };

            const res = await axios.post('/api/download/config', payload);
            const cfg = res.data || {};

            // Update state with server response
            if (typeof cfg.output_dir === 'string') {
                setOutputDir(typeof cfg.output_dir === 'string' ? cfg.output_dir || '' : '');
            }
            if (typeof cfg.download_scrape_after_default === 'boolean') {
                setScrapeAfter(cfg.download_scrape_after_default);
            }
            if (typeof cfg.download_use_proxy === 'boolean') {
                setUseProxy(cfg.download_use_proxy);
            }
            if (typeof cfg.download_proxy_url === 'string') {
                setProxyUrl(cfg.download_proxy_url || '');
            }
            if (typeof cfg.download_resolution === 'string') {
                setResolution(cfg.download_resolution || DEFAULT_CONFIG.resolution);
            }
            if (typeof cfg.max_download_workers === 'number') {
                setWorkers(Math.max(1, Math.min(128, cfg.max_download_workers)));
            }
            if (typeof cfg.filename_format === 'string') {
                setFilenameFormat(cfg.filename_format || DEFAULT_CONFIG.filenameFormat);
            }

            // Update last saved payload reference
            const normalized = {
                output_dir: cfg.output_dir ?? payload.output_dir ?? '',
                download_scrape_after_default: cfg.download_scrape_after_default ?? payload.download_scrape_after_default ?? DEFAULT_CONFIG.scrapeAfter,
                download_use_proxy: cfg.download_use_proxy ?? payload.download_use_proxy ?? DEFAULT_CONFIG.useProxy,
                download_proxy_url: cfg.download_proxy_url ?? payload.download_proxy_url ?? '',
                download_resolution: cfg.download_resolution ?? payload.download_resolution ?? DEFAULT_CONFIG.resolution,
                max_download_workers: cfg.max_download_workers ?? payload.max_download_workers ?? DEFAULT_CONFIG.workers,
                filename_format: cfg.filename_format ?? payload.filename_format ?? DEFAULT_CONFIG.filenameFormat,
            };
            lastSavedPayloadRef.current = JSON.stringify(normalized);
        } catch (err) {
            toast.error?.('Failed to save download config: ' + (err.response?.data?.detail || err.message));
        } finally {
            setSaving(false);
        }
    }, [outputDir, scrapeAfter, useProxy, proxyUrl, resolution, workers, filenameFormat, toast]);

    // Auto-save effect with debounce
    useEffect(() => {
        if (!autoSaveReadyRef.current) return;
        if (autoSaveSkipOnceRef.current) {
            autoSaveSkipOnceRef.current = false;
            return;
        }

        const payload = {
            output_dir: String(outputDir || '').trim(),
            download_scrape_after_default: Boolean(scrapeAfter),
            download_use_proxy: Boolean(useProxy),
            download_proxy_url: String(proxyUrl || ''),
            download_resolution: String(resolution || DEFAULT_CONFIG.resolution),
            max_download_workers: Number(workers || DEFAULT_CONFIG.workers),
            filename_format: String(filenameFormat || DEFAULT_CONFIG.filenameFormat),
        };

        const serialized = JSON.stringify(payload);
        if (serialized === lastSavedPayloadRef.current) return;

        const timer = window.setTimeout(async () => {
            if (saving) return;
            lastSavedPayloadRef.current = serialized;
            await saveConfig(payload);
        }, 450);

        return () => window.clearTimeout(timer);
    }, [outputDir, scrapeAfter, useProxy, proxyUrl, resolution, workers, filenameFormat, saving, saveConfig]);

    // Fetch config on mount
    useEffect(() => {
        fetchConfig();
    }, [fetchConfig]);

    return {
        // State values
        outputDir,
        scrapeAfter,
        useProxy,
        proxyUrl,
        resolution,
        workers,
        filenameFormat,

        // Setters
        setOutputDir,
        setScrapeAfter,
        setUseProxy,
        setProxyUrl,
        setResolution,
        setWorkers,
        setFilenameFormat,

        // UI state
        saving,
        loading,

        // Actions
        fetchConfig,
        saveConfig,
    };
}

export default useDownloadConfig;
