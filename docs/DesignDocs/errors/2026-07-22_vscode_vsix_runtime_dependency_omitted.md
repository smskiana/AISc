# VSIX 排除依赖导致扩展宿主激活失败

## 错误现象

VS Code 扩展可以通过 TypeScript 编译、成功生成 VSIX、成功安装并显示 Activity Bar 贡献点，但打开视图后提示没有 data provider，所有贡献命令均返回 command not found。extension-host 日志报 `Cannot find module`，且 require stack 指向扩展入口。

## 根本原因

打包命令使用 `vsce package --no-dependencies`，但 TypeScript 产物仍保留第三方包的运行时 `require`。VSIX 因此既不包含依赖目录，入口也不是自包含 bundle。`package.json` 中的静态贡献点仍能显示，但扩展模块在执行 `activate()` 前加载失败，造成“已安装但全部行为不可用”的假象。

## 正确做法

1. 使用 esbuild 等 bundler 把非宿主依赖打入扩展入口，只将 `vscode` 等确定由 extension host 提供的模块标为 external；或不使用 `--no-dependencies` 并明确验证依赖被装入 VSIX。
2. 打包门禁必须检查最终入口，而不只检查源码和 TypeScript 编译：禁止残留未随包分发的第三方 `require`，并验证 bundle 大小和预期 external。
3. 独立测试必须在真实 extension host 触发至少一个 activation event，并读取 extension-host 日志；“贡献点可见”和“VSIX 安装成功”不能证明 `activate()` 已执行。

## 本次修复

Project Cognition VS Code adapter 改为单文件 CommonJS bundle，新增 `verify:bundle` 检查，并覆盖安装修复后的 VSIX。不存在的 relation ID 同期收敛为稳定 `RELATION_NOT_FOUND`，避免空成功掩盖调用错误。
