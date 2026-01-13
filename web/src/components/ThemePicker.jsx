/**
 * Theme picker component
 * Dropdown for selecting light/dark/system theme
 */
import React, { useState, useEffect, useRef } from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';
import { Button, cn } from './ui';

/**
 * Theme mode options
 */
const THEME_MODES = {
    LIGHT: 'light',
    DARK: 'dark',
    SYSTEM: 'system',
};

/**
 * Theme picker dropdown component
 * 
 * @param {Object} props - Component props
 * @param {string} props.themeMode - Current theme mode
 * @param {function} props.setThemeMode - Theme mode setter
 */
export function ThemePicker({ themeMode, setThemeMode }) {
    const [showPicker, setShowPicker] = useState(false);
    const pickerRef = useRef(null);

    // Close picker when clicking outside
    useEffect(() => {
        if (!showPicker) return;

        const handleClickOutside = (e) => {
            if (pickerRef.current && !pickerRef.current.contains(e.target)) {
                setShowPicker(false);
            }
        };

        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                setShowPicker(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        document.addEventListener('keydown', handleEscape);

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
            document.removeEventListener('keydown', handleEscape);
        };
    }, [showPicker]);

    const getIcon = () => {
        switch (themeMode) {
            case THEME_MODES.LIGHT:
                return <Sun className="h-4 w-4" />;
            case THEME_MODES.DARK:
                return <Moon className="h-4 w-4" />;
            default:
                return <Monitor className="h-4 w-4" />;
        }
    };

    const handleSelect = (mode) => {
        setThemeMode(mode);
        setShowPicker(false);
    };

    return (
        <div className="relative z-40" ref={pickerRef} onClick={(e) => e.stopPropagation()}>
            <Button
                type="button"
                variant="outline"
                className="h-8 w-8 p-0"
                onClick={() => setShowPicker((v) => !v)}
                aria-label="Theme"
                title="Theme"
            >
                {getIcon()}
            </Button>

            {showPicker && (
                <div className="absolute left-0 z-50 mt-2 w-8 overflow-hidden rounded-md border bg-popover text-sm text-popover-foreground shadow-sm">
                    <button
                        type="button"
                        className={cn(
                            "flex h-8 w-8 items-center justify-center",
                            "hover:bg-accent hover:text-accent-foreground",
                            themeMode === THEME_MODES.LIGHT ? "bg-muted" : ""
                        )}
                        onClick={() => handleSelect(THEME_MODES.LIGHT)}
                        aria-label="Light"
                        title="Light"
                    >
                        <Sun className="h-4 w-4" />
                    </button>
                    <button
                        type="button"
                        className={cn(
                            "flex h-8 w-8 items-center justify-center",
                            "hover:bg-accent hover:text-accent-foreground",
                            themeMode === THEME_MODES.SYSTEM ? "bg-muted" : ""
                        )}
                        onClick={() => handleSelect(THEME_MODES.SYSTEM)}
                        aria-label="System"
                        title="System"
                    >
                        <Monitor className="h-4 w-4" />
                    </button>
                    <button
                        type="button"
                        className={cn(
                            "flex h-8 w-8 items-center justify-center",
                            "hover:bg-accent hover:text-accent-foreground",
                            themeMode === THEME_MODES.DARK ? "bg-muted" : ""
                        )}
                        onClick={() => handleSelect(THEME_MODES.DARK)}
                        aria-label="Dark"
                        title="Dark"
                    >
                        <Moon className="h-4 w-4" />
                    </button>
                </div>
            )}
        </div>
    );
}

export default ThemePicker;
