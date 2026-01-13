# App.jsx 拆分重构计划

## 📋 概述

将 3829 行的 App.jsx 文件拆分为多个模块化组件和 hooks，提高代码可维护性和可读性。

## ✅ 已完成进度 (2024)

### Phase 1: 清理重复代码 ✅
- 删除了 App.jsx 中重复定义的组件和函数
- 创建了 `utils/appHelpers.js` 存放工具函数
- 减少约 150 行代码

### Phase 2: 提取 Modal 组件 ✅
- 创建了 `components/modals/ScrapeDetailModal.jsx` (~240行)
- 创建了 `components/modals/PlayerDetailModal.jsx` (~130行)  
- 集成了已有的 `LogViewerModal` 和 `ContextMenu`
- 减少约 400 行代码

### 总体进度
- 原始文件: **3829 行**
- 当前文件: **3280 行**
- 减少: **549 行 (约 14.3%)**

## 🚧 待完成 (可选)

### Phase 3: Tab 组件提取 (高风险)
由于 App.jsx 中的状态高度耦合（60+ 个 state），提取 Tab 组件需要：
1. 创建 AppContext 共享状态
2. 或使用状态管理库 (zustand/jotai)
3. 大量的 props drilling

建议：保持当前状态，或在有更多时间时进行架构重构

## 📊 当前文件结构分析

### 文件行数分布
| 区域 | 行数范围 | 内容 | 行数 |
|------|----------|------|------|
| 导入和工具组件 | 1-160 | imports, getScrapeStatusLabel, getStatusLabel, StatusIcon, ScrapeStatusIcon, InfoTooltip, BrushCleaningIcon, stableStringify | ~160 |
| App 状态声明 | 162-700 | uiLang, themeMode, activeTab, 各种 state (~60+) | ~540 |
| Fetch 函数 | 700-1100 | fetchHistory, fetchDownloadConfig, fetchScrapeConfig, fetchPlayerConfig | ~400 |
| Save Handlers | 1100-1500 | handleSave*, handleStart*, handleResume, handlePause, handleDelete | ~400 |
| Effects & Memo | 1500-1700 | useEffect 钩子, mergedRows useMemo | ~200 |
| Download Tab JSX | 1700-2300 | 下载标签页完整 JSX | ~600 |
| Player Tab JSX | 2300-2450 | 播放器标签页 JSX | ~150 |
| Scrape Tab JSX | 2450-3500 | 刮削标签页 JSX (8个设置子标签) | ~1050 |
| Modals & Menu | 3500-3829 | Log viewer, Scrape detail, Context menu | ~330 |

### 状态变量分类 (~60+)
1. **UI 状态**: uiLang, themeMode, activeTab, settingsOpen, pickerOpen 等
2. **下载状态**: url, loading, downloadHistory, activeTasks, downloadConfig 等
3. **刮削状态**: scrapeConfig (~40字段), scrapeJobs, scrapeHistory, scrapeItems, scrapePendingCount 等
4. **播放器状态**: playerConfig, playerLibrary, playerDetail 等
5. **模态框状态**: logViewer, scrapeDetail, contextMenu 等
6. **动画状态**: gearSpin, broomSweep, scrapeBroomSweep 等

## 🏗️ 目标架构

```
web/src/
├── App.jsx                    # 主入口 (~300 行)
├── components/
│   ├── index.js              # 组件导出
│   ├── icons/
│   │   ├── index.js
│   │   ├── StatusIcon.jsx    # 下载状态图标
│   │   ├── ScrapeStatusIcon.jsx # 刮削状态图标
│   │   ├── BrushCleaningIcon.jsx # 清扫动画图标
│   │   └── InfoTooltip.jsx   # 信息提示
│   ├── tabs/
│   │   ├── index.js
│   │   ├── DownloadTab.jsx   # 下载标签页
│   │   ├── PlayerTab.jsx     # 播放器标签页
│   │   └── ScrapeTab.jsx     # 刮削标签页
│   └── modals/
│       ├── index.js
│       ├── LogViewerModal.jsx
│       ├── ScrapeDetailModal.jsx
│       └── PlayerDetailModal.jsx
├── hooks/
│   ├── index.js              # hooks 导出
│   ├── useAppState.js        # (已存在) 通用状态 hooks
│   ├── useDownload.js        # 下载逻辑
│   ├── useScrape.js          # 刮削逻辑
│   └── usePlayer.js          # 播放器逻辑
└── utils/
    ├── index.js              # 工具导出
    ├── appHelpers.js         # App 工具函数
    └── accessibility.js      # (已存在) 无障碍工具
```

## 📝 执行计划

### Phase 1: 提取工具函数和图标组件 (TODO #2-4)

#### Step 1.1: 创建 utils/appHelpers.js
提取以下函数：
- `getScrapeStatusLabel(status, lang)` - 刮削状态标签
- `getStatusLabel(status, lang)` - 下载状态标签  
- `stableStringify(value)` - 稳定的 JSON 序列化
- `extractCodeFromPath(path)` - 从路径提取番号 (需从 App.jsx 查找)
- `getExpectedScrapeCrawlerCount(config)` - 计算预期爬虫数量

#### Step 1.2: 创建 components/icons/
- `StatusIcon.jsx` - 下载状态图标组件
- `ScrapeStatusIcon.jsx` - 刮削状态图标组件  
- `InfoTooltip.jsx` - 信息提示组件
- `BrushCleaningIcon.jsx` - 清扫动画 SVG 图标

#### 检查点 1 (TODO #4)
- [ ] 所有新文件无语法错误
- [ ] App.jsx 正确导入新模块
- [ ] 应用可正常启动

