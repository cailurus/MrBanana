/**
 * ScrapeLivePreview - Live preview card showing current scrape progress
 */
import React from 'react';
import { Card } from '../../ui';
import { useScrapeStore } from '../../../stores/scrapeStore';
import { clamp, extractCodeFromPath } from '../../../utils/format';
import { getExpectedScrapeCrawlerCount, proxyImageUrl } from '../../../utils/appHelpers';
import { computeScrapeVirtualFilePhase } from '../../../scrapeProgress';

/**
 * Extract directory path from full file path
 */
function getDirectoryPath(filePath) {
    const s = String(filePath || '').trim();
    if (!s) return '';
    const lastSlash = s.lastIndexOf('/');
    if (lastSlash <= 0) return s;
    return s.substring(0, lastSlash);
}

/**
 * Pick the best matching item from scrape items for preview
 */
function pickScrapeDetailItem(job, items) {
    const list = Array.isArray(items) ? items : [];
    if (!list.length) return null;
    const currentFile = String(job?.current_file || '').trim();
    if (currentFile) {
        const currentName = currentFile.split('/').pop() || currentFile;
        for (let i = list.length - 1; i >= 0; i -= 1) {
            const p = String(list[i]?.path || '');
            if (p && (p.endsWith(currentFile) || p.endsWith(currentName))) return list[i];
        }
    }
    return list[list.length - 1];
}

