"""
第五阶段 5.2 容器化与部署练习（10题）
Docker / Kubernetes / 模型服务 / 推理优化 / 负载均衡 / 部署策略
依赖: numpy, sklearn, fastapi, yaml
"""
import json, time, math, copy, hashlib, threading, queue
from datetime import datetime, timezone
from collections import defaultdict, deque
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import yaml

# ============================================================
# 1. Dockerfile 编写与验证
# ============================================================

def generate_dockerfile(app_config):
    """
    生成标准 Dockerfile
    app_config: {
        "base_image": str,
        "python_version": str,
        "workdir": str,
        "requirements": list[str],
        "app_port": int,
        "entrypoint": str,
        "env_vars": dict,
    }
    """
    lines = []
    base = app_config.get("base_image", f"python:{app_config.get('python_version', '3.12')}-slim")
    lines.append(f"FROM {base}")
    lines.append("")

    # 环境变量
    lines.append("# Environment variables")
    for key, val in app_config.get("env_vars", {}).items():
        lines.append(f"ENV {key}={val}")
    lines.append("")

    # 工作目录
    workdir = app_config.get("workdir", "/app")
    lines.append(f"WORKDIR {workdir}")
    lines.append("")

    # 系统依赖
    lines.append("# Install system dependencies")
    lines.append("RUN apt-get update && apt-get install -y --no-install-recommends \\")
    lines.append("    build-essential curl git \\")
    lines.append("    && rm -rf /var/lib/apt/lists/*")
    lines.append("")

    # Python 依赖
    lines.append("# Install Python dependencies")
    lines.append("COPY requirements.txt .")
    lines.append("RUN pip install --no-cache-dir -r requirements.txt")
    lines.append("")

    # 应用代码
    lines.append("# Copy application code")
    lines.append("COPY . .")
    lines.append("")

    # 端口
    port = app_config.get("app_port", 8000)
    lines.append(f"EXPOSE {port}")
    lines.append("")

    # 健康检查
    lines.append(f"# Health check")
    lines.append(f"HEALTHCHECK --interval=30s --timeout=3s --retries=3 \\")
    lines.append(f"    CMD curl -f http://localhost:{port}/health || exit 1")
    lines.append("")

    # 入口
    entrypoint = app_config.get("entrypoint", "uvicorn main:app --host 0.0.0.0 --port " + str(port))
    parts = entrypoint.split()
    lines.append(f'ENTRYPOINT {json.dumps(parts)}')

    return "\n".join(lines) + "\n"


def generate_requirements_txt(packages):
    """生成 requirements.txt 内容"""
    return "\n".join(packages) + "\n"


def validate_dockerfile(dockerfile_content):
    """验证 Dockerfile 基本规范"""
    issues = []
    lines = dockerfile_content.strip().split("\n")

    # 跳过注释和空行，找第一条指令
    first_instruction = None
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            first_instruction = stripped
            break
    if not first_instruction or not first_instruction.startswith("FROM "):
        issues.append("Missing or invalid FROM instruction")

    has_workdir = any(line.startswith("WORKDIR") for line in lines)
    if not has_workdir:
        issues.append("Missing WORKDIR instruction")

    has_copy = any(line.startswith("COPY") for line in lines)
    if not has_copy:
        issues.append("Missing COPY instruction")

    has_entrypoint = any(line.startswith("ENTRYPOINT") or line.startswith("CMD") for line in lines)
    if not has_entrypoint:
        issues.append("Missing ENTRYPOINT or CMD instruction")

    has_expose = any(line.startswith("EXPOSE") for line in lines)
    if not has_expose:
        issues.append("Missing EXPOSE instruction")

    return issues


def test_01_dockerfile():
    """Dockerfile 生成与验证"""
    config = {
        "base_image": "python:3.12-slim",
        "python_version": "3.12",
        "workdir": "/app",
        "app_port": 8000,
        "entrypoint": "uvicorn main:app --host 0.0.0.0 --port 8000",
        "env_vars": {
            "PYTHONUNBUFFERED": "1",
            "MODEL_PATH": "/app/models/model.pkl",
        },
    }

    dockerfile = generate_dockerfile(config)

    # 验证内容
    assert "FROM python:3.12-slim" in dockerfile
    assert "WORKDIR /app" in dockerfile
    assert "COPY requirements.txt ." in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "ENTRYPOINT" in dockerfile
    assert "PYTHONUNBUFFERED=1" in dockerfile
    assert "MODEL_PATH=/app/models/model.pkl" in dockerfile

    # 验证规范
    issues = validate_dockerfile(dockerfile)
    assert len(issues) == 0, f"Dockerfile issues: {issues}"

    # 生成 requirements.txt
    reqs = generate_requirements_txt(["numpy>=1.24", "scikit-learn>=1.3", "fastapi>=0.100", "uvicorn>=0.23"])
    assert "numpy>=1.24" in reqs
    assert "fastapi>=0.100" in reqs
    print("✅ test_01 Dockerfile 通过")


# ============================================================
# 2. 多阶段构建（Multi-stage Build）
# ============================================================

