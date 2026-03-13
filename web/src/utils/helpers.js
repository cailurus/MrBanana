/**
 * Shared utility functions
 */

/**
 * Stable JSON stringify that handles circular references and sorts keys
 * @param {any} value - Value to stringify
 * @returns {string} JSON string
 */
export function stableStringify(value) {
    const seen = new WeakSet();
    const walk = (v) => {
        if (!v || typeof v !== 'object') return v;
        if (seen.has(v)) return null;
        seen.add(v);
        if (Array.isArray(v)) return v.map(walk);
        const out = {};
        for (const k of Object.keys(v).sort()) out[k] = walk(v[k]);
        return out;
    };
    return JSON.stringify(walk(value));
}

/**
 * Get expected crawler count from scrape config
 * @param {object} scrapeConfig - Scrape configuration object
 * @returns {number} Expected crawler count
 */
export function getExpectedScrapeCrawlerCount(scrapeConfig) {
    const cfg = scrapeConfig && typeof scrapeConfig === 'object' ? scrapeConfig : {};
    const seen = new Set();
    for (const k of Object.keys(cfg)) {
        if (!String(k).startsWith('scrape_sources_')) continue;
        const v = cfg[k];
        if (!Array.isArray(v)) continue;
        for (const s of v) {
            const name = typeof s === 'string' ? s.trim() : '';
            if (name) seen.add(name);
        }
    }
    return Math.max(1, seen.size);
}

/**
 * Proxy image URL through backend
 * @param {string} url - Original image URL
 * @returns {string} Proxied URL
 */
export function proxyImageUrl(url) {
    const s = String(url || '').trim();
    if (!s) return '';
    if (s.startsWith('http://') || s.startsWith('https://')) {
        return `/api/image-proxy?url=${encodeURIComponent(s)}`;
    }
    return s;
}

/**
 * Extract directory path from a full file path
 * @param {string} filePath - Full file path
 * @returns {string} Directory portion
 */
export function getDirectoryPath(filePath) {
    const s = String(filePath || '').trim();
    if (!s) return '';
    const lastSlash = s.lastIndexOf('/');
    if (lastSlash <= 0) return s;
    return s.substring(0, lastSlash);
}
