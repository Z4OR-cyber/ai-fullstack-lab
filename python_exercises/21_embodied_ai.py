#!/usr/bin/env python3
"""
================================================================================
阶段七：具身智能（Embodied AI）— 15 道练习题
================================================================================

本文件涵盖具身智能领域的核心知识点，从机器人学基础到前沿的 VLA 模型、
世界模型、Sim-to-Real 迁移，以及综合性的 SLAM、抓取和端到端系统。

环境信息：
  - Python 3.13.12
  - numpy, gymnasium(1.3.0), cv2(5.0.0), matplotlib, sklearn, scipy 等
  - mujoco: 安装超时，使用 numpy 模拟刚体动力学
  - 无 PyTorch/TensorFlow，全部用 numpy 实现

题目索引：
  7.1 机器人学基础
    题1  运动学与动力学基础（DH参数、正/逆运动学、雅可比、奇异点）
    题2  ROS 2 核心概念模拟（节点/话题/服务/动作、生命周期状态机）
    题3  传感器与感知基础（RGB-D、点云、IMU融合、针孔相机）

  7.2 仿真环境与控制
    题4  MuJoCo仿真入门 / numpy刚体动力学引擎
    题5  强化学习机器人控制（PPO、GAE、域随机化）
    题6  运动规划（RRT、RRT*、A*、碰撞检测、B样条平滑）

  7.3 视觉-语言-动作模型
    题7  VLA模型架构（RT-1/RT-2/OpenVLA对比、CNN视觉编码器、动作头）
    题8  模仿学习（行为克隆BC、DAgger、compounding error）
    题9  扩散策略（DDPM前向/反向扩散、条件动作生成）
    题10 OpenVLA实战模拟（推理流程、LoRA微调、延迟分析）

  7.4 世界模型与前沿
    题11 世界模型（DreamerV3核心概念、潜在动态、想象rollout）
    题12 Sim-to-Real迁移（域随机化、系统辨识、渐进迁移）

  7.5 综合项目
    题13 导航与建图SLAM（ICP扫描匹配、栅格地图、后端优化）
    题14 抓取与操作（Antipodal采样、力控仿真、质点弹簧模型）
    题15 端到端具身智能系统（感知→规划→执行闭环、状态机）

运行方式：
  cd /app/data/所有对话/主对话 && python3 python_exercises/21_embodied_ai.py
================================================================================
"""

import numpy as np
import warnings
warnings.filterwarnings('ignore')

# ── 尝试导入可选库 ──────────────────────────────────────────────────────────
HAS_MUJOCO = False
HAS_GYM = False
HAS_CV2 = False

try:
    import mujoco
    HAS_MUJOCO = True
except ImportError:
    pass

try:
    import gymnasium as gym
    HAS_GYM = True
except ImportError:
    pass

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    pass

print("=" * 80)
print("阶段七：具身智能（Embodied AI）— 15 道练习题")
print("=" * 80)
print(f"环境检测: mujoco={'✓' if HAS_MUJOCO else '✗(numpy替代)'}  "
      f"gymnasium={'✓' if HAS_GYM else '✗(自研)'}  "
      f"cv2={'✓' if HAS_CV2 else '✗'}")
print("=" * 80)

CHARTS_DIR = "/app/data/所有对话/主对话/python_exercises/charts/"
import os
os.makedirs(CHARTS_DIR, exist_ok=True)


# ============================================================================
# 题1：运动学与动力学基础
# ============================================================================
# 知识点：
#   - DH (Denavit-Hartenberg) 参数表：用4个参数(a, alpha, d, theta)描述相邻关节变换
#   - 正运动学：通过齐次变换矩阵链计算末端执行器位姿
#   - 逆运动学：数值解法——雅可比矩阵迭代（阻尼最小二乘）
#   - 雅可比矩阵：描述关节速度到末端速度的线性映射
#   - 奇异点检测：当雅可比矩阵行列式接近0时，机械臂处于奇异构型
# ============================================================================

def dh_transform(a, alpha, d, theta):
    """根据DH参数构建单关节齐次变换矩阵"""
    ct, st = np.cos(theta), np.sin(theta)
    ca, sa = np.cos(alpha), np.sin(alpha)
    return np.array([
        [ct, -st * ca,  st * sa, a * ct],
        [st,  ct * ca, -ct * sa, a * st],
        [0,    sa,       ca,      d],
        [0,    0,        0,       1]
    ])

def forward_kinematics(dh_params, joint_angles):
    """正运动学：DH参数表 + 关节角度 → 末端齐次变换矩阵"""
    T = np.eye(4)
    for i, (a, alpha, d, _) in enumerate(dh_params):
        theta = joint_angles[i]
        T = T @ dh_transform(a, alpha, d, theta)
    return T

def compute_jacobian(dh_params, joint_angles):
    """数值雅可比：通过有限差分计算 6×n 雅可比矩阵"""
    n = len(joint_angles)
    jac = np.zeros((6, n))
    eps = 1e-6
    T0 = forward_kinematics(dh_params, joint_angles)
    p0 = T0[:3, 3]
    R0 = T0[:3, :3]
    # 使用ZYZ或固定轴表示姿态，这里用位置+旋转矩阵展开
    euler0 = np.array([
        np.arctan2(R0[2, 1], R0[2, 2]),
        np.arctan2(-R0[2, 0], np.sqrt(R0[2, 1]**2 + R0[2, 2]**2)),
        np.arctan2(R0[1, 0], R0[0, 0])
    ])
    for i in range(n):
        dq = joint_angles.copy()
        dq[i] += eps
        T1 = forward_kinematics(dh_params, dq)
        p1 = T1[:3, 3]
        R1 = T1[:3, :3]
        euler1 = np.array([
            np.arctan2(R1[2, 1], R1[2, 2]),
            np.arctan2(-R1[2, 0], np.sqrt(R1[2, 1]**2 + R1[2, 2]**2)),
            np.arctan2(R1[1, 0], R1[0, 0])
        ])
        jac[:3, i] = (p1 - p0) / eps
        jac[3:, i] = (euler1 - euler0) / eps
    return jac

def inverse_kinematics(dh_params, target_pos, q_init, max_iter=200, tol=1e-4):
    """逆运动学：阻尼最小二乘雅可比迭代"""
    q = q_init.copy()
    lambda_damp = 0.1
    for it in range(max_iter):
        T = forward_kinematics(dh_params, q)
        err = target_pos - T[:3, 3]
        if np.linalg.norm(err) < tol:
            return q, it, True
        jac = compute_jacobian(dh_params, q)
        J = jac[:3, :]  # 只用位置部分
        JJT = J @ J.T + lambda_damp**2 * np.eye(3)
        dq = J.T @ np.linalg.solve(JJT, err)
        q += dq * 0.5  # 步长
    return q, max_iter, False

print("\n" + "─" * 80)
print("题1：运动学与动力学基础")
print("─" * 80)

# 3-DOF 平面机械臂 DH参数: [a, alpha, d, theta_offset]
dh_params = [
    (0.0,    np.pi/2, 0.5, 0),   # 基座到关节1
    (1.0,    0,       0.0, 0),   # 连杆1
    (1.0,    0,       0.0, 0),   # 连杆2
]
q_home = np.array([0.3, -0.5, 0.2])

# 正运动学
T_ee = forward_kinematics(dh_params, q_home)
print(f"初始关节角: {np.round(q_home, 4)}")
print(f"末端位姿 (齐次矩阵):\n{np.round(T_ee, 4)}")
print(f"末端位置: {np.round(T_ee[:3, 3], 4)}")

# 雅可比矩阵
J = compute_jacobian(dh_params, q_home)
print(f"\n雅可比矩阵 (6×3):\n{np.round(J, 4)}")
det_J = np.linalg.det(J[:3, :])
print(f"位置雅可比行列式: {det_J:.6f}")
print(f"奇异点检测: {'⚠ 奇异构型' if abs(det_J) < 0.01 else '✓ 非奇异'}")

# 逆运动学
target_pos = np.array([1.5, 0.8, 0.5])
q_solved, iterations, success = inverse_kinematics(dh_params, target_pos, q_home)
T_check = forward_kinematics(dh_params, q_solved)
print(f"\n逆运动学目标位置: {target_pos}")
print(f"求解关节角: {np.round(q_solved, 4)}")
print(f"验证末端位置: {np.round(T_check[:3, 3], 4)}")
print(f"迭代次数: {iterations}, 成功: {success}")
pos_err = np.linalg.norm(target_pos - T_check[:3, 3])
print(f"位置误差: {pos_err:.6f}")

print("""
关键总结：
  - DH参数用4个变量(a,α,d,θ)描述任意相邻关节的齐次变换
  - 正运动学通过矩阵连乘得到末端位姿
  - 逆运动学数值解法核心：J⁺Δx = Δq，加阻尼保证数值稳定
  - 雅可比行列式趋零 → 奇异构型，机械臂丧失某方向运动能力
""")
print("✅ 题1完成")


# ============================================================================
# 题2：ROS 2 核心概念模拟
# ============================================================================
# 知识点：
#   - ROS 2 通信模型：话题(pub/sub)、服务(req/res)、动作(goal/feedback/result)
#   - 自定义消息类型：类似结构体定义
#   - Launch参数传递：运行时配置节点
#   - 生命周期节点状态机：Unconfigured→Inactive→Active→Finalized
# ============================================================================

print("\n" + "─" * 80)
print("题2：ROS 2 核心概念模拟")
print("─" * 80)

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# ── 模拟消息类型 ──────────────────────────────────────────────
@dataclass
class TwistMsg:
    linear_x: float = 0.0
    angular_z: float = 0.0

@dataclass
class PoseMsg:
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0

@dataclass
class GraspActionGoal:
    target_x: float = 0.0
    target_y: float = 0.0

@dataclass
class GraspActionResult:
    success: bool = False
    message: str = ""

# ── 模拟ROS 2节点 ─────────────────────────────────────────────
class ROS2Node:
    def __init__(self, name):
        self.name = name
        self._publishers = {}    # topic → callback list
        self._subscribers = {}   # topic → callback
        self._services = {}      # service → handler
        self._params = {}
        self._timers = []
        self._started = False

    def create_publisher(self, msg_type, topic):
        self._publishers.setdefault(topic, [])
        return topic  # 返回topic名作为发布句柄

    def create_subscription(self, msg_type, topic, callback):
        self._subscribers[topic] = callback

    def publish(self, topic, msg):
        if topic in self._subscribers:
            self._subscribers[topic](msg)

    def create_service(self, srv_type, name, handler):
        self._services[name] = handler

    def call_service(self, name, request):
        if name in self._services:
            return self._services[name](request)
        return None

    def set_param(self, key, value):
        self._params[key] = value

    def get_param(self, key, default=None):
        return self._params.get(key, default)

    def create_timer(self, period, callback):
        self._timers.append((period, callback))

# ── 模拟Action（异步目标/反馈/结果）──────────────────────────
class ROS2Action:
    def __init__(self, name):
        self.name = name
        self._goal_callback = None
        self._feedback = None

    def set_goal_handler(self, handler):
        self._goal_callback = handler

    def execute(self, goal):
        if self._goal_callback:
            return self._goal_callback(goal)
        return GraspActionResult(success=False, message="No handler")

# ── 生命周期节点状态机 ─────────────────────────────────────────
class LifecycleState:
    UNCONFIGURED = "unconfigured"
    INACTIVE = "inactive"
    ACTIVE = "active"
    FINALIZED = "finalized"

class LifecycleNode(ROS2Node):
    def __init__(self, name):
        super().__init__(name)
        self.state = LifecycleState.UNCONFIGURED
        self._transitions = {
            (LifecycleState.UNCONFIGURED, "configure"): LifecycleState.INACTIVE,
            (LifecycleState.INACTIVE, "activate"): LifecycleState.ACTIVE,
            (LifecycleState.ACTIVE, "deactivate"): LifecycleState.INACTIVE,
            (LifecycleState.INACTIVE, "cleanup"): LifecycleState.UNCONFIGURED,
            (LifecycleState.UNCONFIGURED, "shutdown"): LifecycleState.FINALIZED,
            (LifecycleState.INACTIVE, "shutdown"): LifecycleState.FINALIZED,
            (LifecycleState.ACTIVE, "shutdown"): LifecycleState.FINALIZED,
        }

    def transition(self, event):
        key = (self.state, event)
        if key in self._transitions:
            old = self.state
            self.state = self._transitions[key]
            print(f"  [Lifecycle] {old} --{event}--> {self.state}")
            return True
        print(f"  [Lifecycle] 非法转换: {self.state} --{event}--> ???")
        return False

# ── 运行示例 ──────────────────────────────────────────────────
print("【1】Pub/Sub 通信示例")

# 创建控制器节点和移动节点
controller = ROS2Node("cmd_controller")
robot = ROS2Node("mobile_robot")

# 控制器发布速度命令，机器人订阅
pub_topic = controller.create_publisher(TwistMsg, "/cmd_vel")
robot.create_subscription(TwistMsg, "/cmd_vel",
    lambda msg: print(f"  机器人收到速度命令: linear={msg.linear_x:.2f}, angular={msg.angular_z:.2f}"))

controller.publish("/cmd_vel", TwistMsg(linear_x=0.5, angular_z=0.1))

print("\n【2】Service 通信示例")

# 导航服务
def navigate_service(request):
    print(f"  导航服务收到请求: 前往 ({request.target_x:.1f}, {request.target_y:.1f})")
    return GraspActionResult(success=True, message=f"已到达({request.target_x},{request.target_y})")

controller.create_service(GraspActionGoal, "/navigate", navigate_service)
result = controller.call_service("/navigate", GraspActionGoal(target_x=2.0, target_y=3.0))
print(f"  导航结果: success={result.success}, msg='{result.message}'")

print("\n【3】Action 通信示例（异步目标/反馈/结果）")
grasp_action = ROS2Action("/grasp")

def grasp_handler(goal):
    steps = 5
    for s in range(steps):
        progress = (s + 1) / steps
        print(f"  [反馈] 抓取进度: {progress*100:.0f}%")
    return GraspActionResult(success=True, message=f"成功抓取({goal.target_x},{goal.target_y})")

grasp_action.set_goal_handler(grasp_handler)
result = grasp_action.execute(GraspActionGoal(target_x=1.0, target_y=0.5))
print(f"  [结果] {result.message}")

print("\n【4】Launch 参数传递")
robot.set_param("use_sim_time", True)
robot.set_param("max_velocity", 2.0)
print(f"  参数: use_sim_time={robot.get_param('use_sim_time')}, max_velocity={robot.get_param('max_velocity')}")

print("\n【5】生命周期节点状态机")
lc_node = LifecycleNode("sensing_node")
lc_node.transition("configure")
lc_node.transition("activate")
lc_node.transition("deactivate")
lc_node.transition("activate")
lc_node.transition("shutdown")
# 非法转换测试
lc_node.transition("activate")

print("""
关键总结：
  - 话题适合高频传感器数据流，服务适合同步请求-响应，动作适合长时间任务
  - 生命周期节点让系统管理器能控制节点的启停顺序，保证确定性启动
  - Launch 参数实现运行时配置，无需重新编译
  - 自定义消息通过 dataclass 模拟，ROS 2 中用 .msg 文件定义
""")
print("✅ 题2完成")


# ============================================================================
# 题3：传感器与感知基础
# ============================================================================
# 知识点：
#   - RGB-D相机：通过结构光/ToF获取深度信息，生成深度图
#   - 点云：深度图→3D点云（相机内参反投影），降采样与法向量估计
#   - IMU仿真：加速度计+陀螺仪，互补滤波融合姿态
#   - 针孔相机模型：内参矩阵K，畸变模型
# ============================================================================

print("\n" + "─" * 80)
print("题3：传感器与感知基础")
print("─" * 80)

# ── 3.1 RGB-D相机深度图仿真 ──────────────────────────────────
print("【3.1】RGB-D相机深度图仿真")
H, W = 60, 80
fx, fy = 525.0, 525.0
cx, cy = W / 2, H / 2

# 模拟场景：一个倾斜平面 + 一个立方体
depth_map = np.zeros((H, W))
for v in range(H):
    for u in range(W):
        # 基础平面深度（随y线性变化，模拟倾斜）
        z = 2.0 + (v - H/2) * 0.02
        # 立方体遮挡（中心区域）
        if 25 < u < 55 and 20 < v < 45:
            z = 1.0
        depth_map[v, u] = z

print(f"  深度图尺寸: {depth_map.shape}")
print(f"  深度范围: [{depth_map.min():.2f}, {depth_map.max():.2f}]m")
print(f"  中心深度: {depth_map[H//2, W//2]:.2f}m")

# ── 3.2 点云生成与处理 ────────────────────────────────────────
print("\n【3.2】点云生成与处理")

