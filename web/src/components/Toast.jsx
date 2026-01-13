import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, CheckCircle2, AlertCircle, Info, AlertTriangle } from 'lucide-react';
import { cn } from './ui';

// Toast Context
const ToastContext = createContext(null);

// Toast types configuration
const TOAST_TYPES = {
    success: {
        icon: CheckCircle2,
        className: 'border-green-500/50 bg-green-500/10 text-green-600 dark:text-green-400',
        iconClassName: 'text-green-500',
    },
    error: {
        icon: AlertCircle,
        className: 'border-red-500/50 bg-red-500/10 text-red-600 dark:text-red-400',
        iconClassName: 'text-red-500',
    },
    warning: {
        icon: AlertTriangle,
        className: 'border-yellow-500/50 bg-yellow-500/10 text-yellow-600 dark:text-yellow-400',
        iconClassName: 'text-yellow-500',
    },
    info: {
        icon: Info,
        className: 'border-blue-500/50 bg-blue-500/10 text-blue-600 dark:text-blue-400',
        iconClassName: 'text-blue-500',
    },
};

// Default duration in ms
const DEFAULT_DURATION = 4000;

// Single Toast component
function ToastItem({ id, type = 'info', message, title, onClose, duration = DEFAULT_DURATION }) {
    const config = TOAST_TYPES[type] || TOAST_TYPES.info;
    const Icon = config.icon;
    const timerRef = useRef(null);
    const [isExiting, setIsExiting] = useState(false);

    const handleClose = useCallback(() => {
        setIsExiting(true);
        // Wait for exit animation
        setTimeout(() => {
            onClose(id);
        }, 200);
    }, [id, onClose]);

    useEffect(() => {
        if (duration > 0) {
            timerRef.current = setTimeout(handleClose, duration);
        }
        return () => {
            if (timerRef.current) {
                clearTimeout(timerRef.current);
            }
        };
    }, [duration, handleClose]);

    // Pause timer on hover
    const handleMouseEnter = () => {
        if (timerRef.current) {
            clearTimeout(timerRef.current);
            timerRef.current = null;
        }
    };

    const handleMouseLeave = () => {
        if (duration > 0 && !timerRef.current) {
            timerRef.current = setTimeout(handleClose, duration / 2);
        }
    };

    return (
        <div
            role="alert"
            aria-live="polite"
            className={cn(
                'pointer-events-auto relative flex w-full items-start gap-3 rounded-lg border p-4 shadow-lg',
                'transition-all duration-200 ease-out',
                isExiting ? 'translate-x-full opacity-0' : 'translate-x-0 opacity-100',
                'bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80',
                config.className
            )}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            <Icon className={cn('h-5 w-5 shrink-0 mt-0.5', config.iconClassName)} />
            <div className="flex-1 min-w-0">
                {title && (
                    <div className="font-medium text-sm mb-1">{title}</div>
                )}
                <div className="text-sm opacity-90 break-words">{message}</div>
            </div>
            <button
                type="button"
                onClick={handleClose}
                className={cn(
                    'shrink-0 rounded-md p-1 opacity-70 transition-opacity',
                    'hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring'
                )}
                aria-label="Close notification"
            >
                <X className="h-4 w-4" />
            </button>
        </div>
    );
}

// Toast Container
function ToastContainer({ toasts, removeToast }) {
    if (toasts.length === 0) return null;

    return createPortal(
        <div
            className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 w-full max-w-sm pointer-events-none"
            aria-label="Notifications"
        >
            {toasts.map((toast) => (
                <ToastItem
                    key={toast.id}
                    {...toast}
                    onClose={removeToast}
                />
            ))}
        </div>,
        document.body
    );
}

// Toast Provider
export function ToastProvider({ children }) {
    const [toasts, setToasts] = useState([]);
    const idCounter = useRef(0);

    const addToast = useCallback(({ type = 'info', message, title, duration = DEFAULT_DURATION }) => {
        const id = ++idCounter.current;
        setToasts((prev) => [...prev, { id, type, message, title, duration }]);
        return id;
    }, []);

    const removeToast = useCallback((id) => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
    }, []);

    const toast = useCallback((message, options = {}) => {
        if (typeof message === 'object') {
            return addToast(message);
        }
        return addToast({ message, ...options });
    }, [addToast]);

    // Convenience methods
    toast.success = (message, options = {}) => addToast({ type: 'success', message, ...options });
    toast.error = (message, options = {}) => addToast({ type: 'error', message, ...options });
    toast.warning = (message, options = {}) => addToast({ type: 'warning', message, ...options });
    toast.info = (message, options = {}) => addToast({ type: 'info', message, ...options });

    return (
        <ToastContext.Provider value={toast}>
            {children}
            <ToastContainer toasts={toasts} removeToast={removeToast} />
        </ToastContext.Provider>
    );
}

// Hook to use toast
export function useToast() {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
}

export default ToastProvider;