def generate_multistage_dockerfile(config):
    """生成多阶段构建 Dockerfile（builder + runtime）"""
    builder_lines = [
        f"# Stage 1: Builder",
        f"FROM python:{config.get('python_version', '3.12')}-slim AS builder",
        f"",
        f"WORKDIR /build",
        f"",
        f"# Install build dependencies",
        f"RUN pip install --user --no-cache-dir wheel setuptools",
        f"",
        f"# Install Python packages to user directory",
        f"COPY requirements.txt .",
        f"RUN pip install --user --no-cache-dir -r requirements.txt",
        f"",
    ]

    runtime_lines = [
        f"# Stage 2: Runtime",
        f"FROM python:{config.get('python_version', '3.12')}-slim AS runtime",
        f"",
        f"# Copy installed packages from builder",
        f"COPY --from=builder /root/.local /root/.local",
        f"",
        f"WORKDIR /app",
        f"",
        f"# Copy application code",
        f"COPY . .",
        f"",
        f"# Set PATH for user packages",
        f"ENV PATH=/root/.local/bin:$PATH",
        f"ENV PYTHONPATH=/app",
        f"",
    ]

    port = config.get("app_port", 8000)
    runtime_lines.extend([
        f"EXPOSE {port}",
        f"",
        f'CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "{port}"]',
    ])

    return "\n".join(builder_lines + runtime_lines) + "\n"


def test_02_multistage_build():
    """多阶段构建 Dockerfile"""
    config = {
        "python_version": "3.12",
        "app_port": 8080,
    }

    dockerfile = generate_multistage_dockerfile(config)

    # 验证有两个 FROM（多阶段）
    from_count = dockerfile.count("FROM ")
    assert from_count == 2, f"Expected 2 FROM instructions, got {from_count}"

    # 验证 builder 阶段
    assert "AS builder" in dockerfile
    assert "AS runtime" in dockerfile
    assert "/build" in dockerfile

    # 验证 COPY --from=builder
    assert "COPY --from=builder" in dockerfile

    # 验证 runtime 阶段
    assert "WORKDIR /app" in dockerfile
    assert "EXPOSE 8080" in dockerfile
    assert "CMD" in dockerfile

    # 验证验证通过
    issues = validate_dockerfile(dockerfile)
    assert len(issues) == 0, f"Multi-stage issues: {issues}"
    print("✅ test_02 多阶段构建通过")


# ============================================================
# 3. Kubernetes 部署清单
# ============================================================

def generate_k8s_deployment(config):
    """
    生成 Kubernetes Deployment + Service YAML
    config: {
        "app_name": str,
        "image": str,
        "replicas": int,
        "port": int,
        "env_vars": dict,
        "resources": {"limits": {"cpu": str, "memory": str}, "requests": {...}},
        "health_probe_path": str,
        "service_type": str,  # ClusterIP, NodePort, LoadBalancer
    }
    """
    app_name = config["app_name"]
    image = config["image"]
    replicas = config.get("replicas", 3)
    port = config.get("port", 8000)
    env_vars = config.get("env_vars", {})
    resources = config.get("resources", {
        "requests": {"cpu": "100m", "memory": "128Mi"},
        "limits": {"cpu": "500m", "memory": "512Mi"},
    })
    probe_path = config.get("health_probe_path", "/health")
    service_type = config.get("service_type", "ClusterIP")

    labels = {"app": app_name, "tier": "backend"}

    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": app_name, "labels": labels},
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": labels},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "containers": [{
                        "name": app_name,
                        "image": image,
                        "ports": [{"containerPort": port}],
                        "env": [{"name": k, "value": str(v)} for k, v in env_vars.items()],
                        "resources": resources,
                        "livenessProbe": {
                            "httpGet": {"path": probe_path, "port": port},
                            "initialDelaySeconds": 15,
                            "periodSeconds": 10,
                        },
                        "readinessProbe": {
                            "httpGet": {"path": probe_path, "port": port},
                            "initialDelaySeconds": 5,
                            "periodSeconds": 5,
                        },
                    }]
                }
            }
        }
    }

    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": f"{app_name}-service", "labels": labels},
        "spec": {
            "type": service_type,
            "selector": labels,
            "ports": [{"port": port, "targetPort": port, "protocol": "TCP"}],
        }
    }

    return {"deployment": deployment, "service": service}


def generate_k8s_hpa(config):
    """生成 Horizontal Pod Autoscaler"""
    app_name = config["app_name"]
    port = config.get("port", 8000)
    return {
        "apiVersion": "autoscaling/v2",
        "kind": "HorizontalPodAutoscaler",
        "metadata": {"name": f"{app_name}-hpa"},
        "spec": {
            "scaleTargetRef": {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "name": app_name,
            },
            "minReplicas": config.get("min_replicas", 2),
            "maxReplicas": config.get("max_replicas", 10),
            "metrics": [{
                "type": "Resource",
                "resource": {
                    "name": "cpu",
                    "target": {"type": "Utilization", "averageUtilization": config.get("target_cpu", 70)},
                }
            }],
        }
    }


