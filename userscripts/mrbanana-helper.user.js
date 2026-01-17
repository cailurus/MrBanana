// ==UserScript==
// @name         Mr. Banana Helper
// @namespace    https://github.com/cailurus/MrBanana
// @version      0.2.0
// @description  在 JavDB 和 Jable 页面添加快捷按钮，一键发送到 Mr. Banana 服务
// @author       xxm
// @match        https://javdb.com/*
// @match        https://*.javdb.com/*
// @match        https://jable.tv/videos/*
// @match        https://*.jable.tv/videos/*
// @icon         https://raw.githubusercontent.com/cailurus/MrBanana/main/web/public/favicon.svg
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @grant        GM_addStyle
// @connect      *
// @license      MIT
// @downloadURL  https://raw.githubusercontent.com/cailurus/MrBanana/main/userscripts/mrbanana-helper.user.js
// @updateURL    https://raw.githubusercontent.com/cailurus/MrBanana/main/userscripts/mrbanana-helper.user.js
// ==/UserScript==

(function () {
    'use strict';

    console.log('[MrBanana] 脚本已加载，当前页面:', window.location.href);

    // =========================================================================
    // 配置管理
    // =========================================================================
    const DEFAULT_SERVER = 'http://192.168.1.100:8000';

    function getServerUrl() {
        return GM_getValue('mrbanana_server', DEFAULT_SERVER);
    }

    function setServerUrl(url) {
        GM_setValue('mrbanana_server', url);
    }

    function getConnectionStatus() {
        return GM_getValue('mrbanana_status', null);
    }

    function setConnectionStatus(status) {
        GM_setValue('mrbanana_status', status);
    }

    // =========================================================================
    // 样式
    // =========================================================================
    GM_addStyle(`
        /* 按钮样式 */
        .mrbanana-btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        .mrbanana-btn-subscribe {
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white;
            box-shadow: 0 2px 8px rgba(245, 158, 11, 0.3);
        }
        .mrbanana-btn-subscribe:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(245, 158, 11, 0.4);
        }
        .mrbanana-btn-download {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
        }
        .mrbanana-btn-download:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
        }
        .mrbanana-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none !important;
        }
        .mrbanana-btn-success {
            background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%) !important;
        }
        .mrbanana-btn-error {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
        }

        /* Toast 通知 */
        .mrbanana-toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 8px;
            color: white;
            font-size: 14px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            z-index: 999999;
            animation: mrbanana-slide-in 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        .mrbanana-toast-success { background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); }
        .mrbanana-toast-error { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }
        .mrbanana-toast-info { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }

        @keyframes mrbanana-slide-in {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        /* 设置面板 */
        .mrbanana-settings-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(4px);
            z-index: 999998;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: mrbanana-fade-in 0.2s ease;
        }
        @keyframes mrbanana-fade-in {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        .mrbanana-settings-panel {
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            width: 420px;
            max-width: 90vw;
            overflow: hidden;
            animation: mrbanana-zoom-in 0.3s ease;
        }
        @keyframes mrbanana-zoom-in {
            from { transform: scale(0.9); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }

        .mrbanana-settings-header {
            background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
            color: white;
            padding: 20px 24px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .mrbanana-settings-header h2 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
        }
        .mrbanana-settings-header .logo {
            font-size: 28px;
        }
        .mrbanana-settings-close {
            margin-left: auto;
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            width: 32px;
            height: 32px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s;
        }
        .mrbanana-settings-close:hover {
            background: rgba(255,255,255,0.3);
        }

        .mrbanana-settings-body {
            padding: 24px;
        }

        .mrbanana-form-group {
            margin-bottom: 20px;
        }
        .mrbanana-form-label {
            display: block;
            font-size: 14px;
            font-weight: 500;
            color: #374151;
            margin-bottom: 8px;
        }
        .mrbanana-form-hint {
            font-size: 12px;
            color: #6b7280;
            margin-top: 4px;
        }
        .mrbanana-form-input {
            width: 100%;
            padding: 10px 14px;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.2s, box-shadow 0.2s;
            box-sizing: border-box;
        }
        .mrbanana-form-input:focus {
            outline: none;
            border-color: #f59e0b;
            box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.1);
        }

        .mrbanana-status-card {
            background: #f9fafb;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 20px;
        }
        .mrbanana-status-row {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .mrbanana-status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            flex-shrink: 0;
        }
        .mrbanana-status-indicator.online {
            background: #22c55e;
            box-shadow: 0 0 8px rgba(34, 197, 94, 0.5);
        }
        .mrbanana-status-indicator.offline {
            background: #ef4444;
            box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
        }
        .mrbanana-status-indicator.checking {
            background: #f59e0b;
            animation: mrbanana-pulse 1s infinite;
        }
        @keyframes mrbanana-pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .mrbanana-status-text {
            font-size: 14px;
            color: #374151;
        }
        .mrbanana-status-version {
            margin-left: auto;
            font-size: 12px;
            color: #6b7280;
            background: #e5e7eb;
            padding: 2px 8px;
            border-radius: 4px;
        }

        .mrbanana-btn-row {
            display: flex;
            gap: 12px;
        }
        .mrbanana-btn-primary {
            flex: 1;
            padding: 12px 20px;
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        .mrbanana-btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(245, 158, 11, 0.4);
        }
        .mrbanana-btn-primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .mrbanana-btn-secondary {
            flex: 1;
            padding: 12px 20px;
            background: #f3f4f6;
            color: #374151;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        .mrbanana-btn-secondary:hover {
            background: #e5e7eb;
        }
    `);

    // =========================================================================
    // 工具函数
    // =========================================================================
    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `mrbanana-toast mrbanana-toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    function createButton(text, className, onClick) {
        const btn = document.createElement('button');
        btn.className = `mrbanana-btn ${className}`;
        btn.innerHTML = `🍌 ${text}`;
        btn.onclick = onClick;
        return btn;
    }

    // =========================================================================
    // 设置面板
    // =========================================================================
    function showSettingsPanel() {
        // 移除已存在的面板
        const existing = document.querySelector('.mrbanana-settings-overlay');
        if (existing) existing.remove();

        const currentUrl = getServerUrl();
        const lastStatus = getConnectionStatus();

        const overlay = document.createElement('div');
        overlay.className = 'mrbanana-settings-overlay';
        overlay.innerHTML = `
            <div class="mrbanana-settings-panel">
                <div class="mrbanana-settings-header">
                    <span class="logo">🍌</span>
                    <h2>Mr. Banana 设置</h2>
                    <button class="mrbanana-settings-close" title="关闭">×</button>
                </div>
                <div class="mrbanana-settings-body">
                    <div class="mrbanana-status-card">
                        <div class="mrbanana-status-row">
                            <div class="mrbanana-status-indicator ${lastStatus?.online ? 'online' : 'offline'}" id="mrbanana-status-dot"></div>
                            <span class="mrbanana-status-text" id="mrbanana-status-text">
                                ${lastStatus?.online ? '服务已连接' : '服务未连接'}
                            </span>
                            <span class="mrbanana-status-version" id="mrbanana-status-version" style="${lastStatus?.version ? '' : 'display:none'}">
                                v${lastStatus?.version || ''}
                            </span>
                        </div>
                    </div>

                    <div class="mrbanana-form-group">
                        <label class="mrbanana-form-label">服务器地址</label>
                        <input type="text" class="mrbanana-form-input" id="mrbanana-server-input" 
                               value="${currentUrl}" placeholder="http://192.168.1.100:8000">
                        <div class="mrbanana-form-hint">
                            输入你部署的 Mr. Banana 服务地址，例如：<br>
                            • 本机：http://localhost:8000<br>
                            • 内网 NAS：http://192.168.1.100:8000<br>
                            • 远程服务器：https://your-domain.com
                        </div>
                    </div>

                    <div class="mrbanana-btn-row">
                        <button class="mrbanana-btn-secondary" id="mrbanana-test-btn">
                            🔍 测试连接
                        </button>
                        <button class="mrbanana-btn-primary" id="mrbanana-save-btn">
                            💾 保存设置
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        // 事件绑定
        const closeBtn = overlay.querySelector('.mrbanana-settings-close');
        const testBtn = overlay.querySelector('#mrbanana-test-btn');
        const saveBtn = overlay.querySelector('#mrbanana-save-btn');
        const input = overlay.querySelector('#mrbanana-server-input');

        // 点击遮罩关闭
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });

        closeBtn.addEventListener('click', () => overlay.remove());

        // 测试连接
        testBtn.addEventListener('click', () => {
            const url = input.value.trim().replace(/\/$/, '');
            if (!url) {
                showToast('请输入服务器地址', 'error');
                return;
            }
            testConnection(url, overlay);
        });

        // 保存设置
        saveBtn.addEventListener('click', () => {
            const url = input.value.trim().replace(/\/$/, '');
            if (!url) {
                showToast('请输入服务器地址', 'error');
                return;
            }
            setServerUrl(url);
            showToast('设置已保存');
            // 保存后自动测试
            testConnection(url, overlay);
        });

        // ESC 关闭
        const handleEsc = (e) => {
            if (e.key === 'Escape') {
                overlay.remove();
                document.removeEventListener('keydown', handleEsc);
            }
        };
        document.addEventListener('keydown', handleEsc);
    }

    function testConnection(url, overlay) {
        const statusDot = overlay.querySelector('#mrbanana-status-dot');
        const statusText = overlay.querySelector('#mrbanana-status-text');
        const statusVersion = overlay.querySelector('#mrbanana-status-version');
        const testBtn = overlay.querySelector('#mrbanana-test-btn');

        // 设置检测中状态
        statusDot.className = 'mrbanana-status-indicator checking';
        statusText.textContent = '正在连接...';
        statusVersion.style.display = 'none';
        testBtn.disabled = true;
        testBtn.textContent = '⏳ 检测中...';

        GM_xmlhttpRequest({
            method: 'GET',
            url: `${url}/api/version`,
            timeout: 10000,
            onload: function (response) {
                testBtn.disabled = false;
                testBtn.textContent = '🔍 测试连接';

                if (response.status >= 200 && response.status < 300) {
                    try {
                        const data = JSON.parse(response.responseText);
                        statusDot.className = 'mrbanana-status-indicator online';
                        statusText.textContent = '服务已连接';
                        statusVersion.textContent = `v${data.version || '?'}`;
                        statusVersion.style.display = '';
                        setConnectionStatus({ online: true, version: data.version });
                        showToast('连接成功！');
                    } catch (e) {
                        statusDot.className = 'mrbanana-status-indicator online';
                        statusText.textContent = '服务已连接（版本未知）';
                        setConnectionStatus({ online: true, version: null });
                        showToast('连接成功！');
                    }
                } else {
                    statusDot.className = 'mrbanana-status-indicator offline';
                    statusText.textContent = `连接失败 (${response.status})`;
                    setConnectionStatus({ online: false });
                    showToast(`连接失败: HTTP ${response.status}`, 'error');
                }
            },
            onerror: function (error) {
                testBtn.disabled = false;
                testBtn.textContent = '🔍 测试连接';
                statusDot.className = 'mrbanana-status-indicator offline';
                statusText.textContent = '无法连接到服务器';
                setConnectionStatus({ online: false });
                showToast('无法连接到服务器，请检查地址是否正确', 'error');
            },
            ontimeout: function () {
                testBtn.disabled = false;
                testBtn.textContent = '🔍 测试连接';
                statusDot.className = 'mrbanana-status-indicator offline';
                statusText.textContent = '连接超时';
                setConnectionStatus({ online: false });
                showToast('连接超时，请检查网络', 'error');
            }
        });
    }

    // 注册菜单命令
    GM_registerMenuCommand('⚙️ Mr. Banana 设置', showSettingsPanel);

    // =========================================================================
    // JavDB 处理
    // =========================================================================
    function handleJavDB() {
        console.log('[MrBanana] handleJavDB 开始执行');

        // JavDB 新版页面结构: h2.title.is-4 > strong:first-child (第一个是番号)
        const codeEl = document.querySelector('h2.title.is-4 > strong:first-child');
        console.log('[MrBanana] 番号元素:', codeEl);
        if (!codeEl) {
            console.log('[MrBanana] 未找到番号元素，尝试备用选择器...');
            // 尝试其他可能的选择器
            const allH2 = document.querySelectorAll('h2');
            console.log('[MrBanana] 页面上所有 h2:', allH2);
            return;
        }

        const code = codeEl.textContent.trim();
        console.log('[MrBanana] 番号:', code);
        if (!code) return;

        const titleSection = document.querySelector('h2.title.is-4');
        console.log('[MrBanana] 标题区域:', titleSection);
        if (!titleSection) return;

        if (document.querySelector('.mrbanana-javdb-btn')) {
            console.log('[MrBanana] 按钮已存在，跳过');
            return;
        }

        console.log('[MrBanana] 准备添加按钮...');

        const btn = createButton('订阅到 Mr. Banana', 'mrbanana-btn-subscribe mrbanana-javdb-btn', async () => {
            const serverUrl = getServerUrl();
            if (serverUrl === DEFAULT_SERVER) {
                showToast('请先设置 Mr. Banana 服务器地址', 'info');
                showSettingsPanel();
                return;
            }

            btn.disabled = true;
            btn.innerHTML = '🍌 订阅中...';

            GM_xmlhttpRequest({
                method: 'POST',
                url: `${serverUrl}/api/subscription`,
                headers: { 'Content-Type': 'application/json' },
                data: JSON.stringify({ code: code }),
                onload: function (response) {
                    if (response.status >= 200 && response.status < 300) {
                        btn.innerHTML = '✓ 已订阅';
                        btn.classList.add('mrbanana-btn-success');
                        showToast(`已订阅 ${code}`);
                    } else {
                        let errorMsg = '订阅失败';
                        try {
                            const data = JSON.parse(response.responseText);
                            errorMsg = data.detail || errorMsg;
                        } catch (e) { }
                        btn.innerHTML = '✗ 失败';
                        btn.classList.add('mrbanana-btn-error');
                        showToast(errorMsg, 'error');
                        setTimeout(() => {
                            btn.innerHTML = '🍌 订阅到 Mr. Banana';
                            btn.classList.remove('mrbanana-btn-error');
                            btn.disabled = false;
                        }, 2000);
                    }
                },
                onerror: function () {
                    btn.innerHTML = '✗ 连接失败';
                    btn.classList.add('mrbanana-btn-error');
                    showToast('无法连接服务器', 'error');
                    setTimeout(() => {
                        btn.innerHTML = '🍌 订阅到 Mr. Banana';
                        btn.classList.remove('mrbanana-btn-error');
                        btn.disabled = false;
                    }, 2000);
                }
            });
        });

        btn.style.marginLeft = '12px';
        titleSection.appendChild(btn);
    }

    // =========================================================================
    // Jable 处理
    // =========================================================================
    function handleJable() {
        console.log('[MrBanana] handleJable 开始执行');

        const videoUrl = window.location.href;
        if (!videoUrl.includes('/videos/')) {
            console.log('[MrBanana] 不是视频页面，跳过');
            return;
        }

        // 尝试多个可能的选择器
        let titleSection = document.querySelector('.info-header h4, .video-info h4');
        console.log('[MrBanana] 标题选择器1结果:', titleSection);

        if (!titleSection) {
            // 尝试更多选择器
            titleSection = document.querySelector('h4.title, .detail-title h4, section.detail h4');
            console.log('[MrBanana] 标题选择器2结果:', titleSection);
        }

        if (!titleSection) {
            // 打印页面上所有 h4 元素帮助调试
            const allH4 = document.querySelectorAll('h4');
            console.log('[MrBanana] 页面上所有 h4:', allH4);
            return;
        }

        if (document.querySelector('.mrbanana-jable-btn')) {
            console.log('[MrBanana] 按钮已存在，跳过');
            return;
        }

        console.log('[MrBanana] 准备添加 Jable 按钮...');

        const btn = createButton('下载到 Mr. Banana', 'mrbanana-btn-download mrbanana-jable-btn', async () => {
            const serverUrl = getServerUrl();
            if (serverUrl === DEFAULT_SERVER) {
                showToast('请先设置 Mr. Banana 服务器地址', 'info');
                showSettingsPanel();
                return;
            }

            btn.disabled = true;
            btn.innerHTML = '🍌 添加中...';

            // 先获取默认下载配置
            GM_xmlhttpRequest({
                method: 'GET',
                url: `${serverUrl}/api/download/config`,
                timeout: 10000,
                onload: function (configResponse) {
                    let outputDir = '';
                    let scrapeAfter = false;

                    if (configResponse.status >= 200 && configResponse.status < 300) {
                        try {
                            const config = JSON.parse(configResponse.responseText);
                            outputDir = config.output_dir || '';
                            scrapeAfter = config.download_scrape_after_default || false;
                            console.log('[MrBanana] 获取到默认配置:', outputDir, scrapeAfter);
                        } catch (e) {
                            console.log('[MrBanana] 解析配置失败:', e);
                        }
                    }

                    if (!outputDir) {
                        btn.innerHTML = '✗ 未配置目录';
                        btn.classList.add('mrbanana-btn-error');
                        showToast('请先在 Mr. Banana 中设置默认下载目录', 'error');
                        setTimeout(() => {
                            btn.innerHTML = '🍌 下载到 Mr. Banana';
                            btn.classList.remove('mrbanana-btn-error');
                            btn.disabled = false;
                        }, 2000);
                        return;
                    }

                    // 发送下载请求
                    GM_xmlhttpRequest({
                        method: 'POST',
                        url: `${serverUrl}/api/download`,
                        headers: { 'Content-Type': 'application/json' },
                        data: JSON.stringify({
                            url: videoUrl,
                            output_dir: outputDir,
                            scrape_after_download: scrapeAfter
                        }),
                        onload: function (response) {
                            if (response.status >= 200 && response.status < 300) {
                                btn.innerHTML = '✓ 已添加';
                                btn.classList.add('mrbanana-btn-success');
                                showToast('已添加到下载队列');
                            } else {
                                let errorMsg = '添加失败';
                                try {
                                    const data = JSON.parse(response.responseText);
                                    errorMsg = data.detail || errorMsg;
                                } catch (e) { }
                                btn.innerHTML = '✗ 失败';
                                btn.classList.add('mrbanana-btn-error');
                                showToast(errorMsg, 'error');
                                setTimeout(() => {
                                    btn.innerHTML = '🍌 下载到 Mr. Banana';
                                    btn.classList.remove('mrbanana-btn-error');
                                    btn.disabled = false;
                                }, 2000);
                            }
                        },
                        onerror: function () {
                            btn.innerHTML = '✗ 连接失败';
                            btn.classList.add('mrbanana-btn-error');
                            showToast('无法连接服务器', 'error');
                            setTimeout(() => {
                                btn.innerHTML = '🍌 下载到 Mr. Banana';
                                btn.classList.remove('mrbanana-btn-error');
                                btn.disabled = false;
                            }, 2000);
                        }
                    });
                },
                onerror: function () {
                    btn.innerHTML = '✗ 连接失败';
                    btn.classList.add('mrbanana-btn-error');
                    showToast('无法连接服务器', 'error');
                    setTimeout(() => {
                        btn.innerHTML = '🍌 下载到 Mr. Banana';
                        btn.classList.remove('mrbanana-btn-error');
                        btn.disabled = false;
                    }, 2000);
                }
            });
        });

        btn.style.marginLeft = '12px';
        btn.style.display = 'inline-flex';
        titleSection.parentNode.insertBefore(btn, titleSection.nextSibling);
    }

    // =========================================================================
    // 初始化
    // =========================================================================
    function init() {
        const hostname = window.location.hostname;

        if (hostname.includes('javdb')) {
            setTimeout(handleJavDB, 1000);
            const observer = new MutationObserver(() => {
                setTimeout(handleJavDB, 500);
            });
            observer.observe(document.body, { childList: true, subtree: true });
        } else if (hostname.includes('jable')) {
            setTimeout(handleJable, 1000);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
