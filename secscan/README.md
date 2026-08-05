<p align="center">
  <h1 align="center">🛡️ SecScan</h1>
  <p align="center">AI 驱动的代码安全审计平台</p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.10+-blue" alt="Python">
    <img src="https://img.shields.io/badge/FastAPI-latest-009688" alt="FastAPI">
    <img src="https://img.shields.io/badge/version-2.0.0-green" alt="Version">
    <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License">
  </p>
</p>

---

## 📋 简介

**SecScan** 是一个 AI 驱动的代码安全审计平台，支持 **Python** 和 **JavaScript** 代码的自动化安全扫描。

平台采用 **AST 抽象语法树分析** 与 **正则匹配** 双引擎策略，可检测 **10 种** OWASP 常见安全漏洞（SQL注入、命令注入、XSS、SSRF 等），并结合 **RAG（检索增强生成）** 技术从内置知识库中检索修复建议，为开发者提供详细的漏洞修复指导。

所有扫描结果持久化到 **SQLite 数据库**，支持历史查询、分页筛选和记录管理。

---

## ✨ 功能特性

| 特性 | 说明 |
|------|------|
| 🔍 **双引擎分析** | Python 使用 AST 分析（高精度），JavaScript 使用正则匹配（覆盖广） |
| 🛡️ **10 种漏洞检测** | 覆盖 OWASP Top 10，每条规则映射到 MITRE CWE 标准 |
| 📚 **RAG 修复建议** | 内置 10 份漏洞修复知识文档，通过 TF-IDF 向量检索增强修复建议 |
| 🖥️ **Web 界面** | 支持拖拽上传 / 代码粘贴，可视化漏洞分布图表，一键导出 JSON 报告 |
| 💾 **数据库持久化** | SQLite 存储，扫描结果不丢失，支持历史查询与记录删除 |
| 📖 **RESTful API** | 标准化 API，自动生成交互式文档（Swagger UI） |
| 🐳 **Docker 一键部署** | 多阶段构建、双网络隔离、健康检查，生产级可用 |
| ☸️ **K8s 部署就绪** | 含 Deployment / Service / Ingress / HPA / PDB 完整清单 |
| 🔧 **CI/CD 集成** | GitHub Actions 流水线：Lint → 矩阵测试 → 构建 → 推送 GHCR |
| 🇨🇳 **全中文文档** | 规则描述、修复建议、API 文档、代码注释均为中文 |

---

## 🚀 快速开始

### 前置条件

- **Python ≥ 3.10**（推荐 3.12+）
- **pip**（随 Python 自动安装）

---

### 方式 A：pip 安装（最简单）

> 适合本地体验和快速试用，无需 Docker。

```bash
# 1. 进入项目目录
cd secscan

# 2. 创建虚拟环境（推荐）
python -m venv .venv

# 3. 激活虚拟环境
# Linux / macOS:
source .venv/bin/activate
# Windows (PowerShell):
# .venv\Scripts\Activate.ps1

# 4. 安装依赖
pip install -r requirements.txt

# 5. 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

✅ 启动后访问：
- **Web 界面**：http://localhost:8000
- **API 文档**：http://localhost:8000/docs
- **健康检查**：http://localhost:8000/

---

### 方式 B：Docker Compose（生产级）

> 适合生产环境部署，自动编排应用 + PostgreSQL + ChromaDB 三服务。

```bash
# 1. 复制环境变量模板
cp .env.example .env

# 2. 编辑 .env，修改密码和密钥（重要！）
#    特别是 POSTGRES_PASSWORD 和 SECRET_KEY
vim .env

# 3. 启动所有服务
docker compose up -d

# 4. 查看服务状态
docker compose ps

# 5. 查看日志（可选）
docker compose logs -f secscan-app
```

✅ 服务启动后：
- **Web 界面**：http://localhost:8000
- **PostgreSQL**：`localhost:5432`（开发模式，生产模式仅内部网络可达）
- **ChromaDB**：`localhost:8001`（开发模式）

**停止服务：**
```bash
docker compose down        # 停止容器，保留数据
docker compose down -v     # 停止容器并删除数据卷（谨慎！）
```

---

### 方式 C：开发模式（热重载）

> 适合二次开发，代码修改后自动重启。

#### 方式 C-1：本地开发

```bash
# 1. 安装依赖（同方式 A）
pip install -r requirements.txt