def test_03_kubernetes_manifest():
    """Kubernetes 部署清单生成与验证"""
    config = {
        "app_name": "ml-inference-service",
        "image": "registry.example.com/ml-service:v2.0",
        "replicas": 3,
        "port": 8080,
        "env_vars": {"MODEL_PATH": "/models/iris.pkl", "BATCH_SIZE": "32"},
        "resources": {
            "requests": {"cpu": "250m", "memory": "256Mi"},
            "limits": {"cpu": "1000m", "memory": "1Gi"},
        },
        "service_type": "LoadBalancer",
    }

    manifests = generate_k8s_deployment(config)

    # 验证 Deployment
    dep = manifests["deployment"]
    assert dep["kind"] == "Deployment"
    assert dep["metadata"]["name"] == "ml-inference-service"
    assert dep["spec"]["replicas"] == 3

    container = dep["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "registry.example.com/ml-service:v2.0"
    assert container["ports"][0]["containerPort"] == 8080

    # 验证环境变量
    env_dict = {e["name"]: e["value"] for e in container["env"]}
    assert env_dict["MODEL_PATH"] == "/models/iris.pkl"
    assert env_dict["BATCH_SIZE"] == "32"

    # 验证资源限制
    assert container["resources"]["limits"]["cpu"] == "1000m"
    assert container["resources"]["limits"]["memory"] == "1Gi"
    assert container["resources"]["requests"]["cpu"] == "250m"

    # 验证健康检查
    assert container["livenessProbe"]["httpGet"]["path"] == "/health"
    assert container["readinessProbe"]["httpGet"]["port"] == 8080

    # 验证 Service
    svc = manifests["service"]
    assert svc["kind"] == "Service"
    assert svc["spec"]["type"] == "LoadBalancer"
    assert svc["spec"]["ports"][0]["port"] == 8080

    # 验证 HPA
    hpa = generate_k8s_hpa({**config, "min_replicas": 2, "max_replicas": 10, "target_cpu": 70})
    assert hpa["kind"] == "HorizontalPodAutoscaler"
    assert hpa["spec"]["minReplicas"] == 2
    assert hpa["spec"]["maxReplicas"] == 10
    assert hpa["spec"]["metrics"][0]["resource"]["target"]["averageUtilization"] == 70

    # 验证可序列化为 YAML
    combined_yaml = yaml.dump_all([dep, svc, hpa], default_flow_style=False)
    assert "Deployment" in combined_yaml
    assert "Service" in combined_yaml
    assert "HorizontalPodAutoscaler" in combined_yaml
    print("✅ test_03 Kubernetes清单通过")


# ============================================================
# 4. 健康检查端点
# ============================================================

class HealthChecker:
    """模型服务健康检查系统"""
    def __init__(self):
        self.checks = {}
        self.start_time = time.time()

    def register_check(self, name, check_func):
        """注册健康检查项"""
        self.checks[name] = check_func

    def run_checks(self):
        """执行所有健康检查"""
        results = {}
        all_healthy = True
        for name, func in self.checks.items():
            try:
                result = func()
                if isinstance(result, tuple):
                    healthy, detail = result
                else:
                    healthy = bool(result)
                    detail = "" if healthy else "Check returned False"
                results[name] = {"status": "healthy" if healthy else "unhealthy", "detail": detail}
                if not healthy:
                    all_healthy = False
            except Exception as e:
                results[name] = {"status": "error", "detail": str(e)}
                all_healthy = False
        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": time.time() - self.start_time,
            "checks": results,
        }

    def liveness(self):
        """存活检查：进程是否正常运行"""
        return {"status": "alive", "uptime": time.time() - self.start_time}

    def readiness(self):
        """就绪检查：是否可以接收流量"""
        result = self.run_checks()
        return {
            "ready": result["status"] == "healthy",
            "status": result["status"],
        }


def test_04_health_check():
    """健康检查端点"""
    checker = HealthChecker()

    # 注册检查项
    checker.register_check("model_loaded", lambda: (True, "Model loaded in memory"))
    checker.register_check("database_connected", lambda: (True, "DB connection OK"))
    checker.register_check("gpu_available", lambda: (False, "No GPU detected"))

    # 运行检查
    result = checker.run_checks()
    assert result["status"] == "unhealthy"  # GPU 不可用
    assert result["checks"]["model_loaded"]["status"] == "healthy"
    assert result["checks"]["database_connected"]["status"] == "healthy"
    assert result["checks"]["gpu_available"]["status"] == "unhealthy"
    assert "uptime_seconds" in result

    # 存活检查
    live = checker.liveness()
    assert live["status"] == "alive"
    assert live["uptime"] >= 0

    # 就绪检查
    ready = checker.readiness()
    assert ready["ready"] is False  # 因为 GPU 不健康

    # 修复后
    checker.checks["gpu_available"] = lambda: (True, "GPU available")
    ready2 = checker.readiness()
    assert ready2["ready"] is True

    # 错误处理
    checker.register_check("failing_check", lambda: 1/0)
    result2 = checker.run_checks()
    assert result2["checks"]["failing_check"]["status"] == "error"
    print("✅ test_04 健康检查通过")


# ============================================================
# 5. 模型推理服务
# ============================================================

