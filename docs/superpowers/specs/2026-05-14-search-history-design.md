# 搜索历史功能设计

**日期:** 2026-05-14  
**范围:** 搜索页三平台独立搜索历史，显示在平台标签下方，带清除按钮

---

## 布局

```
[ 搜索框                              ]
[ 网易云 | Spotify | YouTube Music    ]
[ 最近搜索                       清除 ]  ← _history_panel
  Taylor Swift
  周杰伦
[ 专辑横滚 + 结果列表（有内容时）      ]
```

## 显示逻辑

- 搜索框**为空**时：显示 `_history_panel`，隐藏专辑横滚和结果列表
- 搜索框**有内容**时：隐藏 `_history_panel`，显示结果
- 切换平台：刷新 `_history_panel` 为当前平台的历史
- 历史为空时：隐藏整个 `_history_panel`

## 数据层

**存储**：`settings` 表，三个 key：
- `search_history_netease`
- `search_history_spotify`
- `search_history_ytmusic`

值为 JSON 数组字符串，newest-first，最多 15 条，写入时自动去重+截断。

**AppController 新增：**

```python
async def get_search_history(self, platform: str) -> list[str]
async def add_search_history(self, platform: str, query: str) -> None
async def clear_search_history(self, platform: str) -> None
```

- `add_search_history`：query strip 后若为空则跳过；去重（移除旧的同名条目）后插入头部；超 15 条截断；调用 `_repo.set_setting`
- `clear_search_history`：保存空数组 `"[]"`
- `get_search_history`：读取后 JSON 解析，失败返回 `[]`

## UI — _history_panel

`QWidget`，垂直布局：
- 顶行：`QLabel("最近搜索")` + `QPushButton("清除")` 右对齐
- 历史词列表：每条是 `QPushButton`（左对齐文本，无边框背景），点击后填入搜索框并立即触发搜索（跳过防抖，直接调用 `_do_search`）

## 写入时机

`_do_search(query)` 返回结果非空后，调用 `asyncio.ensure_future(ctrl.add_search_history(platform, query))`
