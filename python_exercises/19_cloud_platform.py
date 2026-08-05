"""
第五阶段 5.3 云平台练习（10题）
云存储抽象 / Serverless / 自动伸缩 / 成本优化 / IAM安全 / 多云策略 / 云原生 / IaC / 模型部署流水线 / 监控告警
依赖: numpy, yaml
"""
import json, time, math, hashlib, copy, threading
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
import numpy as np
import yaml

# ============================================================
# 1. 云存储抽象（S3-like）
# ============================================================

class CloudStorage:
    """模拟 S3/OSS 云存储：bucket、对象上传下载、版本控制、生命周期"""
    def __init__(self):
        self.buckets = {}  # bucket_name -> {key -> list of versions}

    def create_bucket(self, name, region="us-east-1"):
        if name in self.buckets:
            raise ValueError(f"Bucket {name} already exists")
        self.buckets[name] = {"_meta": {"region": region, "created": datetime.now(timezone.utc).isoformat()}, "_objects": {}}
        return True

    def put_object(self, bucket, key, content, metadata=None):
        if bucket not in self.buckets:
            raise KeyError(f"Bucket {bucket} not found")
        objs = self.buckets[bucket]["_objects"]
        if key not in objs:
            objs[key] = []
        version_id = len(objs[key]) + 1
        content_str = json.dumps(content, sort_keys=True, default=str) if not isinstance(content, str) else content
        etag = hashlib.md5(content_str.encode()).hexdigest()
        objs[key].append({
            "version_id": version_id,
            "content": copy.deepcopy(content),
            "metadata": metadata or {},
            "etag": etag,
            "size": len(content_str.encode()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return {"version_id": version_id, "etag": etag}

    def get_object(self, bucket, key, version_id=None):
        if bucket not in self.buckets:
            raise KeyError(f"Bucket {bucket} not found")
        objs = self.buckets[bucket]["_objects"]
        if key not in objs:
            raise KeyError(f"Object {key} not found")
        versions = objs[key]
        if version_id is None:
            return versions[-1]
        for v in versions:
            if v["version_id"] == version_id:
                return v
        raise KeyError(f"Version {version_id} not found")

    def list_objects(self, bucket, prefix=""):
        if bucket not in self.buckets:
            raise KeyError(f"Bucket {bucket} not found")
        objs = self.buckets[bucket]["_objects"]
        result = []
        for key, versions in objs.items():
            if key.startswith(prefix):
                latest = versions[-1]
                result.append({
                    "key": key,
                    "size": latest["size"],
                    "etag": latest["etag"],
                    "version_id": latest["version_id"],
                    "last_modified": latest["timestamp"],
                })
        return sorted(result, key=lambda x: x["key"])

    def delete_object(self, bucket, key):
        if bucket not in self.buckets:
            raise KeyError(f"Bucket {bucket} not found")
        objs = self.buckets[bucket]["_objects"]
        if key in objs:
            del objs[key]
            return True
        return False

    def get_bucket_size(self, bucket):
        if bucket not in self.buckets:
            return 0
        total = 0
        for versions in self.buckets[bucket]["_objects"].values():
            total += sum(v["size"] for v in versions)
        return total


def test_01_cloud_storage():
    """云存储抽象"""
    storage = CloudStorage()

    # 创建 bucket
    storage.create_bucket("ml-models", region="us-east-1")
    storage.create_bucket("training-data", region="ap-southeast-1")

    # 上传对象（多版本）
    storage.put_object("ml-models", "iris/model.pkl", {"weights": [0.1, 0.2]}, metadata={"framework": "sklearn"})
    storage.put_object("ml-models", "iris/model.pkl", {"weights": [0.15, 0.25]}, metadata={"framework": "sklearn", "version": "2.0"})
    storage.put_object("ml-models", "iris/config.json", {"batch_size": 32, "lr": 0.001})
    storage.put_object("ml-models", "breast_cancer/model.pkl", {"weights": [0.5, 0.3]})

    # 获取最新版本
    latest = storage.get_object("ml-models", "iris/model.pkl")
    assert latest["content"]["weights"] == [0.15, 0.25]
    assert latest["version_id"] == 2

    # 获取指定版本
    v1 = storage.get_object("ml-models", "iris/model.pkl", version_id=1)
    assert v1["content"]["weights"] == [0.1, 0.2]

    # 列出对象
    all_objs = storage.list_objects("ml-models")
    assert len(all_objs) == 3  # iris/model.pkl, iris/config.json, breast_cancer/model.pkl

    iris_objs = storage.list_objects("ml-models", prefix="iris/")
    assert len(iris_objs) == 2

    # 验证 ETag
    assert latest["etag"] != v1["etag"]

    # 删除对象
    assert storage.delete_object("ml-models", "iris/config.json") is True
    assert len(storage.list_objects("ml-models", prefix="iris/")) == 1

    # Bucket 大小
    size = storage.get_bucket_size("ml-models")
    assert size > 0
    print("✅ test_01 云存储通过")


# ============================================================
# 2. Serverless 函数（Lambda 模拟）
# ============================================================

class ServerlessFunction:
    """模拟 AWS Lambda / 阿里云函数计算"""
    def __init__(self, name, handler, runtime="python3.12", memory_mb=256, timeout_sec=30):
        self.name = name
        self.handler = handler
        self.runtime = runtime
        self.memory_mb = memory_mb
        self.timeout_sec = timeout_sec
        self.invocations = 0
        self.errors = 0
        self.total_duration = 0.0
        self.cold_starts = 0
        self._warm = False
        self.last_invocation = None

    def invoke(self, event):
        """调用函数"""
        self.invocations += 1

        # 冷启动检测
        cold_start = not self._warm
        if cold_start:
            self.cold_starts += 1
            time.sleep(0.001)  # 模拟冷启动开销

        start = time.time()
        try:
            result = self.handler(event)
            duration = time.time() - start
            self.total_duration += duration
            self._warm = True
            self.last_invocation = {
                "status": "success",
                "duration_ms": duration * 1000,
                "cold_start": cold_start,
                "memory_mb": self.memory_mb,
            }
            return result
        except Exception as e:
            duration = time.time() - start
            self.total_duration += duration
            self.errors += 1
            self.last_invocation = {
                "status": "error",
                "error": str(e),
                "duration_ms": duration * 1000,
                "cold_start": cold_start,
            }
            raise

    def get_metrics(self):
        return {
            "name": self.name,
            "invocations": self.invocations,
            "errors": self.errors,
            "cold_starts": self.cold_starts,
            "avg_duration_ms": (self.total_duration / self.invocations * 1000) if self.invocations > 0 else 0,
            "error_rate": self.errors / self.invocations if self.invocations > 0 else 0,
            "memory_mb": self.memory_mb,
        }


class ServerlessPlatform:
    """Serverless 平台：函数注册、事件触发、API Gateway"""
    def __init__(self):
        self.functions = {}
        self.api_routes = {}  # path -> (method, function_name)

    def register_function(self, func):
        self.functions[func.name] = func

    def add_api_route(self, path, method, function_name):
        self.api_routes[path] = (method, function_name)

    def invoke_function(self, name, event):
        if name not in self.functions:
            raise KeyError(f"Function {name} not found")
        return self.functions[name].invoke(event)

    def handle_api_request(self, method, path, body=None):
        if path not in self.api_routes:
            return {"statusCode": 404, "body": "Not Found"}
        req_method, func_name = self.api_routes[path]
        if req_method != method:
            return {"statusCode": 405, "body": "Method Not Allowed"}
        event = {"httpMethod": method, "path": path, "body": body or {}}
        try:
            result = self.invoke_function(func_name, event)
            return {"statusCode": 200, "body": result}
        except Exception as e:
            return {"statusCode": 500, "body": {"error": str(e)}}


def test_02_serverless():
    """Serverless 函数"""
    platform = ServerlessPlatform()

    # 定义推理函数
    def inference_handler(event):
        body = event.get("body", {})
        features = body.get("features", [0, 0, 0, 0])
        # 模拟推理
        prediction = 1 if sum(features) > 2 else 0
        return {"prediction": prediction, "confidence": 0.85}

    # 定义预处理函数
    def preprocess_handler(event):
        body = event.get("body", {})
        raw = body.get("raw_text", "")
        tokens = raw.split()
        return {"tokens": tokens, "count": len(tokens)}

    func1 = ServerlessFunction("inference", inference_handler, memory_mb=512, timeout_sec=10)
    func2 = ServerlessFunction("preprocess", preprocess_handler, memory_mb=256, timeout_sec=5)

    platform.register_function(func1)
    platform.register_function(func2)

    # API Gateway 路由
    platform.add_api_route("/predict", "POST", "inference")
    platform.add_api_route("/preprocess", "POST", "preprocess")

    # 直接调用
    result = platform.invoke_function("inference", {"body": {"features": [1, 1, 1, 1]}})
    assert result["prediction"] == 1

    result2 = platform.invoke_function("preprocess", {"body": {"raw_text": "hello world foo"}})
    assert result2["count"] == 3

    # API 请求
    api_result = platform.handle_api_request("POST", "/predict", {"features": [0, 0, 0, 0]})
    assert api_result["statusCode"] == 200
    assert api_result["body"]["prediction"] == 0

    # 404
    not_found = platform.handle_api_request("GET", "/unknown", {})
    assert not_found["statusCode"] == 404

    # 405
    method_error = platform.handle_api_request("GET", "/predict", {})
    assert method_error["statusCode"] == 405

    # 冷启动检测
    func3 = ServerlessFunction("cold", lambda e: {"ok": True})
    platform.register_function(func3)
    platform.invoke_function("cold", {})
    platform.invoke_function("cold", {})
    platform.invoke_function("cold", {})
    metrics = func3.get_metrics()
    assert metrics["invocations"] == 3
    assert metrics["cold_starts"] == 1  # 只有第一次是冷启动
    assert metrics["errors"] == 0
    print("✅ test_02 Serverless通过")


# ============================================================
# 3. 自动伸缩（Auto-scaling）
# ============================================================

class AutoScaler:
    """自动伸缩：基于 CPU/内存/请求队列长度"""
    def __init__(self, min_replicas=2, max_replicas=10, target_cpu=70, target_memory=80, scale_up_threshold=3, scale_down_threshold=3):
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.target_cpu = target_cpu
        self.target_memory = target_memory
        self.scale_up_threshold = scale_up_threshold  # 连续 N 次超阈值才扩容
        self.scale_down_threshold = scale_down_threshold
        self.current_replicas = min_replicas
        self.scale_events = []
        self._over_threshold_count = 0
        self._under_threshold_count = 0

    def evaluate(self, cpu_usage, memory_usage, request_queue_length=0):
        """评估是否需要伸缩"""
        action = "none"

        # 需要扩容
        if cpu_usage > self.target_cpu or memory_usage > self.target_memory:
            self._over_threshold_count += 1
            self._under_threshold_count = 0
            if self._over_threshold_count >= self.scale_up_threshold and self.current_replicas < self.max_replicas:
                new_replicas = min(
                    self.current_replicas + max(1, self.current_replicas // 2),
                    self.max_replicas
                )
                self._log_scale("scale_up", self.current_replicas, new_replicas, cpu_usage, memory_usage)
                self.current_replicas = new_replicas
                self._over_threshold_count = 0
                action = "scale_up"

        # 需要缩容
        elif cpu_usage < self.target_cpu * 0.5 and memory_usage < self.target_memory * 0.5:
            self._under_threshold_count += 1
            self._over_threshold_count = 0
            if self._under_threshold_count >= self.scale_down_threshold and self.current_replicas > self.min_replicas:
                new_replicas = max(self.current_replicas - 1, self.min_replicas)
                self._log_scale("scale_down", self.current_replicas, new_replicas, cpu_usage, memory_usage)
                self.current_replicas = new_replicas
                self._under_threshold_count = 0
                action = "scale_down"
        else:
            self._over_threshold_count = 0
            self._under_threshold_count = 0

        return {
            "action": action,
            "current_replicas": self.current_replicas,
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
        }

    def _log_scale(self, action, from_r, to_r, cpu, mem):
        self.scale_events.append({
            "action": action,
            "from": from_r,
            "to": to_r,
            "cpu": cpu,
            "memory": mem,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_scale_history(self):
        return self.scale_events


def test_03_auto_scaling():
    """自动伸缩"""
    scaler = AutoScaler(min_replicas=2, max_replicas=10, target_cpu=70, target_memory=80, scale_up_threshold=2, scale_down_threshold=3)

    # 初始状态
    assert scaler.current_replicas == 2

    # 高负载，但未达到连续阈值
    r = scaler.evaluate(85, 60)
    assert r["action"] == "none"
    assert scaler.current_replicas == 2

    # 第二次高负载 → 扩容
    r = scaler.evaluate(88, 65)
    assert r["action"] == "scale_up"
    assert scaler.current_replicas == 3  # 2 + max(1, 2//2) = 3

    # 持续高负载 → 继续扩容
    scaler.evaluate(90, 70)
    r = scaler.evaluate(92, 75)
    assert r["action"] == "scale_up"
    assert scaler.current_replicas >= 4

    # 负载降低，未达连续阈值
    scaler.evaluate(20, 30)
    scaler.evaluate(20, 30)
    r = scaler.evaluate(20, 30)
    assert r["action"] == "scale_down"

    # 不超过最大副本数
    scaler2 = AutoScaler(min_replicas=1, max_replicas=5, target_cpu=50, scale_up_threshold=1, scale_down_threshold=1)
    for _ in range(20):
        scaler2.evaluate(90, 90)
    assert scaler2.current_replicas == 5  # 不超过 max

    # 不低于最小副本数
    scaler3 = AutoScaler(min_replicas=2, max_replicas=5, target_cpu=70, scale_up_threshold=1, scale_down_threshold=1)
    for _ in range(20):
        scaler3.evaluate(10, 10)
    assert scaler3.current_replicas == 2  # 不低于 min

    # 验证伸缩历史
    assert len(scaler.get_scale_history()) >= 2
    print("✅ test_03 自动伸缩通过")


# ============================================================
# 4. 成本优化
# ============================================================

class CloudCostOptimizer:
    """云成本优化：实例选型、预留实例/按需/Spot 混合策略"""
    INSTANCE_TYPES = {
        "t3.micro": {"cpu": 2, "memory_gb": 1, "price_per_hour": 0.0208},
        "t3.small": {"cpu": 2, "memory_gb": 2, "price_per_hour": 0.0416},
        "t3.medium": {"cpu": 2, "memory_gb": 4, "price_per_hour": 0.0832},
        "m5.large": {"cpu": 2, "memory_gb": 8, "price_per_hour": 0.096},
        "m5.xlarge": {"cpu": 4, "memory_gb": 16, "price_per_hour": 0.192},
        "m5.2xlarge": {"cpu": 8, "memory_gb": 32, "price_per_hour": 0.384},
        "g4dn.xlarge": {"cpu": 4, "memory_gb": 16, "gpu": 1, "price_per_hour": 0.526},
        "g4dn.2xlarge": {"cpu": 8, "memory_gb": 32, "gpu": 1, "price_per_hour": 0.752},
    }

    def __init__(self):
        self.resources = []

    def add_resource(self, instance_type, count=1, pricing_model="on_demand"):
        if instance_type not in self.INSTANCE_TYPES:
            raise ValueError(f"Unknown instance type: {instance_type}")
        self.resources.append({
            "instance_type": instance_type,
            "count": count,
            "pricing_model": pricing_model,
            "specs": self.INSTANCE_TYPES[instance_type],
        })

    def calculate_monthly_cost(self):
        """计算月度成本"""
        monthly_hours = 730  # 平均每月小时数
        total = 0.0
        breakdown = {}
        for res in self.resources:
            base_price = res["specs"]["price_per_hour"]
            # 定价模型折扣
            if res["pricing_model"] == "reserved":
                price = base_price * 0.6  # 预留实例 40% 折扣
            elif res["pricing_model"] == "spot":
                price = base_price * 0.3  # Spot 实例 70% 折扣
            else:
                price = base_price

            cost = price * monthly_hours * res["count"]
            key = f"{res['instance_type']}({res['pricing_model']})"
            breakdown[key] = breakdown.get(key, 0) + cost
            total += cost

        return {"total_monthly_cost": round(total, 2), "breakdown": breakdown}

    def recommend_instance_type(self, required_cpu, required_memory_gb, require_gpu=False):
        """推荐最具性价比的实例类型"""
        candidates = []
        for it_name, specs in self.INSTANCE_TYPES.items():
            if specs["cpu"] >= required_cpu and specs["memory_gb"] >= required_memory_gb:
                if require_gpu and "gpu" not in specs:
                    continue
                # 性价比 = 资源总量 / 价格
                total_resources = specs["cpu"] + specs["memory_gb"] + specs.get("gpu", 0) * 10
                cost_efficiency = total_resources / specs["price_per_hour"]
                candidates.append((it_name, specs["price_per_hour"], cost_efficiency))

        if not candidates:
            return None

        # 按价格排序（最便宜的满足需求的）
        candidates.sort(key=lambda x: x[1])
        return {"recommended": candidates[0][0], "price_per_hour": candidates[0][1]}

    def optimize_pricing_mix(self, workload_pattern):
        """
        优化定价策略混合
        workload_pattern: {"steady": float, "spiky": float, "batch": float}
        steady: 稳定负载比例（适合预留实例）
        spiky: 突发负载比例（适合按需实例）
        batch: 批处理负载比例（适合 Spot 实例）
        """
        total = workload_pattern["steady"] + workload_pattern["spiky"] + workload_pattern["batch"]
        if total == 0:
            return {}

        return {
            "reserved_ratio": workload_pattern["steady"] / total,
            "on_demand_ratio": workload_pattern["spiky"] / total,
            "spot_ratio": workload_pattern["batch"] / total,
            "estimated_savings_pct": round((1 - (workload_pattern["steady"] * 0.6 + workload_pattern["spiky"] * 1.0 + workload_pattern["batch"] * 0.3) / total) * 100, 1),
        }


def test_04_cost_optimization():
    """云成本优化"""
    optimizer = CloudCostOptimizer()

    # 添加资源
    optimizer.add_resource("m5.large", count=3, pricing_model="on_demand")
    optimizer.add_resource("m5.xlarge", count=2, pricing_model="reserved")
    optimizer.add_resource("g4dn.xlarge", count=1, pricing_model="spot")

    # 月度成本
    cost = optimizer.calculate_monthly_cost()
    assert cost["total_monthly_cost"] > 0
    assert len(cost["breakdown"]) == 3

    # 验证预留实例比按需便宜
    optimizer2 = CloudCostOptimizer()
    optimizer2.add_resource("m5.large", count=1, pricing_model="on_demand")
    optimizer2.add_resource("m5.large", count=1, pricing_model="reserved")
    optimizer2.add_resource("m5.large", count=1, pricing_model="spot")
    cost2 = optimizer2.calculate_monthly_cost()
    on_demand_cost = cost2["breakdown"]["m5.large(on_demand)"]
    reserved_cost = cost2["breakdown"]["m5.large(reserved)"]
    spot_cost = cost2["breakdown"]["m5.large(spot)"]
    assert reserved_cost < on_demand_cost  # 预留 < 按需
    assert spot_cost < reserved_cost  # Spot < 预留

    # 实例推荐
    rec = optimizer.recommend_instance_type(required_cpu=4, required_memory_gb=16)
    assert rec is not None
    assert rec["recommended"] in CloudCostOptimizer.INSTANCE_TYPES
    rec_specs = CloudCostOptimizer.INSTANCE_TYPES[rec["recommended"]]
    assert rec_specs["cpu"] >= 4
    assert rec_specs["memory_gb"] >= 16

    # GPU 推荐
    gpu_rec = optimizer.recommend_instance_type(required_cpu=4, required_memory_gb=16, require_gpu=True)
    assert gpu_rec is not None
    assert "g4dn" in gpu_rec["recommended"]

    # 定价混合优化
    mix = optimizer.optimize_pricing_mix({"steady": 50, "spiky": 30, "batch": 20})
    assert mix["reserved_ratio"] > 0
    assert mix["spot_ratio"] > 0
    assert mix["estimated_savings_pct"] > 0
    assert abs(mix["reserved_ratio"] + mix["on_demand_ratio"] + mix["spot_ratio"] - 1.0) < 0.01
    print("✅ test_04 成本优化通过")


# ============================================================
# 5. IAM 安全策略
# ============================================================

class IAMPolicy:
    """IAM 策略管理：角色、权限、资源访问控制"""
    def __init__(self):
        self.roles = {}  # role_name -> {"policies": [policy], "users": [user]}
        self.users = {}  # user_name -> {"roles": [role_name]}

    def create_role(self, name, description=""):
        if name in self.roles:
            raise ValueError(f"Role {name} already exists")
        self.roles[name] = {"description": description, "policies": [], "users": []}

    def create_user(self, name):
        if name in self.users:
            raise ValueError(f"User {name} already exists")
        self.users[name] = {"roles": []}

    def attach_policy(self, role_name, policy):
        """
        policy: {
            "effect": "Allow" | "Deny",
            "actions": list[str],  # e.g. ["s3:GetObject", "s3:PutObject"]
            "resources": list[str],  # e.g. ["arn:aws:s3:::ml-models/*"]
        }
        """
        if role_name not in self.roles:
            raise KeyError(f"Role {role_name} not found")
        self.roles[role_name]["policies"].append(policy)

    def assign_role(self, user_name, role_name):
        if user_name not in self.users:
            raise KeyError(f"User {user_name} not found")
        if role_name not in self.roles:
            raise KeyError(f"Role {role_name} not found")
        if role_name not in self.users[user_name]["roles"]:
            self.users[user_name]["roles"].append(role_name)
            self.roles[role_name]["users"].append(user_name)

    def check_permission(self, user_name, action, resource):
        """检查用户是否有权限执行操作"""
        if user_name not in self.users:
            return False

        user_roles = self.users[user_name]["roles"]
        allowed = False
        denied = False

        for role_name in user_roles:
            for policy in self.roles[role_name]["policies"]:
                if self._match_action(action, policy["actions"]) and self._match_resource(resource, policy["resources"]):
                    if policy["effect"] == "Deny":
                        denied = True
                    elif policy["effect"] == "Allow":
                        allowed = True

        # Deny 优先
        return allowed and not denied

    def _match_action(self, action, patterns):
        for p in patterns:
            if p == "*" or p == action:
                return True
            if p.endswith(":*") and action.startswith(p[:-1]):
                return True
        return False

    def _match_resource(self, resource, patterns):
        for p in patterns:
            if p == "*" or p == resource:
                return True
            if "*" in p:
                # 通配符匹配
                prefix = p.split("*")[0]
                if resource.startswith(prefix):
                    return True
        return False

    def audit_user_permissions(self, user_name):
        """审计用户权限"""
        if user_name not in self.users:
            return {"user": user_name, "roles": [], "policies": []}

        user_roles = self.users[user_name]["roles"]
        all_policies = []
        for role_name in user_roles:
            for policy in self.roles[role_name]["policies"]:
                all_policies.append({"role": role_name, **policy})

        return {"user": user_name, "roles": user_roles, "policies": all_policies}


def test_05_iam_security():
    """IAM 安全策略"""
    iam = IAMPolicy()

    # 创建角色和用户
    iam.create_role("ml-engineer", "ML 工程师角色")
    iam.create_role("data-scientist", "数据科学家角色")
    iam.create_role("admin", "管理员角色")
    iam.create_user("alice")
    iam.create_user("bob")
    iam.create_user("charlie")

    # 附加策略
    iam.attach_policy("ml-engineer", {
        "effect": "Allow",
        "actions": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
        "resources": ["arn:aws:s3:::ml-models/*", "arn:aws:s3:::training-data/*"],
    })
    iam.attach_policy("ml-engineer", {
        "effect": "Deny",
        "actions": ["s3:DeleteObject"],
        "resources": ["arn:aws:s3:::ml-models/*"],
    })
    iam.attach_policy("data-scientist", {
        "effect": "Allow",
        "actions": ["s3:GetObject", "s3:ListBucket"],
        "resources": ["arn:aws:s3:::training-data/*"],
    })
    iam.attach_policy("admin", {
        "effect": "Allow",
        "actions": ["*"],
        "resources": ["*"],
    })

    # 分配角色
    iam.assign_role("alice", "ml-engineer")
    iam.assign_role("bob", "data-scientist")
    iam.assign_role("charlie", "admin")

    # 权限检查
    assert iam.check_permission("alice", "s3:GetObject", "arn:aws:s3:::ml-models/iris.pkl") is True
    assert iam.check_permission("alice", "s3:PutObject", "arn:aws:s3:::ml-models/model.pkl") is True
    assert iam.check_permission("alice", "s3:DeleteObject", "arn:aws:s3:::ml-models/model.pkl") is False  # Deny
    assert iam.check_permission("alice", "s3:GetObject", "arn:aws:s3:::other-bucket/data.csv") is False  # 资源不在范围内

    assert iam.check_permission("bob", "s3:GetObject", "arn:aws:s3:::training-data/data.csv") is True
    assert iam.check_permission("bob", "s3:PutObject", "arn:aws:s3:::training-data/data.csv") is False  # 只有读权限

    assert iam.check_permission("charlie", "s3:DeleteObject", "arn:aws:s3:::any-bucket/any-object") is True  # admin 通配符

    # 审计
    audit = iam.audit_user_permissions("alice")
    assert "ml-engineer" in audit["roles"]
    assert len(audit["policies"]) == 2  # Allow + Deny
    print("✅ test_05 IAM安全通过")


# ============================================================
# 6. 多云策略
# ============================================================

class MultiCloudManager:
    """多云管理：抽象不同云服务商，统一接口"""
    CLOUD_PROVIDERS = {
        "aws": {"storage": "S3", "compute": "EC2", "ml": "SageMaker", "regions": ["us-east-1", "us-west-2", "ap-southeast-1"]},
        "aliyun": {"storage": "OSS", "compute": "ECS", "ml": "PAI", "regions": ["cn-hangzhou", "cn-shanghai", "cn-beijing"]},
        "azure": {"storage": "Blob", "compute": "VM", "ml": "Azure ML", "regions": ["eastus", "westeurope", "southeastasia"]},
    }

    def __init__(self):
        self.deployments = {}  # deployment_id -> config
        self._counter = 0

    def deploy_multi_cloud(self, app_config, target_clouds=None):
        """部署到多个云"""
        target_clouds = target_clouds or list(self.CLOUD_PROVIDERS.keys())
        results = {}
        for cloud in target_clouds:
            if cloud not in self.CLOUD_PROVIDERS:
                results[cloud] = {"status": "error", "reason": "Unknown provider"}
                continue

            provider_info = self.CLOUD_PROVIDERS[cloud]
            self._counter += 1
            deploy_id = f"deploy_{self._counter:04d}"

            deployment = {
                "deploy_id": deploy_id,
                "cloud": cloud,
                "app_name": app_config["name"],
                "storage_service": provider_info["storage"],
                "compute_service": provider_info["compute"],
                "ml_service": provider_info["ml"],
                "region": app_config.get("region", provider_info["regions"][0]),
                "status": "deployed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.deployments[deploy_id] = deployment
            results[cloud] = deployment

        return results

    def get_cheapest_cloud(self, app_config):
        """选择最便宜的云"""
        # 模拟不同云的价格
        pricing = {
            "aws": {"compute_hour": 0.096, "storage_gb_month": 0.023, "ml_hour": 0.50},
            "aliyun": {"compute_hour": 0.080, "storage_gb_month": 0.020, "ml_hour": 0.45},
            "azure": {"compute_hour": 0.090, "storage_gb_month": 0.022, "ml_hour": 0.48},
        }

        hours = app_config.get("compute_hours", 730)
        storage_gb = app_config.get("storage_gb", 100)
        ml_hours = app_config.get("ml_hours", 100)

        costs = {}
        for cloud, prices in pricing.items():
            total = (prices["compute_hour"] * hours + prices["storage_gb_month"] * storage_gb + prices["ml_hour"] * ml_hours)
            costs[cloud] = round(total, 2)

        cheapest = min(costs, key=costs.get)
        return {"cheapest_cloud": cheapest, "costs": costs, "monthly_total": costs[cheapest]}

    def failover(self, primary_cloud, app_config):
        """故障转移"""
        if primary_cloud not in self.CLOUD_PROVIDERS:
            raise ValueError(f"Unknown cloud: {primary_cloud}")

        # 找备选云
        backup_clouds = [c for c in self.CLOUD_PROVIDERS if c != primary_cloud]
        if not backup_clouds:
            raise RuntimeError("No backup cloud available")

        results = {}
        for cloud in backup_clouds:
            self._counter += 1
            deploy_id = f"failover_{self._counter:04d}"
            provider_info = self.CLOUD_PROVIDERS[cloud]
            deployment = {
                "deploy_id": deploy_id,
                "cloud": cloud,
                "app_name": app_config["name"],
                "status": "failover_active",
                "original_cloud": primary_cloud,
                "region": provider_info["regions"][0],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.deployments[deploy_id] = deployment
            results[cloud] = deployment

        return {"failed_over_from": primary_cloud, "backup_deployments": results}

    def get_deployment_summary(self):
        by_cloud = defaultdict(list)
        for dep in self.deployments.values():
            by_cloud[dep["cloud"]].append(dep["deploy_id"])
        return {cloud: {"count": len(ids), "deploy_ids": ids} for cloud, ids in by_cloud.items()}


def test_06_multi_cloud():
    """多云策略"""
    mgr = MultiCloudManager()

    app_config = {"name": "ml-inference", "region": "us-east-1", "compute_hours": 730, "storage_gb": 500, "ml_hours": 200}

    # 多云部署
    results = mgr.deploy_multi_cloud(app_config, target_clouds=["aws", "aliyun", "azure"])
    assert results["aws"]["status"] == "deployed"
    assert results["aws"]["storage_service"] == "S3"
    assert results["aliyun"]["storage_service"] == "OSS"
    assert results["azure"]["ml_service"] == "Azure ML"

    # 最便宜云选择
    cheapest = mgr.get_cheapest_cloud(app_config)
    assert cheapest["cheapest_cloud"] in ["aws", "aliyun", "azure"]
    assert all(c in cheapest["costs"] for c in ["aws", "aliyun", "azure"])
    assert cheapest["monthly_total"] == cheapest["costs"][cheapest["cheapest_cloud"]]

    # 阿里云应该最便宜（价格最低）
    assert cheapest["cheapest_cloud"] == "aliyun"

    # 故障转移
    failover_result = mgr.failover("aws", app_config)
    assert failover_result["failed_over_from"] == "aws"
    assert "aliyun" in failover_result["backup_deployments"]
    assert "azure" in failover_result["backup_deployments"]

    # 部署摘要
    summary = mgr.get_deployment_summary()
    assert "aws" in summary
    assert "aliyun" in summary
    assert "azure" in summary
    print("✅ test_06 多云策略通过")


# ============================================================
# 7. 云原生模式（微服务设计）
# ============================================================

class MicroservicePattern:
    """云原生微服务模式：服务注册发现、断路器、重试、限流"""

    @staticmethod
    def service_registry():
        """服务注册与发现"""
        registry = {}

        def register(service_name, instance_id, host, port, metadata=None):
            if service_name not in registry:
                registry[service_name] = []
            registry[service_name].append({
                "instance_id": instance_id,
                "host": host,
                "port": port,
                "metadata": metadata or {},
                "healthy": True,
                "registered_at": datetime.now(timezone.utc).isoformat(),
            })

        def discover(service_name):
            return [i for i in registry.get(service_name, []) if i["healthy"]]

        def deregister(service_name, instance_id):
            if service_name in registry:
                registry[service_name] = [i for i in registry[service_name] if i["instance_id"] != instance_id]

        def set_health(service_name, instance_id, healthy):
            for i in registry.get(service_name, []):
                if i["instance_id"] == instance_id:
                    i["healthy"] = healthy

        return {"register": register, "discover": discover, "deregister": deregister, "set_health": set_health, "_registry": registry}

    @staticmethod
    def circuit_breaker(failure_threshold=5, recovery_timeout=30):
        """断路器模式"""
        state = {"status": "closed", "failure_count": 0, "last_failure_time": None}

        def record_success():
            state["failure_count"] = 0
            state["status"] = "closed"

        def record_failure():
            state["failure_count"] += 1
            state["last_failure_time"] = time.time()
            if state["failure_count"] >= failure_threshold:
                state["status"] = "open"

        def can_request():
            if state["status"] == "closed":
                return True
            if state["status"] == "open":
                # 检查是否应该尝试半开
                if state["last_failure_time"] and (time.time() - state["last_failure_time"]) >= recovery_timeout:
                    state["status"] = "half_open"
                    return True
                return False
            if state["status"] == "half_open":
                return True
            return False

        return {"record_success": record_success, "record_failure": record_failure, "can_request": can_request, "state": state}

    @staticmethod
    def rate_limiter(max_requests=100, window_seconds=60):
        """滑动窗口限流"""
        requests = deque()

        def allow():
            now = time.time()
            # 清理过期请求
            while requests and requests[0] < now - window_seconds:
                requests.popleft()
            if len(requests) < max_requests:
                requests.append(now)
                return True
            return False

        def get_stats():
            return {"current_count": len(requests), "max_requests": max_requests, "window_seconds": window_seconds}

        return {"allow": allow, "get_stats": get_stats}

    @staticmethod
    def retry_with_backoff(max_retries=3, base_delay=0.1):
        """指数退避重试"""
        def execute(func, *args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
            raise last_error

        return execute


def test_07_cloud_native():
    """云原生微服务模式"""
    # 服务注册发现
    reg = MicroservicePattern.service_registry()
    reg["register"]("user-service", "inst-1", "10.0.0.1", 8000)
    reg["register"]("user-service", "inst-2", "10.0.0.2", 8000)
    reg["register"]("user-service", "inst-3", "10.0.0.3", 8000)

    instances = reg["discover"]("user-service")
    assert len(instances) == 3

    # 设置一个实例不健康
    reg["set_health"]("user-service", "inst-2", False)
    healthy = reg["discover"]("user-service")
    assert len(healthy) == 2
    assert all(i["instance_id"] != "inst-2" for i in healthy)

    # 注销
    reg["deregister"]("user-service", "inst-1")
    assert len(reg["discover"]("user-service")) == 1

    # 断路器
    cb = MicroservicePattern.circuit_breaker(failure_threshold=3, recovery_timeout=0.1)
    assert cb["can_request"]() is True  # closed

    cb["record_failure"]()
    cb["record_failure"]()
    assert cb["can_request"]() is True  # still closed (2 < 3)

    cb["record_failure"]()
    assert cb["state"]["status"] == "open"
    assert cb["can_request"]() is False  # open → blocked

    # 等待恢复
    time.sleep(0.15)
    assert cb["can_request"]() is True  # half_open
    cb["record_success"]
    # half_open 状态下可以请求
    assert cb["can_request"]() is True

    # 限流器
    rl = MicroservicePattern.rate_limiter(max_requests=5, window_seconds=1)
    allowed = [rl["allow"]() for _ in range(7)]
    assert sum(allowed) == 5  # 只有 5 个被允许
    assert allowed[5] is False

    # 重试
    call_count = [0]
    def flaky():
        call_count[0] += 1
        if call_count[0] < 3:
            raise ConnectionError("temp error")
        return "success"

    retry = MicroservicePattern.retry_with_backoff(max_retries=3, base_delay=0.01)
    result = retry(flaky)
    assert result == "success"
    assert call_count[0] == 3
    print("✅ test_07 云原生模式通过")


# ============================================================
# 8. 基础设施即代码（IaC）
# ============================================================

class InfrastructureAsCode:
    """基础设施即代码：生成 Terraform-like 配置"""
    def __init__(self):
        self.resources = []
        self.variables = {}
        self.outputs = {}

    def add_variable(self, name, default=None, description=""):
        self.variables[name] = {"default": default, "description": description}

    def add_resource(self, resource_type, name, config):
        self.resources.append({
            "type": resource_type,
            "name": name,
            "config": config,
        })

    def add_output(self, name, value, description=""):
        self.outputs[name] = {"value": value, "description": description}

    def generate_terraform(self):
        """生成 Terraform HCL 格式配置"""
        lines = []

        # Variables
        if self.variables:
            lines.append("# Variables")
            for name, info in self.variables.items():
                lines.append(f'variable "{name}" {{')
                if info["description"]:
                    lines.append(f'  description = "{info["description"]}"')
                if info["default"] is not None:
                    default_val = json.dumps(info["default"]) if isinstance(info["default"], (dict, list)) else f'"{info["default"]}"'
                    lines.append(f'  default = {default_val}')
                lines.append("}")
                lines.append("")

        # Resources
        for res in self.resources:
            lines.append(f'resource "{res["type"]}" "{res["name"]}" {{')
            for key, value in res["config"].items():
                if isinstance(value, str):
                    lines.append(f'  {key} = "{value}"')
                elif isinstance(value, (int, float)):
                    lines.append(f'  {key} = {value}')
                elif isinstance(value, bool):
                    lines.append(f'  {key} = {str(value).lower()}')
                elif isinstance(value, list):
                    lines.append(f'  {key} = {json.dumps(value)}')
                elif isinstance(value, dict):
                    lines.append(f'  {key} = {{')
                    for k, v in value.items():
                        lines.append(f'    {k} = "{v}"')
                    lines.append('  }')
            lines.append("}")
            lines.append("")

        # Outputs
        if self.outputs:
            lines.append("# Outputs")
            for name, info in self.outputs.items():
                lines.append(f'output "{name}" {{')
                if info["description"]:
                    lines.append(f'  description = "{info["description"]}"')
                lines.append(f'  value = {info["value"]}')
                lines.append("}")
                lines.append("")

        return "\n".join(lines)

    def generate_yaml_manifest(self):
        """生成 YAML 格式清单"""
        return yaml.dump({
            "variables": self.variables,
            "resources": self.resources,
            "outputs": self.outputs,
        }, default_flow_style=False, sort_keys=True)

    def validate(self):
        """验证配置完整性"""
        issues = []
        resource_names = [r["name"] for r in self.resources]
        if len(resource_names) != len(set(resource_names)):
            issues.append("Duplicate resource names found")

        for res in self.resources:
            if not res.get("config"):
                issues.append(f"Resource {res['name']} has empty config")

        return {"valid": len(issues) == 0, "issues": issues, "resource_count": len(self.resources)}


def test_08_iac():
    """基础设施即代码"""
    iac = InfrastructureAsCode()

    # 变量
    iac.add_variable("region", default="us-east-1", description="AWS region")
    iac.add_variable("instance_count", default=3, description="Number of instances")

    # 资源
    iac.add_resource("aws_s3_bucket", "model_storage", {
        "bucket": "ml-models-prod",
        "acl": "private",
        "versioning": True,
    })
    iac.add_resource("aws_ec2_instance", "ml_server", {
        "instance_type": "m5.xlarge",
        "count": 3,
        "tags": {"Name": "ml-server", "Env": "prod"},
    })
    iac.add_resource("aws_iam_role", "ml_role", {
        "name": "ml-service-role",
        "assume_role_policy": "ec2",
    })

    # 输出
    iac.add_output("bucket_name", "ml-models-prod", description="S3 bucket name")
    iac.add_output("instance_ids", "aws_ec2_instance.ml_server.id", description="EC2 instance IDs")

    # 生成 Terraform
    tf = iac.generate_terraform()
    assert 'resource "aws_s3_bucket" "model_storage"' in tf
    assert 'resource "aws_ec2_instance" "ml_server"' in tf
    assert 'variable "region"' in tf
    assert 'output "bucket_name"' in tf
    assert "us-east-1" in tf

    # 生成 YAML
    yml = iac.generate_yaml_manifest()
    assert "aws_s3_bucket" in yml
    assert "model_storage" in yml

    # 验证
    validation = iac.validate()
    assert validation["valid"] is True
    assert validation["resource_count"] == 3
    assert len(validation["issues"]) == 0

    # 重复名称检测
    iac.add_resource("aws_s3_bucket", "model_storage", {"bucket": "duplicate"})
    validation2 = iac.validate()
    assert validation2["valid"] is False
    assert "Duplicate resource names found" in validation2["issues"]
    print("✅ test_08 IaC通过")


# ============================================================
# 9. 端到端模型部署流水线
# ============================================================

class ModelDeploymentPipeline:
    """端到端模型部署流水线：训练→评估→打包→部署→监控"""
    def __init__(self):
        self.stages = [
            "data_preparation",
            "model_training",
            "model_evaluation",
            "model_packaging",
            "deployment",
            "post_deployment_monitoring",
        ]
        self.stage_status = {s: "pending" for s in self.stages}
        self.stage_results = {}
        self.current_stage = 0
        self.rollback_on_failure = True
        self.deployment_history = []

    def run_pipeline(self, model_config):
        """运行完整部署流水线"""
        results = {}

        for i, stage in enumerate(self.stages):
            self.current_stage = i
            self.stage_status[stage] = "running"

            try:
                result = self._execute_stage(stage, model_config, results)
                results[stage] = result
                self.stage_results[stage] = result
                self.stage_status[stage] = "completed"
            except Exception as e:
                self.stage_status[stage] = "failed"
                results[stage] = {"error": str(e)}
                if self.rollback_on_failure:
                    self._rollback()
                return {"status": "failed", "failed_stage": stage, "results": results}

        self.deployment_history.append({
            "model": model_config.get("name", "unnamed"),
            "version": model_config.get("version", "v1"),
            "stages_completed": len(self.stages),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
        })

        return {"status": "success", "results": results}

    def _execute_stage(self, stage, config, prev_results):
        if stage == "data_preparation":
            return {"rows": config.get("data_rows", 1000), "features": config.get("features", 10), "split_ratio": "80/20"}
        elif stage == "model_training":
            return {"algorithm": config.get("algorithm", "LogisticRegression"), "epochs": config.get("epochs", 100), "final_loss": 0.15}
        elif stage == "model_evaluation":
            acc = config.get("accuracy", 0.92)
            if acc < config.get("min_accuracy", 0.8):
                raise ValueError(f"Accuracy {acc} below threshold {config.get('min_accuracy', 0.8)}")
            return {"accuracy": acc, "f1": acc - 0.03, "precision": acc - 0.01, "recall": acc - 0.02}
        elif stage == "model_packaging":
            return {"model_size_mb": 25.5, "format": "onnx", "model_uri": "s3://ml-models/model.onnx"}
        elif stage == "deployment":
            if config.get("deploy", True):
                return {"endpoint": f"https://api.example.com/v1/predict", "replicas": 3, "status": "serving"}
            return {"endpoint": None, "status": "not_deployed"}
        elif stage == "post_deployment_monitoring":
            return {"monitoring_enabled": True, "alerts_configured": True, "drift_detection": True}

    def _rollback(self):
        """回滚已完成的阶段"""
        for stage in self.stages[:self.current_stage]:
            if self.stage_status[stage] == "completed":
                self.stage_status[stage] = "rolled_back"

    def get_pipeline_status(self):
        return {
            "current_stage": self.stages[self.current_stage] if self.current_stage < len(self.stages) else None,
            "stages": self.stage_status,
            "deployment_history": self.deployment_history,
        }


def test_09_deployment_pipeline():
    """端到端模型部署流水线"""
    pipeline = ModelDeploymentPipeline()

    config = {
        "name": "iris_classifier",
        "version": "v2.0",
        "data_rows": 5000,
        "features": 4,
        "algorithm": "LogisticRegression",
        "epochs": 200,
        "accuracy": 0.94,
        "min_accuracy": 0.85,
        "deploy": True,
    }

    result = pipeline.run_pipeline(config)

    # 验证全部成功
    assert result["status"] == "success"
    assert "data_preparation" in result["results"]
    assert "model_evaluation" in result["results"]
    assert "deployment" in result["results"]

    # 验证各阶段结果
    assert result["results"]["data_preparation"]["rows"] == 5000
    assert result["results"]["model_training"]["algorithm"] == "LogisticRegression"
    assert result["results"]["model_evaluation"]["accuracy"] == 0.94
    assert result["results"]["model_packaging"]["format"] == "onnx"
    assert result["results"]["deployment"]["endpoint"] is not None
    assert result["results"]["post_deployment_monitoring"]["drift_detection"] is True

    # 验证状态
    status = pipeline.get_pipeline_status()
    assert all(s == "completed" for s in status["stages"].values())
    assert len(status["deployment_history"]) == 1

    # 测试失败场景（准确率不达标）
    pipeline2 = ModelDeploymentPipeline()
    failed_config = {**config, "accuracy": 0.7, "min_accuracy": 0.85}
    result2 = pipeline2.run_pipeline(failed_config)
    assert result2["status"] == "failed"
    assert result2["failed_stage"] == "model_evaluation"

    # 验证回滚
    status2 = pipeline2.get_pipeline_status()
    assert status2["stages"]["model_evaluation"] == "failed"
    # data_preparation 和 model_training 已完成但被回滚
    assert status2["stages"]["data_preparation"] == "rolled_back"
    print("✅ test_09 部署流水线通过")


# ============================================================
# 10. 监控告警系统
# ============================================================

class MonitoringAlertSystem:
    """云监控告警系统：指标采集、阈值告警、告警路由、值班排班"""
    def __init__(self):
        self.metrics = defaultdict(list)  # metric_name -> list of (timestamp, value)
        self.alerts = {}  # alert_id -> alert info
        self.alert_rules = []  # list of rule configs
        self.oncall_schedule = {}  # date_str -> person
        self.notification_channels = []  # list of channel configs
        self._alert_counter = 0
        self._max_metrics_per_name = 1000

    def record_metric(self, name, value, timestamp=None):
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        self.metrics[name].append((ts, value))
        # 限制历史数据量
        if len(self.metrics[name]) > self._max_metrics_per_name:
            self.metrics[name] = self.metrics[name][-self._max_metrics_per_name:]

        # 检查告警规则
        self._check_alert_rules(name, value)

    def add_alert_rule(self, rule_name, metric_name, condition, threshold, severity="warning"):
        """
        condition: ">", "<", ">=", "<="
        severity: "info", "warning", "critical"
        """
        self.alert_rules.append({
            "rule_name": rule_name,
            "metric_name": metric_name,
            "condition": condition,
            "threshold": threshold,
            "severity": severity,
        })

    def _check_alert_rules(self, metric_name, value):
        for rule in self.alert_rules:
            if rule["metric_name"] != metric_name:
                continue
            triggered = False
            if rule["condition"] == ">" and value > rule["threshold"]:
                triggered = True
            elif rule["condition"] == "<" and value < rule["threshold"]:
                triggered = True
            elif rule["condition"] == ">=" and value >= rule["threshold"]:
                triggered = True
            elif rule["condition"] == "<=" and value <= rule["threshold"]:
                triggered = True

            if triggered:
                self._alert_counter += 1
                alert_id = f"alert_{self._alert_counter:04d}"
                self.alerts[alert_id] = {
                    "alert_id": alert_id,
                    "rule": rule["rule_name"],
                    "metric": metric_name,
                    "value": value,
                    "threshold": rule["threshold"],
                    "condition": rule["condition"],
                    "severity": rule["severity"],
                    "status": "firing",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "assigned_to": self._get_oncall_person(),
                }

    def set_oncall_schedule(self, date_str, person):
        self.oncall_schedule[date_str] = person

    def _get_oncall_person(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.oncall_schedule.get(today, "unassigned")

    def add_notification_channel(self, channel_type, config):
        self.notification_channels.append({"type": channel_type, "config": config})

    def acknowledge_alert(self, alert_id, person):
        if alert_id not in self.alerts:
            raise KeyError(f"Alert {alert_id} not found")
        self.alerts[alert_id]["status"] = "acknowledged"
        self.alerts[alert_id]["acknowledged_by"] = person
        self.alerts[alert_id]["acknowledged_at"] = datetime.now(timezone.utc).isoformat()

    def resolve_alert(self, alert_id):
        if alert_id not in self.alerts:
            raise KeyError(f"Alert {alert_id} not found")
        self.alerts[alert_id]["status"] = "resolved"
        self.alerts[alert_id]["resolved_at"] = datetime.now(timezone.utc).isoformat()

    def get_active_alerts(self):
        return {aid: a for aid, a in self.alerts.items() if a["status"] == "firing"}

    def get_metric_stats(self, name, window=100):
        values = [v for _, v in self.metrics[name][-window:]]
        if not values:
            return {"count": 0, "avg": 0, "min": 0, "max": 0, "p95": 0}
        arr = np.array(values)
        return {
            "count": len(arr),
            "avg": float(np.mean(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "p95": float(np.percentile(arr, 95)),
        }

    def get_dashboard_data(self):
        return {
            "total_metrics": len(self.metrics),
            "total_alerts": len(self.alerts),
            "active_alerts": len(self.get_active_alerts()),
            "alert_rules": len(self.alert_rules),
            "notification_channels": len(self.notification_channels),
            "metric_names": list(self.metrics.keys()),
        }


def test_10_monitoring_alert():
    """监控告警系统"""
    monitor = MonitoringAlertSystem()

    # 设置值班排班
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    monitor.set_oncall_schedule(today, "alice")

    # 通知渠道
    monitor.add_notification_channel("slack", {"webhook_url": "https://hooks.slack.com/xxx", "channel": "#ml-alerts"})
    monitor.add_notification_channel("email", {"recipients": ["team@ml.example.com"]})

    # 告警规则
    monitor.add_alert_rule("high_error_rate", "error_rate", ">", 0.05, severity="critical")
    monitor.add_alert_rule("high_latency", "p99_latency_ms", ">", 500, severity="warning")
    monitor.add_alert_rule("low_throughput", "throughput_qps", "<", 100, severity="warning")

    # 记录指标（正常范围）
    monitor.record_metric("error_rate", 0.01)
    monitor.record_metric("p99_latency_ms", 200)
    monitor.record_metric("throughput_qps", 500)

    assert len(monitor.get_active_alerts()) == 0

    # 记录异常指标
    monitor.record_metric("error_rate", 0.08)  # > 0.05 → critical
    monitor.record_metric("p99_latency_ms", 800)  # > 500 → warning
    monitor.record_metric("throughput_qps", 50)  # < 100 → warning

    active = monitor.get_active_alerts()
    assert len(active) == 3

    # 验证告警详情
    critical_alerts = [a for a in active.values() if a["severity"] == "critical"]
    assert len(critical_alerts) == 1
    assert critical_alerts[0]["rule"] == "high_error_rate"
    assert critical_alerts[0]["value"] == 0.08
    assert critical_alerts[0]["assigned_to"] == "alice"

    warning_alerts = [a for a in active.values() if a["severity"] == "warning"]
    assert len(warning_alerts) == 2

    # 确认告警
    alert_id = critical_alerts[0]["alert_id"]
    monitor.acknowledge_alert(alert_id, "bob")
    assert monitor.alerts[alert_id]["status"] == "acknowledged"
    assert monitor.alerts[alert_id]["acknowledged_by"] == "bob"

    # 解决告警
    monitor.resolve_alert(alert_id)
    assert monitor.alerts[alert_id]["status"] == "resolved"

    # 活跃告警减少
    active_after = monitor.get_active_alerts()
    assert len(active_after) == 2  # 剩下两个 warning

    # 指标统计
    monitor.record_metric("error_rate", 0.02)
    monitor.record_metric("error_rate", 0.03)
    stats = monitor.get_metric_stats("error_rate")
    assert stats["count"] >= 3
    assert stats["max"] == 0.08
    assert stats["avg"] > 0

    # 仪表盘
    dashboard = monitor.get_dashboard_data()
    assert dashboard["total_metrics"] >= 3
    assert dashboard["total_alerts"] >= 3
    assert dashboard["active_alerts"] == 2
    assert dashboard["notification_channels"] == 2
    print("✅ test_10 监控告警通过")


# ============================================================
# 主函数
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("第五阶段 5.3 云平台练习")
    print("=" * 60)
    tests = [
        test_01_cloud_storage,
        test_02_serverless,
        test_03_auto_scaling,
        test_04_cost_optimization,
        test_05_iam_security,
        test_06_multi_cloud,
        test_07_cloud_native,
        test_08_iac,
        test_09_deployment_pipeline,
        test_10_monitoring_alert,
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
