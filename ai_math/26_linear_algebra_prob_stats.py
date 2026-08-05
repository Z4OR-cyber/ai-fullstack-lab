# -*- coding: utf-8 -*-
"""
================================================================
阶段标题：AI数学基础深化 —— 线性代数与概率统计（第26期）
题数：15题
创建日期：2026-08-05
依赖：numpy, scipy, sympy, matplotlib
说明：全部手写实现，重在理解数学原理而非调API
================================================================
"""

import numpy as np
from scipy import linalg
import sympy as sp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 全局中文显示设置
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 保存图片目录（与脚本同目录）
import os
SAVE_DIR = os.path.dirname(os.path.abspath(__file__))


def save_fig(fig, filename):
    """保存图片到脚本所在目录"""
    path = os.path.join(SAVE_DIR, filename)
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f"  -> 图已保存: {path}")


# ================================================================
# 第1题：矩阵分解 —— LU分解（手写实现）
# ================================================================
# 数学推导：
#   LU分解将矩阵 A 分解为 A = L * U，其中 L 为单位下三角矩阵，
#   U 为上三角矩阵。采用Doolittle算法：
#   对于 k = 0, 1, ..., n-1：
#     U[k, j] = A[k, j] - sum(L[k, s] * U[s, j], s=0..k-1)   (j >= k)
#     L[i, k] = (A[i, k] - sum(L[i, s] * U[s, k], s=0..k-1)) / U[k, k]  (i > k)
#   当主元为零时需要选主元（部分主元法），此时 PA = LU。
# ================================================================

def lu_decomposition(A):
    """
    手写LU分解（带部分主元法）
    返回 P, L, U 使得 P @ A = L @ U
    """
    A = np.array(A, dtype=float)
    n = A.shape[0]
    L = np.eye(n)
    U = A.copy()
    P = np.eye(n)

    for k in range(n):
        # 选主元：找第k列中第k行以下绝对值最大的元素
        max_row = np.argmax(np.abs(U[k:, k])) + k
        if max_row != k:
            U[[k, max_row], :] = U[[max_row, k], :]
            P[[k, max_row], :] = P[[max_row, k], :]
            if k > 0:
                L[[k, max_row], :k] = L[[max_row, k], :k]

        for i in range(k + 1, n):
            L[i, k] = U[i, k] / U[k, k]
            U[i, k:] -= L[i, k] * U[k, k:]

    return P, L, U


print("=" * 60)
print("第1题：LU分解（手写实现）")
print("=" * 60)

A1 = np.array([[2.0, 1.0, -1.0],
               [-3.0, -1.0, 2.0],
               [-2.0, 1.0, 2.0]])

P1, L1, U1 = lu_decomposition(A1)
print("原始矩阵 A =\n", A1)
print("排列矩阵 P =\n", P1)
print("下三角 L =\n", L1)
print("上三角 U =\n", U1)
print("验证 P@A = L@U ?", np.allclose(P1 @ A1, L1 @ U1))
print("  用LU分解解线性方程组 Ax=b：")
b1 = np.array([8.0, -11.0, -3.0])
# Ly = Pb, Ux = y
y1 = np.linalg.solve(L1, P1 @ b1)
x1 = np.linalg.solve(U1, y1)
print(f"  解 x = {x1}")
print(f"  验证 Ax = {A1 @ x1}, 应为 {b1}")

print("\n思考题：为什么需要主元选择？如果不用主元法，对什么矩阵会失败？\n")


# ================================================================
# 第2题：QR分解 —— Gram-Schmidt正交化
# ================================================================
# 数学推导：
#   QR分解将矩阵 A 分解为 A = Q * R，其中 Q 为正交矩阵（列向量正交），
#   R 为上三角矩阵。通过Gram-Schmidt正交化过程实现：
#   设 A 的列向量为 a_1, a_2, ..., a_n，则：
#     u_1 = a_1,  e_1 = u_1 / ||u_1||
#     u_k = a_k - sum(<a_k, e_j> * e_j, j=1..k-1),  e_k = u_k / ||u_k||
#   Q = [e_1, e_2, ..., e_n]，R[j,k] = <e_j, a_k> (j<=k)
# ================================================================

def gram_schmidt_qr(A):
    """
    手写Gram-Schmidt正交化实现QR分解
    """
    A = np.array(A, dtype=float)
    m, n = A.shape
    Q = np.zeros((m, n))
    R = np.zeros((n, n))

    for k in range(n):
        v = A[:, k].copy()
        for j in range(k):
            R[j, k] = np.dot(Q[:, j], A[:, k])
            v -= R[j, k] * Q[:, j]
        R[k, k] = np.linalg.norm(v)
        if R[k, k] < 1e-12:
            R[k, k] = 1e-12  # 防止除零
        Q[:, k] = v / R[k, k]

    return Q, R


print("=" * 60)
print("第2题：QR分解（Gram-Schmidt正交化）")
print("=" * 60)

A2 = np.array([[1.0, 1.0, 0.0],
               [1.0, 0.0, 1.0],
               [0.0, 1.0, 1.0]])

Q2, R2 = gram_schmidt_qr(A2)
print("A =\n", A2)
print("Q (正交矩阵) =\n", Q2)
print("R (上三角矩阵) =\n", R2)
print("验证 Q@R = A ?", np.allclose(Q2 @ R2, A2))
print("验证 Q的列正交 ?", np.allclose(Q2.T @ Q2, np.eye(3)))

fig2, axes2 = plt.subplots(1, 2, figsize=(10, 4))
# 可视化：原矩阵列向量 vs 正交化后的列向量
origin = np.zeros(3)
for i in range(3):
    axes2[0].quiver(0, 0, A2[0, i], A2[1, i], angles='xy', scale_units='xy', scale=1, color='blue', width=0.02)
axes2[0].set_xlim(-1.5, 2.0); axes2[0].set_ylim(-1.5, 2.0)
axes2[0].set_title('原始列向量'); axes2[0].grid(True)
axes2[0].set_aspect('equal')

for i in range(3):
    axes2[1].quiver(0, 0, Q2[0, i], Q2[1, i], angles='xy', scale_units='xy', scale=1, color='red', width=0.02)
axes2[1].set_xlim(-1.5, 2.0); axes2[1].set_ylim(-1.5, 2.0)
axes2[1].set_title('Gram-Schmidt正交化后'); axes2[1].grid(True)
axes2[1].set_aspect('equal')
save_fig(fig2, 'ex02_qr_gram_schmidt.png')

print("\n思考题：经典Gram-Schmidt在数值上可能不稳定，改进版（Modified GS）改了什么？\n")


