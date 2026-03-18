# iOS 触控滚动修复（Omni 页面）

## 问题

在 iPhone / iPad 上访问 Omni Full-Duplex 页面时，页面无法通过触控上下滑动，导致最下方的控制按钮（Start、Stop 等）完全不可见、无法点击。

## 根因分析

| 原因 | 说明 |
|------|------|
| `body { height: 100vh }` | 来自 `duplex-shared.css`，把 body 锁死在一屏高度，内容溢出时无法滚动 |
| `.col-left, .col-right { overflow: hidden }` | 列容器裁切溢出内容，触控事件无法触发滚动 |
| 媒体查询断点太小（768px） | iPad 竖屏 810px、横屏 1024px+，全部未命中 |

## 修复方案

修改文件：`static/omni/omni.css`（仅影响 Omni 页面，不影响其他页面）

### 1. 全局允许滚动（无媒体查询）

```css
html {
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
}
body {
    height: auto !important;
    min-height: 100vh;
    overflow-y: auto !important;
    -webkit-overflow-scrolling: touch;
}
```

- 用 `!important` 覆盖 `duplex-shared.css` 的 `height: 100vh`
- `-webkit-overflow-scrolling: touch` 启用 iOS 惯性滚动
- 桌面端内容未溢出时不会出现滚动条，无副作用

### 2. 平板 & 手机：固定底部控制栏（≤1024px）

```css
@media (max-width: 1024px) {
    .main          { height: auto; overflow: visible; padding-bottom: 72px; }
    .col-left,
    .col-right     { overflow: visible; }
    .panel-controls {
        position: fixed; bottom: 0; left: 0; right: 0;
        z-index: 50;
        border-radius: 10px 10px 0 0;
        box-shadow: 0 -2px 12px rgba(0,0,0,0.1);
    }
}
```

- 断点提升到 1024px，覆盖所有 iPad 尺寸
- `.panel-controls` 固定在屏幕底部，始终可见
- `padding-bottom: 72px` 防止页面内容被固定栏遮挡

### 3. 触控设备兜底（hover: none + pointer: coarse）

```css
@media (hover: none) and (pointer: coarse) {
    /* 与上面相同的规则 */
}
```

- 即使 iPad Pro 横屏宽度 > 1024px，该查询也能命中触控设备
- 双重保障，确保所有触屏设备都可滚动

## 断点层级总结

| 断点 | 覆盖设备 | 效果 |
|------|----------|------|
| 无限制 | 所有设备 | body 允许滚动 |
| ≤ 1024px | iPad 竖屏、所有手机 | 固定底部控制栏 + 内容区可滑动 |
| hover:none + pointer:coarse | 所有触控设备 | 同上（兜底） |
| ≤ 768px | 手机 | 单列布局 + 全屏模式优化 |
| ≤ 480px | 小屏手机 | 更紧凑的控制栏 |

## 注意事项

- 仅修改了 `omni.css`，不影响 `audio-duplex` 或 `half-duplex` 页面
- 如果其他 duplex 页面也有相同问题，可参照此方案在对应 CSS 中添加类似覆盖
- 全屏模式（video fullscreen）下控制栏有独立的固定定位逻辑，不受此修改影响
