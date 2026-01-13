function clamp(n, min, max) {
    const x = Number(n);
    if (Number.isNaN(x)) return min;
    return Math.min(max, Math.max(min, x));
}

export function computeScrapeVirtualFilePhase(state, opts) {
    const s = state || {};
    const o = opts || {};

    // IMPORTANT: expected crawlers must be stable (from config), otherwise
    // the first "try crawler" would immediately become 100% crawl progress.
    const expectedCrawlers = Math.max(1, Number(o.expectedCrawlers || s.expectedCrawlers || 1));
    const tried = Math.max(0, Number(s.crawlersTried || 0));
    const crawlRatio = clamp(tried / expectedCrawlers, 0, 1);

    const wantTranslate = Boolean(o.translateEnabled);
    const wantPoster = Boolean(o.downloadPoster);
    const wantFanart = Boolean(o.downloadFanart);
    const wantPreviews = Boolean(o.downloadPreviews) && Number(o.previewLimit || 0) > 0;
    const wantTrailer = Boolean(o.downloadTrailer);
    const wantNfo = Boolean(o.writeNfo);

    const posterDone = wantPoster ? Boolean(s.posterDone) : true;
    const fanartDone = wantFanart ? Boolean(s.fanartDone) : true;
    const previewsDone = wantPreviews ? Boolean(s.previewsDone) : true;
    // Trailer download is performed inside NFO writer without log lines; treat it as done once NFO is done.
    const trailerDone = wantTrailer ? Boolean(s.nfoDone) : true;
    const translateTitleDone = wantTranslate ? Boolean(s.translateTitleDone) : true;
    const translatePlotDone = wantTranslate ? Boolean(s.translatePlotDone) : true;
    const nfoDone = wantNfo ? Boolean(s.nfoDone) : true;

    const startDone = Boolean(
        (typeof s.currentFileName === 'string' && s.currentFileName.trim()) ||
        (typeof s.file === 'string' && s.file.trim()) ||
        (typeof s.file_name === 'string' && s.file_name.trim()) ||
        Number(s.fileIndex || 0) > 0
    );

    const hitDone = Boolean(
        (typeof s.hitCrawler === 'string' && s.hitCrawler.trim()) ||
        (typeof s.hitUrl === 'string' && s.hitUrl.trim()) ||
        (typeof s.hitTitle === 'string' && s.hitTitle.trim()) ||
        (typeof s.url === 'string' && s.url.trim()) ||
        (typeof s.title === 'string' && s.title.trim())
    );

    // Metadata completeness (title/plot/actors/tags/cover/etc.).
    const titleDone = Boolean((typeof s.title === 'string' && s.title.trim()) || (typeof s.hitTitle === 'string' && s.hitTitle.trim()));
    const urlDone = Boolean((typeof s.url === 'string' && s.url.trim()) || (typeof s.hitUrl === 'string' && s.hitUrl.trim()));
    const releaseDone = Boolean(s.release);
    const runtimeDone = Boolean(s.runtime);
    const studioDone = Boolean(s.studio || s.series);
    const actorsDone = Array.isArray(s.actors) ? s.actors.length > 0 : Boolean(s.actors);
    const tagsDone = Array.isArray(s.tags) ? s.tags.length > 0 : Boolean(s.tags);
    const plotLen = Number(s.plot_len || 0);
    const plotPreview = typeof s.plot_preview === 'string' ? s.plot_preview.trim() : '';
    const plotDone = plotLen >= 30 || plotPreview.length >= 30;
    const posterUrlDone = typeof s.poster_url === 'string' ? Boolean(s.poster_url.trim()) : Boolean(s.poster_url);
    const fanartUrlDone = typeof s.fanart_url === 'string' ? Boolean(s.fanart_url.trim()) : Boolean(s.fanart_url);

    const metaParts = [
        titleDone,
        urlDone,
        plotDone,
        actorsDone,
        tagsDone,
        releaseDone,
        runtimeDone,
        studioDone,
        posterUrlDone,
        fanartUrlDone,
    ];
    const metaRatio = metaParts.length ? metaParts.reduce((acc, v) => acc + (v ? 1 : 0), 0) / metaParts.length : 1;

    const translateRatio = wantTranslate ? (Number(translateTitleDone) + Number(translatePlotDone)) / 2 : 1;

    const artworkParts = [];
    if (wantPoster) artworkParts.push(posterDone);
    if (wantFanart) artworkParts.push(fanartDone);
    if (wantPreviews) artworkParts.push(previewsDone);
    if (wantTrailer) artworkParts.push(trailerDone);
    const artworkRatio = artworkParts.length ? artworkParts.reduce((acc, v) => acc + (v ? 1 : 0), 0) / artworkParts.length : 1;

    // Step weights (normalized to [0,1] by dividing by totalWeight).
    const wStart = 0.04;
    const wCrawl = 0.26;
    const wHit = 0.10;
    const wMeta = 0.26;
    const wTranslate = wantTranslate ? 0.12 : 0.0;
    const wArtwork = 0.16;
    const wNfo = wantNfo ? 0.06 : 0.0;
    const totalWeight = wStart + wCrawl + wHit + wMeta + wTranslate + wArtwork + wNfo;

    const raw =
        wStart * (startDone ? 1 : 0) +
        wCrawl * crawlRatio +
        wHit * (hitDone ? 1 : 0) +
        wMeta * metaRatio +
        wTranslate * translateRatio +
        wArtwork * artworkRatio +
        wNfo * (nfoDone ? 1 : 0);

    return clamp(totalWeight > 0 ? raw / totalWeight : 0, 0, 1);
}

