/**
 * Subscription Store - manages subscription-related state
 */
import { create } from 'zustand';
import axios from 'axios';

export const useSubscriptionStore = create((set, get) => ({
    // Subscription list
    subscriptions: [],
    loading: false,

    // Config
    config: {
        checkIntervalDays: 1,
        lastAutoCheckAt: null,
        telegramBotToken: '',
        telegramChatId: '',
        telegramEnabled: false,
    },
    configLoading: false,

    // Fetch subscriptions
    fetchSubscriptions: async () => {
        set({ loading: true });
        try {
            const res = await axios.get('/api/subscription');
            set({ subscriptions: Array.isArray(res.data) ? res.data : [] });
        } catch (err) {
            console.error('Failed to fetch subscriptions', err);
            set({ subscriptions: [] });
        } finally {
            set({ loading: false });
        }
    },

    // Add subscription
    addSubscription: async (code, magnetLinks = []) => {
        try {
            await axios.post('/api/subscription', {
                code,
                magnet_links: magnetLinks,
            });
            await get().fetchSubscriptions();
            return { success: true };
        } catch (err) {
            if (err.response?.status === 409) {
                return { success: false, error: 'already_exists' };
            }
            throw err;
        }
    },

    // Remove subscription
    removeSubscription: async (id) => {
        try {
            await axios.delete(`/api/subscription/${id}`);
            await get().fetchSubscriptions();
        } catch (err) {
            console.error('Failed to remove subscription', err);
            throw err;
        }
    },

    // Mark as read
    markAsRead: async (id) => {
        try {
            await axios.post(`/api/subscription/${id}/mark-read`);
            await get().fetchSubscriptions();
        } catch (err) {
            console.error('Failed to mark as read', err);
            throw err;
        }
    },

    // Check all updates
    checkAllUpdates: async () => {
        try {
            await axios.post('/api/subscription/check');
        } catch (err) {
            console.error('Failed to check updates', err);
            throw err;
        }
    },

    // Check single subscription
    checkSingleUpdate: async (id) => {
        try {
            const res = await axios.post(`/api/subscription/${id}/check`);
            await get().fetchSubscriptions();
            return res.data;
        } catch (err) {
            console.error('Failed to check subscription', err);
            throw err;
        }
    },

    // Fetch config
    fetchConfig: async () => {
        set({ configLoading: true });
        try {
            const res = await axios.get('/api/subscription/config');
            set({
                config: {
                    checkIntervalDays: res.data.check_interval_days || 1,
                    lastAutoCheckAt: res.data.last_auto_check_at,
                    telegramBotToken: res.data.telegram_bot_token || '',
                    telegramChatId: res.data.telegram_chat_id || '',
                    telegramEnabled: res.data.telegram_enabled || false,
                },
            });
        } catch (err) {
            console.error('Failed to fetch subscription config', err);
        } finally {
            set({ configLoading: false });
        }
    },

    // Update config
    updateConfig: async (configData) => {
        try {
            await axios.post('/api/subscription/config', configData);
            await get().fetchConfig();
        } catch (err) {
            console.error('Failed to update subscription config', err);
            throw err;
        }
    },

    // Test Telegram
    testTelegram: async () => {
        try {
            const res = await axios.post('/api/subscription/telegram/test');
            return res.data;
        } catch (err) {
            console.error('Failed to test telegram', err);
            throw err;
        }
    },

    // Clear all
    clearAll: async () => {
        try {
            await axios.post('/api/subscription/clear');
            set({ subscriptions: [] });
        } catch (err) {
            console.error('Failed to clear subscriptions', err);
            throw err;
        }
    },
}));

export default useSubscriptionStore;
