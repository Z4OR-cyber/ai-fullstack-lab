# DevOps实战：从Docker到K8s的完整部署手册

> **摘要**：容器化和CI/CD是现代软件交付的基石。本文基于DevOps练习代码和实际项目配置文件，系统讲解Docker多阶段构建、Docker Compose多服务编排、Kubernetes部署清单（Deployment/Service/Ingress/HPA/探针）、GitHub Actions CI/CD流水线以及可观测性（Prometheus + Grafana）体系，呈现从开发到生产的完整部署流程。

**关键词**：Docker、Kubernetes、CI/CD、GitHub Actions、Prometheus、Grafana、可观测性

---

## 一、Docker多阶段构建

### 1.1 为什么需要多阶段构建？

传统Dockerfile在一个镜像中安装所有工具（编译器、构建工具），导致最终镜像庞大且存在安全风险。多阶段构建将构建过程分为多个阶段——builder阶段安装编译工具，runtime阶段仅复制产物，镜像体积通常减少50%~80%。

### 1.2 生产级Dockerfile

```dockerfile
# -------------------- 第一阶段：builder --------------------
FROM python:3.13-slim AS builder

WORKDIR /build

# 关键：先复制依赖文件，利用Docker层缓存
# 只要requirements.txt不变，pip install层就会被缓存
COPY requirements.txt .

# 创建虚拟环境，隔离依赖
RUN python -m venv /opt/venv

# 安装依赖（--no-cache-dir减小体积）
RUN /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# -------------------- 第二阶段：runtime --------------------
FROM python:3.13-slim AS runtime

# 环境变量优化
ENV PYTHONUNBUFFERED=1 \        # 禁用输出缓冲，日志实时输出
    PYTHONDONTWRITEBYTECODE=1 \ # 不生成.pyc文件
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# 安装curl（HEALTHCHECK需要）+ 清理apt缓存
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 从builder复制虚拟环境（仅包含已安装的依赖）
COPY --from=builder /opt/venv /opt/venv

# 创建非root用户（安全最佳实践）
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# 复制应用代码（放在依赖安装之后，最大化层缓存命中）
COPY --chown=appuser:appuser . .

USER appuser
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 1.3 最佳实践总结

| 实践 | 做法 | 收益 |
|------|------|------|
| 多阶段构建 | builder安装依赖 → runtime仅复制venv | 镜像体积减少50-80% |
| 层缓存优化 | 先COPY requirements.txt再COPY源码 | 代码变更不触发重新安装依赖 |
| 虚拟环境 | builder中创建venv，复制到runtime | 依赖隔离，避免系统包冲突 |
| 非root用户 | 创建appuser，`USER appuser` | 最小权限原则，降低安全风险 |
| HEALTHCHECK | `curl -f /health` | 编排工具可感知健康状态 |
| .dockerignore | 排除.git、\_\_pycache\_\_、.env | 加速构建，防止敏感信息泄露 |

HEALTHCHECK的四个参数含义：
- `--interval=30s`：检查间隔
- `--timeout=5s`：单次检查超时
- `--start-period=10s`：容器启动后等待10秒再开始检查
- `--retries=3`：连续3次失败才标记为unhealthy

---

## 二、Docker Compose多服务编排

### 2.1 完整编排配置

```yaml
services:
  # -------------------- FastAPI 应用 --------------------
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: todo-app
    ports:
      - "${APP_PORT:-8000}:8000"
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy    # 等待db健康后才启动
      redis:
        condition: service_healthy
    networks:
      - app-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  # -------------------- PostgreSQL 数据库 --------------------
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres-data:/var/lib/postgresql/data    # 数据持久化
      - ./init-db:/docker-entrypoint-initdb.d:ro  # 初始化脚本
    networks:
      - app-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  # -------------------- Redis 缓存 --------------------
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    networks:
      - app-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres-data:
    driver: local
  redis-data:
    driver: local

networks:
  app-network:
    driver: bridge