# 深度图→点云（针孔模型反投影）
points = []
for v in range(H):
    for u in range(W):
        z = depth_map[v, u]
        if z > 0:
            x = (u - cx) * z / fx
            y = (v - cy) * z / fy
            points.append([x, y, z])
points = np.array(points)
print(f"  原始点云数量: {len(points)}")

# 体素降采样：将空间划分为网格，每个网格取一个代表点
voxel_size = 0.1
voxel_indices = np.floor(points / voxel_size).astype(int)
_, unique_idx = np.unique(voxel_indices, axis=0, return_index=True)
downsampled = points[unique_idx]
print(f"  降采样后点数: {len(downsampled)} (体素大小={voxel_size}m)")

# 法向量估计（简化PCA）
def estimate_normals_simple(pts, k=10):
    """对每个点用最近邻PCA估法向量"""
    normals = np.zeros_like(pts)
    n = len(pts)
    step = max(1, n // 200)  # 采样部分点以加速
    for i in range(0, n, step):
        diff = pts - pts[i]
        dists = np.sum(diff**2, axis=1)
        neighbors = np.argsort(dists)[:k]
        local_pts = pts[neighbors]
        cov = np.cov(local_pts.T)
        eigvals, eigvecs = np.linalg.eigh(cov)
        normals[i] = eigvecs[:, 0]  # 最小特征值对应的方向
    return normals

normals = estimate_normals_simple(downsampled, k=10)
print(f"  法向量估计完成 (形状: {normals.shape})")
print(f"  样本法向量: {np.round(normals[0], 4)}")

# ── 3.3 IMU仿真与互补滤波 ─────────────────────────────────────
print("\n【3.3】IMU仿真与互补滤波融合")

dt = 0.01
T_total = 5.0
n_steps = int(T_total / dt)
true_angle = np.zeros(n_steps)
gyro_data = np.zeros(n_steps)
accel_angle = np.zeros(n_steps)

for i in range(n_steps):
    t = i * dt
    # 真实角度：缓慢正弦摆动
    true_angle[i] = 30 * np.sin(0.5 * t)  # 度
    # 陀螺仪测量：真实角速度 + 噪声 + 漂移
    true_rate = 30 * 0.5 * np.cos(0.5 * t)
    gyro_data[i] = true_rate + np.random.randn() * 0.5 + 0.02 * t  # 逐渐漂移
    # 加速度计测量角度：真实角度 + 高频噪声
    accel_angle[i] = true_angle[i] + np.random.randn() * 3.0

# 互补滤波：高通陀螺 + 低通加速度
alpha_cf = 0.98
fused_angle = np.zeros(n_steps)
fused_angle[0] = accel_angle[0]
for i in range(1, n_steps):
    fused_angle[i] = alpha_cf * (fused_angle[i-1] + gyro_data[i] * dt) + (1 - alpha_cf) * accel_angle[i]

rmse_gyro = np.sqrt(np.mean((true_angle - np.cumsum(gyro_data) * dt + true_angle[0])**2))
rmse_accel = np.sqrt(np.mean((true_angle - accel_angle)**2))
rmse_fused = np.sqrt(np.mean((true_angle - fused_angle)**2))
print(f"  陀螺仪积分RMSE: {rmse_gyro:.2f}° (受漂移影响)")
print(f"  加速度计RMSE: {rmse_accel:.2f}° (受噪声影响)")
print(f"  互补滤波RMSE: {rmse_fused:.2f}° (融合后最优)")

# ── 3.4 针孔相机模型与标定 ────────────────────────────────────
print("\n【3.4】针孔相机模型与标定")

# 内参矩阵 K
K = np.array([
    [fx,  0, cx],
    [ 0, fy, cy],
    [ 0,  0,  1]
])
print(f"  相机内参矩阵 K:\n{K}")

# 标定：已知3D点→2D投影，验证投影模型
P_3d = np.array([0.3, 0.2, 2.0])  # 3D世界点（相机坐标系）
P_proj = K @ P_3d  # 投影
u_pixel = P_proj[0] / P_proj[2]
v_pixel = P_proj[1] / P_proj[2]
print(f"  3D点 {P_3d} → 像素 ({u_pixel:.1f}, {v_pixel:.1f})")

# 畸变模型（径向畸变）
k1, k2 = 0.1, -0.05  # 畸变系数
r2 = u_pixel**2 + v_pixel**2
distortion = 1 + k1 * r2 + k2 * r2**2
u_distorted = u_pixel * distortion
v_distorted = v_pixel * distortion
print(f"  畸变后像素: ({u_distorted:.1f}, {v_distorted:.1f})")

print("""
关键总结：
  - RGB-D相机通过深度图反投影生成点云，内参矩阵K是核心
  - 体素降采样在保持空间结构的同时大幅减少点数
  - 互补滤波用陀螺的高频+加速度计的低频，简单有效
  - 针孔模型：P_uv = K * P_camera，畸变模型补偿镜头误差
""")
print("✅ 题3完成")



# ============================================================================
# 题4：MuJoCo仿真入门 / numpy刚体动力学引擎
# ============================================================================
# 知识点：
#   - MuJoCo (Multi-Joint dynamics with Contact)：物理仿真引擎
#   - MJCF模型格式：XML描述刚体、关节、执行器
#   - 如果安装失败→用numpy实现简化刚体动力学
#   - 欧拉-拉格朗日方程：M(q)q̈ + C(q,q̇)q̇ + G(q) = τ
#   - 数值积分：RK4 / 半隐式欧拉
# ============================================================================

print("\n" + "─" * 80)
print("题4：MuJoCo仿真入门 / numpy刚体动力学引擎")
print("─" * 80)

if HAS_MUJOCO:
    print("  mujoco可用，使用真实引擎...")
else:
    print("  mujoco不可用，使用numpy实现的简化刚体动力学引擎")

# ── 简化双摆系统（2-DOF机械臂）────────────────────────────────
class RigidBodySim:
    """numpy实现的2-DOF机械臂动力学仿真器"""
    def __init__(self, m1=1.0, m2=1.0, l1=1.0, l2=1.0, g=9.81):
        self.m1, self.m2 = m1, m2
        self.l1, self.l2 = l1, l2
        self.g = g
        # 状态: [q1, q2, q1_dot, q2_dot]
        self.state = np.array([0.1, 0.0, 0.0, 0.0])
        self.t = 0.0

    def dynamics(self, state, tau):
        """欧拉-拉格朗日方程：计算加速度"""
        q1, q2, q1d, q2d = state
        m1, m2, l1, l2, g = self.m1, self.m2, self.l1, self.l2, self.g

        # 惯量矩阵 M(q)
        M11 = m1 * l1**2 + m2 * (l1**2 + l2**2 + 2*l1*l2*np.cos(q2))
        M12 = m2 * (l2**2 + l1*l2*np.cos(q2))
        M22 = m2 * l2**2
        M = np.array([[M11, M12], [M12, M22]])

        # 科里奥利力 C(q, q̇)
        C11 = -m2 * l1 * l2 * np.sin(q2) * q2d
        C12 = -m2 * l1 * l2 * np.sin(q2) * (q1d + q2d)
        C21 = m2 * l1 * l2 * np.sin(q2) * q1d
        C22 = 0
        C = np.array([[C11, C12], [C21, C22]])

        # 重力项 G(q)
        G1 = (m1 + m2) * g * l1 * np.cos(q1) + m2 * g * l2 * np.cos(q1 + q2)
        G2 = m2 * g * l2 * np.cos(q1 + q2)
        G_vec = np.array([G1, G2])

        # M*q̈ + C*q̇ + G = τ  →  q̈ = M⁻¹(τ - C*q̇ - G)
        q_ddot = np.linalg.solve(M, tau - C @ np.array([q1d, q2d]) - G_vec)
        return np.array([q1d, q2d, q_ddot[0], q_ddot[1]])

    def rk4_step(self, dt, tau=np.array([0.0, 0.0])):
        """RK4数值积分"""
        s = self.state
        k1 = self.dynamics(s, tau)
        k2 = self.dynamics(s + 0.5*dt*k1, tau)
        k3 = self.dynamics(s + 0.5*dt*k2, tau)
        k4 = self.dynamics(s + dt*k3, tau)
        self.state = s + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)
        self.t += dt

    def get_joint_positions(self):
        """获取关节末端位置"""
        q1, q2 = self.state[0], self.state[1]
        x1 = self.l1 * np.cos(q1)
        y1 = self.l1 * np.sin(q1)
        x2 = x1 + self.l2 * np.cos(q1 + q2)
        y2 = y1 + self.l2 * np.sin(q1 + q2)
        return np.array([x1, y1]), np.array([x2, y2])

    def get_joint_state(self):
        """读取关节状态（位置、速度）"""
        return self.state.copy()

    def apply_torque(self, dt, tau):
        """施加控制力矩"""
        self.rk4_step(dt, tau)

# ── 仿真运行 ──────────────────────────────────────────────────
sim = RigidBodySim(m1=2.0, m2=1.0, l1=1.0, l2=0.8, g=9.81)
dt = 0.001
n_steps = 2000

# PD控制器：跟踪目标角度
q_target = np.array([np.pi/2, np.pi/4])
Kp = np.array([50.0, 30.0])
Kd = np.array([5.0, 3.0])

positions_log = []
velocities_log = []
torques_log = []
time_log = []

for step in range(n_steps):
    q = sim.get_joint_state()
    # PD控制力矩
    tau = Kp * (q_target - q[:2]) - Kd * q[2:]
    tau = np.clip(tau, -50, 50)  # 力矩限制
    sim.apply_torque(dt, tau)

    if step % 100 == 0:
        positions_log.append(q[:2].copy())
        velocities_log.append(q[2:].copy())
        torques_log.append(tau.copy())
        time_log.append(sim.t)

positions_log = np.array(positions_log)
velocities_log = np.array(velocities_log)
torques_log = np.array(torques_log)
time_log = np.array(time_log)

final_state = sim.get_joint_state()
print(f"  仿真步数: {n_steps}, 总时间: {sim.t:.2f}s")
print(f"  初始角度: [0.1, 0.0] rad")
print(f"  目标角度: {np.round(q_target, 4)} rad")
print(f"  最终角度: {np.round(final_state[:2], 4)} rad")
print(f"  角度误差: {np.round(q_target - final_state[:2], 4)} rad")
print(f"  最终角速度: {np.round(final_state[2:], 6)} rad/s")
print(f"  最大力矩: [{torques_log[:,0].max():.2f}, {torques_log[:,1].max():.2f}] Nm")
print(f"  末端位置: {np.round(sim.get_joint_positions()[1], 4)}")

print("""
关键总结：
  - 欧拉-拉格朗日方程：M(q)q̈ + C(q,q̇)q̇ + G(q) = τ
  - M是构型依赖的惯量矩阵，C是科里奥利/离心力，G是重力
  - RK4比欧拉法精度高4阶，适合刚体仿真
  - PD控制通过力矩输入驱动关节到目标位置
  - MuJoCo内部也是求解类似的动力学方程，但支持接触/约束/摩擦
""")
print("✅ 题4完成")


# ============================================================================
# 题5：强化学习机器人控制
# ============================================================================
# 知识点：
#   - PPO (Proximal Policy Optimization)：clip目标函数防止策略更新过大
#   - GAE (Generalized Advantage Estimation)：λ-回报平衡偏差与方差
#   - 域随机化：训练时随机化物理参数，提升sim-to-real泛化
#   - CartPole环境：经典的控制问题
# ============================================================================

print("\n" + "─" * 80)
print("题5：强化学习机器人控制")
print("─" * 80)

# ── CartPole环境（自研，兼容gymnasium接口）───────────────────
class CartPoleEnv:
    """简化CartPole物理环境"""
    def __init__(self, gravity=9.81, masscart=1.0, masspole=0.1, length=0.5, force_mag=10.0, seed=42):
        self.gravity = gravity
        self.masscart = masscart
        self.masspole = masspole
        self.length = length  # 半杆长
        self.force_mag = force_mag
        self.total_mass = masscart + masspole
        self.polemass_length = masspole * length
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.reset()

    def reset(self):
        self.state = self.rng.uniform(-0.05, 0.05, size=4)
        self.steps = 0
        return self.state.copy()

    def step(self, action):
        x, x_dot, theta, theta_dot = self.state
        force = self.force_mag if action == 1 else -self.force_mag
        costheta = np.cos(theta)
        sintheta = np.sin(theta)
        temp = (force + self.polemass_length * theta_dot**2 * sintheta) / self.total_mass
        thetaacc = (self.gravity * sintheta - costheta * temp) / (
            self.length * (4.0/3.0 - self.masspole * costheta**2 / self.total_mass))
        xacc = temp - self.polemass_length * thetaacc * costheta / self.total_mass

        dt = 0.02
        x = x + dt * x_dot
        x_dot = x_dot + dt * xacc
        theta = theta + dt * theta_dot
        theta_dot = theta_dot + dt * thetaacc

        self.state = np.array([x, x_dot, theta, theta_dot])
        self.steps += 1

        done = bool(theta > 0.21 or theta < -0.21 or x > 2.4 or x < -2.4 or self.steps > 200)
        reward = 1.0 if not done else 0.0
        return self.state.copy(), reward, done

    def set_domain_random_params(self):
        """域随机化：随机化物理参数"""
        self.gravity = self.rng.uniform(8.0, 11.0)
        self.masscart = self.rng.uniform(0.8, 1.2)
        self.masspole = self.rng.uniform(0.08, 0.12)
        self.length = self.rng.uniform(0.4, 0.6)
        self.force_mag = self.rng.uniform(8.0, 12.0)
        self.total_mass = self.masscart + self.masspole
        self.polemass_length = self.masspole * self.length

# ── PPO核心组件 ──────────────────────────────────────────────
class PolicyNetwork:
    """简化策略网络（numpy MLP）：4→64→64→2（动作logits）"""
    def __init__(self, obs_dim=4, act_dim=2, hidden=64, lr=0.001, seed=42):
        rng = np.random.default_rng(seed)
        self.W1 = rng.standard_normal((obs_dim, hidden)) * 0.1
        self.b1 = np.zeros(hidden)
        self.W2 = rng.standard_normal((hidden, hidden)) * 0.1
        self.b2 = np.zeros(hidden)
        self.W3 = rng.standard_normal((hidden, act_dim)) * 0.1
        self.b3 = np.zeros(act_dim)
        self.lr = lr

    def forward(self, x):
        self.x = x
        self.h1 = np.tanh(x @ self.W1 + self.b1)
        self.h2 = np.tanh(self.h1 @ self.W2 + self.b2)
        logits = self.h2 @ self.W3 + self.b3
        # softmax
        exp_l = np.exp(logits - logits.max())
        self.probs = exp_l / exp_l.sum()
        return self.probs

    def sample(self, x):
        probs = self.forward(x)
        action = np.random.choice(len(probs), p=probs)
        return action, probs[action]

    def update(self, grads, lr_scale=1.0):
        self.W1 -= self.lr * lr_scale * grads['W1']
        self.b1 -= self.lr * lr_scale * grads['b1']
        self.W2 -= self.lr * lr_scale * grads['W2']
        self.b2 -= self.lr * lr_scale * grads['b2']
        self.W3 -= self.lr * lr_scale * grads['W3']
        self.b3 -= self.lr * lr_scale * grads['b3']

class ValueNetwork:
    """价值网络：4→64→64→1"""
    def __init__(self, obs_dim=4, hidden=64, lr=0.002, seed=42):
        rng = np.random.default_rng(seed + 1)
        self.W1 = rng.standard_normal((obs_dim, hidden)) * 0.1
        self.b1 = np.zeros(hidden)
        self.W2 = rng.standard_normal((hidden, hidden)) * 0.1
        self.b2 = np.zeros(hidden)
        self.W3 = rng.standard_normal((hidden, 1)) * 0.1
        self.b3 = np.zeros(1)
        self.lr = lr

    def forward(self, x):
        self.x = x
        self.h1 = np.tanh(x @ self.W1 + self.b1)
        self.h2 = np.tanh(self.h1 @ self.W2 + self.b2)
        v = self.h2 @ self.W3 + self.b3
        return v[0]

    def update(self, x, target, lr_scale=1.0):
        v = self.forward(x)
        loss = 0.5 * (target - v)**2
        dv = (v - target)
        dW3 = np.outer(self.h2, dv)
        db3 = dv
        dh2 = dv * self.W3[:, 0]
        dW2 = np.outer(self.h1, dh2 * (1 - self.h2**2))
        db2 = dh2 * (1 - self.h2**2)
        dh1 = (dh2 * (1 - self.h2**2)) @ self.W2.T
        dW1 = np.outer(self.x, dh1 * (1 - self.h1**2))
        db1 = dh1 * (1 - self.h1**2)
        self.W1 -= self.lr * lr_scale * dW1
        self.b1 -= self.lr * lr_scale * db1
        self.W2 -= self.lr * lr_scale * dW2
        self.b2 -= self.lr * lr_scale * db2
        self.W3 -= self.lr * lr_scale * dW3
        self.b3 -= self.lr * lr_scale * db3
        return loss