# 2. 以热重载模式启动
python -m uvicorn app.main:app --reload --port 8000
```

修改任意 Python 文件后，服务会自动重新加载。

#### 方式 C-2：Docker 开发模式

```bash
# docker-compose.override.yml 已预配置热重载 + 调试端口
docker compose up -d

# 支持远程调试（debugpy）
# 端口 5678 已映射
```

---

### 🎯 一键启动脚本（推荐新手使用）

不想手动操作？使用一键启动脚本：

```bash
# Linux / macOS
chmod +x start.sh
./start.sh

# Windows
start.bat
```

脚本会自动检查 Python 版本、安装依赖、启动服务并打开浏览器。

---

## 📡 API 文档

启动服务后，访问 **http://localhost:8000/docs** 可查看完整的交互式 API 文档（Swagger UI）。

### 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 健康检查，返回应用基本信息和可用端点列表 |
| `POST` | `/api/scan` | 上传代码文件（`.py` / `.js`），执行安全扫描 |
| `GET` | `/api/report/{scan_id}` | 根据扫描 ID 获取完整的扫描报告（含漏洞详情） |
| `GET` | `/api/history` | 查询扫描历史列表，支持分页和筛选 |
| `DELETE` | `/api/report/{scan_id}` | 删除指定的扫描记录 |

### 详细说明

#### POST /api/scan — 上传代码扫描

**请求：** `multipart/form-data`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | ✅ | 代码文件，支持 `.py` / `.js` / `.mjs` |

**示例（curl）：**
```bash
curl -X POST http://localhost:8000/api/scan \
  -F "file=@your_code.py"
