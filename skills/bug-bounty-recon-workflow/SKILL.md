# Recon 自动化工作流

> 7步 Recon 侦察流程 + P0-P3 目标分级策略

## 技能描述
整合 subfinder/httpx/dnsx/nuclei/ffuf/katana 工具链的自动化侦察工作流。从子域名枚举到漏洞扫描，按 P0-P3 分级筛选高价值目标。

## 工作流步骤
1. 子域名枚举（subfinder）
2. DNS 记录收集（dnsx）
3. 存活主机探测（httpx）
4. 主机分类筛选
5. 目录爆破（ffuf）
6. 漏洞扫描（nuclei）
7. 爬虫扩展（katana）

## P0-P3 分级策略
- P0：目录列表暴露、Staging环境公开、QA环境暴露
- P1：登录页面、API端点、Beta环境
- P2：需客户端证书的API、VPN端点、默认页面
- P3：重定向页面、静态资源

## 三平台发布状态
- Coze 技能商店：已发布
- EvoMap：已发布（bundle_4f0c4b9090c52d25）
- GitHub：本目录