# ================================================================
# 第3题：特征值与特征向量 —— 幂迭代法
# ================================================================
# 数学推导：
#   对于方阵 A，特征值 λ 和特征向量 v 满足 A*v = λ*v。
#   幂迭代法求最大特征值：
#     1. 随机初始化向量 v_0
#     2. 迭代：v_{k+1} = A * v_k / ||A * v_k||  （归一化）
#     3. λ ≈ v_k^T * A * v_k  （Rayleigh商）
#   收敛条件：最大特征值在模长上严格大于其他特征值。
#   逆幂迭代：对 A^{-1} 用幂迭代 → 求最小特征值。
# ================================================================

def power_iteration(A, n_iter=1000, tol=1e-10):
    """
    幂迭代法求最大特征值及对应特征向量
    """
    n = A.shape[0]
    v = np.random.randn(n)
    v /= np.linalg.norm(v)
    eigenvalue_old = 0

    for i in range(n_iter):
        w = A @ v
        norm_w = np.linalg.norm(w)
        if norm_w < 1e-15:
            break
        v = w / norm_w
        eigenvalue = v @ A @ v  # Rayleigh商
        if abs(eigenvalue - eigenvalue_old) < tol:
            break
        eigenvalue_old = eigenvalue

    return eigenvalue, v


print("=" * 60)
print("第3题：特征值与特征向量（幂迭代法手写）")
print("=" * 60)

A3 = np.array([[4.0, 1.0, 2.0],
               [1.0, 3.0, 0.0],
               [2.0, 0.0, 5.0]])

eigval_max, eigvec_max = power_iteration(A3)
print(f"幂迭代求最大特征值: {eigval_max:.6f}")
print(f"对应特征向量: {eigvec_max}")
# 用numpy验证
eigvals_np = np.linalg.eigvals(A3)
print(f"numpy验证所有特征值: {sorted(eigvals_np, reverse=True)}")
print(f"验证 A@v ≈ λ*v ?", np.allclose(A3 @ eigvec_max, eigval_max * eigvec_max, atol=1e-6))

# 可视化：幂迭代收敛过程
conv_vals = []
v_tmp = np.random.randn(3); v_tmp /= np.linalg.norm(v_tmp)
for _ in range(50):
    w = A3 @ v_tmp; v_tmp = w / np.linalg.norm(w)
    conv_vals.append(v_tmp @ A3 @ v_tmp)

fig3, ax3 = plt.subplots(figsize=(8, 4))
ax3.plot(conv_vals, 'b.-', label='Rayleigh商')
ax3.axhline(y=eigval_max, color='r', linestyle='--', label=f'收敛值={eigval_max:.4f}')
ax3.set_xlabel('迭代次数'); ax3.set_ylabel('特征值估计')
ax3.set_title('幂迭代法收敛过程'); ax3.legend(); ax3.grid(True)
save_fig(fig3, 'ex03_power_iteration.png')

print("\n思考题：如果最大特征值是复数，幂迭代法还能用吗？如何处理？\n")


# ================================================================
# 第4题：SVD分解 —— 手写实现及图像压缩应用
# ================================================================
# 数学推导：
#   奇异值分解：A = U * Σ * V^T
#   其中 U 是 m×m 正交矩阵（左奇异向量），V 是 n×n 正交矩阵（右奇异向量），
#   Σ 是 m×n 对角矩阵（奇异值，从大到小排列）。
#   推导：A^T*A 的特征向量组成 V，特征值的平方根为奇异值；
#         A*V = U*Σ → U = A*V*Σ^{-1}
#   截断SVD（低秩近似）：保留前k个奇异值，A_k = U[:,:k] * Σ[:k,:k] * V[:,:k]^T
#   Eckart-Young定理：A_k 是秩为k的最优近似（Frobenius范数意义下）。
# ================================================================

def svd_manual(A):
    """
    手写SVD分解：通过 A^T*A 的特征分解实现
    """
    A = np.array(A, dtype=float)
    m, n = A.shape

    # 求 A^T * A 的特征值和特征向量 → 得到 V 和奇异值
    AtA = A.T @ A
    eigvals, eigvecs = np.linalg.eigh(AtA)  # eigh用于对称矩阵

    # 排序（降序）
    idx = np.argsort(eigvals)[::-1]
    eigvals = eigvals[idx]
    eigvecs = eigvecs[:, idx]

    # 奇异值 = sqrt(特征值)，过滤负数（数值误差）
    singular_values = np.sqrt(np.maximum(eigvals, 0))

    # V
    V = eigvecs

    # U = A * V / Σ（对非零奇异值）
    tol = max(m, n) * np.finfo(float).eps * (singular_values[0] if len(singular_values) > 0 and singular_values[0] > 0 else 1)
    U = np.zeros((m, m))
    r = 0  # 有效秩
    for i in range(min(m, n)):
        if singular_values[i] > tol:
            U[:, i] = A @ V[:, i] / singular_values[i]
            r += 1

    # 补全U的剩余列（用Gram-Schmidt正交化生成正交补空间）
    if r < m:
        np.random.seed(0)
        for i in range(r, m):
            v = np.random.randn(m)
            for j in range(i):
                v -= np.dot(U[:, j], v) * U[:, j]
            norm = np.linalg.norm(v)
            if norm > 1e-12:
                U[:, i] = v / norm

    Sigma = np.zeros((m, n))
    for i in range(min(m, n)):
        Sigma[i, i] = singular_values[i]

    return U, Sigma, V.T


print("=" * 60)
print("第4题：SVD分解（手写实现 + 低秩压缩应用）")
print("=" * 60)

# 用一个简单矩阵验证
A4 = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
U4, S4, Vt4 = svd_manual(A4)
print("A =\n", A4)
print("U =\n", U4)
print("Σ =\n", S4)
print("V^T =\n", Vt4)
print("验证 U@Σ@V^T = A ?", np.allclose(U4 @ S4 @ Vt4, A4))

# 应用：低秩近似压缩
# 构造一个低秩矩阵 + 噪声
np.random.seed(42)
true_rank = 3
A_low = np.random.randn(20, 3) @ np.random.randn(3, 15)  # 秩3矩阵
A_noisy = A_low + 0.1 * np.random.randn(20, 15)  # 加噪声

U_n, S_n, Vt_n = svd_manual(A_noisy)
print("\n奇异值:", np.round(np.diag(S_n)[:8], 3))

# 截断到前3个奇异值
k = 3
A_compressed = U_n[:, :k] @ S_n[:k, :k] @ Vt_n[:k, :]
print(f"压缩前后Frobenius误差: {np.linalg.norm(A_noisy - A_low, 'fro'):.4f} -> {np.linalg.norm(A_compressed - A_low, 'fro'):.4f}")

# 可视化奇异值衰减
fig4, ax4 = plt.subplots(figsize=(8, 4))
ax4.semilogy(np.diag(S_n), 'bo-', label='奇异值')
ax4.axvline(x=k - 1, color='r', linestyle='--', label=f'截断 k={k}')
ax4.set_xlabel('索引'); ax4.set_ylabel('奇异值(对数尺度)')
ax4.set_title('SVD奇异值衰减'); ax4.legend(); ax4.grid(True)
save_fig(fig4, 'ex04_svd_compression.png')

