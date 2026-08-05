"""
====================================================================
DevOps 实操练习（5题）— AI 全栈学习补充
作者：koze | 仓库：ai-fullstack-lab
环境：Python 3.13.12
说明：本文件包含所有讲解文本和可运行的 Python 代码片段
      配置文件（Dockerfile/yaml 等）已保存到 devops/ 目录
====================================================================

学习目标：
  第1题：GitHub Actions CI/CD — 自动化测试与构建
  第2题：Docker 容器化 — 多阶段构建生产级镜像
  第3题：Docker Compose — 多服务编排
  第4题：Kubernetes 部署 — 应用上 K8s
  第5题：可观测性 — 日志、指标与告警

运行方式：
  python 28_devops_practice.py

配置文件位置：
  devops/
    ci.yml                      # 第1题：CI/CD Pipeline
    Dockerfile                  # 第2题：多阶段 Dockerfile
    .dockerignore               # 第2题：Docker 忽略文件
    app/main.py                 # 第2题：FastAPI 应用
    requirements.txt            # 第2题：Python 依赖
    docker-compose.yml          # 第3题：多服务编排
    docker-compose.override.yml # 第3题：开发环境覆盖
    .env.example                # 第3题：环境变量模板
    k8s/k8s-deployment.yaml     # 第4题：K8s 部署清单
    app/observable_main.py      # 第5题：可观测应用
    prometheus.yml              # 第5题：Prometheus 配置
    alerting_rules.yml          # 第5题：告警规则
    grafana_dashboard.json      # 第5题：Grafana 仪表盘
"""

# ============================================================
# 工具函数：用于演示和验证
# ============================================================

def print_separator(title: str = "") -> None:
    """打印分隔线"""
    width = 70
    if title:
        padding = width - len(title) - 4
        left = padding // 2
        right = padding - left
        print(f"\n{'=' * left}  {title}  {'=' * right}")
    else:
        print("=" * width)


# ============================================================
# 第1题：GitHub Actions CI/CD — Python 测试自动化
# ============================================================

def exercise_1_ci_cd() -> None:
    """
    第1题：GitHub Actions CI/CD — Python 测试自动化

    【知识点讲解】

    1. CI/CD 的核心概念

    CI（Continuous Integration，持续集成）是指开发人员频繁地将代码合并到主分支，
    每次合并都自动触发构建和测试。CD（Continuous Delivery/Deployment，持续交付/部署）
    在 CI 的基础上，自动将通过测试的代码部署到预发布或生产环境。

    CI/CD 的核心价值在于：尽早发现问题、减少手动操作、提高交付速度和代码质量。
    没有 CI/CD 时，集成问题往往在发布前才发现，修复成本极高。有了 CI/CD，
    每次提交都会自动验证，问题在几分钟内暴露。

    2. GitHub Actions 的基本结构

    GitHub Actions 使用 YAML 文件定义工作流（Workflow），存放在 .github/workflows/ 目录下。
    核心概念：
    - Workflow（工作流）：一个自动化流程，由一个或多个 Job 组成
    - Job（任务）：一组按顺序执行的 Step，运行在同一个 Runner（虚拟机）上
    - Step（步骤）：Job 中的一个操作，可以是 shell 命令或预制的 Action
    - Action：可复用的代码单元，如 actions/checkout（检出代码）、actions/setup-python（安装 Python）

    工作流通过 on 字段定义触发条件：push、pull_request、workflow_dispatch（手动）、
    schedule（定时）等。还可以用 concurrency 控制并发，避免重复构建浪费资源。

    3. 矩阵测试（Matrix Strategy）

    矩阵测试允许在多个环境下并行运行同一个 Job。例如同时在 Python 3.11、3.12、3.13
    上运行测试，确保代码的版本兼容性。每个矩阵组合创建一个独立的 Job 实例。

    fail-fast: false 确保一个版本失败不会取消其他版本的测试，这样你能看到所有版本的结果。

    4. 缓存加速（pip cache）

    每次 CI 运行都重新安装 pip 依赖很慢。使用 actions/cache 缓存 ~/.cache/pip 目录，
    下次运行时直接从缓存恢复，只需安装新增或变更的包。缓存 key 包含 requirements.txt
    的哈希值，依赖文件变化时自动创建新缓存。

    5. 代码覆盖率与产物管理

    pytest-cov 插件生成覆盖率报告，--cov-report=xml 生成 Cobertura XML 格式，
    可上传到 Codecov 等服务进行可视化。actions/upload-artifact 将测试结果、
    构建产物上传，可在 Actions 页面下载，保留一定天数后自动清理。

    【配置文件】
    完整的 CI/CD 配置已保存到 devops/ci.yml，包含：
    - lint job：flake8 + pylint 代码检查
    - test job：矩阵测试（Python 3.11/3.12/3.13）+ 覆盖率
    - build job：构建 wheel 包并上传为 artifact

    【演示代码】下面演示如何用 Python 模拟 CI/CD 的核心流程
    """
    print_separator("第1题：GitHub Actions CI/CD")

    import subprocess
    import sys
    import os

    # ---- 模拟 CI Pipeline 的各阶段 ----

    # 阶段1：代码检查（模拟 flake8）
    print("\n[阶段1] 代码检查 (Lint)")
    print("-" * 40)

    sample_code = """
def add(a, b):
    return a + b

def greet(name):
    return f"Hello, {name}!"
"""
    # 检查基本风格：行长度、缩进等
    lines = sample_code.strip().split("\n")
    lint_issues = []
    for i, line in enumerate(lines, 1):
        if len(line) > 100:
            lint_issues.append(f"  行 {i}: 行宽超过 100 字符 ({len(line)})")
        if "\t" in line:
            lint_issues.append(f"  行 {i}: 使用了 Tab 缩进（应使用空格）")

    if lint_issues:
        print("发现以下问题：")
        for issue in lint_issues:
            print(issue)
    else:
        print("✓ 代码检查通过，无风格问题")

    # 阶段2：单元测试（模拟 pytest）
    print("\n[阶段2] 单元测试 (Test)")
    print("-" * 40)

    # 定义被测函数
    def add(a, b):
        return a + b

    def greet(name):
        return f"Hello, {name}!"

    # 定义测试用例
    test_cases = [
        ("test_add", lambda: add(1, 2) == 3),
        ("test_add_negative", lambda: add(-1, -2) == -3),
        ("test_add_zero", lambda: add(0, 0) == 0),
        ("test_greet", lambda: greet("World") == "Hello, World!"),
        ("test_greet_empty", lambda: greet("") == "Hello, !"),
    ]

    passed = 0
    failed = 0
    for name, assertion in test_cases:
        try:
            assert assertion()
            print(f"  ✓ {name}")
            passed += 1
        except AssertionError:
            print(f"  ✗ {name}")
            failed += 1

    print(f"\n  测试结果：{passed} 通过, {failed} 失败")

    # 阶段3：覆盖率报告（模拟 pytest-cov）
    print("\n[阶段3] 代码覆盖率 (Coverage)")
    print("-" * 40)

    # 模拟覆盖率计算
    total_lines = len(lines)
    covered_lines = total_lines - 1  # 假设有一行未覆盖
    coverage = (covered_lines / total_lines) * 100
    print(f"  总行数: {total_lines}")
    print(f"  覆盖行数: {covered_lines}")
    print(f"  覆盖率: {coverage:.1f}%")
    threshold = 80
    status = "✓ 达标" if coverage >= threshold else "✗ 未达标"
    print(f"  阈值: {threshold}% → {status}")

    # 阶段4：构建产物（模拟 python -m build）
    print("\n[阶段4] 构建产物 (Build)")
    print("-" * 40)
    print("  构建产物: dist/todo_app-1.0.0-py3-none-any.whl")
    print("  构建产物: dist/todo_app-1.0.0.tar.gz")
    print("  ✓ 构建完成，已上传为 artifact")

    print("\n" + "=" * 50)
    print("CI/CD Pipeline 执行完毕！")
    print("配置文件位置: devops/ci.yml")
    print("=" * 50)

    # ---- 思考题 ----
    print("\n📌 思考题：")
    print("  1. 如果项目有多个微服务，如何避免每个服务都写一份完整的 CI 配置？")
    print("     （提示：可复用 Workflow、composite actions）")
    print("  2. 矩阵测试中 fail-fast 设为 true 和 false 各有什么优缺点？")
    print("  3. 如何在 CI 中安全地使用 Secrets（如数据库密码、API Key）？")


