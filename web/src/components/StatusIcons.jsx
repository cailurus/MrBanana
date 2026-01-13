import React from 'react';
import { Activity, AlertCircle, CheckCircle2, Clock, Pause } from 'lucide-react';
import { t } from '../i18n';

/**
 * Get download status label
 * @param {string} status - Status string
 * @param {string} lang - Language code
 * @returns {string} Localized status label
 */
export function getStatusLabel(status, lang = 'zh-CN') {
    return (
        {
            Preparing: t(lang, 'status.download.Preparing'),
            Queued: t(lang, 'status.download.Queued'),
            Downloading: t(lang, 'status.download.Downloading'),
            Paused: t(lang, 'status.download.Paused'),
            Merging: t(lang, 'status.download.Merging'),
            Completed: t(lang, 'status.download.Completed'),
            Failed: t(lang, 'status.download.Failed'),
        }[status] || status || t(lang, 'common.none')
    );
}

/**
 * Get scrape status label
 * @param {string} status - Status string
 * @param {string} lang - Language code
 * @returns {string} Localized status label
 */
export function getScrapeStatusLabel(status, lang = 'zh-CN') {
    return (
        {
            Pending: t(lang, 'status.scrape.Pending'),
            Starting: t(lang, 'status.scrape.Starting'),
            Running: t(lang, 'status.scrape.Running'),
            Completed: t(lang, 'status.scrape.Completed'),
            Failed: t(lang, 'status.scrape.Failed'),
        }[status] || status || t(lang, 'common.none')
    );
}

/**
 * Status icon for download tasks
 */
export function StatusIcon({ status, error }) {
    if (status === 'Completed') return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    if (status === 'Failed') {
        const msg = typeof error === 'string' ? error.trim() : '';
        return <AlertCircle className="h-5 w-5 text-red-500 cursor-help" title={msg || 'Failed'} />;
    }
    if (status === 'Downloading') return <Activity className="h-5 w-5 text-blue-500 animate-pulse" />;
    if (status === 'Paused') return <Pause className="h-5 w-5 text-yellow-600" />;
    return <Clock className="h-5 w-5 text-gray-500" />;
}

/**
 * Status icon for scrape tasks
 */
export function ScrapeStatusIcon({ status }) {
    if (status === 'Completed') return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    if (status === 'Failed') return <AlertCircle className="h-5 w-5 text-red-500" />;
    if (status === 'Running' || status === 'Starting') return <Activity className="h-5 w-5 text-blue-500 animate-pulse" />;
    return <Clock className="h-5 w-5 text-gray-500" />;
}