```

**响应示例：**
```json
{
  "scan_id": "a1b2c3d4-...",
  "filename": "app.py",
  "language": "Python",
  "scan_time": "2025-01-15T12:00:00",
  "vulnerabilities": [
    {
      "rule_id": "SC004",
      "vuln_type": "硬编码密钥",
      "cwe_id": "CWE-798",
      "severity": "High",
      "description": "检测到代码中硬编码了API密钥...",
      "line": 5,
      "code_snippet": "API_KEY = \"sk-1234567890abcdef\"",
      "fix_suggestion": "将敏感凭证移至环境变量..."
    }
  ],
  "summary": {
    "total": 1,
    "critical": 0,
    "high": 1,
    "medium": 0,
    "low": 0,
    "info": 0
  }
}
```

#### GET /api/report/{scan_id} — 获取扫描报告

```bash
curl http://localhost:8000/api/report/a1b2c3d4-xxxx
```

#### GET /api/history — 查询扫描历史

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `skip` | int | 0 | 跳过的记录数（分页偏移） |
| `limit` | int | 20 | 每页记录数（1-100） |
| `filename` | string | — | 按文件名模糊筛选 |
| `language` | string | — | 按语言精确筛选（Python / JavaScript） |

```bash
# 获取前 10 条 Python 扫描记录
curl "http://localhost:8000/api/history?limit=10&language=Python"
```

#### DELETE /api/report/{scan_id} — 删除扫描记录

```bash
curl -X DELETE http://localhost:8000/api/report/a1b2c3d4-xxxx
```

---

## 🛡️ 检测规则

SecScan 支持检测以下 10 种安全漏洞，每条规则映射到 MITRE CWE 标准：

| 规则 ID | 漏洞类型 | CWE 编号 | 严重程度 | 检测方式 | 支持语言 |
|---------|---------|---------|---------|---------|---------|
| SC001 | SQL 注入 | CWE-89 | 🔴 Critical | AST + 正则 | Python / JS |
| SC002 | 命令注入 | CWE-78 | 🔴 Critical | AST + 正则 | Python / JS |
| SC003 | XSS 跨站脚本 | CWE-79 | 🟠 High | AST + 正则 | Python / JS |
| SC004 | 硬编码密钥 | CWE-798 | 🟠 High | AST + 正则 | Python / JS |
| SC005 | 路径遍历 | CWE-22 | 🟠 High | AST + 正则 | Python / JS |
| SC006 | 不安全的反序列化 | CWE-502 | 🔴 Critical | AST + 正则 | Python / JS |
| SC007 | 弱加密算法 | CWE-327 | 🟠 High | AST + 正则 | Python / JS |
| SC008 | SSRF 服务端请求伪造 | CWE-918 | 🟠 High | AST + 正则 | Python / JS |
| SC009 | 敏感信息泄露 | CWE-532 | 🟡 Medium | AST + 正则 | Python / JS |
| SC010 | 不安全的随机数 | CWE-330 | 🟡 Medium | AST + 正则 | Python / JS |

### 严重程度说明

| 级别 | 含义 | 典型漏洞 |
|------|------|---------|
| 🔴 **Critical** | 严重 — 可被远程利用，直接导致系统被攻破 | SQL 注入、命令注入、不安全的反序列化 |
| 🟠 **High** | 高危 — 可导致敏感数据泄露或权限提升 | XSS、硬编码密钥、路径遍历、弱加密、SSRF |
| 🟡 **Medium** | 中危 — 需要特定条件才能利用 | 敏感信息泄露、不安全的随机数 |
| 🔵 **Low** | 低危 — 影响有限 | — |
| ⚪ **Info** | 信息 — 最佳实践建议 | 语法错误等 |

### RAG 知识库

每种漏洞类型对应一份详细的修复指南文档（共 10 份），存放在 `app/data/security_kb/` 目录下：

```
app/data/security_kb/
├── SC001_SQL注入修复指南.md
├── SC002_命令注入修复指南.md
├── SC003_XSS修复指南.md
├── SC004_硬编码密钥修复指南.md
├── SC005_路径遍历修复指南.md
├── SC006_不安全反序列化修复指南.md
├── SC007_弱加密修复指南.md
├── SC008_SSRF修复指南.md
├── SC009_信息泄露修复指南.md
└── SC010_不安全随机数修复指南.md
```

扫描时，RAG 模块会从知识库中检索与漏洞最相关的内容，增强原始修复建议，提供更详细的修复指导。

---

## 🏗️ 项目架构

```
secscan/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口（健康检查 + 前端静态服务）
│   ├── api/
│   │   ├── __init__.py
│   │   ├── scan.py             # POST /api/scan — 文件上传扫描
│   │   └── report.py           # GET /api/report + GET /api/history + DELETE
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── analyzer.py          # Python AST 分析器（基于 ast.NodeVisitor）
│   │   ├── rules.py             # 漏洞规则定义（10 种 + 语法错误规则 SC000）
│   │   ├── scanner.py           # 扫描调度器（AST + 正则协调 + RAG 增强 + DB 持久化）
│   │   └── severity.py          # 严重程度评级枚举
│   ├── models/
│   │   ├── __init__.py
│   │   └── scan_result.py       # Pydantic 数据模型（ScanResult / Vulnerability / ScanSummary）
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── knowledge_base.py    # 安全知识库（文档加载 + 分块）
│   │   ├── retriever.py         # 向量检索器（TF-IDF + 余弦相似度）
│   │   └── advisor.py           # 修复建议生成器（RAG 增强整合）
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py          # SQLAlchemy 引擎管理（SQLite，支持自定义路径）
│   │   ├── models.py            # ORM 模型（ScanRecord / VulnerabilityRecord）
│   │   └── crud.py              # 数据库 CRUD 操作
│   └── data/
│       └── security_kb/         # 10 份漏洞修复知识文档（SC001-SC010）
├── frontend/
│   ├── index.html               # Web 界面（拖拽上传 / 代码粘贴 / 可视化图表）
│   ├── styles.css               # 样式表
│   └── app.js                   # 前端逻辑（API 调用 / 图表渲染 / 报告导出）
├── tests/
│   ├── conftest.py              # pytest 配置与夹具
│   ├── test_scanner.py           # 扫描引擎测试（32 个用例）
│   ├── test_database.py          # 数据库测试（25 个用例）
│   ├── test_rag.py               # RAG 模块测试（43 个用例）
│   └── samples/                  # 测试样本代码
├── k8s/
│   └── deployment.yaml           # Kubernetes 部署清单（8 个资源）
├── .github/workflows/
│   └── ci.yml                    # GitHub Actions CI/CD 流水线
├── Dockerfile                    # 多阶段构建生产级镜像
├── docker-compose.yml            # 多服务编排（应用 + PostgreSQL + ChromaDB）
├── docker-compose.override.yml   # 开发环境覆盖（热重载 + 调试端口）
├── .dockerignore
├── .env.example                  # 环境变量模板
├── requirements.txt
├── start.sh                      # Linux/macOS 一键启动脚本
├── start.bat                     # Windows 一键启动脚本
├── VERSION
├── LICENSE
└── README.md
```

### 系统架构图

```
                    ┌──────────────┐
                    │   Web 前端    │  index.html + app.js + styles.css
                    │  (拖拽/粘贴)  │
                    └──────┬───────┘
                           │ HTTP
                    ┌──────▼───────┐
                    │   FastAPI    │  main.py
                    │   (uvicorn)  │
                    └──┬───┬───┬───┘
           ┌───────────┘   │   └───────────┐
    ┌──────▼──────┐  ┌─────▼─────┐  ┌───────▼───────┐
    │  /api/scan  │  │/api/report│  │ /api/history  │
    │  文件上传    │  │ 报告查询   │  │ 历史列表/删除  │
    └──────┬──────┘  └─────┬─────┘  └───────┬───────┘
           │               │               │
    ┌──────▼───────────────▼───────────────▼───────┐
    │              Scanner 扫描调度器               │
    │  ┌─────────────────────────────────────┐      │
    │  │  Python AST 分析器 (ast.NodeVisitor)│      │
    │  ┌─────────────────────────────────────┐      │
    │  │  JavaScript 正则匹配 (10条规则)      │      │
    │  ┌─────────────────────────────────────┐      │
    │  │  RAG 修复建议增强 (TF-IDF 检索)     │      │
    │  └─────────────────────────────────────┘      │
    └──────────────────┬───────────────────────────┘
                       │ SQLAlchemy ORM
               ┌───────▼────────┐
               │   SQLite 数据库  │  data/secscan.db
               │  (扫描记录持久化) │
               └────────────────┘
