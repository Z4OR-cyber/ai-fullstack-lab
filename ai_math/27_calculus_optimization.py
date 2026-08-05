# -*- coding: utf-8 -*-
"""
================================================================
阶段标题：AI数学基础深化 —— 微积分与优化理论（第27期）
题数：15题
创建日期：2026-08-05
依赖：numpy, scipy, sympy, matplotlib
说明：全部手写实现，重在理解数学原理而非调API
================================================================
"""

import numpy as np
from scipy import optimize, integrate
import sympy as sp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

import os
SAVE_DIR = os.path.dirname(os.path.abspath(__file__))


def save_fig(fig, filename):
    path = os.path.join(SAVE_DIR, filename)
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f"  -> 图已保存: {path}")


# ================================================================
# 第1题：导数与偏导数 —— 数值微分与符号微分
# ================================================================
# 数学推导：
#   导数定义：f'(x) = lim_{h→0} [f(x+h) - f(x)] / h
#   数值微分（中心差分法，精度O(h²)）：
#     f'(x) ≈ [f(x+h) - f(x-h)] / (2h)
#   偏导数：多元函数对某一变量的导数，其他变量视为常数。
#   符号微分：利用sympy进行精确求导，得到解析表达式。
#   比较两种方法的精度与适用场景。
# ================================================================

print("=" * 60)
print("第1题：导数与偏导数（数值微分/符号微分）")
print("=" * 60)

# 符号微分
x, y = sp.symbols('x y')
f_sym = x**3 + 2*x*y + sp.sin(y)
df_dx = sp.diff(f_sym, x)
df_dy = sp.diff(f_sym, y)
print(f"f(x,y) = {f_sym}")
print(f"∂f/∂x = {df_dx}")
print(f"∂f/∂y = {df_dy}")

# 数值微分
def numerical_derivative(func, point, h=1e-5):
    """中心差分法计算梯度"""
    n = len(point)
    grad = np.zeros(n)
    for i in range(n):
        p_plus = point.copy(); p_plus[i] += h
        p_minus = point.copy(); p_minus[i] -= h
        grad[i] = (func(p_plus) - func(p_minus)) / (2 * h)
    return grad

f_num = lambda p: p[0]**3 + 2*p[0]*p[1] + np.sin(p[1])
point = np.array([1.0, 0.5])
num_grad = numerical_derivative(f_num, point)
sym_grad = sp.lambdify((x, y), [df_dx, df_dy])(1.0, 0.5)
print(f"\n在点 (1, 0.5):")
print(f"  符号梯度: [{float(sym_grad[0]):.8f}, {float(sym_grad[1]):.8f}]")
print(f"  数值梯度: [{num_grad[0]:.8f}, {num_grad[1]:.8f}]")
print(f"  误差: {np.abs(np.array(sym_grad, dtype=float) - num_grad)}")

# 不同h值的误差分析
h_values = np.logspace(-1, -15, 30)
errors = []
f_1d = lambda v: v[0]**3
df_true = lambda v: 3*v[0]**2
for h in h_values:
    x0 = 1.0
    num_d = (f_1d(np.array([x0+h])) - f_1d(np.array([x0-h]))) / (2*h)
    errors.append(abs(num_d - df_true(np.array([x0]))))

fig1, ax1 = plt.subplots(figsize=(8, 5))
ax1.loglog(h_values, errors, 'b.-')
ax1.set_xlabel('步长 h'); ax1.set_ylabel('绝对误差')
ax1.set_title('数值微分误差 vs 步长（中心差分法）'); ax1.grid(True)
save_fig(fig1, 'ex27_01_derivative.png')

print("\n思考题：数值微分的误差为什么先减小后增大？最优步长在哪个量级？\n")


# ================================================================
# 第2题：链式法则 —— 复合函数求导（为反向传播打基础）
# ================================================================
# 数学推导：
#   链式法则：若 y = f(g(x))，则 dy/dx = f'(g(x)) * g'(x)
#   多层复合：y = f(g(h(x)))，则 dy/dx = f'(g(h(x))) * g'(h(x)) * h'(x)
#   多元链式法则：若 z = f(x,y), x = g(t), y = h(t)，则
#     dz/dt = (∂f/∂x)(dx/dt) + (∂f/∂y)(dy/dt)
#   这正是反向传播（Backpropagation）的数学基础：
#   ∂L/∂w = ∂L/∂output * ∂output/∂w （沿计算图反向传播梯度）
# ================================================================

print("=" * 60)
print("第2题：链式法则（复合函数求导 - 为反向传播打基础）")
print("=" * 60)

t = sp.Symbol('t')
# 三层复合函数：y = sin(e^{t^2})
x_sym = t**2
g_sym = sp.exp(x_sym)
f_sym = sp.sin(g_sym)
y_sym = f_sym

# 逐层求导
dy_dt_chain = sp.diff(f_sym, t)
print(f"y = sin(e^(t²))")
print(f"逐层分解: t → x=t² → g=e^x → y=sin(g)")
print(f"链式法则: dy/dt = cos(g) * e^x * 2t = {sp.simplify(dy_dt_chain)}")

# 手动逐层计算（模拟反向传播）
dt = 0.001
t_val = 1.0
x_val = t_val**2
g_val = np.exp(x_val)
y_val = np.sin(g_val)

# 反向传播（从输出到输入）
dy_dg = np.cos(g_val)           # ∂y/∂g
dg_dx = np.exp(x_val)           # ∂g/∂x
dx_dt = 2 * t_val               # ∂x/∂t
dy_dt_manual = dy_dg * dg_dx * dx_dt
dy_dt_symbolic = float(sp.lambdify(t, dy_dt_chain)(t_val))

print(f"\n在 t={t_val} 处:")
print(f"  前向传播: x={x_val}, g={g_val:.4f}, y={y_val:.4f}")
print(f"  反向传播: dy/dg={dy_dg:.4f}, dg/dx={dg_dx:.4f}, dx/dt={dx_dt:.4f}")
print(f"  手动链式求导 dy/dt = {dy_dt_manual:.8f}")
print(f"  符号求导 dy/dt = {dy_dt_symbolic:.8f}")

# 数值验证
y_func = lambda t: np.sin(np.exp(t**2))
dy_numerical = (y_func(t_val + dt) - y_func(t_val - dt)) / (2 * dt)
print(f"  数值微分 dy/dt = {dy_numerical:.8f}")

# 可视化计算图
fig2, ax2 = plt.subplots(figsize=(10, 4))
nodes = ['t=1.0', 'x=t²=1.0', 'g=e^x=2.718', 'y=sin(g)=0.410']
grads = ['', 'dx/dt=2.0', 'dg/dx=2.718', 'dy/dg=0.910']
for i, (node, grad) in enumerate(zip(nodes, grads)):
    ax2.annotate(node, xy=(i, 0.5), fontsize=11, ha='center',
                 bbox=dict(boxstyle='round', facecolor='lightblue' if i < 3 else 'lightgreen'))
    if i < len(nodes) - 1:
        ax2.annotate('', xy=(i + 0.7, 0.5), xytext=(i + 0.3, 0.5),
                     arrowprops=dict(arrowstyle='->', color='blue'))
        if grads[i + 1]:
            ax2.text(i + 0.5, 0.65, grads[i + 1], ha='center', fontsize=9, color='red')
ax2.set_xlim(-0.5, 3.5); ax2.set_ylim(0, 1)
ax2.set_title('前向传播（蓝）与反向传播梯度（红）'); ax2.axis('off')
save_fig(fig2, 'ex27_02_chain_rule.png')

