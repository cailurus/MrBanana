export function clamp(num, min, max) {
    return Math.min(Math.max(num, min), max);
}

export function extractCodeFromUrl(url) {
    if (!url) return '-';
    const clean = String(url).replace(/\/+$/, '');
    const parts = clean.split('/');
    return parts[parts.length - 1] || '-';
}

export function extractCodeFromPath(path) {
    const s = String(path || '').trim();
    if (!s) return '-';
    const name = s.split('/').pop() || s;
    let stem = name.replace(/\.[^/.]+$/, '');
    if (!stem) return '-';
    // Clean up common prefixes like "4k2.me@", "xxx@", etc.
    stem = stem.replace(/^[A-Za-z0-9._-]*@/, '');
    // Match JAV code pattern: 2-6 letters + hyphen + 2-5 digits (ignore suffix like -C, ch, etc.)
    let m = stem.match(/(?<![A-Za-z])([A-Za-z]{2,6})-(\d{2,5})(?=[^0-9]|$)/i);
    if (m) return `${m[1].toUpperCase()}-${m[2]}`;
    // Also support patterns without hyphen like "ABC123" -> "ABC-123"
    m = stem.match(/(?<![A-Za-z])([A-Za-z]{2,6})(\d{2,5})(?=[^0-9]|$)/i);
    if (m) return `${m[1].toUpperCase()}-${m[2]}`;
    return '-';
}

export function formatDateTime(value) {
    if (!value) return '-';
    // Support both ISO strings and unix timestamps (seconds/ms).
    let v = value;
    if (typeof v === 'string' && /^\d+(?:\.\d+)?$/.test(v)) v = Number(v);
    if (typeof v === 'number' && Number.isFinite(v)) {
        // Heuristic: scrape jobs use time.time() seconds; JS Date expects ms.
        v = v < 1e12 ? v * 1000 : v;
    }
    const date = new Date(v);
    if (Number.isNaN(date.getTime())) return '-';
    // Keep output compact to avoid UI overflow: yyyy/mm/dd hh:mm (no seconds)
    return date.toLocaleString(undefined, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    });
}
