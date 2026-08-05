# 🧪 AI Fullstack Lab

> AI 全栈开发学习与实践仓库，涵盖 **496 道编程练习** + **SecScan** AI 驱动代码安全审计平台 v2.0.0

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Exercises](https://img.shields.io/badge/Exercises-496-brightgreen)
![Languages](https://img.shields.io/badge/Languages-25+-orange)
![Tests](https://img.shields.io/badge/Tests-100%20passed-success)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Version](https://img.shields.io/badge/Version-2.0.0-red)

---

## 📂 目录结构

```
ai-fullstack-lab/
├── python_exercises/          # Python 全栈练习（30 文件 · 496 题）
│   ├── 01_oop_basics.py            # 面向对象编程
│   ├── 02_async_basics.py           # 异步编程
│   ├── 03_data_structures.py        # 数据结构
│   ├── 04_numpy_basics.py           # NumPy 科学计算
│   ├── 05_pandas_basics.py          # Pandas 数据处理
│   ├── 06_matplotlib_basics.py      # Matplotlib 可视化
│   ├── 07_math_basics.py            # 数学基础
│   ├── 08_linux_basics.py           # Linux 系统操作
│   ├── 09_ml_basics.py              # 机器学习基础
│   ├── 10_dl_basics.py              # 深度学习基础
│   ├── 11_fastapi_basics.py         # FastAPI 后端开发
│   ├── 12_database_basics.py        # 数据库工程
│   ├── 13_frontend_fullstack.py     # 前端全栈开发
│   ├── 14_llm_basics.py             # 大语言模型
│   ├── 15_agent_basics.py           # AI Agent 开发
│   ├── 16_multimodal_basics.py     # 多模态 AI
│   ├── 17_mlops_basics.py           # MLOps 机器学习运维
│   ├── 18_container_deploy.py       # 容器化部署
│   ├── 19_cloud_platform.py         # 云平台实践
│   ├── 20_database_engineering.py   # 数据库工程深化
│   ├── 21_embodied_ai.py            # 具身智能
│   ├── 23_security_attack.py        # 安全攻击篇
│   ├── 24_design_patterns.py       # 设计模式
│   ├── 25_system_design.py          # 系统设计
│   ├── 26_security_defense.py       # 安全防御篇
│   ├── 27_rag_system.py             # RAG 检索增强生成
│   ├── 28_devops_practice.py        # DevOps 实践
│   ├── 01~03_*_extensions.py        # OOP/异步/数据结构扩展
│   └── charts/                      # 14 张可视化图表
│
├── lang_exercises/            # 22 种编程语言练习（22 文件）
│   ├── 13_rust.rs                  # Rust — 系统级安全语言
│   ├── 14_go.go                    # Go — 并发服务
│   ├── 15_cpp.cpp                  # C++ — 高性能
│   ├── 16_java.java                 # Java — 企业级
│   ├── 17_javascript.js            # JavaScript — Web 之王
│   ├── 18_csharp.cs                # C# — .NET 生态
│   ├── 19_ruby.rb                  # Ruby — 优雅脚本
│   ├── 20_swift.swift               # Swift — Apple 生态
│   ├── 21_kotlin.kt                # Kotlin — JVM 现代
│   ├── 22_r.r                      # R — 统计分析
│   ├── 23_julia.jl                 # Julia — 科学计算
│   ├── 24_clojure.clj              # Clojure — Lisp on JVM
│   ├── 24_elixir.exs               # Elixir — 并发函数式
│   ├── 24_erlang.erl               # Erlang — 电信级容错
│   ├── 24_haskell.hs               # Haskell — 纯函数式
│   ├── 24_scala.scala              # Scala — OOP + FP
│   ├── 25_dart.dart                # Dart — 跨平台
│   ├── 25_lua.lua                  # Lua — 嵌入式脚本
│   ├── 25_nim.nim                  # Nim — 系统级高效
│   ├── 25_perl.pl                  # Perl — 文本处理
│   ├── 25_php.php                  # PHP — Web 后端
│   └── 25_zig.zig                  # Zig — 系统级现代
│
├── ts_exercises/              # TypeScript 全栈练习（5 文件）
│   ├── q11_type_basics.ts          # 类型基础
│   ├── q12_generics_advanced.ts     # 泛型进阶
│   ├── q13_typescript_react.ts      # TS + React
│   ├── q14_typescript_ai_sdk.ts    # TS + AI SDK
│   └── q15_fullstack_type_safety.ts # 全栈类型安全
│
├── ai_math/                   # AI 数学基础（83 文件 · 含 76 张可视化图）
│   ├── 26_linear_algebra_prob_stats.py   # 线性代数 + 概率统计（40 题）
│   ├── 27_calculus_optimization.py       # 微积分 + 优化理论（40 题）
│   ├── 28_info_theory_numerical.py       # 信息论 + 数值方法（40 题）
│   ├── 29_ml_model_math.py               # ML 模型数学（15 个模型从零手写）
│   ├── 30_dl_model_math.py               # DL 模型数学（CNN/RNN/LSTM/Transformer/GAN/Diffusion）
│   ├── figures_ml/                      # 15 张 ML 可视化
│   ├── figures_dl/                      # 15 张 DL 可视化
│   └── figures_rag/                     # 8 张 RAG 可视化
│
├── c_exercises/              # C 语言底层练习（27 文件 · 20 题）
│   ├── q01_types_io.c              # 类型与 I/O
│   ├── q02_control_flow.c          # 控制流
│   ├── q03_functions_scope.c       # 函数与作用域
│   ├── q04_arrays_strings.c        # 数组与字符串
│   ├── q05_preprocessor.c          # 预处理器
│   ├── q06_pointer_basics.c        # 指针基础
│   ├── q07_pointer_array.c         # 指针与数组
│   ├── q08_dynamic_memory.c        # 动态内存管理
│   ├── q09_function_pointers.c     # 函数指针
│   ├── q10_strings_pointers.c      # 字符串与指针
│   ├── q11_memory_layout.c         # 内存布局
│   ├── q12_struct_union.c          # 结构体与联合
│   ├── q13_linked_list.c           # 链表与内存池
│   ├── q14_file_io.c               # 文件 I/O
│   ├── q15_multifile.c             # 多文件工程
│   ├── q16_process_exec.c          # 进程与 exec
│   ├── q17_signal_handling.c       # 信号处理
│   ├── q18_file_descriptors.c      # 文件描述符
│   ├── q19_web_server.c            # C 语言 Web 服务器
│   ├── q20_c_python_interop.c      # C 与 Python 互操作
│   ├── math_utils.c / .h           # 数学工具库
│   ├── string_utils.c / .h         # 字符串工具库
│   ├── Makefile                     # 构建配置
│   └── run_all.sh                  # 一键编译运行
│
├── devops/                    # DevOps 配置文件（13 文件）
│   ├── Dockerfile                  # 多阶段构建
│   ├── docker-compose.yml          # 编排配置
│   ├── docker-compose.override.yml # 本地覆盖
│   ├── ci.yml                      # GitHub Actions CI
│   ├── prometheus.yml              # 监控配置
│   ├── grafana_dashboard.json      # 仪表盘
│   ├── alerting_rules.yml         # 告警规则
│   ├── .env.example                # 环境变量模板
│   ├── requirements.txt            # Python 依赖
│   └── k8s/                        # Kubernetes 部署
│
├── secscan/                   # 🔒 SecScan 安全审计平台 v2.0.0（44 文件）
│   ├── app/                        # 后端应用
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── engine/                 # 审计引擎（AST 分析器 + 10 种漏洞规则）
│   │   ├── rag/                    # RAG 知识库（TF-IDF 检索 + 修复建议）
│   │   ├── api/                    # REST API（扫描 + 报告）
│   │   ├── db/                     # SQLite 持久化
│   │   ├── models/                 # 数据模型
│   │   └── data/security_kb/       # 10 份安全修复指南
│   ├── frontend/                   # Web 前端（深色主题 + 拖拽上传 + Chart.js）
│   ├── tests/                      # 100 个测试用例
│   ├── Dockerfile + docker-compose.yml
│   ├── k8s/deployment.yaml         # K8s 部署
│   ├── .github/workflows/ci.yml    # CI/CD
│   ├── start.sh / start.bat        # 一键启动
│   └── README.md                   # 详细文档
│
├── skills/                    # 技能封装（21 文件 · 8 个技能）
│   ├── security-audit-agent/       # 代码安全审计 Agent
│   ├── bug-bounty-knowledge-base/  # Bug Bounty 知识库
│   ├── bug-bounty-recon-workflow/  # Recon 自动化工作流
│   ├── rag-exercise-collection/    # RAG 练习集
│   ├── card-game-balance-tester/   # 卡牌游戏平衡测试
│   ├── card-data-validator/        # 卡牌数据验证
│   ├── grill-me/                   # 苏格拉底式方案追问
│   └── humanizer/                  # AI 写作去味
│
├── docs/                      # 项目文档（3 文件）
│   ├── AI全栈学习路线图.md
│   ├── AI全栈能力地图_重排版.md
│   └── 知识体系图谱.md
│
├── experiences/               # 学习心得（4 文件）
│
├── .gitignore
├── LICENSE
└── README.md
```

---

## ✨ 项目亮点

### 🔒 SecScan v2.0.0 — AI 驱动代码安全审计平台

一个完整的端到端安全审计工具，从代码上传到漏洞报告全流程自动化：

| 模块 | 技术实现 | 亮点 |
|------|---------|------|
| 审计引擎 | Python AST 分析器 + 10 种漏洞规则 | SQL 注入 / 命令注入 / XSS / 硬编码密钥 / 路径遍历 / 反序列化 / 弱加密 / SSRF / 信息泄露 / 不安全随机数 |
| RAG 知识库 | TF-IDF 向量检索 + 10 份修复文档 | 检测到漏洞后自动匹配修复指南，生成可执行建议 |
| Web 前端 | 原生 HTML/CSS/JS + Chart.js | 深色主题 / 拖拽上传 / 漏洞分布饼图 / 历史记录 |
| 数据持久化 | SQLite + SQLAlchemy | 扫描历史 / 分页查询 / 数据导出 |
| 容器化部署 | Docker 多阶段构建 + K8s + GitHub Actions | 一键 `docker compose up` / CI/CD 流水线 |
| 测试 | pytest | **100 个测试用例全部通过** |

```bash
# 快速启动
cd secscan
bash start.sh        # Linux/macOS
start.bat            # Windows
# 浏览器打开 http://localhost:8000
```

> 📖 详细文档见 [secscan/README.md](secscan/README.md)

### 📚 496 道练习覆盖全栈

从 Python 基础到具身智能，从 C 语言底层到 25 种编程语言，从安全攻防到 DevOps 实践 —— 一站式覆盖 AI 全栈开发所需的所有技能领域。

### 🧮 纯 NumPy 实现 AI 算法

所有 ML/DL 模型均使用 **纯 NumPy 从零手写**，不依赖 PyTorch / TensorFlow。涵盖：
- **ML**：线性回归 / 逻辑回归 / SVM / 决策树 / 随机森林 / GBDT / K-Means / 朴素贝叶斯 / PCA / LDA / KNN / 感知机
- **DL**：MLP / CNN / RNN / LSTM / GRU / Attention / Transformer / Seq2Seq / GAN / Diffusion

### 🌍 25+ 种编程语言

系统级（C / Rust / Go / C++ / Zig / Nim）、企业级（Java / C# / Kotlin / Swift）、Web（JavaScript / TypeScript / Ruby / PHP / Dart）、数据科学（R / Julia）、函数式（Haskell / Elixir / Scala / Clojure / Erlang）、脚本（Lua / Perl）—— 每种语言配套完整练习。

---

## 🗺️ 学习路线图

### 轨道 1 ｜ 编程语言（~221 题）

> Python → C → 系统级语言 → 企业级 → 脚本 → 函数式 → TypeScript

| 文件 | 语言 | 题数 | 内容 |
|------|------|------|------|
| `python_exercises/01~03` | Python | 12+ | OOP / 异步 / 数据结构 |
| `python_exercises/24~25` | Python | 20 | 设计模式 / 系统设计 |
| `c_exercises/q01~q20` | C | 20 | 从类型 I/O 到 C-Python 互操作 |
| `lang_exercises/13~25` | 22 种语言 | 185 | 系统级 / 企业级 / Web / 函数式 / 脚本 |
| `ts_exercises/q11~q15` | TypeScript | 5 | 类型 / 泛型 / React / AI SDK / 全栈安全 |

### 轨道 2 ｜ AI 与数学（~165 题）

> 数学基础 → ML/DL → AI 数学深化 → 前沿 → 具身 AI

| 文件 | 内容 | 题数 |
|------|------|------|
| `python_exercises/04~06` | NumPy / Pandas / Matplotlib | 15 |
| `python_exercises/07` | 数学基础 | 15 |
| `python_exercises/09~10` | 机器学习 / 深度学习基础 | 30 |
| `python_exercises/14~16` | LLM / Agent / 多模态 | 30 |
| `python_exercises/21` | 具身智能 | 15 |
| `python_exercises/27` | RAG 检索增强生成 | 10 |
| `ai_math/26~30` | 线性代数 / 微积分 / 信息论 / ML / DL 数学 | 50 |

### 轨道 3 ｜ 工程与全栈（~60 题）

> 全栈开发 → 数据库工程 → 工程进阶 → DevOps

| 文件 | 内容 | 题数 |
|------|------|------|
| `python_exercises/08` | Linux 系统操作 | 5 |
| `python_exercises/11~13` | FastAPI / 数据库 / 前端全栈 | 15 |
| `python_exercises/17~19` | MLOps / 容器部署 / 云平台 | 15 |
| `python_exercises/20` | 数据库工程深化 | 15 |
| `python_exercises/28` | DevOps 实践 | 5 |
| `devops/` | Docker / K8s / CI / 监控配置 | 5 |

### 轨道 4 ｜ 安全攻防（~50 题）

> 攻击技术 → 防御技术 → Bug Bounty 实战

| 文件 | 内容 | 题数 |
|------|------|------|
| `python_exercises/23` | 安全攻击（注入 / XSS / SSRF / 反序列化 / 攻击链） | 15 |
| `python_exercises/26` | 安全防御（输入验证 / 权限控制 / 加密 / 审计） | 15 |
| `secscan/` | SecScan 安全审计平台实战项目 | 20 |

### 轨道 5 ｜ 技能产出（8 个技能）

> 将学习成果封装为可复用技能

| 技能 | 说明 |
|------|------|
| `skills/security-audit-agent` | Python/C 代码安全扫描，检测 15 类安全漏洞 |
| `skills/bug-bounty-knowledge-base` | Bug Bounty 完整知识库（工具链 / 漏洞类型 / 报告写作） |
| `skills/bug-bounty-recon-workflow` | Recon 自动化侦察（subfinder/httpx/nuclei/ffuf） |
| `skills/rag-exercise-collection` | RAG 实战练习集（嵌入 / 检索 / 分块 / 评估） |
| `skills/card-game-balance-tester` | 卡牌游戏数值平衡测试工具 |
| `skills/card-data-validator` | 卡牌 JSON 数据验证器 |
| `skills/grill-me` | 苏格拉底式方案追问工具 |
| `skills/humanizer` | AI 写作痕迹检测与修复 |

---

## 📊 统计数据

| 指标 | 数值 |
|------|------|
| 总代码行数 | ~73,000 行 |
| 文件总数 | 255 |
| 练习题数 | 496 |
| 编程语言 | 25+ |
| 测试用例 | 100 |
| 可视化图表 | 90+ |
| SecScan 版本 | v2.0.0 |

### 语言分布

| 语言 | 文件数 | 代码行数 |
|------|--------|---------|
| Python | 35+ | ~38,000 |
| TypeScript | 5 | ~1,900 |
| C | 20+ | ~3,300 |
| Rust / Go / C++ / Java / JS / C# | 6 | ~9,500 |
| Ruby / Swift / Kotlin / R / Julia | 5 | ~4,300 |
| Haskell / Scala / Clojure / Elixir / Erlang | 5 | ~6,500 |
| Dart / Lua / Nim / Perl / PHP / Zig | 6 | ~4,200 |
| HTML / CSS / JavaScript (SecScan 前端) | 3 | ~1,400 |
| YAML / Dockerfile / K8s | 13+ | ~1,600 |

---

## 🛠️ 技术栈

| 领域 | 技术 |
|------|------|
| **核心语言** | Python 3.13 / C / TypeScript / Rust / Go / C++ / Java |
| **AI / ML** | NumPy / Pandas / Matplotlib / scikit-learn |
| **DL（纯手写）** | MLP / CNN / RNN / LSTM / Transformer / GAN / Diffusion |
| **LLM / Agent** | LangChain / RAG / Prompt Engineering / Function Calling |
| **后端** | FastAPI / SQLAlchemy / Pydantic / Uvicorn |
| **前端** | HTML5 / CSS3 / JavaScript / Chart.js |
| **数据库** | SQLite / SQLAlchemy ORM |
| **DevOps** | Docker / Docker Compose / Kubernetes / GitHub Actions |
| **安全** | AST 分析 / TF-IDF 检索 / 漏洞规则引擎 |
| **测试** | pytest / httpx |
| **监控** | Prometheus / Grafana |

---

## 📄 License

[MIT License](LICENSE) © 2026 [Z4OR-cyber](https://github.com/Z4OR-cyber)

---

## 👤 作者

**Z4OR-cyber** — AI 全栈开发者 / 安全研究员

- GitHub: [@Z4OR-cyber](https://github.com/Z4OR-cyber)

> ⭐ 如果这个仓库对你有帮助，欢迎 Star！
