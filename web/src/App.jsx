/**
 * Mr. Banana - Main Application Component
 * 
 * Uses extracted hooks and components for better maintainability.
 */
import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import axios from 'axios';
import { t, detectDefaultUiLang } from './i18n';
import { Button } from './components/ui';
import { useToast } from './components/Toast';
import { LogViewerModal } from './components/LogViewerModal';
import { ContextMenu } from './components/ContextMenu';
import { ThemePicker } from './components/ThemePicker';
import { LanguagePicker } from './components/LanguagePicker';
import { DownloadTab, PlayerTab } from './components/tabs';
import { ScrapeTab } from './components/tabs/scrape';
import { stableStringify } from './utils/appHelpers';
import { useDownloadStore } from './stores';
import { useTheme, usePersistedString } from './hooks';
import faviconUrl from '/favicon.svg';

function App() {
    const toast = useToast();

    // Get store action for updating activeTasks
    const setStoreActiveTasks = useDownloadStore((s) => s.setActiveTasks);

    // =========================================================================
    // Theme & Language (using extracted hooks)
    // =========================================================================
    const { themeMode, setThemeMode } = useTheme('mr-banana-theme-mode');

    const [uiLang, setUiLang] = usePersistedString(
        'mr-banana-ui-lang',
        detectDefaultUiLang(),
        ['banana-ui-lang', 'mrjet-ui-lang']
    );

    const tr = useCallback((key, vars) => t(uiLang, key, vars), [uiLang]);

    // =========================================================================
    // Tab Management (using extracted hook)
    // =========================================================================
    const [activeTab, setActiveTab] = usePersistedString(
        'mr-banana-active-tab',
        'download',
        ['banana-active-tab', 'mrjet-active-tab']
    );

    // =========================================================================
    // Legacy state (to be migrated to stores)
    // =========================================================================
    const [showDownloadSettings, setShowDownloadSettings] = useState(false);
    const [showDownloadAdvanced, setShowDownloadAdvanced] = useState(false);
    const [downloadSettingsSaving, setDownloadSettingsSaving] = useState(false);
    const [downloadAdvancedTab, setDownloadAdvancedTab] = useState('download');
    const downloadAutoSaveReadyRef = useRef(false);
    const downloadAutoSaveSkipOnceRef = useRef(false);
    const downloadLastSavedPayloadRef = useRef('');

    const playerAutoSaveReadyRef = useRef(false);
    const playerAutoSaveSkipOnceRef = useRef(false);
    const playerLastSavedPayloadRef = useRef('');

    const settingsOpenAudioRef = useRef(null);
    const brushCleanAudioRef = useRef(null);
    const [downloadGearSpin, setDownloadGearSpin] = useState(false);
    const downloadGearAnimatingRef = useRef(false);
    const downloadGearSpinTimerRef = useRef(null);

    const [playerGearSpin, setPlayerGearSpin] = useState(false);
    const playerGearAnimatingRef = useRef(false);
    const playerGearSpinTimerRef = useRef(null);

    useEffect(() => {
        try {
            settingsOpenAudioRef.current = new Audio(settingsOpenSfxUrl);
            settingsOpenAudioRef.current.preload = 'auto';
            settingsOpenAudioRef.current.volume = 0.35;
        } catch {
            settingsOpenAudioRef.current = null;
        }

        try {
            brushCleanAudioRef.current = new Audio(brushCleanSfxUrl);
            brushCleanAudioRef.current.preload = 'auto';
            brushCleanAudioRef.current.volume = 0.35;
        } catch {
            brushCleanAudioRef.current = null;
        }

        return () => {
            if (downloadGearSpinTimerRef.current) {
                window.clearTimeout(downloadGearSpinTimerRef.current);
                downloadGearSpinTimerRef.current = null;
            }
            if (playerGearSpinTimerRef.current) {
                window.clearTimeout(playerGearSpinTimerRef.current);
                playerGearSpinTimerRef.current = null;
            }
            if (downloadBroomTimerRef.current) {
                window.clearTimeout(downloadBroomTimerRef.current);
                downloadBroomTimerRef.current = null;
            }
            settingsOpenAudioRef.current = null;
            brushCleanAudioRef.current = null;
        };
    }, []);

    const playSettingsOpenSfx = () => {
        try {
            const a = settingsOpenAudioRef.current;
            if (!a) return;
            a.currentTime = 0;
            const p = a.play();
            if (p && typeof p.catch === 'function') p.catch(() => { });
        } catch {
            // ignore
        }
    };

    const stopSettingsOpenSfx = () => {
        try {
            const a = settingsOpenAudioRef.current;
            if (!a) return;
            a.pause();
            a.currentTime = 0;
        } catch {
            // ignore
        }
    };

    const playBrushCleanSfx = () => {
        try {
            const a = brushCleanAudioRef.current;
            if (!a) return;
            a.currentTime = 0;
            const p = a.play();
            if (p && typeof p.catch === 'function') p.catch(() => { });
        } catch {
            // ignore
        }
    };

    const startDownloadGearSpin = () => {
        downloadGearAnimatingRef.current = true;
        setDownloadGearSpin(false);
        window.requestAnimationFrame(() => setDownloadGearSpin(true));

        if (downloadGearSpinTimerRef.current) {
            window.clearTimeout(downloadGearSpinTimerRef.current);
            downloadGearSpinTimerRef.current = null;
        }

        downloadGearSpinTimerRef.current = window.setTimeout(() => {
            setDownloadGearSpin(false);
            downloadGearAnimatingRef.current = false;
            downloadGearSpinTimerRef.current = null;
        }, 1250);
    };

    const startPlayerGearSpin = () => {
        playerGearAnimatingRef.current = true;
        setPlayerGearSpin(false);
        window.requestAnimationFrame(() => setPlayerGearSpin(true));

        if (playerGearSpinTimerRef.current) {
            window.clearTimeout(playerGearSpinTimerRef.current);
            playerGearSpinTimerRef.current = null;
        }

        playerGearSpinTimerRef.current = window.setTimeout(() => {
            setPlayerGearSpin(false);
            playerGearAnimatingRef.current = false;
            playerGearSpinTimerRef.current = null;
        }, 1250);
    };

    const startDownloadBroomSweep = () => {
        if (downloadBroomAnimatingRef.current) return;
        downloadBroomAnimatingRef.current = true;
        setDownloadBroomSweep(false);
        window.requestAnimationFrame(() => setDownloadBroomSweep(true));

        if (downloadBroomTimerRef.current) {
            window.clearTimeout(downloadBroomTimerRef.current);
            downloadBroomTimerRef.current = null;
        }

        downloadBroomTimerRef.current = window.setTimeout(() => {
            setDownloadBroomSweep(false);
            downloadBroomAnimatingRef.current = false;
            downloadBroomTimerRef.current = null;
        }, 650);
    };

    const [url, setUrl] = useState('');
    const [loading, setLoading] = useState(false);
    const [history, setHistory] = useState([]);
    const [activeTasks, setActiveTasks] = useState([]);

    const [clearingDownloadHistory, setClearingDownloadHistory] = useState(false);

    const [downloadBroomSweep, setDownloadBroomSweep] = useState(false);
    const downloadBroomAnimatingRef = useRef(false);
    const downloadBroomTimerRef = useRef(null);

    const [downloadOutputDir, setDownloadOutputDir] = useState('');
    const [downloadScrapeAfter, setDownloadScrapeAfter] = useState(false);
    const [downloadUseProxy, setDownloadUseProxy] = useState(false);
    const [downloadProxyUrl, setDownloadProxyUrl] = useState('');
    const [downloadResolution, setDownloadResolution] = useState('best');
    const [downloadWorkers, setDownloadWorkers] = useState(16);
    const [downloadFilenameFormat, setDownloadFilenameFormat] = useState('{id}');

    const [showPlayerSettings, setShowPlayerSettings] = useState(false);
    const [playerConfigSaving, setPlayerConfigSaving] = useState(false);
    const [playerRootDir, setPlayerRootDir] = useState('');
    const [playerDetail, setPlayerDetail] = useState({ open: false, item: null, playing: false });

    const [libraryItems, setLibraryItems] = useState([]);
    const [dirPickerField, setDirPickerField] = useState(null);
    const libraryPollTimer = useRef(null);

    const [contextMenu, setContextMenu] = useState(null);
    const [logViewer, setLogViewer] = useState({ open: false, kind: 'download', id: null, file: null });
    const [logText, setLogText] = useState('');
    const [logOffset, setLogOffset] = useState(0);
    const [logExists, setLogExists] = useState(true);
    const ws = useRef(null);
    const lastTaskStatusRef = useRef(new Map());
    const logPollTimer = useRef(null);
    const logEndRef = useRef(null);

    const logOffsetRef = useRef(0);

    const fetchHistory = async () => {
        try {
            const res = await axios.get('/api/history', { params: { limit: 50 } });
            setHistory(Array.isArray(res.data) ? res.data : []);
        } catch (err) {
            console.error('Failed to fetch history', err);
            setHistory([]);
        }
    };

    const fetchDownloadConfig = async () => {
        try {
            const res = await axios.get('/api/download/config');
            const cfg = res.data || {};
            if (typeof cfg.output_dir === 'string') setDownloadOutputDir(cfg.output_dir || '');
            if (typeof cfg.download_scrape_after_default === 'boolean') setDownloadScrapeAfter(cfg.download_scrape_after_default);
            if (typeof cfg.download_use_proxy === 'boolean') setDownloadUseProxy(cfg.download_use_proxy);
            if (typeof cfg.download_proxy_url === 'string') setDownloadProxyUrl(cfg.download_proxy_url || '');
            if (typeof cfg.download_resolution === 'string') setDownloadResolution(cfg.download_resolution || 'best');
            if (typeof cfg.max_download_workers === 'number') setDownloadWorkers(Math.max(1, Math.min(128, cfg.max_download_workers)));
            if (typeof cfg.filename_format === 'string') setDownloadFilenameFormat(cfg.filename_format || '{id}');
        } catch (err) {
            console.error('Failed to fetch download config', err);
        } finally {
            downloadAutoSaveReadyRef.current = true;
            downloadAutoSaveSkipOnceRef.current = true;
        }
    };

    useEffect(() => {
        if (!downloadAutoSaveReadyRef.current) return;
        if (downloadAutoSaveSkipOnceRef.current) {
            downloadAutoSaveSkipOnceRef.current = false;
            return;
        }

        const payload = {
            output_dir: String(downloadOutputDir || '').trim(),
            download_scrape_after_default: Boolean(downloadScrapeAfter),
            download_use_proxy: Boolean(downloadUseProxy),
            download_proxy_url: String(downloadProxyUrl || ''),
            download_resolution: String(downloadResolution || 'best'),
            max_download_workers: Number(downloadWorkers || 16),
            filename_format: String(downloadFilenameFormat || '{id}'),
        };

        const serialized = JSON.stringify(payload);
        if (serialized === downloadLastSavedPayloadRef.current) return;

        const t = window.setTimeout(async () => {
            if (downloadSettingsSaving) return;
            downloadLastSavedPayloadRef.current = serialized;
            await handleSaveDownloadConfig(payload);
        }, 450);

        return () => window.clearTimeout(t);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        downloadOutputDir,
        downloadScrapeAfter,
        downloadUseProxy,
        downloadProxyUrl,
        downloadResolution,
        downloadWorkers,
        downloadFilenameFormat,
    ]);

    const fetchPlayerConfig = async () => {
        try {
            const res = await axios.get('/api/player/config');
            const cfg = res.data || {};
            if (typeof cfg.player_root_dir === 'string') setPlayerRootDir(cfg.player_root_dir || '');
        } catch (err) {
            console.error('Failed to fetch player config', err);
        } finally {
            playerAutoSaveReadyRef.current = true;
            playerAutoSaveSkipOnceRef.current = true;
        }
    };

    useEffect(() => {
        if (!playerAutoSaveReadyRef.current) return;
        if (playerAutoSaveSkipOnceRef.current) {
            playerAutoSaveSkipOnceRef.current = false;
            return;
        }

        const payload = {
            player_root_dir: String(playerRootDir || '').trim(),
        };

        const serialized = stableStringify(payload);
        if (serialized === playerLastSavedPayloadRef.current) return;

        const t = window.setTimeout(async () => {
            if (playerConfigSaving) return;
            playerLastSavedPayloadRef.current = serialized;
            await handleSavePlayerConfig(payload);
        }, 450);

        return () => window.clearTimeout(t);
    }, [playerRootDir, playerConfigSaving]);

    const fetchLibraryItems = async () => {
        try {
            const res = await axios.get('/api/library/items', { params: { limit: 200 } });
            setLibraryItems(Array.isArray(res.data) ? res.data : []);
        } catch (err) {
            console.error('Failed to fetch library items', err);
            setLibraryItems([]);
        }
    };

    // Fetch initial data + connect ws on mount
    useEffect(() => {
        fetchHistory();
        fetchDownloadConfig();
        fetchPlayerConfig();
        connectWebSocket();

        return () => {
            if (ws.current) {
                try {
                    ws.current.onclose = null;
                    ws.current.close();
                } catch {
                    // ignore
                }
                ws.current = null;
            }

            if (libraryPollTimer.current) {
                window.clearInterval(libraryPollTimer.current);
                libraryPollTimer.current = null;
            }
            if (logPollTimer.current) {
                window.clearInterval(logPollTimer.current);
                logPollTimer.current = null;
            }
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const connectWebSocket = () => {
        // 开发环境：直连后端，避免 Vite ws proxy 在断连时刷 EPIPE
        const wsUrl = import.meta.env.DEV
            ? 'ws://127.0.0.1:8000/ws'
            : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;

        // For development without proxy, you might need hardcoded localhost
        // const wsUrl = 'ws://127.0.0.1:8000/ws'; 

        ws.current = new WebSocket(wsUrl);

        ws.current.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'update') {
                const tasks = Array.isArray(data.tasks) ? data.tasks : [];

                // Only refresh history when a task transitions into a terminal state.
                // (Otherwise, once any completed task exists in active_tasks, we'd fetch on every tick.)
                let shouldRefreshHistory = false;
                for (const t of tasks) {
                    const id = String(t.id);
                    const prev = lastTaskStatusRef.current.get(id);
                    const next = t.status;
                    if (prev && prev !== next && (next === 'Completed' || next === 'Failed')) {
                        shouldRefreshHistory = true;
                    }
                    lastTaskStatusRef.current.set(id, next);
                }

                setActiveTasks(tasks);
                setStoreActiveTasks(tasks); // Also update the store for DownloadTab
                if (shouldRefreshHistory) fetchHistory();
            }
        };

        ws.current.onclose = () => {
            setTimeout(connectWebSocket, 3000); // Reconnect
        };
    };

    useEffect(() => {
        if (!contextMenu) return;
        const onGlobalClick = () => setContextMenu(null);
        const onEsc = (e) => {
            if (e.key === 'Escape') setContextMenu(null);
        };
        window.addEventListener('click', onGlobalClick);
        window.addEventListener('keydown', onEsc);
        return () => {
            window.removeEventListener('click', onGlobalClick);
            window.removeEventListener('keydown', onEsc);
        };
    }, [contextMenu]);

    useEffect(() => {
        if (activeTab !== 'player') return;
        fetchLibraryItems();
    }, [activeTab]);

    async function handleSavePlayerConfig(overridePayload = null) {
        setPlayerConfigSaving(true);
        try {
            const payload = overridePayload
                ? { ...overridePayload }
                : {
                    player_root_dir: String(playerRootDir || '').trim(),
                };

            playerLastSavedPayloadRef.current = stableStringify(payload);

            const res = await axios.post('/api/player/config', payload);
            const cfg = res.data || {};
            if (typeof cfg.player_root_dir === 'string') {
                playerAutoSaveSkipOnceRef.current = true;
                setPlayerRootDir(cfg.player_root_dir || '');
                playerLastSavedPayloadRef.current = stableStringify({ player_root_dir: cfg.player_root_dir || '' });
            } else {
                playerLastSavedPayloadRef.current = stableStringify({ player_root_dir: String(payload.player_root_dir || '') });
            }
        } catch (err) {
            toast.error('Failed to save player config: ' + (err.response?.data?.detail || err.message));
        } finally {
            setPlayerConfigSaving(false);
        }
    }

    const handleSaveDownloadConfig = async (overridePayload = null) => {
        setDownloadSettingsSaving(true);
        try {
            const payload = overridePayload || {
                output_dir: String(downloadOutputDir || '').trim(),
                download_scrape_after_default: Boolean(downloadScrapeAfter),
                download_use_proxy: Boolean(downloadUseProxy),
                download_proxy_url: String(downloadProxyUrl || ''),
                download_resolution: String(downloadResolution || 'best'),
                max_download_workers: Number(downloadWorkers || 16),
                filename_format: String(downloadFilenameFormat || '{id}'),
            };
            const res = await axios.post('/api/download/config', payload);
            const cfg = res.data || {};
            if (typeof cfg.output_dir === 'string') setDownloadOutputDir(cfg.output_dir || '');
            if (typeof cfg.download_scrape_after_default === 'boolean') setDownloadScrapeAfter(cfg.download_scrape_after_default);
            if (typeof cfg.download_use_proxy === 'boolean') setDownloadUseProxy(cfg.download_use_proxy);
            if (typeof cfg.download_proxy_url === 'string') setDownloadProxyUrl(cfg.download_proxy_url || '');
            if (typeof cfg.download_resolution === 'string') setDownloadResolution(cfg.download_resolution || 'best');
            if (typeof cfg.max_download_workers === 'number') setDownloadWorkers(Math.max(1, Math.min(128, cfg.max_download_workers)));
            if (typeof cfg.filename_format === 'string') setDownloadFilenameFormat(cfg.filename_format || '{id}');

            const normalized = {
                output_dir: typeof cfg.output_dir === 'string' ? (cfg.output_dir || '') : (payload.output_dir || ''),
                download_scrape_after_default:
                    typeof cfg.download_scrape_after_default === 'boolean' ? cfg.download_scrape_after_default : Boolean(payload.download_scrape_after_default),
                download_use_proxy: typeof cfg.download_use_proxy === 'boolean' ? cfg.download_use_proxy : Boolean(payload.download_use_proxy),
                download_proxy_url: typeof cfg.download_proxy_url === 'string' ? (cfg.download_proxy_url || '') : String(payload.download_proxy_url || ''),
                download_resolution: typeof cfg.download_resolution === 'string' ? (cfg.download_resolution || 'best') : String(payload.download_resolution || 'best'),
                max_download_workers:
                    typeof cfg.max_download_workers === 'number' ? cfg.max_download_workers : Number(payload.max_download_workers || 16),
                filename_format: typeof cfg.filename_format === 'string' ? (cfg.filename_format || '{id}') : String(payload.filename_format || '{id}'),
            };
            downloadLastSavedPayloadRef.current = JSON.stringify(normalized);
        } catch (err) {
            toast.error('Failed to save download config: ' + (err.response?.data?.detail || err.message));
        } finally {
            setDownloadSettingsSaving(false);
        }
    };

    const chooseDirectory = async ({ title, initialDir }) => {
        try {
            const res = await axios.post('/api/system/choose-directory', {
                title,
                initial_dir: initialDir || null,
            });
            return res?.data?.path || null;
        } catch (err) {
            toast.error('Failed to choose directory: ' + (err.response?.data?.detail || err.message));
            return null;
        }
    };

    const handlePickPlayerRootDir = async () => {
        setDirPickerField('player_root_dir');
        const picked = await chooseDirectory({
            title: tr('player.settings.rootDir'),
            initialDir: playerRootDir,
        });
        if (picked) setPlayerRootDir(picked);
        setDirPickerField(null);
    };

    const handleResume = async (taskId) => {
        try {
            const out = String(downloadOutputDir || '').trim();
            if (!out) {
                toast.error(t(uiLang, 'download.error.noOutputDir'));
                return;
            }
            await axios.post('/api/resume', { task_id: taskId, output_dir: out });
            fetchHistory();
        } catch (err) {
            toast.error('Failed to resume download: ' + (err.response?.data?.detail || err.message));
        }
    };

    const handlePickDownloadOutputDir = async () => {
        setDirPickerField('download_output_dir');
        const picked = await chooseDirectory({
            title: '选择下载输出目录',
            initialDir: downloadOutputDir,
        });
        if (picked) setDownloadOutputDir(picked);
        setDirPickerField(null);
    };

    const handlePause = async (taskId) => {
        try {
            await axios.post('/api/pause', { task_id: taskId });
            fetchHistory();
        } catch (err) {
            toast.error('Failed to pause download: ' + (err.response?.data?.detail || err.message));
        }
    };

    const handleDelete = async (taskId) => {
        try {
            await axios.post('/api/delete', { task_id: taskId });
            setLogViewer((v) => (v.open && String(v.id) === String(taskId) ? { open: false, kind: 'download', id: null } : v));
            fetchHistory();
        } catch (err) {
            toast.error('Failed to delete task: ' + (err.response?.data?.detail || err.message));
        }
    };

    const openLogViewer = async ({ kind, id, file = null }) => {
        setLogViewer({ open: true, kind, id, file });
        setLogText('');
        setLogOffset(0);
        logOffsetRef.current = 0;
        setLogExists(true);

        try {
            if (kind === 'scrape-item' && file) {
                const res = await axios.get(`/api/scrape/logs/${id}/item`, { params: { filename: file } });
                setLogExists(Boolean(res.data?.exists));
                setLogText(res.data?.text || '');
                logOffsetRef.current = 0;
                setLogOffset(0);
            } else {
                const safeKind = kind === 'scrape' ? 'scrape' : 'download';
                const base = safeKind === 'scrape' ? `/api/scrape/logs/${id}` : `/api/logs/${id}`;
                const res = await axios.get(`${base}?offset=0`);
                setLogExists(Boolean(res.data?.exists));
                setLogText(res.data?.text || '');
                const next = res.data?.next_offset ?? 0;
                logOffsetRef.current = next;
                setLogOffset(next);
            }
        } catch (err) {
            setLogText(`[failed to load log] ${err.response?.data?.detail || err.message}\n`);
        }
    };

    const handleClearDownloadHistory = async () => {
        if (clearingDownloadHistory) return;
        setClearingDownloadHistory(true);
        try {
            await axios.post('/api/download/history/clear');

            // Immediate UI effect
            setHistory([]);
            setActiveTasks([]);

            if (logViewer.open && logViewer.kind === 'download') {
                setLogText('');
                setLogOffset(0);
                logOffsetRef.current = 0;
                setLogExists(false);
            }

            // Best-effort re-fetch
            fetchHistory(true);
        } catch (err) {
            console.error('Failed to clear download history', err);
        } finally {
            setClearingDownloadHistory(false);
        }
    };

    const closeLogViewer = () => {
        setLogViewer({ open: false, kind: 'download', id: null, file: null });
    };

    const openPlayerDetail = (item) => {
        setPlayerDetail({ open: true, item, playing: false });
    };

    const closePlayerDetail = () => {
        setPlayerDetail({ open: false, item: null, playing: false });
    };

    useEffect(() => {
        if (!playerDetail.open) return;
        const onKeyDown = (e) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                closePlayerDetail();
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [playerDetail.open]);



    useEffect(() => {
        if (!logViewer.open || !logViewer.id) return;

        const tick = async () => {
            try {
                if (logViewer.kind === 'scrape-item' && logViewer.file) {
                    const res = await axios.get(`/api/scrape/logs/${logViewer.id}/item`, { params: { filename: logViewer.file } });
                    setLogExists(Boolean(res.data?.exists));
                    setLogText(res.data?.text || '');
                    logOffsetRef.current = 0;
                    setLogOffset(0);
                } else {
                    const currentOffset = logOffsetRef.current || 0;
                    const safeKind = logViewer.kind === 'scrape' ? 'scrape' : 'download';
                    const base = safeKind === 'scrape' ? `/api/scrape/logs/${logViewer.id}` : `/api/logs/${logViewer.id}`;
                    const res = await axios.get(`${base}?offset=${currentOffset}`);
                    setLogExists(Boolean(res.data?.exists));
                    const nextOffset = res.data?.next_offset ?? currentOffset;
                    const chunk = res.data?.text || '';
                    if (chunk) setLogText((prev) => prev + chunk);
                    logOffsetRef.current = nextOffset;
                    setLogOffset(nextOffset);
                }
            } catch {
                // ignore transient errors to keep UI smooth
            }
        };

        // poll every 1s while modal is open
        logPollTimer.current = window.setInterval(tick, 1000);
        return () => {
            if (logPollTimer.current) {
                window.clearInterval(logPollTimer.current);
                logPollTimer.current = null;
            }
        };
    }, [logViewer.open, logViewer.kind, logViewer.id, logViewer.file]);

    useEffect(() => {
        if (!logViewer.open) return;
        // keep scrolled to bottom on updates
        logEndRef.current?.scrollIntoView({ block: 'end' });
    }, [logText, logViewer.open]);

    const mergedRows = useMemo(() => {
        const activeById = new Map(activeTasks.map((t) => [String(t.id), t]));
        const seenIds = new Set();

        const rows = (history || []).map((item) => {
            const id = String(item.id);
            seenIds.add(id);

            const active = activeById.get(id);
            const status = active?.status || item.status;
            const progress = active?.progress;
            const speed = active?.speed;
            const error = active?.error ?? item.error ?? null;
            const scrapeAfter = typeof active?.scrape_after_download === 'boolean'
                ? active.scrape_after_download
                : (item.scrape_after_download === null || typeof item.scrape_after_download === 'undefined')
                    ? null
                    : Boolean(Number(item.scrape_after_download));
            const scrapeJobId = active?.scrape_job_id ?? item.scrape_job_id ?? null;
            const scrapeStatus = active?.scrape_status ?? item.scrape_status ?? null;

            return {
                ...item,
                status,
                progress,
                speed,
                error,
                scrape_after_download: scrapeAfter,
                scrape_job_id: scrapeJobId,
                scrape_status: scrapeStatus,
            };
        });

        // 兜底：如果 websocket 推过来的任务不在 history 里，也显示出来
        for (const task of activeTasks || []) {
            const id = String(task.id);
            if (seenIds.has(id)) continue;
            rows.push({
                id: task.id,
                url: task.url,
                title: null,
                status: task.status,
                created_at: null,
                completed_at: null,
                progress: task.progress,
                speed: task.speed,
                error: task.error ?? null,
                scrape_after_download: Boolean(task.scrape_after_download),
                scrape_job_id: task.scrape_job_id ?? null,
                scrape_status: task.scrape_status ?? null,
            });
        }

        // 默认按创建时间倒序；没有 created_at 的放在最上面（通常是刚创建但尚未同步到 history）
        rows.sort((a, b) => {
            const at = a.created_at ? new Date(a.created_at).getTime() : Number.POSITIVE_INFINITY;
            const bt = b.created_at ? new Date(b.created_at).getTime() : Number.POSITIVE_INFINITY;
            return bt - at;
        });

        return rows;
    }, [activeTasks, history]);

    return (
        <div className="min-h-screen bg-background p-8 font-sans text-foreground">
            <div className="mx-auto max-w-5xl space-y-8">

                {/* Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <img
                            src={faviconUrl}
                            alt="Mr. Banana"
                            className="h-7 w-7 object-contain"
                            draggable={false}
                        />
                        <h1 className="text-2xl font-bold tracking-tight">{tr('app.title')}</h1>
                    </div>
                    <div className="flex items-center gap-3">
                        <ThemePicker
                            themeMode={themeMode}
                            setThemeMode={setThemeMode}
                        />
                        <LanguagePicker
                            language={uiLang}
                            setLanguage={setUiLang}
                        />
                    </div>
                </div>

                {/* Tabs */}
                <div className="w-full">
                    <div className="flex w-full items-center gap-3">
                        <Button
                            type="button"
                            className="flex-1 border"
                            variant={activeTab === 'download' ? 'default' : 'ghost'}
                            onClick={() => setActiveTab('download')}
                        >
                            {tr('tab.download')}
                        </Button>
                        <Button
                            type="button"
                            className="flex-1 border"
                            variant={activeTab === 'scrape' ? 'default' : 'ghost'}
                            onClick={() => setActiveTab('scrape')}
                        >
                            {tr('tab.scrape')}
                        </Button>
                        <Button
                            type="button"
                            className="flex-1 border"
                            variant={activeTab === 'player' ? 'default' : 'ghost'}
                            onClick={() => setActiveTab('player')}
                        >
                            {tr('tab.player')}
                        </Button>
                    </div>
                </div>

                {activeTab === 'download' && (
                    <DownloadTab
                        uiLang={uiLang}
                        dirPickerField={dirPickerField}
                        setDirPickerField={setDirPickerField}
                        openLogViewer={openLogViewer}
                        setContextMenu={setContextMenu}
                    />
                )}

                {activeTab === 'player' && (
                    <PlayerTab
                        uiLang={uiLang}
                        dirPickerField={dirPickerField}
                        setDirPickerField={setDirPickerField}
                    />
                )}

                {activeTab === 'scrape' && (
                    <ScrapeTab
                        uiLang={uiLang}
                        dirPickerField={dirPickerField}
                        setDirPickerField={setDirPickerField}
                        openLogViewer={openLogViewer}
                        tr={tr}
                    />
                )}

                <ContextMenu
                    contextMenu={contextMenu}
                    onClose={() => setContextMenu(null)}
                    onResume={handleResume}
                    onPause={handlePause}
                    onDelete={handleDelete}
                    tr={tr}
                />

                <LogViewerModal
                    open={logViewer.open}
                    onClose={closeLogViewer}
                    logViewer={logViewer}
                    logText={logText}
                    logExists={logExists}
                    logEndRef={logEndRef}
                    tr={tr}
                />

            </div>
        </div>
    );
}

export default App;
