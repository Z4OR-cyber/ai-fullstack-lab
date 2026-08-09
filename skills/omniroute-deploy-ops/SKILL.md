# OmniRoute 部署运维技能

## 概述
OmniRoute AI网关的本地部署、配置、故障排查和日常运维指南。覆盖 Node.js 部署路线、环境配置、SWC兼容性修复和服务器管理。

## 部署流程

### 1. 环境检测
- Node.js >= 22.22.2
- npm >= 10
- 内存 >= 4GB

### 2. 获取代码
zip下载替代git clone（避免超时）

### 3. 安装依赖
npm install（约1467个包，需后台运行避免超时）

### 4. 环境配置 (.env)
- JWT_SECRET / API_KEY_SECRET / INITIAL_PASSWORD
- PORT=20128
- OMNIROUTE_USE_TURBOPACK=0（关键）

### 5. 启动
node --max-old-space-size=4096 scripts/dev/run-next.mjs dev

## 故障排查

### SWC二进制不兼容
症状: @next/swc-win32-x64-msvc is not a valid Win32 application
修复: OMNIROUTE_USE_TURBOPACK=0，回退WASM绑定

### npm install超时
修复: 后台运行+日志轮查

### 内存不足
修复: 调整--max-old-space-size（8192降到4096）

## 技术栈
Next.js 16 + TypeScript 6.0 + better-sqlite3 + Tailwind CSS v4
290 providers, MCP 104 tools, A2A v0.3

## 许可
参考上游仓库许可
