/**
 * Language picker component
 * Dropdown for selecting UI language
 */
import React, { useState, useEffect, useRef } from 'react';
import { Button, cn } from './ui';

/**
 * Supported languages
 */
export const LANGUAGES = {
    EN: 'en',
    ZH_CN: 'zh-CN',
    ZH_TW: 'zh-TW',
};

/**
 * Language display labels
 */
const LANGUAGE_LABELS = {
    [LANGUAGES.EN]: 'EN',
    [LANGUAGES.ZH_CN]: '简',
    [LANGUAGES.ZH_TW]: '繁',
};

/**
 * Language picker dropdown component
 * 
 * @param {Object} props - Component props
 * @param {string} props.language - Current language
 * @param {function} props.setLanguage - Language setter
 */
export function LanguagePicker({ language, setLanguage }) {
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

    const getDisplayLabel = () => {
        return LANGUAGE_LABELS[language] || 'EN';
    };

    const handleSelect = (lang) => {
        setLanguage(lang);
        setShowPicker(false);
    };

    return (
        <div className="relative z-40" ref={pickerRef} onClick={(e) => e.stopPropagation()}>
            <Button
                type="button"
                variant="outline"
                className="h-9 w-9 p-0"
                onClick={() => setShowPicker((v) => !v)}
                aria-label="Language"
            >
                <span className="text-sm font-medium">{getDisplayLabel()}</span>
            </Button>

            {showPicker && (
                <div className="absolute left-0 z-50 mt-2 w-9 rounded-md border bg-popover p-1 text-sm text-popover-foreground shadow-sm">
                    {Object.entries(LANGUAGE_LABELS).map(([lang, label]) => (
                        <button
                            key={lang}
                            type="button"
                            className={cn(
                                "inline-flex w-full items-center justify-center rounded-sm px-2 py-1.5 whitespace-nowrap",
                                "hover:bg-accent hover:text-accent-foreground",
                                language === lang ? "bg-muted" : ""
                            )}
                            onClick={() => handleSelect(lang)}
                        >
                            <span>{label}</span>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

export default LanguagePicker;