def compute_gae(rewards, values, gamma=0.99, lam=0.95):
    """GAE: 广义优势估计"""
    advantages = np.zeros(len(rewards))
    last_adv = 0
    for t in reversed(range(len(rewards))):
        if t == len(rewards) - 1:
            next_value = 0.0
        else:
            next_value = values[t + 1]
        delta = rewards[t] + gamma * next_value - values[t]
        last_adv = delta + gamma * lam * last_adv
        advantages[t] = last_adv
    returns = advantages + np.array(values)
    return advantages, returns

# ── PPO训练循环 ──────────────────────────────────────────────
env = CartPoleEnv(seed=42)
policy = PolicyNetwork(seed=42)
value_fn = ValueNetwork(seed=42)

n_episodes = 300
clip_ratio = 0.2
gamma = 0.99
episode_rewards = []

for ep in range(n_episodes):
    # ── 收集轨迹 ──
    state = env.reset()
    # 域随机化（每50轮随机化物理参数）
    if ep % 50 == 0 and ep > 0:
        env.set_domain_random_params()

    states, actions, rewards, log_probs, values = [], [], [], [], []
    done = False

    while not done:
        s = state.copy()
        action, prob = policy.sample(s)
        v = value_fn.forward(s)
        next_state, reward, done = env.step(action)

        states.append(s)
        actions.append(action)
        rewards.append(reward)
        log_probs.append(np.log(prob + 1e-8))
        values.append(v)
        state = next_state

    ep_reward = sum(rewards)
    episode_rewards.append(ep_reward)

    # ── 计算GAE ──
    advantages, returns = compute_gae(rewards, values, gamma=gamma, lam=0.95)
    advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

    # ── PPO更新（简化版）──
    for s, a, old_lp, adv, ret in zip(states, actions, log_probs, advantages, returns):
        probs = policy.forward(s)
        new_lp = np.log(probs[a] + 1e-8)
        ratio = np.exp(new_lp - old_lp)
        clipped_ratio = np.clip(ratio, 1 - clip_ratio, 1 + clip_ratio)
        policy_loss = -min(ratio * adv, clipped_ratio * adv)

        # 数值梯度（简化）
        grad_W3 = np.outer(policy.h2, probs)
        grad_W3[:, a] -= policy.h2
        grad_W3 *= -adv * 0.01

        policy.update({
            'W1': np.zeros_like(policy.W1),
            'b1': np.zeros_like(policy.b1),
            'W2': np.zeros_like(policy.W2),
            'b2': np.zeros_like(policy.b2),
            'W3': grad_W3,
            'b3': probs * 0
        }, lr_scale=1.0)

        value_fn.update(s, ret, lr_scale=0.5)

# 评估
eval_rewards = []
for ep in range(10):
    state = env.reset()
    total_r = 0
    done = False
    while not done:
        probs = policy.forward(state)
        action = np.argmax(probs)
        state, reward, done = env.step(action)
        total_r += reward
    eval_rewards.append(total_r)

print(f"  训练轮数: {n_episodes}")
print(f"  前50轮平均奖励: {np.mean(episode_rewards[:50]):.1f}")
print(f"  后50轮平均奖励: {np.mean(episode_rewards[-50:]):.1f}")
print(f"  评估10轮平均奖励: {np.mean(eval_rewards):.1f}")
print(f"  域随机化: 每50轮随机化重力/质量/杆长/力矩")

print("""
关键总结：
  - PPO核心：clip(ratio, 1-ε, 1+ε) * advantage 限制策略更新步长
  - GAE：A_t = Σ(γλ)^k * δ_{t+k}，平衡偏差(λ→0)与方差(λ→1)
  - 域随机化：训练时随机化物理参数，提升策略在真实环境中的泛化
  - CartPole是RL控制的经典benchmark，杆角度>12°或小车越界即失败
""")
print("✅ 题5完成")


# ============================================================================
# 题6：运动规划
# ============================================================================
# 知识点：
#   - RRT (Rapidly-exploring Random Tree)：随机扩展树
#   - RRT*：RRT的渐进最优版本，重新连接邻居节点
#   - A*：基于栅格的启发式搜索
#   - 碰撞检测：圆形和矩形障碍物
#   - 轨迹平滑：B样条插值
# ============================================================================

print("\n" + "─" * 80)
print("题6：运动规划")
print("─" * 80)

# ── 环境定义 ──────────────────────────────────────────────────
class Obstacle:
    def __init__(self, kind, **params):
        self.kind = kind
        self.params = params

    def contains(self, point, margin=0.3):
        x, y = point
        if self.kind == 'circle':
            cx, cy, r = self.params['cx'], self.params['cy'], self.params['r']
            return (x - cx)**2 + (y - cy)**2 < (r + margin)**2
        elif self.kind == 'rect':
            x0, y0, w, h = self.params['x'], self.params['y'], self.params['w'], self.params['h']
            return (x0 - margin < x < x0 + w + margin and y0 - margin < y < y0 + h + margin)

def is_collision_free(p1, p2, obstacles, step=0.05):
    """检查线段p1→p2是否与障碍物碰撞"""
    dist = np.linalg.norm(p2 - p1)
    n = max(int(dist / step), 2)
    for i in range(n + 1):
        t = i / n
        pt = p1 + t * (p2 - p1)
        for obs in obstacles:
            if obs.contains(pt):
                return False
    return True

# 设置障碍物
obstacles = [
    Obstacle('circle', cx=3, cy=3, r=1.0),
    Obstacle('circle', cx=7, cy=5, r=1.2),
    Obstacle('rect', x=4, y=6, w=2, h=1.5),
]
start = np.array([0.5, 0.5])
goal = np.array([9.0, 9.0])

# ── RRT算法 ──────────────────────────────────────────────────
def rrt(start, goal, obstacles, max_iter=2000, step_size=0.5, goal_bias=0.1, seed=42):
    rng = np.random.default_rng(seed)
    tree = [start.copy()]
    parents = [-1]
    for i in range(max_iter):
        if rng.random() < goal_bias:
            sample = goal.copy()
        else:
            sample = rng.uniform([0, 0], [10, 10])
        # 找最近节点
        dists = [np.linalg.norm(node - sample) for node in tree]
        nearest_idx = np.argmin(dists)
        nearest = tree[nearest_idx]
        # 扩展
        direction = sample - nearest
        if np.linalg.norm(direction) < 1e-6:
            continue
        new_node = nearest + step_size * direction / np.linalg.norm(direction)
        if is_collision_free(nearest, new_node, obstacles):
            tree.append(new_node)
            parents.append(nearest_idx)
            if np.linalg.norm(new_node - goal) < step_size * 2:
                if is_collision_free(new_node, goal, obstacles):
                    tree.append(goal.copy())
                    parents.append(len(tree) - 2)
                    # 回溯路径
                    path = [goal.copy()]
                    idx = len(tree) - 1
                    while parents[idx] != -1:
                        path.append(tree[parents[idx]])
                        idx = parents[idx]
                    return path[::-1], len(tree)
    return None, len(tree)

# ── RRT*算法 ─────────────────────────────────────────────────
def rrt_star(start, goal, obstacles, max_iter=1500, step_size=0.5, radius=1.5, seed=42):
    rng = np.random.default_rng(seed)
    tree = [start.copy()]
    parents = [-1]
    costs = [0.0]
    for i in range(max_iter):
        sample = rng.uniform([0, 0], [10, 10])
        if rng.random() < 0.1:
            sample = goal.copy()
        dists = [np.linalg.norm(node - sample) for node in tree]
        nearest_idx = np.argmin(dists)
        nearest = tree[nearest_idx]
        direction = sample - nearest
        if np.linalg.norm(direction) < 1e-6:
            continue
        new_node = nearest + step_size * direction / np.linalg.norm(direction)
        if not is_collision_free(nearest, new_node, obstacles):
            continue
        # 找邻居
        neighbors = [j for j in range(len(tree)) if np.linalg.norm(tree[j] - new_node) < radius]
        # 选择最小成本父节点
        best_parent = nearest_idx
        best_cost = costs[nearest_idx] + np.linalg.norm(new_node - nearest)
        for j in neighbors:
            if is_collision_free(tree[j], new_node, obstacles):
                c = costs[j] + np.linalg.norm(new_node - tree[j])
                if c < best_cost:
                    best_cost = c
                    best_parent = j
        tree.append(new_node)
        parents.append(best_parent)
        costs.append(best_cost)
        # 重新连接
        for j in neighbors:
            if j == best_parent:
                continue
            if is_collision_free(new_node, tree[j], obstacles):
                new_cost = best_cost + np.linalg.norm(tree[j] - new_node)
                if new_cost < costs[j]:
                    parents[j] = len(tree) - 1
                    costs[j] = new_cost
        # 检查目标
        if np.linalg.norm(new_node - goal) < step_size * 2:
            if is_collision_free(new_node, goal, obstacles):
                tree.append(goal.copy())
                parents.append(len(tree) - 2)
                costs.append(costs[-1] + np.linalg.norm(goal - new_node))
                path = [goal.copy()]
                idx = len(tree) - 1
                while parents[idx] != -1:
                    path.append(tree[parents[idx]])
                    idx = parents[idx]
                return path[::-1], len(tree)
    return None, len(tree)

# ── A*算法 ───────────────────────────────────────────────────
def a_star(start, goal, obstacles, grid_size=0.5, world_size=10):
    """栅格A*搜索"""
    def to_grid(p):
        return (int(p[0] / grid_size), int(p[1] / grid_size))
    def to_world(g):
        return np.array([g[0] * grid_size + grid_size/2, g[1] * grid_size + grid_size/2])

    grid_n = int(world_size / grid_size)
    start_g = to_grid(start)
    goal_g = to_grid(goal)

    open_set = {start_g: 0}
    came_from = {}
    g_score = {start_g: 0}
    f_score = {start_g: np.linalg.norm(np.array(start_g) - np.array(goal_g))}

    while open_set:
        current = min(open_set, key=lambda k: f_score.get(k, 1e9))
        if current == goal_g:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return [to_world(g) for g in reversed(path)]
        del open_set[current]
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
            neighbor = (current[0]+dx, current[1]+dy)
            if not (0 <= neighbor[0] < grid_n and 0 <= neighbor[1] < grid_n):
                continue
            pt = to_world(neighbor)
            if any(obs.contains(pt, margin=0.1) for obs in obstacles):
                continue
            move_cost = np.sqrt(dx**2 + dy**2)
            tentative = g_score[current] + move_cost
            if tentative < g_score.get(neighbor, 1e9):
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                f_score[neighbor] = tentative + np.linalg.norm(np.array(neighbor) - np.array(goal_g))
                open_set[neighbor] = tentative
    return None

# ── B样条平滑 ────────────────────────────────────────────────
def bspline_smooth(path, n_output=50):
    """简化的B样条插值平滑（Catmull-Rom）"""
    path = np.array(path)
    n = len(path)
    if n < 3:
        return path
    t_new = np.linspace(0, 1, n_output)
    smoothed = np.zeros((n_output, 2))
    for i, ti in enumerate(t_new):
        if ti <= 0:
            smoothed[i] = path[0]
        elif ti >= 1:
            smoothed[i] = path[-1]
        else:
            idx = ti * (n - 1)
            idx0 = int(idx)
            idx1 = min(idx0 + 1, n - 1)
            frac = idx - idx0
            idx_1 = max(idx0 - 1, 0)
            idx2 = min(idx1 + 1, n - 1)
            p0, p1, p2, p3 = path[idx_1], path[idx0], path[idx1], path[idx2]
            t2 = frac
            smoothed[i] = 0.5 * (
                2*p1 + (-p0 + p2)*t2 + (2*p0 - 5*p1 + 4*p2 - p3)*t2**2 + (-p0 + 3*p1 - 3*p2 + p3)*t2**3
            )
    return smoothed

# ── 运行三种规划算法 ──────────────────────────────────────────
print("【1】RRT路径规划")
rrt_path, rrt_nodes = rrt(start, goal, obstacles, max_iter=3000, seed=42)
if rrt_path:
    rrt_len = sum(np.linalg.norm(rrt_path[i+1] - rrt_path[i]) for i in range(len(rrt_path)-1))
    print(f"  找到路径! 节点数: {rrt_nodes}, 路径长度: {rrt_len:.2f}")
else:
    print(f"  未找到路径 (节点数: {rrt_nodes})")

print("\n【2】RRT*路径规划")
rrt_star_path, rrt_star_nodes = rrt_star(start, goal, obstacles, max_iter=2000, seed=42)
if rrt_star_path:
    rrt_star_len = sum(np.linalg.norm(rrt_star_path[i+1] - rrt_star_path[i]) for i in range(len(rrt_star_path)-1))
    print(f"  找到路径! 节点点数: {rrt_star_nodes}, 路径长度: {rrt_star_len:.2f}")
else:
    print(f"  未找到路径 (节点数: {rrt_star_nodes})")

print("\n【3】A*路径规划")
astar_path = a_star(start, goal, obstacles, grid_size=0.5)
if astar_path:
    astar_len = sum(np.linalg.norm(astar_path[i+1] - astar_path[i]) for i in range(len(astar_path)-1))
    print(f"  找到路径! 栅格步数: {len(astar_path)}, 路径长度: {astar_len:.2f}")
else:
    print("  未找到路径")

# B样条平滑
print("\n【4】轨迹平滑（B样条/Catmull-Rom）")
if rrt_path:
    smoothed = bspline_smooth(rrt_path, n_output=50)
    smooth_len = sum(np.linalg.norm(smoothed[i+1] - smoothed[i]) for i in range(len(smoothed)-1))
    print(f"  原始路径点数: {len(rrt_path)}, 平滑后点数: {len(smoothed)}")
    print(f"  平滑后路径长度: {smooth_len:.2f} (原: {rrt_len:.2f})")

# 可视化
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

fig, ax = plt.subplots(1, 1, figsize=(8, 8))
for obs in obstacles:
    if obs.kind == 'circle':
        circle = plt.Circle((obs.params['cx'], obs.params['cy']), obs.params['r'], color='red', alpha=0.5)
        ax.add_patch(circle)
    elif obs.kind == 'rect':
        rect = plt.Rectangle((obs.params['x'], obs.params['y']), obs.params['w'], obs.params['h'], color='red', alpha=0.5)
        ax.add_patch(rect)
ax.plot(*start, 'go', markersize=12, label='Start')
ax.plot(*goal, 'r*', markersize=15, label='Goal')
if rrt_path:
    path_arr = np.array(rrt_path)
    ax.plot(path_arr[:, 0], path_arr[:, 1], 'b.-', label='RRT')
if rrt_star_path:
    path_arr = np.array(rrt_star_path)
    ax.plot(path_arr[:, 0], path_arr[:, 1], 'g.-', label='RRT*')
if astar_path:
    path_arr = np.array(astar_path)
    ax.plot(path_arr[:, 0], path_arr[:, 1], 'm.-', label='A*')
if rrt_path:
    ax.plot(smoothed[:, 0], smoothed[:, 1], 'c-', linewidth=2, label='B-spline')
ax.set_xlim(-0.5, 10.5)
ax.set_ylim(-0.5, 10.5)
ax.set_aspect('equal')
ax.legend()
ax.set_title('Motion Planning: RRT vs RRT* vs A*')
fig.savefig(CHARTS_DIR + 'q6_motion_planning.png', dpi=100, bbox_inches='tight')
plt.close(fig)
print("  图表已保存: q6_motion_planning.png")

print("""
关键总结：
  - RRT：随机扩展，概率完备但不最优；goal_bias加速收敛
  - RRT*：加入重新连接(rewire)，路径渐近最优；radius决定优化范围
  - A*：栅格搜索，启发式保证最优但分辨率受限
  - B样条/Catmull-Rom：消除路径锯齿，生成连续可微轨迹
""")
print("✅ 题6完成")


# ============================================================================
# 题7：VLA模型架构
# ============================================================================
# 知识点：
#   - VLA (Vision-Language-Action) 模型：将视觉和语言输入映射到机器人动作
#   - RT-1：专用架构（EfficientNet视觉 + Transformer语言 + 动作tokenizer）
#   - RT-2：将VLM（PaLI/PaLM）微调为输出动作token，继承世界知识
#   - OpenVLA：开源VLA，基于Prismatic VLM，7B参数，支持LoRA微调
#   - 架构组件：视觉编码器(CNN)、语言嵌入层、动作头(MLP)、动作tokenization
# ============================================================================

print("\n" + "─" * 80)
print("题7：VLA模型架构")
print("─" * 80)

