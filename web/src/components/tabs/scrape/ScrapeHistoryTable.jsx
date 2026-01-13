/**
 * ScrapeHistoryTable - History table showing scrape job records
 */
import React from 'react';
import { History } from 'lucide-react';
import { Card, cn } from '../../ui';
import { BrushCleaningIcon } from '../../Icons';
import { StatusIcon as NewStatusIcon } from '../../StatusBadge';
import { EmptyState } from '../../EmptyState';
import { useScrapeStore } from '../../../stores/scrapeStore';
import { clamp, extractCodeFromPath } from '../../../utils/format';
import { getExpectedScrapeCrawlerCount } from '../../../utils/appHelpers';
import { computeScrapeVirtualFilePhase } from '../../../scrapeProgress';

/**
 * Get scrape status label
 */
function getScrapeStatusLabel(status, uiLang) {
    const labels = {
        'zh-CN': {
            Starting: '启动中',
            Running: '进行中',
            Completed: '已完成',
            Failed: '失败',
        },
        'zh-TW': {
            Starting: '啟動中',
            Running: '進行中',
            Completed: '已完成',
            Failed: '失敗',
        },
        en: {
            Starting: 'Starting',
            Running: 'Running',
            Completed: 'Completed',
            Failed: 'Failed',
        },
    };
    const langLabels = labels[uiLang] || labels['zh-CN'];
    return langLabels[status] || status;
}

// Import shared formatDateTime
import { formatDateTime } from '../../../utils/format';

