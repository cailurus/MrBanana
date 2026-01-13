/**
 * ScrapeSettingsPanel - Settings panel for scrape configuration
 * Contains 8 advanced tabs: trigger, naming, download, nfo, translation, concurrency, network, sources
 */
import React from 'react';
import { AlertCircle, ChevronDown } from 'lucide-react';
import { Card, Input, Select, Button, cn } from '../../ui';
import { InfoTooltip } from '../../InfoTooltip';
import { useScrapeStore } from '../../../stores/scrapeStore';

// Advanced tab definitions
const ADVANCED_TABS = [
    { key: 'trigger', labelKey: 'common.section.trigger' },
    { key: 'naming', labelKey: 'common.section.naming' },
    { key: 'download', labelKey: 'common.section.download' },
    { key: 'nfo', labelKey: 'common.section.nfo' },
    { key: 'translation', labelKey: 'common.section.translation' },
    { key: 'concurrency', labelKey: 'common.section.concurrency' },
    { key: 'network', labelKey: 'common.section.network' },
    { key: 'sources', labelKey: 'common.section.sources' },
];

// Source field definitions for the sources tab (read-only, not user-configurable)
// Note: Only JavTrailers is used for most fields, DMM for plot
const SOURCE_FIELD_DEFS = [
    { titleKey: 'scrape.field.title', key: 'scrape_sources_title', order: ['javtrailers'] },
    { titleKey: 'scrape.field.plot', key: 'scrape_sources_plot', order: ['dmm'] },
    { titleKey: 'scrape.field.actors', key: 'scrape_sources_actors', order: ['javtrailers'] },
    { titleKey: 'scrape.field.fanart', key: 'scrape_sources_fanart', order: ['javtrailers'] },
    { titleKey: 'scrape.field.poster', key: 'scrape_sources_poster', order: ['javtrailers'] },
    { titleKey: 'scrape.field.previews', key: 'scrape_sources_previews', order: ['javtrailers'] },
    { titleKey: 'scrape.field.trailer', key: 'scrape_sources_trailer', order: ['javtrailers'] },
    { titleKey: 'scrape.field.tags', key: 'scrape_sources_tags', order: ['javtrailers'] },
    { titleKey: 'scrape.field.release', key: 'scrape_sources_release', order: ['javtrailers'] },
    { titleKey: 'scrape.field.runtime', key: 'scrape_sources_runtime', order: ['javtrailers'] },
    { titleKey: 'scrape.field.studio', key: 'scrape_sources_studio', order: ['javtrailers'] },
];

// Source info mapping for tooltip display - which fields each source provides
const SOURCE_INFO = {
    subtitlecat: ['scrape.download.subtitle'],
    dmm: ['scrape.field.plot'],
    javtrailers: ['scrape.field.title', 'scrape.field.actors', 'scrape.field.fanart', 'scrape.field.poster', 'scrape.field.previews', 'scrape.field.trailer', 'scrape.field.tags', 'scrape.field.release', 'scrape.field.runtime', 'scrape.field.studio'],
};

// Available sources for testing (simplified - removed javdb, javbus, theporndb, jav321)
const AVAILABLE_SOURCES = ['subtitlecat', 'dmm', 'javtrailers'];

/**
 * TriggerTab - Trigger mode settings
 */
