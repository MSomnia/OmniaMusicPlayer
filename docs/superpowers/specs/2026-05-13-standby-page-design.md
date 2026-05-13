# 待机页设计文档

**日期：** 2026-05-13  
**状态：** 已批准，待实现

---

## 概述

待机页（Standby Page）是一个全屏沉浸式视图，覆盖 sidebar 与 content 区域，仅保留底部 NowPlayingBar。进入通道为点击侧边栏顶部的用户名。设计目标是"屏保式"氛围体验，视觉重心在歌词。

---

## 架构

### 组件结构

- **新文件：** `ui/pages/standby_page.py`，包含 `StandbyPage(QWidget)`
- `StandbyPage` 作为 `_AppRoot` 的直接子 widget，初始 `hide()`
- 与现有 `_ErrorToast` 采用相同的 overlay 模式（绝对定位子 widget）

### 尺寸同步

`MainWindow.resizeEvent` 中更新几何，始终覆盖 body 区域：

```
x=0, y=0
width  = central_widget.width()
height = central_widget.height() - now_playing_bar.height()
```

### 入口修改

`SidebarWidget`：
- `_title` label 替换为 `_ClickableLabel`（在 `sidebar.py` 内部局部定义，与 `now_playing_bar.py` 中同名类模式相同，不跨模块复用）
- 新增信号 `standby_requested = pyqtSignal()`，点击 `_title` 时 emit

`MainWindow._wire_signals()`：
- 连接 `sidebar.standby_requested → _toggle_standby()`

---

## 视觉设计

### 风格：氛围发光（方案 B）

- 背景：直接复用 `_AppRoot.background_pixmap()`，无背景图时纯黑
- 遮罩：`rgba(0, 0, 0, 0.25)` 半透明叠加
- 封面光晕：在封面中心绘制 `QRadialGradient`，颜色来自 `cover_color_ready`，半径 = 控件宽度 × 35%，透明度 0.30；无颜色数据时默认 `rgba(80, 60, 120, 0.15)`

### 布局：左右各 50%

**左半部分（从上到下，纵向 flex）：**

| 元素 | 尺寸/样式 |
|---|---|
| 封面图 | 130×130px，圆角 10px，居中，有光晕 box-shadow |
| 歌名 | font-size 16px，bold，白色，封面下 12px |
| 艺术家 | font-size 11px，`rgba(255,255,255,0.55)`，歌名下 4px |
| 分隔线 | 宽 70%，1px，`rgba(255,255,255,0.08)`，下边距 16px |
| 歌词滚动区 | 剩余高度，居中对齐，逐行高亮 |

封面、歌名、艺术家组合占上部固定空间，歌词区 `stretch=1` 占满剩余高度。

**右半部分：**

- 居中显示占位符：`✦` 图标 + "更多内容 / 即将到来"，`rgba(255,255,255,0.18)`
- 左侧用 `rgba(255,255,255,0.06)` 1px 竖线分隔

**关闭按钮：**

- 位置：左上角，绝对定位，`top=12, left=12`
- 样式：`rgba(255,255,255,0.10)` 背景，`rgba(255,255,255,0.15)` 边框，圆角 20px，`"✕  退出待机"`
- 点击：调用 `StandbyPage.leave()`

---

## 歌词显示

- `StandbyPage` 内部持有独立的 `LyricsEngine` 实例（不与 `LyricsView` 共享）
- 歌词行用 `QLabel` 列表渲染，垂直居中对齐，当前行放大 + accent 色高亮，其余行渐隐
- `position_changed` 信号：只在 `isVisible()` 时处理，避免后台无效计算
- 滚动：`QScrollArea`，`QPropertyAnimation` 平滑滚动到当前行，duration 450ms

---

## 状态机

| 状态 | 封面 | 歌名/艺术家 | 歌词区 |
|---|---|---|---|
| 正在播放 | 歌曲封面图 | 实际数据 | 同步滚动高亮 |
| 无歌曲（`state.current_track is None`） | 灰色音乐图标（内置 SVG/emoji） | "暂无播放" / "—" | 空白 |
| 加载中（`state.status == "loading"`） | 灰色占位方块 | 歌名（若有） | 空白 |

---

## 进入/退出动画

| 动作 | 效果 | 时长 | Easing |
|---|---|---|---|
| 进入 | opacity 0 → 1，`raise_()` | 300ms | OutCubic |
| 退出 | opacity 1 → 0，动画完成后 `hide()` | 200ms | InCubic |

使用 `QGraphicsOpacityEffect` + `QPropertyAnimation`。

---

## 信号接线（MainWindow）

```
ctrl.state_changed      → standby_page.on_state_changed
ctrl.cover_art_bytes    → standby_page.set_cover_art_bytes
ctrl.cover_color_ready  → standby_page.set_cover_color
ctrl.lyrics_ready       → standby_page.set_lyrics
ctrl.position_changed   → standby_page.update_position
```

初始化时同步当前状态（与 `LyricsView` 接线方式一致）。

---

## 不在本期范围内

- 右侧区域的实际内容（当前为占位符）
- 鼠标/键盘快捷键退出（如 ESC）
- 封面旋转动画（设置项已有，但待机页封面静止）
