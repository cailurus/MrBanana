/**
 * ScrapeTab - Main scrape tab component
 * Manages polling, refs, and integrates sub-components
 */
import React, { useEffect, useRef } from 'react';
import { Activity, Settings } from 'lucide-react';
import axios from 'axios';

import { useToast } from '../../Toast';
import { useScrapeStore } from '../../../stores/scrapeStore';
import { useGearAnimation, useBroomAnimation, playSettingsOpenSfx, stopSettingsOpenSfx, playBrushCleanSfx } from '../../../hooks/useAnimations';
import { cn } from '../../ui';
import { getExpectedScrapeCrawlerCount } from '../../../utils/appHelpers';
import { parseScrapeLogChunk } from '../../../scrapeProgress';

import { ScrapeSettingsPanel } from './ScrapeSettingsPanel';
import { ScrapeControlBar } from './ScrapeControlBar';
import { ScrapeLivePreview } from './ScrapeLivePreview';
import { ScrapeHistoryTable } from './ScrapeHistoryTable';
import { ScrapeDetailModal, DirectoryBrowserModal } from '../../modals';

export function ScrapeTab({
    uiLang,
    dirPickerField,
    setDirPickerField,
    openLogViewer,
    tr,
}) {
    // Toast hook
    const toast = useToast();

    // Store hooks
    const config = useScrapeStore((s) => s.config);
    const setConfig = useScrapeStore((s) => s.setConfig);
    const autoSaveReady = useScrapeStore((s) => s.autoSaveReady);
    const autoSaveSkipOnce = useScrapeStore((s) => s.autoSaveSkipOnce);
    const setAutoSaveSkipOnce = useScrapeStore((s) => s.setAutoSaveSkipOnce);
    const lastSavedPayload = useScrapeStore((s) => s.lastSavedPayload);
    const setLastSavedPayload = useScrapeStore((s) => s.setLastSavedPayload);
    const configSaving = useScrapeStore((s) => s.configSaving);
    const loading = useScrapeStore((s) => s.loading);

    const showSettings = useScrapeStore((s) => s.showSettings);
    const setShowSettings = useScrapeStore((s) => s.setShowSettings);
    const toggleSettings = useScrapeStore((s) => s.toggleSettings);

    const detail = useScrapeStore((s) => s.detail);
    const openDetail = useScrapeStore((s) => s.openDetail);
    const closeDetail = useScrapeStore((s) => s.closeDetail);

    const liveState = useScrapeStore((s) => s.liveState);
    const setLiveState = useScrapeStore((s) => s.setLiveState);
    const logOffset = useScrapeStore((s) => s.logOffset);
    const setLogOffset = useScrapeStore((s) => s.setLogOffset);
    const lastPreviewFile = useScrapeStore((s) => s.lastPreviewFile);
    const setLastPreviewFile = useScrapeStore((s) => s.setLastPreviewFile);
    const resetLiveStateForNewFile = useScrapeStore((s) => s.resetLiveStateForNewFile);

    const hasRunningJob = useScrapeStore((s) => s.hasRunningJob);
    const getLatestJob = useScrapeStore((s) => s.getLatestJob);
    const fetchJobs = useScrapeStore((s) => s.fetchJobs);
    const fetchHistory = useScrapeStore((s) => s.fetchHistory);
    const fetchItems = useScrapeStore((s) => s.fetchItems);
    const fetchPendingCount = useScrapeStore((s) => s.fetchPendingCount);
    const fetchConfig = useScrapeStore((s) => s.fetchConfig);
    const saveConfig = useScrapeStore((s) => s.saveConfig);
    const clearHistory = useScrapeStore((s) => s.clearHistory);
    const clearingHistory = useScrapeStore((s) => s.clearingHistory);

    // Refs for polling timers
    const jobsPollTimer = useRef(null);
    const historyPollTimer = useRef(null);
    const itemsPollTimer = useRef(null);
    const logPollTimer = useRef(null);
    const logOffsetRef = useRef(0);
    const lastPreviewFileRef = useRef('');

    // Animation hooks
    const { spinning: gearSpin, start: startGearSpin, isAnimating: isGearAnimating } = useGearAnimation();
    const { sweeping: broomSweep, start: startBroomSweep } = useBroomAnimation();

    // Directory browser state for remote access
    const [showDirBrowser, setShowDirBrowser] = React.useState(false);
    const [dirBrowserTarget, setDirBrowserTarget] = React.useState(null); // 'input' or 'output'

    // stableStringify for config comparison
    const stableStringify = (obj) => {
        if (obj === null || obj === undefined) return String(obj);
        if (typeof obj !== 'object') return JSON.stringify(obj);
        if (Array.isArray(obj)) return '[' + obj.map(stableStringify).join(',') + ']';
        const keys = Object.keys(obj).sort();
        return '{' + keys.map((k) => JSON.stringify(k) + ':' + stableStringify(obj[k])).join(',') + '}';
    };

    // Clean config payload
    const cleanConfigPayload = (cfg) => {
        const payload = { ...cfg };
        delete payload.scrape_sources_fallback;
        delete payload.scrape_sources_directors;
        delete payload.scrape_sources_series;
        delete payload.scrape_sources_want;
        return payload;
    };

    // Computed values
    const latestJob = getLatestJob();
    const isRunning = hasRunningJob();

    // Choose directory helper - supports native dialog (localhost) or remote browser
    const chooseDirectory = async ({ title, initialDir }) => {
        try {
            const res = await axios.post('/api/system/choose-directory', {
                title,
                initial_dir: initialDir || null,
            });
            return res?.data?.path || null;
        } catch (err) {
            // If 403 (not localhost), signal to use remote browser
            if (err.response?.status === 403) {
                return null;
            }
            toast.error('Failed to choose directory: ' + (err.response?.data?.detail || err.message));
            return null;
        }
    };

    // Directory picker handlers
    const handlePickScrapeDir = async () => {
        setDirPickerField('scrape_dir');
        const picked = await chooseDirectory({
            title: tr('scrape.dirPicker.inputTitle'),
            initialDir: config.scrape_dir,
        });
        if (picked) {
            setConfig({ scrape_dir: picked });
        } else if (picked === null) {
            // Native dialog not available - show remote browser
            setDirBrowserTarget('input');
            setShowDirBrowser(true);
        }
        setDirPickerField(null);
    };

    const handlePickScrapeOutputDir = async () => {
        setDirPickerField('scrape_output_dir');
        const picked = await chooseDirectory({
            title: tr('scrape.dirPicker.outputTitle'),
            initialDir: config.scrape_output_dir || config.scrape_dir,
        });
        if (picked) {
            setConfig({ scrape_output_dir: picked });
        } else if (picked === null) {
            // Native dialog not available - show remote browser
            setDirBrowserTarget('output');
            setShowDirBrowser(true);
        }
        setDirPickerField(null);
    };

    const handleDirBrowserSelect = (path) => {
        if (dirBrowserTarget === 'input') {
            setConfig({ scrape_dir: path });
        } else if (dirBrowserTarget === 'output') {
            setConfig({ scrape_output_dir: path });
        }
    };

    // Toggle settings with animation
    const handleToggleSettings = () => {
        // Only block during opening animation, allow closing anytime
        if (isGearAnimating() && !showSettings) return;

        const willOpen = !showSettings;
        if (willOpen) {
            startGearSpin();
            playSettingsOpenSfx();
        } else {
            stopSettingsOpenSfx();
        }
        toggleSettings();
    };

    // Clear history handler
    const handleClearHistory = async () => {
        try {
            await clearHistory();
        } catch (err) {
            // Error handled in store
        }
    };

    // Initial data fetch
    useEffect(() => {
        fetchConfig();
        fetchJobs(true);
        fetchHistory(true);

        return () => {
            // Cleanup timers
            if (jobsPollTimer.current) {
                window.clearInterval(jobsPollTimer.current);
                jobsPollTimer.current = null;
            }
            if (historyPollTimer.current) {
                window.clearInterval(historyPollTimer.current);
                historyPollTimer.current = null;
            }
            if (itemsPollTimer.current) {
                window.clearInterval(itemsPollTimer.current);
                itemsPollTimer.current = null;
            }
            if (logPollTimer.current) {
                window.clearInterval(logPollTimer.current);
                logPollTimer.current = null;
            }
        };
    }, []);

    // Auto-save config effect
    useEffect(() => {
        if (!autoSaveReady) return;
        if (autoSaveSkipOnce) {
            setAutoSaveSkipOnce(false);
            return;
        }

        const payload = cleanConfigPayload(config);
        const serialized = stableStringify(payload);
        if (serialized === lastSavedPayload) return;

        const t = window.setTimeout(async () => {
            if (configSaving) return;
            // Don't set lastSavedPayload here - let saveConfig handle it
            try {
                await saveConfig();
            } catch (err) {
                // Error is logged in store
            }
        }, 450);

        return () => window.clearTimeout(t);
    }, [config, configSaving, autoSaveReady, autoSaveSkipOnce, lastSavedPayload]);

    // Fetch pending count when scrape_dir changes
    useEffect(() => {
        const dir = String(config.scrape_dir || '').trim();
        if (!dir) return;
        const t = window.setTimeout(() => {
            fetchPendingCount();
        }, 450);
        return () => window.clearTimeout(t);
    }, [config.scrape_dir, fetchPendingCount]);

    // Poll jobs and history
    useEffect(() => {
        fetchJobs();
        fetchHistory(true);

        // Jobs polling - clear and recreate with correct interval based on isRunning
        if (jobsPollTimer.current) {
            window.clearInterval(jobsPollTimer.current);
            jobsPollTimer.current = null;
        }
        const jobsIntervalMs = isRunning ? 1500 : 8000; // 8s when idle to reduce noise
        jobsPollTimer.current = window.setInterval(fetchJobs, jobsIntervalMs);

        // History polling
        const historyIntervalMs = isRunning ? 1500 : 10000; // 10s when idle
        if (historyPollTimer.current) {
            window.clearInterval(historyPollTimer.current);
            historyPollTimer.current = null;
        }
        historyPollTimer.current = window.setInterval(fetchHistory, historyIntervalMs);

        return () => {
            if (jobsPollTimer.current) {
                window.clearInterval(jobsPollTimer.current);
                jobsPollTimer.current = null;
            }
            if (historyPollTimer.current) {
                window.clearInterval(historyPollTimer.current);
                historyPollTimer.current = null;
            }
        };
    }, [isRunning]);

    // Poll items for active job
    useEffect(() => {
        const jobId = latestJob?.id;
        const active = Boolean(jobId) && (latestJob?.status === 'Running' || latestJob?.status === 'Starting');

        if (!active) {
            if (itemsPollTimer.current) {
                window.clearInterval(itemsPollTimer.current);
                itemsPollTimer.current = null;
            }
            return;
        }

        fetchItems(jobId);
        if (!itemsPollTimer.current) {
            itemsPollTimer.current = window.setInterval(() => fetchItems(jobId), 1000);
        }

        return () => {
            if (itemsPollTimer.current) {
                window.clearInterval(itemsPollTimer.current);
                itemsPollTimer.current = null;
            }
        };
    }, [latestJob?.id, latestJob?.status]);

    // Poll scrape logs for live progress
    useEffect(() => {
        const jobId = latestJob?.id;
        const active = Boolean(jobId) && (latestJob?.status === 'Running' || latestJob?.status === 'Starting');

        if (!active) {
            if (logPollTimer.current) {
                window.clearInterval(logPollTimer.current);
                logPollTimer.current = null;
            }
            logOffsetRef.current = 0;
            setLiveState({ jobId: null, state: liveState?.state || {} });
            return;
        }

        const tick = async () => {
            try {
                const offset = Number(logOffsetRef.current || 0);
                const res = await axios.get(`/api/scrape/logs/${jobId}?offset=${offset}`);
                const nextOffset = res.data?.next_offset ?? offset;
                const chunk = res.data?.text || '';
                if (chunk) {
                    setLiveState((prev) => {
                        const prevState = (prev && prev.jobId === jobId) ? (prev.state || {}) : {};
                        const parsed = parseScrapeLogChunk(chunk, prevState);
                        return { jobId, state: parsed };
                    });
                }
                logOffsetRef.current = nextOffset;
            } catch {
                // ignore
            }
        };

        // immediate
        tick();
        if (!logPollTimer.current) {
            logPollTimer.current = window.setInterval(tick, 400);
        }

        return () => {
            if (logPollTimer.current) {
                window.clearInterval(logPollTimer.current);
                logPollTimer.current = null;
            }
        };
    }, [latestJob?.id, latestJob?.status]);

    // Reset live state when current_file changes
    useEffect(() => {
        const job = latestJob;
        const jobId = job?.id;
        const status = String(job?.status || '');
        const active = Boolean(jobId) && (status === 'Running' || status === 'Starting');
        if (!active) {
            lastPreviewFileRef.current = '';
            return;
        }

        const currentFile = String(job?.current_file || '').trim();
        if (!currentFile) return;

        const prevFile = String(lastPreviewFileRef.current || '');
        if (prevFile && prevFile === currentFile) return;
        lastPreviewFileRef.current = currentFile;

        resetLiveStateForNewFile(
            jobId,
            currentFile,
            Number(job?.current || 0),
            Number(job?.total || 0),
            getExpectedScrapeCrawlerCount(config)
        );
    }, [latestJob?.id, latestJob?.status, latestJob?.current_file, latestJob?.current, latestJob?.total, config]);

    // Keyboard handler for detail modal
    useEffect(() => {
        if (!detail.open) return;
        const onKeyDown = (e) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                closeDetail();
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [detail.open, closeDetail]);

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                    <Activity className="h-5 w-5 text-primary" />
                    {tr('tab.scrape')}
                </h2>
                <button
                    type="button"
                    aria-label={tr('common.settings')}
                    onClick={handleToggleSettings}
                    className="inline-flex h-9 w-9 items-center justify-center text-muted-foreground hover:text-foreground"
                >
                    <Settings
                        className={cn(
                            'h-5 w-5 mr-banana-gear',
                            showSettings ? 'mr-banana-gear--open' : '',
                            gearSpin ? 'mr-banana-gear--spin' : ''
                        )}
                    />
                </button>
            </div>

            {showSettings && (
                <div className="mr-banana-settings-panel">
                    <ScrapeSettingsPanel
                        tr={tr}
                        dirPickerField={dirPickerField}
                        onPickScrapeDir={handlePickScrapeDir}
                        onPickScrapeOutputDir={handlePickScrapeOutputDir}
                    />
                </div>
            )}

            <ScrapeControlBar tr={tr} />

            <ScrapeLivePreview tr={tr} />

            <ScrapeHistoryTable
                tr={tr}
                uiLang={uiLang}
                onOpenLogViewer={openLogViewer}
                onOpenDetail={openDetail}
                onClearHistory={handleClearHistory}
                broomSweep={broomSweep}
                playBrushCleanSfx={playBrushCleanSfx}
                startBroomSweep={startBroomSweep}
            />

            <ScrapeDetailModal
                open={detail.open}
                item={detail.item}
                onClose={closeDetail}
                tr={tr}
            />

            {/* Remote Directory Browser Modal */}
            <DirectoryBrowserModal
                isOpen={showDirBrowser}
                onClose={() => setShowDirBrowser(false)}
                onSelect={handleDirBrowserSelect}
                title={dirBrowserTarget === 'input' ? tr('scrape.dirPicker.inputTitle') : tr('scrape.dirPicker.outputTitle')}
                initialDir={dirBrowserTarget === 'input' ? config.scrape_dir : config.scrape_output_dir}
                tr={tr}
            />
        </div>
    );
}

export default ScrapeTab;