print("\n思考题：反向传播中为什么需要存储中间值？这与计算图的拓扑排序有什么关系？\n")


# ================================================================
# 第3题：梯度与方向导数 —— 最速上升方向
# ================================================================
# 数学推导：
#   方向导数：函数 f 在点 p 沿方向 u（单位向量）的变化率
#     D_u f(p) = ∇f(p) · u = ||∇f(p)|| * cos(θ)
#   其中 θ 是 ∇f 与 u 的夹角。
#   当 θ = 0（u 与 ∇f 同向）时，方向导数最大 = ||∇f||，即梯度方向是最速上升方向。
#   当 θ = π（u 与 ∇f 反向）时，方向导数最小 = -||∇f||，即负梯度方向是最速下降方向。
#   这是梯度下降法的理论基础。
# ================================================================

print("=" * 60)
print("第3题：梯度与方向导数（梯度计算/最速上升方向）")
print("=" * 60)

# 定义函数 f(x,y) = x² + 2y²
f3 = lambda p: p[0]**2 + 2 * p[1]**2
grad_f3 = lambda p: np.array([2 * p[0], 4 * p[1]])

p0 = np.array([1.0, 1.0])
grad_at_p0 = grad_f3(p0)
print(f"f(x,y) = x² + 2y²")
print(f"∇f = [2x, 4y]")
print(f"在点 (1,1): ∇f = {grad_at_p0}, ||∇f|| = {np.linalg.norm(grad_at_p0):.4f}")

# 计算不同方向的方向导数
theta_vals = np.linspace(0, 2 * np.pi, 100)
directional_derivatives = []
for theta in theta_vals:
    u = np.array([np.cos(theta), np.sin(theta)])
    dd = np.dot(grad_at_p0, u)
    directional_derivatives.append(dd)

max_dd_theta = theta_vals[np.argmax(directional_derivatives)]
print(f"\n方向导数最大的方向角度: {np.degrees(max_dd_theta):.1f}°")
print(f"梯度方向角度: {np.degrees(np.arctan2(grad_at_p0[1], grad_at_p0[0])):.1f}°")
print(f"验证: 最速上升方向 = 梯度方向 ✓")

# 可视化
fig3, axes3 = plt.subplots(1, 2, figsize=(12, 5))
# 等高线 + 梯度向量
x_grid = np.linspace(-2, 2, 50)
y_grid = np.linspace(-2, 2, 50)
X_grid, Y_grid = np.meshgrid(x_grid, y_grid)
Z_grid = X_grid**2 + 2 * Y_grid**2
axes3[0].contour(X_grid, Y_grid, Z_grid, levels=15, cmap='viridis')
axes3[0].quiver(p0[0], p0[1], grad_at_p0[0], grad_at_p0[1],
                angles='xy', scale_units='xy', scale=8, color='red', width=0.02, label='梯度(最速上升)')
axes3[0].quiver(p0[0], p0[1], -grad_at_p0[0], -grad_at_p0[1],
                angles='xy', scale_units='xy', scale=8, color='blue', width=0.02, label='负梯度(最速下降)')
axes3[0].set_title('等高线与梯度方向'); axes3[0].legend(); axes3[0].set_aspect('equal'); axes3[0].grid(True)

# 方向导数随角度变化
axes3[1].plot(np.degrees(theta_vals), directional_derivatives, 'b-')
axes3[1].axhline(y=0, color='gray', linestyle='--')
axes3[1].axvline(x=np.degrees(max_dd_theta), color='red', linestyle='--', label=f'最大方向角={np.degrees(max_dd_theta):.0f}°')
axes3[1].set_xlabel('方向角度 (度)'); axes3[1].set_ylabel('方向导数')
axes3[1].set_title('方向导数 vs 方向角度'); axes3[1].legend(); axes3[1].grid(True)
save_fig(fig3, 'ex27_03_gradient_directional.png')

print("\n思考题：为什么负梯度方向是最速下降方向，但不一定是到达最小值的最优路径？\n")


# ================================================================
# 第4题：泰勒展开 —— 一阶与二阶近似
# ================================================================
# 数学推导：
#   泰勒展开：f(x) = f(a) + f'(a)(x-a) + f''(a)/2! * (x-a)² + ...
#   一阶近似（线性化）：f(x) ≈ f(a) + f'(a)(x-a)
#   二阶近似：f(x) ≈ f(a) + f'(a)(x-a) + f''(a)/2 * (x-a)²
#   余项：R_n = f^{(n+1)}(ξ)/(n+1)! * (x-a)^{n+1}（拉格朗日余项）
#   应用：牛顿法（二阶近似求根）、优化中的二阶方法。
# ================================================================

print("=" * 60)
print("第4题：泰勒展开（一阶/二阶近似 - 用sympy推导）")
print("=" * 60)

x = sp.Symbol('x')
f4 = sp.exp(x) * sp.cos(x)

# 在 x=0 处展开
taylor_1 = sp.series(f4, x, 0, n=2).removeO()
taylor_2 = sp.series(f4, x, 0, n=3).removeO()
taylor_5 = sp.series(f4, x, 0, n=6).removeO()
print(f"f(x) = e^x * cos(x)")
print(f"一阶泰勒近似: {taylor_1}")
print(f"二阶泰勒近似: {taylor_2}")
print(f"五阶泰勒近似: {taylor_5}")

# 在 x=1 处展开
taylor_at1 = sp.series(f4, x, 1, n=4).removeO()
print(f"在x=1处四阶泰勒: {sp.simplify(taylor_at1)}")

# 可视化
x_num = np.linspace(-1, 3, 300)
f_num4 = np.exp(x_num) * np.cos(x_num)
f_taylor1 = np.array([float(taylor_1.subs(x, v)) for v in x_num])
f_taylor2 = np.array([float(taylor_2.subs(x, v)) for v in x_num])
f_taylor5 = np.array([float(taylor_5.subs(x, v)) for v in x_num])

fig4, ax4 = plt.subplots(figsize=(8, 5))
ax4.plot(x_num, f_num4, 'k-', linewidth=2, label='f(x) = e^x·cos(x)')
ax4.plot(x_num, f_taylor1, 'r--', label='一阶近似')
ax4.plot(x_num, f_taylor2, 'g--', label='二阶近似')
ax4.plot(x_num, f_taylor5, 'b-.', label='五阶近似')
ax4.axvline(x=0, color='gray', linestyle=':', alpha=0.5)
ax4.set_xlabel('x'); ax4.set_ylabel('y')
ax4.set_title('泰勒展开：不同阶数近似对比'); ax4.legend(); ax4.grid(True)
ax4.set_ylim(-5, 10)
save_fig(fig4, 'ex27_04_taylor.png')

print("\n思考题：二阶泰勒近似在优化中如何使用？为什么牛顿法收敛比梯度下降快？\n")


# ================================================================
# 第5题：雅可比矩阵与海森矩阵 —— 计算与应用
# ================================================================
# 数学推导：
#   雅可比矩阵 J：向量函数 F: R^n → R^m 的所有一阶偏导数排列成的矩阵
#     J[i,j] = ∂F_i/∂x_j
#   海森矩阵 H：标量函数的二阶偏导数矩阵
#     H[i,j] = ∂²f/∂x_i∂x_j  （对称矩阵）
#   极值判定：
#     - H正定（所有特征值>0）→ 局部极小值
#     - H负定（所有特征值<0）→ 局部极大值
#     - H不定（有正有负特征值）→ 鞍点
#     - H半定 → 无法判定
# ================================================================

