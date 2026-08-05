# SecScan：用Python构建AI驱动的代码安全审计平台

> **摘要**：本文记录了SecScan——一个AI驱动的代码安全审计平台的完整开发过程。平台基于FastAPI构建，使用Python AST分析器检测10种安全漏洞，并通过RAG知识库增强修复建议。文章涵盖架构设计、AST漏洞检测规则实现、RAG增强模块、SQLite数据持久化、Docker多阶段构建及K8s部署，完整呈现从0到1的6阶段开发历程。

**关键词**：代码安全审计、AST分析、FastAPI、RAG、Docker、Kubernetes

---

## 一、项目背景与目标

在安全开发实践中，代码审计是发现漏洞的第一道防线。市面上的安全扫描工具要么价格昂贵，要么黑盒运行无法定制规则。SecScan的目标是：

- **开源透明**：所有检测规则可见可改
- **多语言支持**：Python用AST精确分析，JavaScript用正则快速覆盖
- **AI增强**：RAG知识库为每个漏洞提供详细修复指导
- **生产就绪**：Docker容器化 + K8s部署 + CI/CD流水线

### 技术栈选型

| 层级 | 技术 | 选型理由 |
|------|------|---------|
| Web框架 | FastAPI | 异步高性能、自动生成OpenAPI文档 |
| 代码分析 | Python ast模块 | 标准库、无需安装、理解代码结构 |
| 知识增强 | RAG（TF-IDF + 向量检索） | 无需LLM API即可增强建议 |
| 数据持久化 | SQLAlchemy + SQLite | 轻量级、零配置、支持迁移到PostgreSQL |
| 容器化 | Docker多阶段构建 | 镜像体积小、非root运行 |
| 编排部署 | Kubernetes | 滚动更新、健康检查、自动扩缩容 |

---

## 二、项目架构设计

### 2.1 整体架构

```
┌──────────────────────────────────────────────┐
│                   FastAPI                     │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │ /api/scan│  │/api/report│  │/api/history│ │
│  └────┬─────┘  └────┬─────┘  └─────┬──────┘ │
│       │              │               │       │
│  ┌────▼──────────────▼───────────────▼─────┐ │
│  │           Scanner（扫描调度器）          │ │
│  │  ┌─────────────┐  ┌──────────────────┐ │ │
│  │  │PythonAST    │  │JS Regex Patterns │ │ │
│  │  │Analyzer     │  │                  │ │ │
│  │  └──────┬──────┘  └────────┬─────────┘ │ │
│  │         │                  │           │ │
│  │  ┌──────▼──────────────────▼─────────┐ │ │
│  │  │        Rules（规则引擎）           │ │ │
│  │  │   SC001~SC010 漏洞检测规则        │ │ │
│  │  └───────────────────────────────────┘ │ │
│  └────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────┐ │
│  │         RAG FixAdvisor                 │ │
│  │  Knowledge Base → VectorRetriever      │ │
│  │  → Enhanced Fix Suggestion             │ │
│  └────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────┐ │
│  │     SQLite (SQLAlchemy ORM)            │ │
│  └────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

### 2.2 目录结构

```
secscan/
├── app/
│   ├── main.py              # FastAPI入口
│   ├── api/
│   │   ├── scan.py           # 扫描API
│   │   └── report.py         # 报告API
│   ├── engine/
│   │   ├── analyzer.py       # Python AST分析器
│   │   ├── rules.py          # 漏洞规则定义
│   │   ├── scanner.py        # 扫描调度器
│   │   └── severity.py       # 严重程度枚举
│   ├── rag/
│   │   ├── advisor.py        # 修复建议生成器
│   │   ├── knowledge_base.py # 安全知识库
│   │   └── retriever.py      # 向量检索器
│   ├── db/
│   │   ├── database.py       # 数据库连接
│   │   ├── models.py         # ORM模型
│   │   └── crud.py           # 增删改查
│   ├── models/
│   │   └── scan_result.py    # 数据模型
│   └── data/
│       └── security_kb/      # 10篇修复指南文档
├── Dockerfile
├── .github/workflows/ci.yml
└── requirements.txt
```

---

## 三、10种漏洞检测规则实现

### 3.1 规则定义

每条规则包含规则ID、漏洞类型、CWE编号、严重程度、描述和修复建议。使用Python `dataclass` 定义：

```python
@dataclass(frozen=True)
class Rule:
    rule_id: str        # SC001~SC010
    vuln_type: str      # 漏洞类型中文名称
    cwe_id: str         # CWE编号
    severity: Severity  # CRITICAL/HIGH/MEDIUM/LOW/INFO
    description: str    # 漏洞描述
    fix_suggestion: str # 修复建议

