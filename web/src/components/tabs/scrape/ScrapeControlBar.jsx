/**
 * ScrapeControlBar - Control bar with start button and status display
 */
import React from 'react';
import { AlertCircle } from 'lucide-react';
import { Card, Button } from '../../ui';
import { useScrapeStore } from '../../../stores/scrapeStore';

export function ScrapeControlBar({ tr }) {
    const config = useScrapeStore((s) => s.config);
    const loading = useScrapeStore((s) => s.loading);
    const liveState = useScrapeStore((s) => s.liveState);
    const pendingCount = useScrapeStore((s) => s.pendingCount);
    const pendingChecking = useScrapeStore((s) => s.pendingChecking);
    const startScrape = useScrapeStore((s) => s.startScrape);
    const getLatestJob = useScrapeStore((s) => s.getLatestJob);

    const scrapeInputDirEmpty = !String(config.scrape_dir || '').trim();
    const scrapeOutputDirEmpty = !String(config.scrape_output_dir || '').trim();
    const latestJob = getLatestJob();
    const live = (liveState?.jobId === latestJob?.id) ? (liveState.state || {}) : {};

    const handleStartScrape = async () => {
        try {
            await startScrape();
        } catch (err) {
            // Error is already handled in store
        }
    };

    return (
        <Card className="p-6 space-y-4">
            <div className="flex items-center justify-between gap-4">
                <div className="flex min-w-0 items-center gap-3">
                    <Button
                        type="button"
                        disabled={loading || scrapeInputDirEmpty || scrapeOutputDirEmpty}
                        onClick={handleStartScrape}
                    >
                        {loading ? tr('common.processing') : tr('scrape.start')}
                        {(scrapeInputDirEmpty || scrapeOutputDirEmpty) && (
                            <AlertCircle className="ml-2 h-4 w-4 text-amber-500" />
                        )}
                    </Button>
                    <div className="min-w-0 text-xs text-muted-foreground truncate">
                        {(() => {
                            const mini = live?.mini;
                            if (mini && mini.key) return tr(mini.key, mini.vars);
                            if (typeof pendingCount === 'number' && pendingCount >= 0) {
                                return tr('mini.idleWithPending', { n: pendingCount });
                            }
                            if (pendingChecking) return tr('mini.idle');
                            return tr('mini.idle');
                        })()}
                    </div>
                </div>
                <div className="text-sm text-muted-foreground tabular-nums">
                    {(() => {
                        const job = latestJob;
                        const active = Boolean(job) && (job.status === 'Running' || job.status === 'Starting');
                        if (!active) return tr('common.notStarted');
                        const total = Number(job.total || 0);
                        const current0 = Math.max(0, Number(job.current || 0));
                        const current1 = total > 0 ? Math.min(total, current0 + 1) : 0;
                        return `${current1}/${total}`;
                    })()}
                </div>
            </div>
        </Card>
    );
}

export default ScrapeControlBar;