# ── 简化CNN视觉编码器 ────────────────────────────────────────
class SimpleCNN:
    """简化CNN：处理RGB图像→特征向量"""
    def __init__(self, input_channels=3, seed=42):
        rng = np.random.default_rng(seed)
        self.conv1_W = rng.standard_normal((3, 3, input_channels, 8)) * 0.1
        self.conv1_b = np.zeros(8)
        self.conv2_W = rng.standard_normal((3, 3, 8, 16)) * 0.1
        self.conv2_b = np.zeros(16)
        self.fc_W = rng.standard_normal((16 * 4 * 4, 64)) * 0.1
        self.fc_b = np.zeros(64)

    def _conv2d(self, x, W, b, stride=2):
        """简化卷积前向"""
        h, w, c_in = x.shape
        kh, kw, _, c_out = W.shape
        oh = (h - kh) // stride + 1
        ow = (w - kw) // stride + 1
        out = np.zeros((oh, ow, c_out))
        for i in range(oh):
            for j in range(ow):
                patch = x[i*stride:i*stride+kh, j*stride:j*stride+kw, :]
                for co in range(c_out):
                    out[i, j, co] = np.sum(patch * W[:, :, :, co]) + b[co]
        return np.maximum(out, 0)  # ReLU

    def forward(self, img):
        """img: (H, W, C) → feature: (64,)"""
        x = self._conv2d(img, self.conv1_W, self.conv1_b, stride=2)
        x = self._conv2d(x, self.conv2_W, self.conv2_b, stride=2)
        x = x.flatten()
        if len(x) > self.fc_W.shape[0]:
            x = x[:self.fc_W.shape[0]]
        elif len(x) < self.fc_W.shape[0]:
            x = np.pad(x, (0, self.fc_W.shape[0] - len(x)))
        feat = np.tanh(x @ self.fc_W + self.fc_b)
        return feat

# ── 语言嵌入模块 ──────────────────────────────────────────────
class LanguageEmbedder:
    """简化语言编码：关键词→嵌入向量"""
    def __init__(self, vocab_size=100, embed_dim=64, seed=42):
        rng = np.random.default_rng(seed + 2)
        self.embeddings = rng.standard_normal((vocab_size, embed_dim)) * 0.1
        self.vocab = {}
        self._idx = 0

    def encode(self, text):
        """简单词级编码：每个词→token id→嵌入平均"""
        words = text.lower().split()
        vectors = []
        for w in words:
            if w not in self.vocab:
                self.vocab[w] = self._idx % len(self.embeddings)
                self._idx += 1
            vectors.append(self.embeddings[self.vocab[w]])
        if vectors:
            return np.mean(vectors, axis=0)
        return np.zeros(self.embeddings.shape[1])

# ── 动作头（MLP）──────────────────────────────────────────────
class ActionHead:
    """MLP动作头：融合特征→动作输出"""
    def __init__(self, input_dim=128, hidden=64, action_dim=7, seed=42):
        rng = np.random.default_rng(seed + 3)
        self.W1 = rng.standard_normal((input_dim, hidden)) * 0.1
        self.b1 = np.zeros(hidden)
        self.W2 = rng.standard_normal((hidden, action_dim)) * 0.1
        self.b2 = np.zeros(action_dim)

    def forward(self, fused_feat):
        h = np.tanh(fused_feat @ self.W1 + self.b1)
        action = h @ self.W2 + self.b2
        return action

# ── 动作Tokenization方案对比 ──────────────────────────────────
class ActionTokenizer:
    """将连续动作离散化为token"""
    def __init__(self, action_dim=7, n_bins=256, action_range=(-1.0, 1.0)):
        self.action_dim = action_dim
        self.n_bins = n_bins
        self.lo, self.hi = action_range

    def encode(self, action):
        tokens = []
        for a in action:
            a = np.clip(a, self.lo, self.hi)
            token = int((a - self.lo) / (self.hi - self.lo) * (self.n_bins - 1))
            tokens.append(token)
        return tokens

    def decode(self, tokens):
        actions = []
        for t in tokens:
            a = self.lo + t / (self.n_bins - 1) * (self.hi - self.lo)
            actions.append(a)
        return np.array(actions)

# ── VLA模型 ───────────────────────────────────────────────────
class VLAModel:
    """简化VLA模型：图像+语言→动作"""
    def __init__(self, model_type="RT-1", seed=42):
        self.model_type = model_type
        self.visual_encoder = SimpleCNN(seed=seed)
        self.language_encoder = LanguageEmbedder(seed=seed)
        fuse_dim = 64 + 64
        self.action_head = ActionHead(input_dim=fuse_dim, action_dim=7, seed=seed)
        self.tokenizer = ActionTokenizer()

    def forward(self, image, instruction):
        vis_feat = self.visual_encoder.forward(image)
        lang_feat = self.language_encoder.encode(instruction)
        fused = np.concatenate([vis_feat, lang_feat])
        action = self.action_head.forward(fused)
        action_tokens = self.tokenizer.encode(action)
        return action, action_tokens

    def get_architecture_info(self):
        archs = {
            "RT-1": {
                "视觉编码器": "EfficientNet (专用CNN)",
                "语言编码器": "Film-conditioned Transformer",
                "动作头": "独立token分类头",
                "参数量": "~35M",
                "特点": "专用架构，效率高但不继承世界知识"
            },
            "RT-2": {
                "视觉编码器": "ViT (来自PaLI)",
                "语言编码器": "PaLM/PaLI (大语言模型)",
                "动作头": "动作token复用语言词表",
                "参数量": "~5B-55B",
                "特点": "继承LLM世界知识，支持链式推理"
            },
            "OpenVLA": {
                "视觉编码器": "DINOv2 + SigLIP双视觉编码器",
                "语言编码器": "Llama-2 7B",
                "动作头": "MLP动作头 (7维连续动作)",
                "参数量": "~7B",
                "特点": "开源可复现，支持LoRA高效微调"
            }
        }
        return archs.get(self.model_type, {})

# ── 运行VLA模型对比 ───────────────────────────────────────────
print("【1】VLA模型架构对比")
for model_name in ["RT-1", "RT-2", "OpenVLA"]:
    model = VLAModel(model_type=model_name)
    info = model.get_architecture_info()
    print(f"\n  ── {model_name} ──")
    for k, v in info.items():
        print(f"    {k}: {v}")

print("\n【2】VLA前向推理示例")
test_img = np.random.default_rng(100).uniform(0, 1, (32, 32, 3))
test_instruction = "pick up the red cup"

vla = VLAModel(model_type="OpenVLA")
action, tokens = vla.forward(test_img, test_instruction)
print(f"  输入: 图像(32x32x3) + 指令='{test_instruction}'")
print(f"  输出动作(7维): {np.round(action, 4)}")
print(f"  动作tokens: {tokens}")
decoded = vla.tokenizer.decode(tokens)
print(f"  token解码动作: {np.round(decoded, 4)}")
token_error = np.mean(np.abs(action - decoded))
print(f"  量化误差: {token_error:.6f}")

print("\n【3】动作Tokenization方案对比")
for n_bins in [16, 64, 256, 1024]:
    tok = ActionTokenizer(n_bins=n_bins)
    test_action = np.array([0.5, -0.3, 0.8, 0.1, -0.7, 0.4, -0.2])
    tokens = tok.encode(test_action)
    decoded = tok.decode(tokens)
    err = np.mean(np.abs(test_action - decoded))
    print(f"  bins={n_bins:5d}: token范围=[{min(tokens)},{max(tokens)}], 量化误差={err:.6f}")

print("""
关键总结：
  - RT-1：专用架构，效率高但缺乏世界知识，适合实时控制
  - RT-2：复用LLM词表做动作token，继承推理能力，但推理慢
  - OpenVLA：开源7B模型，双视觉编码器+Llama，支持LoRA微调
  - 动作tokenization：bins越多精度越高但词表越大，需要权衡
  - VLA核心：视觉编码+语言理解→特征融合→动作生成
""")
print("✅ 题7完成")


# ============================================================================
# 题8：模仿学习(IL)
# ============================================================================
# 知识点：
#   - 行为克隆(Behavior Cloning, BC)：监督学习，从专家数据直接学习策略
#   - DAgger (Dataset Aggregation)：迭代收集数据，解决分布偏移问题
#   - Compounding Error：BC的误差随时间累积，因训练分布≠执行分布
# ============================================================================

print("\n" + "─" * 80)
print("题8：模仿学习(IL)")
print("─" * 80)

# ── 简单1D导航环境 ────────────────────────────────────────────
class NavigationEnv:
    """1D导航：小车在轨道上移动，目标是到达目标点"""
    def __init__(self, seed=42):
        self.rng = np.random.default_rng(seed)
        self.reset()

    def reset(self):
        self.pos = self.rng.uniform(-1, 1)
        self.target = self.rng.uniform(2, 4)
        self.steps = 0
        return np.array([self.pos, self.target])

    def expert_action(self, state):
        diff = state[1] - state[0]
        return np.clip(diff * 2.0, -1, 1)

    def step(self, action):
        self.pos += action * 0.1
        self.steps += 1
        state = np.array([self.pos, self.target])
        reward = -abs(self.pos - self.target)
        done = abs(self.pos - self.target) < 0.1 or self.steps > 50
        return state, reward, done

# ── 策略网络（numpy MLP）──────────────────────────────────────
class MLP:
    def __init__(self, in_dim=2, hidden=32, out_dim=1, lr=0.01, seed=42):
        rng = np.random.default_rng(seed)
        self.W1 = rng.standard_normal((in_dim, hidden)) * 0.5
        self.b1 = np.zeros(hidden)
        self.W2 = rng.standard_normal((hidden, out_dim)) * 0.5
        self.b2 = np.zeros(out_dim)
        self.lr = lr

    def forward(self, x):
        self.x = x
        self.h = np.tanh(x @ self.W1 + self.b1)
        return (self.h @ self.W2 + self.b2).flatten()

    def train_step(self, x, y):
        pred = self.forward(x)
        err = pred - y
        dW2 = np.outer(self.h, err)
        db2 = err
        dh = err @ self.W2.T
        dW1 = np.outer(self.x, dh * (1 - self.h**2))
        db1 = dh * (1 - self.h**2)
        self.W1 -= self.lr * dW1
        self.b1 -= self.lr * db1
        self.W2 -= self.lr * dW2
        self.b2 -= self.lr * db2
        return np.mean(err**2)

# ── 1. 行为克隆(BC) ──────────────────────────────────────────
print("【1】行为克隆(BC)")
env = NavigationEnv(seed=42)

# 收集专家数据
expert_states, expert_actions = [], []
for _ in range(500):
    state = env.reset()
    done = False
    while not done:
        action = env.expert_action(state)
        expert_states.append(state.copy())
        expert_actions.append(action)
        state, _, done = env.step(action)

expert_states = np.array(expert_states)
expert_actions = np.array(expert_actions)
print(f"  专家数据量: {len(expert_states)} 条")

# 训练BC策略
bc_policy = MLP(lr=0.01, seed=42)
n_epochs = 50
for epoch in range(n_epochs):
    indices = np.random.permutation(len(expert_states))
    total_loss = 0
    for idx in indices:
        total_loss += bc_policy.train_step(expert_states[idx], expert_actions[idx])
    if (epoch + 1) % 10 == 0:
        print(f"  Epoch {epoch+1}: loss={total_loss/len(expert_states):.6f}")

# 评估BC策略
bc_rewards = []
for _ in range(50):
    state = env.reset()
    total_r = 0
    done = False
    while not done:
        action = bc_policy.forward(state)[0]
        state, r, done = env.step(action)
        total_r += r
    bc_rewards.append(total_r)
print(f"  BC策略平均奖励: {np.mean(bc_rewards):.2f} ± {np.std(bc_rewards):.2f}")

# ── 2. DAgger ────────────────────────────────────────────────
print("\n【2】DAgger算法")
dagger_policy = MLP(lr=0.01, seed=42)
for epoch in range(20):
    for idx in np.random.permutation(len(expert_states)):
        dagger_policy.train_step(expert_states[idx], expert_actions[idx])

dagger_states = list(expert_states)
dagger_actions = list(expert_actions)
dagger_rewards_history = []

for iteration in range(5):
    new_states = []
    for _ in range(50):
        state = env.reset()
        done = False
        while not done:
            action = dagger_policy.forward(state)[0]
            new_states.append(state.copy())
            state, _, done = env.step(action)

    for s in new_states:
        expert_a = env.expert_action(s)
        dagger_states.append(s)
        dagger_actions.append(expert_a)

    for epoch in range(10):
        for idx in np.random.permutation(len(dagger_states)):
            dagger_policy.train_step(dagger_states[idx], dagger_actions[idx])

    rewards = []
    for _ in range(30):
        state = env.reset()
        total_r = 0
        done = False
        while not done:
            action = dagger_policy.forward(state)[0]
            state, r, done = env.step(action)
            total_r += r
        rewards.append(total_r)
    dagger_rewards_history.append(np.mean(rewards))
    print(f"  DAgger Iter {iteration+1}: 数据量={len(dagger_states)}, 平均奖励={np.mean(rewards):.2f}")

# ── 3. Compounding Error分析 ─────────────────────────────────
print("\n【3】Compounding Error分析")
horizons = [10, 20, 30, 40, 50]
bc_errors = []
dagger_errors = []

for h in horizons:
    bc_errs = []
    dagger_errs = []
    for _ in range(50):
        env.reset()
        state = env.reset()
        for _ in range(h):
            a_bc = bc_policy.forward(state)[0]
            a_expert = env.expert_action(state)
            bc_errs.append(abs(a_bc - a_expert))
            a_dg = dagger_policy.forward(state)[0]
            dagger_errs.append(abs(a_dg - a_expert))
            state, _, _ = env.step(a_bc)
    bc_errors.append(np.mean(bc_errs))
    dagger_errors.append(np.mean(dagger_errs))

print(f"  {'Horizon':>8} | {'BC误差':>10} | {'DAgger误差':>12}")
print(f"  {'-'*8} | {'-'*10} | {'-'*12}")
for i, h in enumerate(horizons):
    print(f"  {h:8d} | {bc_errors[i]:10.4f} | {dagger_errors[i]:12.4f}")

print(f"\n  BC最终奖励: {np.mean(bc_rewards):.2f}")
print(f"  DAgger最终奖励: {dagger_rewards_history[-1]:.2f}")

print("""
关键总结：
  - BC受compounding error影响：小误差累积成大偏差，轨迹越长越严重
  - DAgger通过迭代收集策略自身分布下的数据，消除分布偏移
  - DAgger需要在线访问专家（可能是人类或慢速规划器）
  - 实际应用中BC+DAgger组合：BC预训练→DAgger在线微调
""")
print("✅ 题8完成")


# ============================================================================
# 题9：扩散策略(Diffusion Policy)
# ============================================================================
# 知识点：
#   - DDPM (Denoising Diffusion Probabilistic Models)：
#     前向：逐步加噪声 q(x_t|x_0) = N(√ᾱ_t·x_0, (1-ᾱ_t)·I)
#     反向：学习去噪 ε_θ(x_t, t) 预测噪声
#   - 条件生成：以观测为条件生成动作序列
#   - 多模态动作分布：扩散模型天然支持多模态
#   - 训练：预测噪声；推理：逐步去噪
# ============================================================================

print("\n" + "─" * 80)
print("题9：扩散策略(Diffusion Policy)")
print("─" * 80)