export function ScrapeLivePreview({ tr }) {
    const config = useScrapeStore((s) => s.config);
    const items = useScrapeStore((s) => s.items);
    const liveState = useScrapeStore((s) => s.liveState);
    const getLatestJob = useScrapeStore((s) => s.getLatestJob);

    const job = getLatestJob();
    const active = Boolean(job) && (job.status === 'Running' || job.status === 'Starting');

    // Only show preview when:
    // 1. There's an active job (Running/Starting), OR
    // 2. A job just completed in THIS session (liveState.jobId matches the completed job)
    // This ensures preview is hidden on page refresh but stays after completion
    const hasLiveStateForJob = Boolean(liveState?.jobId) && liveState.jobId === job?.id;
    const justCompleted = Boolean(job) && job.status === 'Completed' && hasLiveStateForJob;
    const hasJobToShow = active || justCompleted;

    // When job is completed, show the last item from history
    const it0 = pickScrapeDetailItem(job, items);
    const live = (liveState?.jobId === job?.id) ? (liveState.state || {}) : {};
    const currentFile = String(job?.current_file || '').trim() || String(live.currentFileName || '').trim();
    const currentName = currentFile ? (currentFile.split('/').pop() || currentFile) : '';
    const itMatchesCurrent = Boolean(it0 && currentFile && String(it0?.path || '').trim() && (
        String(it0.path).endsWith(currentFile) || String(it0.path).endsWith(currentName)
    ));

    // When active: avoid showing a stale last-completed item as the current preview
    // When completed: always show the last item from items list
    const it = justCompleted ? it0 : (itMatchesCurrent ? it0 : null);

    // Don't show anything if there's no job to display
    if (!hasJobToShow) return null;

    const currentCode = extractCodeFromPath(currentFile);
    const liveCode = (typeof live?.code === 'string' && live.code.trim()) ? live.code.trim() : '';
    const code = it?.code ? it.code : (liveCode || currentCode);

    const liveTitle = (typeof live?.title === 'string' && live.title.trim()) ? live.title.trim() : '';
    const title =
        (it && (it.title || it.code))
            ? (it.title || it.code)
            : (liveTitle || (live.hitTitle ? live.hitTitle : (code !== '-' ? code : tr('scrape.inProgress'))));

    const livePoster = (typeof live?.poster_url === 'string' && live.poster_url.trim()) ? live.poster_url.trim() : '';
    const liveFanart = (typeof live?.fanart_url === 'string' && live.fanart_url.trim()) ? live.fanart_url.trim() : '';
    // Prefer local URL over proxy URL for faster loading
    const posterImg = it?.poster_local_url || proxyImageUrl((it?.poster_url || livePoster) || '');
    const fanartImg = it?.fanart_local_url || proxyImageUrl((it?.fanart_url || liveFanart) || '');

    const actors = Array.isArray(it?.actors) ? it.actors : (Array.isArray(live?.actors) ? live.actors : []);
    const tags = Array.isArray(it?.tags) ? it.tags : (Array.isArray(live?.tags) ? live.tags : []);
    const plot = typeof it?.plot === 'string'
        ? it.plot.trim()
        : (typeof live?.plot_preview === 'string' ? live.plot_preview.trim() : '');

    const release = it?.release ? it.release : (live?.release || '');
    const studio = it?.studio ? it.studio : (live?.studio || '');
    const runtime = it?.runtime ? it.runtime : (live?.runtime || '');
    const subtitles = Array.isArray(live?.subtitles) ? live.subtitles : [];

    // File directory: when completed, show output path directory; otherwise show input path directory
    const itemPath = it?.path || '';
    const inputDir = String(config.scrape_dir || '').trim();
    const outputDir = String(config.scrape_output_dir || '').trim();
    // If completed and item has a path, derive directory from item path; otherwise show input dir
    const fileDirectory = justCompleted && itemPath
        ? getDirectoryPath(itemPath)
        : (active ? inputDir : '');

    const filePhase = computeScrapeVirtualFilePhase(live, {
        expectedCrawlers: getExpectedScrapeCrawlerCount(config),
        translateEnabled: Boolean(config.scrape_translate_enabled),
        downloadPoster: Boolean(config.scrape_download_poster),
        downloadFanart: Boolean(config.scrape_download_fanart),
        downloadPreviews: Boolean(config.scrape_download_previews),
        downloadTrailer: Boolean(config.scrape_download_trailer),
        downloadSubtitle: Boolean(config.scrape_download_subtitle),
        previewLimit: Number(config.scrape_preview_limit || 0),
        writeNfo: Boolean(config.scrape_write_nfo),
    });

    const total = Number(job?.total || live.fileTotal || 0);
    const idx = Number(job?.current || live.fileIndex || 0);
    const overall = total > 0
        ? clamp((Math.max(0, idx) + filePhase) / total * 100, 0, 100)
        : 0;

    // Format runtime with mins suffix
    const runtimeDisplay = runtime ? `${runtime} mins` : '-';

    return (
        <Card className="p-6">
            <div className="mb-3 text-sm font-medium">{tr('scrape.currentPreview')}</div>
            <div className="space-y-4">
                <div className="grid grid-cols-[9rem_1fr] gap-4">
                    {/* Left side: Poster and Fanart images with placeholders */}
                    <div className="w-36 flex flex-col gap-2">
                        {/* Poster placeholder - always show container */}
                        <div className="aspect-[2/3] overflow-hidden rounded-md border bg-muted">
                            {posterImg ? (
                                <img src={posterImg} alt={title} className="h-full w-full object-cover" loading="lazy" />
                            ) : (
                                <div className="h-full w-full flex items-center justify-center text-muted-foreground/30 text-xs">
                                    {tr('scrape.field.poster')}
                                </div>
                            )}
                        </div>
                        {/* Fanart placeholder - always show container */}
                        <div className="aspect-[16/9] overflow-hidden rounded-md border bg-muted">
                            {fanartImg ? (
                                <img src={fanartImg} alt="" className="h-full w-full object-cover" loading="lazy" />
                            ) : (
                                <div className="h-full w-full flex items-center justify-center text-muted-foreground/30 text-xs">
                                    {tr('scrape.field.fanart')}
                                </div>
                            )}
                        </div>
                    </div>
                    {/* Right side: Metadata panel - height matches left images */}
                    <div className="min-w-0 flex">
                        <div className="relative overflow-hidden rounded-lg border bg-card/50 p-3 flex-1 flex flex-col">
                            <div className="relative flex-1 flex flex-col justify-between">
                                {/* Title */}
                                <div className="text-base font-medium h-6 leading-6 truncate" title={title}>
                                    {title || <span className="text-muted-foreground/50">{tr('scrape.field.title')}</span>}
                                </div>
                                {/* Code / Release / Studio / Runtime */}
                                <div className="text-xs text-muted-foreground tabular-nums h-5 leading-5 truncate">
                                    {code !== '-' ? `${tr('scrape.code')}：${code}` : `${tr('scrape.code')}：-`}
                                    {` · ${tr('scrape.release')}：${release || '-'}`}
                                    {` · ${tr('scrape.studio')}：${studio || '-'}`}
                                    {` · ${tr('scrape.runtime')}：${runtimeDisplay}`}
                                </div>
                                {/* File directory */}
                                <div className="text-xs text-muted-foreground h-5 leading-5 truncate" title={fileDirectory}>
                                    {tr('scrape.fileDirectory')}：{fileDirectory || '-'}
                                </div>
                                {/* Actors */}
                                <div className="text-xs text-muted-foreground h-5 leading-5 truncate" title={actors.length > 0 ? actors.join(' / ') : ''}>
                                    {tr('scrape.actors')}：{actors.length > 0 ? actors.join(' / ') : '-'}
                                </div>
                                {/* Subtitles */}
                                <div className="text-xs text-muted-foreground h-5 leading-5 truncate" title={subtitles.length > 0 ? subtitles.join(' / ') : ''}>
                                    {tr('scrape.subtitle')}：{subtitles.length > 0 ? subtitles.join(' / ') : '-'}
                                </div>
                                {/* Plot - fixed height with ellipsis for overflow */}
                                <div className="text-xs text-muted-foreground leading-5 h-[3.25rem] overflow-hidden" title={plot}>
                                    <span className="line-clamp-2">{tr('scrape.plot')}：{plot || '-'}</span>
                                </div>
                                {/* Tags */}
                                <div className="h-10 overflow-hidden">
                                    {tags.length > 0 ? (
                                        <div className="flex flex-wrap gap-1.5 pt-1">
                                            {tags.slice(0, 10).map((t) => (
                                                <span key={t} className="rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                                                    {t}
                                                </span>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="pt-2 text-xs text-muted-foreground">{tr('scrape.tags')}：-</div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </Card>
    );
}

export default ScrapeLivePreview;
