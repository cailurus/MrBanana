/**
 * WebSocket connection hook for real-time task updates
 * Extracted from App.jsx to reduce component complexity
 */
import { useRef, useEffect, useCallback } from 'react';
import { useDownloadStore } from '../stores';

/**
 * Hook for managing WebSocket connection to backend
 * Handles automatic reconnection and task state updates
 * 
 * @param {Object} options - Configuration options
 * @param {function} options.onTaskUpdate - Callback when tasks are updated
 * @param {function} options.onHistoryRefreshNeeded - Callback when history should be refreshed
 * @returns {Object} - WebSocket state and controls
 */
export function useWebSocket({ onTaskUpdate, onHistoryRefreshNeeded }) {
    const wsRef = useRef(null);
    const lastTaskStatusRef = useRef(new Map());
    const reconnectTimeoutRef = useRef(null);
    const { setActiveTasks } = useDownloadStore();

    const getWebSocketUrl = useCallback(() => {
        // Development mode: connect directly to backend to avoid Vite ws proxy EPIPE issues
        if (import.meta.env.DEV) {
            return 'ws://127.0.0.1:8000/ws';
        }
        // Production: use same host as page
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}/ws`;
    }, []);

    const handleMessage = useCallback((event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'update') {
                const tasks = Array.isArray(data.tasks) ? data.tasks : [];

                // Check for task state transitions to terminal states
                // Only refresh history when a task newly enters Completed/Failed
                let shouldRefreshHistory = false;
                for (const task of tasks) {
                    const id = String(task.id);
                    const prevStatus = lastTaskStatusRef.current.get(id);
                    const nextStatus = task.status;

                    if (prevStatus && prevStatus !== nextStatus) {
                        if (nextStatus === 'Completed' || nextStatus === 'Failed') {
                            shouldRefreshHistory = true;
                        }
                    }
                    lastTaskStatusRef.current.set(id, nextStatus);
                }

                // Update stores
                setActiveTasks(tasks);

                // Notify parent if callback provided
                if (onTaskUpdate) {
                    onTaskUpdate(tasks);
                }

                // Refresh history if needed
                if (shouldRefreshHistory && onHistoryRefreshNeeded) {
                    onHistoryRefreshNeeded();
                }
            }
        } catch (err) {
            console.error('Failed to parse WebSocket message:', err);
        }
    }, [setActiveTasks, onTaskUpdate, onHistoryRefreshNeeded]);

    const connect = useCallback(() => {
        // Clean up any existing connection
        if (wsRef.current) {
            try {
                wsRef.current.onclose = null;
                wsRef.current.close();
            } catch {
                // ignore
            }
        }

        const wsUrl = getWebSocketUrl();
        wsRef.current = new WebSocket(wsUrl);

        wsRef.current.onmessage = handleMessage;

        wsRef.current.onclose = () => {
            // Auto-reconnect after 3 seconds
            reconnectTimeoutRef.current = setTimeout(connect, 3000);
        };

        wsRef.current.onerror = (err) => {
            console.error('WebSocket error:', err);
        };
    }, [getWebSocketUrl, handleMessage]);

    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }

        if (wsRef.current) {
            try {
                wsRef.current.onclose = null;
                wsRef.current.close();
            } catch {
                // ignore
            }
            wsRef.current = null;
        }
    }, []);

    // Connect on mount, disconnect on unmount
    useEffect(() => {
        connect();

        return () => {
            disconnect();
        };
    }, [connect, disconnect]);

    // Clear task status history when needed (e.g., after clearing download history)
    const clearTaskStatusHistory = useCallback(() => {
        lastTaskStatusRef.current.clear();
    }, []);

    return {
        isConnected: wsRef.current?.readyState === WebSocket.OPEN,
        connect,
        disconnect,
        clearTaskStatusHistory,
    };
}

export default useWebSocket;
