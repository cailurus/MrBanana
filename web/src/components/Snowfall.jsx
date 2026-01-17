/**
 * Snowfall Effect Component
 * 
 * A beautiful snowfall effect that can be triggered by clicking the © symbol.
 * This is an independent, fun feature that can be easily removed.
 * 
 * Usage:
 *   const { Snowfall, toggleSnow, isSnowing } = useSnowfall();
 *   <div onClick={toggleSnow}>©</div>
 *   <Snowfall />
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';

// Snowflake characters for variety
const SNOWFLAKES = ['❄', '❅', '❆', '✻', '✼', '❉', '✿', '❋'];

/**
 * Single Snowflake Component
 */
function Snowflake({ style, char }) {
    return (
        <div
            className="snowflake pointer-events-none select-none"
            style={style}
        >
            {char}
        </div>
    );
}

/**
 * Generate random snowflake properties
 */
function createSnowflake(id) {
    const size = Math.random() * 1 + 0.5; // 0.5 - 1.5rem
    const left = Math.random() * 100; // 0 - 100%
    const animationDuration = Math.random() * 8 + 8; // 8 - 16s
    const animationDelay = Math.random() * -15; // stagger start
    const opacity = Math.random() * 0.6 + 0.4; // 0.4 - 1
    const char = SNOWFLAKES[Math.floor(Math.random() * SNOWFLAKES.length)];
    const drift = (Math.random() - 0.5) * 100; // horizontal drift

    return {
        id,
        char,
        style: {
            position: 'fixed',
            top: '-2rem',
            left: `${left}%`,
            fontSize: `${size}rem`,
            opacity,
            color: 'white',
            textShadow: '0 0 5px rgba(255,255,255,0.8), 0 0 10px rgba(173,216,230,0.5)',
            animation: `snowfall-drop ${animationDuration}s linear ${animationDelay}s infinite`,
            '--drift': `${drift}px`,
            zIndex: 9999,
            filter: 'blur(0.3px)',
        },
    };
}

/**
 * Snowfall Container Component
 */
function SnowfallContainer({ active, snowflakeCount = 50 }) {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        if (active) {
            setMounted(true);
        } else {
            // Delay unmount to allow fade out
            const timer = setTimeout(() => setMounted(false), 500);
            return () => clearTimeout(timer);
        }
    }, [active]);

    // Generate snowflakes once
    const snowflakes = useMemo(() => {
        return Array.from({ length: snowflakeCount }, (_, i) => createSnowflake(i));
    }, [snowflakeCount]);

    if (!mounted) return null;

    return (
        <>
            {/* CSS Animation Styles */}
            <style>{`
                @keyframes snowfall-drop {
                    0% {
                        transform: translateY(0) translateX(0) rotate(0deg);
                        opacity: var(--start-opacity, 1);
                    }
                    25% {
                        transform: translateY(25vh) translateX(calc(var(--drift) * 0.5)) rotate(90deg);
                    }
                    50% {
                        transform: translateY(50vh) translateX(var(--drift)) rotate(180deg);
                    }
                    75% {
                        transform: translateY(75vh) translateX(calc(var(--drift) * 0.5)) rotate(270deg);
                    }
                    100% {
                        transform: translateY(105vh) translateX(0) rotate(360deg);
                        opacity: 0;
                    }
                }
                
                .snowfall-container {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100vw;
                    height: 100vh;
                    pointer-events: none;
                    z-index: 9999;
                    overflow: hidden;
                    transition: opacity 0.5s ease;
                }
                
                .snowfall-container.fading {
                    opacity: 0;
                }
            `}</style>

            <div className={`snowfall-container ${active ? '' : 'fading'}`}>
                {snowflakes.map((flake) => (
                    <Snowflake key={flake.id} style={flake.style} char={flake.char} />
                ))}
            </div>
        </>
    );
}

/**
 * useSnowfall Hook
 * 
 * Returns the Snowfall component and toggle function.
 * Keep snowfall state and logic encapsulated.
 */
export function useSnowfall() {
    const [isSnowing, setIsSnowing] = useState(false);

    const toggleSnow = useCallback(() => {
        setIsSnowing((prev) => !prev);
    }, []);

    const startSnow = useCallback(() => setIsSnowing(true), []);
    const stopSnow = useCallback(() => setIsSnowing(false), []);

    // The Snowfall component bound to this hook's state
    const Snowfall = useCallback(
        () => <SnowfallContainer active={isSnowing} />,
        [isSnowing]
    );

    return {
        Snowfall,
        toggleSnow,
        startSnow,
        stopSnow,
        isSnowing,
    };
}

export default SnowfallContainer;