# ── DDPM核心 ──────────────────────────────────────────────────
class DiffusionPolicy:
    """简化扩散策略：条件动作生成"""
    def __init__(self, action_dim=2, n_timesteps=50, seed=42):
        self.action_dim = action_dim
        self.n_timesteps = n_timesteps
        self.rng = np.random.default_rng(seed)

        self.betas = np.linspace(1e-4, 0.02, n_timesteps)
        self.alphas = 1 - self.betas
        self.alpha_bars = np.cumprod(self.alphas)

        hidden = 64
        cond_dim = 4
        input_dim = action_dim + 1 + cond_dim
        rng = np.random.default_rng(seed)
        self.W1 = rng.standard_normal((input_dim, hidden)) * 0.1
        self.b1 = np.zeros(hidden)
        self.W2 = rng.standard_normal((hidden, hidden)) * 0.1
        self.b2 = np.zeros(hidden)
        self.W3 = rng.standard_normal((hidden, action_dim)) * 0.1
        self.b3 = np.zeros(action_dim)
        self.lr = 0.001

    def _denoise_net(self, x, t, cond):
        t_emb = np.array([t / self.n_timesteps])
        inp = np.concatenate([x, t_emb, cond])
        h1 = np.tanh(inp @ self.W1 + self.b1)
        h2 = np.tanh(h1 @ self.W2 + self.b2)
        return h2 @ self.W3 + self.b3

    def _denoise_grad(self, x, t, cond, target_noise):
        t_emb = np.array([t / self.n_timesteps])
        inp = np.concatenate([x, t_emb, cond])
        h1 = np.tanh(inp @ self.W1 + self.b1)
        h2 = np.tanh(h1 @ self.W2 + self.b2)
        pred = h2 @ self.W3 + self.b3
        err = pred - target_noise

        dW3 = np.outer(h2, err)
        db3 = err
        dh2 = err @ self.W3.T
        dh2_act = dh2 * (1 - h2**2)
        dW2 = np.outer(h1, dh2_act)
        db2 = dh2_act
        dh1 = dh2_act @ self.W2.T
        dh1_act = dh1 * (1 - h1**2)
        dW1 = np.outer(inp, dh1_act)
        db1 = dh1_act
        return {'W1': dW1, 'b1': db1, 'W2': dW2, 'b2': db2, 'W3': dW3, 'b3': db3}

    def forward_diffuse(self, x_0, t):
        noise = self.rng.standard_normal(x_0.shape)
        sqrt_ab = np.sqrt(self.alpha_bars[t])
        sqrt_1mab = np.sqrt(1 - self.alpha_bars[t])
        x_t = sqrt_ab * x_0 + sqrt_1mab * noise
        return x_t, noise

    def train_step(self, x_0, cond):
        t = self.rng.integers(0, self.n_timesteps)
        x_t, noise = self.forward_diffuse(x_0, t)
        grads = self._denoise_grad(x_t, t, cond, noise)
        loss = np.mean(noise**2) * 0.01
        for k in grads:
            setattr(self, k, getattr(self, k) - self.lr * grads[k])
        return loss

    def sample(self, cond, n_samples=1):
        samples = []
        for _ in range(n_samples):
            x = self.rng.standard_normal(self.action_dim)
            for t in reversed(range(self.n_timesteps)):
                pred_noise = self._denoise_net(x, t, cond)
                alpha = self.alphas[t]
                alpha_bar = self.alpha_bars[t]
                mean = (1 / np.sqrt(alpha)) * (x - (1 - alpha) / np.sqrt(1 - alpha_bar) * pred_noise)
                if t > 0:
                    x = mean + np.sqrt(self.betas[t]) * self.rng.standard_normal(self.action_dim)
                else:
                    x = mean
            samples.append(x.copy())
        return np.array(samples)

# ── 训练与多模态演示 ──────────────────────────────────────────
print("【1】DDPM前向扩散演示")
dp = DiffusionPolicy(action_dim=2, n_timesteps=50, seed=42)
x_0 = np.array([0.5, -0.3])
for t in [0, 10, 25, 49]:
    x_t, _ = dp.forward_diffuse(x_0, t)
    print(f"  t={t:3d}: x_t = {np.round(x_t, 4)}, ᾱ_t = {dp.alpha_bars[t]:.6f}")

print("\n【2】训练扩散策略（多模态动作分布）")
rng_data = np.random.default_rng(123)
train_data = []
conditions = []
for _ in range(500):
    cond = rng_data.uniform(-1, 1, 4)
    if rng_data.random() < 0.5:
        action = np.array([1.0, 0.5]) + rng_data.standard_normal(2) * 0.1
    else:
        action = np.array([-0.5, -1.0]) + rng_data.standard_normal(2) * 0.1
    train_data.append(action)
    conditions.append(cond)

train_data = np.array(train_data)
conditions = np.array(conditions)

losses = []
for epoch in range(100):
    epoch_loss = 0
    for i in range(len(train_data)):
        epoch_loss += dp.train_step(train_data[i], conditions[i])
    losses.append(epoch_loss / len(train_data))
    if (epoch + 1) % 25 == 0:
        print(f"  Epoch {epoch+1}: loss={losses[-1]:.6f}")

print("\n【3】条件动作生成（多模态）")
test_cond = rng_data.uniform(-1, 1, 4)
samples = dp.sample(test_cond, n_samples=100)
print(f"  生成 {len(samples)} 个动作样本")
print(f"  均值: {np.round(samples.mean(axis=0), 4)}")
print(f"  方差: {np.round(samples.var(axis=0), 4)}")
from sklearn.cluster import KMeans
kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
labels = kmeans.fit_predict(samples)
cluster_centers = kmeans.cluster_centers_
print(f"  K-Means聚类中心:")
for i, c in enumerate(cluster_centers):
    count = np.sum(labels == i)
    print(f"    模式{i+1}: 中心={np.round(c, 4)}, 样本数={count}")

print("""
关键总结：
  - 前向扩散：x_t = √ᾱ_t·x_0 + √(1-ᾱ_t)·ε，逐步加噪
  - 反向去噪：学习 ε_θ(x_t, t) 预测噪声，逐步去噪
  - 条件生成：将观测作为条件输入去噪网络
  - 多模态：扩散模型天然支持多模态分布，这是相比BC的核心优势
  - 扩散策略：用未来动作序列替代单步动作，提升时序一致性
""")
print("✅ 题9完成")


# ============================================================================
# 题10：OpenVLA实战模拟
# ============================================================================
# 知识点：
#   - OpenVLA推理流程：图像+语言→动作token→解码为关节角度
#   - LoRA微调：低秩适配器，只训练少量参数
#   - 推理延迟分析：模型大小 vs 延迟 vs 精度
#   - 动作空间映射：归一化动作→实际关节角度
# ============================================================================

print("\n" + "─" * 80)
print("题10：OpenVLA实战模拟")
print("─" * 80)

# ── OpenVLA模型配置 ──────────────────────────────────────────
class OpenVLAConfig:
    """模拟OpenVLA模型配置"""
    def __init__(self):
        self.model_name = "openvla/openvla-7b"
        self.vision_backbone = "DINOv2 + SigLIP"
        self.language_backbone = "Llama-2 7B"
        self.action_dim = 7  # 7维动作: [x, y, z, rx, ry, rz, gripper]
        self.action_token_bins = 256
        self.image_size = (224, 224, 3)
        self.max_seq_len = 1024
        self.lora_r = 16  # LoRA秩
        self.lora_alpha = 32
        self.lora_target = ["q_proj", "v_proj"]

class OpenVLASimulator:
    """OpenVLA推理流程模拟器"""
    def __init__(self, config=None):
        self.config = config or OpenVLAConfig()
        # 初始化模拟权重
        rng = np.random.default_rng(42)
        self.action_head_W = rng.standard_normal((128, self.config.action_dim)) * 0.1
        self.action_head_b = np.zeros(self.config.action_dim)
        self.visual_proj = rng.standard_normal((10, 128)) * 0.1
        self.lang_proj = rng.standard_normal((64, 128)) * 0.1
        # LoRA参数（未训练前为0）
        self.lora_A = np.zeros((self.config.lora_r, 128))
        self.lora_B = np.zeros((128, self.config.lora_r))
        # 动作归一化参数
        self.action_mean = np.array([0.0, 0.0, 0.3, 0.0, 0.0, 0.0, 0.0])
        self.action_std = np.array([0.2, 0.2, 0.1, 0.3, 0.3, 0.3, 0.5])

    def encode_image(self, image):
        """模拟视觉编码器"""
        # 简化：用图像统计量作为特征
        feat = np.concatenate([
            image.mean(axis=(0, 1)),
            image.std(axis=(0, 1)),
            np.array([image[:112, :112].mean(), image[112:, :112].mean(),
                      image[:112, 112:].mean(), image[112:, 112:].mean()])
        ])
        return feat @ self.visual_proj

    def encode_language(self, instruction):
        """模拟语言编码器"""
        rng = np.random.default_rng(hash(instruction) % 2**31)
        return rng.standard_normal(64) @ self.lang_proj

    def predict_action_tokens(self, image, instruction):
        """推理：图像+指令→动作tokens"""
        vis_feat = self.encode_image(image)
        lang_feat = self.encode_language(instruction)
        fused = vis_feat + lang_feat
        # 应用LoRA（如果已微调）
        lora_out = fused @ self.lora_B @ self.lora_A
        fused = fused + lora_out
        # 动作头
        action_logits = fused @ self.action_head_W + self.action_head_b
        # Token化
        tokens = []
        for logit in action_logits:
            token = int(np.clip((logit + 1) / 2 * (self.config.action_token_bins - 1),
                                0, self.config.action_token_bins - 1))
            tokens.append(token)
        return tokens, action_logits

    def decode_tokens_to_action(self, tokens):
        """动作token→归一化动作"""
        actions = np.array([
            t / (self.config.action_token_bins - 1) * 2 - 1 for t in tokens
        ])
        return actions

    def map_to_joint_angles(self, normalized_actions):
        """归一化动作→实际关节角度"""
        return normalized_actions * self.action_std + self.action_mean

    def lora_fine_tune(self, n_steps=100, lr=0.01):
        """模拟LoRA微调"""
        rng = np.random.default_rng(99)
        losses = []
        for step in range(n_steps):
            # 随机目标
            target = rng.standard_normal(7)
            # 前向
            dummy_feat = rng.standard_normal(128)
            lora_out = dummy_feat @ self.lora_B @ self.lora_A
            pred = dummy_feat + lora_out
            pred_action = pred @ self.action_head_W + self.action_head_b
            # 损失
            loss = np.mean((pred_action - target)**2)
            losses.append(loss)
            # 反向传播更新LoRA参数（简化梯度）
            grad = (pred_action - target) @ self.action_head_W.T
            grad_lora_B = np.outer(grad, self.lora_A @ dummy_feat) * 0.001
            grad_lora_A = np.outer(self.lora_B.T @ grad, dummy_feat) * 0.001
            self.lora_B -= lr * grad_lora_B
            self.lora_A -= lr * grad_lora_A
        return losses

# ── 运行OpenVLA模拟 ──────────────────────────────────────────
print("【1】模型配置")
config = OpenVLAConfig()
print(f"  模型: {config.model_name}")
print(f"  视觉骨干: {config.vision_backbone}")
print(f"  语言骨干: {config.language_backbone}")
print(f"  动作维度: {config.action_dim}")
print(f"  动作token bins: {config.action_token_bins}")
print(f"  LoRA: r={config.lora_r}, alpha={config.lora_alpha}")

print("\n【2】推理流程演示")
model = OpenVLASimulator(config)
# 模拟图像
test_image = np.random.default_rng(100).uniform(0, 1, (224, 224, 3))
instruction = "pick up the red cup"

tokens, logits = model.predict_action_tokens(test_image, instruction)
normalized_actions = model.decode_tokens_to_action(tokens)
joint_angles = model.map_to_joint_angles(normalized_actions)

print(f"  输入: 图像(224x224x3) + 指令='{instruction}'")
print(f"  动作logits: {np.round(logits, 4)}")
print(f"  动作tokens: {tokens}")
print(f"  归一化动作: {np.round(normalized_actions, 4)}")
print(f"  关节角度: {np.round(joint_angles, 4)}")
print(f"  动作空间: [Δx, Δy, Δz, Δrx, Δry, Δrz, gripper]")

print("\n【3】LoRA微调模拟")
model2 = OpenVLASimulator(config)
losses = model2.lora_fine_tune(n_steps=200, lr=0.01)
print(f"  初始loss: {losses[0]:.4f}")
print(f"  最终loss: {losses[-1]:.4f}")
print(f"  LoRA参数量: r×2×128 = {config.lora_r * 2 * 128}")
print(f"  全量微调参数量: 7B → LoRA仅 {config.lora_r * 2 * 128 / 7e9 * 100:.4f}%")

print("\n【4】推理延迟分析")
import time
latencies = []
for _ in range(20):
    t0 = time.time()
    model.predict_action_tokens(test_image, instruction)
    latencies.append((time.time() - t0) * 1000)

print(f"  模拟推理延迟: {np.mean(latencies):.2f}ms (±{np.std(latencies):.2f}ms)")
print(f"  真实OpenVLA-7B延迟参考: ~0.5-2s (取决于硬件)")
print(f"  RT-1延迟参考: ~100ms (专用轻量架构)")
print(f"  控制频率需求: ≥10Hz (即<100ms)")

print("\n【5】动作空间映射验证")
test_actions = np.array([
    [-1, -1, -1, -1, -1, -1, -1],  # 最小动作
    [ 0,  0,  0,  0,  0,  0,  0],  # 零动作
    [ 1,  1,  1,  1,  1,  1,  1],  # 最大动作
])
for a in test_actions:
    joints = model.map_to_joint_angles(a)
    print(f"  归一化{a} → 关节{np.round(joints, 3)}")

print("""
关键总结：
  - OpenVLA推理流程：图像编码+语言编码→融合→动作头→token→解码→关节角度
  - LoRA微调：冻结骨干，只训练低秩矩阵A和B，参数量减少99%+
  - 推理延迟是VLA落地的关键挑战，7B模型难以实时控制
  - 动作空间映射：归一化[-1,1] → 关节范围，需要统计训练数据
  - 实际部署需要量化/蒸馏等加速手段
""")
print("✅ 题10完成")


# ============================================================================
# 题11：世界模型(World Model)
# ============================================================================
# 知识点：
#   - DreamerV3：在潜在空间中学习世界模型+actor-critic
#   - 潜在空间动态模型：RSSM，预测下一时刻潜在状态
#   - 想象rollout：在世界模型中"想象"未来轨迹
#   - 奖励预测 & 价值估计：从潜在状态预测奖励和价值
#   - 世界模型 vs VLA协同：世界模型提供想象训练数据
# ============================================================================

print("\n" + "─" * 80)
print("题11：世界模型(World Model)")
print("─" * 80)

# ── 简化潜在空间动态模型 ──────────────────────────────────────
class LatentDynamicsModel:
    """简化潜在空间动态模型（模拟RSSM核心概念）"""
    def __init__(self, latent_dim=16, action_dim=2, seed=42):
        rng = np.random.default_rng(seed)
        self.latent_dim = latent_dim
        self.action_dim = action_dim
        # 状态转移矩阵 W: (latent+action) → latent
        self.transition_W = rng.standard_normal((latent_dim + action_dim, latent_dim)) * 0.1
        self.transition_b = np.zeros(latent_dim)
        # 奖励预测头
        self.reward_W = rng.standard_normal((latent_dim, 1)) * 0.1
        self.reward_b = np.zeros(1)
        # 价值预测头
        self.value_W = rng.standard_normal((latent_dim, 1)) * 0.1
        self.value_b = np.zeros(1)
        self.lr = 0.01

    def step(self, latent, action):
        """潜在状态转移"""
        inp = np.concatenate([latent, action])
        next_latent = np.tanh(inp @ self.transition_W + self.transition_b)
        return next_latent

    def predict_reward(self, latent):
        return (latent @ self.reward_W + self.reward_b)[0]

    def predict_value(self, latent):
        return (latent @ self.value_W + self.value_b)[0]

    def train_transition(self, latent, action, target_next_latent, target_reward):
        """训练动态模型"""
        inp = np.concatenate([latent, action])
        pred_next = np.tanh(inp @ self.transition_W + self.transition_b)
        pred_reward = (pred_next @ self.reward_W + self.reward_b)[0]

        err_latent = pred_next - target_next_latent
        err_reward = pred_reward - target_reward

        # 状态转移梯度 (latent_dim+action_dim, latent_dim)
        d_tanh = (1 - pred_next**2)
        grad_W = np.outer(inp, err_latent * d_tanh)
        self.transition_W -= self.lr * grad_W
        self.transition_b -= self.lr * (err_latent * d_tanh)
        # 奖励头梯度 (latent_dim, 1)
        self.reward_W -= self.lr * np.outer(pred_next, [err_reward])
        self.reward_b -= self.lr * np.array([err_reward])
        return np.mean(err_latent**2) + err_reward**2

# ── 想象rollout ──────────────────────────────────────────────
def imagine_rollout(world_model, init_latent, policy_fn, horizon=10):
    """在世界模型中想象未来轨迹"""
    latent = init_latent.copy()
    trajectory = {
        'latents': [latent.copy()],
        'actions': [],
        'rewards': [],
        'values': []
    }
    for h in range(horizon):
        action = policy_fn(latent)
        reward = world_model.predict_reward(latent)
        value = world_model.predict_value(latent)
        trajectory['actions'].append(action)
        trajectory['rewards'].append(reward)
        trajectory['values'].append(value)
        latent = world_model.step(latent, action)
        trajectory['latents'].append(latent.copy())
    # 最后一步的价值
    trajectory['values'].append(world_model.predict_value(latent))
    return trajectory

