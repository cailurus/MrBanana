import React, { useState, useEffect, useRef } from 'react';
import { Info } from 'lucide-react';

/**
 * Info tooltip component with hover/click support
 */
export function InfoTooltip({ text }) {
    const [open, setOpen] = useState(false);
    const rootRef = useRef(null);

    useEffect(() => {
        if (!open) return;
        const onDocDown = (e) => {
            const el = rootRef.current;
            if (!el) return;
            if (el.contains(e.target)) return;
            setOpen(false);
        };
        document.addEventListener('mousedown', onDocDown);
        return () => document.removeEventListener('mousedown', onDocDown);
    }, [open]);

    const msg = typeof text === 'string' ? text.trim() : '';
    if (!msg) return null;

    return (
        <span
            ref={rootRef}
            className="relative inline-flex"
            onMouseEnter={() => setOpen(true)}
            onMouseLeave={() => setOpen(false)}
        >
            <button
                type="button"
                aria-label={msg}
                onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setOpen((v) => !v);
                }}
                onFocus={() => setOpen(true)}
                onBlur={() => setOpen(false)}
                className="inline-flex h-4 w-4 items-center justify-center text-muted-foreground hover:text-foreground"
            >
                <Info className="h-4 w-4" />
            </button>

            {open && (
                <span
                    className="absolute left-1/2 -translate-x-1/2 top-6 w-64 rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-lg"
                    style={{ zIndex: 9999 }}
                >
                    {msg}
                </span>
            )}
        </span>
    );
}

export default InfoTooltip;