RULES: Dict[str, Rule] = {
    "SC001": Rule(
        rule_id="SC001",
        vuln_type="SQL注入",
        cwe_id="CWE-89",
        severity=Severity.CRITICAL,
        description="检测到通过字符串拼接构造SQL语句，攻击者可注入恶意SQL代码",
        fix_suggestion="使用参数化查询代替字符串拼接。例如：\n"
                       "  cursor.execute('SELECT * FROM users WHERE name = ?', (username,))",
    ),
    "SC002": Rule(
        rule_id="SC002",
        vuln_type="命令注入",
        cwe_id="CWE-78",
        severity=Severity.CRITICAL,
        description="检测到使用os.system/subprocess执行包含用户输入的命令",
        fix_suggestion="使用subprocess.run()并传入参数列表(非字符串拼接)，避免shell=True",
    ),
    # ... SC003~SC010 同理
}
```

完整规则列表：

| 规则ID | 漏洞类型 | CWE | 严重程度 |
|--------|---------|-----|---------|
| SC001 | SQL注入 | CWE-89 | CRITICAL |
| SC002 | 命令注入 | CWE-78 | CRITICAL |
| SC003 | XSS跨站脚本 | CWE-79 | HIGH |
| SC004 | 硬编码密钥 | CWE-798 | HIGH |
| SC005 | 路径遍历 | CWE-22 | HIGH |
| SC006 | 不安全反序列化 | CWE-502 | CRITICAL |
| SC007 | 弱加密算法 | CWE-327 | HIGH |
| SC008 | SSRF | CWE-918 | HIGH |
| SC009 | 敏感信息泄露 | CWE-532 | MEDIUM |
| SC010 | 不安全随机数 | CWE-330 | MEDIUM |

### 3.2 Python AST分析器

SecScan的核心是`PythonASTAnalyzer`，继承`ast.NodeVisitor`，通过遍历AST节点检测漏洞。相比正则匹配，AST分析能理解代码结构，大幅减少误报。

```python
class PythonASTAnalyzer(ast.NodeVisitor):
    # 危险函数调用集合
    DANGEROUS_COMMAND_CALLS = {
        'os.system', 'os.popen',
        'subprocess.call', 'subprocess.run', 'subprocess.Popen',
        'subprocess.check_output', 'subprocess.check_call',
    }
    DANGEROUS_DESERIALIZE_CALLS = {
        'pickle.loads', 'pickle.load', 'cPickle.loads', 'cPickle.load',
        'eval', 'exec', 'yaml.load', 'marshal.loads', 'marshal.load',
    }
    WEAK_CRYPTO_CALLS = {'hashlib.md5', 'hashlib.sha1'}
    SSRF_CALLS = {
        'requests.get', 'requests.post', 'requests.put',
        'requests.delete', 'requests.request',
        'urllib.request.urlopen', 'httpx.get', 'httpx.post',
    }
    XSS_CALLS = {'render_template_string', 'mark_safe'}

    def analyze(self) -> List[Dict[str, Any]]:
        try:
            tree = ast.parse(self.source)
        except SyntaxError as e:
            self._add_finding("SC000", e.lineno or 1)
            return self.findings
        self.visit(tree)
        return self.findings

    def visit_Call(self, node: ast.Call):
        """访问函数调用节点，检测各类漏洞"""
        self._check_sql_injection_call(node)
        self._check_command_injection(node)
        self._check_xss(node)
        self._check_path_traversal(node)
        self._check_deserialization(node)
        self._check_weak_crypto(node)
        self._check_ssrf(node)
        self._check_info_leakage(node)
        self._check_insecure_random(node)
        self.generic_visit(node)
```

### 3.3 SQL注入检测详解

SQL注入检测有两种模式：

```python
def _check_sql_injection_call(self, node: ast.Call):
    """检测execute/executemany调用中使用字符串拼接或f-string"""
    call_name = self._get_full_name(node.func)
    if call_name.endswith('execute') or call_name.endswith('executemany'):
        if node.args and isinstance(node.args[0], (ast.BinOp, ast.JoinedStr)):
            self._add_finding("SC001", node.lineno)

def _check_sql_injection_assign(self, node: ast.Assign):
    """检测变量赋值为包含SQL关键字的拼接字符串"""
    if isinstance(node.value, (ast.BinOp, ast.JoinedStr)):
        if self._contains_sql_keyword(node.value):
            self._add_finding("SC001", node.lineno)
