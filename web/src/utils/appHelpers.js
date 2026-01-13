/**
 * App helper utilities
 * Contains utility functions used across the app
 */

/**
 * Get expected scrape crawler count from config
 * Counts unique crawler sources enabled in config
 * 
 * @param {Object} scrapeConfig - Scrape configuration object
 * @returns {number} Number of expected crawlers (minimum 1)
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
 * Stable JSON stringify that handles circular references
 * and sorts object keys for consistent output
 * 
 * @param {*} value - Value to stringify
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
 * Proxy image URL through backend to handle CORS
 * 
 * @param {string} url - Original image URL
 * @returns {string} Proxied URL or empty string
 */
export function proxyImageUrl(url) {
    const s = String(url || '').trim();
    if (!s) return '';
    // Remote URLs - proxy through backend
    if (s.startsWith('http://') || s.startsWith('https://')) {
        return `/api/image-proxy?url=${encodeURIComponent(s)}`;
    }
    // Local paths - no proxy needed
    return s;
}

/**
 * Default scrape configuration object
 * Contains all scrape settings with default values
 */
export const DEFAULT_SCRAPE_CONFIG = {
    // Trigger settings
    scrape_triggered_by: 'manual',
    scrape_watch_dirs: [],
    scrape_exclude_paths: [],
    scrape_file_pattern: '',

    // Naming settings
    scrape_naming_folder_pattern: '',
    scrape_naming_video_pattern: '',
    scrape_naming_poster_pattern: 'poster',
    scrape_naming_fanart_pattern: 'fanart',
    scrape_naming_thumb_pattern: '',
    scrape_naming_nfo_pattern: '',

    // Download settings
    scrape_download_poster: true,
    scrape_download_fanart: true,
    scrape_download_previews: false,
    scrape_download_trailer: false,
    scrape_preview_limit: 0,

    // NFO settings
    scrape_write_nfo: true,
    scrape_nfo_skip_fields: [],

    // Translation settings
    scrape_translate_enabled: false,
    scrape_translate_provider: '',
    scrape_translate_api_url: '',
    scrape_translate_api_key: '',
    scrape_translate_fields: [],
    scrape_translate_target_lang: 'zh-CN',
    scrape_translate_model: '',

    // Concurrency settings
    scrape_max_concurrent: 1,
    scrape_delay_between: 1000,

    // Network settings
    scrape_proxy_enabled: false,
    scrape_proxy_url: '',
    scrape_timeout: 30000,
    scrape_retry_count: 3,

    // Source settings (dynamic)
};

/**
 * Default download configuration
 */
export const DEFAULT_DOWNLOAD_CONFIG = {
    output_dir: '',
    proxy_enabled: false,
    proxy_url: '',
    max_concurrent: 3,
    auto_start: true,
};

/**
 * Default player configuration
 */
export const DEFAULT_PLAYER_CONFIG = {
    media_library_dirs: [],
    subtitle_enabled: true,
    subtitle_lang: 'zh-CN',
};