print("\n思考题：SVD为什么在推荐系统（协同过滤）中如此重要？\n")


# ================================================================
# 第5题：矩阵伪逆与最小二乘 —— Moore-Penrose伪逆
# ================================================================
# 数学推导：
#   Moore-Penrose伪逆 A^+ 满足四个条件：
#   (1) A*A^+*A = A  (2) A^+*A*A^+ = A^+  (3) (A*A^+)^T = A*A^+  (4) (A^+*A)^T = A^+*A
#   通过SVD计算：若 A = UΣV^T，则 A^+ = V*Σ^+*U^T，其中Σ^+是对角元素取倒数。
#   最小二乘问题：min ||Ax - b||^2 的解为 x = A^+*b
#   当A列满秩时，A^+ = (A^T*A)^{-1}*A^T（正规方程解）
# ================================================================

def moore_penrose_pinv(A):
    """
    手写Moore-Penrose伪逆（基于SVD）
    """
    A = np.array(A, dtype=float)
    U, S, Vt = svd_manual(A)
    m, n = A.shape
    tol = max(m, n) * np.finfo(float).eps * np.max(np.diag(S))
    S_inv = np.zeros((n, m))
    for i in range(min(m, n)):
        if abs(S[i, i]) > tol:
            S_inv[i, i] = 1.0 / S[i, i]
    return Vt.T @ S_inv @ U.T


print("=" * 60)
print("第5题：矩阵伪逆与最小二乘（Moore-Penrose伪逆）")
print("=" * 60)

# 超定方程组：3个方程2个未知数
A5 = np.array([[1.0, 1.0], [1.0, 2.0], [1.0, 3.0], [1.0, 4.0]])
b5 = np.array([6.0, 5.0, 7.0, 10.0])

A5_pinv = moore_penrose_pinv(A5)
print("A^+ (伪逆) =\n", A5_pinv)
x5 = A5_pinv @ b5
print(f"最小二乘解 x = {x5}")
print(f"numpy验证: {np.linalg.pinv(A5) @ b5}")
print(f"残差 ||Ax-b|| = {np.linalg.norm(A5 @ x5 - b5):.6f}")

# 可视化：最小二乘拟合直线
fig5, ax5 = plt.subplots(figsize=(8, 5))
xs = np.array([1, 2, 3, 4])
ax5.scatter(xs, b5, color='blue', s=80, zorder=5, label='数据点')
x_line = np.linspace(0.5, 4.5, 100)
y_line = x5[0] + x5[1] * x_line
ax5.plot(x_line, y_line, 'r-', label=f'拟合: y = {x5[0]:.2f} + {x5[1]:.2f}x')
for xi, yi in zip(xs, b5):
    yi_hat = x5[0] + x5[1] * xi
    ax5.plot([xi, xi], [yi, yi_hat], 'g--', alpha=0.6)
ax5.set_xlabel('x'); ax5.set_ylabel('y')
ax5.set_title('最小二乘直线拟合（残差用绿色虚线表示）'); ax5.legend(); ax5.grid(True)
save_fig(fig5, 'ex05_pinv_least_squares.png')

print("\n思考题：当方程组是欠定的（方程少于未知数），伪逆给出什么解？\n")


# ================================================================
# 第6题：概率分布 —— 二项/泊松/正态/指数分布采样与可视化
# ================================================================
# 数学推导：
#   二项分布 B(n,p)：n次独立伯努利试验中成功k次的概率
#     P(X=k) = C(n,k) * p^k * (1-p)^{n-k}
#   泊松分布 Po(λ)：单位时间内事件发生k次的概率
#     P(X=k) = λ^k * e^{-λ} / k!
#   正态分布 N(μ,σ²)：
#     f(x) = (1/(σ√2π)) * exp(-(x-μ)²/(2σ²))
#   指数分布 Exp(λ)：
#     f(x) = λ * e^{-λx}  (x >= 0)
#   泊松定理：当 n→∞, p→0, np→λ 时，二项分布→泊松分布
# ================================================================

print("=" * 60)
print("第6题：概率分布（二项/泊松/正态/指数 - 采样与可视化）")
print("=" * 60)

np.random.seed(2026)

# 二项分布 vs 泊松分布
n_trials, p = 1000, 0.02  # n大p小 → 近似泊松
lam = n_trials * p
binom_samples = np.random.binomial(n_trials, p, size=10000)
poisson_samples = np.random.poisson(lam, size=10000)

# 正态分布与指数分布
normal_samples = np.random.normal(0, 1, size=10000)
exp_samples = np.random.exponential(1.0, size=10000)

print(f"二项分布 B({n_trials},{p}): 均值={binom_samples.mean():.3f}, 方差={binom_samples.var():.3f}")
print(f"泊松分布 Po({lam}): 均值={poisson_samples.mean():.3f}, 方差={poisson_samples.var():.3f}")
print(f"正态分布 N(0,1): 均值={normal_samples.mean():.3f}, 方差={normal_samples.var():.3f}")
print(f"指数分布 Exp(1): 均值={exp_samples.mean():.3f}, 方差={exp_samples.var():.3f}")

fig6, axes6 = plt.subplots(2, 2, figsize=(12, 8))
axes6[0, 0].hist(binom_samples, bins=30, density=True, alpha=0.6, color='blue', label='二项')
axes6[0, 0].hist(poisson_samples, bins=30, density=True, alpha=0.6, color='red', label='泊松')
axes6[0, 0].set_title(f'二项 B({n_trials},{p}) vs 泊松 Po({lam})'); axes6[0, 0].legend()

axes6[0, 1].hist(normal_samples, bins=50, density=True, alpha=0.6, color='green')
x_range = np.linspace(-4, 4, 200)
axes6[0, 1].plot(x_range, np.exp(-x_range**2 / 2) / np.sqrt(2 * np.pi), 'r-', linewidth=2, label='理论PDF')
axes6[0, 1].set_title('正态分布 N(0,1)'); axes6[0, 1].legend()

axes6[1, 0].hist(exp_samples, bins=50, density=True, alpha=0.6, color='orange')
x_exp = np.linspace(0, 8, 200)
axes6[1, 0].plot(x_exp, np.exp(-x_exp), 'r-', linewidth=2, label='理论PDF')
axes6[1, 0].set_title('指数分布 Exp(1)'); axes6[1, 0].legend()

# Q-Q图检验正态性
from scipy import stats
stats.probplot(normal_samples[:1000], dist="norm", plot=axes6[1, 1])
axes6[1, 1].set_title('正态Q-Q图')
plt.tight_layout()
save_fig(fig6, 'ex06_distributions.png')