```

### 2.2 关键设计解析

**服务依赖与健康检查**：`depends_on`默认只等待容器启动，不等服务就绪。加上`condition: service_healthy`后，Compose会等待db和redis的healthcheck通过后才启动app，解决了"数据库还在初始化，应用就尝试连接"的问题。

**数据持久化**：命名卷（`postgres-data`、`redis-data`）由Docker管理，独立于容器生命周期。容器删除后数据不丢失。

**网络隔离**：自定义bridge网络`app-network`，服务之间通过服务名通信（app连接`db:5432`、`redis:6379`），无需IP地址。

**环境变量管理**：通过`.env`文件注入敏感配置，`${VAR:-default}`语法支持默认值：

```env
APP_PORT=8000
POSTGRES_USER=todo_user
POSTGRES_PASSWORD=change_me_to_a_strong_password
POSTGRES_DB=todo_db
```

### 2.3 开发环境覆盖

Docker Compose支持多文件覆盖机制：
- `docker-compose.yml`：基础配置
- `docker-compose.override.yml`：开发覆盖（自动加载）

```yaml
# docker-compose.override.yml — 开发环境
services:
  app:
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug
    ports:
      - "8000:8000"
      - "5678:5678"  # 调试端口
    volumes:
      - ./:/app      # 代码热重载
    environment:
      - ENVIRONMENT=development
      - DEBUG=true
```

覆盖文件深度合并到基础配置：开发环境启用热重载、暴露调试端口、使用弱密码；生产环境禁用调试、限制端口暴露。

---

## 三、Kubernetes部署

### 3.1 完整部署清单

K8s部署清单包含Namespace、ConfigMap、Secret、Deployment、Service、Ingress和HPA。

#### ConfigMap + Secret

```yaml
# ConfigMap — 非敏感配置
apiVersion: v1
kind: ConfigMap
metadata:
  name: todo-app-config
  namespace: todo-app
data:
  APP_ENV: "production"
  DATABASE_HOST: "todo-db-service"
  DATABASE_PORT: "5432"
  REDIS_HOST: "todo-redis-service"
  REDIS_PORT: "6379"

---
# Secret — 敏感配置
apiVersion: v1
kind: Secret
metadata:
  name: todo-app-secret
  namespace: todo-app
type: Opaque
stringData:
  DATABASE_USER: "todo_user"
  DATABASE_PASSWORD: "change_me_in_production"
  SECRET_KEY: "generate_a_real_secret_key_here"
# 注意：stringData是明文，K8s自动base64编码
# 生产环境应使用Sealed Secrets或External Secrets Operator
```

#### Deployment + 三种探针

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: todo-app
  namespace: todo-app
spec:
  replicas: 3                    # 初始副本数（HPA会动态调整）
  selector:
    matchLabels:
      app: todo-app
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1               # 滚动更新时最多多1个副本
      maxUnavailable: 0         # 不允许有不可用副本（零停机更新）
  revisionHistoryLimit: 10      # 保留10个历史版本（用于回滚）
  template:
    spec:
      containers:
        - name: todo-app
          image: todo-app:1.0.0
          envFrom:
            - configMapRef:
                name: todo-app-config
            - secretRef:
                name: todo-app-secret
          resources:
            requests:           # 调度依据
              cpu: "100m"       # 0.1核
              memory: "128Mi"
            limits:             # 硬上限
              cpu: "500m"
              memory: "256Mi"
          # 就绪探针：失败时从Service Endpoints移除该Pod
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
            failureThreshold: 3
          # 存活探针：失败时K8s重启该Pod
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 20
            failureThreshold: 3
          # 启动探针：启动期间禁用liveness/readiness
          startupProbe:
            httpGet:
              path: /health
              port: 8000
            periodSeconds: 5
            failureThreshold: 12  # 最多等60秒启动
          lifecycle:
            preStop:
              exec:
                command: ["sleep", "5"]  # 等待负载均衡器移除该Pod
      terminationGracePeriodSeconds: 30
```

**三种探针的职责区分**：