class ModelServer:
    """模拟模型推理服务：加载模型、单次推理、批量推理"""
    def __init__(self):
        self.model = None
        self.is_loaded = False
        self.inference_count = 0
        self.total_latency = 0.0

    def load_model(self, model):
        self.model = model
        self.is_loaded = True

    def predict(self, features):
        """单次推理"""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")
        if not isinstance(features, (list, np.ndarray)):
            raise ValueError("Features must be list or array")

        features = np.array(features).reshape(1, -1) if np.array(features).ndim == 1 else np.array(features)
        start = time.time()
        prediction = self.model.predict(features)
        latency = time.time() - start

        self.inference_count += 1
        self.total_latency += latency
        return {
            "prediction": prediction.tolist() if hasattr(prediction, "tolist") else prediction,
            "latency_ms": latency * 1000,
        }

    def batch_predict(self, features_batch, batch_size=32):
        """批量推理"""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")

        features_batch = np.array(features_batch)
        if features_batch.ndim == 1:
            features_batch = features_batch.reshape(1, -1)

        total_samples = len(features_batch)
        results = []
        start = time.time()

        for i in range(0, total_samples, batch_size):
            batch = features_batch[i:i + batch_size]
            preds = self.model.predict(batch)
            results.extend(preds.tolist() if hasattr(preds, "tolist") else preds)

        total_latency = time.time() - start
        self.inference_count += total_samples
        self.total_latency += total_latency

        return {
            "predictions": results,
            "total_samples": total_samples,
            "batches": math.ceil(total_samples / batch_size),
            "latency_ms": total_latency * 1000,
            "throughput": total_samples / total_latency if total_latency > 0 else 0,
        }

    def get_metrics(self):
        avg_latency = (self.total_latency / self.inference_count * 1000) if self.inference_count > 0 else 0
        return {
            "is_loaded": self.is_loaded,
            "total_inferences": self.inference_count,
            "avg_latency_ms": avg_latency,
            "total_latency_ms": self.total_latency * 1000,
        }


def test_05_model_serving():
    """模型推理服务"""
    # 准备模型
    X, y = make_classification(n_samples=500, n_features=4, n_classes=2, random_state=42)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = LogisticRegression(max_iter=200)
    model.fit(X_train, y_train)

    server = ModelServer()

    # 未加载模型时报错
    try:
        server.predict([1, 2, 3, 4])
        assert False, "Should raise error"
    except RuntimeError:
        pass

    # 加载模型
    server.load_model(model)
    assert server.is_loaded is True

    # 单次推理
    result = server.predict(X_test[0])
    assert "prediction" in result
    assert "latency_ms" in result
    assert result["latency_ms"] >= 0

    # 批量推理
    batch_result = server.batch_predict(X_test[:50], batch_size=16)
    assert batch_result["total_samples"] == 50
    assert batch_result["batches"] == 4  # 50/16 = 3.125 → 4 batches
    assert len(batch_result["predictions"]) == 50
    assert batch_result["throughput"] > 0

    # 验证准确率
    acc = accuracy_score(y_test[:50], batch_result["predictions"])
    assert acc > 0.7

    # 服务指标
    metrics = server.get_metrics()
    assert metrics["is_loaded"] is True
    assert metrics["total_inferences"] == 51  # 1 single + 50 batch
    assert metrics["avg_latency_ms"] >= 0
    print("✅ test_05 模型推理服务通过")


# ============================================================
# 6. 推理优化（量化模拟）
# ============================================================

class InferenceOptimizer:
    """推理优化：FP32→FP16→INT8 量化模拟 + 动态批处理"""

    @staticmethod
    def simulate_quantization(weights, precision="int8"):
        """
        模拟权重量化
        FP32 → INT8: scale + zero_point + clip + round
        FP32 → FP16: 直接截断到半精度
        """
        weights = np.array(weights, dtype=np.float32)

        if precision == "fp16":
            # 模拟 FP16 精度（减少有效位数）
            quantized = np.float16(weights).astype(np.float32)
            return quantized, 0.0, 0.0

        elif precision == "int8":
            # 对称量化
            max_val = np.max(np.abs(weights))
            if max_val == 0:
                return np.zeros_like(weights), 0.0, 0.0
            scale = max_val / 127.0
            quantized = np.round(weights / scale).clip(-128, 127).astype(np.int8)
            # 反量化
            dequantized = (quantized.astype(np.float32) * scale)
            return dequantized, float(scale), 0.0

        elif precision == "int4":
            # 4-bit 量化
            max_val = np.max(np.abs(weights))
            if max_val == 0:
                return np.zeros_like(weights), 0.0, 0.0
            scale = max_val / 7.0
            quantized = np.round(weights / scale).clip(-8, 7).astype(np.int8)
            dequantized = (quantized.astype(np.float32) * scale)
            return dequantized, float(scale), 0.0

        return weights, 0.0, 0.0

    @staticmethod
    def compute_quantization_error(original, quantized):
        """计算量化误差（MSE + 最大偏差 + 信噪比）"""
        original = np.array(original, dtype=np.float32)
        quantized = np.array(quantized, dtype=np.float32)

        mse = float(np.mean((original - quantized) ** 2))
        max_diff = float(np.max(np.abs(original - quantized)))
        signal_power = float(np.mean(original ** 2))
        noise_power = mse if mse > 0 else 1e-10
        snr_db = 10 * math.log10(signal_power / noise_power) if signal_power > 0 else 0.0

        return {"mse": mse, "max_diff": max_diff, "snr_db": snr_db}

    @staticmethod
    def dynamic_batching(requests, max_batch_size=32, max_wait_ms=10):
        """
        动态批处理：收集请求直到达到 batch_size 或超时
        requests: list of {"id": int, "data": list, "arrival_time": float}
        """
        batches = []
        current_batch = []
        batch_start_time = None

        for req in sorted(requests, key=lambda r: r["arrival_time"]):
            if batch_start_time is None:
                batch_start_time = req["arrival_time"]

            current_batch.append(req)

            # 检查是否应该发出这个 batch
            should_flush = (
                len(current_batch) >= max_batch_size or
                (req["arrival_time"] - batch_start_time) >= max_wait_ms / 1000.0
            )

            if should_flush:
                batches.append({
                    "requests": [r["id"] for r in current_batch],
                    "size": len(current_batch),
                    "start_time": batch_start_time,
                    "end_time": req["arrival_time"],
                })
                current_batch = []
                batch_start_time = None

        # 处理剩余请求
        if current_batch:
            batches.append({
                "requests": [r["id"] for r in current_batch],
                "size": len(current_batch),
                "start_time": batch_start_time,
                "end_time": current_batch[-1]["arrival_time"],
            })

        return batches

    @staticmethod
    def estimate_speedup(precision, original_size_mb=100):
        """估算量化后推理加速比"""
        size_multipliers = {"fp32": 1.0, "fp16": 2.0, "int8": 4.0, "int4": 8.0}
        multiplier = size_multipliers.get(precision, 1.0)
        # 内存带宽提升 → 推理加速（经验估计，不是线性）
        speedup = 1.0 + (multiplier - 1.0) * 0.7
        return {
            "precision": precision,
            "size_multiplier": multiplier,
            "estimated_model_size_mb": original_size_mb / multiplier,
            "estimated_speedup": round(speedup, 2),
        }