print("\n思考题：为什么二项分布在n大p小时会趋近泊松分布？试从概率公式推导。\n")


# ================================================================
# 第7题：多元正态分布 —— 协方差矩阵与马氏距离
# ================================================================
# 数学推导：
#   多元正态分布 N(μ, Σ) 的密度函数：
#     f(x) = (2π)^{-d/2} |Σ|^{-1/2} exp(-1/2 * (x-μ)^T Σ^{-1} (x-μ))
#   协方差矩阵 Σ 描述各维度之间的线性相关性。
#   马氏距离：D_M(x) = sqrt((x-μ)^T Σ^{-1} (x-μ))
#   它考虑了数据的协方差结构，相当于在"去相关"空间中的欧氏距离。
#   若 Σ = I（单位矩阵），马氏距离退化为欧氏距离。
# ================================================================

print("=" * 60)
print("第7题：多元正态分布（协方差矩阵/马氏距离）")
print("=" * 60)

# 构造一个2D正态分布
mu7 = np.array([0.0, 0.0])
Sigma7 = np.array([[1.0, 0.8], [0.8, 1.0]])  # 强正相关

# 采样
np.random.seed(42)
samples7 = np.random.multivariate_normal(mu7, Sigma7, size=2000)

# 计算马氏距离
Sigma7_inv = np.linalg.inv(Sigma7)
diff = samples7 - mu7
maha_dist = np.sqrt(np.sum((diff @ Sigma7_inv) * diff, axis=1))
euclid_dist = np.linalg.norm(diff, axis=1)

print(f"协方差矩阵 Σ =\n{Sigma7}")
print(f"相关系数: {Sigma7[0,1] / np.sqrt(Sigma7[0,0] * Sigma7[1,1]):.3f}")
print(f"马氏距离均值: {maha_dist.mean():.3f}, 标准差: {maha_dist.std():.3f}")
print(f"欧氏距离均值: {euclid_dist.mean():.3f}, 标准差: {euclid_dist.std():.3f}")

# 可视化：散点图 + 等高线（马氏距离椭圆）
fig7, axes7 = plt.subplots(1, 2, figsize=(12, 5))

# 散点图 + 欧氏距离等高线
axes7[0].scatter(samples7[:, 0], samples7[:, 1], s=2, alpha=0.3, color='blue')
theta = np.linspace(0, 2 * np.pi, 100)
for r in [1, 2, 3]:
    axes7[0].plot(r * np.cos(theta), r * np.sin(theta), 'r--', alpha=0.5)
axes7[0].set_title('欧氏距离等高线（圆形）'); axes7[0].set_aspect('equal')
axes7[0].set_xlim(-4, 4); axes7[0].set_ylim(-4, 4)

# 散点图 + 马氏距离等高线（椭圆）
axes7[1].scatter(samples7[:, 0], samples7[:, 1], s=2, alpha=0.3, color='blue')
# 椭圆参数：对Σ做特征分解
eigvals7, eigvecs7 = np.linalg.eigh(Sigma7)
angle7 = np.degrees(np.arctan2(eigvecs7[1, 0], eigvecs7[0, 0]))
for r in [1, 2, 3]:
    ell = matplotlib.patches.Ellipse(xy=mu7, width=2*r*np.sqrt(eigvals7[0]),
                                      height=2*r*np.sqrt(eigvals7[1]),
                                      angle=angle7, fill=False, color='red', linestyle='--', alpha=0.5)
    axes7[1].add_patch(ell)
axes7[1].set_title('马氏距离等高线（椭圆）'); axes7[1].set_aspect('equal')
axes7[1].set_xlim(-4, 4); axes7[1].set_ylim(-4, 4)
save_fig(fig7, 'ex07_mahalanobis.png')

print("\n思考题：马氏距离在异常检测中如何应用？它比欧氏距离好在哪？\n")


# ================================================================
# 第8题：贝叶斯定理 —— 先验/后验/似然的贝叶斯推断
# ================================================================
# 数学推导：
#   贝叶斯定理：P(H|D) = P(D|H) * P(H) / P(D)
#   其中：
#     P(H)   — 先验概率（观察数据前对假设的信念）
#     P(D|H) — 似然函数（在假设H下观测到数据D的概率）
#     P(H|D) — 后验概率（观察数据后对假设的更新信念）
#     P(D)   — 边缘似然（归一化常数）
#   应用举例：医学检测
#     设疾病 prevalence = 1%，检测灵敏度=99%，特异度=95%
#     P(病|阳性) = P(阳性|病)*P(病) / [P(阳性|病)*P(病) + P(阳性|无病)*P(无病)]
# ================================================================

print("=" * 60)
print("第8题：贝叶斯定理（先验/后验/似然 - 手写贝叶斯推断）")
print("=" * 60)

# 场景：硬币是否偏倚？用贝叶斯推断
# 先验：θ（正面概率）~ Beta(1,1) 即均匀分布
# 似然：观测到 n 次中 k 次正面 → Binomial(k; n, θ)
# 后验：θ|data ~ Beta(1+k, 1+n-k)（Beta-Binomial共轭）

def beta_pdf(x, a, b):
    """手写Beta分布PDF（不调用scipy.stats）"""
    from math import lgamma
    log_B = lgamma(a) + lgamma(b) - lgamma(a + b)
    return np.exp((a - 1) * np.log(x + 1e-15) + (b - 1) * np.log(1 - x + 1e-15) - log_B)

# 实验数据：抛20次，14次正面
n_flips, k_heads = 20, 14
prior_a, prior_b = 1, 1  # 均匀先验
post_a, post_b = prior_a + k_heads, prior_b + n_flips - k_heads  # 共轭更新

theta_grid = np.linspace(0, 1, 500)
prior_pdf = beta_pdf(theta_grid, prior_a, prior_b)
posterior_pdf = beta_pdf(theta_grid, post_a, post_b)
likelihood = theta_grid ** k_heads * (1 - theta_grid) ** (n_flips - k_heads)
likelihood_normalized = likelihood / np.trapezoid(likelihood, theta_grid)

print(f"实验数据: {n_flips}次抛硬币, {k_heads}次正面")
print(f"先验: Beta({prior_a},{prior_b}) → 均匀分布")
print(f"后验: Beta({post_a},{post_b})")
print(f"后验均值(后验估计): {post_a / (post_a + post_b):.4f}")
print(f"MLE估计: {k_heads / n_flips:.4f}")

