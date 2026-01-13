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
    const stem = name.replace(/\.[^/.]+$/, '');
    const m = stem.match(/[A-Za-z0-9]+-[A-Za-z0-9]+/);
    return (m && m[0]) ? m[0].toUpperCase() : '-';
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