| 探针 | 失败后果 | 用途 |
|------|---------|------|
| startupProbe | 重启Pod | 检测应用是否已启动，启动期间禁用其他探针 |
| readinessProbe | 从Service Endpoints移除 | 检测是否准备好接收流量 |
| livenessProbe | 重启Pod | 检测应用是否存活 |

#### Service + Ingress

```yaml
# Service — 集群内部访问
apiVersion: v1
kind: Service
metadata:
  name: todo-app-service
  namespace: todo-app
spec:
  type: ClusterIP
  selector:
    app: todo-app
  ports:
    - port: 80
      targetPort: 8000

---
# Ingress — 域名路由 + TLS
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: todo-app-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/limit-rps: "10"  # 限流
spec:
  tls:
    - hosts: [todo.example.com]
      secretName: todo-tls
  rules:
    - host: todo.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: todo-app-service
                port:
                  number: 80
```

#### HPA（水平Pod自动扩缩容）

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: todo-app-hpa
  namespace: todo-app
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: todo-app
  minReplicas: 3                # 最小副本数
  maxReplicas: 10               # 最大副本数
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70  # CPU使用率超过70%扩容
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

HPA根据CPU和内存使用率自动调整Pod数量：负载高时自动扩容，负载低时自动缩容，既保证性能又控制成本。

---

## 四、GitHub Actions CI/CD流水线

### 4.1 完整CI配置

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  workflow_dispatch:            # 支持手动触发

# 同一分支新推送取消旧运行，节省CI资源
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  # -------------------- 代码检查 --------------------
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - uses: actions/cache@v4        # 缓存pip依赖加速
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-lint-${{ hashFiles('**/requirements*.txt') }}
      - run: pip install flake8 pylint
      - run: flake8 . --max-line-length=100 --extend-ignore=E203,W503

  # -------------------- 矩阵测试 --------------------
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false             # 一个版本失败不取消其他版本
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python-version }} }
      - run: pip install -r requirements.txt pytest pytest-cov pytest-xdist
      - run: pytest -n auto --cov=. --cov-report=xml --cov-report=term-missing
      - uses: actions/upload-artifact@v4   # 上传测试产物
        if: always()                        # 即使失败也上传
        with:
          name: test-results-${{ matrix.python-version }}
          path: |
            coverage.xml
            test-results.xml
      - uses: codecov/codecov-action@v4    # 上传覆盖率到Codecov
        if: matrix.python-version == '3.13'

  # -------------------- 构建 --------------------
  build:
    needs: [lint, test]           # 等待lint和test通过后才构建
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t todo-app:latest .
```

### 4.2 设计要点

| 特性 | 实现方式 | 价值 |
|------|---------|------|
| 矩阵测试 | `matrix: python-version: ["3.11", "3.12", "3.13"]` | 多版本兼容性验证 |
| 缓存加速 | `actions/cache`缓存pip目录 | 减少依赖安装时间 |
| 并发控制 | `concurrency: cancel-in-progress: true` | 避免重复构建浪费资源 |
| 产物管理 | `upload-artifact`保留7天 | 测试结果可追溯 |
| 依赖编排 | `needs: [lint, test]` | 阶段式流水线，失败快速反馈 |
| `fail-fast: false` | 矩阵中一个失败不取消其他 | 看到所有版本的结果 |

---

## 五、可观测性：Prometheus + Grafana

### 5.1 Prometheus配置

```yaml
global:
  scrape_interval: 15s          # 全局抓取间隔
  evaluation_interval: 15s      # 规则评估间隔

rule_files:
  - "alerting_rules.yml"

scrape_configs:
  # 抓取FastAPI应用的/metrics端点
  - job_name: "todo-app"
    metrics_path: "/metrics"
    scrape_interval: 10s        # 应用指标更频繁抓取
    static_configs:
      - targets: ["app:8000"]
        labels:
          service: "todo-app"
          env: "production"

  # 抓取主机指标
  - job_name: "node-exporter"
    static_configs:
      - targets: ["node-exporter:9100"]