fig8, ax8 = plt.subplots(figsize=(8, 5))
ax8.plot(theta_grid, prior_pdf, 'b-', label=f'先验 Beta({prior_a},{prior_b})')
ax8.plot(theta_grid, likelihood_normalized, 'g--', label='似然(归一化)')
ax8.plot(theta_grid, posterior_pdf, 'r-', linewidth=2, label=f'后验 Beta({post_a},{post_b})')
ax8.axvline(x=0.5, color='gray', linestyle=':', alpha=0.5, label='θ=0.5')
ax8.set_xlabel('θ (正面概率)'); ax8.set_ylabel('密度')
ax8.set_title('贝叶斯推断：硬币是否偏倚？'); ax8.legend(); ax8.grid(True)
save_fig(fig8, 'ex08_bayesian_inference.png')

# 医学检测示例
prev = 0.01; sensitivity = 0.99; specificity = 0.95
p_positive_given_disease = sensitivity
p_positive_given_healthy = 1 - specificity
p_positive = p_positive_given_disease * prev + p_positive_given_healthy * (1 - prev)
p_disease_given_positive = p_positive_given_disease * prev / p_positive
print(f"\n医学检测: 患病率={prev}, 灵敏度={sensitivity}, 特异度={specificity}")
print(f"阳性时真正患病概率 = {p_disease_given_positive:.4f} ({p_disease_given_positive*100:.1f}%)")

print("\n思考题：为什么医学检测阳性后患病概率如此低？这与直觉为何不同？\n")


# ================================================================
# 第9题：蒙特卡洛方法 —— 随机采样估计π与积分
# ================================================================
# 数学推导：
#   蒙特卡洛方法利用随机采样来近似计算确定性的数学量。
#   估计π：在单位正方形[0,1]×[0,1]中随机撒点，
#     落入四分之一圆内的概率 = (π/4) / 1 = π/4
#     所以 π ≈ 4 * (圆内点数 / 总点数)
#   估计积分 ∫f(x)dx ≈ (b-a)/N * Σf(x_i)，其中x_i~Uniform(a,b)
#   收敛速率：误差 ~ O(1/√N)，与维度无关（这是MC的优势）。
# ================================================================

print("=" * 60)
print("第9题：蒙特卡洛方法（随机采样估计π/积分）")
print("=" * 60)

np.random.seed(123)
N = 100000

# 估计π
x_mc = np.random.uniform(0, 1, N)
y_mc = np.random.uniform(0, 1, N)
inside = x_mc**2 + y_mc**2 <= 1
pi_estimate = 4 * np.sum(inside) / N
print(f"蒙特卡洛估计π = {pi_estimate:.6f} (真实值 = {np.pi:.6f})")
print(f"绝对误差 = {abs(pi_estimate - np.pi):.6f}")

# 估计积分 ∫₀¹ x² dx = 1/3
N2 = 100000
x_samples = np.random.uniform(0, 1, N2)
integral_estimate = np.mean(x_samples**2)
print(f"MC估计 ∫₀¹x²dx = {integral_estimate:.6f} (真实值 = {1/3:.6f})")

# 收敛过程可视化
sample_sizes = np.logspace(2, 6, 50).astype(int)
pi_estimates = []
for ns in sample_sizes:
    xs = np.random.uniform(0, 1, ns)
    ys = np.random.uniform(0, 1, ns)
    pi_estimates.append(4 * np.sum(xs**2 + ys**2 <= 1) / ns)

fig9, axes9 = plt.subplots(1, 2, figsize=(12, 5))

# 散点图
colors = np.where(inside, 'blue', 'red')
axes9[0].scatter(x_mc[:2000], y_mc[:2000], c=colors[:2000], s=1, alpha=0.5)
theta9 = np.linspace(0, np.pi / 2, 100)
axes9[0].plot(np.cos(theta9), np.sin(theta9), 'k-', linewidth=2)
axes9[0].set_title(f'蒙特卡洛估计π = {pi_estimate:.4f}')
axes9[0].set_aspect('equal')

# 收敛曲线
axes9[1].plot(sample_sizes, pi_estimates, 'b.-', label='MC估计')
axes9[1].axhline(y=np.pi, color='r', linestyle='--', label=f'π = {np.pi:.4f}')
axes9[1].set_xscale('log')
axes9[1].set_xlabel('采样数'); axes9[1].set_ylabel('π估计值')
axes9[1].set_title('蒙特卡洛收敛过程'); axes9[1].legend(); axes9[1].grid(True)
save_fig(fig9, 'ex09_monte_carlo.png')

print("\n思考题：蒙特卡洛方法的误差为什么是O(1/√N)？用中心极限定理推导。\n")


# ================================================================
# 第10题：假设检验 —— t检验与卡方检验（手写实现）
# ================================================================
# 数学推导：
#   t检验：检验样本均值是否与假设值有显著差异
#     t = (x̄ - μ₀) / (s/√n)，其中 x̄ 为样本均值，s 为样本标准差
#     t服从自由度为 n-1 的t分布
#     p值 = 2 * P(T > |t|)（双侧检验）
#   卡方检验（拟合优度）：检验观测频数是否符合期望分布
#     χ² = Σ (O_i - E_i)² / E_i，自由度 = 类别数 - 1 - 估计参数数
#     p值 = P(χ² > 检验统计量)
# ================================================================

print("=" * 60)
print("第10题：假设检验（t检验/卡方检验 - 手写实现）")
print("=" * 60)

# 手写t检验
def manual_t_test(sample, mu0):
    """手写单样本t检验"""
    n = len(sample)
    x_bar = np.mean(sample)
    s = np.std(sample, ddof=1)  # 样本标准差
    t_stat = (x_bar - mu0) / (s / np.sqrt(n))
    # 使用scipy的t分布计算p值
    from scipy.stats import t as t_dist
    p_value = 2 * (1 - t_dist.cdf(abs(t_stat), df=n - 1))
    return t_stat, p_value, n - 1

# 手写卡方拟合优度检验
def manual_chi2_test(observed, expected):
    """手写卡方拟合优度检验"""
    chi2_stat = np.sum((observed - expected) ** 2 / expected)
    df = len(observed) - 1
    from scipy.stats import chi2
    p_value = 1 - chi2.cdf(chi2_stat, df=df)
    return chi2_stat, p_value, df

# t检验示例：检验一组学生成绩均值是否为75
np.random.seed(42)
scores = np.random.normal(78, 10, size=30)  # 真实均值78
t_stat, p_val, df_t = manual_t_test(scores, 75)
print(f"t检验: H₀: μ=75 vs H₁: μ≠75")
print(f"  样本均值={np.mean(scores):.2f}, t统计量={t_stat:.4f}, p值={p_val:.4f}, df={df_t}")
print(f"  α=0.05: {'拒绝H₀' if p_val < 0.05 else '不能拒绝H₀'}")