# ── 简化Actor-Critic（基于想象的策略优化）──────────────────────
class ImagineActorCritic:
    """在想象空间中训练actor-critic"""
    def __init__(self, latent_dim=16, action_dim=2, seed=42):
        rng = np.random.default_rng(seed + 5)
        self.action_dim = action_dim
        # Actor: latent → action
        self.actor_W = rng.standard_normal((latent_dim, action_dim)) * 0.1
        self.actor_b = np.zeros(action_dim)
        # Critic: latent → value
        self.critic_W = rng.standard_normal((latent_dim, 1)) * 0.1
        self.critic_b = np.zeros(1)
        self.lr = 0.01

    def get_action(self, latent):
        return np.tanh(latent @ self.actor_W + self.actor_b)

    def get_value(self, latent):
        return (latent @ self.critic_W + self.critic_b)[0]

    def update(self, latents, rewards, values, gamma=0.99):
        """基于想象轨迹更新"""
        for i, s in enumerate(latents):
            action = self.get_action(s)
            v = self.get_value(s)
            # 计算回报
            returns = sum(gamma**k * rewards[min(i + k, len(rewards) - 1)]
                          for k in range(min(5, len(rewards) - i)))
            advantage = returns - v
            # 简化更新
            self.actor_W += self.lr * np.outer(s, action * advantage) * 0.01
            self.critic_W += self.lr * np.outer(s, np.array([advantage])) * 0.01

# ── 运行世界模型 ──────────────────────────────────────────────
print("【1】潜在空间动态模型训练")
world_model = LatentDynamicsModel(latent_dim=16, action_dim=2, seed=42)

# 生成训练数据（模拟环境轨迹）
rng_data = np.random.default_rng(123)
real_trajectories = []
for _ in range(200):
    latent = rng_data.standard_normal(16) * 0.5
    action = rng_data.uniform(-1, 1, 2)
    # 简化"真实"状态转移
    true_next = np.tanh(latent * 0.9 + action @ np.random.default_rng(456).standard_normal((2, 16)) * 0.1)
    true_reward = float(np.sum(latent[:4]) * 0.1 + rng_data.standard_normal() * 0.05)
    real_trajectories.append((latent, action, true_next, true_reward))

# 训练
for epoch in range(50):
    total_loss = 0
    for latent, action, next_latent, reward in real_trajectories:
        loss = world_model.train_transition(latent, action, next_latent, reward)
        total_loss += loss
    if (epoch + 1) % 10 == 0:
        print(f"  Epoch {epoch+1}: loss={total_loss/len(real_trajectories):.6f}")

print("\n【2】想象Rollout")
# 简单随机策略
def random_policy(latent):
    return np.random.default_rng().uniform(-1, 1, 2)

init_latent = rng_data.standard_normal(16) * 0.5
rollout = imagine_rollout(world_model, init_latent, random_policy, horizon=10)
print(f"  想象长度: {len(rollout['rewards'])}")
print(f"  累积想象奖励: {sum(rollout['rewards']):.4f}")
print(f"  想象奖励序列: {np.round(rollout['rewards'], 4)}")
print(f"  价值估计序列: {np.round(rollout['values'], 4)}")

print("\n【3】想象空间Actor-Critic训练")
ac = ImagineActorCritic(latent_dim=16, action_dim=2, seed=42)
for ep in range(100):
    init_latent = rng_data.standard_normal(16) * 0.5
    rollout = imagine_rollout(world_model, init_latent, ac.get_action, horizon=8)
    ac.update(rollout['latents'][:-1], rollout['rewards'], rollout['values'])
    if (ep + 1) % 25 == 0:
        total_r = sum(rollout['rewards'])
        print(f"  Episode {ep+1}: 想象累积奖励={total_r:.4f}")

print("\n【4】世界模型 vs VLA协同策略")
print("  ┌─────────────┬────────────────────────┬────────────────────────┐")
print("  │     维度    │       世界模型         │         VLA            │")
print("  ├─────────────┼────────────────────────┼────────────────────────┤")
print("  │  训练数据   │  自监督（交互数据）     │  监督（专家演示）      │")
print("  │  数据效率   │  高（想象rollout）      │  低（需大量演示）      │")
print("  │  泛化能力   │  可想象未见情况          │  受限于训练分布        │")
print("  │  推理速度   │  快（小模型）            │  慢（大VLM）           │")
print("  │  可解释性   │  潜在状态可分析          │  黑盒                   │")
print("  └─────────────┴────────────────────────┴────────────────────────┘")
print("  协同方案：世界模型提供想象数据→VLA微调；VLA提供高质量交互数据→世界模型更新")

print("""
关键总结：
  - DreamerV3核心：在潜在空间学习动态模型，用想象rollout训练策略
  - RSSM：循环状态空间模型，同时建模确定性+随机性
  - 想象rollout：无需真实环境交互即可训练，数据效率极高
  - 世界模型vs VLA：前者数据效率高但可能不准，后者直接但数据需求大
  - 趋势：世界模型提供"想象力"，VLA提供"执行力"，两者互补
""")
print("✅ 题11完成")


# ============================================================================
# 题12：Sim-to-Real迁移
# ============================================================================
# 知识点：
#   - 域随机化(Domain Randomization)：训练时随机化仿真参数
#   - 系统辨识(System Identification)：从真实数据估计物理参数
#   - 渐进式迁移：逐步从仿真过渡到真实环境
#   - Real2Sim2Real闭环：用真实数据校准仿真→训练→再部署
#   - 迁移成功度量：sim gap、任务成功率
# ============================================================================

print("\n" + "─" * 80)
print("题12：Sim-to-Real迁移")
print("─" * 80)

# ── 域随机化 ──────────────────────────────────────────────────
class DomainRandomizer:
    """物理+视觉域随机化"""
    def __init__(self, seed=42):
        self.rng = np.random.default_rng(seed)

        # 物理参数范围
        self.physics_ranges = {
            'gravity': (7.0, 12.0),
            'friction': (0.3, 1.2),
            'mass': (0.5, 2.0),
            'restitution': (0.1, 0.8),
            'damping': (0.01, 0.5),
        }
        # 视觉参数范围
        self.visual_ranges = {
            'brightness': (0.5, 1.5),
            'contrast': (0.7, 1.3),
            'hue_shift': (-0.1, 0.1),
            'noise_std': (0.0, 0.1),
        }

    def randomize_physics(self):
        params = {}
        for key, (lo, hi) in self.physics_ranges.items():
            params[key] = self.rng.uniform(lo, hi)
        return params

    def randomize_visual(self, image):
        """对图像应用视觉随机化"""
        img = image.copy()
        # 亮度
        brightness = self.rng.uniform(*self.visual_ranges['brightness'])
        img = img * brightness
        # 对比度
        contrast = self.rng.uniform(*self.visual_ranges['contrast'])
        mean = img.mean()
        img = (img - mean) * contrast + mean
        # 噪声
        noise_std = self.rng.uniform(*self.visual_ranges['noise_std'])
        img = img + self.rng.standard_normal(img.shape) * noise_std
        return np.clip(img, 0, 1)

# ── 系统辨识 ──────────────────────────────────────────────────
class SystemIdentifier:
    """从真实数据估计物理参数"""
    def __init__(self):
        self.estimated_params = {}

    def estimate_gravity(self, free_fall_data):
        """从自由落体数据估计重力"""
        # d = 0.5 * g * t^2 → g = 2d / t^2
        times, distances = free_fall_data
        g_estimates = 2 * np.array(distances) / (np.array(times)**2 + 1e-8)
        return np.median(g_estimates)

    def estimate_friction(self, slide_data):
        """从滑动数据估计摩擦系数"""
        # a = μ * g → μ = a / g
        accelerations, g_true = slide_data
        mu_estimates = np.array(accelerations) / (g_true + 1e-8)
        return np.median(mu_estimates)

    def estimate_mass(self, force_accel_data):
        """从力-加速度数据估计质量"""
        # F = m*a → m = F/a
        forces, accelerations = force_accel_data
        m_estimates = np.array(forces) / (np.array(accelerations) + 1e-8)
        return np.median(m_estimates)

# ── 渐进式迁移策略 ────────────────────────────────────────────
class ProgressiveTransfer:
    """渐进式Sim-to-Real迁移"""
    def __init__(self):
        self.stages = [
            {'name': '纯仿真', 'real_ratio': 0.0, 'randomization': 1.0},
            {'name': '仿真为主+少量真实', 'real_ratio': 0.1, 'randomization': 0.8},
            {'name': '混合训练', 'real_ratio': 0.3, 'randomization': 0.5},
            {'name': '真实为主+仿真辅助', 'real_ratio': 0.7, 'randomization': 0.2},
            {'name': '纯真实微调', 'real_ratio': 1.0, 'randomization': 0.0},
        ]

    def get_stage(self, step, total_steps):
        progress = step / total_steps
        idx = min(int(progress * len(self.stages)), len(self.stages) - 1)
        return self.stages[idx]

# ── Real2Sim2Real闭环 ─────────────────────────────────────────
class Real2Sim2Real:
    """Real2Sim2Real闭环模拟"""
    def __init__(self, seed=42):
        self.rng = np.random.default_rng(seed)
        self.true_params = {'gravity': 9.81, 'friction': 0.5, 'mass': 1.0}
        self.sim_params = {'gravity': 9.81, 'friction': 0.5, 'mass': 1.0}  # 初始猜测

    def real_env_step(self, action):
        """真实环境步骤（带噪声）"""
        g = self.true_params['gravity']
        noise = self.rng.standard_normal() * 0.05
        return action * g + noise

    def collect_real_data(self, n=50):
        """收集真实环境数据"""
        data = []
        for _ in range(n):
            action = self.rng.uniform(0, 1)
            result = self.real_env_step(action)
            data.append((action, result))
        return data

    def calibrate_sim(self, real_data):
        """用真实数据校准仿真参数"""
        actions = np.array([d[0] for d in real_data])
        results = np.array([d[1] for d in real_data])
        # 估计重力: result ≈ action * g
        g_est = np.median(results / (actions + 1e-8))
        self.sim_params['gravity'] = g_est
        return g_est

    def sim_env_step(self, action):
        """仿真环境步骤"""
        g = self.sim_params['gravity']
        return action * g

# ── 运行Sim-to-Real演示 ──────────────────────────────────────
print("【1】域随机化")
dr = DomainRandomizer(seed=42)
for _ in range(3):
    phys = dr.randomize_physics()
    print(f"  物理参数: gravity={phys['gravity']:.2f}, friction={phys['friction']:.2f}, "
          f"mass={phys['mass']:.2f}, restitution={phys['restitution']:.2f}")

test_img = np.random.default_rng(50).uniform(0.3, 0.7, (32, 32, 3))
augmented = dr.randomize_visual(test_img)
print(f"  视觉随机化: 原始均值={test_img.mean():.3f} → 增强后均值={augmented.mean():.3f}")

print("\n【2】系统辨识")
si = SystemIdentifier()
# 模拟自由落体数据
t_data = np.linspace(0.1, 1.0, 10)
d_data = 0.5 * 9.81 * t_data**2 + np.random.default_rng(42).standard_normal(10) * 0.02
g_est = si.estimate_gravity((t_data, d_data))
print(f"  重力估计: {g_est:.4f} (真实: 9.81)")

# 摩擦系数估计
a_data = 0.5 * 9.81 + np.random.default_rng(42).standard_normal(10) * 0.1
mu_est = si.estimate_friction((a_data, 9.81))
print(f"  摩擦系数估计: {mu_est:.4f} (真实: 0.5)")

# 质量估计
f_data = np.array([5, 10, 15, 20, 25])
a_data2 = f_data / 1.0 + np.random.default_rng(42).standard_normal(5) * 0.1
m_est = si.estimate_mass((f_data, a_data2))
print(f"  质量估计: {m_est:.4f} (真实: 1.0)")

print("\n【3】渐进式迁移策略")
pt = ProgressiveTransfer()
total_steps = 1000
for step in [0, 200, 400, 600, 800, 999]:
    stage = pt.get_stage(step, total_steps)
    print(f"  Step {step:4d}: {stage['name']} (真实数据比例={stage['real_ratio']:.0%}, "
          f"随机化强度={stage['randomization']:.0%})")

print("\n【4】Real2Sim2Real闭环")
r2s2r = Real2Sim2Real(seed=42)
print(f"  初始仿真参数: gravity={r2s2r.sim_params['gravity']:.4f}")
# Round 1: 收集真实数据→校准仿真
real_data = r2s2r.collect_real_data(100)
g_calibrated = r2s2r.calibrate_sim(real_data)
print(f"  校准后仿真参数: gravity={g_calibrated:.4f} (真实: {r2s2r.true_params['gravity']})")
# 验证sim gap
test_actions = np.linspace(0.1, 1.0, 10)
sim_results = [r2s2r.sim_env_step(a) for a in test_actions]
real_results = [r2s2r.real_env_step(a) for a in test_actions]
sim_gap = np.mean(np.abs(np.array(sim_results) - np.array(real_results)))
print(f"  Sim-Real Gap: {sim_gap:.4f} (校准前应更大)")

# Round 2: 再收集→再校准
real_data2 = r2s2r.collect_real_data(200)
r2s2r.calibrate_sim(real_data2)
sim_results2 = [r2s2r.sim_env_step(a) for a in test_actions]
sim_gap2 = np.mean(np.abs(np.array(sim_results2) - np.array(real_results)))
print(f"  二次校准Sim-Real Gap: {sim_gap2:.4f}")
print(f"  迁移成功度量: sim_gap减少 {((sim_gap - sim_gap2) / sim_gap * 100):.1f}%")

print("""
关键总结：
  - 域随机化：通过在训练时随机化物理/视觉参数，让策略对参数变化鲁棒
  - 系统辨识：从真实数据反推物理参数，缩小sim-real gap
  - 渐进式迁移：逐步增加真实数据比例，降低随机化强度
  - Real2Sim2Real：收集真实数据→校准仿真→训练→部署→再收集，闭环优化
  - 成功度量：sim gap越小、任务成功率越高，迁移越成功
""")
print("✅ 题12完成")


# ============================================================================
# 题13：导航与建图(SLAM)
# ============================================================================
# 知识点：
#   - 里程计仿真：根据运动模型推算位姿
#   - ICP (Iterative Closest Point)：扫描匹配，对齐两组点云
#   - 栅格地图构建：将激光扫描投影到占据栅格
#   - 前端跟踪+后端优化：前端实时跟踪，后端全局优化
#   - 路径规划集成：在构建的地图上规划路径
# ============================================================================

print("\n" + "─" * 80)
print("题13：导航与建图(SLAM)")
print("─" * 80)

# ── 里程计仿真 ────────────────────────────────────────────────
class Odometry:
    """差速驱动机器人里程计"""
    def __init__(self, noise_std=0.01):
        self.pose = np.array([0.0, 0.0, 0.0])  # [x, y, theta]
        self.noise_std = noise_std

    def update(self, v, omega, dt):
        """根据线速度v和角速度omega更新位姿"""
        theta = self.pose[2]
        noise_v = np.random.randn() * self.noise_std
        noise_omega = np.random.randn() * self.noise_std
        v_n = v + noise_v
        omega_n = omega + noise_omega

        if abs(omega_n) < 1e-6:
            self.pose[0] += v_n * np.cos(theta) * dt
            self.pose[1] += v_n * np.sin(theta) * dt
        else:
            self.pose[0] += (v_n / omega_n) * (np.sin(theta + omega_n * dt) - np.sin(theta))
            self.pose[1] -= (v_n / omega_n) * (np.cos(theta + omega_n * dt) - np.cos(theta))
        self.pose[2] += omega_n * dt
        self.pose[2] = (self.pose[2] + np.pi) % (2 * np.pi) - np.pi

# ── ICP扫描匹配 ──────────────────────────────────────────────
def icp_2d(source, target, max_iter=50, tol=1e-4):
    """2D ICP算法：对齐source到target"""
    src = source.copy()
    R = np.eye(2)
    t = np.zeros(2)
    prev_error = float('inf')

    for iteration in range(max_iter):
        # 找最近邻
        correspondences = []
        for i, p in enumerate(src):
            dists = np.sum((target - p)**2, axis=1)
            j = np.argmin(dists)
            correspondences.append((i, j))

        # 计算质心
        src_pts = np.array([src[i] for i, _ in correspondences])
        tgt_pts = np.array([target[j] for _, j in correspondences])

        src_centroid = src_pts.mean(axis=0)
        tgt_centroid = tgt_pts.mean(axis=0)

        # 去质心
        src_centered = src_pts - src_centroid
        tgt_centered = tgt_pts - tgt_centroid

        # SVD求旋转
        H = src_centered.T @ tgt_centered
        U, S, Vt = np.linalg.svd(H)
        R_iter = Vt.T @ U.T
        t_iter = tgt_centroid - R_iter @ src_centroid

        # 应用变换
        src = (R_iter @ src.T).T + t_iter
        R = R_iter @ R
        t = R_iter @ t + t_iter

        # 计算误差
        mean_error = np.mean([np.sum((src[i] - target[j])**2)
                              for i, j in correspondences])
        if abs(prev_error - mean_error) < tol:
            break
        prev_error = mean_error

    return R, t, prev_error, iteration + 1

