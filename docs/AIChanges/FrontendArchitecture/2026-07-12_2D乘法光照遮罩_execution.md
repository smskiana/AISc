> 设计方案: [2026-07-12_2D乘法光照遮罩_plan.md](2026-07-12_2D乘法光照遮罩_plan.md)

# 2D 乘法光照遮罩 — 执行记录

## 实际改动

1. 新增 `Assets/Shaders/Shader_2DMultiplyLightingMask.shader`
   - Shader 菜单路径：`SakurabashiDoori/2D/Multiply Lighting Mask`
   - 使用 `Blend DstColor Zero` 与底下已渲染颜色做乘法混合。
   - `_MainTex` 的 alpha 与 `_Strength` 控制遮罩影响强度。
   - `_Color` 可整体染色，`_Brightness` 可调整遮罩亮度，`_MinMultiplier` 可限制最暗值。
   - 保留 UI Stencil / ColorMask / RectMask2D clip 相关属性，方便 SpriteRenderer 与 UGUI Image 共用。

2. 新增 `Assets/Materials/M_2DMultiplyLightingMask.mat`
   - 默认引用新增 shader。
   - 默认参数保持白色、强度 1、亮度 1。

3. 新增 Unity `.meta`
   - `Assets/Shaders.meta`
   - `Assets/Shaders/Shader_2DMultiplyLightingMask.shader.meta`
   - `Assets/Materials/M_2DMultiplyLightingMask.mat.meta`

## 使用方式

1. 创建一个覆盖目标区域的 SpriteRenderer 或 UI Image。
2. 使用 `M_2DMultiplyLightingMask` 材质。
3. 遮罩图建议约定：
   - 白色或 alpha 0：不影响底图。
   - 灰色：压暗底图。
   - 偏蓝 / 偏橙：做夜晚或暖光染色。
4. 确保遮罩对象绘制在被影响元素之后：
   - SpriteRenderer：调 Sorting Layer / Order in Layer。
   - UGUI：放在目标 UI 层级上方。

## 验证方式

1. 已静态检查 shader 关键结构：
   - 花括号数量一致：`11/11`
   - 乘法混合行存在：`Blend DstColor Zero`
   - 材质引用的 shader GUID 与 shader `.meta` 一致。
2. 未启动 Unity 编辑器导入，因此本轮未做 Console 编译验证。

## 未完成项

1. 后续可在 Unity 中创建一张全屏灰蓝遮罩图，挂到该材质上，验证夜晚压暗效果。
2. 如果未来切换 URP 2D Renderer，建议另做 URP 版本或改用 Render Feature / 2D Light 工作流。