# 卡方检验示例：骰子是否公平
observed_dice = np.array([22, 17, 20, 26, 18, 17])  # 掷骰子120次各面频数
expected_dice = np.array([20, 20, 20, 20, 20, 20])  # 公平时期望
chi2_stat, p_chi, df_chi = manual_chi2_test(observed_dice, expected_dice)
print(f"\n卡方检验: 骰子是否公平？")
print(f"  观测频数: {observed_dice}")
print(f"  期望频数: {expected_dice}")
print(f"  χ²统计量={chi2_stat:.4f}, p值={p_chi:.4f}, df={df_chi}")
print(f"  α=0.05: {'拒绝H₀(骰子不公平)' if p_chi < 0.05 else '不能拒绝H₀(骰子可能是公平的)'}")

# 可视化
fig10, axes10 = plt.subplots(1, 2, figsize=(12, 5))
# t分布与检验统计量
from scipy.stats import t as t_dist
x_t = np.linspace(-4, 4, 200)
axes10[0].plot(x_t, t_dist.pdf(x_t, df=df_t), 'b-', label=f't分布(df={df_t})')
axes10[0].axvline(x=t_stat, color='r', linestyle='--', label=f't={t_stat:.2f}')
axes10[0].fill_between(x_t, 0, t_dist.pdf(x_t, df=df_t),
                        where=(np.abs(x_t) > abs(t_stat)), alpha=0.3, color='red', label='拒绝域')
axes10[0].set_title(f't检验: p={p_val:.4f}'); axes10[0].legend(); axes10[0].grid(True)

# 卡方检验
from scipy.stats import chi2
x_chi = np.linspace(0, 20, 200)
axes10[1].plot(x_chi, chi2.pdf(x_chi, df=df_chi), 'b-', label=f'χ²分布(df={df_chi})')
axes10[1].axvline(x=chi2_stat, color='r', linestyle='--', label=f'χ²={chi2_stat:.2f}')
axes10[1].fill_between(x_chi, 0, chi2.pdf(x_chi, df=df_chi),
                        where=(x_chi > chi2_stat), alpha=0.3, color='red', label='拒绝域')
axes10[1].set_title(f'卡方检验: p={p_chi:.4f}'); axes10[1].legend(); axes10[1].grid(True)
save_fig(fig10, 'ex10_hypothesis_testing.png')

print("\n思考题：p值的真正含义是什么？p值小是否意味着H₀为假的概率小？\n")


# ================================================================
# 第11题：置信区间 —— Bootstrap方法
# ================================================================
# 数学推导：
#   Bootstrap是一种非参数重采样方法，用于估计统计量的分布和置信区间。
#   算法：
#     1. 从原始样本 {x_1,...,x_n} 中有放回地抽取 n 个样本 → 一个Bootstrap样本
#     2. 计算统计量 θ*_b
#     3. 重复 B 次，得到 θ*_1,...,θ*_B
#     4. 置信区间：取 [θ*_(α/2), θ*_(1-α/2)] 分位数
#   原理：Bootstrap样本的分布近似真实统计量的抽样分布。
#   优势：不需要知道总体分布，适用于复杂统计量（如中位数、相关系数）。
# ================================================================

print("=" * 60)
print("第11题：置信区间（Bootstrap方法）")
print("=" * 60)

def bootstrap_ci(data, stat_func, n_bootstrap=10000, confidence=0.95):
    """
    Bootstrap置信区间
    data: 原始数据
    stat_func: 统计函数（如 np.mean, np.median）
    """
    n = len(data)
    boot_stats = np.zeros(n_bootstrap)
    for b in range(n_bootstrap):
        boot_sample = np.random.choice(data, size=n, replace=True)
        boot_stats[b] = stat_func(boot_sample)
    alpha = 1 - confidence
    lower = np.percentile(boot_stats, 100 * alpha / 2)
    upper = np.percentile(boot_stats, 100 * (1 - alpha / 2))
    return boot_stats, lower, upper

np.random.seed(42)
# 生成非正态数据（指数分布的均值）
data11 = np.random.exponential(scale=2.0, size=100)
boot_means, ci_lower, ci_upper = bootstrap_ci(data11, np.mean, n_bootstrap=10000)

print(f"原始数据: 指数分布 Exp(2), n=100")
print(f"样本均值: {np.mean(data11):.4f}")
print(f"Bootstrap 95% 置信区间: [{ci_lower:.4f}, {ci_upper:.4f}]")

# 与正态近似置信区间比较
from scipy.stats import norm
z = norm.ppf(0.975)
se = np.std(data11, ddof=1) / np.sqrt(len(data11))
normal_lower = np.mean(data11) - z * se
normal_upper = np.mean(data11) + z * se
print(f"正态近似 95% 置信区间: [{normal_lower:.4f}, {normal_upper:.4f}]")

# Bootstrap中位数
boot_medians, med_lower, med_upper = bootstrap_ci(data11, np.median, n_bootstrap=10000)
print(f"样本中位数: {np.median(data11):.4f}")
print(f"Bootstrap中位数 95% CI: [{med_lower:.4f}, {med_upper:.4f}]")

fig11, ax11 = plt.subplots(figsize=(8, 5))
ax11.hist(boot_means, bins=50, density=True, alpha=0.6, color='blue', label='Bootstrap均值分布')
ax11.axvline(x=ci_lower, color='red', linestyle='--', label=f'95% CI下界={ci_lower:.2f}')
ax11.axvline(x=ci_upper, color='red', linestyle='--', label=f'95% CI上界={ci_upper:.2f}')
ax11.axvline(x=np.mean(data11), color='green', linestyle='-', linewidth=2, label=f'样本均值={np.mean(data11):.2f}')
ax11.set_xlabel('Bootstrap均值'); ax11.set_ylabel('密度')
ax11.set_title('Bootstrap均值置信区间'); ax11.legend(); ax11.grid(True)
save_fig(fig11, 'ex11_bootstrap.png')

print("\n思考题：Bootstrap为什么对中位数也能给出置信区间，而传统方法困难？\n")


# ================================================================
# 第12题：矩阵微分 —— 梯度/雅可比/海森矩阵
# ================================================================
# 数学推导：
#   标量函数 f: R^n → R 的梯度是一个向量：
#     ∇f = [∂f/∂x_1, ∂f/∂x_2, ..., ∂f/∂x_n]^T
#   向量函数 f: R^n → R^m 的雅可比矩阵 J：
#     J[i,j] = ∂f_i/∂x_j  （m×n矩阵）
#   标量函数的海森矩阵 H（梯度的雅可比）：
#     H[i,j] = ∂²f/∂x_i∂x_j  （n×n对称矩阵）
#   链式法则：若 y = f(g(x))，则 ∂y/∂x = (∂y/∂g)(∂g/∂x) = J_f * J_g
# ================================================================

print("=" * 60)
print("第12题：矩阵微分（梯度/雅可比/海森矩阵）")
print("=" * 60)

# 用sympy进行符号计算
x, y = sp.symbols('x y')
f12 = x**2 * sp.sin(y) + y**3 * sp.exp(x)