```

---

## ⚙️ 配置说明

### 环境变量（.env）

复制 `.env.example` 为 `.env` 后按需修改：

```bash
cp .env.example .env
```

| 变量名 | 默认值 | 说明 |
|--------|-------|------|
| `APP_PORT` | `8000` | 应用对外端口 |
| `ENVIRONMENT` | `production` | 运行环境（`production` / `development`） |
| `DEBUG` | `false` | 是否开启调试模式 |
| `POSTGRES_USER` | `secscan` | PostgreSQL 用户名 |
| `POSTGRES_PASSWORD` | — | PostgreSQL 密码（**必须修改**） |
| `POSTGRES_DB` | `secscan_db` | PostgreSQL 数据库名 |
| `DATABASE_URL` | — | 数据库连接字符串 |
| `CHROMA_HOST` | `chromadb` | ChromaDB 向量数据库地址 |
| `CHROMA_PORT` | `8000` | ChromaDB 端口 |
| `SECRET_KEY` | — | 应用密钥（**必须修改为随机强密钥**） |
| `CORS_ORIGINS` | — | CORS 允许的来源，逗号分隔 |
| `LOG_LEVEL` | `info` | 日志级别（`debug` / `info` / `warning` / `error`） |
| `SECSCAN_DB_PATH` | `data/secscan.db` | SQLite 数据库文件路径 |

> **⚠️ 安全提示：** 生产环境务必修改 `POSTGRES_PASSWORD` 和 `SECRET_KEY`，不要使用默认值！

### 本地开发（SQLite 模式）

本地 pip 启动时，应用默认使用 SQLite，无需额外配置。数据库文件自动创建在 `data/secscan.db`。

---

## 📸 截图

> Web 界面截图占位（后续补充）

| 上传扫描 | 扫描结果 |
|---------|---------|
| *待补充* | *待补充* |

---

## 🧪 运行测试

```bash
cd secscan

# 运行全部测试
python -m pytest tests/ -v

# 运行特定测试模块
python -m pytest tests/test_scanner.py -v    # 扫描引擎（32 个用例）
python -m pytest tests/test_database.py -v   # 数据库（25 个用例）
python -m pytest tests/test_rag.py -v         # RAG 模块（43 个用例）

