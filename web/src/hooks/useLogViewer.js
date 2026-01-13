/**
 * Log viewer hook
 * Manages log viewing with polling and scrolling functionality
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';

/**
 * Log viewer types
 */
export const LOG_KINDS = {
    DOWNLOAD: 'download',
    SCRAPE: 'scrape',
    SCRAPE_ITEM: 'scrape-item',
};

/**
 * Initial log viewer state
 */
const INITIAL_STATE = {
    open: false,
    kind: LOG_KINDS.DOWNLOAD,
    id: null,
    file: null,
};

/**
 * Hook for managing log viewer state and polling
 * 
 * @returns {Object} Log viewer state and handlers
 */
export function useLogViewer() {
    // Viewer state
    const [viewer, setViewer] = useState(INITIAL_STATE);
    const [logText, setLogText] = useState('');
    const [logOffset, setLogOffset] = useState(0);
    const [logExists, setLogExists] = useState(true);

    // Refs
    const logOffsetRef = useRef(0);
    const logEndRef = useRef(null);
    const pollTimerRef = useRef(null);

    /**
     * Open log viewer for a specific task
     * @param {Object} params - Log viewer parameters
     * @param {string} params.kind - Type of log (download, scrape, scrape-item)
     * @param {string|number} params.id - Task ID
     * @param {string} [params.file] - Specific file for scrape-item logs
     */
    const open = useCallback(async ({ kind, id, file = null }) => {
        setViewer({ open: true, kind, id, file });
        setLogText('');
        setLogOffset(0);
        logOffsetRef.current = 0;
        setLogExists(true);

        try {
            if (kind === LOG_KINDS.SCRAPE_ITEM && file) {
                const res = await axios.get(`/api/scrape/logs/${id}/item`, {
                    params: { filename: file }
                });
                setLogExists(Boolean(res.data?.exists));
                setLogText(res.data?.text || '');
                logOffsetRef.current = 0;
                setLogOffset(0);
            } else {
                const safeKind = kind === LOG_KINDS.SCRAPE ? 'scrape' : 'download';
                const base = safeKind === 'scrape'
                    ? `/api/scrape/logs/${id}`
                    : `/api/logs/${id}`;
                const res = await axios.get(`${base}?offset=0`);
                setLogExists(Boolean(res.data?.exists));
                setLogText(res.data?.text || '');
                const next = res.data?.next_offset ?? 0;
                logOffsetRef.current = next;
                setLogOffset(next);
            }
        } catch (err) {
            setLogText(`[failed to load log] ${err.response?.data?.detail || err.message}\n`);
        }
    }, []);

    /**
     * Close log viewer
     */
    const close = useCallback(() => {
        setViewer(INITIAL_STATE);
    }, []);

    /**
     * Close viewer if it matches a specific task
     * Useful when a task is deleted
     */
    const closeIfMatches = useCallback((taskId) => {
        setViewer((v) => {
            if (v.open && String(v.id) === String(taskId)) {
                return { open: false, kind: LOG_KINDS.DOWNLOAD, id: null, file: null };
            }
            return v;
        });
    }, []);

    /**
     * Reset log state (for when download history is cleared)
     */
    const resetLogs = useCallback(() => {
        if (viewer.open && viewer.kind === LOG_KINDS.DOWNLOAD) {
            setLogText('');
            setLogOffset(0);
            logOffsetRef.current = 0;
            setLogExists(false);
        }
    }, [viewer.open, viewer.kind]);

    // Polling effect
    useEffect(() => {
        if (!viewer.open || !viewer.id) return;

        const tick = async () => {
            try {
                if (viewer.kind === LOG_KINDS.SCRAPE_ITEM && viewer.file) {
                    const res = await axios.get(`/api/scrape/logs/${viewer.id}/item`, {
                        params: { filename: viewer.file }
                    });
                    setLogExists(Boolean(res.data?.exists));
                    setLogText(res.data?.text || '');
                    logOffsetRef.current = 0;
                    setLogOffset(0);
                } else {
                    const currentOffset = logOffsetRef.current || 0;
                    const safeKind = viewer.kind === LOG_KINDS.SCRAPE ? 'scrape' : 'download';
                    const base = safeKind === 'scrape'
                        ? `/api/scrape/logs/${viewer.id}`
                        : `/api/logs/${viewer.id}`;
                    const res = await axios.get(`${base}?offset=${currentOffset}`);
                    setLogExists(Boolean(res.data?.exists));
                    const nextOffset = res.data?.next_offset ?? currentOffset;
                    const chunk = res.data?.text || '';
                    if (chunk) setLogText((prev) => prev + chunk);
                    logOffsetRef.current = nextOffset;
                    setLogOffset(nextOffset);
                }
            } catch {
                // ignore transient errors to keep UI smooth
            }
        };

        // Poll every 1s while modal is open
        pollTimerRef.current = window.setInterval(tick, 1000);
        return () => {
            if (pollTimerRef.current) {
                window.clearInterval(pollTimerRef.current);
                pollTimerRef.current = null;
            }
        };
    }, [viewer.open, viewer.kind, viewer.id, viewer.file]);

    // Auto-scroll to bottom effect
    useEffect(() => {
        if (!viewer.open) return;
        logEndRef.current?.scrollIntoView({ block: 'end' });
    }, [logText, viewer.open]);

    return {
        // State
        viewer,
        logText,
        logOffset,
        logExists,
        logEndRef,

        // Actions
        open,
        close,
        closeIfMatches,
        resetLogs,
    };
}

export default useLogViewer;