export function ScrapeHistoryTable({
    tr,
    uiLang,
    onOpenLogViewer,
    onOpenDetail,
    onClearHistory,
    broomSweep,
    playBrushCleanSfx,
    startBroomSweep,
}) {
    const config = useScrapeStore((s) => s.config);
    const history = useScrapeStore((s) => s.history);
    const clearingHistory = useScrapeStore((s) => s.clearingHistory);
    const liveState = useScrapeStore((s) => s.liveState);
    const getLatestJob = useScrapeStore((s) => s.getLatestJob);

    const latestJob = getLatestJob();

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between gap-4">
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                    <History className="h-5 w-5 text-primary" />
                    {tr('scrape.history')}
                </h2>
                <button
                    type="button"
                    aria-label={clearingHistory ? tr('scrape.clearingHistory') : tr('scrape.clearHistory')}
                    title={clearingHistory ? tr('scrape.clearingHistory') : tr('scrape.clearHistory')}
                    disabled={clearingHistory}
                    onClick={() => {
                        if (clearingHistory) return;
                        playBrushCleanSfx?.();
                        startBroomSweep?.();
                        onClearHistory?.();
                    }}
                    className={cn(
                        'inline-flex h-9 w-9 items-center justify-center text-muted-foreground hover:text-foreground',
                        'disabled:cursor-not-allowed disabled:opacity-50'
                    )}
                >
                    <BrushCleaningIcon
                        className={cn(
                            'h-5 w-5 mr-banana-broom',
                            (clearingHistory || broomSweep) ? 'mr-banana-broom--sweep' : ''
                        )}
                    />
                </button>
            </div>
            <Card className="overflow-hidden">
                <div className="relative w-full overflow-auto">
                    <div className="min-w-[860px] p-2">
                        <div className="grid w-full grid-cols-[8rem_10rem_1fr_1fr_6rem_6rem] items-center gap-3 rounded-xl border border-border/60 bg-muted/30 px-3 py-2 text-center text-xs font-medium text-muted-foreground">
                            <div>{tr('scrape.code')}</div>
                            <div>{tr('scrape.status')}</div>
                            <div>{tr('scrape.startTime')}</div>
                            <div>{tr('scrape.endTime')}</div>
                            <div className="whitespace-nowrap">{tr('scrape.log')}</div>
                            <div className="whitespace-nowrap">{tr('scrape.detail')}</div>
                        </div>

                        <div className="mt-2 space-y-2">
                            {(Array.isArray(history) ? [...history] : []).map((row, idx) => {
                                const jobId = Number(row?.job_id || 0);
                                const rawStatus = String(row?.job_status || '');
                                const isCurrent = Boolean(row?.is_current);
                                const status = (!isCurrent && (rawStatus === 'Running' || rawStatus === 'Starting'))
                                    ? 'Completed'
                                    : rawStatus;
                                const path = String(row?.path || '').trim();

                                const showProgressBar = isCurrent && (rawStatus === 'Running' || rawStatus === 'Starting');
                                const live = (liveState?.jobId === jobId) ? (liveState.state || {}) : {};
                                const liveFile = (showProgressBar && typeof live?.file === 'string' && live.file.trim()) ? live.file.trim() : '';
                                const liveName = (showProgressBar && typeof live?.currentFileName === 'string' && live.currentFileName.trim())
                                    ? live.currentFileName.trim()
                                    : ((showProgressBar && typeof live?.file_name === 'string' && live.file_name.trim()) ? live.file_name.trim() : '');

                                const effectiveLogFile = liveFile || liveName || path;
                                const code = showProgressBar
                                    ? extractCodeFromPath(effectiveLogFile)
                                    : ((typeof row?.code === 'string' && row.code.trim()) ? row.code.trim() : extractCodeFromPath(path));

                                const filePhase = showProgressBar
                                    ? computeScrapeVirtualFilePhase(live, {
                                        expectedCrawlers: getExpectedScrapeCrawlerCount(config),
                                        translateEnabled: Boolean(config.scrape_translate_enabled),
                                        downloadPoster: Boolean(config.scrape_download_poster),
                                        downloadFanart: Boolean(config.scrape_download_fanart),
                                        downloadPreviews: Boolean(config.scrape_download_previews),
                                        downloadTrailer: Boolean(config.scrape_download_trailer),
                                        previewLimit: Number(config.scrape_preview_limit || 0),
                                        writeNfo: Boolean(config.scrape_write_nfo),
                                    })
                                    : 0;

                                const progressPct = showProgressBar ? clamp(filePhase * 100, 0, 100) : 0;

                                return (
                                    <div
                                        key={`${jobId}-${idx}-${path || code}`}
                                        className={cn(
                                            'group relative overflow-hidden rounded-xl border border-border/60',
                                            'bg-card/65 supports-[backdrop-filter]:bg-card/45 supports-[backdrop-filter]:backdrop-blur-xl',
                                            'transition-colors hover:bg-card/75'
                                        )}
                                    >
                                        {showProgressBar ? (
                                            <div
                                                className="absolute left-0 bottom-0 h-1 overflow-hidden bg-gradient-to-r from-primary/55 via-primary/35 to-primary/15"
                                                style={{ width: `${progressPct}%` }}
                                            >
                                                <div className="mr-banana-progress-indicator" />
                                            </div>
                                        ) : null}
                                        <div className="relative grid w-full grid-cols-[8rem_10rem_1fr_1fr_6rem_6rem] items-center gap-3 px-3 py-3 text-center">
                                            <div className="font-medium text-sm">
                                                {code && code !== '-' ? code : <span className="text-muted-foreground">-</span>}
                                            </div>
                                            <div className="min-w-0">
                                                <div className="flex items-center justify-center gap-2">
                                                    <NewStatusIcon status={status} type="scrape" />
                                                    <span className="truncate text-sm">{getScrapeStatusLabel(status, uiLang)}</span>
                                                </div>
                                            </div>
                                            <div
                                                className="text-muted-foreground tabular-nums text-xs truncate"
                                                title={formatDateTime(row?.job_created_at)}
                                            >
                                                {formatDateTime(row?.job_created_at)}
                                            </div>
                                            <div
                                                className="text-muted-foreground tabular-nums text-xs truncate"
                                                title={row?.item_completed_at
                                                    ? formatDateTime(row?.item_completed_at)
                                                    : (row?.job_completed_at ? formatDateTime(row?.job_completed_at) : '-')
                                                }
                                            >
                                                {row?.item_completed_at
                                                    ? formatDateTime(row?.item_completed_at)
                                                    : (row?.job_completed_at ? formatDateTime(row?.job_completed_at) : <span className="text-muted-foreground">-</span>)
                                                }
                                            </div>
                                            <div>
                                                <button
                                                    type="button"
                                                    className={cn(
                                                        'inline-flex items-center justify-center rounded-md px-2 py-1 text-sm',
                                                        'hover:bg-accent hover:text-accent-foreground',
                                                        'text-muted-foreground'
                                                    )}
                                                    onClick={() => {
                                                        const j = Number(row?.job_id || 0);
                                                        if (!j) return;
                                                        // Get the filename from path for item-level logs
                                                        const filePath = String(row?.path || '').trim();
                                                        const fileName = filePath ? filePath.split('/').pop() : null;
                                                        if (fileName) {
                                                            // Open item-specific log
                                                            onOpenLogViewer?.({ kind: 'scrape-item', id: j, file: fileName });
                                                        } else {
                                                            // Fallback to job-level log
                                                            onOpenLogViewer?.({ kind: 'scrape', id: j });
                                                        }
                                                    }}
                                                >
                                                    {tr('common.view')}
                                                </button>
                                            </div>
                                            <div>
                                                <button
                                                    type="button"
                                                    className={cn(
                                                        'inline-flex items-center justify-center rounded-md px-2 py-1 text-sm',
                                                        'hover:bg-accent hover:text-accent-foreground',
                                                        'text-muted-foreground'
                                                    )}
                                                    onClick={() => onOpenDetail?.(row)}
                                                >
                                                    {tr('common.open')}
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}

                            {(!Array.isArray(history) || history.length === 0) && (
                                <EmptyState
                                    type="scrape"
                                    title={tr('scrape.table.empty')}
                                    description={tr('scrape.table.emptyHint')}
                                />
                            )}
                        </div>
                    </div>
                </div>
            </Card>
        </div>
    );
}

export default ScrapeHistoryTable;