```

关键设计：`ast.BinOp`检测字符串拼接（`"SELECT..." + var`），`ast.JoinedStr`检测f-string（`f"SELECT...{var}"`）。`subprocess.run(["cmd", "arg"])`列表形式是安全的，不会触发误报。

### 3.4 JavaScript正则检测

对于JavaScript代码，使用正则表达式逐行扫描：

```python
JS_PATTERNS: List[tuple] = [
    # SQL注入 - 字符串拼接SQL语句
    (re.compile(r'''["'`].*(?:SELECT|INSERT|UPDATE|DELETE|DROP)\s.*["'`]\s*\+''',
                re.IGNORECASE), "SC001"),
    # 命令注入 - child_process
    (re.compile(r'child_process\.(?:exec|execSync|spawn|fork)\s*\('), "SC002"),
    # XSS - innerHTML赋值
    (re.compile(r'\.innerHTML\s*='), "SC003"),
    # 硬编码密钥
    (re.compile(
        r'(?:const|let|var)\s+\w*(?:api_key|apikey|password|secret|token)\w*\s*=\s*["\'`][^"\'`]{4,}["\'`]',
        re.IGNORECASE
    ), "SC004"),
    # 不安全反序列化 - eval
    (re.compile(r'\beval\s*\('), "SC006"),
    # 弱加密 - createHash('md5')
    (re.compile(r'''createHash\s*\(\s*["'`](?:md5|sha1)["'`]\s*\)''',
                re.IGNORECASE), "SC007"),
    # SSRF - fetch/axios使用变量URL
    (re.compile(r'(?:fetch|axios\.(?:get|post|put|delete|request))\s*\(\s*[a-zA-Z_$]'), "SC008"),
    # 不安全随机数 - Math.random()
    (re.compile(r'Math\.random\s*\(\s*\)'), "SC010"),
]
```

每条规则包含编译后的正则和对应规则ID，同一行同一规则只报告一次，避免重复。

---

## 四、RAG知识库增强修复建议

### 4.1 设计思路

传统扫描工具只报告"发现了SQL注入"，但开发者可能不知道怎么修。SecScan内置了10篇安全修复指南（Markdown格式），通过RAG检索为每个漏洞提供增强的修复建议。

### 4.2 FixAdvisor工作流程

```python
class FixAdvisor:
    def __init__(self):
        self.kb = SecurityKnowledgeBase()
        self.retriever = VectorRetriever()

    def initialize(self):
        """加载知识库并构建向量索引"""
        self.kb.load()
        chunks = self.kb.get_all_chunks()
        if chunks:
            self.retriever.build_index(chunks)

    def enhance_suggestion(self, vuln_type, description, code_snippet,
                           original_suggestion, rule_id=None):
        """增强修复建议"""
        # 构造查询文本
        query = f"{vuln_type} {description} {code_snippet}"

        # 策略1：按rule_id直接检索该漏洞类型的知识分块
        doc_chunks = self.retriever.search_by_doc(query, rule_id, top_k=3)

        # 策略2：全局检索补充
        if len(doc_chunks) < 2:
            global_results = self.retriever.search(query, top_k=3)
            # 去重后合并
            existing_ids = {c["chunk_id"] for c in doc_chunks}
            for result in global_results:
                if result["chunk_id"] not in existing_ids:
                    doc_chunks.append(result)

        # 整合原始建议和检索结果
        return self._compose_suggestion(original_suggestion, doc_chunks, vuln_type)
```

### 4.3 增强建议输出格式

```
[原始修复建议]
使用参数化查询代替字符串拼接。例如：
  cursor.execute('SELECT * FROM users WHERE name = ?', (username,))

---
[知识库参考]
来源1: [SC001_SQL注入修复指南] 参数化查询确保用户输入被当作数据而非SQL代码...
来源2: [SC001_SQL注入修复指南] ORM框架（SQLAlchemy、Django ORM）自动参数化...
```

这种双层建议——简洁的原始建议 + 详细的知识库参考——让开发者既能快速了解修复方向，又能深入理解原理。

---

## 五、扫描调度器：统一入口

`Scanner`类是整个系统的调度中心，根据文件类型选择分析策略，并持久化结果：

```python
class Scanner:
    def __init__(self):
        init_db()  # 确保数据库表已创建

    def scan_code(self, filename: str, content: str) -> ScanResult:
        # 1. 检测语言
        language = self._detect_language(filename)

        # 2. 选择分析策略
        if language == "Python":
            findings = self._scan_python(content)
        elif language == "JavaScript":
            findings = self._scan_javascript(content)
        else:
            findings = []

        # 3. 转换为模型对象
        vulnerabilities = [Vulnerability(**f) for f in findings]

        # 4. RAG增强修复建议
        self._enhance_fix_suggestions(vulnerabilities)

        # 5. 构建统计摘要
        summary = self._build_summary(vulnerabilities)

        # 6. 生成结果并持久化
        scan_id = str(uuid.uuid4())
        result = ScanResult(scan_id=scan_id, filename=filename, ...)

        db = get_session()
        try:
            crud.create_scan_result(db, result)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        return result
