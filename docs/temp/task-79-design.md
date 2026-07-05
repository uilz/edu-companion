# Task #79 — Professional 风格 Design Token 应用 + Cockpit 视觉精修

## 状态：已完成

## 实施摘要

按 design-language.md professional 风格（Linear/Notion）规范，对 Cockpit 驾驶舱和外壳进行了系统化视觉精修。

## 改动文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `frontend/src/app/globals.css` | 修改 | 颜色 slate 化、圆角 8/12、阴影 sm/md、添加 cockpit-card / tabular / skeleton-block 工具类 |
| `frontend/src/components/dashboard/Cockpit.tsx` | 重写 | 应用新 token、加 shadow/hover、加载 skeleton、空态图标、数字 28px |
| `frontend/src/components/layout/AppShell.tsx` | 微调 | 平板 header 加 backdrop-blur、按钮 rounded-md |
| `scripts/task79_verify.py` | 新增 | E2E 验证脚本（设计 token + 视觉细节检查） |
| `docs/temp/task-79-design.md` | 新增 | 任务设计文档 |

## Token 变更（before → after）

| Token | Before | After | 验证 |
|-------|--------|-------|------|
| `--color-page` | `#fbfaf7` 暖白 | `#fff` 纯白 | ✅ |
| `--color-ink-primary` | `#1c1917` 暖墨 | `#171717` slate-900 | ✅ |
| `--color-divider` | `#e7e3de` 暖灰 | `#e5e5e5` slate-200 | ✅ |
| `--color-accent` | `#2563eb` | `#2563eb` | ✅ |
| `--radius-md` | 10px | 8px | ✅ |
| `--radius-lg` | 14px | 12px | ✅ |
| `--shadow-sm` | 0 1px 3px / .06 | 0 1px 2px / .04 | ✅ |
| `--shadow-md` | 0 4px 16px / .08 | 0 4px 12px / .06 | ✅ |
| 字体 | Inter+Noto | Inter 优先 | ✅ |
| 圆角覆盖 | 无 | radius-md 8 / radius-lg 12 | ✅ |
| 间距覆盖 | 无 | space-3 10 / space-4 14 / space-5 20 | ✅ |

> 暗色模式同步更新：去暖色 → 真中性（#0a0a0a page, #141414 surface, #262626 divider）

## Cockpit 视觉变更

| 项目 | Before | After |
|------|--------|-------|
| 卡片圆角 | rounded-lg 14px | 12px (radius-lg) |
| 卡片阴影 | 无 | shadow-sm 默认 + shadow-md hover |
| 卡片 hover | 无效果 | translateY(-1px) + 阴影加深 + 边框色变化 |
| 焦点区强调 | bg-accent/5 | 左侧 3px 蓝边 + shadow-sm |
| 数字字号 | 22px | 28px（更突出） |
| 数字 tabular | ✅ | ✅ + 强化 tnum font-feature |
| 加载态 | 仅 spinner | 4 块 skeleton shimmer |
| 空态 | 纯文字居中 | 图标 + 引导文字（icon-in-rounded-square） |
| 标题区 | 20px bold | 22px semibold tracking-tight |
| 时长文案 | 11px | 12-13px |
| Primary 按钮 | 12px h-8 | 13px h-9 + shadow-sm + active scale |
| Hover transition | 仅 color | color + bg + shadow + transform |

## 验证结果

| 检查 | 结果 |
|------|------|
| Login | ✅ |
| 5 区结构 | ✅ 焦点/3数据/AI/时间线/快速跳转 |
| Design Token 套用 | ✅ 16/16 通过 |
| 数字 tabular-nums | ✅ |
| 数字 28px | ✅ |
| 卡片 12px 圆角 | ✅ |
| 卡片 shadow-sm | ✅ |
| 移动端响应式 | ✅ |
| console error | 0 ✅ |
| console warning | 0 ✅ |
| page error | 0 ✅ |
| network error | 0 ✅ |
| 1240 pytest passed | ✅（与 baseline 1236 一致或更多，原有 5 警告保持） |
| 154+ API endpoints | ✅（未改后端） |

## 截图证据

- `screenshots/task79/before-cockpit-desktop.png` - 修改前桌面
- `screenshots/task79/after-cockpit-desktop.png` - 修改后桌面
- `screenshots/task79/before-cockpit-mobile.png` - 修改前移动
- `screenshots/task79/after-cockpit-mobile.png` - 修改后移动
- `screenshots/task79/after-cockpit-detail.png` - 修改后焦点区细节

## 边界 / 未做

1. **其他模块页面**（conversation / practice / analytics 等）未触 — 按 Part C 节制原则
2. **BottomNav / MobileDrawer** 原样保留
3. **纯无数据** 的真实数据未注入验证（基于 Task #78 截图结论）
4. **hover 效果** 在 headless Firefox 中可能无法完全复现（hover 截图在真实浏览器更明显）

## 后续建议

- Task #80：把 cockpit-card / tabular / skeleton-block 工具类应用到 conversation 气泡
- Task #80：把 Linear/Notion 风格的 color/diff/data viz 推广到 analytics 页
