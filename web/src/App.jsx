/**
 * Mr. Banana - Main Application Component
 *
 * Delegates download/player/scrape state to their respective stores and hooks.
 * App.jsx only owns: tab navigation, WebSocket, log viewer, context menu, about modal.
 */
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { X, ArrowUpCircle } from 'lucide-react';
import { t, detectDefaultUiLang, APP_VERSION } from './i18n';
import { Button } from './components/ui';
import { useToast } from './components/Toast';
import { LogViewerModal } from './components/LogViewerModal';
import { ContextMenu } from './components/ContextMenu';
import { ThemePicker } from './components/ThemePicker';
import { LanguagePicker } from './components/LanguagePicker';
import { DownloadTab, PlayerTab, SubscriptionTab } from './components/tabs';
import { ScrapeTab } from './components/tabs/scrape';
import { useDownloadStore } from './stores';
import { useTheme, usePersistedString } from './hooks';
import { useWebSocket } from './hooks/useWebSocket';
import { useLogViewer } from './hooks/useLogViewer';
import { useSnowfall } from './components/Snowfall';
import faviconUrl from '/favicon.svg';

// App build info
const APP_BUILD_DATE = '2026-03-13';
const APP_AUTHOR = 'xxm';

function App() {
    const toast = useToast();

    // About modal
    const [showAbout, setShowAbout] = useState(false);

    // Update check
    const [updateInfo, setUpdateInfo] = useState(null);
    useEffect(() => {
        axios.get('/api/version/check')
            .then((resp) => { if (resp.data?.has_update) setUpdateInfo(resp.data); })
            .catch(() => {});
    }, []);

    // =========================================================================
    // Theme & Language
    // =========================================================================
    const { themeMode, setThemeMode } = useTheme('mr-banana-theme-mode');

    const [uiLang, setUiLang] = usePersistedString(
        'mr-banana-ui-lang',
        detectDefaultUiLang(),
        ['banana-ui-lang', 'mrjet-ui-lang'],
    );

    const tr = useCallback((key, vars) => t(uiLang, key, vars), [uiLang]);

    // =========================================================================
    // Easter eggs
    // =========================================================================
    const { Snowfall, toggleSnow } = useSnowfall();

    // =========================================================================
    // Tab Management
    // =========================================================================
    const [activeTab, setActiveTab] = usePersistedString(
        'mr-banana-active-tab',
        'download',
        ['banana-active-tab', 'mrjet-active-tab'],
    );

    // =========================================================================
    // Download store (for resume/pause/delete & WebSocket integration)
    // =========================================================================
    const fetchHistory = useDownloadStore((s) => s.fetchHistory);
    const downloadConfig = useDownloadStore((s) => s.config);

    // =========================================================================
    // WebSocket — real-time task updates
    // =========================================================================
    const { clearTaskStatusHistory } = useWebSocket({
        onHistoryRefreshNeeded: fetchHistory,
    });

    // =========================================================================
    // Log viewer
    // =========================================================================
    const logViewer = useLogViewer();

    // =========================================================================
    // Context menu
    // =========================================================================
    const [contextMenu, setContextMenu] = useState(null);

    useEffect(() => {
        if (!contextMenu) return;
        const dismiss = () => setContextMenu(null);
        const onEsc = (e) => { if (e.key === 'Escape') dismiss(); };
        window.addEventListener('click', dismiss);
        window.addEventListener('keydown', onEsc);
        return () => {
            window.removeEventListener('click', dismiss);
            window.removeEventListener('keydown', onEsc);
        };
    }, [contextMenu]);

    // =========================================================================
    // Directory picker shared state
    // =========================================================================
    const [dirPickerField, setDirPickerField] = useState(null);

    // =========================================================================
    // Task actions (resume / pause / delete)
    // =========================================================================
    const handleResume = async (taskId) => {
        try {
            const out = String(downloadConfig.outputDir || '').trim();
            if (!out) {
                toast.error(t(uiLang, 'download.error.noOutputDir'));
                return;
            }
            await axios.post('/api/resume', { task_id: taskId, output_dir: out });
            fetchHistory();
        } catch (err) {
            toast.error('Failed to resume download: ' + (err.response?.data?.detail || err.message));
        }
    };

    const handlePause = async (taskId) => {
        try {
            await axios.post('/api/pause', { task_id: taskId });
            fetchHistory();
        } catch (err) {
            toast.error('Failed to pause download: ' + (err.response?.data?.detail || err.message));
        }
    };

    const handleDelete = async (taskId) => {
        try {
            await axios.post('/api/delete', { task_id: taskId });
            logViewer.closeIfMatches(taskId);
            fetchHistory();
        } catch (err) {
            toast.error('Failed to delete task: ' + (err.response?.data?.detail || err.message));
        }
    };

    // =========================================================================
    // Render
    // =========================================================================
    return (
        <div className="min-h-screen bg-background p-8 font-sans text-foreground">
            <div className="mx-auto max-w-5xl space-y-8">

                {/* Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="relative">
                            <img
                                src={faviconUrl}
                                alt="Mr. Banana"
                                className="h-7 w-7 object-contain cursor-pointer hover:scale-110 transition-transform active:scale-95"
                                draggable={false}
                                onClick={() => setShowAbout(true)}
                                title={tr('app.about')}
                            />
                            {updateInfo && (
                                <a
                                    href={updateInfo.release_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="absolute -top-1 -right-1 flex items-center justify-center"
                                    title={tr('app.newVersionAvailable', { version: updateInfo.latest_version })}
                                >
                                    <span className="relative flex h-3 w-3">
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                        <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                                    </span>
                                </a>
                            )}
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight">{tr('app.title')}</h1>
                        {updateInfo && (
                            <a
                                href={updateInfo.release_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-green-500/10 text-green-600 dark:text-green-400 hover:bg-green-500/20 transition-colors"
                            >
                                <ArrowUpCircle className="h-3 w-3" />
                                {tr('app.newVersion')}
                            </a>
                        )}
                    </div>
                    <div className="flex items-center gap-3">
                        <ThemePicker themeMode={themeMode} setThemeMode={setThemeMode} />
                        <LanguagePicker language={uiLang} setLanguage={setUiLang} />
                    </div>
                </div>

                {/* Tabs */}
                <div className="w-full">
                    <div className="flex w-full items-center gap-3">
                        {['subscription', 'download', 'scrape', 'player'].map((tab) => (
                            <Button
                                key={tab}
                                type="button"
                                className="flex-1 border"
                                variant={activeTab === tab ? 'default' : 'ghost'}
                                onClick={() => setActiveTab(tab)}
                            >
                                {tr(`tab.${tab}`)}
                            </Button>
                        ))}
                    </div>
                </div>

                {activeTab === 'subscription' && (
                    <SubscriptionTab uiLang={uiLang} />
                )}

                {activeTab === 'download' && (
                    <DownloadTab
                        uiLang={uiLang}
                        dirPickerField={dirPickerField}
                        setDirPickerField={setDirPickerField}
                        openLogViewer={logViewer.open}
                        setContextMenu={setContextMenu}
                        onResume={handleResume}
                    />
                )}

                {activeTab === 'player' && (
                    <PlayerTab
                        uiLang={uiLang}
                        dirPickerField={dirPickerField}
                        setDirPickerField={setDirPickerField}
                    />
                )}

                {activeTab === 'scrape' && (
                    <ScrapeTab
                        uiLang={uiLang}
                        dirPickerField={dirPickerField}
                        setDirPickerField={setDirPickerField}
                        openLogViewer={logViewer.open}
                        tr={tr}
                    />
                )}

                <ContextMenu
                    contextMenu={contextMenu}
                    onClose={() => setContextMenu(null)}
                    onResume={handleResume}
                    onPause={handlePause}
                    onDelete={handleDelete}
                    tr={tr}
                />

                <LogViewerModal
                    open={logViewer.viewer.open}
                    onClose={logViewer.close}
                    logViewer={logViewer.viewer}
                    logText={logViewer.logText}
                    logExists={logViewer.logExists}
                    logEndRef={logViewer.logEndRef}
                    tr={tr}
                />

                {/* About Modal */}
                {showAbout && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowAbout(false)}>
                        <div
                            className="relative bg-card border rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4 animate-in fade-in zoom-in-95 duration-200"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <button
                                type="button"
                                className="absolute top-3 right-3 p-1 rounded-lg hover:bg-muted transition-colors"
                                onClick={() => setShowAbout(false)}
                            >
                                <X className="h-4 w-4 text-muted-foreground" />
                            </button>

                            <div className="flex flex-col items-center text-center space-y-4">
                                <img src={faviconUrl} alt="Mr. Banana" className="h-16 w-16 object-contain" draggable={false} />
                                <div>
                                    <h2 className="text-xl font-bold">Mr. Banana</h2>
                                    <p className="text-sm text-muted-foreground mt-1">{tr('app.aboutSubtitle')}</p>
                                </div>

                                <div className="w-full space-y-2 text-sm">
                                    <div className="flex justify-between py-2 border-b border-border/50">
                                        <span className="text-muted-foreground">{tr('app.version')}</span>
                                        <span className="font-mono">v{APP_VERSION}</span>
                                    </div>
                                    <div className="flex justify-between py-2 border-b border-border/50">
                                        <span className="text-muted-foreground">{tr('app.buildDate')}</span>
                                        <span className="font-mono">{APP_BUILD_DATE}</span>
                                    </div>
                                    <div className="flex justify-between py-2 border-b border-border/50">
                                        <span className="text-muted-foreground">{tr('app.author')}</span>
                                        <span>{APP_AUTHOR}</span>
                                    </div>
                                    <div className="flex justify-between py-2">
                                        <span className="text-muted-foreground">GitHub</span>
                                        <a
                                            href="https://github.com/cailurus/MrBanana"
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-primary hover:underline"
                                        >
                                            cailurus/MrBanana
                                        </a>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Footer */}
                <div className="text-center text-xs text-muted-foreground/60 pt-4 pb-2">
                    <span
                        onClick={toggleSnow}
                        className="cursor-pointer hover:text-muted-foreground transition-colors"
                        title="❄️"
                    >©</span> {new Date().getFullYear()} Mr. Banana. All Rights Reserved.
                </div>

            </div>

            <Snowfall />
        </div>
    );
}

export default App;
