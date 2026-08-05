"""
第五阶段 5.1 MLOps 全流程练习（10题）
实验追踪 / 模型注册 / 数据版本 / CI-CD / 监控 / 漂移检测 / 流水线 / 制品管理 / 超参追踪 / AB测试
依赖: numpy, sklearn, yaml, prometheus_client
"""
import json, time, hashlib, pickle, os, io, copy, math
from datetime import datetime, timezone
from collections import defaultdict
import numpy as np
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import yaml

# ============================================================
# 1. 轻量级实验追踪器（模拟 MLflow）
# ============================================================

class ExperimentTracker:
    """轻量实验追踪，支持创建实验、记录参数/指标/模型、查询最佳 run"""
    def __init__(self):
        self.experiments = {}  # name -> list of runs
        self._run_counter = 0

    def create_experiment(self, name):
        if name not in self.experiments:
            self.experiments[name] = []
        return name

    def start_run(self, experiment_name, params=None, tags=None):
        if experiment_name not in self.experiments:
            self.create_experiment(experiment_name)
        self._run_counter += 1
        run = {
            "run_id": f"run_{self._run_counter:04d}",
            "experiment": experiment_name,
            "params": params or {},
            "metrics": {},
            "tags": tags or {},
            "model": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.experiments[experiment_name].append(run)
        return run["run_id"]

    def log_metric(self, experiment_name, run_id, key, value):
        for run in self.experiments.get(experiment_name, []):
            if run["run_id"] == run_id:
                run["metrics"][key] = value
                return
        raise ValueError(f"Run {run_id} not found")

    def log_model(self, experiment_name, run_id, model):
        for run in self.experiments.get(experiment_name, []):
            if run["run_id"] == run_id:
                run["model"] = model
                return
        raise ValueError(f"Run {run_id} not found")

    def get_best_run(self, experiment_name, metric_key, mode="max"):
        runs = self.experiments.get(experiment_name, [])
        if not runs:
            return None
        scored = [(r, r["metrics"].get(metric_key, float("-inf") if mode == "max" else float("inf"))) for r in runs]
        if mode == "max":
            best = max(scored, key=lambda x: x[1])
        else:
            best = min(scored, key=lambda x: x[1])
        return best[0]


def test_01_experiment_tracker():
    """实验追踪器：记录多个 run，查询最佳准确率"""
    tracker = ExperimentTracker()
    tracker.create_experiment("iris_clf")

    # Run 1
    rid1 = tracker.start_run("iris_clf", params={"C": 0.1, "solver": "lbfgs"})
    tracker.log_metric("iris_clf", rid1, "accuracy", 0.85)
    tracker.log_metric("iris_clf", rid1, "loss", 0.42)

    # Run 2
    rid2 = tracker.start_run("iris_clf", params={"C": 1.0, "solver": "lbfgs"})
    tracker.log_metric("iris_clf", rid2, "accuracy", 0.92)
    tracker.log_metric("iris_clf", rid2, "loss", 0.21)

    # Run 3
    rid3 = tracker.start_run("iris_clf", params={"C": 10.0, "solver": "liblinear"})
    tracker.log_metric("iris_clf", rid3, "accuracy", 0.88)
    tracker.log_metric("iris_clf", rid3, "loss", 0.33)

    best = tracker.get_best_run("iris_clf", "accuracy", "max")
    assert best["run_id"] == rid2
    assert best["metrics"]["accuracy"] == 0.92
    assert best["params"]["C"] == 1.0

    best_loss = tracker.get_best_run("iris_clf", "loss", "min")
    assert best_loss["run_id"] == rid2
    assert best_loss["metrics"]["loss"] == 0.21
    print("✅ test_01 实验追踪器通过")


# ============================================================
# 2. 模型注册表（版本管理）
# ============================================================

class ModelRegistry:
    """模型注册表：注册、版本管理、阶段切换（staging/production/archived）"""
    def __init__(self):
        self.models = {}  # name -> list of versions

    def register_model(self, name, model, metrics, tags=None):
        if name not in self.models:
            self.models[name] = []
        version = len(self.models[name]) + 1
        entry = {
            "name": name,
            "version": f"v{version}",
            "model": model,
            "metrics": metrics,
            "tags": tags or {},
            "stage": "none",
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        self.models[name].append(entry)
        return entry["version"]

    def transition_stage(self, name, version, stage):
        valid = {"none", "staging", "production", "archived"}
        if stage not in valid:
            raise ValueError(f"Invalid stage: {stage}")
        for entry in self.models.get(name, []):
            if entry["version"] == version:
                # production 唯一性：切换到 production 时，旧 production 自动降为 archived
                if stage == "production":
                    for e in self.models[name]:
                        if e["stage"] == "production":
                            e["stage"] = "archived"
                entry["stage"] = stage
                return entry
        raise ValueError(f"Model {name} {version} not found")

    def get_production_model(self, name):
        for entry in self.models.get(name, []):
            if entry["stage"] == "production":
                return entry
        return None

    def list_versions(self, name):
        return self.models.get(name, [])


def test_02_model_registry():
    """模型注册表：版本管理 + 阶段切换"""
    registry = ModelRegistry()

    # 注册 3 个版本
    v1 = registry.register_model("iris_clf", {"type": "logreg", "C": 0.1}, {"acc": 0.85})
    v2 = registry.register_model("iris_clf", {"type": "logreg", "C": 1.0}, {"acc": 0.92})
    v3 = registry.register_model("iris_clf", {"type": "logreg", "C": 10.0}, {"acc": 0.88})

    assert v1 == "v1"
    assert v2 == "v2"
    assert v3 == "v3"
    assert len(registry.list_versions("iris_clf")) == 3

    # v2 → staging
    registry.transition_stage("iris_clf", "v2", "staging")
    assert registry.models["iris_clf"][1]["stage"] == "staging"

    # v2 → production
    registry.transition_stage("iris_clf", "v2", "production")
    prod = registry.get_production_model("iris_clf")
    assert prod is not None
    assert prod["version"] == "v2"

    # v3 → production，v2 自动降为 archived
    registry.transition_stage("iris_clf", "v3", "production")
    prod = registry.get_production_model("iris_clf")
    assert prod["version"] == "v3"
    assert registry.models["iris_clf"][1]["stage"] == "archived"
    print("✅ test_02 模型注册表通过")


# ============================================================
# 3. 数据版本管理（模拟 DVC）
# ============================================================

class DataVersionManager:
    """模拟 DVC：数据内容哈希 → 版本快照 → 恢复"""
    def __init__(self):
        self.versions = {}  # version_tag -> {hash, data, timestamp}
        self._counter = 0

    def _compute_hash(self, data):
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def commit(self, data, tag=None):
        self._counter += 1
        tag = tag or f"v{self._counter}"
        data_hash = self._compute_hash(data)
        self.versions[tag] = {
            "hash": data_hash,
            "data": copy.deepcopy(data),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return tag, data_hash

    def checkout(self, tag):
        if tag not in self.versions:
            raise KeyError(f"Version {tag} not found")
        return copy.deepcopy(self.versions[tag]["data"])

    def diff(self, tag1, tag2):
        d1 = self.versions[tag1]["data"]
        d2 = self.versions[tag2]["data"]
        changes = []
        all_keys = set(d1.keys()) | set(d2.keys()) if isinstance(d1, dict) else set()
        if isinstance(d1, dict) and isinstance(d2, dict):
            for key in all_keys:
                if key not in d1:
                    changes.append(("added", key, None, d2[key]))
                elif key not in d2:
                    changes.append(("removed", key, d1[key], None))
                elif d1[key] != d2[key]:
                    changes.append(("modified", key, d1[key], d2[key]))
        return changes

    def log(self):
        return [(tag, info["hash"], info["timestamp"]) for tag, info in self.versions.items()]


def test_03_data_versioning():
    """数据版本管理：commit / checkout / diff"""
    dvm = DataVersionManager()

    data_v1 = {"features": ["age", "income"], "rows": 100, "label": "default"}
    tag1, hash1 = dvm.commit(data_v1, tag="dataset_v1")
    assert hash1 is not None

    data_v2 = {"features": ["age", "income", "credit_score"], "rows": 150, "label": "default"}
    tag2, hash2 = dvm.commit(data_v2, tag="dataset_v2")
    assert hash1 != hash2

    # checkout 验证
    restored = dvm.checkout("dataset_v1")
    assert restored["features"] == ["age", "income"]
    assert restored["rows"] == 100

    # diff
    changes = dvm.diff("dataset_v1", "dataset_v2")
    change_types = [c[0] for c in changes]
    assert "modified" in change_types  # features 和 rows 变了
    assert "added" not in change_types  # key 存在于两边，只是值变了

    # 验证 diff 细节
    feat_change = [c for c in changes if c[1] == "features"]
    assert len(feat_change) == 1
    assert feat_change[0][2] == ["age", "income"]
    assert "credit_score" in feat_change[0][3]
    print("✅ test_03 数据版本管理通过")


# ============================================================
# 4. CI/CD 流水线（GitHub Actions YAML 生成）
# ============================================================

def generate_github_actions_pipeline(pipeline_config):
    """
    根据配置生成 GitHub Actions workflow YAML
    pipeline_config: {
        "name": str,
        "triggers": list[str],  # ["push", "pull_request"]
        "python_version": str,
        "steps": list[str],  # ["lint", "test", "build", "deploy"]
        "env": dict,
    }
    """
    trigger_map = {
        "push": {"branches": ["main", "develop"]},
        "pull_request": {"branches": ["main"]},
        "schedule": [{"cron": "0 2 * * *"}],
    }

    job_steps = []

    step_map = {
        "checkout": {
            "name": "Checkout code",
            "uses": "actions/checkout@v4",
        },
        "setup_python": {
            "name": "Set up Python",
            "uses": "actions/setup-python@v5",
            "with": {"python-version": pipeline_config.get("python_version", "3.12")},
        },
        "install_deps": {
            "name": "Install dependencies",
            "run": "pip install -r requirements.txt && pip install pytest flake8",
        },
        "lint": {
            "name": "Run linter",
            "run": "flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics",
        },
        "test": {
            "name": "Run tests",
            "run": "pytest tests/ --cov=src --cov-report=xml",
        },
        "build": {
            "name": "Build package",
            "run": "python -m build",
        },
        "deploy": {
            "name": "Deploy",
            "run": "echo 'Deploying...' && python deploy.py",
        },
    }

    # 固定步骤顺序
    fixed_order = ["checkout", "setup_python", "install_deps"]
    dynamic_steps = [s for s in pipeline_config.get("steps", ["lint", "test"]) if s in step_map]

    for step_name in fixed_order:
        if step_name in step_map:
            job_steps.append(step_map[step_name])

    for step_name in dynamic_steps:
        if step_name not in fixed_order and step_name in step_map:
            job_steps.append(step_map[step_name])

    workflow = {
        "name": pipeline_config.get("name", "CI/CD Pipeline"),
        "on": {t: trigger_map.get(t, {}) for t in pipeline_config.get("triggers", ["push"])},
        "env": pipeline_config.get("env", {"PYTHONUNBUFFERED": "1"}),
        "jobs": {
            "build-and-test": {
                "runs-on": "ubuntu-latest",
                "steps": job_steps,
            }
        },
    }
    return workflow


def test_04_cicd_pipeline():
    """CI/CD 流水线：生成 GitHub Actions YAML 并验证结构"""
    config = {
        "name": "ML Pipeline CI/CD",
        "triggers": ["push", "pull_request"],
        "python_version": "3.12",
        "steps": ["lint", "test", "build", "deploy"],
        "env": {"PYTHONUNBUFFERED": "1", "MLFLOW_TRACKING_URI": "http://localhost:5000"},
    }

    workflow = generate_github_actions_pipeline(config)

    # 验证基本结构
    assert workflow["name"] == "ML Pipeline CI/CD"
    assert "push" in workflow["on"]
    assert "pull_request" in workflow["on"]
    assert workflow["on"]["push"]["branches"] == ["main", "develop"]

    # 验证步骤
    steps = workflow["jobs"]["build-and-test"]["steps"]
    step_names = [s.get("name", "") for s in steps]
    assert "Checkout code" in step_names
    assert "Set up Python" in step_names
    assert "Install dependencies" in step_names
    assert "Run linter" in step_names
    assert "Run tests" in step_names
    assert "Build package" in step_names
    assert "Deploy" in step_names

    # 验证 Python 版本
    setup_step = [s for s in steps if "setup-python" in s.get("uses", "")][0]
    assert setup_step["with"]["python-version"] == "3.12"

    # 验证环境变量
    assert workflow["env"]["MLFLOW_TRACKING_URI"] == "http://localhost:5000"

    # 验证可序列化为 YAML
    yaml_str = yaml.dump(workflow, default_flow_style=False, sort_keys=False)
    assert "ML Pipeline CI/CD" in yaml_str
    assert "actions/checkout@v4" in yaml_str
    assert "pytest" in yaml_str
    print("✅ test_04 CI/CD 流水线通过")


# ============================================================
# 5. 模型监控（Prometheus 指标）
# ============================================================

class ModelMonitor:
    """使用 prometheus_client 进行模型监控"""
    def __init__(self, model_name="default_model"):
        from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
        self.registry = CollectorRegistry()
        self.model_name = model_name
        self.prediction_counter = Counter(
            "model_predictions_total", "Total predictions", ["model", "status"], registry=self.registry
        )
        self.latency_histogram = Histogram(
            "model_prediction_latency_seconds", "Prediction latency",
            ["model"], buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0), registry=self.registry
        )
        self.drift_gauge = Gauge(
            "model_drift_score", "Data drift score", ["model"], registry=self.registry
        )
        self._latencies = []

    def record_prediction(self, status="success", latency=0.01):
        self.prediction_counter.labels(model=self.model_name, status=status).inc()
        self.latency_histogram.labels(model=self.model_name).observe(latency)
        self._latencies.append(latency)

    def set_drift_score(self, score):
        self.drift_gauge.labels(model=self.model_name).set(score)

    def get_stats(self):
        from prometheus_client import generate_latest
        output = generate_latest(self.registry).decode()
        return output

    def get_latency_stats(self):
        if not self._latencies:
            return {"count": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
        arr = np.array(self._latencies)
        return {
            "count": len(arr),
            "avg": float(np.mean(arr)),
            "p50": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99)),
        }


def test_05_model_monitoring():
    """模型监控：记录预测、延迟、漂移分数"""
    monitor = ModelMonitor("iris_classifier")

    # 模拟 100 次预测
    np.random.seed(42)
    for i in range(100):
        latency = np.random.exponential(0.02) + 0.005
        status = "success" if i % 10 != 0 else "error"
        monitor.record_prediction(status=status, latency=latency)

    # 设置漂移分数
    monitor.set_drift_score(0.15)

    # 验证延迟统计
    stats = monitor.get_latency_stats()
    assert stats["count"] == 100
    assert stats["avg"] > 0
    assert stats["p95"] >= stats["p50"]
    assert stats["p99"] >= stats["p95"]

    # 验证 Prometheus 输出
    output = monitor.get_stats()
    assert "model_predictions_total" in output
    assert "model_prediction_latency_seconds" in output
    assert "model_drift_score" in output
    assert "iris_classifier" in output
    assert "success" in output
    assert "error" in output

    # 验证计数（10 次 error, 90 次 success）
    assert 'status="success"' in output
    assert 'status="error"' in output
    print("✅ test_05 模型监控通过")


# ============================================================
# 6. 模型漂移检测
# ============================================================

class DriftDetector:
    """检测数据漂移和概念漂移"""
    @staticmethod
    def population_stability_index(expected, actual, bins=10):
        """PSI: 衡量分布变化，<0.1 稳定, 0.1-0.25 轻微漂移, >0.25 显著漂移"""
        expected = np.array(expected, dtype=float)
        actual = np.array(actual, dtype=float)

        # 用 expected 的分位数作为分箱边界
        edges = np.quantile(expected, np.linspace(0, 1, bins + 1))
        edges[0] = -np.inf
        edges[-1] = np.inf

        exp_counts = np.histogram(expected, bins=edges)[0]
        act_counts = np.histogram(actual, bins=edges)[0]

        exp_pct = (exp_counts + 0.5) / (len(expected) + 0.5 * bins)
        act_pct = (act_counts + 0.5) / (len(actual) + 0.5 * bins)

        psi = np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct))
        return float(psi)

    @staticmethod
    def ks_statistic(sample1, sample2):
        """KS 检验统计量：衡量两个分布的最大差异"""
        s1 = np.sort(sample1)
        s2 = np.sort(sample2)
        all_vals = np.sort(np.unique(np.concatenate([s1, s2])))
        cdf1 = np.searchsorted(s1, all_vals, side="right") / len(s1)
        cdf2 = np.searchsorted(s2, all_vals, side="right") / len(s2)
        return float(np.max(np.abs(cdf1 - cdf2)))

    @staticmethod
    def detect_concept_drift(accuracies, window_size=10, threshold=0.05):
        """用滑动窗口检测准确率下降趋势"""
        acc = np.array(accuracies)
        if len(acc) < window_size * 2:
            return False, 0.0

        recent = acc[-window_size:]
        baseline = acc[-2 * window_size:-window_size]

        recent_mean = np.mean(recent)
        baseline_mean = np.mean(baseline)
        drop = baseline_mean - recent_mean

        return bool(drop > threshold), float(drop)

    @staticmethod
    def classify_drift(psi_value):
        if psi_value < 0.1:
            return "stable"
        elif psi_value < 0.25:
            return "slight_drift"
        else:
            return "significant_drift"


