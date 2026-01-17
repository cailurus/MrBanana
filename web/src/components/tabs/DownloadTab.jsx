/**
 * DownloadTab - Download management tab component
 * Uses downloadStore for state management
 */
import React, { useMemo, useState, useCallback, useEffect } from 'react';
import axios from 'axios';
import { History, Download, Settings, ChevronDown, AlertCircle, Search, Copy, Check, ExternalLink, Magnet, Play, Clock, Users, Tag, Building, Film, Loader2, Plus, Bell, Link2 } from 'lucide-react';
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
import { DirectoryBrowserModal } from '../modals';

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
 * MagnetLinkItem - Individual magnet link display
 */
function MagnetLinkItem({ magnet, tr }) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(magnet.url);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy', err);
        }
    };

    return (
        <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
            <Link2 className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate" title={magnet.name}>
                    {magnet.name}
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {magnet.size && <span>{magnet.size}</span>}
                    {magnet.is_hd && (
                        <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-600 dark:text-amber-400">
                            {tr('download.search.hd')}
                        </span>
                    )}
                    {magnet.has_subtitle && (
                        <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-600 dark:text-blue-400">
                            {tr('download.search.subtitle')}
                        </span>
                    )}
                </div>
            </div>
            <button
                type="button"
                onClick={handleCopy}
                className={cn(
                    'inline-flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors',
                    copied
                        ? 'bg-green-500/20 text-green-600 dark:text-green-400'
                        : 'bg-primary/10 text-primary hover:bg-primary/20'
                )}
            >
                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                {copied ? tr('download.search.copied') : tr('download.search.copyMagnet')}
            </button>
        </div>
    );
}

/**
 * SearchResultPreview - Display search results
 */
