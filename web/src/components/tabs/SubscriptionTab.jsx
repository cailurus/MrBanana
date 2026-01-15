/**
 * SubscriptionTab - Subscription management tab component
 */
import React, { useState, useCallback, useEffect } from 'react';
import { Bell, Settings, Trash2, RefreshCw, AlertCircle, Clock, ExternalLink, Loader2, Send, History, X, Magnet, Copy, Check } from 'lucide-react';
import { t } from '../../i18n';
import { Button, Card, Input, cn } from '../ui';
import { useToast } from '../Toast';
import { EmptyState } from '../EmptyState';
import { InfoTooltip } from '../InfoTooltip';
import { BrushCleaningIcon } from '../Icons';
import { useGearAnimation, useBroomAnimation, playSettingsOpenSfx, stopSettingsOpenSfx, playBrushCleanSfx } from '../../hooks';
import { useSubscriptionStore } from '../../stores/subscriptionStore';
import { formatDateTime } from '../../utils/format';

/**
 * UpdateHistoryModal - Modal for displaying update history
 */
function UpdateHistoryModal({ isOpen, onClose, item, tr }) {
    const [copiedUrl, setCopiedUrl] = useState(null);

    if (!isOpen || !item) return null;

    const history = item.update_history || [];

    const handleCopy = async (url) => {
        try {
            await navigator.clipboard.writeText(url);
            setCopiedUrl(url);
            setTimeout(() => setCopiedUrl(null), 2000);
        } catch (err) {
            console.error('Failed to copy', err);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
            <div className={cn(
                'relative z-10 w-full max-w-lg max-h-[80vh] overflow-hidden',
                'rounded-xl border border-border/60',
                'bg-card/95 supports-[backdrop-filter]:bg-card/85 supports-[backdrop-filter]:backdrop-blur-xl',
                'shadow-xl'
            )}>
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-border/60">
                    <div className="flex items-center gap-2">
                        <History className="h-5 w-5 text-primary" />
                        <span className="font-medium">{tr('subscription.updateHistory')}</span>
                        <span className="text-muted-foreground">- {item.code}</span>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted"
                    >
                        <X className="h-5 w-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="overflow-y-auto max-h-[60vh] p-4 space-y-4">
                    {history.length === 0 ? (
                        <div className="text-center py-8 text-muted-foreground">
                            {tr('subscription.updateHistory.empty')}
                        </div>
                    ) : (
                        history.map((entry, index) => (
                            <div
                                key={index}
                                className="rounded-lg border border-border/60 bg-muted/30 p-3 space-y-2"
                            >
                                <div className="flex items-center justify-between text-sm">
                                    <div className="flex items-center gap-2 text-muted-foreground">
                                        <Clock className="h-3.5 w-3.5" />
                                        {formatDateTime(entry.time)}
                                    </div>
                                    <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400 text-xs">
                                        {tr('subscription.updateHistory.newLinks', { count: entry.count })}
                                    </span>
                                </div>
                                {entry.links && entry.links.length > 0 && (
                                    <div className="space-y-1.5">
                                        {entry.links.map((link, linkIndex) => (
                                            <div
                                                key={linkIndex}
                                                className="flex items-center gap-2 text-xs bg-background/50 rounded px-2 py-1.5"
                                            >
                                                <Magnet className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                                                <span className="flex-1 truncate text-muted-foreground">
                                                    {link.name || link.url?.substring(0, 60) || 'Unknown'}
                                                </span>
                                                {link.size && (
                                                    <span className="text-muted-foreground">{link.size}</span>
                                                )}
                                                {link.is_hd && (
                                                    <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-600 dark:text-blue-400">
                                                        HD
                                                    </span>
                                                )}
                                                {link.has_subtitle && (
                                                    <span className="px-1.5 py-0.5 rounded bg-green-500/20 text-green-600 dark:text-green-400">
                                                        字幕
                                                    </span>
                                                )}
                                                {link.url && (
                                                    <button
                                                        onClick={() => handleCopy(link.url)}
                                                        className="p-1 rounded hover:bg-muted"
                                                        title="Copy magnet link"
                                                    >
                                                        {copiedUrl === link.url ? (
                                                            <Check className="h-3 w-3 text-green-500" />
                                                        ) : (
                                                            <Copy className="h-3 w-3 text-muted-foreground" />
                                                        )}
                                                    </button>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}

/**
 * SubscriptionItem - Single subscription item display
 */
function SubscriptionItem({ item, tr, onDelete, onMarkRead, onCheck, checking }) {
    const [deleting, setDeleting] = useState(false);
    const [showHistory, setShowHistory] = useState(false);

    const handleDelete = async () => {
        setDeleting(true);
        try {
            await onDelete(item.id);
        } finally {
            setDeleting(false);
        }
    };

    const handleMarkRead = async () => {
        try {
            await onMarkRead(item.id);
        } catch (err) {
            console.error('Failed to mark as read', err);
        }
    };

    // Construct external URL - use javdb_url if available, otherwise fallback to search URL
    const externalUrl = item.javdb_url || `https://javdb.com/search?q=${encodeURIComponent(item.code)}`;

    // Check if there is update history
    const hasHistory = item.update_history && item.update_history.length > 0;

    return (
        <>
            <div className={cn(
                'relative rounded-xl border border-border/60 p-4',
                'bg-card/65 supports-[backdrop-filter]:bg-card/45 supports-[backdrop-filter]:backdrop-blur-xl',
                'transition-colors hover:bg-card/75',
                item.has_update && 'border-amber-500/50'
            )}>
                <div className="flex items-center gap-4">
                    {/* Left: Info */}
                    <div className="flex-1 min-w-0 space-y-2">
                        <div className="flex items-center gap-2">
                            <span className="text-lg font-bold">{item.code}</span>
                            {/* Magnet link count */}
                            {item.magnet_links && item.magnet_links.length > 0 && (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs">
                                    <Magnet className="h-3 w-3" />
                                    {item.magnet_links.length} {tr('subscription.magnetCount')}
                                </span>
                            )}
                            {!!item.has_update && (
                                <span
                                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400 text-xs cursor-pointer"
                                    onClick={handleMarkRead}
                                    title={tr('subscription.clickToMarkRead')}
                                >
                                    <AlertCircle className="h-3 w-3" />
                                    {item.update_detail || tr('subscription.hasUpdate')}
                                </span>
                            )}
                        </div>

                        <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                            <div className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                {tr('subscription.addedAt')}: {formatDateTime(item.created_at)}
                            </div>
                            {item.last_checked_at && (
                                <div className="flex items-center gap-1">
                                    <RefreshCw className="h-3 w-3" />
                                    {tr('subscription.lastChecked')}: {formatDateTime(item.last_checked_at)}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Right: Actions */}
                    <div className="flex items-center gap-2">
                        {/* Update History Button - only show if has history */}
                        {hasHistory && (
                            <button
                                type="button"
                                onClick={() => setShowHistory(true)}
                                className={cn(
                                    'inline-flex items-center justify-center h-8 w-8 rounded-md',
                                    'text-muted-foreground hover:text-foreground hover:bg-muted'
                                )}
                                title={tr('subscription.updateHistory.viewLog')}
                            >
                                <History className="h-4 w-4" />
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={() => onCheck(item.id)}
                            disabled={checking === item.id}
                            className={cn(
                                'inline-flex items-center justify-center h-8 w-8 rounded-md',
                                'text-muted-foreground hover:text-foreground hover:bg-muted',
                                'disabled:opacity-50 disabled:cursor-not-allowed'
                            )}
                            title={tr('subscription.checkNow')}
                        >
                            {checking === item.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <RefreshCw className="h-4 w-4" />
                            )}
                        </button>
                        <a
                            href={externalUrl}
                            target="_blank"
                            rel="noreferrer"
                            className={cn(
                                'inline-flex items-center justify-center h-8 w-8 rounded-md',
                                'text-muted-foreground hover:text-foreground hover:bg-muted'
                            )}
                            title={tr('subscription.viewOnJavdb')}
                        >
                            <ExternalLink className="h-4 w-4" />
                        </a>
                        <button
                            type="button"
                            onClick={handleDelete}
                            disabled={deleting}
                            className={cn(
                                'inline-flex items-center justify-center h-8 w-8 rounded-md',
                                'text-muted-foreground hover:text-destructive hover:bg-destructive/10',
                                'disabled:opacity-50 disabled:cursor-not-allowed'
                            )}
                            title={tr('subscription.delete')}
                        >
                            {deleting ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <Trash2 className="h-4 w-4" />
                            )}
                        </button>
                    </div>
                </div>
            </div>

            {/* Update History Modal */}
            <UpdateHistoryModal
                isOpen={showHistory}
                onClose={() => setShowHistory(false)}
                item={item}
                tr={tr}
            />
        </>
    );
}

/**
 * SubscriptionTab Component
 */
export function SubscriptionTab({ uiLang }) {
    const toast = useToast();
    const tr = useCallback((key, vars) => t(uiLang, key, vars), [uiLang]);

    // Store state
    const {
        subscriptions,
        loading,
        config,
        configLoading,
        fetchSubscriptions,
        fetchConfig,
        updateConfig,
        testTelegram,
        removeSubscription,
        markAsRead,
        checkAllUpdates,
        checkSingleUpdate,
        clearAll,
    } = useSubscriptionStore();

    // Local UI state
    const [showSettings, setShowSettings] = useState(false);
    const [clearing, setClearing] = useState(false);
    const [checkingAll, setCheckingAll] = useState(false);
    const [checkingId, setCheckingId] = useState(null);
    const [intervalDays, setIntervalDays] = useState(1);
    const [telegramBotToken, setTelegramBotToken] = useState('');
    const [telegramChatId, setTelegramChatId] = useState('');
    const [telegramEnabled, setTelegramEnabled] = useState(false);
    const [testingTelegram, setTestingTelegram] = useState(false);

    // Animation hooks
    const gearAnim = useGearAnimation();
    const broomAnim = useBroomAnimation();

    // Fetch data on mount
    useEffect(() => {
        fetchSubscriptions();
        fetchConfig();
    }, [fetchSubscriptions, fetchConfig]);

    // Sync config values from store
    useEffect(() => {
        if (config.checkIntervalDays) {
            setIntervalDays(config.checkIntervalDays);
        }
        if (config.telegramBotToken !== undefined) {
            setTelegramBotToken(config.telegramBotToken);
        }
        if (config.telegramChatId !== undefined) {
            setTelegramChatId(config.telegramChatId);
        }
        if (config.telegramEnabled !== undefined) {
            setTelegramEnabled(config.telegramEnabled);
        }
    }, [config]);

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

    // Save config
    const handleSaveConfig = async () => {
        try {
            await updateConfig({
                check_interval_days: intervalDays,
                telegram_bot_token: telegramBotToken,
                telegram_chat_id: telegramChatId,
                telegram_enabled: telegramEnabled,
            });
            toast.success(tr('subscription.configSaved'));
        } catch (err) {
            toast.error('保存配置失败');
        }
    };

    // Test Telegram
    const handleTestTelegram = async () => {
        if (!telegramBotToken || !telegramChatId) {
            toast.warning(tr('subscription.telegram.fillRequired'));
            return;
        }
        setTestingTelegram(true);
        try {
            // Save config first
            await updateConfig({
                check_interval_days: intervalDays,
                telegram_bot_token: telegramBotToken,
                telegram_chat_id: telegramChatId,
                telegram_enabled: telegramEnabled,
            });
            // Then test
            await testTelegram();
            toast.success(tr('subscription.telegram.testSuccess'));
        } catch (err) {
            // Show detailed error message from backend
            const errorDetail = err.response?.data?.detail || tr('subscription.telegram.testFailed');
            toast.error(errorDetail);
        } finally {
            setTestingTelegram(false);
        }
    };

    // Check all updates
    const handleCheckAll = async () => {
        setCheckingAll(true);
        try {
            const result = await checkAllUpdates();
            if (result.updated_count > 0) {
                toast.success(tr('subscription.checkComplete', { checked: result.checked_count, updated: result.updated_count }));
            } else {
                toast.info(tr('subscription.checkCompleteNoUpdate', { checked: result.checked_count }));
            }
            // Refresh to show updated data
            fetchSubscriptions();
        } catch (err) {
            toast.error('检查更新失败');
        } finally {
            setCheckingAll(false);
        }
    };

    // Check single subscription
    const handleCheckSingle = async (id) => {
        setCheckingId(id);
        try {
            const result = await checkSingleUpdate(id);
            if (result.has_update) {
                toast.success(tr('subscription.foundNewLinks', { count: result.new_count }));
            } else {
                toast.info(tr('subscription.noNewLinks'));
            }
        } catch (err) {
            toast.error('检查失败');
        } finally {
            setCheckingId(null);
        }
    };

    // Clear all handler
    const handleClearAll = async () => {
        if (clearing) return;
        setClearing(true);
        playBrushCleanSfx();
        broomAnim.start();
        try {
            await clearAll();
            toast.success(tr('subscription.cleared'));
        } catch (err) {
            toast.error('清空失败');
        } finally {
            setClearing(false);
        }
    };

    // Delete handler
    const handleDelete = async (id) => {
        try {
            await removeSubscription(id);
            toast.success(tr('subscription.deleted'));
        } catch (err) {
            toast.error('删除失败');
        }
    };

    // Mark as read handler
    const handleMarkRead = async (id) => {
        try {
            await markAsRead(id);
        } catch (err) {
            toast.error('标记失败');
        }
    };

    // Count updates
    const updateCount = subscriptions.filter(s => s.has_update).length;

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                    <Bell className="h-5 w-5 text-primary" />
                    {tr('tab.subscription')}
                    {updateCount > 0 && (
                        <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400 text-xs">
                            {updateCount} {tr('subscription.updates')}
                        </span>
                    )}
                </h2>
                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={handleCheckAll}
                        disabled={checkingAll || subscriptions.length === 0}
                        className={cn(
                            'inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-sm',
                            'bg-primary/10 text-primary hover:bg-primary/20',
                            'disabled:opacity-50 disabled:cursor-not-allowed'
                        )}
                    >
                        {checkingAll ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <RefreshCw className="h-4 w-4" />
                        )}
                        {tr('subscription.checkAll')}
                    </button>
                    <button
                        type="button"
                        aria-label={tr('common.settings')}
                        onClick={handleSettingsClick}
                        className="inline-flex h-9 w-9 items-center justify-center text-muted-foreground hover:text-foreground"
                    >
                        <Settings className={cn('h-5 w-5 mr-banana-gear', showSettings ? 'mr-banana-gear--open' : '', gearAnim.spinning ? 'mr-banana-gear--spin' : '')} />
                    </button>
                </div>
            </div>

            {/* Settings Panel */}
            {showSettings && (
                <Card className="p-6 space-y-6">
                    {/* Check Interval */}
                    <div className="grid gap-4 max-w-md">
                        <div className="grid gap-2">
                            <div className="flex items-center gap-2 text-sm">
                                <div>{tr('subscription.checkInterval')}</div>
                                <InfoTooltip text={tr('subscription.checkIntervalHint')} />
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-sm text-muted-foreground">{tr('subscription.every')}</span>
                                <Input
                                    type="number"
                                    min={1}
                                    max={30}
                                    value={intervalDays}
                                    onChange={(e) => setIntervalDays(Math.max(1, Math.min(30, Number(e.target.value) || 1)))}
                                    className="w-20"
                                />
                                <span className="text-sm text-muted-foreground">{tr('subscription.days')}</span>
                            </div>
                        </div>

                        {config.lastAutoCheckAt && (
                            <div className="text-sm text-muted-foreground">
                                {tr('subscription.lastAutoCheck')}: {formatDateTime(config.lastAutoCheckAt)}
                            </div>
                        )}
                    </div>

                    {/* Telegram Settings */}
                    <div className="border-t border-border pt-6">
                        <div className="grid gap-4 max-w-md">
                            <div className="flex items-center gap-2 text-sm font-medium">
                                <Send className="h-4 w-4" />
                                {tr('subscription.telegram.title')}
                            </div>
                            <p className="text-xs text-muted-foreground">
                                {tr('subscription.telegram.hint')}
                            </p>

                            {/* Telegram Tutorial */}
                            <details className="text-xs">
                                <summary className="cursor-pointer text-primary hover:underline">
                                    {tr('subscription.telegram.tutorial')}
                                </summary>
                                <div className="mt-2 p-3 rounded-lg bg-muted/50 space-y-1.5 text-muted-foreground">
                                    <p>{tr('subscription.telegram.tutorialStep1')}</p>
                                    <p>{tr('subscription.telegram.tutorialStep2')}</p>
                                    <p>{tr('subscription.telegram.tutorialStep3')}</p>
                                    <p>{tr('subscription.telegram.tutorialStep4')}</p>
                                </div>
                            </details>

                            <div className="flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    id="telegram-enabled"
                                    checked={telegramEnabled}
                                    onChange={(e) => setTelegramEnabled(e.target.checked)}
                                    className="h-4 w-4 rounded border-border"
                                />
                                <label htmlFor="telegram-enabled" className="text-sm">
                                    {tr('subscription.telegram.enable')}
                                </label>
                            </div>

                            <div className="grid gap-2">
                                <label className="text-sm">{tr('subscription.telegram.botToken')}</label>
                                <Input
                                    type="password"
                                    placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                                    value={telegramBotToken}
                                    onChange={(e) => setTelegramBotToken(e.target.value)}
                                    disabled={!telegramEnabled}
                                />
                            </div>

                            <div className="grid gap-2">
                                <label className="text-sm">{tr('subscription.telegram.chatId')}</label>
                                <Input
                                    type="text"
                                    placeholder="-1001234567890"
                                    value={telegramChatId}
                                    onChange={(e) => setTelegramChatId(e.target.value)}
                                    disabled={!telegramEnabled}
                                />
                            </div>

                            <Button
                                variant="outline"
                                onClick={handleTestTelegram}
                                disabled={!telegramEnabled || testingTelegram || !telegramBotToken || !telegramChatId}
                            >
                                {testingTelegram ? (
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                ) : (
                                    <Send className="h-4 w-4 mr-2" />
                                )}
                                {tr('subscription.telegram.test')}
                            </Button>
                        </div>
                    </div>

                    {/* Save Button */}
                    <div className="border-t border-border pt-4">
                        <Button onClick={handleSaveConfig} disabled={configLoading}>
                            {tr('common.saveConfig')}
                        </Button>
                    </div>
                </Card>
            )}

            {/* Subscription List */}
            <div className="space-y-4">
                <div className="flex items-center justify-between gap-4">
                    <h3 className="flex items-center gap-2 text-base font-medium">
                        {tr('subscription.list')}
                        <span className="text-sm text-muted-foreground">({subscriptions.length})</span>
                    </h3>
                    <button
                        type="button"
                        aria-label={clearing ? tr('subscription.clearing') : tr('subscription.clearAll')}
                        title={clearing ? tr('subscription.clearing') : tr('subscription.clearAll')}
                        disabled={clearing || subscriptions.length === 0}
                        onClick={handleClearAll}
                        className={cn(
                            'inline-flex h-9 w-9 items-center justify-center text-muted-foreground hover:text-foreground',
                            'disabled:cursor-not-allowed disabled:opacity-50'
                        )}
                    >
                        <BrushCleaningIcon
                            className={cn(
                                'h-5 w-5 mr-banana-broom',
                                (clearing || broomAnim.sweeping) ? 'mr-banana-broom--sweep' : ''
                            )}
                        />
                    </button>
                </div>

                <Card className="overflow-hidden">
                    <div className="p-4 space-y-3">
                        {loading ? (
                            <div className="flex items-center justify-center py-8">
                                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                            </div>
                        ) : subscriptions.length === 0 ? (
                            <EmptyState
                                type="subscription"
                                title={tr('subscription.empty')}
                                description={tr('subscription.emptyHint')}
                            />
                        ) : (
                            subscriptions.map((item) => (
                                <SubscriptionItem
                                    key={item.id}
                                    item={item}
                                    tr={tr}
                                    onDelete={handleDelete}
                                    onMarkRead={handleMarkRead}
                                    onCheck={handleCheckSingle}
                                    checking={checkingId}
                                />
                            ))
                        )}
                    </div>
                </Card>
            </div>
        </div>
    );
}

export default SubscriptionTab;