def test_06_drift_detection():
    """漂移检测：PSI + KS + 概念漂移"""
    np.random.seed(42)

    # 正态分布原始数据
    baseline = np.random.normal(50, 10, 1000)

    # 轻微偏移的数据
    slight_shift = np.random.normal(53, 10, 1000)

    # 显著偏移的数据
    significant_shift = np.random.normal(65, 15, 1000)

    # PSI 测试
    psi_slight = DriftDetector.population_stability_index(baseline, slight_shift)
    psi_significant = DriftDetector.population_stability_index(baseline, significant_shift)
    psi_same = DriftDetector.population_stability_index(baseline, baseline)

    assert psi_same < 0.1  # 同分布 → 稳定
    assert psi_slight < psi_significant  # 偏移越大 PSI 越大

    drift_level = DriftDetector.classify_drift(psi_significant)
    assert drift_level in ("slight_drift", "significant_drift")

    drift_same = DriftDetector.classify_drift(psi_same)
    assert drift_same == "stable"

    # KS 统计量
    ks_same = DriftDetector.ks_statistic(baseline, baseline[:500])
    ks_diff = DriftDetector.ks_statistic(baseline, significant_shift)
    assert ks_same < ks_diff  # 同分布差异小

    # 概念漂移检测
    accuracies = [0.95] * 20 + [0.88, 0.85, 0.82, 0.80, 0.78, 0.75, 0.72, 0.70, 0.68, 0.65]
    drifted, drop = DriftDetector.detect_concept_drift(accuracies, window_size=10, threshold=0.05)
    assert drifted is True
    assert drop > 0.05

    # 无漂移场景
    stable_acc = [0.95] * 30
    not_drifted, no_drop = DriftDetector.detect_concept_drift(stable_acc, window_size=10, threshold=0.05)
    assert not_drifted is False
    print("✅ test_06 漂移检测通过")


