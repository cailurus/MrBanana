import { useEffect, useRef, useCallback } from 'react';

/**
 * Hook for managing focus trap within a container
 * Useful for modals and dialogs
 * 
 * @param {boolean} active - Whether the focus trap is active
 * @returns {React.RefObject} - Ref to attach to the container element
 */
export function useFocusTrap(active = true) {
    const containerRef = useRef(null);

    useEffect(() => {
        if (!active || !containerRef.current) return;

        const container = containerRef.current;
        const focusableElements = container.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );

        const firstFocusable = focusableElements[0];
        const lastFocusable = focusableElements[focusableElements.length - 1];

        // Focus first element when trap becomes active
        if (firstFocusable) {
            firstFocusable.focus();
        }

        const handleKeyDown = (e) => {
            if (e.key !== 'Tab') return;

            if (e.shiftKey) {
                // Shift + Tab
                if (document.activeElement === firstFocusable) {
                    e.preventDefault();
                    lastFocusable?.focus();
                }
            } else {
                // Tab
                if (document.activeElement === lastFocusable) {
                    e.preventDefault();
                    firstFocusable?.focus();
                }
            }
        };

        container.addEventListener('keydown', handleKeyDown);
        return () => container.removeEventListener('keydown', handleKeyDown);
    }, [active]);

    return containerRef;
}

/**
 * Hook for keyboard navigation in lists
 * Supports arrow keys, Home, End
 * 
 * @param {Object} options - Configuration options
 * @param {number} options.itemCount - Total number of items
 * @param {number} options.currentIndex - Currently focused index
 * @param {function} options.onIndexChange - Index change handler
 * @param {function} [options.onSelect] - Selection handler (Enter/Space)
 * @param {boolean} [options.horizontal=false] - Use left/right arrows instead of up/down
 * @param {boolean} [options.loop=true] - Loop at ends
 * @returns {function} - onKeyDown handler to attach to the list container
 */
export function useArrowNavigation({
    itemCount,
    currentIndex,
    onIndexChange,
    onSelect,
    horizontal = false,
    loop = true,
}) {
    const handleKeyDown = useCallback((e) => {
        const prevKey = horizontal ? 'ArrowLeft' : 'ArrowUp';
        const nextKey = horizontal ? 'ArrowRight' : 'ArrowDown';

        switch (e.key) {
            case prevKey:
                e.preventDefault();
                if (currentIndex > 0) {
                    onIndexChange(currentIndex - 1);
                } else if (loop && itemCount > 0) {
                    onIndexChange(itemCount - 1);
                }
                break;

            case nextKey:
                e.preventDefault();
                if (currentIndex < itemCount - 1) {
                    onIndexChange(currentIndex + 1);
                } else if (loop && itemCount > 0) {
                    onIndexChange(0);
                }
                break;

            case 'Home':
                e.preventDefault();
                if (itemCount > 0) {
                    onIndexChange(0);
                }
                break;

            case 'End':
                e.preventDefault();
                if (itemCount > 0) {
                    onIndexChange(itemCount - 1);
                }
                break;

            case 'Enter':
            case ' ':
                if (onSelect && currentIndex >= 0 && currentIndex < itemCount) {
                    e.preventDefault();
                    onSelect(currentIndex);
                }
                break;

            default:
                break;
        }
    }, [currentIndex, itemCount, onIndexChange, onSelect, horizontal, loop]);

    return handleKeyDown;
}

/**
 * Hook for handling Escape key to close overlays
 * 
 * @param {function} onClose - Close handler
 * @param {boolean} [enabled=true] - Whether the hook is enabled
 */
export function useEscapeKey(onClose, enabled = true) {
    useEffect(() => {
        if (!enabled) return;

        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                onClose();
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [onClose, enabled]);
}

/**
 * Hook for click outside detection
 * 
 * @param {function} onClickOutside - Handler for clicks outside
 * @param {boolean} [enabled=true] - Whether the hook is enabled
 * @returns {React.RefObject} - Ref to attach to the container
 */
export function useClickOutside(onClickOutside, enabled = true) {
    const ref = useRef(null);

    useEffect(() => {
        if (!enabled) return;

        const handleClick = (e) => {
            if (ref.current && !ref.current.contains(e.target)) {
                onClickOutside();
            }
        };

        document.addEventListener('mousedown', handleClick);
        document.addEventListener('touchstart', handleClick);

        return () => {
            document.removeEventListener('mousedown', handleClick);
            document.removeEventListener('touchstart', handleClick);
        };
    }, [onClickOutside, enabled]);

    return ref;
}

/**
 * Visually hidden text for screen readers
 * 
 * @param {Object} props
 * @param {React.ReactNode} props.children - Content to hide visually
 */
export function VisuallyHidden({ children }) {
    return (
        <span
            style={{
                position: 'absolute',
                width: '1px',
                height: '1px',
                padding: 0,
                margin: '-1px',
                overflow: 'hidden',
                clip: 'rect(0, 0, 0, 0)',
                whiteSpace: 'nowrap',
                border: 0,
            }}
        >
            {children}
        </span>
    );
}

/**
 * Skip link for keyboard navigation
 * Allows users to skip to main content
 * 
 * @param {Object} props
 * @param {string} [props.href='#main-content'] - Target ID
 * @param {string} [props.children='跳到主要内容'] - Link text
 */
export function SkipLink({ href = '#main-content', children = '跳到主要内容' }) {
    return (
        <a
            href={href}
            className="sr-only focus:not-sr-only focus:absolute focus:z-[100] focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2"
        >
            {children}
        </a>
    );
}

/**
 * Announce text to screen readers via live region
 * 
 * @param {string} message - Message to announce
 * @param {'polite' | 'assertive'} [priority='polite'] - Announcement priority
 */
export function announce(message, priority = 'polite') {
    // Find or create the announcer element
    let announcer = document.getElementById('aria-live-announcer');

    if (!announcer) {
        announcer = document.createElement('div');
        announcer.id = 'aria-live-announcer';
        announcer.setAttribute('aria-live', priority);
        announcer.setAttribute('aria-atomic', 'true');
        announcer.style.cssText = 'position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); border: 0;';
        document.body.appendChild(announcer);
    }

    // Clear and set message with a delay to ensure it's announced
    announcer.textContent = '';
    announcer.setAttribute('aria-live', priority);

    setTimeout(() => {
        announcer.textContent = message;
    }, 100);
}

/**
 * Hook for managing announcements
 * 
 * @returns {function} - Announce function
 */
export function useAnnounce() {
    return useCallback((message, priority = 'polite') => {
        announce(message, priority);
    }, []);
}

export default {
    useFocusTrap,
    useArrowNavigation,
    useEscapeKey,
    useClickOutside,
    VisuallyHidden,
    SkipLink,
    announce,
    useAnnounce,
};
