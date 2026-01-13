import React from 'react';
import { Play, Pause, X, FileText } from 'lucide-react';
import { cn } from './ui';
import { StatusIcon } from './StatusBadge';

/**
 * DownloadHistoryCard - Mobile card view for download history item
 */
export function DownloadHistoryCard({
    item,
    code,
    status,
    statusLabel,
    scrapeText,
    speedText,
    progressPct,
    showProgressBar,
    createdAt,
    completedAt,
    onResume,
    onPause,
    onDelete,
    onViewLog,
    onContextMenu,
    tr,
}) {
    const isPaused = status === 'Paused';
    const isDownloading = status === 'Downloading';
    const canResume = isPaused || status === 'Failed';
    const canPause = isDownloading || status === 'Preparing';

    return (
        <div
            className={cn(
                'relative overflow-hidden rounded-xl border border-border/60',
                'bg-card/65 supports-[backdrop-filter]:bg-card/45 supports-[backdrop-filter]:backdrop-blur-xl',
                'transition-colors active:bg-card/80'
            )}
            onContextMenu={onContextMenu}
        >
            {/* Progress bar */}
            {showProgressBar && (
                <div
                    className="absolute left-0 bottom-0 h-1 overflow-hidden bg-primary/25"
                    style={{ width: `${progressPct}%` }}
                >
                    <div className="mr-banana-progress-indicator" />
                </div>
            )}

            <div className="p-3 space-y-2">
                {/* Header row: Code + Status */}
                <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                        <StatusIcon status={status} type="download" error={item.error} size="sm" />
                        {item.url ? (
                            <a
                                href={item.url}
                                target="_blank"
                                rel="noreferrer"
                                className="font-medium text-sm text-primary hover:underline truncate"
                                title={item.url}
                            >
                                {code}
                            </a>
                        ) : (
                            <span className="text-muted-foreground text-sm">-</span>
                        )}
                    </div>
                    <span className="text-xs text-muted-foreground px-2 py-0.5 bg-muted/50 rounded-full shrink-0">
                        {statusLabel}
                    </span>
                </div>

                {/* Info row */}
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span>刮削: {scrapeText}</span>
                    {speedText !== '-' && <span>速度: {speedText}</span>}
                    <span title={createdAt}>添加: {createdAt}</span>
                    {completedAt && completedAt !== '-' && <span title={completedAt}>完成: {completedAt}</span>}
                </div>

                {/* Action buttons */}
                <div className="flex items-center gap-2 pt-1">
                    {canResume && (
                        <button
                            className="flex items-center gap-1 px-2 py-1 text-xs rounded-md bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                            onClick={() => onResume(item.id)}
                        >
                            <Play className="h-3 w-3" />
                            恢复
                        </button>
                    )}
                    {canPause && (
                        <button
                            className="flex items-center gap-1 px-2 py-1 text-xs rounded-md bg-yellow-500/10 text-yellow-600 dark:text-yellow-500 hover:bg-yellow-500/20 transition-colors"
                            onClick={() => onPause(item.id)}
                        >
                            <Pause className="h-3 w-3" />
                            暂停
                        </button>
                    )}
                    <button
                        className="flex items-center gap-1 px-2 py-1 text-xs rounded-md bg-muted hover:bg-muted/80 text-muted-foreground transition-colors"
                        onClick={() => onViewLog(item.id)}
                    >
                        <FileText className="h-3 w-3" />
                        日志
                    </button>
                    <button
                        className="flex items-center gap-1 px-2 py-1 text-xs rounded-md bg-red-500/10 text-red-600 dark:text-red-500 hover:bg-red-500/20 transition-colors ml-auto"
                        onClick={() => onDelete(item.id)}
                    >
                        <X className="h-3 w-3" />
                        删除
                    </button>
                </div>
            </div>
        </div>
    );
}

/**
 * Hook to detect mobile viewport
 */
export function useIsMobile(breakpoint = 768) {
    const [isMobile, setIsMobile] = React.useState(() =>
        typeof window !== 'undefined' ? window.innerWidth < breakpoint : false
    );

    React.useEffect(() => {
        const handleResize = () => {
            setIsMobile(window.innerWidth < breakpoint);
        };

        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [breakpoint]);

    return isMobile;
}

export default DownloadHistoryCard;