function TriggerTab({ tr }) {
    const config = useScrapeStore((s) => s.config);
    const setConfig = useScrapeStore((s) => s.setConfig);

    return (
        <div className="space-y-3">
            <label className="grid gap-2 text-sm max-w-sm">
                {tr('scrape.trigger.mode')}
                <Select
                    value={config.scrape_trigger_mode || 'manual'}
                    onChange={(e) => setConfig({ scrape_trigger_mode: e.target.value })}
                >
                    <option value="manual">{tr('scrape.trigger.manual')}</option>
                    <option value="interval">{tr('scrape.trigger.interval')}</option>
                    <option value="watch">{tr('scrape.trigger.watch')}</option>
                </Select>
            </label>

            {String(config.scrape_trigger_mode || 'manual') === 'interval' && (
                <label className="grid gap-2 text-sm max-w-sm">
                    {tr('scrape.trigger.intervalMinutes')}
                    <Input
                        type="number"
                        min={1}
                        value={Math.max(1, Math.round(Number(config.scrape_trigger_interval_sec || 3600) / 60))}
                        onChange={(e) => {
                            const minutes = Math.max(1, Number(e.target.value || 1));
                            setConfig({ scrape_trigger_interval_sec: Math.round(minutes * 60) });
                        }}
                    />
                </label>
            )}

            {String(config.scrape_trigger_mode || 'manual') === 'watch' && (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <label className="grid gap-2 text-sm">
                        {tr('scrape.trigger.pollSec')}
                        <Input
                            type="number"
                            min={2}
                            step="1"
                            value={Number(config.scrape_trigger_watch_poll_sec ?? 10)}
                            onChange={(e) => setConfig({ scrape_trigger_watch_poll_sec: Number(e.target.value || 10) })}
                        />
                    </label>
                    <label className="grid gap-2 text-sm">
                        {tr('scrape.trigger.quietSec')}
                        <Input
                            type="number"
                            min={5}
                            step="1"
                            value={Number(config.scrape_trigger_watch_quiet_sec ?? 30)}
                            onChange={(e) => setConfig({ scrape_trigger_watch_quiet_sec: Number(e.target.value || 30) })}
                        />
                    </label>
                    <label className="grid gap-2 text-sm md:col-span-2">
                        <div className="flex items-center gap-2">
                            <div>{tr('scrape.trigger.minAgeSec')}</div>
                            <InfoTooltip
                                text={tr('scrape.trigger.watchNote', {
                                    sec: String(config.scrape_trigger_watch_min_age_sec ?? 300),
                                })}
                            />
                        </div>
                        <Input
                            type="number"
                            min={0}
                            step="1"
                            value={Number(config.scrape_trigger_watch_min_age_sec ?? 300)}
                            onChange={(e) => setConfig({ scrape_trigger_watch_min_age_sec: Number(e.target.value || 0) })}
                        />
                    </label>
                </div>
            )}
        </div>
    );
}

/**
 * NamingTab - File naming and structure settings
 */
function NamingTab({ tr }) {
    const config = useScrapeStore((s) => s.config);
    const setConfig = useScrapeStore((s) => s.setConfig);

    return (
        <div className="space-y-3">
            <div className="grid gap-3">
                <div className="flex items-center gap-2 text-sm">
                    <div>{tr('scrape.naming.structure')}</div>
                    <InfoTooltip text={tr('scrape.naming.varsHint')} />
                </div>
                <Input
                    placeholder={tr('scrape.naming.structurePlaceholder')}
                    value={config.scrape_structure || ''}
                    onChange={(e) => setConfig({ scrape_structure: e.target.value })}
                />
            </div>

            <label className="flex items-center gap-2 text-sm">
                <input
                    type="checkbox"
                    checked={Boolean(config.scrape_rename)}
                    onChange={(e) => setConfig({ scrape_rename: e.target.checked })}
                />
                {tr('scrape.naming.renameToCode')}
            </label>

            <label className="grid gap-2 text-sm max-w-sm">
                <div className="flex items-center gap-2">
                    <div>{tr('scrape.naming.sourceHandling')}</div>
                    <InfoTooltip text={tr('scrape.naming.source.hint')} />
                </div>
                <Select
                    value={Boolean(config.scrape_copy_source) ? 'copy' : 'move'}
                    onChange={(e) => setConfig({ scrape_copy_source: e.target.value === 'copy' })}
                >
                    <option value="copy">{tr('scrape.naming.source.copy')}</option>
                    <option value="move">{tr('scrape.naming.source.move')}</option>
                </Select>
            </label>

            <label className="grid gap-2 text-sm max-w-sm">
                <div className="flex items-center gap-2">
                    <div>{tr('scrape.naming.existingAction')}</div>
                    <InfoTooltip text={tr('scrape.naming.existing.hint')} />
                </div>
                <Select
                    value={String(config.scrape_existing_action || 'skip')}
                    onChange={(e) => setConfig({ scrape_existing_action: e.target.value })}
                >
                    <option value="skip">{tr('scrape.naming.existing.skip')}</option>
                    <option value="overwrite">{tr('scrape.naming.existing.overwrite')}</option>
                </Select>
            </label>
        </div>
    );
}

/**
 * DownloadTab - Download options for artwork/media
 */