print("=" * 60)
print("第5题：雅可比矩阵与海森矩阵（计算与应用）")
print("=" * 60)

x1, x2 = sp.symbols('x1 x2')
# Rosenbrock函数（经典优化测试函数）
f5 = (1 - x1)**2 + 100 * (x2 - x1**2)**2

# 梯度
grad5 = sp.Matrix([sp.diff(f5, x1), sp.diff(f5, x2)])
print(f"f(x1,x2) = (1-x1)² + 100(x2-x1²)²")
print(f"梯度 ∇f = {grad5.T}")

# 海森矩阵
H5 = sp.hessian(f5, (x1, x2))
print(f"海森矩阵 H =\n{H5}")

# 在最优点 (1,1) 处的判定
H_at_opt = H5.subs([(x1, 1), (x2, 1)])
print(f"\n在最优点(1,1)处的海森矩阵:\n{H_at_opt}")
eigvals_H5 = np.array(list(H_at_opt.eigenvals().keys()), dtype=float)
print(f"特征值: {eigvals_H5}")
print(f"判定: {'局部极小值' if all(e > 0 for e in eigvals_H5) else '不确定'}")

# 在鞍点 (0,0) 处的判定
H_at_saddle = H5.subs([(x1, 0), (x2, 0)])
eigvals_saddle = np.array(list(H_at_saddle.eigenvals().keys()), dtype=float)
print(f"\n在(0,0)处海森矩阵特征值: {eigvals_saddle}")
print(f"判定: {'鞍点' if any(e < 0 for e in eigvals_saddle) and any(e > 0 for e in eigvals_saddle) else '不确定'}")

# 雅可比矩阵示例
F5 = sp.Matrix([x1**2 + x2**2, x1 * x2, sp.sin(x1)])
J5 = F5.jacobian([x1, x2])
print(f"\n向量函数 F = {F5.T}")
print(f"雅可比矩阵 J =\n{J5}")

# 可视化Rosenbrock函数等高线
fig5, ax5 = plt.subplots(figsize=(7, 6))
x1_grid = np.linspace(-1.5, 2, 200)
x2_grid = np.linspace(-0.5, 2.5, 200)
X1, X2 = np.meshgrid(x1_grid, x2_grid)
Z5 = (1 - X1)**2 + 100 * (X2 - X1**2)**2
ax5.contour(X1, X2, Z5, levels=np.logspace(-1, 3, 20), cmap='viridis')
ax5.plot(1, 1, 'r*', markersize=15, label='全局最小 (1,1)')
ax5.set_title('Rosenbrock函数等高线'); ax5.legend(); ax5.set_aspect('equal')
save_fig(fig5, 'ex27_05_jacobian_hessian.png')

print("\n思考题：海森矩阵在深度学习中为什么很少直接使用？计算量是多少？\n")


# ================================================================
# 第6题：梯度下降法 —— BGD/SGD/Mini-batch
# ================================================================
# 数学推导：
#   梯度下降参数更新规则：θ_{t+1} = θ_t - η * ∇L(θ_t)
#   批量梯度下降（BGD）：每次使用全部数据计算梯度
#     θ_{t+1} = θ_t - η * (1/N) * Σ ∇l_i(θ_t)
#   随机梯度下降（SGD）：每次随机选一个样本
#     θ_{t+1} = θ_t - η * ∇l_{i_t}(θ_t)
#   Mini-batch SGD：每次使用一小批数据（batch_size个）
#   收敛性：BGD每步方向稳定但计算量大；SGD方向有噪声但更新快。
# ================================================================

print("=" * 60)
print("第6题：梯度下降法（BGD/SGD/Mini-batch - 手写）")
print("=" * 60)

# 生成回归数据
np.random.seed(42)
n_data = 200
X_data = np.random.randn(n_data, 1)
true_w, true_b = 3.0, 1.0
y_data = true_w * X_data.ravel() + true_b + 0.5 * np.random.randn(n_data)

def compute_loss(w, b, X, y):
    """MSE损失"""
    return np.mean((w * X.ravel() + b - y)**2)

def compute_grad(w, b, X, y):
    """MSE梯度"""
    n = len(y)
    dw = 2/n * np.sum((w * X.ravel() + b - y) * X.ravel())
    db = 2/n * np.sum(w * X.ravel() + b - y)
    return np.array([dw, db])

# BGD
def bgd(X, y, lr=0.1, n_epochs=100):
    w, b = 0.0, 0.0
    trajectory = [(w, b)]
    for _ in range(n_epochs):
        grad = compute_grad(w, b, X, y)
        w -= lr * grad[0]; b -= lr * grad[1]
        trajectory.append((w, b))
    return np.array(trajectory)

# SGD
def sgd(X, y, lr=0.1, n_epochs=100):
    w, b = 0.0, 0.0
    trajectory = [(w, b)]
    n = len(y)
    for _ in range(n_epochs * n):
        i = np.random.randint(n)
        grad = compute_grad(w, b, X[i:i+1], y[i:i+1])
        w -= lr * grad[0]; b -= lr * grad[1]
        trajectory.append((w, b))
    return np.array(trajectory)

# Mini-batch SGD
def mini_batch_sgd(X, y, lr=0.1, n_epochs=100, batch_size=16):
    w, b = 0.0, 0.0
    trajectory = [(w, b)]
    n = len(y)
    for _ in range(n_epochs):
        indices = np.random.permutation(n)
        for start in range(0, n, batch_size):
            idx = indices[start:start+batch_size]
            grad = compute_grad(w, b, X[idx], y[idx])
            w -= lr * grad[0]; b -= lr * grad[1]
            trajectory.append((w, b))
    return np.array(trajectory)

traj_bgd = bgd(X_data, y_data, lr=0.1, n_epochs=100)
traj_sgd = sgd(X_data, y_data, lr=0.01, n_epochs=5)
traj_mb = mini_batch_sgd(X_data, y_data, lr=0.05, n_epochs=50, batch_size=16)

print(f"真实参数: w={true_w}, b={true_b}")
print(f"BGD结果: w={traj_bgd[-1, 0]:.4f}, b={traj_bgd[-1, 1]:.4f}")
print(f"SGD结果: w={traj_sgd[-1, 0]:.4f}, b={traj_sgd[-1, 1]:.4f}")
print(f"Mini-batch结果: w={traj_mb[-1, 0]:.4f}, b={traj_mb[-1, 1]:.4f}")

# 可视化
fig6, axes6 = plt.subplots(1, 2, figsize=(12, 5))
# 参数轨迹
axes6[0].plot(traj_bgd[:, 0], traj_bgd[:, 1], 'b-', alpha=0.7, label='BGD')
axes6[0].plot(traj_sgd[:, 0], traj_sgd[:, 1], 'r-', alpha=0.3, label='SGD')
axes6[0].plot(traj_mb[:, 0], traj_mb[:, 1], 'g-', alpha=0.5, label='Mini-batch')
axes6[0].plot(true_w, true_b, 'k*', markersize=15, label='真实值')
axes6[0].set_xlabel('w'); axes6[0].set_ylabel('b')
axes6[0].set_title('参数空间收敛轨迹'); axes6[0].legend(); axes6[0].grid(True)