def test_06_inference_optimization():
    """推理优化：量化 + 动态批处理"""
    np.random.seed(42)
    weights = np.random.randn(100).astype(np.float32) * 2.5

    # INT8 量化
    dequant_int8, scale_int8, _ = InferenceOptimizer.simulate_quantization(weights, "int8")
    assert scale_int8 > 0
    error_int8 = InferenceOptimizer.compute_quantization_error(weights, dequant_int8)
    assert error_int8["mse"] > 0
    assert error_int8["snr_db"] > 20  # INT8 应该有不错的 SNR

    # FP16 量化
    dequant_fp16, _, _ = InferenceOptimizer.simulate_quantization(weights, "fp16")
    error_fp16 = InferenceOptimizer.compute_quantization_error(weights, dequant_fp16)
    assert error_fp16["mse"] < error_int8["mse"]  # FP16 误差更小

    # INT4 量化（误差最大）
    dequant_int4, scale_int4, _ = InferenceOptimizer.simulate_quantization(weights, "int4")
    error_int4 = InferenceOptimizer.compute_quantization_error(weights, dequant_int4)
    assert error_int4["mse"] > error_int8["mse"]  # INT4 误差更大

    # 误差排序: INT4 > INT8 > FP16
    assert error_int4["mse"] > error_int8["mse"] > error_fp16["mse"]

    # 动态批处理
    requests = []
    for i in range(50):
        requests.append({
            "id": i,
            "data": [i, i+1, i+2, i+3],
            "arrival_time": i * 0.003,  # 每 3ms 来一个请求
        })

    batches = InferenceOptimizer.dynamic_batching(requests, max_batch_size=16, max_wait_ms=10)
    total_served = sum(b["size"] for b in batches)
    assert total_served == 50
    assert all(b["size"] <= 16 for b in batches)  # 不超过 max_batch_size
    assert len(batches) > 1  # 应该有多个 batch

    # 加速比估算
    speedup_int8 = InferenceOptimizer.estimate_speedup("int8", 200)
    assert speedup_int8["estimated_model_size_mb"] == 50  # 200/4
    assert speedup_int8["estimated_speedup"] > 1.0

    speedup_int4 = InferenceOptimizer.estimate_speedup("int4", 200)
    assert speedup_int4["estimated_model_size_mb"] == 25  # 200/8
    assert speedup_int4["estimated_speedup"] > speedup_int8["estimated_speedup"]
    print("✅ test_06 推理优化通过")


# ============================================================
# 7. 负载均衡器
# ============================================================

class LoadBalancer:
    """负载均衡器：支持轮询/加权轮询/最少连接"""
    def __init__(self, strategy="round_robin"):
        self.strategy = strategy
        self.backends = []  # [{"name": str, "weight": int, "connections": int, "healthy": bool}]
        self._rr_index = 0

    def add_backend(self, name, weight=1):
        self.backends.append({"name": name, "weight": weight, "connections": 0, "healthy": True})

    def remove_backend(self, name):
        self.backends = [b for b in self.backends if b["name"] != name]

    def get_backend(self):
        """根据策略选择后端"""
        healthy = [b for b in self.backends if b["healthy"]]
        if not healthy:
            return None

        if self.strategy == "round_robin":
            backend = healthy[self._rr_index % len(healthy)]
            self._rr_index = (self._rr_index + 1) % len(healthy)
            return backend["name"]

        elif self.strategy == "weighted_round_robin":
            # 扩展列表按权重
            expanded = []
            for b in healthy:
                expanded.extend([b] * b["weight"])
            backend = expanded[self._rr_index % len(expanded)]
            self._rr_index = (self._rr_index + 1) % len(expanded)
            return backend["name"]

        elif self.strategy == "least_connections":
            backend = min(healthy, key=lambda b: b["connections"])
            return backend["name"]

        return healthy[0]["name"]

    def increment_connections(self, name):
        for b in self.backends:
            if b["name"] == name:
                b["connections"] += 1
                return

    def decrement_connections(self, name):
        for b in self.backends:
            if b["name"] == name:
                b["connections"] = max(0, b["connections"] - 1)
                return

    def set_health(self, name, healthy):
        for b in self.backends:
            if b["name"] == name:
                b["healthy"] = healthy
                return

    def get_stats(self):
        return {
            "strategy": self.strategy,
            "total_backends": len(self.backends),
            "healthy_backends": sum(1 for b in self.backends if b["healthy"]),
            "backends": [{"name": b["name"], "weight": b["weight"], "connections": b["connections"], "healthy": b["healthy"]} for b in self.backends],
        }