# 梯度
grad_x = sp.diff(f12, x)
grad_y = sp.diff(f12, y)
print(f"f(x,y) = {f12}")
print(f"∂f/∂x = {grad_x}")
print(f"∂f/∂y = {grad_y}")
print(f"梯度 ∇f = [{grad_x}, {grad_y}]")

# 海森矩阵
H12 = sp.Matrix([
    [sp.diff(f12, x, x), sp.diff(f12, x, y)],
    [sp.diff(f12, y, x), sp.diff(f12, y, y)]
])
print(f"海森矩阵 H =\n{H12}")

# 雅可比矩阵示例：向量函数
f_vec = sp.Matrix([x**2 + y**2, x * y, sp.sin(x) + sp.cos(y)])
J12 = f_vec.jacobian([x, y])
print(f"\n向量函数 F = {f_vec.T}")
print(f"雅可比矩阵 J =\n{J12}")

# 数值梯度验证
def numerical_gradient(func, point, h=1e-5):
    """数值梯度（中心差分法）"""
    n = len(point)
    grad = np.zeros(n)
    for i in range(n):
        point_plus = point.copy(); point_plus[i] += h
        point_minus = point.copy(); point_minus[i] -= h
        grad[i] = (func(point_plus) - func(point_minus)) / (2 * h)
    return grad

f_num = lambda p: p[0]**2 * np.sin(p[1]) + p[1]**3 * np.exp(p[0])
point = np.array([1.0, 0.5])
num_grad = numerical_gradient(f_num, point)
sym_grad = sp.lambdify((x, y), [grad_x, grad_y])(1.0, 0.5)
print(f"\n在点(1, 0.5)处:")
print(f"  符号梯度: {sym_grad}")
print(f"  数值梯度: {num_grad}")

# 海森矩阵特征值与极值判定
H_num = np.array(H12.subs([(x, 1.0), (y, 0.5)])).astype(float)
eigvals_H = np.linalg.eigvalsh(H_num)
print(f"  海森矩阵特征值: {eigvals_H}")
print(f"  判定: {'局部极小' if all(e > 0 for e in eigvals_H) else '局部极大' if all(e < 0 for e in eigvals_H) else '鞍点'}")

print("\n思考题：在神经网络中，海森矩阵为什么难以计算？拟牛顿法如何近似？\n")


# ================================================================
# 第13题：线性空间与投影 —— 正交投影与格拉姆矩阵
# ================================================================
# 数学推导：
#   向量 b 在向量 a 上的正交投影：
#     proj_a(b) = (<b,a>/<a,a>) * a = (a^T b / a^T a) * a
#   向量 b 在子空间 span{v_1,...,v_k} 上的投影：
#     proj_V(b) = A(A^T A)^{-1} A^T b，其中 A = [v_1,...,v_k]
#   投影矩阵：P = A(A^T A)^{-1} A^T，满足 P² = P（幂等），P^T = P（对称）
#   格拉姆矩阵：G = A^T A，G[i,j] = <v_i, v_j>，描述向量组内积关系
# ================================================================

print("=" * 60)
print("第13题：线性空间与投影（正交投影/格拉姆矩阵）")
print("=" * 60)

# 向量b在平面上的正交投影
v1 = np.array([1.0, 0.0, 1.0])
v2 = np.array([0.0, 1.0, 1.0])
b13 = np.array([1.0, 1.0, 0.0])

A13 = np.column_stack([v1, v2])  # 子空间的基矩阵
# 投影矩阵
G = A13.T @ A13  # 格拉姆矩阵
print(f"格拉姆矩阵 G = A^T A =\n{G}")
print(f"G对角线（各向量模长平方）: {np.diag(G)}")
print(f"G非对角线（向量内积）: G[0,1] = {G[0,1]}")

P13 = A13 @ np.linalg.inv(G) @ A13.T
proj_b = P13 @ b13
residual = b13 - proj_b

print(f"\n向量 b = {b13}")
print(f"投影 proj_V(b) = {proj_b}")
print(f"残差 b - proj = {residual}")
print(f"验证投影矩阵幂等 P²=P? {np.allclose(P13 @ P13, P13)}")
print(f"验证投影矩阵对称 P^T=P? {np.allclose(P13.T, P13)}")
print(f"验证残差正交于子空间: <r,v1>={np.dot(residual, v1):.10f}, <r,v2>={np.dot(residual, v2):.10f}")

# 可视化（2D简化版）
fig13, ax13 = plt.subplots(figsize=(7, 7))
# 用2D示例：向量b到直线y=x的投影
b2d = np.array([3.0, 1.0])
a2d = np.array([1.0, 1.0])
proj2d = (np.dot(b2d, a2d) / np.dot(a2d, a2d)) * a2d

ax13.quiver(0, 0, b2d[0], b2d[1], angles='xy', scale_units='xy', scale=1, color='blue', width=0.02, label='b')
ax13.quiver(0, 0, a2d[0], a2d[1], angles='xy', scale_units='xy', scale=1, color='green', width=0.02, label='a (子空间基)')
ax13.quiver(0, 0, proj2d[0], proj2d[1], angles='xy', scale_units='xy', scale=1, color='red', width=0.02, label='proj_a(b)')
ax13.plot([b2d[0], proj2d[0]], [b2d[1], proj2d[1]], 'k--', label='残差(正交)')
ax13.set_xlim(-0.5, 4); ax13.set_ylim(-0.5, 4)
ax13.set_aspect('equal'); ax13.legend(); ax13.grid(True)
ax13.set_title('正交投影（2D示意）')
save_fig(fig13, 'ex13_orthogonal_projection.png')

print("\n思考题：最小二乘法与正交投影有什么关系？残差为什么垂直于投影？\n")


# ================================================================
# 第14题：协方差与相关 —— 协方差矩阵与PCA数学推导
# ================================================================
# 数学推导：
#   协方差矩阵：Σ = E[(X-μ)(X-μ)^T]，样本估计 Σ = (1/(n-1)) X_c^T X_c
#   其中 X_c 是中心化后的数据矩阵。
#   PCA（主成分分析）：
#     1. 中心化数据 X_c = X - mean(X)
#     2. 计算协方差矩阵 C = X_c^T X_c / (n-1)
#     3. 对C做特征分解 C = V Λ V^T
#     4. 按特征值降序排列，取前k个特征向量 → 投影矩阵
#     5. 降维结果 Z = X_c @ V[:, :k]
#   数学本质：PCA寻找数据方差最大的方向（即协方差矩阵的最大特征向量方向）
#   解释率 = λ_i / Σλ_j
# ================================================================

print("=" * 60)
print("第14题：协方差与相关（协方差矩阵/PCA数学推导）")
print("=" * 60)

np.random.seed(42)
# 构造有相关性的2D数据
mean14 = [0, 0]
cov14 = [[3, 2], [2, 2]]
X14 = np.random.multivariate_normal(mean14, cov14, 200)