```

---

## 六、SQLite数据持久化

### 6.1 数据模型

使用SQLAlchemy ORM定义数据模型，支持扫描结果、漏洞列表和统计摘要的存储：

```python
# 数据库连接
engine = create_engine("sqlite:///secscan.db")
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)
```

### 6.2 API端点

```python
@router.post("/api/scan", response_model=ScanResult)
async def scan_code(request: ScanRequest):
    scanner = Scanner()
    result = scanner.scan_code(request.filename, request.content)
    return result

@router.get("/api/report/{scan_id}", response_model=ScanResult)
async def get_report(scan_id: str):
    scanner = Scanner()
    result = scanner.get_result(scan_id)
    if not result:
        raise HTTPException(status_code=404, detail="扫描结果不存在")
    return result

@router.get("/api/history")
async def get_history():
    # 获取历史扫描记录
    ...
```

选择SQLite的理由：零配置、单文件、适合中小规模应用。未来可平滑迁移到PostgreSQL——只需修改连接字符串。

---

## 七、Docker多阶段构建

### 7.1 Dockerfile设计

```dockerfile
# -------------------- 第一阶段：builder --------------------
FROM python:3.13-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# -------------------- 第二阶段：runtime --------------------
FROM python:3.13-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# 安装curl（HEALTHCHECK需要）
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 从builder复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 创建非root用户
RUN groupadd -r secscan && useradd -r -g secscan -d /app -s /sbin/nologin secscan

WORKDIR /app
COPY --chown=secscan:secscan . .
USER secscan
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 7.2 关键设计决策

| 决策 | 理由 |
|------|------|
| 多阶段构建 | builder阶段安装依赖，runtime仅复制虚拟环境，镜像体积减少50%+ |
| 虚拟环境隔离 | 避免与系统Python包冲突，便于复制到runtime阶段 |
| 先复制requirements.txt | 利用Docker层缓存，代码变更时不重新安装依赖 |
| 非root用户 | 安全最佳实践，容器逃逸时降低风险 |
| HEALTHCHECK | Docker定期检查/health端点，自动标记不健康容器 |

---

## 八、CI/CD与K8s部署

### 8.1 GitHub Actions流水线

```yaml
name: CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install flake8 pylint
      - run: flake8 . --max-line-length=100 --extend-ignore=E203,W503

  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python-version }} }
      - run: pip install -r requirements.txt pytest pytest-cov
      - run: pytest --cov=. --cov-report=xml --cov-report=term-missing

  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t secscan:latest .
```

### 8.2 K8s部署要点

K8s部署清单包含Deployment、Service、Ingress和HPA（水平Pod自动扩缩容）。关键配置：

- **滚动更新**：`maxSurge: 1, maxUnavailable: 0`，确保更新时不中断服务
- **三种探针**：startupProbe（启动检测）、readinessProbe（就绪检测）、livenessProbe（存活检测）
- **资源限制**：requests是调度依据，limits是硬上限
- **优雅终止**：`preStop: sleep 5`等待负载均衡器移除Pod

---

## 九、6阶段开发过程

### 阶段1：核心API + 安全审计引擎

搭建FastAPI框架，实现Python AST分析器和10条漏洞检测规则。建立API端点`POST /api/scan`。

### 阶段2：JavaScript支持 + 正则规则

新增JavaScript正则检测规则，实现多语言支持。扫描器根据文件扩展名自动选择分析策略。

### 阶段3：RAG知识库增强

编写10篇安全修复指南文档，实现TF-IDF向量检索器，构建FixAdvisor为每个漏洞提供增强建议。

### 阶段4：数据持久化

集成SQLAlchemy + SQLite，实现扫描结果的存储、查询、删除。支持应用重启后获取历史记录。

### 阶段5：Docker容器化

编写多阶段Dockerfile，实现非root运行、HEALTHCHECK、镜像体积优化。

### 阶段6：CI/CD + K8s部署

配置GitHub Actions流水线（lint → test → build），编写K8s部署清单（Deployment + Service + Ingress + HPA）。

---

## 十、总结

SecScan的开发过程展示了如何从零构建一个生产级安全工具：

1. **AST分析 > 正则匹配**：理解代码结构，大幅减少误报
2. **RAG增强修复建议**：不只是发现问题，更指导如何修复
3. **分层架构设计**：API层 → 引擎层 → RAG层 → 持久化层，职责清晰
4. **多语言策略**：Python用AST（精确），JavaScript用正则（覆盖广）
5. **生产级Dockerfile**：多阶段构建 + 非root + HEALTHCHECK
6. **CI/CD自动化**：lint → 矩阵测试 → 构建，每次提交自动验证

项目代码完全开源，44个文件覆盖了从API设计到容器部署的完整链路，适合作为安全工具开发的参考项目。

> **项目信息**：SecScan v2.0.0 | FastAPI + AST + RAG + Docker + K8s | 44个文件 | 6阶段开发

---

*作者：koze | AI全栈学习笔记*
