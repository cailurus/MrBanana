/**
 * DownloadTab - Simple multi-code batch download
 */
import React, { useState, useCallback, useEffect } from 'react';
import axios from 'axios';
import { History, Download, Settings, ChevronDown, AlertCircle, RotateCcw, Trash2 } from 'lucide-react';
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
import { DirectoryBrowserModal } from '../modals';

/**
 * DownloadTab Component
 */
export function DownloadTab({
    uiLang,
    dirPickerField,
    setDirPickerField,
    openLogViewer,
    onResume,
}) {
    const toast = useToast();
    const tr = useCallback((key, vars) => t(uiLang, key, vars), [uiLang]);

    const {
        history, activeTasks,
        config, setConfig,
        configSaving,
        fetchHistory,
        fetchConfig,
        clearHistory,
        saveConfig,
    } = useDownloadStore();

    useEffect(() => {
        fetchConfig();
        fetchHistory();
    }, [fetchConfig, fetchHistory]);

    const [showSettings, setShowSettings] = useState(false);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [advancedTab, setAdvancedTab] = useState('download');
    const [clearing, setClearing] = useState(false);
    const [showDirBrowser, setShowDirBrowser] = useState(false);
    const [codesInput, setCodesInput] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const gearAnim = useGearAnimation();
    const broomAnim = useBroomAnimation();

    const outputDirEmpty = !String(config.outputDir || '').trim();

    // Directory picker
    const chooseDirectory = async ({ title, initialDir }) => {
        try {
            const res = await axios.post('/api/system/choose-directory', { title, initial_dir: initialDir || null });
            return res?.data?.path || null;
        } catch (err) {
            if (err.response?.status === 403) return null;
            toast.error('Failed to choose directory');
            return null;
        }
    };

    const handlePickOutputDir = async () => {
        setDirPickerField('download_output_dir');
        const picked = await chooseDirectory({ title: '选择下载输出目录', initialDir: config.outputDir });
        if (picked) {
            setConfig({ outputDir: picked });
            await saveConfig({ outputDir: picked });
        } else if (picked === null) {
            setShowDirBrowser(true);
        }
        setDirPickerField(null);
    };

    const handleDirBrowserSelect = async (path) => {
        setConfig({ outputDir: path });
        await saveConfig({ outputDir: path });
    };

    // Batch submit codes
    const handleBatchSubmit = async () => {
        const out = String(config.outputDir || '').trim();
        if (!out) {
            toast.error(t(uiLang, 'download.error.noOutputDir'));
            return;
        }

        const codes = codesInput
            .split(/[\n,;\s]+/)
            .map(s => s.trim())
            .filter(Boolean);

        if (codes.length === 0) {
            toast.error('请输入至少一个番号');
            return;
        }

        setSubmitting(true);
        try {
            const res = await axios.post('/api/jable/batch-download', {
                codes,
                output_dir: out,
            });
            const { added, skipped, errors } = res.data;
            if (added > 0) toast.success(`已添加 ${added} 个下载任务`);
            if (skipped.length > 0) toast.info(`跳过 ${skipped.length} 个重复: ${skipped.join(', ')}`);
            if (errors.length > 0) toast.error(`失败: ${errors.join('; ')}`);
            fetchHistory();
            setCodesInput('');
        } catch (err) {
            toast.error('批量下载失败: ' + (err.response?.data?.detail || err.message));
        } finally {
            setSubmitting(false);
        }
    };

    const handleClearHistory = async () => {
        if (clearing) return;
        setClearing(true);
        playBrushCleanSfx();
        broomAnim.start();
        try {
            await clearHistory();
        } finally {
            setClearing(false);
        }
    };

    const handleSettingsClick = () => {
        if (gearAnim.isAnimating()) return;
        setShowSettings(v => {
            const next = !v;
            if (next) { gearAnim.start(); playSettingsOpenSfx(); }
            else stopSettingsOpenSfx();
            return next;
        });
    };

    // Merge history + active
    const activeById = new Map((activeTasks || []).map(t => [String(t.id), t]));
    const mergedRows = (history || []).map(item => ({ ...item, ...(activeById.get(String(item.id)) || {}) }));
    if (mergedRows.length === 0 && activeTasks.length > 0) {
        mergedRows.push(...activeTasks);
    }

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                    <Download className="h-5 w-5 text-primary" />
                    {tr('tab.download')}
                </h2>
                <button type="button" aria-label={tr('common.settings')} onClick={handleSettingsClick}
                    className="inline-flex h-9 w-9 items-center justify-center text-muted-foreground hover:text-foreground">
                    <Settings className={cn('h-5 w-5 mr-banana-gear', showSettings ? 'mr-banana-gear--open' : '', gearAnim.spinning ? 'mr-banana-gear--spin' : '')} />
                </button>
            </div>

            {/* Settings Panel */}
            {showSettings && (
                <Card className="p-6 space-y-5">
                    <div className="grid gap-2">
                        <div className="flex items-center gap-2 text-sm">
                            <div>{tr('download.settings.outputDir')}</div>
                            {outputDirEmpty && <AlertCircle className="h-4 w-4 text-amber-500" />}
                        </div>
                        <Input placeholder={tr('common.chooseDir')} value={config.outputDir} readOnly
                            disabled={!!dirPickerField || configSaving} onClick={handlePickOutputDir} />
                    </div>

                    {showAdvanced && (
                        <div className="space-y-3">
                            <div className="flex flex-wrap items-center gap-2">
                                {[{ key: 'network', label: tr('common.section.network') }, { key: 'download', label: tr('common.section.download') }].map(it => (
                                    <button key={it.key} type="button" onClick={() => setAdvancedTab(it.key)}
                                        className={cn('rounded-md border px-2 py-1 text-xs', advancedTab === it.key ? 'bg-muted text-foreground' : 'bg-transparent text-muted-foreground hover:text-foreground')}>
                                        {it.label}
                                    </button>
                                ))}
                            </div>

                            {advancedTab === 'network' && (
                                <div className="space-y-3">
                                    <label className="flex items-center gap-2 text-sm">
                                        <input type="checkbox" checked={config.useProxy} onChange={e => setConfig({ useProxy: e.target.checked })} disabled={configSaving} />
                                        {tr('download.settings.network.useProxy')}
                                    </label>
                                    {config.useProxy && (
                                        <div className="grid gap-2 max-w-md">
                                            <div className="flex items-center gap-2"><div className="text-sm">{tr('download.settings.proxyUrl')}</div><InfoTooltip text={tr('download.settings.proxyHint')} /></div>
                                            <Input placeholder="http://127.0.0.1:7890" value={config.proxyUrl} onChange={e => setConfig({ proxyUrl: e.target.value })} disabled={configSaving} />
                                        </div>
                                    )}
                                    <div className="grid gap-2 max-w-md">
                                        <div className="flex items-center gap-2">
                                            <div className="text-sm">Jable Cookie (Cloudflare)</div>
                                            <InfoTooltip text="贴入 jable.tv 的 Cookie，用于绕过 Cloudflare 和读取收藏/稍后观看" />
                                        </div>
                                        <Input placeholder="cf_clearance=abc123" value={config.jableCookie}
                                            onChange={e => setConfig({ jableCookie: e.target.value })}
                                            onBlur={() => saveConfig({ jableCookie: config.jableCookie })} disabled={configSaving} />
                                    </div>
                                </div>
                            )}

                            {advancedTab === 'download' && (
                                <div className="grid gap-3">
                                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                                        <label className="grid gap-2 text-sm">{tr('download.settings.resolution')}
                                            <Select value={config.resolution} onChange={e => setConfig({ resolution: e.target.value })} disabled={configSaving}>
                                                <option value="best">{tr('download.settings.resolution.best')}</option>
                                                <option value="1080p">1080p</option><option value="720p">720p</option>
                                                <option value="480p">480p</option><option value="360p">360p</option>
                                            </Select>
                                        </label>
                                        <label className="grid gap-2 text-sm">{tr('download.settings.workers')}
                                            <Input type="number" min={1} max={128} value={Number(config.workers || 16)}
                                                onChange={e => setConfig({ workers: Math.max(1, Math.min(128, Number(e.target.value || 16))) })} disabled={configSaving} />
                                        </label>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="flex justify-center pt-1">
                        <button type="button" aria-label={tr('common.advanced')} title={tr('common.advanced')} onClick={() => setShowAdvanced(v => !v)}
                            className={cn('inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground transition-transform', !showAdvanced && 'mr-banana-chevron-hint')}>
                            <ChevronDown className={cn('h-4 w-4 transition-transform', showAdvanced ? 'rotate-180' : '')} />
                        </button>
                    </div>
                </Card>
            )}

            {/* Batch Input */}
            <Card className="p-6 space-y-3">
                <div className="text-sm font-medium">批量下载 (Multi-code)</div>
                <textarea
                    placeholder="输入番号，每行一个或用逗号/空格分隔&#10;例如:&#10;miaa-330&#10;ssni-369&#10;ipx-580"
                    value={codesInput}
                    onChange={e => setCodesInput(e.target.value)}
                    rows={5}
                    className="w-full rounded-lg border border-border bg-input px-3 py-2 text-sm placeholder:text-muted-foreground resize-y min-h-[100px]"
                />
                <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">
                        {codesInput ? `已输入 ${codesInput.split(/[\n,;\s]+/).filter(Boolean).length} 个番号` : ''}
                    </span>
                    <Button onClick={handleBatchSubmit} disabled={submitting || outputDirEmpty || !codesInput.trim()}>
                        {submitting ? '添加中...' : '开始下载'}
                        {outputDirEmpty && <AlertCircle className="ml-2 h-4 w-4 text-amber-500" />}
                    </Button>
                </div>
            </Card>

            {/* History */}
            <div className="space-y-4">
                <div className="flex items-center justify-between gap-4">
                    <h2 className="flex items-center gap-2 text-lg font-semibold">
                        <History className="h-5 w-5 text-primary" />
                        {tr('download.history.title')}
                    </h2>
                    <button type="button" disabled={clearing} onClick={handleClearHistory}
                        className={cn('inline-flex h-9 w-9 items-center justify-center text-muted-foreground hover:text-foreground', 'disabled:cursor-not-allowed disabled:opacity-50')}>
                        <Trash2 className="h-5 w-5" />
                    </button>
                </div>
                <Card className="overflow-hidden">
                    <div className="relative w-full overflow-auto">
                        <div className="min-w-[800px] p-2">
                            <div className="grid grid-cols-[8rem_8rem_7rem_10rem_6rem_4rem] items-center gap-3 rounded-xl border border-border/60 bg-muted/30 px-3 py-2 text-center text-xs font-medium text-muted-foreground">
                                <div>{tr('download.table.code')}</div>
                                <div>{tr('download.table.status')}</div>
                                <div>{tr('download.table.scrape')}</div>
                                <div>{tr('download.table.createdAt')}</div>
                                <div className="whitespace-nowrap">{tr('download.table.speed')}</div>
                                <div className="whitespace-nowrap">{tr('download.table.log')}</div>
                            </div>
                            <div className="mt-2 space-y-2">
                                {mergedRows.map(item => {
                                    const status = item.status || 'Unknown';
                                    const code = extractCodeFromUrl(item.url);
                                    const progressPct = clamp(typeof item.progress === 'number' ? item.progress : (status === 'Completed' ? 100 : 0), 0, 100);
                                    const showBar = status === 'Preparing' || status === 'Downloading' || status === 'Paused';

                                    return (
                                        <div key={item.id}
                                            className={cn('group relative overflow-hidden rounded-xl border border-border/60', 'bg-card/65 supports-[backdrop-filter]:bg-card/45 supports-[backdrop-filter]:backdrop-blur-xl', 'transition-colors hover:bg-card/75')}>
                                            {showBar && <div className="absolute left-0 bottom-0 h-1 bg-primary/25" style={{ width: `${progressPct}%` }}><div className="mr-banana-progress-indicator" /></div>}
                                            <div className="relative grid grid-cols-[8rem_8rem_7rem_10rem_6rem_4rem] items-center gap-3 px-3 pt-3 pb-4 text-center">
                                                <div className="min-w-0 text-sm font-medium truncate">{code || '-'}</div>
                                                <div className="min-w-0 flex items-center justify-center gap-2">
                                                    <NewStatusIcon status={status} type="download" error={item.error} />
                                                    <span className="truncate text-sm">{getStatusLabel(status, uiLang)}</span>
                                                    {status === 'Failed' && onResume && (
                                                        <button type="button" title={tr('download.menu.resume')} onClick={e => { e.stopPropagation(); onResume(item.id); }}
                                                            className="inline-flex items-center justify-center h-5 w-5 rounded-md text-red-400 hover:text-red-600 transition-colors shrink-0">
                                                            <RotateCcw className="h-3.5 w-3.5" />
                                                        </button>
                                                    )}
                                                </div>
                                                <div className="text-muted-foreground text-sm">-</div>
                                                <div className="text-muted-foreground tabular-nums text-xs truncate" title={formatDateTime(item.created_at)}>{formatDateTime(item.created_at)}</div>
                                                <div className="text-muted-foreground tabular-nums text-sm">{status === 'Downloading' ? (item.speed || '-') : '-'}</div>
                                                <button type="button" onClick={() => openLogViewer({ kind: 'download', id: item.id })}
                                                    className="inline-flex items-center justify-center rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-accent">
                                                    {tr('common.view')}
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })}
                                {mergedRows.length === 0 && <EmptyState type="download" title={tr('download.table.empty')} description={tr('download.table.emptyHint')} />}
                            </div>
                        </div>
                    </div>
                </Card>
            </div>

            <DirectoryBrowserModal isOpen={showDirBrowser} onClose={() => setShowDirBrowser(false)} onSelect={handleDirBrowserSelect}
                title={tr('download.settings.outputDir')} initialDir={config.outputDir} tr={tr} />
        </div>
    );
}

export default DownloadTab;