# 简洁模式
python -m pytest tests/ -q

# 带覆盖率
python -m pytest tests/ --cov=app --cov-report=term-missing
```

当前共 **100 个测试用例**，覆盖扫描引擎、数据库操作和 RAG 检索模块。

---

## 🛠️ 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| **Web 框架** | FastAPI | 高性能异步 Web 框架，自动生成 API 文档 |
| **ASGI 服务器** | Uvicorn | 基于 uvloop 的高性能 ASGI 实现 |
| **数据验证** | Pydantic v2 | 类型安全的数据模型和序列化 |
| **静态分析** | Python AST | 标准库 `ast` 模块，抽象语法树分析 |
| **RAG 检索** | TF-IDF + 余弦相似度 | 纯 Python 实现，无需外部向量数据库 |
| **数据库** | SQLAlchemy + SQLite | ORM 映射 + 轻量级嵌入式数据库 |
| **前端** | 原生 HTML / CSS / JavaScript | 无框架依赖，Chart.js 图表 |
| **容器化** | Docker + Docker Compose | 多阶段构建、多服务编排 |
| **编排** | Kubernetes | 完整 K8s 部署清单（HPA 自动扩缩容） |
| **CI/CD** | GitHub Actions | Lint → 矩阵测试 → 构建 → 推送 |

---

## 👨‍💻 开发指南

### 项目结构约定

- `app/engine/` — 核心扫描引擎，规则定义在此
- `app/rag/` — RAG 模块，知识库管理与检索
- `app/db/` — 数据库层，ORM 模型与 CRUD
- `app/api/` — API 路由层
- `tests/` — 测试代码，使用 pytest

### 添加新的检测规则

1. 在 `app/engine/rules.py` 的 `RULES` 字典中添加新的 `Rule` 对象
2. 在 `app/engine/analyzer.py` 中添加对应的 AST 检测方法（Python）
3. 在 `app/engine/scanner.py` 的 `JS_PATTERNS` 列表中添加正则规则（JavaScript）
4. 在 `app/data/security_kb/` 中添加对应的修复指南文档
5. 在 `tests/test_scanner.py` 中添加测试用例

### 代码风格

- 行宽限制：100 字符
- 使用 4 空格缩进
- 所有公开函数和类需有文档字符串
- 提交前运行 `flake8 . --max-line-length=100 --extend-ignore=E203,W503`

### 贡献流程

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 编写代码并添加测试
4. 确保测试通过：`python -m pytest tests/ -q`
5. 提交代码：`git commit -m "feat: 添加 XXX 功能"`
6. 推送分支：`git push origin feature/your-feature`
7. 提交 Pull Request

---

## ❓ 常见问题

### Q: 端口 8000 被占用怎么办？

```bash
# 方法 1：换端口启动
python -m uvicorn app.main:app --port 8080

# 方法 2：查找并释放端口（Linux/macOS）
lsof -i :8000        # 查看占用进程
kill -9 <PID>        # 终止进程

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Q: 启动脚本报 Python 版本不够？

SecScan 要求 Python ≥ 3.10。请升级 Python 版本：
- 官网下载：https://www.python.org/downloads/
- 推荐使用 [pyenv](https://github.com/pyenv/pyenv) 管理多版本 Python

### Q: Docker 构建很慢？

```bash
# 使用 BuildKit 加速
DOCKER_BUILDKIT=1 docker compose build

# 清理构建缓存重来
docker builder prune -f
```

### Q: 扫描结果显示 "语法错误"？

文件可能包含语法错误，AST 分析器无法解析。请先修复语法错误后重新扫描。

### Q: 如何切换为 PostgreSQL？

Docker Compose 模式已内置 PostgreSQL。本地开发可设置环境变量：
```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/secscan_db"
```

---

## 📄 License

本项目基于 [MIT License](LICENSE) 开源协议。

---

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) — 高性能 Python Web 框架
- [SQLAlchemy](https://www.sqlalchemy.org/) — Python SQL 工具包
- [MITRE CWE](https://cwe.mitre.org/) — 通用弱点枚举标准
- [OWASP](https://owasp.org/) — 开放 Web 应用安全项目

---

<p align="center">
  SecScan v2.0.0 — 让代码更安全 🛡️
</p>
