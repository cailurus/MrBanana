import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from './ui';

/**
 * LoadingSpinner - A simple spinning loader
 * 
 * @param {Object} props
 * @param {'sm' | 'md' | 'lg' | 'xl'} [props.size='md'] - Size variant
 * @param {string} [props.className] - Additional CSS classes
 */
export function LoadingSpinner({ size = 'md', className }) {
    const sizeClasses = {
        sm: 'h-4 w-4',
        md: 'h-6 w-6',
        lg: 'h-8 w-8',
        xl: 'h-12 w-12',
    };

    return (
        <Loader2
            className={cn(
                'animate-spin text-muted-foreground',
                sizeClasses[size] || sizeClasses.md,
                className
            )}
            aria-label="Loading"
        />
    );
}

/**
 * LoadingOverlay - Full container loading overlay
 * 
 * @param {Object} props
 * @param {boolean} [props.show=true] - Whether to show the overlay
 * @param {string} [props.text] - Optional loading text
 * @param {string} [props.className] - Additional CSS classes
 */
export function LoadingOverlay({ show = true, text, className }) {
    if (!show) return null;

    return (
        <div
            className={cn(
                'absolute inset-0 z-10 flex flex-col items-center justify-center',
                'bg-background/80 supports-[backdrop-filter]:backdrop-blur-sm',
                className
            )}
            role="status"
            aria-live="polite"
        >
            <LoadingSpinner size="lg" />
            {text && (
                <p className="mt-3 text-sm text-muted-foreground animate-pulse">
                    {text}
                </p>
            )}
        </div>
    );
}

/**
 * Skeleton - Placeholder for loading content
 * 
 * @param {Object} props
 * @param {'text' | 'circle' | 'rect' | 'avatar'} [props.variant='text'] - Shape variant
 * @param {string} [props.width] - Custom width (e.g., '100px', '50%')
 * @param {string} [props.height] - Custom height
 * @param {string} [props.className] - Additional CSS classes
 */
export function Skeleton({ variant = 'text', width, height, className }) {
    const variantClasses = {
        text: 'h-4 rounded',
        circle: 'rounded-full aspect-square',
        rect: 'rounded-lg',
        avatar: 'h-10 w-10 rounded-full',
    };

    const baseClasses = cn(
        'animate-pulse bg-muted/60',
        variantClasses[variant] || variantClasses.text,
        className
    );

    const style = {
        width: width || (variant === 'text' ? '100%' : undefined),
        height: height || undefined,
    };

    return <div className={baseClasses} style={style} aria-hidden="true" />;
}

/**
 * SkeletonText - Multiple lines of skeleton text
 * 
 * @param {Object} props
 * @param {number} [props.lines=3] - Number of lines
 * @param {string} [props.className] - Additional CSS classes
 */
export function SkeletonText({ lines = 3, className }) {
    return (
        <div className={cn('space-y-2', className)} aria-hidden="true">
            {Array.from({ length: lines }).map((_, i) => (
                <Skeleton
                    key={i}
                    variant="text"
                    width={i === lines - 1 ? '60%' : '100%'}
                />
            ))}
        </div>
    );
}

/**
 * SkeletonCard - Card-shaped skeleton placeholder
 * 
 * @param {Object} props
 * @param {string} [props.className] - Additional CSS classes
 */
export function SkeletonCard({ className }) {
    return (
        <div
            className={cn(
                'rounded-xl border border-border/60 bg-card/50 p-4 space-y-3',
                className
            )}
            aria-hidden="true"
        >
            <div className="flex items-center gap-3">
                <Skeleton variant="avatar" />
                <div className="flex-1 space-y-2">
                    <Skeleton variant="text" width="40%" />
                    <Skeleton variant="text" width="60%" />
                </div>
            </div>
            <SkeletonText lines={2} />
        </div>
    );
}

/**
 * SkeletonTable - Table rows skeleton
 * 
 * @param {Object} props
 * @param {number} [props.rows=5] - Number of rows
 * @param {number} [props.cols=5] - Number of columns
 * @param {string} [props.className] - Additional CSS classes
 */
export function SkeletonTable({ rows = 5, cols = 5, className }) {
    return (
        <div className={cn('space-y-2', className)} aria-hidden="true">
            {Array.from({ length: rows }).map((_, rowIndex) => (
                <div
                    key={rowIndex}
                    className="flex items-center gap-3 rounded-lg bg-card/30 p-3"
                >
                    {Array.from({ length: cols }).map((_, colIndex) => (
                        <Skeleton
                            key={colIndex}
                            variant="text"
                            width={colIndex === 0 ? '80px' : undefined}
                            className="flex-1"
                        />
                    ))}
                </div>
            ))}
        </div>
    );
}

/**
 * PageLoader - Full page loading state
 * 
 * @param {Object} props
 * @param {string} [props.text='Loading...'] - Loading text
 */
export function PageLoader({ text = 'Loading...' }) {
    return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-background">
            <LoadingSpinner size="xl" className="text-primary" />
            <p className="mt-4 text-lg text-muted-foreground">{text}</p>
        </div>
    );
}

/**
 * ButtonLoader - Inline loading state for buttons
 * 
 * @param {Object} props
 * @param {boolean} props.loading - Whether loading
 * @param {React.ReactNode} props.children - Button content
 */
export function ButtonLoader({ loading, children }) {
    if (!loading) return children;

    return (
        <span className="inline-flex items-center gap-2">
            <LoadingSpinner size="sm" />
            {children}
        </span>
    );
}

export default LoadingSpinner;