### Phase 2: 创建业务逻辑 Hooks (TODO #5-8)

#### Step 2.1: 创建 hooks/useDownload.js
状态：
- url, loading, downloadHistory, activeTasks
- downloadConfig (output_dir, proxy_enabled, max_concurrent 等)
- contextMenu

Handlers：
- fetchHistory, fetchDownloadConfig
- handleSaveDownloadConfig
- handleResume, handlePause, handleDelete
- handleClearHistory

#### Step 2.2: 创建 hooks/useScrape.js  
状态：
- scrapeConfig (~40 字段)
- scrapeJobs, scrapeHistory, scrapeItems
- scrapePendingCount, scrapeLiveState
- scrapeDetail

Handlers：
- fetchScrapeConfig, fetchScrapePendingCount
- handleSaveScrapeConfig
- handleStartScrape, handleClearScrapeHistory
- openScrapeDetail, closeScrapeDetail

#### Step 2.3: 创建 hooks/usePlayer.js
状态：
- playerConfig
- playerLibrary, playerDetail

Handlers：
- fetchPlayerConfig, fetchPlayerLibrary
- handleSavePlayerConfig
- openPlayerDetail, closePlayerDetail

#### 检查点 2 (TODO #8)
- [ ] 所有 hooks 正确导出
- [ ] 无循环依赖
- [ ] App.jsx 可正常使用 hooks

### Phase 3: 创建 Tab 组件 (TODO #9-12)

#### Step 3.1: 创建 DownloadTab.jsx (~600行)
- 设置面板 (output_dir, proxy, concurrent 等)
- 输入表单 (URL 输入, 下载按钮)
- 历史表格 (使用 mergedRows)

#### Step 3.2: 创建 PlayerTab.jsx (~150行)
- 设置面板
- 媒体库网格
- PlayerDetail 模态框入口

#### Step 3.3: 创建 ScrapeTab.jsx (~1050行)
- 设置卡片 (8个子标签)
  - trigger (触发设置)
  - naming (命名设置)
  - download (下载设置) 
  - nfo (NFO 设置)
  - translation (翻译设置)
  - concurrency (并发设置)
  - network (网络设置)
  - sources (数据源设置)
- 当前预览卡片
- 历史表格

#### 检查点 3 (TODO #12)
- [ ] 三个 Tab 组件正常渲染
- [ ] Props 传递正确
- [ ] 无 UI 回归

### Phase 4: 提取 Modal 组件 (TODO #13-15)

#### Step 4.1: 创建 modals/LogViewerModal.jsx
- 日志查看器模态框
- 支持 download 和 scrape 两种模式

#### Step 4.2: 创建 modals/ScrapeDetailModal.jsx
- 刮削详情模态框
- 海报、背景、标签等展示

#### Step 4.3: 创建 modals/PlayerDetailModal.jsx
- 播放器详情模态框

#### Step 4.4: 创建 ContextMenu.jsx
- 右键菜单组件
- 恢复/暂停/删除操作

#### 检查点 4 (TODO #15)
- [ ] 所有模态框正常工作
- [ ] Portal 渲染正确
- [ ] 键盘交互正常

### Phase 5: 重构 App.jsx (TODO #16)

最终 App.jsx 结构：
```jsx
function App() {
  // UI 状态
  const { theme, setTheme } = useTheme();
  const { lang, setLang } = useLanguage();
  const [activeTab, setActiveTab] = useActiveTab();
  
  // 业务 hooks
  const download = useDownload();
  const scrape = useScrape();
  const player = usePlayer();
  
  // 共享状态
  const [logViewer, setLogViewer] = useState({ open: false });
  
  // 音频效果
  const audioRefs = useAudioEffects();
  
  return (
    <div className="...">
      {/* Header */}
      <header>...</header>
      
      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>...</TabsList>
        
        <TabsContent value="download">
          <DownloadTab {...download} />
        </TabsContent>
        
        <TabsContent value="player">
          <PlayerTab {...player} />
        </TabsContent>
        
        <TabsContent value="scrape">
          <ScrapeTab {...scrape} />
        </TabsContent>
      </Tabs>
      
      {/* Modals */}
      <LogViewerModal {...logViewer} />
      <ContextMenu {...download.contextMenu} />
    </div>
  );
}
```

### 最终检查 (TODO #17)
- [ ] 所有文件无编译错误
- [ ] 应用可正常启动
- [ ] 三个标签页功能正常
- [ ] 所有模态框正常
- [ ] 主题切换正常
- [ ] 语言切换正常
- [ ] 更新 index.js 导出文件

## 🔄 回滚策略

1. **Git 备份**: 开始前创建 backup 分支
2. **增量提交**: 每个 Phase 完成后提交
3. **旧代码保留**: 新文件创建后再修改 App.jsx
4. **错误回滚**: 发现问题时 git checkout 恢复

## ⚠️ 注意事项

1. **循环依赖**: hooks 之间不要互相导入
2. **Props 传递**: 确保所有必要的 props 传递到子组件
3. **Context**: 考虑使用 React Context 减少 props drilling
4. **性能**: 使用 useMemo/useCallback 避免不必要的重渲染
5. **类型安全**: 保持现有的 JSDoc 注释

## 📅 时间估算

| Phase | 预计时间 | 复杂度 |
|-------|----------|--------|
| Phase 1 | 15 分钟 | 低 |
| Phase 2 | 30 分钟 | 中 |
| Phase 3 | 45 分钟 | 高 |
| Phase 4 | 20 分钟 | 中 |
| Phase 5 | 30 分钟 | 中 |
| 检查 | 15 分钟 | - |
| **总计** | **~2.5 小时** | - |

---
文档创建时间: 2024
