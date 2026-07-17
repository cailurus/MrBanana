/**
 * SubscriptionTab - Jable.tv liked/watch-later with login
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Heart, Clock, Download, RefreshCw, Loader2, Key, LogOut } from 'lucide-react';
import { Button, Card, Input, cn } from '../ui';
import { useToast } from '../Toast';
import { EmptyState } from '../EmptyState';

const PLACEHOLDER_IMG = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjI4MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjI4MCIgZmlsbD0iIzJhMmEyYSIvPjx0ZXh0IHg9IjEwMCIgeT0iMTQwIiBmb250LXNpemU9IjE0IiBmaWxsPSIjNjY2IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmb250LWZhbWlseT0iQXJpYWwiPuWbvueJh+acqueMhTwvdGV4dD48L3N2Zz4=';

export function SubscriptionTab() {
    const toast = useToast();

    // Local state: jable login status
    const [loggedIn, setLoggedIn] = useState(false);
    const [jableUser, setJableUser] = useState('');
    const [loading, setLoading] = useState(false);
    const [liked, setLiked] = useState([]);
    const [watchLater, setWatchLater] = useState([]);
    const [activeTab, setActiveTab] = useState('watch_later');
    const [downloadingAll, setDownloadingAll] = useState(false);
    const [downloadingIds, setDownloadingIds] = useState(new Set());

    // Login modal state
    const [showLoginModal, setShowLoginModal] = useState(false);
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [loggingIn, setLoggingIn] = useState(false);

    // Check login status on mount
    useEffect(() => {
        axios.get('/api/jable/status').then(r => {
            if (r.data.logged_in) {
                setLoggedIn(true);
                setJableUser(r.data.username || '');
            }
        }).catch(() => {});
    }, []);

    // Fetch lists when logged in
    const fetchLists = async () => {
        setLoading(true);
        try {
            const res = await axios.get('/api/jable/lists');
            setLiked(res.data.liked || []);
            setWatchLater(res.data.watch_later || []);
        } catch (err) {
            toast.error('获取列表失败: ' + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    // Auto-fetch after login
    useEffect(() => {
        if (loggedIn) fetchLists();
    }, [loggedIn]);

    const handleLogin = async (e) => {
        e.preventDefault();
        if (!username || !password) { toast.warning('请输入用户名和密码'); return; }
        setLoggingIn(true);
        try {
            const res = await axios.post('/api/jable/login', { username, password });
            toast.success(res.data.message);
            setLoggedIn(true);
            setJableUser(res.data.username || '');
            setShowLoginModal(false);
            setUsername('');
            setPassword('');
            setTimeout(() => fetchLists(), 500);
        } catch (err) {
            toast.error('登录失败: ' + (err.response?.data?.detail || err.message));
        } finally {
            setLoggingIn(false);
        }
    };

    const handleLogout = async () => {
        try {
            await axios.post('/api/jable/logout');
            setLoggedIn(false);
            setJableUser('');
            setLiked([]);
            setWatchLater([]);
            toast.success('已登出');
        } catch (err) {
            toast.error('登出失败');
        }
    };

    const items = activeTab === 'liked' ? liked : watchLater;

    const handleDownloadSingle = async (code) => {
        const dlRes = await axios.get('/api/download/config');
        const out = String(dlRes.data.output_dir || '').trim();
        if (!out) { toast.error('请先在下载设置中配置输出目录'); return; }
        setDownloadingIds(prev => new Set([...prev, code]));
        try {
            const res = await axios.post('/api/jable/batch-download', { codes: [code], output_dir: out });
            if (res.data.added > 0) toast.success(`已添加 ${code}`);
            else if (res.data.skipped.includes(code)) toast.info(`${code} 已存在`);
        } catch (err) {
            toast.error(`添加失败: ${err.response?.data?.detail || err.message}`);
        } finally {
            setDownloadingIds(prev => { const next = new Set(prev); next.delete(code); return next; });
        }
    };

    const handleDownloadAll = async () => {
        const dlRes = await axios.get('/api/download/config');
        const out = String(dlRes.data.output_dir || '').trim();
        if (!out) { toast.error('请先在下载设置中配置输出目录'); return; }
        if (items.length === 0) return;
        setDownloadingAll(true);
        try {
            const res = await axios.post('/api/jable/batch-download', { codes: items.map(i => i.code), output_dir: out });
            if (res.data.added > 0) toast.success(`已添加 ${res.data.added} 个下载任务`);
            if (res.data.skipped.length > 0) toast.info(`跳过 ${res.data.skipped.length} 个重复`);
            if (res.data.errors.length > 0) toast.error(`失败: ${res.data.errors.join('; ')}`);
        } catch (err) {
            toast.error('批量下载失败: ' + (err.response?.data?.detail || err.message));
        } finally {
            setDownloadingAll(false);
        }
    };

    return (
        <div className="space-y-4">
            {/* Login / Logout bar */}
            {!loggedIn ? (
                <Card className="p-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h3 className="text-sm font-medium">Jable.tv 账户</h3>
                            <p className="text-xs text-muted-foreground mt-1">登录后可查看影片收藏和稍后观看列表</p>
                        </div>
                        <Button onClick={() => setShowLoginModal(true)}>
                            <Key className="h-4 w-4 mr-2" />登录 Jable.tv
                        </Button>
                    </div>
                </Card>
            ) : (
                <Card className="p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-sm">
                            <Heart className="h-4 w-4 text-primary" />
                            已登录: <span className="font-medium">{jableUser}</span>
                        </div>
                        <button type="button" onClick={handleLogout}
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10">
                            <LogOut className="h-3.5 w-3.5" />登出
                        </button>
                    </div>
                </Card>
            )}

            {/* Header */}
            <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                    <Heart className="h-5 w-5 text-primary" />
                    {loggedIn ? `Jable.tv ${activeTab === 'liked' ? '影片收藏' : '稍后观看'}` : 'Jable.tv'}
                </h2>
                <div className="flex items-center gap-2">
                    {loggedIn && (
                        <>
                            <button type="button" onClick={fetchLists} disabled={loading}
                                className={cn('inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-sm', 'bg-primary/10 text-primary hover:bg-primary/20', 'disabled:opacity-50')}>
                                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}刷新
                            </button>
                            {items.length > 0 && (
                                <button type="button" onClick={handleDownloadAll} disabled={downloadingAll}
                                    className={cn('inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-sm', 'bg-green-500/20 text-green-600 dark:text-green-400 hover:bg-green-500/30', 'disabled:opacity-50')}>
                                    <Download className="h-4 w-4" />
                                    {downloadingAll ? '添加中...' : '下载全部'}
                                </button>
                            )}
                        </>
                    )}
                </div>
            </div>

            {/* Tab Switcher */}
            {loggedIn && (
                <div className="flex gap-1 p-1 rounded-lg bg-muted/50 w-fit">
                    <button type="button" onClick={() => setActiveTab('watch_later')}
                        className={cn('flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm transition-colors',
                            activeTab === 'watch_later' ? 'bg-card shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground')}>
                        <Clock className="h-4 w-4" />稍后观看 ({watchLater.length})
                    </button>
                    <button type="button" onClick={() => setActiveTab('liked')}
                        className={cn('flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm transition-colors',
                            activeTab === 'liked' ? 'bg-card shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground')}>
                        <Heart className="h-4 w-4" />影片收藏 ({liked.length})
                    </button>
                </div>
            )}

            {/* Content */}
            <Card className="overflow-hidden">
                <div className="p-4">
                    {!loggedIn ? (
                        <EmptyState type="subscription" title="未登录" description="点击上方按钮登录 Jable.tv" />
                    ) : loading ? (
                        <div className="flex items-center justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>
                    ) : items.length === 0 ? (
                        <EmptyState type="subscription" title={activeTab === 'liked' ? '暂无收藏' : '暂无稍后观看'} description="点击刷新获取" />
                    ) : (
                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
                            {items.map((item) => (
                                <div key={item.code} className="group relative rounded-lg border border-border/60 bg-card/50 overflow-hidden hover:shadow-lg transition-all">
                                    <div className="aspect-[2/3] bg-muted overflow-hidden relative">
                                        {item.thumbnail_url ? (
                                            <img src={item.thumbnail_url} alt={item.title || item.code} className="w-full h-full object-cover" loading="lazy"
                                                onError={(e) => { e.target.src = PLACEHOLDER_IMG; }} />
                                        ) : (
                                            <img src={PLACEHOLDER_IMG} alt="placeholder" className="w-full h-full object-cover" />
                                        )}
                                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
                                            <button type="button" onClick={() => handleDownloadSingle(item.code)} disabled={downloadingIds.has(item.code)}
                                                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-white/90 text-black text-xs font-medium hover:bg-white transition-colors disabled:opacity-50">
                                                {downloadingIds.has(item.code) ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3" />}下载
                                            </button>
                                        </div>
                                    </div>
                                    <div className="p-2">
                                        <div className="text-xs font-medium truncate" title={item.code}>{item.code}</div>
                                        {item.title && item.title !== item.code && (
                                            <div className="text-xs text-muted-foreground truncate mt-0.5" title={item.title}>{item.title}</div>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </Card>

            {/* Login Modal */}
            {showLoginModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowLoginModal(false)} />
                    <div className="relative z-10 w-full max-w-sm rounded-xl border border-border/60 bg-card/95 p-6 shadow-xl space-y-4">
                        <h3 className="text-lg font-semibold">Jable.tv 登录</h3>
                        <form onSubmit={handleLogin} className="space-y-3">
                            <div className="grid gap-1.5">
                                <label className="text-sm">用户名/邮箱</label>
                                <Input type="text" placeholder="jable.tv 用户名" value={username}
                                    onChange={e => setUsername(e.target.value)} disabled={loggingIn} autoFocus />
                            </div>
                            <div className="grid gap-1.5">
                                <label className="text-sm">密码</label>
                                <Input type="password" placeholder="jable.tv 密码" value={password}
                                    onChange={e => setPassword(e.target.value)} disabled={loggingIn} />
                            </div>
                            <div className="flex gap-2 pt-2">
                                <Button type="submit" disabled={loggingIn} className="flex-1">
                                    {loggingIn ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                                    {loggingIn ? '登录中...' : '登录'}
                                </Button>
                                <Button variant="outline" type="button" onClick={() => setShowLoginModal(false)} disabled={loggingIn}>
                                    取消
                                </Button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}

export default SubscriptionTab;