function DownloadOptionsTab({ tr }) {
    const config = useScrapeStore((s) => s.config);
    const setConfig = useScrapeStore((s) => s.setConfig);

    return (
        <div className="space-y-3">
            <div className="flex flex-wrap gap-6">
                <label className="flex items-center gap-2 text-sm">
                    <input
                        type="checkbox"
                        checked={Boolean(config.scrape_download_poster)}
                        onChange={(e) => setConfig({ scrape_download_poster: e.target.checked })}
                    />
                    {tr('scrape.download.poster')}
                </label>
                <label className="flex items-center gap-2 text-sm">
                    <input
                        type="checkbox"
                        checked={Boolean(config.scrape_download_fanart)}
                        onChange={(e) => setConfig({ scrape_download_fanart: e.target.checked })}
                    />
                    {tr('scrape.download.fanart')}
                </label>
                <label className="flex items-center gap-2 text-sm">
                    <input
                        type="checkbox"
                        checked={Boolean(config.scrape_download_previews)}
                        onChange={(e) => setConfig({ scrape_download_previews: e.target.checked })}
                    />
                    {tr('scrape.download.previews')}
                </label>
                <label className="flex items-center gap-2 text-sm">
                    <input
                        type="checkbox"
                        checked={Boolean(config.scrape_download_trailer)}
                        onChange={(e) => setConfig({ scrape_download_trailer: e.target.checked })}
                    />
                    {tr('scrape.download.trailer')}
                </label>
                <label className="flex items-center gap-2 text-sm">
                    <input
                        type="checkbox"
                        checked={Boolean(config.scrape_download_subtitle)}
                        onChange={(e) => setConfig({ scrape_download_subtitle: e.target.checked })}
                    />
                    {tr('scrape.download.subtitle')}
                </label>
            </div>

            <label className="grid gap-2 text-sm max-w-xs">
                {tr('scrape.download.previewLimit')}
                <Input
                    type="number"
                    min={0}
                    value={config.scrape_preview_limit ?? 8}
                    onChange={(e) => setConfig({ scrape_preview_limit: Number(e.target.value || 0) })}
                />
            </label>
        </div>
    );
}

/**
 * NfoTab - NFO generation settings
 */
function NfoTab({ tr }) {
    const config = useScrapeStore((s) => s.config);
    const setConfig = useScrapeStore((s) => s.setConfig);

    return (
        <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm">
                <input
                    type="checkbox"
                    checked={Boolean(config.scrape_write_nfo)}
                    onChange={(e) => setConfig({ scrape_write_nfo: e.target.checked })}
                />
                {tr('scrape.nfo.generate')}
                <InfoTooltip text={`${tr('scrape.nfo.fields')} ${tr('scrape.nfo.fieldsHint')}`.trim()} />
            </label>
            <div className="flex flex-wrap gap-6">
                {(config.scrape_nfo_fields || []).map((f) => (
                    <span key={f} className="text-xs rounded-md border px-2 py-1 text-muted-foreground">
                        {f}
                    </span>
                ))}
            </div>
        </div>
    );
}

/**
 * TranslationTab - Translation settings
 */
function TranslationTab({ tr }) {
    const config = useScrapeStore((s) => s.config);
    const setConfig = useScrapeStore((s) => s.setConfig);

    return (
        <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm">
                <input
                    type="checkbox"
                    checked={Boolean(config.scrape_translate_enabled)}
                    onChange={(e) => setConfig({ scrape_translate_enabled: e.target.checked })}
                />
                {tr('scrape.translation.enable')}
            </label>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <label className="grid gap-2 text-sm">
                    {tr('scrape.translation.outputLang')}
                    <Select
                        value={config.scrape_translate_target_lang || 'zh-CN'}
                        onChange={(e) => setConfig({ scrape_translate_target_lang: e.target.value })}
                        disabled={!Boolean(config.scrape_translate_enabled)}
                    >
                        <option value="zh-CN">{tr('scrape.translation.lang.zhCN')}</option>
                        <option value="zh-TW">{tr('scrape.translation.lang.zhTW')}</option>
                        <option value="en">{tr('scrape.translation.lang.en')}</option>
                    </Select>
                </label>
                <label className="grid gap-2 text-sm">
                    {tr('scrape.translation.api')}
                    <Select
                        value={config.scrape_translate_provider || 'google'}
                        onChange={(e) => setConfig({ scrape_translate_provider: e.target.value })}
                        disabled={!Boolean(config.scrape_translate_enabled)}
                    >
                        <option value="google">{tr('scrape.translation.provider.google')}</option>
                        <option value="microsoft">{tr('scrape.translation.provider.microsoft')}</option>
                        <option value="deepl">{tr('scrape.translation.provider.deepl')}</option>
                    </Select>
                </label>
            </div>

            {Boolean(config.scrape_translate_enabled) &&
                String(config.scrape_translate_provider || 'google') === 'deepl' && (
                    <label className="grid gap-2 text-sm max-w-xl">
                        {tr('scrape.translation.deeplKey')}
                        <Input
                            type="password"
                            placeholder={tr('scrape.translation.deeplPlaceholder')}
                            value={config.scrape_translate_api_key || ''}
                            onChange={(e) => setConfig({ scrape_translate_api_key: e.target.value })}
                        />
                    </label>
                )}
        </div>
    );
}