# ── 栅格地图 ──────────────────────────────────────────────────
class GridMap:
    """占据栅格地图"""
    def __init__(self, size=200, resolution=0.1):
        self.size = size
        self.resolution = resolution
        self.grid = np.zeros((size, size))  # log-odds
        self.log_odds_occ = 0.85
        self.log_odds_free = -0.4

    def update(self, pose, scan_points):
        """根据激光扫描更新栅格地图"""
        gx = int(pose[0] / self.resolution + self.size / 2)
        gy = int(pose[1] / self.resolution + self.size / 2)

        for point in scan_points:
            # 障碍物位置
            ox = int((pose[0] + point[0]) / self.resolution + self.size / 2)
            oy = int((pose[1] + point[1]) / self.resolution + self.size / 2)

            # 标记空闲区域（射线追踪）
            steps = max(abs(ox - gx), abs(oy - gy), 1)
            for s in range(steps):
                ix = int(gx + (ox - gx) * s / steps)
                iy = int(gy + (oy - gy) * s / steps)
                if 0 <= ix < self.size and 0 <= iy < self.size:
                    self.grid[ix, iy] += self.log_odds_free

            # 标记占据
            if 0 <= ox < self.size and 0 <= oy < self.size:
                self.grid[ox, oy] += self.log_odds_occ

    def get_occupancy(self):
        """转换为概率图"""
        prob = 1 - 1 / (1 + np.exp(self.grid))
        return prob

# ── 后端优化（简化g2o）────────────────────────────────────────
def simple_pose_graph_optimization(poses, constraints, n_iter=10):
    """简化的位姿图优化（梯度下降）"""
    poses = np.array(poses, dtype=float)
    for iteration in range(n_iter):
        total_residual = 0
        for i, j, rel_pose, info in constraints:
            # 残差 = predicted - measured
            diff = poses[j] - poses[i]
            predicted = rel_pose
            residual = diff - predicted
            total_residual += np.sum(residual**2 * info)
            # 梯度下降
            poses[j] -= 0.01 * residual * info
    return poses, total_residual

# ── 运行SLAM演示 ─────────────────────────────────────────────
print("【1】里程计仿真")
np.random.seed(42)
odom = Odometry(noise_std=0.02)
true_pose = np.array([0.0, 0.0, 0.0])
odom_log = [odom.pose.copy()]
true_log = [true_pose.copy()]

for t in range(100):
    v = 0.5  # 线速度
    omega = 0.05 * np.sin(t * 0.1)  # 角速度
    # 真实位姿
    theta = true_pose[2]
    true_pose[0] += v * np.cos(theta) * 0.1
    true_pose[1] += v * np.sin(theta) * 0.1
    true_pose[2] += omega * 0.1
    # 里程计
    odom.update(v, omega, 0.1)
    odom_log.append(odom.pose.copy())
    true_log.append(true_pose.copy())

odom_log = np.array(odom_log)
true_log = np.array(true_log)
final_err = np.linalg.norm(true_log[-1][:2] - odom_log[-1][:2])
print(f"  里程计最终位置: {np.round(odom_log[-1][:2], 3)}")
print(f"  真实最终位置: {np.round(true_log[-1][:2], 3)}")
print(f"  里程计漂移: {final_err:.3f}m")

print("\n【2】ICP扫描匹配")
# 生成两组点云（target是source旋转平移后的版本）
rng = np.random.default_rng(42)
source_points = rng.uniform(-2, 2, (30, 2))
true_R = np.array([[np.cos(0.3), -np.sin(0.3)], [np.sin(0.3), np.cos(0.3)]])
true_t = np.array([0.5, -0.3])
target_points = (true_R @ source_points.T).T + true_t

R_est, t_est, error, iters = icp_2d(source_points, target_points)
print(f"  ICP迭代次数: {iters}")
print(f"  估计旋转角: {np.arctan2(R_est[1, 0], R_est[0, 0]):.4f} rad (真实: 0.3)")
print(f"  估计平移: {np.round(t_est, 4)} (真实: {true_t})")
print(f"  匹配误差: {error:.6f}")

print("\n【3】栅格地图构建")
grid_map = GridMap(size=100, resolution=0.2)
# 模拟激光扫描
for step in range(0, 100, 10):
    pose = odom_log[step]
    # 模拟360度扫描
    n_rays = 36
    scan = []
    for angle in np.linspace(0, 2 * np.pi, n_rays):
        r = 2.0 + np.random.randn() * 0.2  # 测量距离
        scan.append([r * np.cos(angle), r * np.sin(angle)])
    grid_map.update(pose, scan)

occ = grid_map.get_occupancy()
occupied = np.sum(occ > 0.65)
free = np.sum(occ < 0.35)
print(f"  栅格地图: {grid_map.size}x{grid_map.size}, 分辨率={grid_map.resolution}m")
print(f"  占据栅格数: {occupied}, 空闲栅格数: {free}")
print(f"  地图覆盖率: {(occupied + free) / (grid_map.size**2) * 100:.1f}%")

print("\n【4】后端位姿图优化")
# 简化的位姿图：5个位姿节点，4个约束
poses = [[0, 0], [1, 0], [2, 0.1], [3, 0.2], [4, 0.5]]
constraints = [
    (0, 1, np.array([1, 0]), 1.0),
    (1, 2, np.array([1, 0.1]), 1.0),
    (2, 3, np.array([1, 0.1]), 1.0),
    (3, 4, np.array([1, 0.3]), 1.0),
    (0, 4, np.array([4, 0.5]), 0.5),  # 回环约束
]
optimized, residual = simple_pose_graph_optimization(poses, constraints, n_iter=20)
print(f"  优化前位姿: {np.round(np.array(poses), 3).tolist()}")
print(f"  优化后位姿: {np.round(optimized, 3).tolist()}")
print(f"  最终残差: {residual:.4f}")

print("\n【5】路径规划集成（在栅格地图上A*）")
# 在栅格地图上做简单路径规划
grid_occ = (occ > 0.5).astype(int)
# 简化：找到起点和终点
start_g = (10, 10)
goal_g = (80, 80)
# 简单BFS路径规划
from collections import deque
def bfs_path(grid, start, goal):
    h, w = grid.shape
    visited = set()
    queue = deque([(start, [start])])
    visited.add(start)
    while queue:
        (x, y), path = queue.popleft()
        if (x, y) == goal:
            return path
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = x+dx, y+dy
            if 0 <= nx < h and 0 <= ny < w and (nx, ny) not in visited and grid[nx, ny] == 0:
                visited.add((nx, ny))
                queue.append(((nx, ny), path + [(nx, ny)]))
    return None

path = bfs_path(grid_occ, start_g, goal_g)
if path:
    print(f"  BFS路径长度: {len(path)}步, 起点={start_g}, 终点={goal_g}")
else:
    print(f"  未找到路径（地图可能被障碍物隔断）")

# 可视化
fig, axes = plt.subplots(1, 2, figsize=(14, 6))
# 里程计vs真实
axes[0].plot(true_log[:, 0], true_log[:, 1], 'g-', label='True trajectory')
axes[0].plot(odom_log[:, 0], odom_log[:, 1], 'r--', label='Odometry')
axes[0].set_title('Odometry Drift')
axes[0].legend()
axes[0].set_aspect('equal')
# 栅格地图
axes[1].imshow(occ, cmap='gray_r', origin='lower')
if path:
    path_arr = np.array(path)
    axes[1].plot(path_arr[:, 1], path_arr[:, 0], 'b-', linewidth=2, label='BFS path')
    axes[1].legend()
axes[1].set_title('Occupancy Grid Map + Path')
fig.savefig(CHARTS_DIR + 'q13_slam.png', dpi=100, bbox_inches='tight')
plt.close(fig)
print("  图表已保存: q13_slam.png")

print("""
关键总结：
  - 里程计通过运动模型积分推算位姿，但误差随时间累积（漂移）
  - ICP通过最近邻匹配+SVD分解求最优刚体变换，对齐连续扫描
  - 栅格地图用log-odds更新，对占据/空闲概率取贝叶斯更新
  - 后端优化利用回环约束全局校正位姿图
  - SLAM=前端跟踪(实时)+后端优化(全局)+地图构建
""")
print("✅ 题13完成")


# ============================================================================
# 题14：抓取与操作
# ============================================================================
# 知识点：
#   - 抓取姿态估计：Antipodal sampling（对跖采样）
#   - 力控反馈仿真：弹簧-阻尼模型
#   - 柔性物体形变：质点弹簧模型（Mass-Spring）
#   - 多指手抓取规划
# ============================================================================

print("\n" + "─" * 80)
print("题14：抓取与操作")
print("─" * 80)

# ── Antipodal抓取采样 ────────────────────────────────────────
def antipodal_grasp_sampling(point_cloud, normals, n_samples=200, friction_coeff=0.5, seed=42):
    """对跖抓取采样：寻找法向量对跖的点对"""
    rng = np.random.default_rng(seed)
    n = len(point_cloud)
    grasps = []

    for _ in range(n_samples):
        i = rng.integers(0, n)
        p1 = point_cloud[i]
        n1 = normals[i]

        # 找对侧点：n1方向延伸找最近点
        dists = np.sum((point_cloud - p1)**2, axis=1)
        # 在n1反方向附近找
        directions = point_cloud - p1
        cos_angles = np.sum(directions * (-n1), axis=1) / (np.linalg.norm(directions, axis=1) + 1e-8)
        # 选择角度小且距离适中的点
        valid = (cos_angles > 0.7) & (dists > 0.05) & (dists < 0.5)
        if not np.any(valid):
            continue

        valid_indices = np.where(valid)[0]
        j = valid_indices[np.argmin(dists[valid])]
        p2 = point_cloud[j]
        n2 = normals[j]

        # 检查Antipodal条件：法向量近似对跖
        cos_n = np.dot(n1, n2)
        if cos_n < -0.8:  # 法向量对跖
            # 检查摩擦锥
            grasp_dir = p2 - p1
            grasp_dir_norm = grasp_dir / (np.linalg.norm(grasp_dir) + 1e-8)
            angle1 = np.arccos(np.clip(np.dot(n1, grasp_dir_norm), -1, 1))
            angle2 = np.arccos(np.clip(np.dot(-n2, grasp_dir_norm), -1, 1))
            friction_angle = np.arctan(friction_coeff)

            if angle1 < friction_angle and angle2 < friction_angle:
                center = (p1 + p2) / 2
                width = np.linalg.norm(p2 - p1)
                grasps.append({
                    'center': center,
                    'width': width,
                    'direction': grasp_dir_norm,
                    'p1': p1, 'p2': p2,
                    'quality': abs(cos_n) * (1 - angle1/friction_angle) * (1 - angle2/friction_angle)
                })

    return grasps

# ── 力控反馈仿真（弹簧-阻尼模型）──────────────────────────────
class ForceControlSim:
    """抓取力控仿真：弹簧-阻尼模型"""
    def __init__(self, k=500, c=10, target_force=10.0):
        self.k = k  # 弹簧刚度
        self.c = c  # 阻尼系数
        self.target_force = target_force
        self.finger_pos = 0.0
        self.finger_vel = 0.0
        self.contact_force = 0.0

    def step(self, dt, control_input):
        """控制输入→手指位置→接触力"""
        # 手指动力学
        force = self.k * control_input - self.c * self.finger_vel
        self.finger_vel += force * dt
        self.finger_pos += self.finger_vel * dt
        # 接触力 = 刚度 × 位移
        self.contact_force = self.k * max(self.finger_pos, 0)
        return self.contact_force

    def pid_control(self, dt, kp=0.001, ki=0.0001, kd=0.01):
        """PID力控"""
        integral = 0
        prev_error = 0
        forces = []
        for _ in range(100):
            error = self.target_force - self.contact_force
            integral += error * dt
            derivative = (error - prev_error) / dt
            control = kp * error + ki * integral + kd * derivative
            control = np.clip(control, 0, 0.05)
            f = self.step(dt, control)
            forces.append(f)
            prev_error = error
        return forces

# ── 柔性物体形变（质点弹簧模型）────────────────────────────────
class MassSpringSystem:
    """2D质点弹簧模型：模拟柔性物体形变"""
    def __init__(self, n_points=10, spacing=0.1, mass=0.01, stiffness=100.0, damping=2.0):
        self.n = n_points
        self.spacing = spacing
        self.masses = np.full(n_points, mass)
        self.positions = np.zeros((n_points, 2))
        self.velocities = np.zeros((n_points, 2))
        self.forces = np.zeros((n_points, 2))
        # 弹簧连接（相邻点）
        self.springs = []
        for i in range(n_points - 1):
            self.springs.append((i, i+1, stiffness))
        # 初始化位置（水平排列）
        self.positions[:, 0] = np.arange(n_points) * spacing
        self.stiffness = stiffness
        self.damping = damping
        self.rest_length = spacing

    def apply_force(self, idx, force):
        self.forces[idx] += force

    def step(self, dt):
        """更新质点位置"""
        self.forces.fill(0)
        # 弹簧力
        for i, j, k in self.springs:
            diff = self.positions[j] - self.positions[i]
            dist = np.linalg.norm(diff)
            if dist > 1e-6:
                direction = diff / dist
                spring_force = k * (dist - self.rest_length)
                self.forces[i] += spring_force * direction
                self.forces[j] -= spring_force * direction
        # 重力
        self.forces[:, 1] += self.masses * 9.81
        # 阻尼
        self.forces -= self.damping * self.velocities
        # 积分
        accel = self.forces / self.masses[:, None]
        self.velocities += accel * dt
        self.positions += self.velocities * dt
        # 固定端点
        self.positions[0] = np.array([0, 0])
        self.velocities[0] = np.array([0, 0])

# ── 多指手抓取规划 ────────────────────────────────────────────
class MultiFingerGrasp:
    """简化三指手抓取规划"""
    def __init__(self, object_center, object_radius):
        self.object_center = np.array(object_center)
        self.object_radius = object_radius
        self.fingers = 3

    def plan_grasp(self):
        """规划3个手指位置（120度均匀分布）"""
        finger_positions = []
        grasp_forces = []
        for i in range(self.fingers):
            angle = 2 * np.pi * i / self.fingers
            # 手指在物体表面
            fx = self.object_center[0] + self.object_radius * np.cos(angle)
            fy = self.object_center[1] + self.object_radius * np.sin(angle)
            finger_positions.append([fx, fy])
            # 法向力指向中心
            force_dir = self.object_center - np.array([fx, fy])
            force_dir = force_dir / np.linalg.norm(force_dir)
            grasp_forces.append(force_dir)
        return np.array(finger_positions), np.array(grasp_forces)

    def check_force_closure(self, forces):
        """检查力封闭：所有力的合力是否为零"""
        total_force = np.sum(forces, axis=0)
        return np.linalg.norm(total_force) < 0.01

# ── 运行抓取演示 ─────────────────────────────────────────────
print("【1】Antipodal抓取采样")
# 生成模拟点云（圆柱体表面）
rng = np.random.default_rng(42)
n_pts = 200
angles = rng.uniform(0, 2 * np.pi, n_pts)
radii = 0.05 + rng.standard_normal(n_pts) * 0.005
pc = np.column_stack([radii * np.cos(angles), radii * np.sin(angles)])
nrm = pc / np.linalg.norm(pc, axis=1, keepdims=True)  # 法向量指向外侧

grasps = antipodal_grasp_sampling(pc, nrm, n_samples=500, friction_coeff=0.5, seed=42)
print(f"  点云点数: {n_pts}")
print(f"  采样抓取候选数: {len(grasps)}")
if grasps:
    best = max(grasps, key=lambda g: g['quality'])
    print(f"  最佳抓取: 中心={np.round(best['center'], 4)}, 宽度={best['width']:.4f}")
    print(f"  抓取质量: {best['quality']:.4f}")
    print(f"  法向量夹角: {np.arccos(np.dot(nrm[np.argmin(np.sum((pc - best['p1'])**2, axis=1))], nrm[np.argmin(np.sum((pc - best['p2'])**2, axis=1))])) * 180 / np.pi:.1f}°")

print("\n【2】力控反馈仿真（弹簧-阻尼模型）")
fc = ForceControlSim(k=500, c=10, target_force=10.0)
forces = fc.pid_control(dt=0.01, kp=0.001, ki=0.0001, kd=0.01)
print(f"  目标力: {fc.target_force:.1f}N")
print(f"  初始接触力: {forces[0]:.2f}N")
print(f"  最终接触力: {forces[-1]:.2f}N")
print(f"  力控稳态误差: {abs(fc.target_force - forces[-1]):.4f}N")
print(f"  超调量: {(max(forces) - fc.target_force) / fc.target_force * 100:.1f}%")

print("\n【3】柔性物体形变（质点弹簧模型）")
ms = MassSpringSystem(n_points=10, spacing=0.1, mass=0.01, stiffness=100.0, damping=2.0)
# 在末端施加向下的力
initial_positions = ms.positions.copy()
for step in range(500):
    if step < 50:
        ms.apply_force(9, np.array([0, -0.5]))  # 末端施加向下载荷
    ms.step(0.001)

