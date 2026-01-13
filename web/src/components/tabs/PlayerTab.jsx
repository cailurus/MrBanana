/**
 * PlayerTab - Media library player tab component
 * Uses playerStore for state management
 */
import React, { useState, useCallback } from 'react';
import axios from 'axios';
import { Play, Settings, AlertCircle } from 'lucide-react';
import { t } from '../../i18n';
import { Card, Input, cn } from '../ui';
import { useToast } from '../Toast';
import { InfoTooltip } from '../InfoTooltip';
import { PlayerDetailModal, DirectoryBrowserModal } from '../modals';
import { useGearAnimation, playSettingsOpenSfx, stopSettingsOpenSfx } from '../../hooks';
import { usePlayerStore } from '../../stores';
import { useScrapeStore } from '../../stores/scrapeStore';
import { proxyImageUrl } from '../../utils/appHelpers';

/**
 * PlayerTab Component
 */
export function PlayerTab({
    uiLang,
    dirPickerField,
    setDirPickerField,
}) {
    const toast = useToast();
    const tr = useCallback((key, vars) => t(uiLang, key, vars), [uiLang]);

    // Store state
    const {
        config, setConfig,
        configSaving,
        libraryItems,
        detail,
        openDetail,
        closeDetail,
        startPlaying,
        saveConfig,
        fetchConfig,
        fetchLibrary,
        configReady,
    } = usePlayerStore();

    // Get scrape config for fallback initial dir
    const scrapeConfig = useScrapeStore((s) => s.config);

    // Local UI state
    const [showSettings, setShowSettings] = useState(false);
    const [showDirBrowser, setShowDirBrowser] = useState(false);

    // Animation hooks
    const gearAnim = useGearAnimation();

    const playerRootDirEmpty = !String(config.player_root_dir || '').trim();

    // Directory picker - supports native dialog (localhost) or remote browser
    const chooseDirectory = async ({ title, initialDir }) => {
        try {
            const res = await axios.post('/api/system/choose-directory', {
                title,
                initial_dir: initialDir || null,
            });
            return res?.data?.path || null;
        } catch (err) {
            // If 403 (not localhost), signal to use remote browser
            if (err.response?.status === 403) {
                return null;
            }
            toast.error('Failed to choose directory: ' + (err.response?.data?.detail || err.message));
            return null;
        }
    };

    const handlePickRootDir = async () => {
        setDirPickerField('player_root_dir');
        const picked = await chooseDirectory({
            title: tr('player.settings.rootDir'),
            initialDir: config.player_root_dir || scrapeConfig?.scrape_output_dir || scrapeConfig?.scrape_dir,
        });
        if (picked) {
            setConfig({ player_root_dir: picked });
            try {
                await saveConfig();
                await fetchLibrary();
            } catch (err) {
                // 已在 store 内打印错误
            }
        } else if (picked === null) {
            // Native dialog not available - show remote browser
            setShowDirBrowser(true);
        }
        setDirPickerField(null);
    };

    const handleDirBrowserSelect = async (path) => {
        setConfig({ player_root_dir: path });
        try {
            await saveConfig();
            await fetchLibrary();
        } catch (err) {
            // 已在 store 内打印错误
        }
    };

    // 初始化加载配置
    React.useEffect(() => {
        fetchConfig();
    }, [fetchConfig]);

    // 配置就绪或目录变化时拉取媒体库
    React.useEffect(() => {
        if (!configReady) return;
        if (!config?.player_root_dir) return;
        fetchLibrary();
    }, [configReady, config?.player_root_dir, fetchLibrary]);

    // Settings gear click
    const handleSettingsClick = () => {
        if (gearAnim.isAnimating()) return;
        setShowSettings((v) => {
            const next = !v;
            if (next) {
                gearAnim.start();
                playSettingsOpenSfx();
            } else {
                stopSettingsOpenSfx();
            }
            return next;
        });
    };

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                    <Play className="h-5 w-5 text-primary" />
                    {tr('player.title')}
                </h2>
                <button
                    type="button"
                    aria-label={tr('common.settings')}
                    onClick={handleSettingsClick}
                    className="inline-flex h-9 w-9 items-center justify-center text-muted-foreground hover:text-foreground"
                >
                    <Settings
                        className={cn(
                            'h-5 w-5 mr-banana-gear',
                            showSettings ? 'mr-banana-gear--open' : '',
                            gearAnim.spinning ? 'mr-banana-gear--spin' : ''
                        )}
                    />
                </button>
            </div>

            {/* Settings Panel */}
            {showSettings && (
                <Card className="p-6 space-y-4">
                    <div className="grid gap-2 max-w-2xl">
                        <div className="flex items-center gap-2 text-sm">
                            <div>{tr('player.settings.rootDir')}</div>
                            <InfoTooltip text={tr('player.settings.hint')} />
                            {playerRootDirEmpty && <AlertCircle className="h-4 w-4 text-amber-500" />}
                        </div>
                        <Input
                            placeholder={tr('common.chooseDir')}
                            value={config.player_root_dir}
                            readOnly
                            disabled={Boolean(dirPickerField) || configSaving}
                            onClick={handlePickRootDir}
                        />
                        <div className="text-xs text-muted-foreground mt-1">
                            {tr('player.settings.priorityHint', {
                                priority: 'player_root_dir > scrape_output_dir'
                            })}
                        </div>
                    </div>
                </Card>
            )}

            {/* Library Grid */}
            <Card className="p-4">
                {Array.isArray(libraryItems) && libraryItems.length > 0 ? (
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                        {libraryItems.map((it, idx) => {
                            const title = it?.title || it?.code || tr('common.none');
                            const poster = proxyImageUrl(it?.poster_url || '');
                            return (
                                <button
                                    key={`${it?.code || 'item'}-${idx}`}
                                    type="button"
                                    className={cn(
                                        'group text-left',
                                        'rounded-xl border border-border/60 bg-card/50 p-2',
                                        'hover:bg-card/70'
                                    )}
                                    onClick={() => openDetail(it)}
                                >
                                    <div className="aspect-[2/3] overflow-hidden rounded-lg border bg-muted">
                                        {poster ? (
                                            <img src={poster} alt={title} className="h-full w-full object-cover" loading="lazy" />
                                        ) : null}
                                    </div>
                                    <div className="mt-2 text-sm font-medium truncate" title={title}>
                                        {title}
                                    </div>
                                    <div className="text-xs text-muted-foreground truncate">{it?.code || ''}</div>
                                </button>
                            );
                        })}
                    </div>
                ) : (
                    <div className="rounded-xl border border-border/60 bg-card/50 px-4 py-10 text-center text-muted-foreground">
                        {tr('player.empty')}
                    </div>
                )}
            </Card>

            {/* Detail Modal */}
            <PlayerDetailModal
                open={detail.open}
                item={detail.item}
                playing={detail.playing}
                onClose={closeDetail}
                onPlay={startPlaying}
                tr={tr}
            />

            {/* Remote Directory Browser Modal */}
            <DirectoryBrowserModal
                isOpen={showDirBrowser}
                onClose={() => setShowDirBrowser(false)}
                onSelect={handleDirBrowserSelect}
                title={tr('player.settings.rootDir')}
                initialDir={config.player_root_dir}
                tr={tr}
            />
        </div>
    );
}

export default PlayerTab;