def test_07_load_balancing():
    """负载均衡器"""
    # 轮询
    lb_rr = LoadBalancer("round_robin")
    lb_rr.add_backend("backend-1")
    lb_rr.add_backend("backend-2")
    lb_rr.add_backend("backend-3")

    selections = [lb_rr.get_backend() for _ in range(9)]
    # 应该均匀分配
    from collections import Counter
    counts = Counter(selections)
    assert all(c == 3 for c in counts.values()), f"Uneven distribution: {counts}"

    # 加权轮询
    lb_wrr = LoadBalancer("weighted_round_robin")
    lb_wrr.add_backend("backend-1", weight=1)
    lb_wrr.add_backend("backend-2", weight=2)
    lb_wrr.add_backend("backend-3", weight=1)

    selections = [lb_wrr.get_backend() for _ in range(8)]
    counts = Counter(selections)
    assert counts["backend-2"] == 4  # weight=2 → 占一半
    assert counts["backend-1"] == 2
    assert counts["backend-3"] == 2

    # 最少连接
    lb_lc = LoadBalancer("least_connections")
    lb_lc.add_backend("backend-1")
    lb_lc.add_backend("backend-2")
    lb_lc.add_backend("backend-3")

    # 模拟连接
    lb_lc.increment_connections("backend-1")
    lb_lc.increment_connections("backend-1")
    lb_lc.increment_connections("backend-2")

    # 下一个应该选 backend-3（连接最少）
    selected = lb_lc.get_backend()
    assert selected == "backend-3"

    # 健康检查
    lb_rr.set_health("backend-1", False)
    selections = [lb_rr.get_backend() for _ in range(6)]
    assert "backend-1" not in selections  # 不健康的后端不被选中
    counts = Counter(selections)
    assert all(c == 3 for c in counts.values())  # backend-2 和 backend-3 各 3 次

    # 统计
    stats = lb_rr.get_stats()
    assert stats["total_backends"] == 3
    assert stats["healthy_backends"] == 2
    print("✅ test_07 负载均衡通过")


# ============================================================
# 8. 蓝绿部署
# ============================================================

