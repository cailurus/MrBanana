import React from 'react';
import { Download, FolderSearch, Inbox, Search, FileQuestion, Bell } from 'lucide-react';
import { cn } from './ui';

/**
 * EmptyState configuration for different types
 */
const EMPTY_STATE_CONFIG = {
    download: {
        icon: Download,
        iconColor: 'text-blue-400 dark:text-blue-500',
        bgGradient: 'from-blue-500/5 to-transparent',
    },
    scrape: {
        icon: FolderSearch,
        iconColor: 'text-emerald-400 dark:text-emerald-500',
        bgGradient: 'from-emerald-500/5 to-transparent',
    },
    search: {
        icon: Search,
        iconColor: 'text-purple-400 dark:text-purple-500',
        bgGradient: 'from-purple-500/5 to-transparent',
    },
    subscription: {
        icon: Bell,
        iconColor: 'text-amber-400 dark:text-amber-500',
        bgGradient: 'from-amber-500/5 to-transparent',
    },
    inbox: {
        icon: Inbox,
        iconColor: 'text-gray-400 dark:text-gray-500',
        bgGradient: 'from-gray-500/5 to-transparent',
    },
    default: {
        icon: FileQuestion,
        iconColor: 'text-gray-400 dark:text-gray-500',
        bgGradient: 'from-gray-500/5 to-transparent',
    },
};

/**
 * EmptyState component for displaying empty content with illustration and guidance
 * 
 * @param {Object} props
 * @param {'download' | 'scrape' | 'search' | 'inbox' | 'default'} [props.type='default'] - Type of empty state
 * @param {string} props.title - Main message to display
 * @param {string} [props.description] - Secondary description text
 * @param {React.ReactNode} [props.action] - Optional action button/element
 * @param {React.ComponentType} [props.icon] - Custom icon component (overrides type icon)
 * @param {'sm' | 'md' | 'lg'} [props.size='md'] - Size variant
 * @param {string} [props.className] - Additional CSS classes
 */
export function EmptyState({
    type = 'default',
    title,
    description,
    action,
    icon: CustomIcon,
    size = 'md',
    className,
}) {
    const config = EMPTY_STATE_CONFIG[type] || EMPTY_STATE_CONFIG.default;
    const Icon = CustomIcon || config.icon;

    const sizeConfig = {
        sm: {
            container: 'py-6 px-4',
            iconWrapper: 'h-12 w-12 mb-3',
            iconSize: 'h-6 w-6',
            title: 'text-sm',
            description: 'text-xs mt-1',
        },
        md: {
            container: 'py-10 px-4',
            iconWrapper: 'h-16 w-16 mb-4',
            iconSize: 'h-8 w-8',
            title: 'text-base',
            description: 'text-sm mt-2',
        },
        lg: {
            container: 'py-16 px-6',
            iconWrapper: 'h-20 w-20 mb-5',
            iconSize: 'h-10 w-10',
            title: 'text-lg',
            description: 'text-base mt-2',
        },
    };

    const sizes = sizeConfig[size] || sizeConfig.md;

    return (
        <div
            className={cn(
                'relative flex flex-col items-center justify-center text-center rounded-xl',
                'border border-border/60 bg-card/50 overflow-hidden',
                sizes.container,
                className
            )}
        >
            {/* Background gradient decoration */}
            <div
                className={cn(
                    'absolute inset-0 bg-gradient-radial',
                    config.bgGradient,
                    'opacity-50 pointer-events-none'
                )}
                aria-hidden="true"
            />

            {/* Decorative dots pattern */}
            <div
                className="absolute inset-0 opacity-[0.03] dark:opacity-[0.05] pointer-events-none"
                style={{
                    backgroundImage: `radial-gradient(circle, currentColor 1px, transparent 1px)`,
                    backgroundSize: '16px 16px',
                }}
                aria-hidden="true"
            />

            {/* Content */}
            <div className="relative z-10 flex flex-col items-center">
                {/* Icon with animated background */}
                <div
                    className={cn(
                        'relative flex items-center justify-center rounded-full',
                        'bg-muted/50 dark:bg-muted/30',
                        'ring-1 ring-border/40',
                        sizes.iconWrapper
                    )}
                >
                    {/* Subtle pulse animation */}
                    <div
                        className={cn(
                            'absolute inset-0 rounded-full',
                            'animate-pulse opacity-30',
                            'bg-current',
                            config.iconColor
                        )}
                        style={{ animationDuration: '3s' }}
                    />
                    <Icon className={cn(sizes.iconSize, config.iconColor, 'relative z-10')} strokeWidth={1.5} />
                </div>

                {/* Title */}
                <p className={cn('font-medium text-muted-foreground', sizes.title)}>
                    {title}
                </p>

                {/* Description */}
                {description && (
                    <p className={cn('text-muted-foreground/70 max-w-sm', sizes.description)}>
                        {description}
                    </p>
                )}

                {/* Action */}
                {action && (
                    <div className="mt-4">
                        {action}
                    </div>
                )}
            </div>
        </div>
    );
}

/**
 * EmptySearchState - Specialized empty state for search results
 */
export function EmptySearchState({ query, onClear, className }) {
    return (
        <EmptyState
            type="search"
            title={query ? `未找到 "${query}" 相关结果` : '没有搜索结果'}
            description={query ? '尝试使用不同的关键词或清除筛选条件' : undefined}
            action={
                onClear && (
                    <button
                        onClick={onClear}
                        className="text-sm text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-primary/50 rounded px-2 py-1"
                    >
                        清除搜索
                    </button>
                )
            }
            className={className}
        />
    );
}

export default EmptyState;
