import React from 'react';
import { Activity, AlertCircle, CheckCircle2, Clock, Pause, Loader2, GitMerge } from 'lucide-react';
import { cn } from './ui';

/**
 * Status configuration mapping for download tasks
 */
const DOWNLOAD_STATUS_CONFIG = {
    Preparing: {
        icon: Loader2,
        iconClass: 'animate-spin text-blue-500',
        bgClass: 'bg-blue-50 dark:bg-blue-900/20',
        textClass: 'text-blue-700 dark:text-blue-300',
        borderClass: 'border-blue-200 dark:border-blue-800',
    },
    Queued: {
        icon: Clock,
        iconClass: 'text-gray-500',
        bgClass: 'bg-gray-50 dark:bg-gray-800',
        textClass: 'text-gray-700 dark:text-gray-300',
        borderClass: 'border-gray-200 dark:border-gray-700',
    },
    Downloading: {
        icon: Activity,
        iconClass: 'animate-pulse text-blue-500',
        bgClass: 'bg-blue-50 dark:bg-blue-900/20',
        textClass: 'text-blue-700 dark:text-blue-300',
        borderClass: 'border-blue-200 dark:border-blue-800',
    },
    Merging: {
        icon: GitMerge,
        iconClass: 'text-indigo-500',
        bgClass: 'bg-indigo-50 dark:bg-indigo-900/20',
        textClass: 'text-indigo-700 dark:text-indigo-300',
        borderClass: 'border-indigo-200 dark:border-indigo-800',
    },
    Paused: {
        icon: Pause,
        iconClass: 'text-yellow-600 dark:text-yellow-500',
        bgClass: 'bg-yellow-50 dark:bg-yellow-900/20',
        textClass: 'text-yellow-700 dark:text-yellow-300',
        borderClass: 'border-yellow-200 dark:border-yellow-800',
    },
    Completed: {
        icon: CheckCircle2,
        iconClass: 'text-green-500',
        bgClass: 'bg-green-50 dark:bg-green-900/20',
        textClass: 'text-green-700 dark:text-green-300',
        borderClass: 'border-green-200 dark:border-green-800',
    },
    Failed: {
        icon: AlertCircle,
        iconClass: 'text-red-500',
        bgClass: 'bg-red-50 dark:bg-red-900/20',
        textClass: 'text-red-700 dark:text-red-300',
        borderClass: 'border-red-200 dark:border-red-800',
    },
};

/**
 * Status configuration mapping for scrape tasks
 */
const SCRAPE_STATUS_CONFIG = {
    Pending: {
        icon: Clock,
        iconClass: 'text-gray-500',
        bgClass: 'bg-gray-50 dark:bg-gray-800',
        textClass: 'text-gray-700 dark:text-gray-300',
        borderClass: 'border-gray-200 dark:border-gray-700',
    },
    Starting: {
        icon: Loader2,
        iconClass: 'animate-spin text-blue-500',
        bgClass: 'bg-blue-50 dark:bg-blue-900/20',
        textClass: 'text-blue-700 dark:text-blue-300',
        borderClass: 'border-blue-200 dark:border-blue-800',
    },
    Running: {
        icon: Activity,
        iconClass: 'animate-pulse text-blue-500',
        bgClass: 'bg-blue-50 dark:bg-blue-900/20',
        textClass: 'text-blue-700 dark:text-blue-300',
        borderClass: 'border-blue-200 dark:border-blue-800',
    },
    Completed: DOWNLOAD_STATUS_CONFIG.Completed,
    Failed: DOWNLOAD_STATUS_CONFIG.Failed,
};

/**
 * Default configuration for unknown status
 */
const DEFAULT_STATUS_CONFIG = {
    icon: Clock,
    iconClass: 'text-gray-400',
    bgClass: 'bg-gray-50 dark:bg-gray-800',
    textClass: 'text-gray-600 dark:text-gray-400',
    borderClass: 'border-gray-200 dark:border-gray-700',
};

/**
 * StatusBadge component for displaying task status with icon and label
 * 
 * @param {Object} props
 * @param {string} props.status - The status string (e.g., 'Downloading', 'Completed')
 * @param {string} [props.label] - Custom label to display (defaults to status)
 * @param {'download' | 'scrape'} [props.type='download'] - Type of status
 * @param {'sm' | 'md' | 'lg'} [props.size='md'] - Size variant
 * @param {boolean} [props.showBorder=false] - Whether to show border
 * @param {string} [props.error] - Error message for Failed status tooltip
 * @param {string} [props.className] - Additional CSS classes
 */
export function StatusBadge({
    status,
    label,
    type = 'download',
    size = 'md',
    showBorder = false,
    error,
    className,
}) {
    const configMap = type === 'scrape' ? SCRAPE_STATUS_CONFIG : DOWNLOAD_STATUS_CONFIG;
    const config = configMap[status] || DEFAULT_STATUS_CONFIG;
    const Icon = config.icon;

    const displayLabel = label || status || 'Unknown';

    const sizeClasses = {
        sm: {
            container: 'px-1.5 py-0.5 text-xs gap-1',
            icon: 'h-3 w-3',
        },
        md: {
            container: 'px-2 py-1 text-sm gap-1.5',
            icon: 'h-4 w-4',
        },
        lg: {
            container: 'px-3 py-1.5 text-base gap-2',
            icon: 'h-5 w-5',
        },
    };

    const sizes = sizeClasses[size] || sizeClasses.md;

    const containerClasses = cn(
        'inline-flex items-center rounded-full font-medium transition-colors',
        sizes.container,
        config.bgClass,
        config.textClass,
        showBorder && `border ${config.borderClass}`,
        className
    );

    const iconClasses = cn(sizes.icon, config.iconClass);

    // Add tooltip for failed status with error message
    const title = status === 'Failed' && error ? error : undefined;

    return (
        <span className={containerClasses} title={title}>
            <Icon className={iconClasses} aria-hidden="true" />
            <span>{displayLabel}</span>
        </span>
    );
}

/**
 * StatusIcon component for displaying only the status icon
 * 
 * @param {Object} props
 * @param {string} props.status - The status string
 * @param {'download' | 'scrape'} [props.type='download'] - Type of status
 * @param {'sm' | 'md' | 'lg'} [props.size='md'] - Size variant
 * @param {string} [props.error] - Error message for Failed status tooltip
 * @param {string} [props.className] - Additional CSS classes
 */
export function StatusIcon({
    status,
    type = 'download',
    size = 'md',
    error,
    className,
}) {
    const configMap = type === 'scrape' ? SCRAPE_STATUS_CONFIG : DOWNLOAD_STATUS_CONFIG;
    const config = configMap[status] || DEFAULT_STATUS_CONFIG;
    const Icon = config.icon;

    const sizeClasses = {
        sm: 'h-4 w-4',
        md: 'h-5 w-5',
        lg: 'h-6 w-6',
    };

    const iconClasses = cn(
        sizeClasses[size] || sizeClasses.md,
        config.iconClass,
        status === 'Failed' && 'cursor-help',
        className
    );

    const title = status === 'Failed' && error ? error : status;

    return <Icon className={iconClasses} title={title} aria-label={status} />;
}

export default StatusBadge;