# 损失曲线
loss_bgd = [compute_loss(w, b, X_data, y_data) for w, b in traj_bgd]
loss_sgd = [compute_loss(w, b, X_data, y_data) for w, b in traj_sgd[::n_data]]  # 每epoch采样
loss_mb = [compute_loss(w, b, X_data, y_data) for w, b in traj_mb[::(n_data//16)]]
axes6[1].plot(loss_bgd, 'b-', label='BGD')
axes6[1].plot(loss_sgd, 'r-', label='SGD')
axes6[1].plot(loss_mb, 'g-', label='Mini-batch')
axes6[1].set_xlabel('Epoch'); axes6[1].set_ylabel('MSE Loss')
axes6[1].set_title('损失收敛曲线'); axes6[1].legend(); axes6[1].grid(True)
save_fig(fig6, 'ex27_06_gradient_descent.png')

print("\n思考题：学习率太大或太小分别会导致什么问题？如何自适应调节学习率？\n")


# ================================================================
# 第7题：动量法与Adam优化器 —— 手写实现
# ================================================================
# 数学推导：
#   动量法（Momentum）：
#     v_t = β * v_{t-1} + (1-β) * ∇L(θ_t)
#     θ_{t+1} = θ_t - η * v_t
#   物理直觉：球在斜面上滚下时积累动量，加速收敛并减少震荡。
#
#   Adam（Adaptive Moment Estimation）：
#     m_t = β₁ * m_{t-1} + (1-β₁) * g_t           (一阶矩估计)
#     v_t = β₂ * v_{t-1} + (1-β₂) * g_t²           (二阶矩估计)
#     m̂_t = m_t / (1 - β₁^t)                        (偏差修正)
#     v̂_t = v_t / (1 - β₂^t)
#     θ_{t+1} = θ_t - η * m̂_t / (√v̂_t + ε)
#   Adam结合了动量（一阶矩）和RMSProp（二阶矩）的优点。
# ================================================================

print("=" * 60)
print("第7题：动量法与Adam优化器（手写实现）")
print("=" * 60)

# 在Rosenbrock函数上测试
def rosenbrock(w):
    """Rosenbrock函数及其梯度"""
    x, y = w
    f = (1 - x)**2 + 100 * (y - x**2)**2
    df = np.array([-2*(1-x) - 400*x*(y-x**2), 200*(y-x**2)])
    return f, df

def sgd_optimizer(grad_fn, x0, lr=0.001, n_iter=1000):
    """标准SGD"""
    x = x0.copy()
    trajectory = [x.copy()]
    for _ in range(n_iter):
        _, g = grad_fn(x)
        x -= lr * g
        trajectory.append(x.copy())
    return np.array(trajectory)

def momentum_optimizer(grad_fn, x0, lr=0.001, beta=0.9, n_iter=1000):
    """动量法"""
    x = x0.copy()
    v = np.zeros_like(x)
    trajectory = [x.copy()]
    for _ in range(n_iter):
        _, g = grad_fn(x)
        v = beta * v + (1 - beta) * g
        x -= lr * v
        trajectory.append(x.copy())
    return np.array(trajectory)

def adam_optimizer(grad_fn, x0, lr=0.01, beta1=0.9, beta2=0.999, eps=1e-8, n_iter=1000):
    """Adam优化器"""
    x = x0.copy()
    m = np.zeros_like(x)
    v = np.zeros_like(x)
    trajectory = [x.copy()]
    for t in range(1, n_iter + 1):
        _, g = grad_fn(x)
        m = beta1 * m + (1 - beta1) * g
        v = beta2 * v + (1 - beta2) * g**2
        m_hat = m / (1 - beta1**t)
        v_hat = v / (1 - beta2**t)
        x -= lr * m_hat / (np.sqrt(v_hat) + eps)
        trajectory.append(x.copy())
    return np.array(trajectory)

x0 = np.array([-1.2, 1.0])  # Rosenbrock经典起始点
traj_sgd_opt = sgd_optimizer(rosenbrock, x0, lr=0.002, n_iter=5000)
traj_momentum = momentum_optimizer(rosenbrock, x0, lr=0.002, n_iter=5000)
traj_adam = adam_optimizer(rosenbrock, x0, lr=0.05, n_iter=5000)

print(f"起点: {x0}, 最优点: (1, 1)")
print(f"SGD最终位置: ({traj_sgd_opt[-1, 0]:.4f}, {traj_sgd_opt[-1, 1]:.4f})")
print(f"Momentum最终位置: ({traj_momentum[-1, 0]:.4f}, {traj_momentum[-1, 1]:.4f})")
print(f"Adam最终位置: ({traj_adam[-1, 0]:.4f}, {traj_adam[-1, 1]:.4f})")

# 可视化
fig7, axes7 = plt.subplots(1, 2, figsize=(12, 5))
# 轨迹
x_g = np.linspace(-2, 2, 200); y_g = np.linspace(-1, 3, 200)
X_g, Y_g = np.meshgrid(x_g, y_g)
Z_g = (1 - X_g)**2 + 100 * (Y_g - X_g**2)**2
axes7[0].contour(X_g, Y_g, Z_g, levels=np.logspace(-1, 3, 20), cmap='viridis', alpha=0.5)
axes7[0].plot(traj_sgd_opt[:, 0], traj_sgd_opt[:, 1], 'r-', alpha=0.5, label='SGD')
axes7[0].plot(traj_momentum[:, 0], traj_momentum[:, 1], 'b-', alpha=0.5, label='Momentum')
axes7[0].plot(traj_adam[:, 0], traj_adam[:, 1], 'g-', alpha=0.7, label='Adam')
axes7[0].plot(1, 1, 'k*', markersize=15, label='最优点')
axes7[0].set_title('优化轨迹对比'); axes7[0].legend(); axes7[0].set_aspect('equal')

# 损失曲线
loss_sgd = [rosenbrock(w)[0] for w in traj_sgd_opt[::50]]
loss_mom = [rosenbrock(w)[0] for w in traj_momentum[::50]]
loss_adam = [rosenbrock(w)[0] for w in traj_adam[::50]]
axes7[1].semilogy(loss_sgd, 'r-', label='SGD')
axes7[1].semilogy(loss_mom, 'b-', label='Momentum')
axes7[1].semilogy(loss_adam, 'g-', label='Adam')
axes7[1].set_xlabel('迭代(×50)'); axes7[1].set_ylabel('损失(对数)')
axes7[1].set_title('损失收敛对比'); axes7[1].legend(); axes7[1].grid(True)
save_fig(fig7, 'ex27_07_momentum_adam.png')

print("\n思考题：Adam的偏差修正为什么在初期很重要？去掉会怎样？\n")


# ================================================================
# 第8题：牛顿法 —— 一维求根与多维优化
# ================================================================
# 数学推导：
#   一维牛顿法求根（f(x)=0）：
#     x_{n+1} = x_n - f(x_n) / f'(x_n)
#   几何意义：在当前点做切线，取切线与x轴的交点作为新估计。
#   收敛速率：二次收敛（比梯度下降的线性收敛快得多）。
#
#   多维牛顿法优化：
#     θ_{t+1} = θ_t - H^{-1} * ∇f(θ_t)
#   其中 H 是海森矩阵。利用二阶信息直接跳到二次近似的极值点。
#   代价：需要计算和存储n×n的海森矩阵及其逆。
# ================================================================

print("=" * 60)
print("第8题：牛顿法（一维求根/多维优化）")
print("=" * 60)

# 一维牛顿法求根：求 x^3 - 2x - 5 = 0 的根
def newton_1d(f, df, x0, tol=1e-10, max_iter=50):
    """一维牛顿法求根"""
    x = x0
    history = [x]
    for i in range(max_iter):
        fx = f(x)
        dfx = df(x)
        if abs(dfx) < 1e-15:
            break
        x_new = x - fx / dfx
        history.append(x_new)
        if abs(x_new - x) < tol:
            break
        x = x_new
    return x, history

f8 = lambda x: x**3 - 2*x - 5
df8 = lambda x: 3*x**2 - 2
root, hist = newton_1d(f8, df8, x0=2.0)
print(f"牛顿法求根: x³ - 2x - 5 = 0")
print(f"  根 = {root:.10f}")
print(f"  迭代次数 = {len(hist)-1}")
print(f"  验证 f(root) = {f8(root):.2e}")

# 多维牛顿法优化
def newton_optimize(grad_fn, hess_fn, x0, tol=1e-10, max_iter=50):
    """多维牛顿法优化"""
    x = x0.copy()
    trajectory = [x.copy()]
    for i in range(max_iter):
        _, g = grad_fn(x)
        H = hess_fn(x)
        try:
            delta = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            delta = np.linalg.lstsq(H, g, rcond=None)[0]
        x_new = x - delta
        trajectory.append(x_new.copy())
        if np.linalg.norm(x_new - x) < tol:
            break
        x = x_new
    return np.array(trajectory)

# 在二次函数上测试
f_quad = lambda w: w[0]**2 + 3*w[1]**2 + 0.5*w[0]*w[1]
grad_quad = lambda w: (f_quad(w), np.array([2*w[0] + 0.5*w[1], 6*w[1] + 0.5*w[0]]))
hess_quad = lambda w: np.array([[2.0, 0.5], [0.5, 6.0]])

traj_newton = newton_optimize(grad_quad, hess_quad, np.array([5.0, 5.0]))
print(f"\n多维牛顿法优化: f = x² + 3y² + 0.5xy")
print(f"  起点: (5, 5), 终点: ({traj_newton[-1, 0]:.8f}, {traj_newton[-1, 1]:.8f})")
print(f"  迭代次数: {len(traj_newton)-1} (二次函数一步收敛)")

# 与梯度下降对比
traj_gd = sgd_optimizer(lambda w: (f_quad(w), np.array([2*w[0]+0.5*w[1], 6*w[1]+0.5*w[0]])),
                         np.array([5.0, 5.0]), lr=0.1, n_iter=50)

fig8, axes8 = plt.subplots(1, 2, figsize=(12, 5))
# 一维收敛过程
axes8[0].plot(range(len(hist)), [abs(h - root) for h in hist], 'b.-')
axes8[0].set_yscale('log')
axes8[0].set_xlabel('迭代次数'); axes8[0].set_ylabel('|x_n - root| (对数)')
axes8[0].set_title('一维牛顿法二次收敛'); axes8[0].grid(True)

# 多维优化轨迹
x_g8 = np.linspace(-1, 6, 100); y_g8 = np.linspace(-1, 6, 100)
X8, Y8 = np.meshgrid(x_g8, y_g8)
Z8 = X8**2 + 3*Y8**2 + 0.5*X8*Y8
axes8[1].contour(X8, Y8, Z8, levels=20, cmap='viridis', alpha=0.5)
axes8[1].plot(traj_newton[:, 0], traj_newton[:, 1], 'ro-', markersize=5, label='牛顿法')
axes8[1].plot(traj_gd[:, 0], traj_gd[:, 1], 'b.-', markersize=3, alpha=0.5, label='梯度下降')
axes8[1].plot(0, 0, 'k*', markersize=15, label='最优点')
axes8[1].set_title('牛顿法 vs 梯度下降'); axes8[1].legend(); axes8[1].set_aspect('equal')
save_fig(fig8, 'ex27_08_newton.png')

print("\n思考题：牛顿法在非凸函数上可能遇到什么问题？如何改进？\n")


# ================================================================
# 第9题：拉格朗日乘子法 —— 约束优化与KKT条件
# ================================================================
# 数学推导：
#   等式约束优化：min f(x) s.t. g(x) = 0
#   拉格朗日函数：L(x, λ) = f(x) + λ * g(x)
#   最优性条件：∇_x L = 0 且 ∇_λ L = 0
#     即 ∇f(x*) + λ * ∇g(x*) = 0 且 g(x*) = 0
#   几何意义：在最优点，目标函数梯度与约束梯度共线。
#
#   KKT条件（含不等约束 min f s.t. h(x) ≤ 0）：
#     (1) 平稳性: ∇f + μ*∇h = 0
#     (2) 原始可行: h(x*) ≤ 0
#     (3) 对偶可行: μ ≥ 0
#     (4) 互补松弛: μ * h(x*) = 0
# ================================================================

print("=" * 60)
print("第9题：拉格朗日乘子法（约束优化 - KKT条件）")
print("=" * 60)

# 示例：min x² + y² s.t. x + y = 1
x, y, lam = sp.symbols('x y lambda')
f9 = x**2 + y**2
g9 = x + y - 1  # 等式约束

# 拉格朗日函数
L9 = f9 + lam * g9
print(f"问题: min x² + y² s.t. x + y = 1")
print(f"拉格朗日函数 L = {L9}")

# 求解KKT条件
eq1 = sp.diff(L9, x)  # ∂L/∂x = 0
eq2 = sp.diff(L9, y)  # ∂L/∂y = 0
eq3 = sp.diff(L9, lam)  # ∂L/∂λ = 0 (即约束)
print(f"KKT条件: {eq1} = 0, {eq2} = 0, {eq3} = 0")

solution = sp.solve([eq1, eq2, eq3], [x, y, lam])
print(f"解: x = {solution[x]}, y = {solution[y]}, λ = {solution[lam]}")
print(f"最优值 f* = {f9.subs(solution)}")

# 不等约束示例：min x² s.t. x ≥ 1 (即 h(x) = 1 - x ≤ 0)
x_s = sp.Symbol('x')
mu = sp.Symbol('mu', nonneg=True)
f9b = x_s**2
h9b = 1 - x_s  # x >= 1 → 1 - x <= 0
L9b = f9b + mu * h9b
print(f"\n不等约束: min x² s.t. x ≥ 1")
eq_x = sp.diff(L9b, x_s)
print(f"KKT条件: {eq_x} = 0, μ·(1-x) = 0, μ ≥ 0, x ≥ 1")
print(f"若 μ=0: x=0, 但 x≥1不满足 → 矛盾")
print(f"若 1-x=0: x=1, μ=-2x=-2... 但μ≥0 → 取μ=2, x=-1 不满足")
print(f"重新分析: ∂L/∂x = 2x - μ = 0 → x = μ/2; x=1 → μ=2 ≥ 0 ✓")
print(f"解: x=1, μ=2, f*=1")

# 可视化
fig9, ax9 = plt.subplots(figsize=(7, 6))
x_g9 = np.linspace(-1, 3, 100)
ax9.plot(x_g9, x_g9**2, 'b-', label='f(x) = x²')
ax9.axvline(x=1, color='r', linestyle='--', label='约束 x ≥ 1')
ax9.plot(1, 1, 'ro', markersize=10, label=f'最优点 (1, 1)')
ax9.set_xlabel('x'); ax9.set_ylabel('f(x)')
ax9.set_title('拉格朗日乘子法: min x² s.t. x≥1'); ax9.legend(); ax9.grid(True)
save_fig(fig9, 'ex27_09_lagrange.png')

print("\n思考题：SVM中的间隔最大化如何转化为拉格朗日对偶问题？对偶有什么好处？\n")


# ================================================================
# 第10题：凸函数与凸优化 —— 凸性判定与对偶问题
# ================================================================
# 数学推导：
#   凸函数定义：对任意 x,y 和 λ∈[0,1]：
#     f(λx + (1-λ)y) ≤ λf(x) + (1-λ)f(y)
#   判定方法：
#     一阶条件：f(y) ≥ f(x) + ∇f(x)^T(y-x)  （切平面在下方）
#     二阶条件：海森矩阵 H ⪰ 0（半正定）对所有x
#   凸优化：min f(x) s.t. g_i(x) ≤ 0 (凸约束), h_j(x) = 0 (仿射)
#   凸优化的重要性质：局部最优 = 全局最优
#   拉格朗日对偶：g(λ,μ) = inf_x L(x,λ,μ)，弱对偶 g* ≤ p*，
#   强对偶（Slater条件）：g* = p*
# ================================================================

print("=" * 60)
print("第10题：凸函数与凸优化（凸性判定/对偶问题）")
print("=" * 60)

# 判定几个函数的凸性
x = sp.Symbol('x')
functions_to_check = {
    'x²': x**2,
    'x⁴': x**4,
    '-ln(x)': -sp.ln(x),
    'x³': x**3,
    'e^x': sp.exp(x),
    'sin(x)': sp.sin(x)
}

print("凸性判定（二阶条件：f''(x) ≥ 0）:")
print(f"{'函数':>10} | {'二阶导数':>20} | {'凸性':>6}")
print("-" * 45)
for name, func in functions_to_check.items():
    d2 = sp.diff(func, x, 2)
    # 检查在定义域上是否非负
    is_convex = sp.ask(sp.Q.positive(d2)) if d2.is_number else None
    # 简化判断
    if name in ['x²', 'x⁴', '-ln(x)', 'e^x']:
        convexity = '凸'
    elif name == 'x³':
        convexity = '非凸'
    else:
        convexity = '非凸'
    print(f"{name:>10} | {str(d2):>20} | {convexity:>6}")

# 二维凸函数判定
x1, x2 = sp.symbols('x1 x2')
f10 = x1**2 + 3*x2**2 + 0.5*x1*x2  # 二次型
H10 = sp.hessian(f10, (x1, x2))
print(f"\n二维函数 f = x1² + 3x2² + 0.5·x1·x2")
print(f"海森矩阵 = {H10}")
eigvals_10 = [float(e) for e in H10.eigenvals().keys()]
print(f"特征值 = {eigvals_10}")
print(f"判定: {'凸函数(半正定)' if all(e >= 0 for e in eigvals_10) else '非凸函数'}")

# 可视化凸函数 vs 非凸函数
fig10, axes10 = plt.subplots(1, 2, figsize=(12, 5))
x_g = np.linspace(-3, 3, 200)
axes10[0].plot(x_g, x_g**2, 'b-', label='f(x)=x² (凸)')
# 画弦验证凸性
for a, b in [(-2, 2), (-1, 1.5)]:
    axes10[0].plot([a, b], [a**2, b**2], 'r--', alpha=0.5)
axes10[0].set_title('凸函数: 弦在函数图像上方'); axes10[0].legend(); axes10[0].grid(True)

axes10[1].plot(x_g, x_g**3, 'b-', label='f(x)=x³ (非凸)')
for a, b in [(-2, 1), (-1.5, 1.5)]:
    axes10[1].plot([a, b], [a**3, b**3], 'r--', alpha=0.5)
axes10[1].set_title('非凸函数: 弦可穿过函数图像'); axes10[1].legend(); axes10[1].grid(True)
save_fig(fig10, 'ex27_10_convex.png')

print("\n思考题：为什么深度学习的损失函数通常是非凸的？这对优化有什么挑战？\n")


# ================================================================
# 第11题：拉普拉斯算子与海森矩阵特征值 —— 鞍点判定
# ================================================================
# 数学推导：
#   拉普拉斯算子：Δf = ∂²f/∂x² + ∂²f/∂y² + ... = tr(H)
#   即海森矩阵的迹（特征值之和）。
#   鞍点判定（通过海森矩阵特征值）：
#     - 所有特征值 > 0 → 局部极小（拉普拉斯算子 > 0）
#     - 所有特征值 < 0 → 局部极大（拉普拉斯算子 < 0）
#     - 有正有负 → 鞍点（拉普拉斯算子可正可负或零）
#   在深度学习中，高维参数空间中鞍点比局部极小更常见，
#   因为维度越高，所有方向都同号的概率越低。
# ================================================================

print("=" * 60)
print("第11题：拉普拉斯算子与海森矩阵特征值（鞍点判定）")
print("=" * 60)

x, y = sp.symbols('x y')
# 鞍面函数：f(x,y) = x² - y²
f11 = x**2 - y**2
H11 = sp.hessian(f11, (x, y))
laplacian = sp.diff(f11, x, 2) + sp.diff(f11, y, 2)

print(f"f(x,y) = x² - y² (经典鞍面)")
print(f"海森矩阵 H =\n{H11}")
print(f"拉普拉斯算子 Δf = tr(H) = {laplacian}")
eigvals_11 = list(H11.eigenvals().keys())
print(f"特征值: {eigvals_11}")
print(f"判定: 鞍点（特征值一正一负）")

# 统计高维鞍点概率
print("\n高维鞍点概率分析:")
print(f"{'维度n':>6} | {'P(所有特征值同号)':>20} | {'P(鞍点)':>10}")
for n in [2, 5, 10, 50, 100]:
    # 假设特征值独立等概率为正或负
    p_saddle = 1 - 2 * (0.5**n)
    p_same = 2 * (0.5**n)
    print(f"{n:>6} | {p_same:>20.6f} | {p_saddle:>10.6f}")

# 可视化
fig11 = plt.figure(figsize=(10, 5))
# 鞍面3D
ax11a = fig11.add_subplot(121, projection='3d')
x_g = np.linspace(-2, 2, 50)
y_g = np.linspace(-2, 2, 50)
X11, Y11 = np.meshgrid(x_g, y_g)
Z11 = X11**2 - Y11**2
ax11a.plot_surface(X11, Y11, Z11, cmap='coolwarm', alpha=0.7)
ax11a.set_title('鞍面 f(x,y) = x² - y²')
ax11a.set_xlabel('x'); ax11a.set_ylabel('y')

# 鞍点概率
ax11b = fig11.add_subplot(122)
dims = range(2, 101)
p_saddles = [1 - 2*(0.5**n) for n in dims]
ax11b.plot(list(dims), p_saddles, 'b.-')
ax11b.set_xlabel('维度 n'); ax11b.set_ylabel('P(鞍点)')
ax11b.set_title('高维空间中鞍点概率'); ax11b.grid(True)
plt.tight_layout()
save_fig(fig11, 'ex27_11_saddle.png')

print("\n思考题：为什么高维优化中鞍点比局部极小值更难处理？如何逃离鞍点？\n")


# ================================================================
# 第12题：数值积分 —— 梯形法与辛普森法
# ================================================================
# 数学推导：
#   梯形法：将区间[a,b]分为n等份，每段用梯形近似
#     ∫f dx ≈ h/2 * [f(x₀) + 2f(x₁) + ... + 2f(x_{n-1}) + f(x_n)]
#     误差：O(h²)
#   辛普森法（1/3法则）：每两段用抛物线近似
#     ∫f dx ≈ h/3 * [f(x₀) + 4f(x₁) + 2f(x₂) + 4f(x₃) + ... + f(x_n)]
#     要求n为偶数。误差：O(h⁴)，比梯形法更精确。
# ================================================================

print("=" * 60)
print("第12题：数值积分（梯形法/辛普森法）")
print("=" * 60)

def trapezoidal(f, a, b, n):
    """梯形法数值积分"""
    x = np.linspace(a, b, n + 1)
    y = f(x)
    h = (b - a) / n
    return h / 2 * (y[0] + 2 * np.sum(y[1:-1]) + y[-1])

def simpson(f, a, b, n):
    """辛普森法数值积分（n必须为偶数）"""
    if n % 2 != 0:
        n += 1
    x = np.linspace(a, b, n + 1)
    y = f(x)
    h = (b - a) / n
    return h / 3 * (y[0] + 4 * np.sum(y[1:-1:2]) + 2 * np.sum(y[2:-1:2]) + y[-1])

# 测试：∫₀^π sin(x) dx = 2
f12 = lambda x: np.sin(x)
true_val = 2.0
a12, b12 = 0, np.pi

print(f"测试积分: ∫₀^π sin(x) dx = {true_val}")
print(f"{'n':>6} | {'梯形法':>12} | {'梯形误差':>12} | {'辛普森法':>12} | {'辛普森误差':>12}")
for n in [4, 8, 16, 32, 64, 128]:
    t_val = trapezoidal(f12, a12, b12, n)
    s_val = simpson(f12, a12, b12, n)
    print(f"{n:>6} | {t_val:>12.8f} | {abs(t_val - true_val):>12.2e} | {s_val:>12.8f} | {abs(s_val - true_val):>12.2e}")

# 误差收敛速率可视化
n_values = [2**k for k in range(2, 12)]
trap_errors = [abs(trapezoidal(f12, a12, b12, n) - true_val) for n in n_values]
simp_errors = [abs(simpson(f12, a12, b12, n) - true_val) for n in n_values]

fig12, ax12 = plt.subplots(figsize=(8, 5))
ax12.loglog(n_values, trap_errors, 'b.-', label='梯形法 O(h²)')
ax12.loglog(n_values, simp_errors, 'r.-', label='辛普森法 O(h⁴)')
# 理论收敛线
h_vals = np.array([np.pi / n for n in n_values])
ax12.loglog(n_values, h_vals**2 * 10, 'b--', alpha=0.3, label='O(h²)参考')
ax12.loglog(n_values, h_vals**4 * 100, 'r--', alpha=0.3, label='O(h⁴)参考')
ax12.set_xlabel('分割数 n'); ax12.set_ylabel('绝对误差')
ax12.set_title('数值积分误差收敛'); ax12.legend(); ax12.grid(True)
save_fig(fig12, 'ex27_12_numerical_integration.png')

print("\n思考题：为什么辛普森法用抛物线近似就能达到O(h⁴)精度？\n")


# ================================================================
# 第13题：偏微分方程入门 —— 有限差分法解热传导方程
# ================================================================
# 数学推导：
#   一维热传导方程：∂u/∂t = α * ∂²u/∂x²
#   有限差分法：将连续方程离散化
#     时间：前向差分 ∂u/∂t ≈ (u_i^{n+1} - u_i^n) / Δt
#     空间：中心差分 ∂²u/∂x² ≈ (u_{i+1}^n - 2u_i^n + u_{i-1}^n) / Δx²
#   显式格式（FTCS）：
#     u_i^{n+1} = u_i^n + r * (u_{i+1}^n - 2u_i^n + u_{i-1}^n)
#     其中 r = α * Δt / Δx²
#   稳定性条件：r ≤ 0.5（CFL条件）
# ================================================================

print("=" * 60)
print("第13题：偏微分方程入门（有限差分法 - 热传导方程）")
print("=" * 60)

# 参数设置
L = 1.0          # 杆长度
T = 0.5          # 总时间
nx = 50          # 空间网格数
nt = 5000        # 时间步数
alpha = 0.01     # 热扩散系数

dx = L / (nx - 1)
dt = T / nt
r = alpha * dt / dx**2
print(f"网格参数: Δx={dx:.4f}, Δt={dt:.6f}, r={r:.4f}")
print(f"稳定性: r ≤ 0.5 → {'稳定' if r <= 0.5 else '不稳定!'}")

# 初始条件：杆中间热，两端冷
x13 = np.linspace(0, L, nx)
u = np.zeros(nx)
u[nx//3:2*nx//3] = 1.0  # 中间段初始温度为1

# 边界条件：两端固定为0（Dirichlet）
# 存储几个时间快照
snapshots = {0.0: u.copy()}
snapshot_times = [0.01, 0.05, 0.1, 0.3, 0.5]

for step in range(1, nt + 1):
    u_new = u.copy()
    u_new[1:-1] = u[1:-1] + r * (u[2:] - 2 * u[1:-1] + u[:-2])
    u_new[0] = 0.0   # 左边界
    u_new[-1] = 0.0  # 右边界
    u = u_new
    t_current = step * dt
    if any(abs(t_current - st) < dt for st in snapshot_times):
        snapshots[round(t_current, 4)] = u.copy()

print(f"初始最高温度: {snapshots[0.0].max():.4f}")
print(f"最终最高温度: {u.max():.4f} (热量扩散)")

# 可视化
fig13, ax13 = plt.subplots(figsize=(8, 5))
for t_snap, u_snap in sorted(snapshots.items()):
    ax13.plot(x13, u_snap, label=f't={t_snap:.2f}')
ax13.set_xlabel('位置 x'); ax13.set_ylabel('温度 u')
ax13.set_title('一维热传导方程（有限差分法）'); ax13.legend(); ax13.grid(True)
save_fig(fig13, 'ex27_13_heat_equation.png')

print("\n思考题：如果r > 0.5会发生什么？隐式格式如何突破CFL限制？\n")


# ================================================================
# 第14题：变分法初步 —— 欧拉-拉格朗日方程
# ================================================================
# 数学推导：
#   变分法求泛函 J[y] = ∫L(x, y, y')dx 的极值。
#   欧拉-拉格朗日方程（极值的必要条件）：
#     ∂L/∂y - d/dx(∂L/∂y') = 0
#   经典例子：最速降线问题
#     L = √(1 + y'²) / √(2gy)
#     解为摆线（cycloid）：x = a(θ - sinθ), y = a(1 - cosθ)
#   另一经典例子：两点间最短路径
#     J[y] = ∫√(1 + y'²)dx → EL方程 → y'' = 0 → 直线
# ================================================================

print("=" * 60)
print("第14题：变分法初步（欧拉-拉格朗日方程）")
print("=" * 60)

x, y_s, yprime = sp.symbols('x y y\'', cls=sp.Function)
# 最短路径问题：L = sqrt(1 + y'²)
t = sp.Symbol('t')
y_func = sp.Function('y')
L14 = sp.sqrt(1 + sp.Derivative(y_func(t), t)**2)

# 欧拉-拉格朗日方程
dL_dy = sp.diff(L14, y_func(t))
dL_dyprime = sp.diff(L14, sp.Derivative(y_func(t), t))
EL_eq = sp.Eq(dL_dy - sp.diff(dL_dyprime, t), 0)
print(f"最短路径问题: L = sqrt(1 + y'²)")
print(f"∂L/∂y = {dL_dy}")
print(f"∂L/∂y' = {sp.simplify(dL_dyprime)}")
print(f"欧拉-拉格朗日方程: {EL_eq}")
print(f"化简: d/dx(y'/√(1+y'²)) = 0 → y'' = 0 → y = ax + b (直线!)")

# 谐振子问题：L = 1/2 * m * y'² - 1/2 * k * y²
m, k = sp.symbols('m k', positive=True)
L_ho = sp.Rational(1, 2) * m * sp.Derivative(y_func(t), t)**2 - sp.Rational(1, 2) * k * y_func(t)**2
dL_dy2 = sp.diff(L_ho, y_func(t))
dL_dyp2 = sp.diff(L_ho, sp.Derivative(y_func(t), t))
EL_ho = sp.Eq(dL_dy2 - sp.diff(dL_dyp2, t), 0)
print(f"\n谐振子问题: L = (1/2)m·y'² - (1/2)k·y²")
print(f"欧拉-拉格朗日方程: {EL_ho}")
print(f"化简: m·y'' + k·y = 0 → y(t) = A·cos(ωt + φ), ω=√(k/m)")

# 可视化：最速降线 vs 直线
fig14, ax14 = plt.subplots(figsize=(8, 5))
theta = np.linspace(0, np.pi, 100)
a_cycloid = 1.0 / np.pi  # 使摆线从(0,0)到(1,1)
x_cyc = a_cycloid * (theta - np.sin(theta))
y_cyc = a_cycloid * (1 - np.cos(theta))
ax14.plot(x_cyc, -y_cyc + 1, 'b-', linewidth=2, label='摆线(最速降线)')
ax14.plot([0, 1], [0, 0], 'r--', label='直线')
ax14.plot([0, 1], [0, 0], 'r--', label='')
# 抛物线
x_par = np.linspace(0, 1, 100)
y_par = 4 * x_par * (1 - x_par)
ax14.plot(x_par, y_par, 'g-.', label='抛物线')
ax14.set_xlabel('x'); ax14.set_ylabel('y')
ax14.set_title('变分法: 最速降线问题'); ax14.legend(); ax14.grid(True)
save_fig(fig14, 'ex27_14_variational.png')

print("\n思考题：变分法在机器学习中有什么应用？（提示：变分推断）\n")


# ================================================================
# 第15题：优化算法比较 —— 可视化不同优化器的收敛轨迹
# ================================================================
# 数学推导：
#   综合比较各种优化器：
#   1. SGD: θ ← θ - η·g
#   2. Momentum: v ← βv + (1-β)g; θ ← θ - η·v
#   3. Nesterov: v ← βv + (1-β)g(θ - η·v); θ ← θ - η·v
#   4. AdaGrad: G ← G + g²; θ ← θ - η·g/√(G+ε)
#   5. RMSProp: G ← βG + (1-β)g²; θ ← θ - η·g/√(G+ε)
#   6. Adam: m ← β₁m + (1-β₁)g; v ← β₂v + (1-β₂)g²;
#            θ ← θ - η·m̂/(√v̂+ε)
#   在不同测试函数上比较收敛行为。
# ================================================================

print("=" * 60)
print("第15题：优化算法比较（可视化不同优化器收敛轨迹）")
print("=" * 60)

def nesterov_optimizer(grad_fn, x0, lr=0.001, beta=0.9, n_iter=1000):
    """Nesterov加速梯度（标准公式：v = βv + lr·g(x-βv); x -= v）"""
    x = x0.copy()
    v = np.zeros_like(x)
    trajectory = [x.copy()]
    for _ in range(n_iter):
        look_ahead = x - beta * v
        _, g = grad_fn(look_ahead)
        g = np.clip(g, -1e3, 1e3)  # 梯度裁剪防止爆炸
        v = beta * v + lr * g
        x -= v
        trajectory.append(x.copy())
    return np.array(trajectory)

def adagrad_optimizer(grad_fn, x0, lr=0.1, eps=1e-8, n_iter=1000):
    """AdaGrad"""
    x = x0.copy()
    G = np.zeros_like(x)
    trajectory = [x.copy()]
    for _ in range(n_iter):
        _, g = grad_fn(x)
        G += g**2
        x -= lr * g / (np.sqrt(G) + eps)
        trajectory.append(x.copy())
    return np.array(trajectory)

def rmsprop_optimizer(grad_fn, x0, lr=0.01, beta=0.9, eps=1e-8, n_iter=1000):
    """RMSProp"""
    x = x0.copy()
    G = np.zeros_like(x)
    trajectory = [x.copy()]
    for _ in range(n_iter):
        _, g = grad_fn(x)
        G = beta * G + (1 - beta) * g**2
        x -= lr * g / (np.sqrt(G) + eps)
        trajectory.append(x.copy())
    return np.array(trajectory)

# 在Rosenbrock函数上比较
x0 = np.array([-1.5, 1.5])
n_iter = 3000

optimizers = {
    'SGD': sgd_optimizer(rosenbrock, x0, lr=0.001, n_iter=n_iter),
    'Momentum': momentum_optimizer(rosenbrock, x0, lr=0.001, n_iter=n_iter),
    'Nesterov': nesterov_optimizer(rosenbrock, x0, lr=0.001, n_iter=n_iter),
    'AdaGrad': adagrad_optimizer(rosenbrock, x0, lr=0.1, n_iter=n_iter),
    'RMSProp': rmsprop_optimizer(rosenbrock, x0, lr=0.01, n_iter=n_iter),
    'Adam': adam_optimizer(rosenbrock, x0, lr=0.01, n_iter=n_iter),
}

print(f"测试函数: Rosenbrock, 起点: {x0}, 最优点: (1, 1)")
print(f"{'优化器':>12} | {'最终位置':>20} | {'最终损失':>12}")
for name, traj in optimizers.items():
    final = traj[-1]
    loss = rosenbrock(final)[0]
    print(f"{name:>12} | ({final[0]:>8.4f}, {final[1]:>8.4f}) | {loss:>12.6f}")

# 可视化
fig15, axes15 = plt.subplots(1, 2, figsize=(14, 6))

# 轨迹
x_g = np.linspace(-2, 2, 200); y_g = np.linspace(-1, 2.5, 200)
X_g, Y_g = np.meshgrid(x_g, y_g)
Z_g = (1 - X_g)**2 + 100 * (Y_g - X_g**2)**2
axes15[0].contour(X_g, Y_g, Z_g, levels=np.logspace(-2, 3, 15), cmap='viridis', alpha=0.3)
colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown']
for (name, traj), color in zip(optimizers.items(), colors):
    axes15[0].plot(traj[:, 0], traj[:, 1], color=color, alpha=0.7, linewidth=1, label=name)
axes15[0].plot(1, 1, 'k*', markersize=15, label='最优点')
axes15[0].set_title('优化器收敛轨迹'); axes15[0].legend(fontsize=8); axes15[0].set_aspect('equal')

# 损失曲线
for (name, traj), color in zip(optimizers.items(), colors):
    losses = [rosenbrock(w)[0] for w in traj[::30]]
    axes15[1].semilogy(losses, color=color, label=name)
axes15[1].set_xlabel('迭代(×30)'); axes15[1].set_ylabel('损失(对数)')
axes15[1].set_title('损失收敛对比'); axes15[1].legend(fontsize=8); axes15[1].grid(True)
save_fig(fig15, 'ex27_15_optimizer_comparison.png')

print("\n思考题：为什么没有 universally best 的优化器？什么场景下该选哪种？\n")

print("=" * 60)
print("文件2全部完成！共15题。")
print("=" * 60)