```

### 5.2 告警规则

```yaml
groups:
  - name: todo-app-alerts
    rules:
      # 告警1：服务不可用
      - alert: TodoAppDown
        expr: up{job="todo-app"} == 0
        for: 1m                   # 持续1分钟才触发
        labels:
          severity: critical
        annotations:
          summary: "Todo App 服务不可用"
          description: "实例 {{ $labels.instance }} 已经离线超过1分钟"

      # 告警2：高错误率
      - alert: TodoAppHighErrorRate
        expr: |
          sum(rate(http_requests_total{job="todo-app", status=~"5.."}[5m]))
          /
          sum(rate(http_requests_total{job="todo-app"}[5m]))
          > 0.05
        for: 2m                   # 5xx错误率超过5%，持续2分钟
        labels:
          severity: warning
        annotations:
          summary: "错误率过高"
          description: "5xx错误率超过5%（当前值：{{ $value | humanizePercentage }}）"

      # 告警3：高延迟
      - alert: TodoAppHighLatency
        expr: |
          histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket{job="todo-app"}[5m])) by (le)
          ) > 1.0
        for: 5m                   # P95延迟超过1秒，持续5分钟
        labels:
          severity: warning

  - name: host-alerts
    rules:
      # 告警4：高CPU
      - alert: HighCpuUsage
        expr: |
          100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
```

### 5.3 可观测性三层体系

| 层级 | 工具 | 关注点 |
|------|------|--------|
| 指标 | Prometheus + Grafana | 系统状态量化（CPU、延迟、错误率） |
| 日志 | ELK / Loki | 事件追溯和问题排查 |
| 追踪 | Jaeger / OpenTelemetry | 请求链路分析（微服务调用关系） |

告警设计的`for`字段很关键——不是达到阈值立即告警，而是持续一段时间才触发，避免瞬时抖动导致的误报。

---

## 六、从开发到生产的完整流程

```
开发环境                    CI/CD                      生产环境
┌──────────┐          ┌──────────────┐          ┌──────────────┐
│ 代码编写  │  push →  │ GitHub Actions│  deploy  │  Kubernetes   │
│ 本地测试  │          │ lint → test  │   →      │  Deployment   │
│ Compose  │          │ → build image│          │  + Service    │
│ 热重载   │          │ → push registry│         │  + Ingress    │
└──────────┘          └──────────────┘          │  + HPA        │
                                                 │  + Probes      │
                                  监控 ← ─────── │  + Prometheus  │
                                  告警 ← ─────── │  + Grafana     │
                                                └──────────────┘
```

### 完整流程

1. **本地开发**：`docker compose up`启动全套服务，`--reload`热重载
2. **提交代码**：push到main/develop分支
3. **CI流水线**：flake8检查 → 矩阵测试(Python 3.11/3.12/3.13) → 覆盖率报告 → 构建Docker镜像
4. **部署K8s**：`kubectl apply -f k8s/`，滚动更新零停机
5. **健康检查**：startup/readiness/liveness三探针保障
6. **监控告警**：Prometheus抓取指标，超过阈值触发告警
7. **自动扩缩容**：HPA根据CPU/内存自动调整Pod数量

---

## 七、总结

DevOps的核心价值在于自动化和可观测性：

1. **Docker多阶段构建**：builder + runtime分离，镜像小且安全
2. **Compose编排**：depends_on + healthcheck解决服务依赖，volumes保证数据持久化
3. **K8s三种探针**：startup（启动）、readiness（就绪）、liveness（存活）各司其职
4. **HPA自动扩缩容**：根据资源使用率动态调整副本数
5. **CI/CD流水线**：lint → 矩阵测试 → 构建，每次提交自动验证
6. **可观测性**：Prometheus指标 + 告警规则，问题在用户感知前发现

从开发到生产，每一步都有自动化保障——开发者只需关注业务代码，基础设施由工具链处理。

> 本文所有配置文件均来自实际项目，包括Dockerfile、docker-compose.yml、k8s-deployment.yaml、ci.yml、prometheus.yml、alerting_rules.yml等。

---

*作者：koze | AI全栈学习笔记*