# 手写PCA
X_centered = X14 - np.mean(X14, axis=0)
cov_matrix = np.cov(X_centered, rowvar=False)
print(f"协方差矩阵 =\n{cov_matrix}")
print(f"相关系数 = {cov_matrix[0,1] / np.sqrt(cov_matrix[0,0] * cov_matrix[1,1]):.4f}")

# 特征分解
eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
# 排序
idx = np.argsort(eigenvalues)[::-1]
eigenvalues = eigenvalues[idx]
eigenvectors = eigenvectors[:, idx]
print(f"特征值: {eigenvalues}")
print(f"特征向量(主成分):\n{eigenvectors}")
print(f"方差解释率: {eigenvalues / eigenvalues.sum()}")

# 投影到主成分空间
Z14 = X_centered @ eigenvectors
# 重构（用所有主成分）
X_reconstructed = Z14 @ eigenvectors.T + np.mean(X14, axis=0)
print(f"重构误差: {np.linalg.norm(X14 - X_reconstructed):.10f}")

# 可视化
fig14, axes14 = plt.subplots(1, 2, figsize=(12, 5))
# 原始数据 + 主成分方向
axes14[0].scatter(X14[:, 0], X14[:, 1], s=5, alpha=0.5, color='blue')
mean_pt = np.mean(X14, axis=0)
for i, (ev, val) in enumerate(zip(eigenvectors.T, eigenvalues)):
    scale = 2 * np.sqrt(val)  # 2倍标准差
    axes14[0].quiver(mean_pt[0], mean_pt[1], ev[0]*scale, ev[1]*scale,
                      angles='xy', scale_units='xy', scale=1, color=['red', 'green'][i],
                      width=0.02, label=f'PC{i+1} (λ={val:.2f})')
axes14[0].set_title('原始数据与主成分方向'); axes14[0].legend(); axes14[0].grid(True)
axes14[0].set_aspect('equal')

# 投影后数据（去相关）
axes14[1].scatter(Z14[:, 0], Z14[:, 1], s=5, alpha=0.5, color='red')
axes14[1].set_title('PCA变换后（去相关）'); axes14[1].grid(True)
axes14[1].set_aspect('equal')
save_fig(fig14, 'ex14_pca.png')

print("\n思考题：PCA与SVD有什么关系？为什么大数据集用SVD而不是直接算协方差矩阵？\n")


# ================================================================
# 第15题：概率不等式 —— 马尔可夫/切比雪夫/大数定律验证
# ================================================================
# 数学推导：
#   马尔可夫不等式（对非负随机变量X, E[X] = μ）：
#     P(X >= a) <= μ / a  (a > 0)
#   切比雪夫不等式（对任意X, E[X]=μ, Var(X)=σ²）：
#     P(|X - μ| >= kσ) <= 1/k²
#   大数定律（LLN）：
#     样本均值 X̄_n → μ 当 n→∞（依概率收敛）
#   中心极限定理（CLT）：
#     √n (X̄_n - μ) / σ → N(0,1) 当 n→∞
# ================================================================

print("=" * 60)
print("第15题：概率不等式（马尔可夫/切比雪夫/大数定律验证）")
print("=" * 60)

np.random.seed(42)

# --- 验证马尔可夫不等式 ---
# 取指数分布 X ~ Exp(1), E[X] = 1
n_samples = 100000
X_exp = np.random.exponential(1.0, n_samples)
mu_exp = 1.0
a_values = [2, 3, 4, 5]
print("马尔可夫不等式验证 (X~Exp(1), μ=1):")
print(f"{'a':>5} | {'P(X≥a) 实际':>12} | {'μ/a 上界':>10} | {'满足?':>6}")
for a in a_values:
    actual = np.mean(X_exp >= a)
    bound = mu_exp / a
    print(f"{a:5.1f} | {actual:12.4f} | {bound:10.4f} | {'是' if actual <= bound else '否'}")

# --- 验证切比雪夫不等式 ---
# 取正态分布 X ~ N(0,1), σ=1
X_norm = np.random.normal(0, 1, n_samples)
mu_norm, sigma_norm = 0, 1
k_values = [1.5, 2, 2.5, 3]
print("\n切比雪夫不等式验证 (X~N(0,1), σ=1):")
print(f"{'k':>5} | {'P(|X-μ|≥kσ) 实际':>16} | {'1/k² 上界':>10} | {'满足?':>6}")
for k in k_values:
    actual = np.mean(np.abs(X_norm - mu_norm) >= k * sigma_norm)
    bound = 1.0 / k**2
    print(f"{k:5.1f} | {actual:16.4f} | {bound:10.4f} | {'是' if actual <= bound else '否'}")

# --- 验证大数定律 ---
# 抛骰子（均匀1-6），样本均值应收敛到3.5
n_trials_list = [10, 100, 1000, 10000, 100000, 1000000]
print("\n大数定律验证 (骰子期望=3.5):")
running_means = []
cumulative_sum = 0
for n in range(1, 100001):
    roll = np.random.randint(1, 7)
    cumulative_sum += roll
    running_means.append(cumulative_sum / n)

for n in [10, 100, 1000, 10000, 100000]:
    print(f"  n={n:>7d}: 样本均值 = {running_means[n-1]:.4f}")

# 可视化
fig15, axes15 = plt.subplots(1, 2, figsize=(12, 5))

# 大数定律收敛
axes15[0].plot(range(1, 100001), running_means, 'b-', alpha=0.7, linewidth=0.5)
axes15[0].axhline(y=3.5, color='r', linestyle='--', label='真实期望 μ=3.5')
axes15[0].set_xscale('log')
axes15[0].set_xlabel('试验次数 n'); axes15[0].set_ylabel('样本均值')
axes15[0].set_title('大数定律: 样本均值→期望'); axes15[0].legend(); axes15[0].grid(True)

# 切比雪夫上界 vs 实际
k_range = np.linspace(1, 4, 50)
actual_probs = [np.mean(np.abs(X_norm) >= k) for k in k_range]
chebyshev_bounds = 1.0 / k_range**2
axes15[1].plot(k_range, actual_probs, 'b-', label='实际 P(|X-μ|≥kσ)')
axes15[1].plot(k_range, chebyshev_bounds, 'r--', label='切比雪夫上界 1/k²')
axes15[1].set_xlabel('k'); axes15[1].set_ylabel('概率')
axes15[1].set_title('切比雪夫不等式: 上界 vs 实际'); axes15[1].legend(); axes15[1].grid(True)
save_fig(fig15, 'ex15_probability_inequalities.png')

print("\n思考题：切比雪夫不等式的上界很松，为什么它仍然重要？它在证明大数定律中起什么作用？\n")

print("=" * 60)
print("文件1全部完成！共15题。")
print("=" * 60)