/**
 * ConcurrencyTab - Thread and delay settings
 */
function ConcurrencyTab({ tr }) {
    const config = useScrapeStore((s) => s.config);
    const setConfig = useScrapeStore((s) => s.setConfig);

    return (
        <div className="space-y-3">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <label className="grid gap-2 text-sm">
                    {tr('scrape.concurrency.threads')}
                    <Input
                        type="number"
                        min={1}
                        value={config.scrape_threads ?? 1}
                        onChange={(e) => setConfig({ scrape_threads: Number(e.target.value || 1) })}
                    />
                </label>
                <label className="grid gap-2 text-sm">
                    {tr('scrape.concurrency.delay')}
                    <Input
                        type="number"
                        min={0}
                        step="0.1"
                        value={config.scrape_thread_delay_sec ?? 0}
                        onChange={(e) => setConfig({ scrape_thread_delay_sec: Number(e.target.value || 0) })}
                    />
                </label>
            </div>
        </div>
    );
}

/**
 * NetworkTab - Proxy settings
 */
function NetworkTab({ tr }) {
    const config = useScrapeStore((s) => s.config);
    const setConfig = useScrapeStore((s) => s.setConfig);

    return (
        <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm">
                <input
                    type="checkbox"
                    checked={Boolean(config.scrape_use_proxy)}
                    onChange={(e) => setConfig({ scrape_use_proxy: e.target.checked })}
                />
                {tr('scrape.network.useProxy')}
            </label>
            {Boolean(config.scrape_use_proxy) && (
                <div className="grid gap-2 max-w-md">
                    <div className="flex items-center gap-2">
                        <div className="text-sm">{tr('scrape.network.proxyUrl')}</div>
                        <InfoTooltip text={tr('scrape.network.proxyHint')} />
                    </div>
                    <Input
                        placeholder={tr('common.placeholder.proxyUrl')}
                        value={config.scrape_proxy_url || ''}
                        onChange={(e) => setConfig({ scrape_proxy_url: e.target.value })}
                    />
                </div>
            )}
        </div>
    );
}

/**
 * SourcesTab - Data source configuration (read-only display with test buttons)
 */
