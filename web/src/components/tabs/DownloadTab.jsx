/**
 * DownloadTab - Download management tab component
 * Uses downloadStore for state management
 */
import React, { useMemo, useState, useCallback } from 'react';
import axios from 'axios';
import { History, Download, Settings, ChevronDown, AlertCircle } from 'lucide-react';
import { t } from '../../i18n';
import { Button, Card, Input, Select, cn } from '../ui';
import { clamp, extractCodeFromUrl, formatDateTime } from '../../utils/format';
import { useToast } from '../Toast';
import { StatusIcon as NewStatusIcon } from '../StatusBadge';
import { EmptyState } from '../EmptyState';
import { getStatusLabel } from '../StatusIcons';
import { InfoTooltip } from '../InfoTooltip';
import { BrushCleaningIcon } from '../Icons';
import { useGearAnimation, useBroomAnimation, playSettingsOpenSfx, stopSettingsOpenSfx, playBrushCleanSfx } from '../../hooks';
import { useDownloadStore } from '../../stores';
import { useScrapeStore } from '../../stores/scrapeStore';

/**
 * Merge history and active tasks into unified rows
 */
function useMergedRows(history, activeTasks) {
    return useMemo(() => {
        const activeById = new Map((activeTasks || []).map((t) => [String(t.id), t]));
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

        // 默认按创建时间倒序；没有 created_at 的放在最上面
        rows.sort((a, b) => {
            const at = a.created_at ? new Date(a.created_at).getTime() : Number.POSITIVE_INFINITY;
            const bt = b.created_at ? new Date(b.created_at).getTime() : Number.POSITIVE_INFINITY;
            return bt - at;
        });

        return rows;
    }, [activeTasks, history]);
}

/**
 * DownloadTab Component
 */
