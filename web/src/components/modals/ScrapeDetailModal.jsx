import React from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import axios from 'axios';
import { Card, cn } from '../ui';
import { proxyImageUrl } from '../../utils/appHelpers';

/**
 * Infer subtitle language from file path
 * @param {string} path - Subtitle file path
 * @returns {string} Language code or filename
 */
function inferSubtitleLang(path) {
    const s = String(path || '').trim();
    const name = (s.split('/').pop() || s).trim();
    // Common patterns:
    //   CODE.zh.srt / CODE.zh-Hans.ass / CODE.en.vtt
    //   CODE.[zh].srt
    let m = name.match(/\.(?<lang>[a-z]{2,3}(?:-[A-Za-z0-9]+)?)\.(?:srt|ass|ssa|vtt|sub)$/i);
    if (m && m.groups && m.groups.lang) return m.groups.lang;
    m = name.match(/\[(?<lang>[a-z]{2,3}(?:-[A-Za-z0-9]+)?)\]\.(?:srt|ass|ssa|vtt|sub)$/i);
    if (m && m.groups && m.groups.lang) return m.groups.lang;
    return name;
}

/**
 * Scrape detail modal component
 * Shows detailed information about a scraped item
 */
export function ScrapeDetailModal({
    open,
    item,
    onClose,
    tr,
}) {
    if (!open) return null;

    const it = item || {};
    const title = it?.title || it?.code || tr('scrape.detail');
    // Prefer local URL over proxy URL for faster loading
    const poster = it?.poster_local_url || proxyImageUrl(it?.poster_url || '');
    const fanart = it?.fanart_local_url || proxyImageUrl(it?.fanart_url || '');
    const actors = Array.isArray(it?.actors) ? it.actors : [];
    const tags = Array.isArray(it?.tags) ? it.tags : [];

    // Extract directory from path
    const getDirectoryPath = (filePath) => {
        const s = String(filePath || '').trim();
        if (!s) return '';
        const lastSlash = s.lastIndexOf('/');
        if (lastSlash <= 0) return s;
        return s.substring(0, lastSlash);
    };
    const fileDirectory = getDirectoryPath(it.path);
    const runtimeDisplay = it.runtime ? `${it.runtime} mins` : '';

    // Detail rows
    const rows = [
        { labelKey: 'scrape.fileDirectory', value: fileDirectory },
        { labelKey: 'scrape.code', value: it.code },
        { labelKey: 'scrape.field.release', value: it.release },
        { labelKey: 'scrape.field.runtime', value: runtimeDisplay },
        { labelKey: 'scrape.field.studio', value: it.studio },
    ];

    // Prefer local trailer over remote URL
    const trailerLocalUrl = typeof it.trailer_local_url === 'string' ? it.trailer_local_url.trim() : '';
    const trailerRemoteUrl = typeof it.trailer_url === 'string' ? it.trailer_url.trim() : '';
    const trailerUrl = trailerLocalUrl || trailerRemoteUrl;
    const trailerIsLocal = Boolean(trailerLocalUrl);

    // Parse subtitles
    const rawSubtitles = Array.isArray(it.subtitles) ? it.subtitles : [];
    const subtitlePaths = rawSubtitles
        .map((s) => {
            if (!s) return '';
            if (typeof s === 'string') return s;
            if (typeof s === 'object' && typeof s.path === 'string') return s.path;
            return '';
        })
        .map((s) => String(s || '').trim())
        .filter(Boolean);

    const subtitleEntries = (() => {
        const seen = new Set();
        const out = [];
        for (const p of subtitlePaths) {
            const lang = String(inferSubtitleLang(p) || '').trim();
            if (!lang || seen.has(lang)) continue;
            seen.add(lang);
            out.push({ lang, path: p });
        }
        return out;
    })();

    // Preview images - prefer local URLs, only use proxy for remote URLs
    const localPreviews = Array.isArray(it?.preview_local_urls) ? it.preview_local_urls : [];
    const remotePreviews = Array.isArray(it?.preview_urls) ? it.preview_urls : [];
    // Use local previews directly (they're already local API URLs), only proxy remote URLs
    const hasLocalPreviews = localPreviews.length > 0;
    const previewList = hasLocalPreviews ? localPreviews : remotePreviews;

    const handleOpenPath = async (path) => {
        try {
            await axios.post('/api/system/open-path', { path, reveal: true });
        } catch (err) {
            console.error('Failed to open path', err);
        }
    };

    return createPortal(
        <div
            className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-foreground/20 py-8"
            onMouseDown={onClose}
        >
            <div
                className="w-full max-w-5xl px-4"
                onMouseDown={(e) => e.stopPropagation()}
            >
                <Card className="max-h-[85vh] overflow-auto p-4">
                    {/* Header with fanart background */}
                    <div className="relative overflow-hidden rounded-xl border bg-card">
                        {fanart ? (
                            <>
                                <img
                                    src={fanart}
                                    alt=""
                                    className="absolute inset-0 h-full w-full object-cover opacity-25"
                                    loading="lazy"
                                />
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
                                        <div className="text-lg font-semibold truncate">
                                            {title}
                                        </div>
                                        <div className="mt-1 text-xs text-foreground tabular-nums">
                                            {it?.code ? `${tr('scrape.code')}${tr('common.colon')}${it.code}` : ''}
                                            {it?.release ? ` · ${tr('scrape.release')}${tr('common.colon')}${it.release}` : ''}
                                            {it?.studio ? ` · ${tr('scrape.studio')}${tr('common.colon')}${it.studio}` : ''}
                                            {actors.length > 0 ? ` · ${tr('scrape.actors')}${tr('common.colon')}${actors.join(' / ')}` : ''}
                                        </div>
                                        {tags.length > 0 ? (
                                            <div className="mt-2 flex flex-wrap gap-2">
                                                {tags.map((t) => (
                                                    <span
                                                        key={t}
                                                        className="rounded-md bg-muted px-2 py-1 text-[11px] text-muted-foreground"
                                                    >
                                                        {t}
                                                    </span>
                                                ))}
                                            </div>
                                        ) : null}
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

                    {/* Details section */}
                    <div className="mt-4 space-y-3">
                        {/* Structured details grid */}
                        <div className="rounded-md border bg-background p-3">
                            <div className="grid gap-2 text-xs">
                                {rows.map((r) => (
                                    <div key={r.labelKey} className="grid grid-cols-[5rem_1fr] gap-2">
                                        <div className="text-muted-foreground font-medium">{tr(r.labelKey)}</div>
                                        <div className="text-foreground break-all">{r.value ? String(r.value) : <span className="text-muted-foreground">{tr('common.none')}</span>}</div>
                                    </div>
                                ))}
                                {trailerUrl ? (
                                    <div className="grid grid-cols-[5rem_1fr] gap-2">
                                        <div className="text-muted-foreground font-medium">{tr('scrape.detail.trailer')}</div>
                                        {trailerIsLocal ? (
                                            <a
                                                className="text-foreground break-all underline underline-offset-4 hover:text-primary"
                                                href={trailerUrl}
                                                target="_blank"
                                                rel="noreferrer"
                                            >
                                                {tr('scrape.detail.trailerLocal')}
                                            </a>
                                        ) : (
                                            <a
                                                className="text-foreground break-all underline underline-offset-4 hover:text-primary"
                                                href={trailerUrl}
                                                target="_blank"
                                                rel="noreferrer"
                                            >
                                                {trailerUrl}
                                            </a>
                                        )}
                                    </div>
                                ) : null}
                                {subtitleEntries.length > 0 ? (
                                    <div className="grid grid-cols-[5rem_1fr] gap-2">
                                        <div className="text-muted-foreground font-medium">{tr('scrape.detail.subtitles')}</div>
                                        <div className="text-foreground">
                                            {subtitleEntries.map((e, idx) => (
                                                <span key={`${e.lang}-${idx}`}>
                                                    <button
                                                        type="button"
                                                        className="underline underline-offset-4 hover:text-primary"
                                                        onClick={() => handleOpenPath(e.path)}
                                                    >
                                                        {e.lang}
                                                    </button>
                                                    {idx < subtitleEntries.length - 1 ? ', ' : ''}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                ) : null}
                            </div>
                        </div>

                        {/* Plot */}
                        <div className="rounded-md border bg-background p-3">
                            <div className="mb-2 text-xs font-medium text-muted-foreground">{tr('scrape.detail.plot')}</div>
                            <div className="max-h-40 overflow-auto text-sm leading-6">
                                {typeof it?.plot === 'string' && it.plot.trim()
                                    ? it.plot
                                    : tr('common.none')}
                            </div>
                        </div>

                        {/* Preview images */}
                        {previewList.length > 0 && (
                            <div className="rounded-md border bg-background p-3">
                                <div className="mb-2 text-xs font-medium text-muted-foreground">{tr('scrape.detail.previews')}</div>
                                <div className="max-h-40 overflow-y-auto pr-1">
                                    <div className="grid grid-cols-3 gap-2">
                                        {previewList.map((u, i) => {
                                            // Local URLs don't need proxy, remote URLs do
                                            const src = hasLocalPreviews ? u : proxyImageUrl(u);
                                            return src ? (
                                                <div key={`${u}-${i}`} className="aspect-[4/3] overflow-hidden rounded-md border bg-muted">
                                                    <img src={src} alt={tr('scrape.detail.previewAlt', { n: i + 1 })} className="h-full w-full object-cover" loading="lazy" />
                                                </div>
                                            ) : null;
                                        })}
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </Card>
            </div>
        </div>,
        document.body
    );
}

export default ScrapeDetailModal;
