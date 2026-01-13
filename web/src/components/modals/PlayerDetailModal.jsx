import React from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { Button, Card, cn } from '../ui';
import { proxyImageUrl } from '../../utils/appHelpers';

/**
 * Player detail modal component
 * Shows detailed information about a library item and allows playback
 */
export function PlayerDetailModal({
    open,
    item,
    playing,
    onClose,
    onPlay,
    tr,
}) {
    if (!open) return null;

    const it = item || {};
    const title = it?.title || it?.code || tr('player.title');
    const poster = proxyImageUrl(it?.poster_url || '');
    const fanart = proxyImageUrl(it?.fanart_url || '');
    const actors = Array.isArray(it?.actors) ? it.actors : [];
    const tags = Array.isArray(it?.tags) ? it.tags : [];
    const canPlay = Boolean(it?.video_rel);
    const videoSrc = canPlay ? `/api/library/video?rel=${encodeURIComponent(String(it.video_rel))}` : '';
    const previewUrls = Array.isArray(it?.preview_urls) ? it.preview_urls : [];

    return createPortal(
        <div
            className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-foreground/20 py-8"
            onMouseDown={onClose}
        >
            <div className="w-full max-w-5xl px-4" onMouseDown={(e) => e.stopPropagation()}>
                <Card className="max-h-[85vh] overflow-auto p-4">
                    <div className="space-y-4">
                        {/* Header with fanart background */}
                        <div className="relative overflow-hidden rounded-xl border bg-card">
                            {fanart ? (
                                <>
                                    <img src={fanart} alt="" className="absolute inset-0 h-full w-full object-cover opacity-25" loading="lazy" />
                                    <div className="absolute inset-0 bg-background/70" />
                                </>
                            ) : null}
                            <div className="relative p-4">
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex min-w-0 gap-4">
                                        <div className="w-24 shrink-0">
                                            <div className="aspect-[2/3] overflow-hidden rounded-md border bg-muted">
                                                {poster ? (
                                                    <img src={poster} alt={title} className="h-full w-full object-cover" loading="lazy" />
                                                ) : null}
                                            </div>
                                        </div>
                                        <div className="min-w-0">
                                            <div className="text-lg font-semibold truncate">{title}</div>
                                            <div className="mt-1 text-xs text-foreground tabular-nums">
                                                {it?.code ? `${tr('scrape.code')}${tr('common.colon')}${it.code}` : ''}
                                                {it?.release ? ` · ${tr('scrape.release')}${tr('common.colon')}${it.release}` : ''}
                                                {it?.studio ? ` · ${tr('scrape.studio')}${tr('common.colon')}${it.studio}` : ''}
                                                {actors.length > 0 ? ` · ${tr('scrape.actors')}${tr('common.colon')}${actors.join(' / ')}` : ''}
                                            </div>
                                            {tags.length > 0 ? (
                                                <div className="mt-2 flex flex-wrap gap-2">
                                                    {tags.slice(0, 16).map((t) => (
                                                        <span key={t} className="rounded-md bg-muted px-2 py-1 text-[11px] text-muted-foreground">{t}</span>
                                                    ))}
                                                </div>
                                            ) : null}
                                            <div className="mt-3 flex items-center gap-3">
                                                <Button
                                                    type="button"
                                                    disabled={!canPlay}
                                                    onClick={onPlay}
                                                >
                                                    {tr('player.play')}
                                                </Button>
                                            </div>
                                        </div>
                                    </div>
                                    <button
                                        type="button"
                                        aria-label={tr('common.close')}
                                        className={cn(
                                            'inline-flex h-9 w-9 items-center justify-center rounded-md',
                                            'hover:bg-accent hover:text-accent-foreground',
                                            'text-muted-foreground'
                                        )}
                                        onClick={onClose}
                                    >
                                        <X className="h-4 w-4" />
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* Video player */}
                        {playing && videoSrc ? (
                            <div className="overflow-hidden rounded-xl border bg-background">
                                <video src={videoSrc} controls autoPlay className="w-full" />
                            </div>
                        ) : null}

                        {/* Preview images */}
                        {previewUrls.length > 0 && (
                            <div className="rounded-md border bg-background p-3">
                                <div className="mb-2 text-xs font-medium text-muted-foreground">{tr('scrape.detail.previews')}</div>
                                <div className="grid grid-cols-3 gap-2">
                                    {previewUrls.slice(0, 12).map((u, i) => (
                                        <div key={`${u}-${i}`} className="aspect-[4/3] overflow-hidden rounded-md border bg-muted">
                                            <img src={proxyImageUrl(u)} alt={tr('scrape.detail.previewAlt', { n: i + 1 })} className="h-full w-full object-cover" loading="lazy" />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Plot */}
                        <div className="rounded-md border bg-background p-3">
                            <div className="mb-2 text-xs font-medium text-muted-foreground">{tr('scrape.detail.plot')}</div>
                            <div className="text-sm leading-6">
                                {typeof it?.plot === 'string' && it.plot.trim() ? it.plot : tr('common.none')}
                            </div>
                        </div>
                    </div>
                </Card>
            </div>
        </div>,
        document.body
    );
}

export default PlayerDetailModal;