class BlueGreenDeployment:
    """蓝绿部署：维护蓝/绿两套环境，切换流量"""
    def __init__(self):
        self.environments = {
            "blue": {"version": None, "status": "idle", "healthy": False, "replicas": 0},
            "green": {"version": None, "status": "idle", "healthy": False, "replicas": 0},
        }
        self.active = None
        self.traffic_split = {"blue": 0, "green": 0}
        self.deployment_history = []

    def deploy(self, target_env, version, replicas=3):
        """部署到目标环境"""
        if target_env not in self.environments:
            raise ValueError(f"Unknown environment: {target_env}")

        self.environments[target_env] = {
            "version": version,
            "status": "deploying",
            "healthy": False,
            "replicas": replicas,
        }

        self.deployment_history.append({
            "action": "deploy",
            "environment": target_env,
            "version": version,
            "replicas": replicas,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def health_check(self, env):
        """健康检查（模拟）"""
        if env not in self.environments:
            return False
        env_info = self.environments[env]
        if env_info["status"] != "deploying":
            return env_info["healthy"]
        # 模拟健康检查通过
        self.environments[env]["status"] = "running"
        self.environments[env]["healthy"] = True
        return True

    def switch_traffic(self, target_env, percentage=100):
        """切换流量到目标环境"""
        if target_env not in self.environments:
            raise ValueError(f"Unknown environment: {target_env}")
        if not self.environments[target_env]["healthy"]:
            raise RuntimeError(f"Environment {target_env} is not healthy")

        other_env = "green" if target_env == "blue" else "blue"
        self.traffic_split[target_env] = percentage
        self.traffic_split[other_env] = 100 - percentage

        if percentage == 100:
            self.active = target_env
            self.deployment_history.append({
                "action": "switch",
                "from": other_env,
                "to": target_env,
                "version": self.environments[target_env]["version"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def rollback(self):
        """回滚到之前的环境"""
        if self.active is None:
            raise RuntimeError("No active environment to rollback from")

        previous = "green" if self.active == "blue" else "blue"
        if not self.environments[previous]["healthy"]:
            raise RuntimeError(f"Previous environment {previous} is not healthy")

        self.traffic_split = {self.active: 0, previous: 100}
        self.active = previous
        self.deployment_history.append({
            "action": "rollback",
            "to": previous,
            "version": self.environments[previous]["version"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return previous

    def get_status(self):
        return {
            "active": self.active,
            "traffic_split": dict(self.traffic_split),
            "environments": copy.deepcopy(self.environments),
        }


def test_08_blue_green():
    """蓝绿部署"""
    bg = BlueGreenDeployment()

    # 初始部署到 blue
    bg.deploy("blue", "v1.0.0", replicas=3)
    assert bg.environments["blue"]["status"] == "deploying"

    # 健康检查
    assert bg.health_check("blue") is True
    assert bg.environments["blue"]["healthy"] is True

    # 切换流量到 blue
    bg.switch_traffic("blue", 100)
    assert bg.active == "blue"
    assert bg.traffic_split["blue"] == 100
    assert bg.traffic_split["green"] == 0

    # 部署新版本到 green
    bg.deploy("green", "v2.0.0", replicas=3)
    assert bg.health_check("green") is True

    # 切换流量到 green
    bg.switch_traffic("green", 100)
    assert bg.active == "green"
    assert bg.traffic_split["green"] == 100
    assert bg.traffic_split["blue"] == 0

    # 回滚到 blue
    previous = bg.rollback()
    assert previous == "blue"
    assert bg.active == "blue"
    assert bg.traffic_split["blue"] == 100

    # 部署历史
    assert len(bg.deployment_history) >= 3  # deploy + switch + rollback

    # 状态检查
    status = bg.get_status()
    assert status["active"] == "blue"
    assert status["traffic_split"]["blue"] == 100

    # 部署到不健康环境时报错
    bg.deploy("green", "v3.0.0")
    # green 还在 deploying，不能切换
    try:
        bg.switch_traffic("green", 100)
        assert False, "Should fail - green not healthy yet"
    except RuntimeError:
        pass
    print("✅ test_08 蓝绿部署通过")


# ============================================================
# 9. 金丝雀部署
# ============================================================

class CanaryDeployment:
    """金丝雀部署：渐进式流量切换"""
    def __init__(self, stages=None):
        self.stages = stages or [5, 25, 50, 100]  # 流量百分比阶段
        self.current_stage = -1
        self.stable_version = None
        self.canary_version = None
        self.canary_metrics = {"error_rate": 0.0, "latency_p99": 0.0, "success_rate": 1.0}
        self.rollback_thresholds = {"error_rate": 0.05, "latency_p99_ms": 500}
        self.history = []

    def start(self, stable_version, canary_version):
        self.stable_version = stable_version
        self.canary_version = canary_version
        self.current_stage = 0
        self.history.append({
            "action": "start",
            "stable": stable_version,
            "canary": canary_version,
            "canary_traffic": self.stages[0],
        })

    def promote(self):
        """提升到下一阶段"""
        if self.current_stage < 0:
            raise RuntimeError("Canary deployment not started")
        if self.current_stage >= len(self.stages) - 1:
            raise RuntimeError("Already at final stage")

        # 检查指标是否达标
        if not self._check_metrics():
            return self.rollback()

        self.current_stage += 1
        self.history.append({
            "action": "promote",
            "stage": self.current_stage,
            "canary_traffic": self.stages[self.current_stage],
        })
        return {"status": "promoted", "canary_traffic": self.stages[self.current_stage]}

    def update_metrics(self, error_rate, latency_p99_ms, success_rate):
        self.canary_metrics = {
            "error_rate": error_rate,
            "latency_p99": latency_p99_ms,
            "success_rate": success_rate,
        }

    def _check_metrics(self):
        """检查金丝雀指标是否在阈值内"""
        return (
            self.canary_metrics["error_rate"] < self.rollback_thresholds["error_rate"] and
            self.canary_metrics["latency_p99"] < self.rollback_thresholds["latency_p99_ms"]
        )

    def rollback(self):
        """回滚金丝雀"""
        self.current_stage = -1
        self.canary_version = None
        self.history.append({
            "action": "rollback",
            "reason": "metrics threshold exceeded",
        })
        return {"status": "rolled_back", "reason": "metrics threshold exceeded"}

    def get_traffic_split(self):
        if self.current_stage < 0:
            return {"stable": 100, "canary": 0}
        canary_pct = self.stages[self.current_stage]
        return {"stable": 100 - canary_pct, "canary": canary_pct}

    def is_complete(self):
        return self.current_stage == len(self.stages) - 1


def test_09_canary_deployment():
    """金丝雀部署"""
    canary = CanaryDeployment(stages=[5, 25, 50, 100])

    # 启动金丝雀
    canary.start("v1.0.0", "v2.0.0")
    assert canary.current_stage == 0
    split = canary.get_traffic_split()
    assert split["canary"] == 5
    assert split["stable"] == 95

    # 更新指标（正常）
    canary.update_metrics(error_rate=0.01, latency_p99_ms=100, success_rate=0.99)

    # 提升到 25%
    result = canary.promote()
    assert result["status"] == "promoted"
    assert canary.get_traffic_split()["canary"] == 25

    # 提升到 50%
    canary.update_metrics(error_rate=0.02, latency_p99_ms=200, success_rate=0.98)
    result = canary.promote()
    assert result["status"] == "promoted"
    assert canary.get_traffic_split()["canary"] == 50

    # 指标恶化 → 回滚
    canary.update_metrics(error_rate=0.08, latency_p99_ms=300, success_rate=0.92)
    result = canary.promote()
    assert result["status"] == "rolled_back"
    assert canary.get_traffic_split()["canary"] == 0
    assert canary.get_traffic_split()["stable"] == 100

    # 重新开始，全部正常完成
    canary2 = CanaryDeployment(stages=[5, 25, 50, 100])
    canary2.start("v1.0.0", "v3.0.0")
    canary2.update_metrics(error_rate=0.01, latency_p99_ms=100, success_rate=0.99)
    canary2.promote()  # → 25%
    canary2.update_metrics(error_rate=0.01, latency_p99_ms=120, success_rate=0.99)
    canary2.promote()  # → 50%
    canary2.update_metrics(error_rate=0.02, latency_p99_ms=150, success_rate=0.98)
    canary2.promote()  # → 100%
    assert canary2.is_complete() is True
    assert canary2.get_traffic_split()["canary"] == 100
    print("✅ test_09 金丝雀部署通过")


# ============================================================
# 10. 部署配置管理
# ============================================================

class DeploymentConfig:
    """部署配置管理：多环境配置 + 配置合并 + 敏感信息处理"""
    def __init__(self):
        self.environments = {}  # env_name -> config dict
        self.secrets = {}  # key -> encrypted_value placeholder

    def set_base_config(self, config):
        """设置基础配置（所有环境共享）"""
        self.environments["base"] = config

    def set_env_config(self, env_name, config):
        """设置环境特定配置"""
        self.environments[env_name] = config

    def get_effective_config(self, env_name):
        """获取合并后的有效配置（base + env 覆盖）"""
        base = copy.deepcopy(self.environments.get("base", {}))
        env_config = copy.deepcopy(self.environments.get(env_name, {}))
        return self._deep_merge(base, env_config)

    def _deep_merge(self, base, override):
        """深度合并两个字典"""
        result = copy.deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    def add_secret(self, key, value):
        """添加敏感配置"""
        # 模拟加密（实际应使用 vault/kms）
        hashed = hashlib.sha256(value.encode()).hexdigest()[:32]
        self.secrets[key] = f"enc:{hashed}"

    def resolve_config(self, env_name):
        """解析最终配置，替换 secret 引用"""
        config = self.get_effective_config(env_name)
        self._resolve_secrets(config)
        return config

    def _resolve_secrets(self, config):
        for key, value in config.items():
            if isinstance(value, dict):
                self._resolve_secrets(value)
            elif isinstance(value, str) and value.startswith("${SECRET:"):
                secret_key = value[9:-1]  # ${SECRET:key} → key
                if secret_key in self.secrets:
                    config[key] = self.secrets[secret_key]

    def validate_config(self, env_name):
        """验证配置完整性"""
        config = self.get_effective_config(env_name)
        required_keys = ["app", "server", "database", "model"]
        missing = []
        for key in required_keys:
            if key not in config:
                missing.append(key)
        return {"valid": len(missing) == 0, "missing": missing}

    def export_yaml(self, env_name):
        """导出为 YAML"""
        config = self.resolve_config(env_name)
        return yaml.dump(config, default_flow_style=False, sort_keys=True)


def test_10_config_management():
    """部署配置管理"""
    dc = DeploymentConfig()

    # 基础配置
    dc.set_base_config({
        "app": {"name": "ml-service", "version": "1.0.0"},
        "server": {"host": "0.0.0.0", "port": 8000, "workers": 4},
        "database": {"host": "localhost", "port": 5432, "pool_size": 10},
        "model": {"path": "/models/default.pkl", "device": "cpu"},
    })

    # 开发环境覆盖
    dc.set_env_config("dev", {
        "server": {"port": 8080, "debug": True},
        "database": {"host": "dev-db.internal"},
        "model": {"path": "/models/dev.pkl"},
    })

    # 生产环境覆盖
    dc.set_env_config("prod", {
        "server": {"workers": 16},
        "database": {"host": "prod-db.internal", "pool_size": 50},
        "model": {"path": "/models/prod.pkl", "device": "cuda"},
    })

    # 验证 dev 配置合并
    dev_config = dc.get_effective_config("dev")
    assert dev_config["app"]["name"] == "ml-service"  # 来自 base
    assert dev_config["server"]["port"] == 8080  # 覆盖
    assert dev_config["server"]["host"] == "0.0.0.0"  # 来自 base
    assert dev_config["server"]["debug"] is True  # dev 新增
    assert dev_config["database"]["host"] == "dev-db.internal"  # 覆盖
    assert dev_config["database"]["port"] == 5432  # 来自 base
    assert dev_config["model"]["path"] == "/models/dev.pkl"  # 覆盖

    # 验证 prod 配置合并
    prod_config = dc.get_effective_config("prod")
    assert prod_config["server"]["workers"] == 16  # 覆盖
    assert prod_config["server"]["port"] == 8000  # 来自 base
    assert prod_config["database"]["pool_size"] == 50  # 覆盖
    assert prod_config["model"]["device"] == "cuda"  # 覆盖

    # 添加密钥
    dc.add_secret("DB_PASSWORD", "super_secret_123")
    dc.set_env_config("prod", {
        "server": {"workers": 16},
        "database": {"host": "prod-db.internal", "pool_size": 50, "password": "${SECRET:DB_PASSWORD}"},
        "model": {"path": "/models/prod.pkl", "device": "cuda"},
    })

    resolved = dc.resolve_config("prod")
    assert resolved["database"]["password"].startswith("enc:")

    # 配置验证
    validation = dc.validate_config("prod")
    assert validation["valid"] is True
    assert len(validation["missing"]) == 0

    # YAML 导出
    yaml_str = dc.export_yaml("prod")
    assert "ml-service" in yaml_str
    assert "prod-db.internal" in yaml_str
    assert "cuda" in yaml_str
    print("✅ test_10 配置管理通过")


# ============================================================
# 主函数
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("第五阶段 5.2 容器化与部署练习")
    print("=" * 60)
    tests = [
        test_01_dockerfile,
        test_02_multistage_build,
        test_03_kubernetes_manifest,
        test_04_health_check,
        test_05_model_serving,
        test_06_inference_optimization,
        test_07_load_balancing,
        test_08_blue_green,
        test_09_canary_deployment,
        test_10_config_management,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print("=" * 60)
    print(f"结果: {passed}/{passed + failed} 通过")
    if failed == 0:
        print("🎉 全部通过！")
    print("=" * 60)