export function parseScrapeLogChunk(chunk, prevState) {
    const next = { ...(prevState || {}) };
    const text = String(chunk || '');
    if (!text) return next;
    const lines = text.split(/\r?\n/);

    const setMini = (key, vars) => {
        next.mini = { key, vars: vars && typeof vars === 'object' ? vars : undefined };
        next.lastUpdateAt = Date.now();
    };

    const stripPyReprQuotes = (s) => {
        const v = String(s || '').trim();
        if (!v) return '';
        if ((v.startsWith("'") && v.endsWith("'")) || (v.startsWith('"') && v.endsWith('"'))) {
            return v.slice(1, -1);
        }
        return v;
    };

    for (const rawLine of lines) {
        let lineRaw = String(rawLine || '');
        // Backend job logs are stored as: "YYYY-MM-DD HH:MM:SS <msg>".
        // Strip the timestamp so parsers can rely on stable prefixes.
        if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} /.test(lineRaw)) {
            lineRaw = lineRaw.slice(20);
        }
        const line = lineRaw.trim();
        if (!line) continue;

        // Structured live payload from backend runner.
        if (line.startsWith('live.json:')) {
            const jsonText = String(line.slice('live.json:'.length) || '').trim();
            if (jsonText) {
                try {
                    const obj = JSON.parse(jsonText);
                    if (obj && typeof obj === 'object') {
                        next.livePhase = typeof obj.phase === 'string' ? obj.phase : next.livePhase;
                        next.code = typeof obj.code === 'string' ? obj.code : next.code;
                        next.title = typeof obj.title === 'string' ? obj.title : next.title;
                        next.url = typeof obj.url === 'string' ? obj.url : next.url;
                        next.release = obj.release ?? next.release;
                        next.runtime = obj.runtime ?? next.runtime;
                        next.studio = obj.studio ?? next.studio;
                        next.series = obj.series ?? next.series;
                        next.actors = Array.isArray(obj.actors) ? obj.actors : next.actors;
                        next.tags = Array.isArray(obj.tags) ? obj.tags : next.tags;
                        next.poster_url = typeof obj.poster_url === 'string' ? obj.poster_url : next.poster_url;
                        next.fanart_url = typeof obj.fanart_url === 'string' ? obj.fanart_url : next.fanart_url;
                        next.plot_len = typeof obj.plot_len === 'number' ? obj.plot_len : next.plot_len;
                        next.plot_source = typeof obj.plot_source === 'string' ? obj.plot_source : next.plot_source;
                        next.plot_preview = typeof obj.plot_preview === 'string' ? obj.plot_preview : next.plot_preview;
                        next.hit_sources = Array.isArray(obj.hit_sources) ? obj.hit_sources : next.hit_sources;
                        next.subtitles = Array.isArray(obj.subtitles) ? obj.subtitles : next.subtitles;
                        next.lastUpdateAt = Date.now();
                    }
                } catch {
                    // ignore malformed JSON
                }
            }
            continue;
        }

        // File boundary marker
        const m = line.match(/===\s*\[(\d+)\/(\d+)\]\s+(.+?)\s*===/);
        if (m) {
            next.fileIndex = Number(m[1] || 0);
            next.fileTotal = Number(m[2] || 0);
            next.currentFileName = String(m[3] || '').trim();
            next.crawlersTried = 0;
            next.posterDone = false;
            next.fanartDone = false;
            next.previewsDone = false;
            next.trailerDone = false;
            next.translateTitleDone = false;
            next.translatePlotDone = false;
            next.nfoDone = false;
            next.hitCrawler = '';
            next.hitTitle = '';
            next.hitUrl = '';
            next.code = '';
            next.title = '';
            next.url = '';
            next.release = '';
            next.runtime = '';
            next.studio = '';
            next.series = '';
            next.actors = [];
            next.tags = [];
            next.poster_url = '';
            next.fanart_url = '';
            next.plot_len = 0;
            next.plot_source = '';
            next.plot_preview = '';
            next.hit_sources = [];
            next.subtitles = [];
            next._lastTryCrawler = '';
            next._lastArtworkKind = '';
            next._lastArtworkSource = '';
            setMini('mini.startFile', { file: next.currentFileName || '' });
            continue;
        }

        if (line.includes('try crawler:')) {
            const name = String(line.split('try crawler:')[1] || '').trim();
            next.crawlersTried = Number(next.crawlersTried || 0) + 1;
            next.expectedCrawlers = Math.max(Number(next.expectedCrawlers || 1), Number(next.crawlersTried || 0));
            if (name) {
                next._lastTryCrawler = name;
                setMini('mini.tryCrawler', { name });
            }
            continue;
        }

        if (line.startsWith('hit crawler:')) {
            const mm = line.match(/^hit crawler:\s+(\S+)\s+title=(.+?)\s+url=(.+)$/);
            if (mm) {
                const name = String(mm[1] || '').trim();
                const title = stripPyReprQuotes(mm[2]);
                const url = stripPyReprQuotes(mm[3]);
                next.hitCrawler = name;
                next.hitTitle = title;
                next.hitUrl = url;
                const who = String(next._lastTryCrawler || name || '').trim();
                if (who) setMini('mini.tryCrawlerOk', { name: who });
            }
            continue;
        }

        if (line.startsWith('miss crawler:')) {
            const name = String(line.split('miss crawler:')[1] || '').trim();
            const who = String(next._lastTryCrawler || name || '').trim();
            if (who) setMini('mini.tryCrawlerFail', { name: who });
            continue;
        }

        if (line.startsWith('error crawler:')) {
            const mm = line.match(/^error crawler:\s+(\S+)\s+error=/);
            const name = mm ? String(mm[1] || '').trim() : '';
            const who = String(next._lastTryCrawler || name || '').trim();
            if (who) setMini('mini.tryCrawlerFail', { name: who });
            continue;
        }

        if (line.startsWith('translate: title start')) {
            setMini('mini.translateTitleStart');
            continue;
        }

        if (line.includes('translate: title done')) {
            next.translateTitleDone = true;
            setMini('mini.translateTitleDone');
            continue;
        }
        if (line.startsWith('translate: plot start')) {
            setMini('mini.translatePlotStart');
            continue;
        }
        if (line.includes('translate: plot done')) {
            next.translatePlotDone = true;
            setMini('mini.translatePlotDone');
            continue;
        }

        if (line.includes('artwork downloaded:') || line.includes('artwork download failed:')) {
            const ok = line.includes('artwork downloaded:');
            const kind = line.includes('-poster') ? 'poster' : (line.includes('-fanart') ? 'fanart' : (line.includes('-preview-') ? 'previews' : ''));

            if (kind === 'poster') next.posterDone = true;
            if (kind === 'fanart') next.fanartDone = true;
            if (kind === 'previews') next.previewsDone = true;

            const src = String(next._lastArtworkSource || '').trim();
            if (kind === 'poster') setMini(ok ? 'mini.artworkPosterOk' : 'mini.artworkPosterFail', { name: src });
            if (kind === 'fanart') setMini(ok ? 'mini.artworkFanartOk' : 'mini.artworkFanartFail', { name: src });
            if (kind === 'previews') setMini(ok ? 'mini.artworkPreviewsOk' : 'mini.artworkPreviewsFail', { name: src });
            continue;
        }
        if (line.includes('artwork try poster:')) {
            const url = String(line.split('artwork try poster:')[1] || '').trim();
            next._lastArtworkKind = 'poster';
            next._lastArtworkSource = url.includes('javtrailers.com') ? 'javtrailers' : (url.includes('pics.dmm.co.jp') ? 'dmm' : '');
            setMini('mini.artworkPoster', { name: next._lastArtworkSource || '' });
            continue;
        }
        if (line.includes('artwork try fanart:')) {
            const url = String(line.split('artwork try fanart:')[1] || '').trim();
            next._lastArtworkKind = 'fanart';
            next._lastArtworkSource = url.includes('javtrailers.com') ? 'javtrailers' : (url.includes('pics.dmm.co.jp') ? 'dmm' : '');
            setMini('mini.artworkFanart', { name: next._lastArtworkSource || '' });
            continue;
        }
        if (line.includes('artwork try preview[')) {
            const url = String(line.split(']')[1] || '').trim();
            next._lastArtworkKind = 'previews';
            next._lastArtworkSource = url.includes('javtrailers.com') ? 'javtrailers' : (url.includes('pics.dmm.co.jp') ? 'dmm' : '');
            setMini('mini.artworkPreviews', { name: next._lastArtworkSource || '' });
            continue;
        }

        if (line.startsWith('write nfo:') || line.includes('write nfo:')) {
            next.nfoDone = true;
            // Lock in expected crawlers for this run once we reach the end of an item.
            next.expectedCrawlers = Math.max(Number(next.expectedCrawlers || 1), Number(next.crawlersTried || 0) || 1);
            setMini('mini.writeNfo');
            continue;
        }
        if (line.includes('nfo disabled')) {
            next.nfoDone = true;
            next.expectedCrawlers = Math.max(Number(next.expectedCrawlers || 1), Number(next.crawlersTried || 0) || 1);
            setMini('mini.doneFile');
            continue;
        }
    }
    return next;
}