final_positions = ms.positions.copy()
deformation = np.linalg.norm(final_positions - initial_positions, axis=1)
print(f"  质点数: {ms.n}, 弹簧刚度: {ms.stiffness}N/m")
print(f"  初始末端位置: {np.round(initial_positions[-1], 4)}")
print(f"  形变后末端位置: {np.round(final_positions[-1], 4)}")
print(f"  最大形变: {deformation.max():.4f}m (在质点{np.argmax(deformation)})")

print("\n【4】多指手抓取规划")
mfg = MultiFingerGrasp(object_center=[0.5, 0.5], object_radius=0.1)
finger_pos, finger_forces = mfg.plan_grasp()
force_closure = mfg.check_force_closure(finger_forces)
print(f"  物体中心: {mfg.object_center}, 半径: {mfg.object_radius}")
print(f"  手指数: {mfg.fingers}")
for i, (pos, force) in enumerate(zip(finger_pos, finger_forces)):
    print(f"    手指{i+1}: 位置={np.round(pos, 4)}, 力方向={np.round(force, 4)}")
print(f"  力封闭检查: {'✓ 通过（合力≈0）' if force_closure else '✗ 失败'}")

# 可视化
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
# Antipodal抓取
axes[0].scatter(pc[:, 0], pc[:, 1], c='blue', s=5, label='Point cloud')
if grasps:
    for g in grasps[:5]:
        axes[0].plot([g['p1'][0], g['p2'][0]], [g['p1'][1], g['p2'][1]], 'r-', linewidth=2)
        axes[0].scatter(*g['center'], c='green', marker='x', s=100)
axes[0].set_title('Antipodal Grasp Sampling')
axes[0].set_aspect('equal')
# 力控
axes[1].plot(forces, 'b-', linewidth=2)
axes[1].axhline(y=10.0, color='r', linestyle='--', label='Target force')
axes[1].set_title('Force Control Response')
axes[1].set_xlabel('Step')
axes[1].set_ylabel('Force (N)')
axes[1].legend()
# 质点弹簧
axes[2].plot(initial_positions[:, 0], initial_positions[:, 1], 'g--', label='Initial')
axes[2].plot(final_positions[:, 0], final_positions[:, 1], 'r-', linewidth=2, label='Deformed')
axes[2].scatter(final_positions[:, 0], final_positions[:, 1], c='red', s=30)
axes[2].set_title('Mass-Spring Deformation')
axes[2].legend()
axes[2].set_aspect('equal')
fig.savefig(CHARTS_DIR + 'q14_grasping.png', dpi=100, bbox_inches='tight')
plt.close(fig)
print("  图表已保存: q14_grasping.png")

print("""
关键总结：
  - Antipodal sampling：寻找法向量对跖的点对，在摩擦锥内形成稳定抓取
  - 力控弹簧-阻尼模型：F = kx + cv̇，PID控制实现目标接触力
  - 质点弹簧模型：质点+弹簧+阻尼，用显式积分模拟柔性物体形变
  - 多指抓取：手指均匀分布形成力封闭，合力为零确保稳定抓取
  - 力封闭：所有接触法向力的合力为零，物体不会滑动
""")
print("✅ 题14完成")


# ============================================================================
# 题15：端到端具身智能系统
# ============================================================================
# 知识点：
#   - 感知→规划→执行闭环：完整具身智能pipeline
#   - 自然语言指令解析：简单NLP匹配任务类型
#   - 多任务策略切换：根据任务类型选择不同策略
#   - 状态机管理：管理任务执行状态
#   - 仿真环境交互：环境感知+动作执行
#   - 任务完成度评估 & 系统监控
# ============================================================================

print("\n" + "─" * 80)
print("题15：端到端具身智能系统")
print("─" * 80)

# ── 自然语言指令解析 ──────────────────────────────────────────
class InstructionParser:
    """简单NLP：基于关键词匹配的任务解析"""
    def __init__(self):
        self.task_keywords = {
            'navigate': ['go', 'move', 'navigate', 'drive', 'walk', 'reach'],
            'grasp': ['pick', 'grab', 'grasp', 'hold', 'take'],
            'place': ['put', 'place', 'drop', 'release', 'set'],
            'open': ['open', 'pull', 'rotate'],
            'close': ['close', 'push', 'shut'],
        }
        self.object_keywords = ['cup', 'bottle', 'box', 'door', 'drawer', 'plate']

    def parse(self, instruction):
        """解析自然语言指令"""
        words = instruction.lower().split()
        task_type = None
        target_object = None
        goal_location = None

        # 识别任务类型
        for task, keywords in self.task_keywords.items():
            if any(kw in words for kw in keywords):
                task_type = task
                break

        # 识别目标物体
        for obj in self.object_keywords:
            if obj in words:
                target_object = obj
                break

        # 识别目标位置（"to"后面的词）
        if 'to' in words:
            idx = words.index('to')
            if idx + 1 < len(words):
                goal_location = words[idx + 1]

        return {
            'task': task_type,
            'object': target_object,
            'goal': goal_location,
            'raw': instruction
        }

# ── 仿真环境 ──────────────────────────────────────────────────
class SimulatedEnvironment:
    """2D仿真环境：机器人+物体"""
    def __init__(self):
        self.robot_pos = np.array([0.0, 0.0])
        self.robot_gripper_open = True
        self.held_object = None
        self.objects = {
            'cup': np.array([2.0, 3.0]),
            'bottle': np.array([4.0, 1.0]),
            'box': np.array([1.0, 5.0]),
        }
        self.locations = {
            'table': np.array([5.0, 5.0]),
            'shelf': np.array([6.0, 2.0]),
            'sink': np.array([3.0, 6.0]),
        }
        self.history = []

    def observe(self):
        """感知环境状态"""
        return {
            'robot_pos': self.robot_pos.copy(),
            'gripper_open': self.robot_gripper_open,
            'held_object': self.held_object,
            'objects': {k: v.copy() for k, v in self.objects.items()},
            'locations': {k: v.copy() for k, v in self.locations.items()},
        }

    def execute_action(self, action):
        """执行动作"""
        action_type = action['type']
        result = {'success': False, 'message': ''}

        if action_type == 'move':
            target = action['target']
            self.robot_pos = target.copy()
            result['success'] = True
            result['message'] = f"移动到 {target}"

        elif action_type == 'grasp':
            obj = action['object']
            if obj in self.objects:
                obj_pos = self.objects[obj]
                dist = np.linalg.norm(self.robot_pos - obj_pos)
                if dist < 0.5:
                    self.held_object = obj
                    self.robot_gripper_open = False
                    result['success'] = True
                    result['message'] = f"抓取了 {obj}"
                else:
                    result['message'] = f"距离{obj}太远({dist:.1f}m)"
            else:
                result['message'] = f"找不到 {obj}"

        elif action_type == 'place':
            if self.held_object:
                loc = action.get('location', 'table')
                if loc in self.locations:
                    loc_pos = self.locations[loc]
                    dist = np.linalg.norm(self.robot_pos - loc_pos)
                    if dist < 0.5:
                        self.objects[self.held_object] = loc_pos.copy()
                        self.held_object = None
                        self.robot_gripper_open = True
                        result['success'] = True
                        result['message'] = f"放置 {action.get('object', '')} 到 {loc}"
                    else:
                        result['message'] = f"距离{loc}太远"
            else:
                result['message'] = "未持有物体"

        elif action_type == 'open_gripper':
            self.robot_gripper_open = True
            result['success'] = True
            result['message'] = "打开夹爪"

        elif action_type == 'close_gripper':
            self.robot_gripper_open = False
            result['success'] = True
            result['message'] = "关闭夹爪"

        self.history.append({
            'action': action,
            'result': result,
            'robot_pos': self.robot_pos.copy()
        })
        return result

# ── 任务状态机 ───────────────────────────────────────────────
class TaskStateMachine:
    """任务执行状态机"""
    STATES = ['IDLE', 'NAVIGATING', 'GRASPING', 'CARRYING', 'PLACING', 'DONE', 'FAILED']

    def __init__(self):
        self.state = 'IDLE'
        self.step_count = 0
        self.plan = []
        self.current_step = 0

    def set_plan(self, plan):
        """设置执行计划"""
        self.plan = plan
        self.current_step = 0
        self.state = 'NAVIGATING' if plan else 'IDLE'

    def get_next_action(self, env_obs):
        """获取下一步动作"""
        if self.current_step >= len(self.plan):
            self.state = 'DONE'
            return None
        return self.plan[self.current_step]

    def advance(self, success):
        """推进状态机"""
        self.step_count += 1
        if success:
            self.current_step += 1
            if self.current_step >= len(self.plan):
                self.state = 'DONE'
            else:
                action = self.plan[self.current_step]
                if action['type'] == 'move':
                    self.state = 'NAVIGATING'
                elif action['type'] == 'grasp':
                    self.state = 'GRASPING'
                elif action['type'] == 'place':
                    self.state = 'PLACING'
        else:
            self.state = 'FAILED'
        return self.state

# ── 任务规划器 ────────────────────────────────────────────────
class TaskPlanner:
    """根据解析的指令生成执行计划"""
    def __init__(self):
        self.parser = InstructionParser()

    def plan(self, instruction, env_obs):
        parsed = self.parser.parse(instruction)
        task = parsed['task']
        obj = parsed['object']
        goal = parsed['goal']

        actions = []
        if task == 'grasp' and obj:
            obj_pos = env_obs['objects'].get(obj, np.array([0, 0]))
            actions.append({'type': 'move', 'target': obj_pos})
            actions.append({'type': 'grasp', 'object': obj})
        elif task == 'place':
            if env_obs['held_object']:
                if goal and goal in env_obs['locations']:
                    goal_pos = env_obs['locations'][goal]
                else:
                    goal_pos = env_obs['locations'].get('table', np.array([5, 5]))
                actions.append({'type': 'move', 'target': goal_pos})
                actions.append({'type': 'place', 'object': env_obs['held_object'], 'location': goal})
        elif task == 'navigate':
            if goal and goal in env_obs['locations']:
                actions.append({'type': 'move', 'target': env_obs['locations'][goal]})

        return actions, parsed

# ── 系统监控面板 ──────────────────────────────────────────────
class SystemMonitor:
    """系统监控面板"""
    def __init__(self):
        self.metrics = {
            'tasks_total': 0,
            'tasks_success': 0,
            'tasks_failed': 0,
            'actions_total': 0,
            'actions_success': 0,
            'total_steps': 0,
            'avg_steps_per_task': 0,
        }

    def record_task(self, success, n_steps):
        self.metrics['tasks_total'] += 1
        if success:
            self.metrics['tasks_success'] += 1
        else:
            self.metrics['tasks_failed'] += 1
        self.metrics['total_steps'] += n_steps
        self.metrics['avg_steps_per_task'] = (
            self.metrics['total_steps'] / self.metrics['tasks_total']
        )

    def record_action(self, success):
        self.metrics['actions_total'] += 1
        if success:
            self.metrics['actions_success'] += 1

    def display(self):
        print("\n  ┌─────────────────────────────────────┐")
        print("  │         系统监控面板               │")
        print("  ├─────────────────────────────────────┤")
        for k, v in self.metrics.items():
            print(f"  │  {k:25s}: {v}")
        if self.metrics['tasks_total'] > 0:
            sr = self.metrics['tasks_success'] / self.metrics['tasks_total'] * 100
            print(f"  │  {'任务成功率':25s}: {sr:.1f}%")
        print("  └─────────────────────────────────────┘")

# ── 端到端系统运行 ────────────────────────────────────────────
print("【1】系统初始化")
env = SimulatedEnvironment()
planner = TaskPlanner()
monitor = SystemMonitor()

print(f"  环境物体: {list(env.objects.keys())}")
print(f"  环境位置: {list(env.locations.keys())}")
print(f"  机器人初始位置: {env.robot_pos}")

print("\n【2】多任务执行")
instructions = [
    "pick up the cup",
    "put the cup to the table",
    "go to the shelf",
    "grab the bottle",
    "place the bottle to the sink",
]

for inst in instructions:
    print(f"\n  ── 指令: '{inst}' ──")
    obs = env.observe()
    actions, parsed = planner.plan(inst, obs)
    print(f"  解析: task={parsed['task']}, object={parsed['object']}, goal={parsed['goal']}")
    print(f"  计划: {len(actions)} 步")

    if not actions:
        print("  ⚠ 无法解析指令，跳过")
        monitor.record_task(False, 0)
        continue

    sm = TaskStateMachine()
    sm.set_plan(actions)
    task_success = True

    while sm.state not in ['DONE', 'FAILED']:
        action = sm.get_next_action(obs)
        if action is None:
            break
        obs = env.observe()
        result = env.execute_action(action)
        monitor.record_action(result['success'])
        print(f"    [{sm.state}] {result['message']} {'✓' if result['success'] else '✗'}")
        sm.advance(result['success'])
        if sm.state == 'FAILED':
            task_success = False
            break

    monitor.record_task(task_success, sm.step_count)
    status = "✅ 成功" if task_success else "❌ 失败"
    print(f"  任务结果: {status} (步骤数: {sm.step_count})")

print("\n【3】系统监控面板")
monitor.display()

print("\n【4】任务完成度评估")
completion_rate = monitor.metrics['tasks_success'] / max(monitor.metrics['tasks_total'], 1)
action_success_rate = monitor.metrics['actions_success'] / max(monitor.metrics['actions_total'], 1)
print(f"  任务完成率: {completion_rate:.1%}")
print(f"  动作成功率: {action_success_rate:.1%}")
print(f"  平均每任务步数: {monitor.metrics['avg_steps_per_task']:.1f}")

# 可视化：最终环境状态
fig, ax = plt.subplots(1, 1, figsize=(8, 8))
# 绘制物体
for obj, pos in env.objects.items():
    ax.scatter(pos[0], pos[1], c='blue', s=100, zorder=5)
    ax.annotate(obj, pos, textcoords="offset points", xytext=(10, 10), fontsize=10)
# 绘制位置
for loc, pos in env.locations.items():
    ax.scatter(pos[0], pos[1], c='green', s=100, marker='s', zorder=5)
    ax.annotate(loc, pos, textcoords="offset points", xytext=(10, -15), fontsize=10)
# 绘制机器人轨迹
if env.history:
    traj = np.array([h['robot_pos'] for h in env.history])
    ax.plot(traj[:, 0], traj[:, 1], 'r-', linewidth=2, alpha=0.5)
ax.scatter(env.robot_pos[0], env.robot_pos[1], c='red', s=200, marker='*', zorder=10, label='Robot')
ax.set_xlim(-1, 8)
ax.set_ylim(-1, 8)
ax.set_aspect('equal')
ax.legend()
ax.set_title('End-to-End Embodied AI System - Final State')
ax.grid(True, alpha=0.3)
fig.savefig(CHARTS_DIR + 'q15_e2e_system.png', dpi=100, bbox_inches='tight')
plt.close(fig)
print("\n  图表已保存: q15_e2e_system.png")

print("""
关键总结：
  - 端到端pipeline：感知(NLP解析)→规划(任务分解)→执行(状态机)→评估
  - 状态机管理任务流程：IDLE→NAVIGATE→GRASP→CARRY→PLACE→DONE
  - 多任务策略切换：根据解析的任务类型选择不同的动作序列
  - 系统监控：实时跟踪任务成功率、动作成功率、平均步数
  - 实际系统需集成感知(视觉/激光)、规划(运动/任务)、控制(力/位置)三层
""")
print("✅ 题15完成")

# ============================================================================
# 总结
# ============================================================================
print("\n" + "=" * 80)
print("阶段七：具身智能（Embodied AI）— 全部 15 题完成！")
print("=" * 80)
print(f"""
库安装情况:
  mujoco:     ✗ 安装超时，使用 numpy 模拟刚体动力学
  gymnasium:  ✓ 已安装 (版本 1.3.0)
  cv2:        ✓ 已安装 (版本 5.0.0)

图表文件:
  q6_motion_planning.png  — 运动规划对比（RRT/RRT*/A*/B样条）
  q13_slam.png            — SLAM里程计漂移与栅格地图
  q14_grasping.png        — 抓取采样/力控响应/质点弹簧形变
  q15_e2e_system.png      — 端到端系统最终状态

核心知识点覆盖:
  7.1 机器人学基础: DH参数/正逆运动学/ROS2通信/RGB-D/IMU/点云
  7.2 仿真与控制:  刚体动力学/PPO强化学习/RRT/RRT*/A*运动规划
  7.3 VLA模型:     RT-1/RT-2/OpenVLA架构/模仿学习/扩散策略/LoRA微调
  7.4 前沿技术:    DreamerV3世界模型/Sim-to-Real域随机化/系统辨识
  7.5 综合项目:    2D SLAM/Antipodal抓取/力控仿真/端到端具身智能系统
""")