function SourcesTab({ tr }) {
    const sourceTestState = useScrapeStore((s) => s.sourceTestState);
    const testSource = useScrapeStore((s) => s.testSource);

    const sourceLabel = (sourceId) => {
        const key = `scrape.source.${String(sourceId || '')}`;
        const v = tr(key);
        return v && v !== key ? v : String(sourceId || '');
    };

    // Build tooltip text showing which fields this source provides
    const getSourceInfoTooltip = (sourceId) => {
        const fields = SOURCE_INFO[sourceId] || [];
        if (fields.length === 0) return '';
        const fieldNames = fields.map((f) => tr(f)).join('、');
        return `${tr('scrape.sources.providesFields')}: ${fieldNames}`;
    };

    return (
        <div className="space-y-3">
            <div className="grid grid-cols-1 gap-4">
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <div className="text-sm font-medium">{tr('scrape.sources')}</div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {AVAILABLE_SOURCES.map((s) => {
                            const st = sourceTestState?.[s]?.status || 'idle';
                            const dot =
                                st === 'ok'
                                    ? 'bg-green-500'
                                    : st === 'fail'
                                        ? 'bg-red-500'
                                        : st === 'testing'
                                            ? 'bg-yellow-500'
                                            : 'bg-muted';
                            const hint =
                                st === 'ok'
                                    ? `${sourceTestState?.[s]?.statusCode || ''} ${sourceTestState?.[s]?.elapsedMs || ''}ms`.trim()
                                    : st === 'fail'
                                        ? tr('status.scrape.Failed')
                                        : st === 'testing'
                                            ? tr('common.processing')
                                            : '';
                            const infoTooltip = getSourceInfoTooltip(s);
                            return (
                                <div key={s} className="flex items-center gap-2 rounded-md border px-2 py-1 text-sm">
                                    <span className={`h-2 w-2 rounded-full ${dot}`} />
                                    <span>{sourceLabel(s)}</span>
                                    {infoTooltip ? <InfoTooltip text={infoTooltip} /> : null}
                                    {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
                                    <Button
                                        type="button"
                                        size="sm"
                                        variant="outline"
                                        disabled={st === 'testing'}
                                        onClick={() => testSource(s)}
                                    >
                                        test
                                    </Button>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
}

/**
 * Main ScrapeSettingsPanel component
 */
export function ScrapeSettingsPanel({
    tr,
    dirPickerField,
    onPickScrapeDir,
    onPickScrapeOutputDir,
}) {
    const config = useScrapeStore((s) => s.config);
    const loading = useScrapeStore((s) => s.loading);
    const configSaving = useScrapeStore((s) => s.configSaving);
    const showAdvanced = useScrapeStore((s) => s.showAdvanced);
    const advancedTab = useScrapeStore((s) => s.advancedTab);
    const toggleAdvanced = useScrapeStore((s) => s.toggleAdvanced);
    const setAdvancedTab = useScrapeStore((s) => s.setAdvancedTab);

    const scrapeInputDirEmpty = !String(config.scrape_dir || '').trim();
    const scrapeOutputDirEmpty = !String(config.scrape_output_dir || '').trim();

    return (
        <Card className="p-6 space-y-5">
            <div className="space-y-3">
                <div className="grid gap-2">
                    <div className="flex items-center gap-2 text-sm">
                        <span>{tr('scrape.settings.scanDir')}</span>
                        {scrapeInputDirEmpty ? <AlertCircle className="h-4 w-4 text-red-500" /> : null}
                    </div>
                    <Input
                        placeholder={tr('common.chooseDir')}
                        value={config.scrape_dir || ''}
                        readOnly
                        disabled={Boolean(dirPickerField) || loading || configSaving}
                        onClick={onPickScrapeDir}
                    />
                </div>

                <div className="grid gap-2">
                    <div className="flex items-center gap-2 text-sm">
                        <span>{tr('scrape.settings.outputDir')}</span>
                        {scrapeOutputDirEmpty ? <AlertCircle className="h-4 w-4 text-red-500" /> : null}
                    </div>
                    <Input
                        placeholder={tr('common.chooseDir')}
                        value={config.scrape_output_dir || ''}
                        readOnly
                        disabled={Boolean(dirPickerField) || loading || configSaving}
                        onClick={onPickScrapeOutputDir}
                    />
                </div>
            </div>

            {showAdvanced && (
                <>
                    <div className="space-y-3">
                        <div className="flex flex-wrap items-center gap-2">
                            {ADVANCED_TABS.map((it) => (
                                <button
                                    key={it.key}
                                    type="button"
                                    onClick={() => setAdvancedTab(it.key)}
                                    className={cn(
                                        'rounded-md border px-2 py-1 text-xs',
                                        advancedTab === it.key
                                            ? 'bg-muted text-foreground'
                                            : 'bg-transparent text-muted-foreground hover:text-foreground'
                                    )}
                                >
                                    {tr(it.labelKey)}
                                </button>
                            ))}
                        </div>

                        {advancedTab === 'trigger' && <TriggerTab tr={tr} />}
                        {advancedTab === 'naming' && <NamingTab tr={tr} />}
                        {advancedTab === 'download' && <DownloadOptionsTab tr={tr} />}
                        {advancedTab === 'nfo' && <NfoTab tr={tr} />}
                        {advancedTab === 'translation' && <TranslationTab tr={tr} />}
                        {advancedTab === 'concurrency' && <ConcurrencyTab tr={tr} />}
                        {advancedTab === 'network' && <NetworkTab tr={tr} />}
                        {advancedTab === 'sources' && <SourcesTab tr={tr} />}
                    </div>
                </>
            )}

            <div className="flex justify-center pt-1">
                <button
                    type="button"
                    aria-label={tr('common.advanced')}
                    title={tr('common.advanced')}
                    onClick={toggleAdvanced}
                    className={cn(
                        'inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground transition-transform',
                        !showAdvanced && 'mr-banana-chevron-hint'
                    )}
                >
                    <ChevronDown className={cn('h-4 w-4 transition-transform', showAdvanced ? 'rotate-180' : '')} />
                </button>
            </div>
        </Card>
    );
}

export default ScrapeSettingsPanel;
