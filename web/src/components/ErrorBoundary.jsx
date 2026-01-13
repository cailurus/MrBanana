import React from 'react';
import { cn } from './ui';

/**
 * React Error Boundary component
 * Catches JavaScript errors in child components and displays a fallback UI
 */
export class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        this.setState({ errorInfo });
        // Log error to console in development
        if (process.env.NODE_ENV === 'development') {
            console.error('ErrorBoundary caught an error:', error, errorInfo);
        }
    }

    render() {
        if (this.state.hasError) {
            const { fallback, children } = this.props;

            if (fallback) {
                return typeof fallback === 'function'
                    ? fallback({ error: this.state.error, errorInfo: this.state.errorInfo })
                    : fallback;
            }

            return (
                <div className={cn(
                    "min-h-[200px] flex flex-col items-center justify-center",
                    "rounded-xl border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/20",
                    "p-6 text-center"
                )}>
                    <div className="text-red-600 dark:text-red-400 mb-2">
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="48"
                            height="48"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <circle cx="12" cy="12" r="10" />
                            <line x1="12" y1="8" x2="12" y2="12" />
                            <line x1="12" y1="16" x2="12.01" y2="16" />
                        </svg>
                    </div>
                    <h3 className="text-lg font-semibold text-red-700 dark:text-red-300 mb-1">
                        Something went wrong
                    </h3>
                    <p className="text-sm text-red-600 dark:text-red-400 mb-4">
                        An unexpected error occurred. Please try refreshing the page.
                    </p>
                    <button
                        type="button"
                        onClick={() => window.location.reload()}
                        className={cn(
                            "px-4 py-2 rounded-md text-sm font-medium",
                            "bg-red-600 text-white hover:bg-red-700",
                            "transition-colors"
                        )}
                    >
                        Refresh Page
                    </button>
                    {process.env.NODE_ENV === 'development' && this.state.error && (
                        <details className="mt-4 text-left w-full max-w-md">
                            <summary className="text-xs text-red-500 cursor-pointer">
                                Error Details (Development)
                            </summary>
                            <pre className="mt-2 text-xs bg-red-100 dark:bg-red-900/30 p-2 rounded overflow-auto max-h-40">
                                {this.state.error.toString()}
                                {this.state.errorInfo?.componentStack}
                            </pre>
                        </details>
                    )}
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