# ============================================================
# 第2题：Docker 容器化 — Python 应用打包
# ============================================================

def exercise_2_docker() -> None:
    """
    第2题：Docker 容器化 — Python 应用打包

    【知识点讲解】

    1. 为什么要容器化

    容器化解决的核心问题是"在我机器上能跑"的困境。Docker 容器将应用及其所有依赖
    （操作系统库、Python 运行时、第三方包）打包成一个标准化单元，确保在任何环境下
    都能一致运行。

    与虚拟机相比，容器不需要完整的操作系统，共享宿主机内核，启动速度快（秒级），
    资源占用小。与直接部署相比，容器提供了环境隔离、版本一致性、快速回滚等优势。

    2. 多阶段构建（Multi-stage Build）

    多阶段构建是 Docker 的最佳实践。传统 Dockerfile 在一个镜像中安装所有工具
    （包括编译器、构建工具），导致最终镜像很大，还可能包含不必要的安全风险。

    多阶段构建将构建过程分为多个阶段（FROM ... AS builder）：
    - builder 阶段：安装编译器、构建工具，编译依赖
    - runtime 阶段：仅从 builder 复制编译好的产物，不包含构建工具

    这样最终镜像只包含运行时所需的最小内容，体积通常可以减少 50%-80%。

    3. 非 root 用户运行

    默认情况下 Docker 容器以 root 用户运行，如果攻击者利用漏洞逃逸到宿主机，
    就会获得 root 权限。安全最佳实践是创建专用用户（如 appuser），以最小权限运行应用。

    4. 镜像层缓存优化

    Docker 构建是分层的，每条指令创建一层。Docker 会缓存已构建的层，如果指令
    或输入文件没变，就直接使用缓存。关键优化：先复制 requirements.txt 并安装依赖，
    再复制应用代码。这样代码变更时不会重新安装依赖，大幅加速构建。

    5. HEALTHCHECK 指令

    HEALTHCHECK 告诉 Docker 如何检查容器是否健康。Docker 会定期执行检查命令，
    根据退出码判断状态（0=healthy, 1=unhealthy）。编排工具（如 Docker Compose、K8s）
    可以根据健康状态决定是否将流量路由到该容器。

    【配置文件】
    - devops/Dockerfile：多阶段构建文件
    - devops/.dockerignore：忽略文件列表
    - devops/app/main.py：被容器化的 FastAPI 应用
    - devops/requirements.txt：Python 依赖

    【演示代码】下面验证 FastAPI 应用代码的正确性
    """
    print_separator("第2题：Docker 容器化")

    # ---- 验证 FastAPI 应用代码可正常运行 ----
    print("\n[验证] FastAPI 应用代码测试")
    print("-" * 40)

    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from pydantic import BaseModel
    from datetime import datetime, timezone
    from typing import Optional

    # 复制 app/main.py 的核心逻辑进行验证
    test_app = FastAPI(title="Todo API Test")

    class TodoCreate(BaseModel):
        title: str
        description: Optional[str] = None

    _test_todos: dict[int, dict] = {}
    _test_next_id: int = 1

    @test_app.get("/health")
    async def health():
        return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

    @test_app.post("/todos", status_code=201)
    async def create_todo(todo: TodoCreate):
        nonlocal _test_next_id
        todo_data = {
            "id": _test_next_id,
            "title": todo.title,
            "description": todo.description,
            "completed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _test_todos[_test_next_id] = todo_data
        _test_next_id += 1
        return todo_data

    @test_app.get("/todos")
    async def list_todos():
        return list(_test_todos.values())

    @test_app.get("/todos/{todo_id}")
    async def get_todo(todo_id: int):
        if todo_id not in _test_todos:
            raise HTTPException(status_code=404, detail="Todo not found")
        return _test_todos[todo_id]

    @test_app.delete("/todos/{todo_id}", status_code=204)
    async def delete_todo(todo_id: int):
        if todo_id not in _test_todos:
            raise HTTPException(status_code=404, detail="Todo not found")
        del _test_todos[todo_id]
        return None

    # 使用 TestClient 测试
    client = TestClient(test_app)

    # 测试健康检查
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    print("  ✓ 健康检查端点正常")

    # 测试创建待办
    response = client.post("/todos", json={"title": "学习 Docker", "description": "完成第2题"})
    assert response.status_code == 201
    todo = response.json()
    assert todo["title"] == "学习 Docker"
    assert todo["completed"] is False
    print(f"  ✓ 创建待办事项成功: id={todo['id']}, title={todo['title']}")

    # 测试获取列表
    response = client.get("/todos")
    assert response.status_code == 200
    assert len(response.json()) == 1
    print(f"  ✓ 获取待办列表成功: 共 {len(response.json())} 条")

    # 测试获取单个
    response = client.get("/todos/1")
    assert response.status_code == 200
    assert response.json()["title"] == "学习 Docker"
    print("  ✓ 获取单个待办成功")

    # 测试 404
    response = client.get("/todos/999")
    assert response.status_code == 404
    print("  ✓ 404 处理正常")

    # 测试删除
    response = client.delete("/todos/1")
    assert response.status_code == 204
    response = client.get("/todos")
    assert len(response.json()) == 0
    print("  ✓ 删除待办成功")

    # ---- 演示 Dockerfile 最佳实践分析 ----
    print("\n[分析] Dockerfile 最佳实践")
    print("-" * 40)

    practices = [
        ("多阶段构建", "builder 安装依赖 → runtime 仅复制 venv", "减小镜像体积 50-80%"),
        ("虚拟环境", "在 builder 中创建 venv，复制到 runtime", "依赖隔离，避免系统包冲突"),
        ("层缓存优化", "先 COPY requirements.txt 再 COPY 源码", "代码变更不触发重新安装依赖"),
        ("非 root 用户", "创建 appuser，USER appuser", "最小权限原则，降低安全风险"),
        ("HEALTHCHECK", "curl -f http://localhost:8000/health", "容器编排工具可感知健康状态"),
        (".dockerignore", "排除 .git, __pycache__, .env 等", "加速构建，防止敏感信息泄露"),
    ]

    for name, desc, benefit in practices:
        print(f"  • {name}")
        print(f"    做法: {desc}")
        print(f"    收益: {benefit}")
        print()

    print("配置文件位置:")
    print("  devops/Dockerfile")
    print("  devops/.dockerignore")
    print("  devops/app/main.py")
    print("  devops/requirements.txt")

    # ---- 思考题 ----
    print("\n📌 思考题：")
    print("  1. 如果应用依赖需要编译 C 扩展（如 numpy），多阶段构建如何处理？")
    print("     （提示：builder 阶段安装 gcc 和 dev headers，runtime 阶段只需要 shared libs）")
    print("  2. 如何进一步减小镜像体积？（提示：distroless、scratch、alpine）")
    print("  3. 为什么 .dockerignore 中要排除 .env 文件？如果忘记排除会怎样？")


# ============================================================
# 第3题：Docker Compose — 多服务编排
# ============================================================

def exercise_3_compose() -> None:
    """
    第3题：Docker Compose — 多服务编排

    【知识点讲解】

    1. Docker Compose 的定位

    Docker Compose 是用于定义和运行多容器 Docker 应用的工具。使用一个 YAML 文件
    配置应用的所有服务（应用、数据库、缓存等），然后一条命令（docker compose up）
    启动所有服务。

    与 Kubernetes 相比，Docker Compose 更轻量，适合开发、测试和小规模部署。
    它不处理自动扩缩容、滚动更新等高级编排功能，但配置简单、上手快。

    2. 服务依赖与健康检查

    depends_on 控制服务启动顺序，但默认只等待容器启动，不等服务就绪。
    例如数据库容器启动了，但 PostgreSQL 还在初始化，此时应用连接会失败。

    解决方案：depends_on + condition: service_healthy。Compose 会等待 db 和 redis
    的 healthcheck 通过后，才启动 app。每个服务需要定义 healthcheck：
    - PostgreSQL: pg_isready -U user -d dbname
    - Redis: redis-cli ping
    - 应用: curl -f http://localhost:8000/health

    3. 数据持久化（Volumes）

    容器是临时的，删除容器数据就丢失了。Docker Volumes 解决这个问题：
    - 命名卷（named volume）：Docker 管理的持久化存储，独立于容器生命周期
    - 绑定挂载（bind mount）：将宿主机目录挂载到容器，适合开发环境代码热重载

    生产环境用命名卷保证数据安全，开发环境用绑定挂载实现代码实时同步。

    4. 网络隔离

    Docker Compose 默认为每个项目创建一个 bridge 网络，服务之间通过服务名通信
    （如 app 连接 db:5432）。可以在 networks 字段定义多个网络，实现更细粒度的隔离。
    例如：前端服务在前端网络，后端+数据库在后端网络，前端无法直接访问数据库。

    5. 开发 vs 生产环境

    Docker Compose 支持多文件覆盖机制：
    - docker-compose.yml：基础配置（生产环境）
    - docker-compose.override.yml：开发环境覆盖（自动加载）
    - docker-compose.prod.yml：生产覆盖（需 -f 指定）

    覆盖文件会深度合并到基础配置。开发环境通常：启用热重载、暴露调试端口、
    使用弱密码；生产环境通常：禁用调试、限制端口暴露、使用强密码和 TLS。

    【配置文件】
    - devops/docker-compose.yml：基础编排（3 个服务 + 网络 + 卷）
    - devops/docker-compose.override.yml：开发环境覆盖
    - devops/.env.example：环境变量模板

    【演示代码】下面验证环境变量管理和配置合并逻辑
    """
    print_separator("第3题：Docker Compose 多服务编排")

    # ---- 演示环境变量管理 ----
    print("\n[演示] 环境变量管理")
    print("-" * 40)

    # 模拟 .env 文件解析
    env_content = """
APP_PORT=8000
ENVIRONMENT=production
POSTGRES_USER=todo_user
POSTGRES_PASSWORD=change_me_to_a_strong_password
POSTGRES_DB=todo_db
DB_PORT=5432
REDIS_PORT=6379
SECRET_KEY=generate_a_random_secret_key_here
""".strip()

    env_vars: dict[str, str] = {}
    for line in env_content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env_vars[key.strip()] = value.strip()

    print("  解析 .env 文件：")
    for key, value in env_vars.items():
        # 敏感字段脱敏显示
        display = value if not any(s in key.upper() for s in ["PASSWORD", "SECRET", "KEY"]) else "*" * len(value)
        print(f"    {key} = {display}")

    # ---- 演示服务依赖图 ----
    print("\n[分析] 服务依赖关系")
    print("-" * 40)

    services = {
        "app": {
            "depends_on": ["db (healthy)", "redis (healthy)"],
            "ports": ["8000:8000"],
            "network": "app-network",
        },
        "db": {
            "image": "postgres:16-alpine",
            "ports": ["5432:5432"],
            "volume": "postgres-data",
            "healthcheck": "pg_isready",
        },
        "redis": {
            "image": "redis:7-alpine",
            "ports": ["6379:6379"],
            "volume": "redis-data",
            "healthcheck": "redis-cli ping",
        },
    }

    print("  启动顺序（自下而上）：")
    print("  ┌─────────────────────────────────────┐")
    print("  │           app (FastAPI)              │")
    print("  │    depends_on: db ✓, redis ✓         │")
    print("  └────────┬────────────────┬────────────┘")
    print("           │                │")
    print("  ┌────────▼──────┐  ┌──────▼──────────┐")
    print("  │  db (PgSQL)   │  │  redis (Cache)  │")
    print("  │  healthcheck  │  │  healthcheck    │")
    print("  │  pg_isready   │  │  redis-cli ping │")
    print("  └───────────────┘  └─────────────────┘")
    print("           │                │")
    print("  ┌────────▼──────┐  ┌──────▼──────────┐")
    print("  │ postgres-data │  │  redis-data     │")
    print("  │ (持久化卷)     │  │  (持久化卷)      │")
    print("  └───────────────┘  └─────────────────┘")

    # ---- 演示配置覆盖合并 ----
    print("\n[演示] 开发环境覆盖合并")
    print("-" * 40)

    base_config = {
        "app": {
            "command": "uvicorn app.main:app --host 0.0.0.0 --port 8000",
            "environment": ["ENVIRONMENT=production"],
            "ports": ["8000:8000"],
        }
    }

    override_config = {
        "app": {
            "command": "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug",
            "environment": ["ENVIRONMENT=development", "DEBUG=true"],
            "ports": ["8000:8000", "5678:5678"],
            "volumes": ["./:/app"],
        }
    }

    # 模拟深度合并
    def deep_merge(base: dict, override: dict) -> dict:
        """模拟 Docker Compose 的配置合并逻辑"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            elif key in result and isinstance(result[key], list) and isinstance(value, list):
                # 列表通常被覆盖（Docker Compose 行为）
                result[key] = value
            else:
                result[key] = value
        return result

    merged = deep_merge(base_config, override_config)

    print("  基础配置 (docker-compose.yml):")
    print(f"    command: {base_config['app']['command']}")
    print(f"    ports: {base_config['app']['ports']}")
    print(f"    volumes: (无)")
    print()
    print("  覆盖配置 (docker-compose.override.yml):")
    print(f"    command: {override_config['app']['command']}")
    print(f"    ports: {override_config['app']['ports']}")
    print(f"    volumes: {override_config['app']['volumes']}")
    print()
    print("  合并结果:")
    print(f"    command: {merged['app']['command']}")
    print(f"    ports: {merged['app']['ports']}")
    print(f"    volumes: {merged['app']['volumes']}")

    print("\n配置文件位置:")
    print("  devops/docker-compose.yml")
    print("  devops/docker-compose.override.yml")
    print("  devops/.env.example")

    # ---- 思考题 ----
    print("\n📌 思考题：")
    print("  1. 如果 db 启动需要 30 秒，但 app 只等 10 秒就超时退出，如何解决？")
    print("     （提示：调整 healthcheck 的 start_period 和 retries）")
    print("  2. 生产环境如何管理 .env 中的密码？（提示：Docker Secrets、Vault）")
    print("  3. 如何用 docker compose 同时运行测试？（提示：--profile、test service）")


# ============================================================
# 第4题：Kubernetes 部署 — 应用上 K8s
# ============================================================

def exercise_4_k8s() -> None:
    """
    第4题：Kubernetes 部署 — 应用上 K8s

    【知识点讲解】

    1. Kubernetes 核心概念

    Kubernetes（K8s）是容器编排的事实标准。它解决的核心问题是：在多台机器上
    管理大量容器，实现自动调度、弹性伸缩、滚动更新、故障自愈。

    核心概念：
    - Pod：K8s 最小调度单元，包含一个或多个容器，共享网络和存储
    - Deployment：管理 Pod 的副本集，负责滚动更新和回滚
    - Service：为一组 Pod 提供稳定的网络端点（Pod IP 会变，Service IP 不变）
    - Ingress：HTTP 层路由，将外部请求按域名/路径路由到不同 Service
    - ConfigMap/Secret：配置管理，分离配置与代码
    - HPA：水平自动扩缩容，根据负载动态调整 Pod 数量

    2. Deployment 与滚动更新

    Deployment 管理一组相同配置的 Pod 副本。当更新镜像版本时，Deployment 会
    逐步创建新版本 Pod、删除旧版本 Pod，实现零停机更新。

    滚动更新策略：
    - maxSurge: 1 — 更新过程中最多比期望副本数多 1 个（先启动新的）
    - maxUnavailable: 0 — 更新过程中不允许有不可用副本（旧的不删，直到新的就绪）

    revisionHistoryLimit 保留历史版本数，用于回滚（kubectl rollout undo）。

    3. 资源限制与 QoS

    每个 Pod 可以设置 resources.requests（调度依据）和 resources.limits（硬上限）：
    - requests.cpu=100m：调度时保证至少 0.1 核 CPU 可用
    - limits.cpu=500m：运行时最多使用 0.5 核 CPU，超过会被限流
    - requests.memory=128Mi：调度时保证至少 128MB 内存
    - limits.memory=256Mi：最多使用 256MB，超过会被 OOMKill

    QoS 等级：requests=limits → Guaranteed（最高优先级），
    有 requests 无 limits → Burstable，都没有 → BestEffort（最先被驱逐）。

    4. 三种探针（Probes）

    - livenessProbe：存活探针，失败时重启 Pod（处理死锁、内存泄漏等）
    - readinessProbe：就绪探针，失败时从 Service Endpoints 移除 Pod（不接收新流量）
    - startupProbe：启动探针，启动期间禁用 liveness/readiness（适合慢启动应用）

    三者配合：startupProbe 先通过（确认应用已启动）→ readinessProbe 通过（确认能处理请求）
    → 持续 livenessProbe 监控（发现假死就重启）。

    5. HPA 自动扩缩容

    HorizontalPodAutoscaler 根据 CPU/内存使用率或自定义指标自动调整 Pod 副本数。
    例如 CPU > 70% 时扩容，CPU < 30% 时缩容。需要 Metrics Server 提供指标数据。

    behavior 字段控制扩缩容行为：scaleDown.stabilizationWindowSeconds=300 表示
    缩容前观察 5 分钟，避免负载波动导致频繁扩缩（flapping）。

    【配置文件】
    devops/k8s/k8s-deployment.yaml 包含完整的 K8s 资源清单：
    - Namespace、ConfigMap、Secret
    - Deployment（3 副本 + 资源限制 + 三种探针 + 滚动更新）
    - Service（ClusterIP + NodePort）
    - Ingress（域名路由 + TLS）
    - HPA（CPU/内存自动扩缩容）

    【演示代码】下面验证 K8s YAML 配置的正确性
    """
    print_separator("第4题：Kubernetes 部署")

    # ---- 验证 K8s YAML 语法 ----
    print("\n[验证] K8s YAML 配置解析")
    print("-" * 40)

    import json

    # 读取并验证 K8s manifest 文件
    k8s_file = os.path.join(os.path.dirname(__file__), "..", "devops", "k8s", "k8s-deployment.yaml")
    k8s_file = os.path.normpath(k8s_file)

    try:
        # 尝试用 yaml 解析（如果安装了 pyyaml）
        import yaml
        with open(k8s_file, "r", encoding="utf-8") as f:
            documents = list(yaml.safe_load_all(f))

        print(f"  ✓ YAML 语法正确，共 {len(documents)} 个资源")

        # 分析每个资源
        resource_info = []
        for doc in documents:
            if doc is None:
                continue
            kind = doc.get("kind", "Unknown")
            name = doc.get("metadata", {}).get("name", "Unknown")
            namespace = doc.get("metadata", {}).get("namespace", "default")
            resource_info.append((kind, name, namespace))

        print(f"\n  资源清单：")
        for kind, name, ns in resource_info:
            print(f"    {kind:25s} | {name:25s} | ns={ns}")

        # 验证关键字段
        deployment = next(d for d in documents if d and d.get("kind") == "Deployment")
        spec = deployment["spec"]
        template_spec = spec["template"]["spec"]
        containers = template_spec["containers"][0]

        print(f"\n  Deployment 关键配置验证：")
        print(f"    副本数: {spec['replicas']}")
        print(f"    滚动更新: maxSurge={spec['strategy']['rollingUpdate']['maxSurge']}, "
              f"maxUnavailable={spec['strategy']['rollingUpdate']['maxUnavailable']}")
        print(f"    镜像: {containers['image']}")
        print(f"    CPU: requests={containers['resources']['requests']['cpu']}, "
              f"limits={containers['resources']['limits']['cpu']}")
        print(f"    内存: requests={containers['resources']['requests']['memory']}, "
              f"limits={containers['resources']['limits']['memory']}")
        print(f"    存活探针: {containers['livenessProbe']['httpGet']['path']}")
        print(f"    就绪探针: {containers['readinessProbe']['httpGet']['path']}")
        print(f"    启动探针: {containers['startupProbe']['httpGet']['path']}")

        hpa = next(d for d in documents if d and d.get("kind") == "HorizontalPodAutoscaler")
        hpa_spec = hpa["spec"]
        print(f"\n  HPA 关键配置验证：")
        print(f"    最小副本: {hpa_spec['minReplicas']}")
        print(f"    最大副本: {hpa_spec['maxReplicas']}")
        for metric in hpa_spec["metrics"]:
            print(f"    指标: {metric['resource']['name']} > {metric['resource']['target']['averageUtilization']}%")

        print("\n  ✓ 所有 K8s 配置验证通过")

    except ImportError:
        print("  (pyyaml 未安装，跳过 YAML 验证)")
        print("  请检查 devops/k8s/k8s-deployment.yaml 文件")
    except FileNotFoundError:
        print(f"  文件未找到: {k8s_file}")
        print("  请检查文件路径")

    # ---- K8s 架构图 ----
    print("\n[架构] K8s 部署拓扑")
    print("-" * 40)

    print("""
  外部请求
    │
    ▼
  ┌──────────────────┐
  │  Ingress         │  todo-app.example.com → todo-app-service:80
  │  (TLS + 路由)     │
  └────────┬─────────┘
           │
    ┌──────▼──────┐
    │   Service   │  ClusterIP: 稳定虚拟 IP
    │  (负载均衡)  │  NodePort: 30080
    └──────┬──────┘
           │
    ┌──────▼──────────────────────────┐
    │        Deployment (3 副本)       │
    │  ┌─────┐  ┌─────┐  ┌─────┐     │
    │  │Pod 1│  │Pod 2│  │Pod 3│     │  HPA: 2~10 副本
    │  │app  │  │app  │  │app  │     │  CPU>70% → 扩容
    │  │:8000│  │:8000│  │:8000│     │  CPU<30% → 缩容
    │  └─────┘  └─────┘  └─────┘     │
    │  ✓ liveness  ✓ readiness       │
    └─────────────────────────────────┘
           │                │
    ┌──────▼──────┐  ┌──────▼──────┐
    │  ConfigMap  │  │   Secret    │
    │ (非敏感配置) │  │ (敏感配置)   │
    └─────────────┘  └─────────────┘
    """)

    print("配置文件位置:")
    print("  devops/k8s/k8s-deployment.yaml")

    # ---- 思考题 ----
    print("\n📌 思考题：")
    print("  1. livenessProbe 和 readinessProbe 都指向 /health，有什么潜在问题？")
    print("     （提示：应用启动慢但健康检查通过 / 应用部分功能故障但 health 仍返回 200）")
    print("  2. maxUnavailable: 0 和 maxSurge: 0 能同时设置吗？为什么？")
    print("  3. HPA 基于 CPU 扩缩容，如果应用是 IO 密集型（CPU 不高但延迟大），如何处理？")


# ============================================================
# 第5题：可观测性 — 日志、指标与告警
# ============================================================

def exercise_5_observability() -> None:
    """
    第5题：可观测性 — 日志、指标与告警

    【知识点讲解】

    1. 可观测性三大支柱

    可观测性（Observability）是指从系统外部行为推断内部状态的能力。它包含三大支柱：

    - 日志（Logging）：离散事件的记录，回答"发生了什么"。结构化日志（JSON 格式）
      便于 ELK/Loki 等系统采集、过滤和分析。
    - 指标（Metrics）：聚合数值数据，回答"趋势如何"。如 QPS、延迟分位数、错误率、
      CPU 使用率。Prometheus 是最流行的指标系统。
    - 追踪（Tracing）：请求在分布式系统中的完整调用链，回答"请求经过了哪些服务、
      每步耗时多少"。OpenTelemetry 是 CNCF 的追踪标准。

    三者互补：指标发现问题（错误率升高）→ 追踪定位问题（哪个服务慢）→ 日志查看细节（具体错误信息）。

    2. 结构化日志

    传统日志是纯文本，难以被机器解析。结构化日志将每条日志输出为 JSON，包含
    timestamp、level、message 以及自定义字段（如 request_id、user_id、duration_ms）。

    好的日志实践：
    - 每条日志包含足够上下文（谁、什么、何时、结果）
    - 不记录敏感信息（密码、token）
    - 使用合适的日志级别（DEBUG < INFO < WARNING < ERROR < CRITICAL）
    - 避免日志风暴（循环中大量打印日志）

    3. Prometheus 指标类型

    Prometheus 定义了四种指标类型：
    - Counter（计数器）：只增不减，如请求总数、错误总数。用 rate() 计算速率。
    - Gauge（仪表盘）：可增可减，如当前连接数、队列长度、温度。
    - Histogram（直方图）：将数据分桶统计分布，如请求延迟分布。用 histogram_quantile() 计算分位数。
    - Summary（摘要）：类似 Histogram，但客户端直接计算分位数（不能跨实例聚合）。

    应用通过 /metrics 端点暴露指标，Prometheus 定时抓取（pull 模式）。

    4. 告警规则设计

    好的告警应该：
    - 可操作性：收到告警后知道该做什么（避免噪音告警）
    - 及时性：for 字段设置合理的观察窗口（太短会误报，太长会延迟）
    - 分级：critical（立即处理）、warning（关注）、info（记录即可）

    常见告警模式：
    - 服务不可用：up{job="xxx"} == 0 for 1m
    - 高错误率：5xx 错误占比 > 5% for 2m
    - 高延迟：P95 延迟 > 1s for 5m
    - 资源耗尽：CPU > 80%、内存 > 85%、磁盘 > 85%

    5. OpenTelemetry 分布式追踪

    在微服务架构中，一个用户请求可能经过多个服务。OpenTelemetry 通过 Trace
    （一次完整的请求链路）和 Span（单个操作）记录请求在各个服务中的流转。

    每个 Span 包含：操作名、开始/结束时间、属性、事件、状态。Span 之间通过
    parent-child 关系形成调用树。Trace ID 贯穿整条链路，用于关联所有相关 Span。

    追踪的核心价值：可视化请求的完整调用链，快速定位性能瓶颈和错误源头。

    【配置文件】
    - devops/app/observable_main.py：可观测 FastAPI 应用
    - devops/prometheus.yml：Prometheus 抓取配置
    - devops/alerting_rules.yml：告警规则
    - devops/grafana_dashboard.json：Grafana 仪表盘模板

    【演示代码】下面验证可观测应用的核心功能
    """
    print_separator("第5题：可观测性 — 日志、指标与告警")

    import os

    # ---- 验证结构化日志 ----
    print("\n[验证] 结构化日志（JSON 格式）")
    print("-" * 40)

    import json
    import logging
    from datetime import datetime, timezone

    class JsonFormatter(logging.Formatter):
        """将日志格式化为 JSON"""

        def format(self, record: logging.LogRecord) -> str:
            log_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)
            # 收集额外字段
            standard_attrs = {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "getMessage",
                "taskName",
            }
            for key, value in record.__dict__.items():
                if key not in standard_attrs:
                    log_data[key] = value
            return json.dumps(log_data, ensure_ascii=False)

    # 创建测试 logger
    test_logger = logging.getLogger("demo_app")
    test_logger.setLevel(logging.DEBUG)
    if not test_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        test_logger.addHandler(handler)
    test_logger.propagate = False

    # 输出不同级别的日志
    test_logger.info("应用启动", extra={"version": "1.0.0", "port": 8000})
    test_logger.warning("缓存未命中", extra={"cache_key": "user:123", "fallback": "database"})
    test_logger.info("请求完成", extra={"method": "GET", "path": "/todos", "status": 200, "duration_ms": 12.5})

    print("\n  ✓ 结构化日志输出正确，每条日志都是合法 JSON")

    # ---- 验证 Prometheus 指标 ----
    print("\n[验证] Prometheus 指标暴露")
    print("-" * 40)

    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry

    registry = CollectorRegistry()

    # 定义指标
    req_counter = Counter(
        "demo_http_requests_total",
        "HTTP 请求总数",
        ["method", "endpoint", "status"],
        registry=registry,
    )

    req_latency = Histogram(
        "demo_http_request_duration_seconds",
        "HTTP 请求耗时",
        ["method", "endpoint"],
        registry=registry,
    )

    active_gauge = Gauge(
        "demo_active_requests",
        "活跃请求数",
        registry=registry,
    )

    # 模拟请求
    import time

    test_requests = [
        ("GET", "/health", 200, 0.001),
        ("GET", "/todos", 200, 0.015),
        ("POST", "/todos", 201, 0.025),
        ("GET", "/todos", 200, 0.010),
        ("GET", "/error", 500, 0.050),
        ("GET", "/todos", 200, 0.008),
        ("GET", "/slow", 200, 0.520),
        ("GET", "/todos", 200, 0.012),
    ]

    for method, endpoint, status, duration in test_requests:
        req_counter.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        req_latency.labels(method=method, endpoint=endpoint).observe(duration)

    active_gauge.set(3)

    # 输出指标
    metrics_output = generate_latest(registry).decode("utf-8")
    print("  /metrics 端点输出（部分）：")
    for line in metrics_output.split("\n"):
        if line and not line.startswith("#"):
            print(f"    {line}")

    print("\n  ✓ Prometheus 指标格式正确")

    # ---- 验证 FastAPI 可观测应用 ----
    print("\n[验证] 可观测 FastAPI 应用")
    print("-" * 40)

    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from fastapi.responses import PlainTextResponse

    obs_app = FastAPI(title="Observable Test App")

    # 简化的中间件
    @obs_app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        test_logger.info(
            "请求完成",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration * 1000, 2),
            },
        )
        return response

    @obs_app.get("/health")
    async def health():
        return {"status": "healthy"}

    @obs_app.get("/metrics")
    async def metrics():
        return PlainTextResponse(
            content=generate_latest(registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    @obs_app.get("/slow")
    async def slow():
        time.sleep(0.1)
        return {"message": "slow response"}

    @obs_app.get("/error")
    async def error():
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="simulated error")

    client = TestClient(obs_app)

    # 测试各端点
    endpoints = [
        ("GET", "/health", 200),
        ("GET", "/metrics", 200),
        ("GET", "/slow", 200),
        ("GET", "/error", 500),
    ]

    for method, path, expected_status in endpoints:
        response = client.get(path) if method == "GET" else client.post(path)
        status_icon = "✓" if response.status_code == expected_status else "✗"
        print(f"  {status_icon} {method} {path} → {response.status_code}")

    # 验证 /metrics 返回 Prometheus 格式
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    assert "demo_http_requests_total" in response.text
    print("\n  ✓ /metrics 端点返回有效的 Prometheus 格式数据")

    # ---- 指标类型说明 ----
    print("\n[知识] Prometheus 指标类型")
    print("-" * 40)

    metric_types = [
        ("Counter", "只增不减", "请求总数、错误总数", "rate(counter[5m]) 计算速率"),
        ("Gauge", "可增可减", "活跃连接数、队列长度", "直接取当前值"),
        ("Histogram", "分布统计", "请求延迟分布", "histogram_quantile(0.95, ...) 计算 P95"),
        ("Summary", "客户端分位数", "少量实例的延迟", "不可跨实例聚合"),
    ]

    for name, desc, example, usage in metric_types:
        print(f"  • {name}")
        print(f"    特征: {desc}")
        print(f"    场景: {example}")
        print(f"    查询: {usage}")
        print()

    # ---- 可观测性架构图 ----
    print("[架构] 可观测性系统拓扑")
    print("-" * 40)

    print("""
  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │  日志       │     │   指标      │     │   追踪      │
  │  (Logs)     │     │  (Metrics)  │     │  (Traces)   │
  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
         │                   │                   │
         ▼                   ▼                   ▼
  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │   Loki /    │     │ Prometheus  │     │    Tempo /  │
  │   ELK       │     │  (抓取)      │     │    Jaeger   │
  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
         │                   │                   │
         │           ┌───────▼───────┐          │
         │           │  AlertManager │          │
         │           │   (告警)       │          │
         │           └───────┬───────┘          │
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                    ┌─────────────────┐
                    │     Grafana     │
                    │  (统一可视化)    │
                    └─────────────────┘
    """)

    print("配置文件位置:")
    print("  devops/app/observable_main.py")
    print("  devops/prometheus.yml")
    print("  devops/alerting_rules.yml")
    print("  devops/grafana_dashboard.json")

    # ---- 思考题 ----
    print("\n📌 思考题：")
    print("  1. 日志、指标、追踪三者如何配合快速定位线上问题？请描述排查流程。")
    print("  2. Prometheus 的 pull 模式和 push 模式各有什么优缺点？")
    print("  3. 如果 /metrics 端点暴露了敏感信息（如数据库连接字符串），会有什么风险？如何避免？")


# ============================================================
# 主函数
# ============================================================

def main() -> None:
    """主函数：依次运行 5 道练习题"""

    print("=" * 70)
    print("  DevOps 实操练习（5题）")
    print("  AI 全栈学习补充 | Python 3.13.12")
    print("=" * 70)

    # 检查依赖
    dependencies = {
        "fastapi": "FastAPI",
        "uvicorn": "Uvicorn",
        "prometheus_client": "Prometheus Client",
        "yaml": "PyYAML（可选，用于 K8s YAML 验证）",
    }

    print("\n依赖检查：")
    import importlib
    for module, name in dependencies.items():
        try:
            importlib.import_module(module)
            print(f"  ✓ {name}")
        except ImportError:
            print(f"  ✗ {name} 未安装")

    # 依次运行 5 道练习
    exercises = [
        exercise_1_ci_cd,
        exercise_2_docker,
        exercise_3_compose,
        exercise_4_k8s,
        exercise_5_observability,
    ]

    for i, exercise in enumerate(exercises, 1):
        try:
            exercise()
        except Exception as exc:
            print(f"\n❌ 第{i}题执行出错: {exc}")
            import traceback
            traceback.print_exc()

    # 总结
    print_separator("练习完成")
    print(f"""
  🎉 DevOps 实操 5 题全部完成！

  文件清单：
    python_exercises/28_devops_practice.py  ← 本文件（讲解 + 可运行代码）
    devops/ci.yml                           ← 第1题：CI/CD Pipeline
    devops/Dockerfile                       ← 第2题：多阶段 Dockerfile
    devops/.dockerignore                    ← 第2题：Docker 忽略文件
    devops/app/main.py                      ← 第2题：FastAPI 应用
    devops/requirements.txt                 ← 第2题：Python 依赖
    devops/docker-compose.yml               ← 第3题：多服务编排
    devops/docker-compose.override.yml      ← 第3题：开发环境覆盖
    devops/.env.example                     ← 第3题：环境变量模板
    devops/k8s/k8s-deployment.yaml          ← 第4题：K8s 部署清单
    devops/app/observable_main.py           ← 第5题：可观测应用
    devops/prometheus.yml                   ← 第5题：Prometheus 配置
    devops/alerting_rules.yml               ← 第5题：告警规则
    devops/grafana_dashboard.json           ← 第5题：Grafana 仪表盘

  知识点覆盖：
    ✓ CI/CD 自动化（GitHub Actions）
    ✓ Docker 容器化（多阶段构建）
    ✓ Docker Compose 多服务编排
    ✓ Kubernetes 部署（Deployment/Service/Ingress/HPA）
    ✓ 可观测性（日志/指标/追踪/告警）
""")


if __name__ == "__main__":
    import os
    main()