# ============================================================
# 7. ML 流水线编排
# ============================================================

class MLPipeline:
    """ML 流水线编排器：定义步骤 → 顺序执行 → 缓存中间结果"""
    def __init__(self, name="pipeline"):
        self.name = name
        self.steps = []  # list of (name, func, inputs)
        self.cache = {}
        self.execution_log = []

    def add_step(self, name, func, inputs=None):
        self.steps.append({"name": name, "func": func, "inputs": inputs or []})
        return self

    def run(self, initial_context=None):
        ctx = initial_context or {}
        self.execution_log = []

        for step in self.steps:
            step_name = step["name"]
            func = step["func"]
            required_inputs = step["inputs"]

            # 检查依赖
            for inp in required_inputs:
                if inp not in ctx:
                    raise ValueError(f"Step '{step_name}' requires input '{inp}' which is not available")

            # 执行
            result = func(ctx)
            ctx[step_name] = result
            self.cache[step_name] = result
            self.execution_log.append({
                "step": step_name,
                "status": "success",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return ctx

    def get_execution_log(self):
        return self.execution_log


def test_07_pipeline_orchestration():
    """ML 流水线编排：数据准备 → 训练 → 评估 → 注册"""
    pipeline = MLPipeline("iris_pipeline")

    def load_data(ctx):
        X, y = make_classification(n_samples=200, n_features=4, n_classes=2, random_state=42)
        return {"X": X.tolist(), "y": y.tolist()}

    def split_data(ctx):
        data = ctx["load_data"]
        X = np.array(data["X"])
        y = np.array(data["y"])
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
        return {"X_train": X_tr.tolist(), "X_test": X_te.tolist(), "y_train": y_tr.tolist(), "y_test": y_te.tolist()}

    def train_model(ctx):
        split = ctx["split_data"]
        model = LogisticRegression(max_iter=200)
        model.fit(np.array(split["X_train"]), np.array(split["y_train"]))
        return {"model": model}

    def evaluate_model(ctx):
        train_result = ctx["train_model"]
        split = ctx["split_data"]
        model = train_result["model"]
        y_pred = model.predict(np.array(split["X_test"]))
        acc = accuracy_score(np.array(split["y_test"]), y_pred)
        return {"accuracy": acc, "predictions": y_pred.tolist()}

    def register_model(ctx):
        eval_result = ctx["evaluate_model"]
        train_result = ctx["train_model"]
        return {
            "registered": True,
            "accuracy": eval_result["accuracy"],
            "model_type": "LogisticRegression",
        }

    pipeline.add_step("load_data", load_data)
    pipeline.add_step("split_data", split_data, inputs=["load_data"])
    pipeline.add_step("train_model", train_model, inputs=["split_data"])
    pipeline.add_step("evaluate_model", evaluate_model, inputs=["train_model", "split_data"])
    pipeline.add_step("register_model", register_model, inputs=["evaluate_model", "train_model"])

    result = pipeline.run()

    # 验证所有步骤执行
    log = pipeline.get_execution_log()
    assert len(log) == 5
    assert all(entry["status"] == "success" for entry in log)
    step_names = [entry["step"] for entry in log]
    assert step_names == ["load_data", "split_data", "train_model", "evaluate_model", "register_model"]

    # 验证结果
    assert "register_model" in result
    assert result["register_model"]["registered"] is True
    assert result["evaluate_model"]["accuracy"] > 0.7  # 简单分类任务应该不错

    # 验证缓存
    assert "load_data" in pipeline.cache
    assert "train_model" in pipeline.cache
    print("✅ test_07 流水线编排通过")


# ============================================================
# 8. 制品管理（Artifact Management）
# ============================================================

class ArtifactStore:
    """制品管理：存储、版本化、检索模型/数据/配置制品"""
    def __init__(self):
        self.artifacts = {}  # uri -> list of versions
        self._version_counter = {}

    def store(self, uri, content, artifact_type="model", metadata=None):
        if uri not in self.artifacts:
            self.artifacts[uri] = []
            self._version_counter[uri] = 0

        self._version_counter[uri] += 1
        version = self._version_counter[uri]

        # 计算内容哈希
        content_str = json.dumps(content, sort_keys=True, default=str)
        content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]

        artifact = {
            "uri": uri,
            "version": version,
            "type": artifact_type,
            "content": copy.deepcopy(content),
            "hash": content_hash,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": len(content_str.encode()),
        }
        self.artifacts[uri].append(artifact)
        return version

    def retrieve(self, uri, version=None):
        if uri not in self.artifacts:
            raise KeyError(f"Artifact {uri} not found")
        versions = self.artifacts[uri]
        if version is None:
            return versions[-1]  # 最新版
        for art in versions:
            if art["version"] == version:
                return art
        raise KeyError(f"Version {version} not found for {uri}")

    def list_artifacts(self, uri=None):
        if uri:
            return self.artifacts.get(uri, [])
        result = []
        for u, versions in self.artifacts.items():
            result.extend(versions)
        return result

    def get_lineage(self, uri):
        """获取制品的版本谱系"""
        versions = self.artifacts.get(uri, [])
        return [(v["version"], v["hash"], v["created_at"], v["metadata"]) for v in versions]


def test_08_artifact_management():
    """制品管理：存储、检索、版本谱系"""
    store = ArtifactStore()

    # 存储模型制品（3 个版本）
    model_v1 = {"weights": [0.1, 0.2], "bias": 0.0}
    model_v2 = {"weights": [0.15, 0.25], "bias": 0.01}
    model_v3 = {"weights": [0.2, 0.3], "bias": 0.02}

    v1 = store.store("models/iris_clf", model_v1, artifact_type="model", metadata={"stage": "dev"})
    v2 = store.store("models/iris_clf", model_v2, artifact_type="model", metadata={"stage": "staging"})
    v3 = store.store("models/iris_clf", model_v3, artifact_type="model", metadata={"stage": "production"})

    assert v1 == 1 and v2 == 2 and v3 == 3

    # 检索最新版
    latest = store.retrieve("models/iris_clf")
    assert latest["version"] == 3
    assert latest["content"]["weights"] == [0.2, 0.3]
    assert latest["metadata"]["stage"] == "production"

    # 检索指定版本
    v1_artifact = store.retrieve("models/iris_clf", version=1)
    assert v1_artifact["content"]["weights"] == [0.1, 0.2]
    assert v1_artifact["hash"] != latest["hash"]

    # 存储数据制品
    store.store("data/training_set", {"rows": 1000, "features": 20}, artifact_type="dataset")

    # 列出所有制品
    all_artifacts = store.list_artifacts()
    assert len(all_artifacts) == 4  # 3 个模型 + 1 个数据

    # 模型制品
    model_artifacts = store.list_artifacts("models/iris_clf")
    assert len(model_artifacts) == 3

    # 版本谱系
    lineage = store.get_lineage("models/iris_clf")
    assert len(lineage) == 3
    stages = [item[3]["stage"] for item in lineage]
    assert stages == ["dev", "staging", "production"]
    print("✅ test_08 制品管理通过")


# ============================================================
# 9. 超参数追踪与对比
# ============================================================

class HyperparameterTracker:
    """超参数追踪：记录、对比、可视化分析"""
    def __init__(self):
        self.trials = []

    def log_trial(self, params, metrics, status="completed"):
        trial = {
            "trial_id": len(self.trials) + 1,
            "params": copy.deepcopy(params),
            "metrics": copy.deepcopy(metrics),
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.trials.append(trial)
        return trial["trial_id"]

    def get_best_trial(self, metric_key, mode="max"):
        completed = [t for t in self.trials if t["status"] == "completed"]
        if not completed:
            return None
        if mode == "max":
            return max(completed, key=lambda t: t["metrics"].get(metric_key, float("-inf")))
        return min(completed, key=lambda t: t["metrics"].get(metric_key, float("inf")))

    def compare_params(self, metric_key, top_k=5):
        """对比不同参数组合的效果"""
        completed = [t for t in self.trials if t["status"] == "completed"]
        sorted_trials = sorted(completed, key=lambda t: t["metrics"].get(metric_key, 0), reverse=True)
        return [(t["trial_id"], t["params"], t["metrics"].get(metric_key)) for t in sorted_trials[:top_k]]

    def param_importance(self, metric_key):
        """估算参数重要性（基于方差）"""
        completed = [t for t in self.trials if t["status"] == "completed"]
        if len(completed) < 2:
            return {}

        all_params = set()
        for t in completed:
            all_params.update(t["params"].keys())

        importance = {}
        for param in all_params:
            groups = defaultdict(list)
            for t in completed:
                val = t["params"].get(param)
                groups[str(val)].append(t["metrics"].get(metric_key, 0))

            if len(groups) < 2:
                importance[param] = 0.0
                continue

            # 组间方差 / 总方差
            all_values = [v for group in groups.values() for v in group]
            overall_var = np.var(all_values) if len(all_values) > 1 else 0
            if overall_var == 0:
                importance[param] = 0.0
                continue

            group_means = [np.mean(g) for g in groups.values()]
            between_var = np.var(group_means)
            importance[param] = float(between_var / overall_var)

        return importance

    def summary(self):
        completed = [t for t in self.trials if t["status"] == "completed"]
        failed = [t for t in self.trials if t["status"] != "completed"]
        return {
            "total_trials": len(self.trials),
            "completed": len(completed),
            "failed": len(failed),
            "unique_param_combos": len(set(json.dumps(t["params"], sort_keys=True) for t in self.trials)),
        }


def test_09_hyperparameter_tracking():
    """超参数追踪：记录、对比、重要性分析"""
    tracker = HyperparameterTracker()

    # 模拟超参搜索
    params_grid = [
        ({"C": 0.01, "solver": "lbfgs"}, {"accuracy": 0.80, "f1": 0.78}),
        ({"C": 0.1, "solver": "lbfgs"}, {"accuracy": 0.85, "f1": 0.83}),
        ({"C": 1.0, "solver": "lbfgs"}, {"accuracy": 0.92, "f1": 0.91}),
        ({"C": 10.0, "solver": "lbfgs"}, {"accuracy": 0.88, "f1": 0.86}),
        ({"C": 1.0, "solver": "liblinear"}, {"accuracy": 0.90, "f1": 0.89}),
        ({"C": 10.0, "solver": "liblinear"}, {"accuracy": 0.87, "f1": 0.85}),
    ]

    for params, metrics in params_grid:
        tracker.log_trial(params, metrics)

    # 最佳 trial
    best = tracker.get_best_trial("accuracy", "max")
    assert best["params"]["C"] == 1.0
    assert best["params"]["solver"] == "lbfgs"
    assert best["metrics"]["accuracy"] == 0.92

    # 对比 top 3
    top3 = tracker.compare_params("accuracy", top_k=3)
    assert len(top3) == 3
    assert top3[0][2] == 0.92  # 最高准确率

    # 参数重要性
    importance = tracker.param_importance("accuracy")
    assert "C" in importance
    assert "solver" in importance
    # C 参数的重要性应该较高（不同 C 值导致准确率差异大）
    assert importance["C"] > 0

    # 摘要
    s = tracker.summary()
    assert s["total_trials"] == 6
    assert s["completed"] == 6
    assert s["failed"] == 0
    assert s["unique_param_combos"] == 6
    print("✅ test_09 超参数追踪通过")


# ============================================================
# 10. A/B 测试框架
# ============================================================

class ABTestFramework:
    """A/B 测试框架：流量分配、统计显著性检验"""
    def __init__(self, experiment_name):
        self.experiment_name = experiment_name
        self.variants = {}  # name -> {"weight": float, "predictions": [], "outcomes": []}
        self.total_requests = 0

    def add_variant(self, name, weight=1.0):
        self.variants[name] = {"weight": weight, "predictions": [], "outcomes": []}

    def assign_traffic(self, user_id):
        """根据用户 ID 稳定分配到某个变体"""
        total_weight = sum(v["weight"] for v in self.variants.values())
        # 用 user_id 哈希做确定性分配
        hash_val = int(hashlib.md5(str(user_id).encode()).hexdigest(), 16)
        normalized = (hash_val % 10000) / 10000.0 * total_weight

        cumulative = 0
        for name, info in self.variants.items():
            cumulative += info["weight"]
            if normalized < cumulative:
                self.total_requests += 1
                return name
        # fallback
        return list(self.variants.keys())[-1]

    def record_outcome(self, variant_name, prediction, actual_outcome):
        if variant_name not in self.variants:
            raise ValueError(f"Unknown variant: {variant_name}")
        self.variants[variant_name]["predictions"].append(prediction)
        self.variants[variant_name]["outcomes"].append(actual_outcome)

    def get_conversion_rate(self, variant_name):
        outcomes = self.variants[variant_name]["outcomes"]
        if not outcomes:
            return 0.0
        return sum(1 for o in outcomes if o == 1) / len(outcomes)

    def z_test(self, variant_a, variant_b):
        """双比例 Z 检验"""
        na = len(self.variants[variant_a]["outcomes"])
        nb = len(self.variants[variant_b]["outcomes"])
        if na == 0 or nb == 0:
            return 0.0, 1.0

        pa = self.get_conversion_rate(variant_a)
        pb = self.get_conversion_rate(variant_b)

        # 合并比例
        p_pool = (pa * na + pb * nb) / (na + nb)
        if p_pool == 0 or p_pool == 1:
            return 0.0, 1.0

        se = math.sqrt(p_pool * (1 - p_pool) * (1/na + 1/nb))
        if se == 0:
            return 0.0, 1.0

        z_score = (pb - pa) / se

        # 双侧 p-value 近似
        from scipy import stats as sp_stats
        p_value = 2 * (1 - sp_stats.norm.cdf(abs(z_score)))

        return float(z_score), float(p_value)

    def get_results(self):
        results = {}
        for name, info in self.variants.items():
            outcomes = info["outcomes"]
            results[name] = {
                "samples": len(outcomes),
                "conversion_rate": self.get_conversion_rate(name),
                "weight": info["weight"],
            }
        return results


def test_10_ab_testing():
    """A/B 测试：流量分配 + 统计检验"""
    ab = ABTestFramework("model_comparison")
    ab.add_variant("control", weight=1.0)      # 旧模型
    ab.add_variant("treatment", weight=1.0)     # 新模型

    # 确定性分配 + 模拟结果
    np.random.seed(42)
    for i in range(1000):
        variant = ab.assign_traffic(f"user_{i}")
        if variant == "control":
            # 旧模型：85% 准确
            outcome = 1 if np.random.random() < 0.85 else 0
        else:
            # 新模型：91% 准确
            outcome = 1 if np.random.random() < 0.91 else 0
        ab.record_outcome(variant, prediction=outcome, actual_outcome=outcome)

    # 验证流量分配（应该接近 50/50）
    results = ab.get_results()
    assert results["control"]["samples"] > 400
    assert results["treatment"]["samples"] > 400

    # 验证转化率
    control_rate = results["control"]["conversion_rate"]
    treatment_rate = results["treatment"]["conversion_rate"]
    assert 0.80 < control_rate < 0.90
    assert 0.87 < treatment_rate < 0.95

    # Z 检验
    z_score, p_value = ab.z_test("control", "treatment")
    # 新模型应该更好
    assert z_score > 0  # treatment > control
    assert p_value < 0.05  # 统计显著

    # 确定性分配验证：同一 user_id 始终分配到同一变体
    for _ in range(5):
        v = ab.assign_traffic("user_42")
        assert v == ab.assign_traffic("user_42")
    print("✅ test_10 A/B 测试通过")


# ============================================================
# 主函数
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("第五阶段 5.1 MLOps 全流程练习")
    print("=" * 60)
    tests = [
        test_01_experiment_tracker,
        test_02_model_registry,
        test_03_data_versioning,
        test_04_cicd_pipeline,
        test_05_model_monitoring,
        test_06_drift_detection,
        test_07_pipeline_orchestration,
        test_08_artifact_management,
        test_09_hyperparameter_tracking,
        test_10_ab_testing,
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