function SearchResultPreview({ result, tr, onDownloadFromJable, downloading, outputDirEmpty, onAddToSubscription, addingToSubscription }) {
    if (!result) return null;

    // Not found state
    if (!result.found) {
        return (
            <Card className="p-6">
                <div className="text-center py-8">
                    <Search className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
                    <h3 className="text-lg font-medium text-muted-foreground">
                        {tr('download.search.notFound')}
                    </h3>
                    <p className="text-sm text-muted-foreground/70 mt-1">
                        {tr('download.search.notFoundHint')}
                    </p>
                </div>
            </Card>
        );
    }

    return (
        <Card className="p-6 space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                    <Search className="h-5 w-5 text-primary" />
                    {tr('download.search.title')}
                </h3>
                <div className="flex items-center gap-3">
                    <button
                        type="button"
                        onClick={onAddToSubscription}
                        disabled={addingToSubscription}
                        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
                        title={tr('download.search.addToSubscription')}
                    >
                        {addingToSubscription ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                            <Bell className="h-3 w-3" />
                        )}
                        {tr('download.search.addToSubscription')}
                    </button>
                    {result.javdb_found && result.javdb_url && (
                        <a
                            href={result.javdb_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                        >
                            <ExternalLink className="h-3 w-3" />
                            {tr('download.search.viewOnJavdb')}
                        </a>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
                {/* Left: Cover Image */}
                <div className="space-y-3">
                    {result.cover_url ? (
                        <div className="relative aspect-[2/3] rounded-lg overflow-hidden bg-muted">
                            <img
                                src={result.cover_url}
                                alt={result.title || result.code}
                                className="w-[200%] h-full object-cover object-right"
                                onError={(e) => {
                                    e.target.style.display = 'none';
                                }}
                            />
                        </div>
                    ) : (
                        <div className="aspect-[2/3] rounded-lg bg-muted flex items-center justify-center">
                            <Film className="h-16 w-16 text-muted-foreground/30" />
                        </div>
                    )}

                    {/* Jable Download Button */}
                    <div className="space-y-2">
                        {result.jable_available ? (
                            <Button
                                className="w-full"
                                onClick={onDownloadFromJable}
                                disabled={downloading || outputDirEmpty}
                            >
                                <Download className="h-4 w-4 mr-2" />
                                {downloading ? tr('download.input.starting') : tr('download.search.downloadFromJable')}
                                {outputDirEmpty && (
                                    <AlertCircle className="ml-2 h-4 w-4 text-amber-500" title={tr('download.error.noOutputDir')} />
                                )}
                            </Button>
                        ) : (
                            <Button className="w-full" disabled variant="secondary">
                                <Download className="h-4 w-4 mr-2" />
                                {tr('download.search.jableNotAvailable')}
                            </Button>
                        )}
                    </div>
                </div>

                {/* Right: Metadata */}
                <div className="space-y-4 min-w-0">
                    {/* Title & Code */}
                    <div>
                        <div className="text-xl font-bold">{result.code}</div>
                        {result.title && result.title !== result.code && (
                            <div className="text-sm text-muted-foreground mt-1">{result.title}</div>
                        )}
                    </div>

                    {/* Metadata Grid */}
                    <div className="grid grid-cols-2 gap-3 text-sm">
                        {result.release && (
                            <div className="flex items-center gap-2">
                                <Clock className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">{tr('download.search.release')}:</span>
                                <span>{result.release}</span>
                            </div>
                        )}
                        {result.runtime && (
                            <div className="flex items-center gap-2">
                                <Play className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">{tr('download.search.runtime')}:</span>
                                <span>{result.runtime} {tr('download.search.minutes')}</span>
                            </div>
                        )}
                        {result.studio && (
                            <div className="flex items-center gap-2">
                                <Building className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">{tr('download.search.studio')}:</span>
                                <span>{result.studio}</span>
                            </div>
                        )}
                        {result.series && (
                            <div className="flex items-center gap-2">
                                <Film className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">{tr('download.search.series')}:</span>
                                <span>{result.series}</span>
                            </div>
                        )}
                        {result.rating && (
                            <div className="flex items-center gap-2">
                                <span className="text-muted-foreground">{tr('download.search.rating')}:</span>
                                <span className="text-amber-500">★ {result.rating}</span>
                            </div>
                        )}
                    </div>

                    {/* Actors */}
                    {result.actors && result.actors.length > 0 && (
                        <div>
                            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                                <Users className="h-4 w-4" />
                                {tr('download.search.actors')}
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {result.actors.map((actor, idx) => (
                                    <span
                                        key={idx}
                                        className="px-2 py-1 rounded-full bg-primary/10 text-primary text-xs"
                                    >
                                        {actor}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Tags */}
                    {result.tags && result.tags.length > 0 && (
                        <div>
                            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                                <Tag className="h-4 w-4" />
                                {tr('download.search.tags')}
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {result.tags.map((tag, idx) => (
                                    <span
                                        key={idx}
                                        className="px-2 py-1 rounded bg-muted text-xs text-muted-foreground"
                                    >
                                        {tag}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Magnet Links */}
                    <div className="min-w-0">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                            <Magnet className="h-4 w-4" />
                            {tr('download.search.magnetLinks')}
                        </div>
                        {result.magnet_links && result.magnet_links.length > 0 ? (
                            <div className="space-y-2 max-h-48 overflow-y-auto overflow-x-hidden">
                                {result.magnet_links.map((magnet, idx) => (
                                    <MagnetLinkItem key={idx} magnet={magnet} tr={tr} />
                                ))}
                            </div>
                        ) : (
                            <div className="text-sm text-muted-foreground/70 p-3 rounded-lg bg-muted/30">
                                {tr('download.search.noMagnet')}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </Card>
    );
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
        fetchConfig,
        clearHistory,
        saveConfig,
        // Search state
        searchQuery, setSearchQuery,
        searchResult, setSearchResult,
        searching,
        search,
        clearSearchResult,
    } = useDownloadStore();

    // Get scrape config for sync before download-then-scrape
    const scrapeConfig = useScrapeStore((s) => s.config);

    // 初始化加载配置
    useEffect(() => {
        fetchConfig();
        fetchHistory();
    }, [fetchConfig, fetchHistory]);

    // Local UI state
    const [showSettings, setShowSettings] = useState(false);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [advancedTab, setAdvancedTab] = useState('download');
    const [clearing, setClearing] = useState(false);
    const [showDirBrowser, setShowDirBrowser] = useState(false);
    const [downloadingFromJable, setDownloadingFromJable] = useState(false);
    const [addingToSubscription, setAddingToSubscription] = useState(false);

    // Animation hooks
    const gearAnim = useGearAnimation();
    const broomAnim = useBroomAnimation();

    // Merged rows
    const mergedRows = useMergedRows(history, activeTasks);

    const outputDirEmpty = !String(config.outputDir || '').trim();

    // Directory picker - supports native dialog (localhost) or remote browser
    const chooseDirectory = async ({ title, initialDir }) => {
        try {
            const res = await axios.post('/api/system/choose-directory', {
                title,
                initial_dir: initialDir || null,
            });
            return res?.data?.path || null;
        } catch (err) {
            // If 403 (not localhost), open remote directory browser
            if (err.response?.status === 403) {
                return null; // Signal to use remote browser
            }
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
        if (picked) {
            setConfig({ outputDir: picked });
            await saveConfig({ outputDir: picked });
        } else if (picked === null) {
            // Native dialog not available - show remote browser
            setShowDirBrowser(true);
        }
        setDirPickerField(null);
    };

    const handleDirBrowserSelect = async (path) => {
        setConfig({ outputDir: path });
        await saveConfig({ outputDir: path });
    };

    // Search handler
    const handleSearch = async (e) => {
        e.preventDefault();
        if (!searchQuery.trim()) return;

        try {
            await search(searchQuery.trim());
        } catch (err) {
            toast.error('搜索失败: ' + (err.response?.data?.detail || err.message));
        }
    };

    // Download from Jable handler
    const handleDownloadFromJable = async () => {
        if (!searchResult?.jable_url || downloadingFromJable) return;

        const out = String(config.outputDir || '').trim();
        if (!out) {
            toast.error(t(uiLang, 'download.error.noOutputDir'));
            return;
        }

        setDownloadingFromJable(true);
        try {
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
                url: searchResult.jable_url,
                output_dir: out,
                scrape_after_download: Boolean(config.scrapeAfter),
            });
            toast.success('下载任务已添加');
            fetchHistory();
        } catch (err) {
            toast.error('下载失败: ' + (err.response?.data?.detail || err.message));
        } finally {
            setDownloadingFromJable(false);
        }
    };

    // Add to subscription handler
    const handleAddToSubscription = async () => {
        if (!searchResult?.code || addingToSubscription) return;

        setAddingToSubscription(true);
        try {
            await axios.post('/api/subscription', {
                code: searchResult.code,
                magnet_links: searchResult.magnet_links || [],
            });
            toast.success(tr('download.search.subscriptionAdded'));
        } catch (err) {
            if (err.response?.status === 409) {
                toast.warning(tr('download.search.alreadySubscribed'));
            } else {
                toast.error('添加订阅失败: ' + (err.response?.data?.detail || err.message));
            }
        } finally {
            setAddingToSubscription(false);
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

            {/* Search Section */}
            <Card className="p-6">
                <form onSubmit={handleSearch} className="space-y-3">
                    <div className="flex gap-4">
                        <Input
                            placeholder={tr('download.input.urlPlaceholder')}
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="flex-1"
                        />
                        <Button type="submit" disabled={searching || !searchQuery.trim()}>
                            {searching ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    {tr('download.input.starting')}
                                </>
                            ) : (
                                <>
                                    <Search className="h-4 w-4 mr-2" />
                                    {tr('download.input.download')}
                                </>
                            )}
                        </Button>
                    </div>
                </form>
            </Card>

            {/* Search Result Preview */}
            {searchResult && (
                <SearchResultPreview
                    result={searchResult}
                    tr={tr}
                    onDownloadFromJable={handleDownloadFromJable}
                    downloading={downloadingFromJable}
                    outputDirEmpty={outputDirEmpty}
                    onAddToSubscription={handleAddToSubscription}
                    addingToSubscription={addingToSubscription}
                />
            )}

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

            {/* Remote Directory Browser Modal */}
            <DirectoryBrowserModal
                isOpen={showDirBrowser}
                onClose={() => setShowDirBrowser(false)}
                onSelect={handleDirBrowserSelect}
                title={tr('download.settings.outputDir')}
                initialDir={config.outputDir}
                tr={tr}
            />
        </div>
    );
}

export default DownloadTab;
