# whiteboard-cli 导入约束（@larksuite/whiteboard-cli ^0.2.13）

## 支持与禁用
- 支持：`rect`（含 rx）、`polygon`、`polyline`、`line`、`ellipse`、`path`、`text`、`linearGradient`、单个 `feDropShadow`。
- 不要用：`tspan` 混排（同一 `<text>` 里混粗体/颜色会重叠，改用多个 `<text>` 手动排位）、`pattern`、`clipPath`、`mask`、blur 滤镜。
- 字体统一 `Noto Sans SC`；文字宽度用其字体文件实测最准（`lib.text_width`）。

## 检查器规则（实测，0.2.13）
- **node-overlap（warning）**：两个**填充矩形/路径**相交面积 ≥ 较小者 50% 即报，嵌套包含也算（例外：小的 < 大的约 50%）。
  `polygon`、`polyline`、`line` 不参与此检查 → 大容器、条纹、表格底、需要叠放的卡片画成多边形（`Svg.rpoly`）。
  无填充（`fill="none"`）的 rect 仍参与。
- **text-overflow（error）**：检查器把「文字左上角所在的形状」当作该文字的容器，文字超出它就报错。
  所以小图标、细条装饰压在文字左上角时会误报：细条改画粗 `line`，图标避让文字（`Painter.dodge_text`）。
  `line` 不会被当作容器。
- 检查器对粗体宽度估算略大，粗体换行宽度留 4–8px 余量。

## 其他经验
- 线上会把多行文本拆成多段节点，做文字比对时按字符多重集比，不按整句比。
- 部分符号（如 ↺）本地渲染缺字形会显示方框，线上通常正常；交付时说明「本地未验证该符号」。
- 线上 preview 图有数分钟延迟，不要轮询。
