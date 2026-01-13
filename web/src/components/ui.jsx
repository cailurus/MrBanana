import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs) {
    return twMerge(clsx(inputs));
}

export const Card = ({ className, children }) => (
    <div
        className={cn(
            'rounded-xl border border-border/60 bg-card/70 text-card-foreground shadow-sm',
            'supports-[backdrop-filter]:bg-card/55 supports-[backdrop-filter]:backdrop-blur-xl',
            className
        )}
    >
        {children}
    </div>
);

export const Button = ({ className, variant = 'default', size = 'default', ...props }) => {
    const variants = {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        outline: 'border border-input bg-background hover:bg-accent hover:text-accent-foreground',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
    };
    const sizes = {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 rounded-lg px-3',
        icon: 'h-10 w-10',
    };
    return (
        <button
            className={cn(
                'relative inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-medium ring-offset-background transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
                'hover:-translate-y-0.5 hover:shadow-md active:translate-y-0 active:shadow-sm',
                variants[variant],
                sizes[size],
                className
            )}
            {...props}
        />
    );
};

export const Input = ({ className, ...props }) => (
    <input
        className={cn(
            'flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
            className
        )}
        {...props}
    />
);

export const Select = ({ className, children, ...props }) => (
    <select
        className={cn(
            'flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
            className
        )}
        {...props}
    >
        {children}
    </select>
);

export const Progress = ({ value, className }) => (
    <div
        className={cn('relative h-2 w-full overflow-hidden rounded-full bg-muted', className)}
        role="progressbar"
        aria-valuenow={Math.round(value || 0)}
        aria-valuemin={0}
        aria-valuemax={100}
    >
        <div
            className="h-full w-full flex-1 bg-primary transition-transform duration-300 ease-out"
            style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
        />
    </div>
);