export function DownloadTab({
    uiLang,
    dirPickerField,
    setDirPickerField,
    openLogViewer,
    setContextMenu,
}) {
    const toast = useToast();
    const tr = useCallback((key, vars) => t(uiLang, key, vars), [uiLang]);

    // Store state
    const {
        url, setUrl,
        loading, setLoading,
        history, activeTasks,
        config, setConfig,
        configSaving, setConfigSaving,
        fetchHistory,
        clearHistory,
    } = useDownloadStore();

    // Get scrape config for sync before download-then-scrape
    const scrapeConfig = useScrapeStore((s) => s.config);

    // Local UI state
    const [showSettings, setShowSettings] = useState(false);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [advancedTab, setAdvancedTab] = useState('download');
    const [clearing, setClearing] = useState(false);

    // Animation hooks
    const gearAnim = useGearAnimation();
    const broomAnim = useBroomAnimation();

    // Merged rows
    const mergedRows = useMergedRows(history, activeTasks);

    const outputDirEmpty = !String(config.outputDir || '').trim();

    // Directory picker
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

    const handlePickOutputDir = async () => {
        setDirPickerField('download_output_dir');
        const picked = await chooseDirectory({
            title: '选择下载输出目录',
            initialDir: config.outputDir,
        });
        if (picked) setConfig({ outputDir: picked });
        setDirPickerField(null);
    };

    // Normalize jable URL input
    const normalizeJableInput = (value) => {
        const s = String(value || '').trim();
        if (!s) return '';
        const lowered = s.toLowerCase();
        if (lowered.includes('jable.tv')) {
            if (lowered.startsWith('http://') || lowered.startsWith('https://')) return s;
            return `https://${s.replace(/^\/+/, '')}`;
        }
        if (lowered.startsWith('http://') || lowered.startsWith('https://')) return s;
        const code = s.replace(/\s+/g, '').toLowerCase();
        return `https://jable.tv/videos/${code}/`;
    };

    // Download handler
    const handleDownload = async (e) => {
        e.preventDefault();
        if (!url) return;

        const payloadUrl = normalizeJableInput(url);
        setLoading(true);

        try {
            const out = String(config.outputDir || '').trim();
            if (!out) {
                toast.error(t(uiLang, 'download.error.noOutputDir'));
                return;
            }

            // Sync scrape config if download-then-scrape is enabled
            if (config.scrapeAfter && scrapeConfig) {
                try {
                    const payload = { ...scrapeConfig };
                    delete payload.scrape_sources_fallback;
                    delete payload.scrape_sources_directors;
                    delete payload.scrape_sources_series;
                    delete payload.scrape_sources_want;
                    await axios.post('/api/scrape/config', payload);
                } catch (err) {
                    toast.warning('已勾选"下载后刮削"，但同步刮削配置失败：' + (err.response?.data?.detail || err.message));
                }
            }

            await axios.post('/api/download', {
                url: payloadUrl,
                output_dir: out,
                scrape_after_download: Boolean(config.scrapeAfter),
            });
            setUrl('');
            fetchHistory();
        } catch (err) {
            toast.error('Failed to start download: ' + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    // Clear history handler
    const handleClearHistory = async () => {
        if (clearing) return;
        setClearing(true);
        try {
            await clearHistory();
        } catch (err) {
            console.error('Failed to clear download history', err);
        } finally {
            setClearing(false);
        }
    };

    // Settings gear click
    const handleSettingsClick = () => {
        if (gearAnim.isAnimating()) return;
        setShowSettings((v) => {
            const next = !v;
            if (next) {
                gearAnim.start();
                playSettingsOpenSfx();
            } else {
                stopSettingsOpenSfx();
            }
            return next;
        });
    };

    // Broom click
    const handleBroomClick = () => {
        if (clearing) return;
        playBrushCleanSfx();
        broomAnim.start();
        handleClearHistory();
    };

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                    <Download className="h-5 w-5 text-primary" />
                    {tr('tab.download')}
                </h2>
                <button
                    type="button"
                    aria-label={tr('common.settings')}
                    onClick={handleSettingsClick}
                    className="inline-flex h-9 w-9 items-center justify-center text-muted-foreground hover:text-foreground"
                >
                    <Settings className={cn('h-5 w-5 mr-banana-gear', showSettings ? 'mr-banana-gear--open' : '', gearAnim.spinning ? 'mr-banana-gear--spin' : '')} />
                </button>
            </div>

            {/* Settings Panel */}
            {showSettings && (
                <Card className="p-6 space-y-5">
                    <div className="space-y-3">
                        <div className="grid gap-2">
                            <div className="flex items-center gap-2 text-sm">
                                <div>{tr('download.settings.outputDir')}</div>
                                {outputDirEmpty && (
                                    <AlertCircle className="h-4 w-4 text-amber-500" title={tr('download.error.noOutputDir')} />
                                )}
                            </div>
                            <Input
                                placeholder={tr('common.chooseDir')}
                                value={config.outputDir}
                                readOnly
                                disabled={Boolean(dirPickerField) || configSaving}
                                onClick={handlePickOutputDir}
                            />
                        </div>
                    </div>

                    {showAdvanced && (
                        <div className="space-y-3">
                            <div className="flex flex-wrap items-center gap-2">
                                {[
                                    { key: 'network', label: tr('common.section.network') },
                                    { key: 'download', label: tr('common.section.download') },
                                ].map((it) => (
                                    <button
                                        key={it.key}
                                        type="button"
                                        onClick={() => setAdvancedTab(it.key)}
                                        className={cn(
                                            'rounded-md border px-2 py-1 text-xs',
                                            advancedTab === it.key
                                                ? 'bg-muted text-foreground'
                                                : 'bg-transparent text-muted-foreground hover:text-foreground'
                                        )}
                                    >
                                        {it.label}
                                    </button>
                                ))}
                            </div>

                            {advancedTab === 'network' && (
                                <div className="space-y-3">
                                    <label className="flex items-center gap-2 text-sm">
                                        <input
                                            type="checkbox"
                                            checked={config.useProxy}
                                            onChange={(e) => setConfig({ useProxy: e.target.checked })}
                                            disabled={configSaving}
                                        />
                                        {tr('download.settings.network.useProxy')}
                                    </label>
                                    {config.useProxy && (
                                        <div className="grid gap-2 max-w-md">
                                            <div className="flex items-center gap-2">
                                                <div className="text-sm">{tr('download.settings.proxyUrl')}</div>
                                                <InfoTooltip text={tr('download.settings.proxyHint')} />
                                            </div>
                                            <Input
                                                placeholder="http://127.0.0.1:7890"
                                                value={config.proxyUrl}
                                                onChange={(e) => setConfig({ proxyUrl: e.target.value })}
                                                disabled={configSaving}
                                            />
                                        </div>
                                    )}
                                </div>
                            )}

                            {advancedTab === 'download' && (
                                <div className="grid gap-3">
                                    <div className="grid gap-2">
                                        <div className="flex items-center gap-2">
                                            <div className="text-sm">{tr('download.settings.after.label')}</div>
                                            <InfoTooltip text={tr('download.settings.after.note')} />
                                        </div>
                                        <div className="flex flex-wrap gap-6">
                                            <label className="flex items-center gap-2 text-sm">
                                                <input
                                                    type="radio"
                                                    name="downloadScrapeAfter"
                                                    checked={config.scrapeAfter === false}
                                                    onChange={() => setConfig({ scrapeAfter: false })}
                                                    disabled={configSaving}
                                                />
                                                {tr('download.settings.after.no')}
                                            </label>
                                            <label className="flex items-center gap-2 text-sm">
                                                <input
                                                    type="radio"
                                                    name="downloadScrapeAfter"
                                                    checked={config.scrapeAfter === true}
                                                    onChange={() => setConfig({ scrapeAfter: true })}
                                                    disabled={configSaving}
                                                />
                                                {tr('download.settings.after.yes')}
                                            </label>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                                        <label className="grid gap-2 text-sm">
                                            {tr('download.settings.resolution')}
                                            <Select
                                                value={config.resolution}
                                                onChange={(e) => setConfig({ resolution: e.target.value })}
                                                disabled={configSaving}
                                            >
                                                <option value="best">{tr('download.settings.resolution.best')}</option>
                                                <option value="1080p">1080p</option>
                                                <option value="720p">720p</option>
                                                <option value="480p">480p</option>
                                                <option value="360p">360p</option>
                                            </Select>
                                        </label>
                                        <label className="grid gap-2 text-sm">
                                            {tr('download.settings.workers')}
                                            <Input
                                                type="number"
                                                min={1}
                                                max={128}
                                                value={Number(config.workers || 16)}
                                                onChange={(e) => setConfig({ workers: Math.max(1, Math.min(128, Number(e.target.value || 16))) })}
                                                disabled={configSaving}
                                            />
                                        </label>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="flex justify-center pt-1">
                        <button
                            type="button"
                            aria-label={tr('common.advanced')}
                            title={tr('common.advanced')}
                            onClick={() => setShowAdvanced((v) => !v)}
                            className={cn(
                                'inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground transition-transform',
                                !showAdvanced && 'mr-banana-chevron-hint'
                            )}
                        >
                            <ChevronDown className={cn('h-4 w-4 transition-transform', showAdvanced ? 'rotate-180' : '')} />
                        </button>
                    </div>
                </Card>
            )}

            {/* Input Section */}
            <Card className="p-6">
                <form onSubmit={handleDownload} className="space-y-3">
                    <div className="flex gap-4">
                        <Input
                            placeholder={tr('download.input.urlPlaceholder')}
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            className="flex-1"
                        />
                        <Button type="submit" disabled={loading || outputDirEmpty}>
                            {loading ? tr('download.input.starting') : tr('download.input.download')}
                            {outputDirEmpty && (
                                <AlertCircle className="ml-2 h-4 w-4 text-amber-500" title={tr('download.error.noOutputDir')} />
                            )}
                        </Button>
                    </div>
                </form>
            </Card>

            {/* History */}
            <div className="space-y-4">
                <div className="flex items-center justify-between gap-4">
                    <h2 className="flex items-center gap-2 text-lg font-semibold">
                        <History className="h-5 w-5 text-primary" />
                        {tr('download.history.title')}
                    </h2>
                    <button
                        type="button"
                        aria-label={clearing ? tr('download.clearingHistory') : tr('download.clearHistory')}
                        title={clearing ? tr('download.clearingHistory') : tr('download.clearHistory')}
                        disabled={clearing}
                        onClick={handleBroomClick}
                        className={cn(
                            'inline-flex h-9 w-9 items-center justify-center text-muted-foreground hover:text-foreground',
                            'disabled:cursor-not-allowed disabled:opacity-50'
                        )}
                    >
                        <BrushCleaningIcon
                            className={cn(
                                'h-5 w-5 mr-banana-broom',
                                (clearing || broomAnim.sweeping) ? 'mr-banana-broom--sweep' : ''
                            )}
                        />
                    </button>
                </div>
                <Card className="overflow-hidden">
                    <div className="relative w-full overflow-auto">
                        <div className="min-w-[920px] p-2">
                            <div className="grid grid-cols-[10rem_10rem_7rem_9rem_9rem_7rem_4rem] items-center gap-3 rounded-xl border border-border/60 bg-muted/30 px-3 py-2 text-center text-xs font-medium text-muted-foreground">
                                <div>{tr('download.table.code')}</div>
                                <div>{tr('download.table.status')}</div>
                                <div className="whitespace-nowrap">{tr('download.table.scrape')}</div>
                                <div>{tr('download.table.createdAt')}</div>
                                <div>{tr('download.table.completedAt')}</div>
                                <div className="whitespace-nowrap">{tr('download.table.speed')}</div>
                                <div className="whitespace-nowrap">{tr('download.table.log')}</div>
                            </div>

                            <div className="mt-2 space-y-2">
                                {mergedRows.map((item) => {
                                    const status = item.status;
                                    const code = extractCodeFromUrl(item.url);

                                    const scrapeAfter = item.scrape_after_download === null || typeof item.scrape_after_download === 'undefined'
                                        ? null
                                        : Boolean(item.scrape_after_download);
                                    const rawScrapeStatus = item.scrape_status;
                                    const scrapeStatusMap = {
                                        Pending: tr('download.scrapeAfter.pending'),
                                        Starting: tr('download.scrapeAfter.starting'),
                                        Running: tr('download.scrapeAfter.running'),
                                        Completed: tr('download.scrapeAfter.completed'),
                                        Failed: tr('download.scrapeAfter.failed'),
                                        Skipped: tr('download.scrapeAfter.skipped'),
                                    };
                                    const scrapeText = scrapeAfter === null
                                        ? tr('common.none')
                                        : scrapeAfter
                                            ? (scrapeStatusMap[String(rawScrapeStatus || '')] || String(rawScrapeStatus || '待刮削'))
                                            : tr('download.scrapeAfter.disabled');

                                    const rawProgress = typeof item.progress === 'number' ? item.progress : null;
                                    const computedProgress = rawProgress ?? (status === 'Completed' ? 100 : status === 'Failed' ? 0 : 0);
                                    const progressPct = clamp(computedProgress, 0, 100);

                                    const showProgressBar = status === 'Preparing' || status === 'Downloading' || status === 'Paused';

                                    const showSpeed = status === 'Downloading' && item.speed;
                                    const speedText = status === 'Merging'
                                        ? '0'
                                        : showSpeed
                                            ? item.speed
                                            : tr('common.none');

                                    return (
                                        <div
                                            key={item.id}
                                            className={cn(
                                                'group relative overflow-hidden rounded-xl border border-border/60',
                                                'bg-card/65 supports-[backdrop-filter]:bg-card/45 supports-[backdrop-filter]:backdrop-blur-xl',
                                                'transition-colors hover:bg-card/75'
                                            )}
                                            onContextMenu={(e) => {
                                                e.preventDefault();
                                                e.stopPropagation();
                                                setContextMenu({
                                                    x: e.clientX,
                                                    y: e.clientY,
                                                    item,
                                                });
                                            }}
                                        >
                                            {showProgressBar ? (
                                                <div
                                                    className="absolute left-0 bottom-0 h-1 overflow-hidden bg-primary/25"
                                                    style={{ width: `${progressPct}%` }}
                                                >
                                                    <div className="mr-banana-progress-indicator" />
                                                </div>
                                            ) : null}
                                            <div className="relative grid grid-cols-[10rem_10rem_7rem_9rem_9rem_7rem_4rem] items-center gap-3 px-3 pt-3 pb-4 text-center">
                                                <div className="min-w-0 text-sm font-medium">
                                                    {item.url ? (
                                                        <a
                                                            href={item.url}
                                                            target="_blank"
                                                            rel="noreferrer"
                                                            className="truncate underline underline-offset-4 block text-center"
                                                            title={item.url}
                                                        >
                                                            {code}
                                                        </a>
                                                    ) : (
                                                        <span className="text-muted-foreground">-</span>
                                                    )}
                                                </div>
                                                <div className="min-w-0">
                                                    <div className="flex items-center justify-center gap-2 min-w-0">
                                                        <NewStatusIcon status={status} type="download" error={item.error} />
                                                        <span className="truncate text-sm">{getStatusLabel(status, uiLang)}</span>
                                                    </div>
                                                </div>
                                                <div className="text-muted-foreground whitespace-nowrap text-sm">{scrapeText}</div>
                                                <div
                                                    className="text-muted-foreground tabular-nums text-xs truncate"
                                                    title={formatDateTime(item.created_at)}
                                                >
                                                    {formatDateTime(item.created_at)}
                                                </div>
                                                <div
                                                    className="text-muted-foreground tabular-nums text-xs truncate"
                                                    title={formatDateTime(item.completed_at)}
                                                >
                                                    {formatDateTime(item.completed_at)}
                                                </div>
                                                <div className="text-muted-foreground whitespace-nowrap tabular-nums text-sm">{speedText}</div>
                                                <div>
                                                    <button
                                                        type="button"
                                                        className={cn(
                                                            'inline-flex items-center justify-center rounded-md px-2 py-1 text-sm',
                                                            'hover:bg-accent hover:text-accent-foreground',
                                                            'text-muted-foreground'
                                                        )}
                                                        onClick={() => openLogViewer({ kind: 'download', id: item.id })}
                                                    >
                                                        {tr('common.view')}
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}

                                {mergedRows.length === 0 && (
                                    <EmptyState
                                        type="download"
                                        title={tr('download.table.empty')}
                                        description={tr('download.table.emptyHint')}
                                    />
                                )}
                            </div>
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    );
}

export default DownloadTab;
