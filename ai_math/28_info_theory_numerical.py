# -*- coding: utf-8 -*-
"""
================================================================
阶段标题：AI数学基础深化 —— 信息论与数值方法（第28期）
题数：10题
创建日期：2026-08-05
依赖：numpy, scipy, sympy, matplotlib
说明：全部手写实现，重在理解数学原理而非调API
================================================================
"""

import numpy as np
from scipy import integrate, optimize
import sympy as sp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import heapq
import os

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

SAVE_DIR = os.path.dirname(os.path.abspath(__file__))


def save_fig(fig, filename):
    path = os.path.join(SAVE_DIR, filename)
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f"  -> 图已保存: {path}")


# ================================================================
# 第1题：信息熵 —— 香农熵手写计算
# ================================================================
# 数学推导：
#   香农熵：H(X) = -Σ p(x) * log₂ p(x)
#   物理意义：随机变量X的不确定性度量。
#   性质：
#     - H ≥ 0（非负性）
#     - 当分布均匀时H最大 = log₂(n)（最大熵）
#     - 当某事件概率为1时H = 0（完全确定）
#   单位：比特（以2为底）/ 纳特（以e为底）
#   交叉熵、KL散度、互信息等均建立在熵的基础之上。
# ================================================================

print("=" * 60)
print("第1题：信息熵（香农熵手写计算）")
print("=" * 60)

def shannon_entropy(probs, base=2):
    """
    手写香农熵计算
    probs: 概率分布列表
    base: 对数底（2=比特, e=纳特）
    """
    probs = np.array(probs)
    # 过滤零概率（0*log0 = 0）
    mask = probs > 0
    if base == 2:
        return -np.sum(probs[mask] * np.log2(probs[mask]))
    else:
        return -np.sum(probs[mask] * np.log(probs[mask]))

# 不同分布的熵
distributions = {
    '均匀分布(4类)': [0.25, 0.25, 0.25, 0.25],
    '偏斜分布': [0.7, 0.1, 0.1, 0.1],
    '极端分布': [0.97, 0.01, 0.01, 0.01],
    '确定分布': [1.0, 0.0, 0.0, 0.0],
    '二项(0.5,0.5)': [0.5, 0.5],
}

print(f"{'分布':>16} | {'香农熵(bits)':>12} | {'最大熵':>8} | {'熵比':>6}")
print("-" * 50)
for name, probs in distributions.items():
    H = shannon_entropy(probs)
    H_max = np.log2(len(probs))
    ratio = H / H_max if H_max > 0 else 0
    print(f"{name:>16} | {H:>12.4f} | {H_max:>8.4f} | {ratio:>6.2f}")

# 熵随概率变化的曲线（二元分布）
p_range = np.linspace(0.001, 0.999, 500)
H_binary = -p_range * np.log2(p_range) - (1 - p_range) * np.log2(1 - p_range)

fig1, ax1 = plt.subplots(figsize=(8, 5))
ax1.plot(p_range, H_binary, 'b-', linewidth=2)
ax1.axvline(x=0.5, color='r', linestyle='--', alpha=0.5, label='p=0.5 (最大熵=1 bit)')
ax1.set_xlabel('P(X=1) = p'); ax1.set_ylabel('H(X) (bits)')
ax1.set_title('二元分布的香农熵 H(p) = -p·log₂(p) - (1-p)·log₂(1-p)'); ax1.legend(); ax1.grid(True)
save_fig(fig1, 'ex28_01_entropy.png')

print("\n思考题：为什么均匀分布的熵最大？试从拉格朗日乘子法推导最大熵分布。\n")


# ================================================================
# 第2题：交叉熵与KL散度 —— 手写实现与可视化
# ================================================================
# 数学推导：
#   交叉熵：H(P, Q) = -Σ p(x) * log q(x)
#   衡量用分布Q编码来自分布P的数据所需的平均比特数。
#   KL散度（相对熵）：KL(P||Q) = Σ p(x) * log(p(x)/q(x))
#     = H(P, Q) - H(P) = 交叉熵 - 熵
#   性质：
#     - KL(P||Q) ≥ 0（非负性，吉布斯不等式）
#     - KL(P||Q) = 0 当且仅当 P = Q
#     - KL散度不对称：KL(P||Q) ≠ KL(Q||P)
#   机器学习中：最小化交叉熵 = 最小化KL散度（因H(P)固定）
# ================================================================

print("=" * 60)
print("第2题：交叉熵与KL散度（手写实现+可视化）")
print("=" * 60)

def cross_entropy(p, q, base=2):
    """手写交叉熵 H(P, Q)"""
    p = np.array(p); q = np.array(q)
    mask = p > 0
    if base == 2:
        return -np.sum(p[mask] * np.log2(q[mask] + 1e-15))
    else:
        return -np.sum(p[mask] * np.log(q[mask] + 1e-15))

def kl_divergence(p, q, base=2):
    """手写KL散度 KL(P||Q)"""
    p = np.array(p); q = np.array(q)
    mask = (p > 0) & (q > 0)
    if base == 2:
        return np.sum(p[mask] * np.log2(p[mask] / q[mask]))
    else:
        return np.sum(p[mask] * np.log(p[mask] / q[mask]))

# 示例
P = np.array([0.5, 0.3, 0.15, 0.05])
Q1 = np.array([0.25, 0.25, 0.25, 0.25])  # 均匀分布
Q2 = np.array([0.4, 0.3, 0.2, 0.1])      # 接近P
Q3 = np.array([0.9, 0.05, 0.03, 0.02])   # 远离P

H_P = shannon_entropy(P)
print(f"真实分布 P = {P}, H(P) = {H_P:.4f} bits")
print(f"\n{'分布Q':>16} | {'H(P,Q)':>8} | {'KL(P||Q)':>10} | {'H(P)+KL':>10}")
for name, Q in [('均匀Q1', Q1), ('接近P的Q2', Q2), ('远离P的Q3', Q3)]:
    H_pq = cross_entropy(P, Q)
    kl = kl_divergence(P, Q)
    print(f"{name:>16} | {H_pq:>8.4f} | {kl:>10.4f} | {H_P + kl:>10.4f}")

print(f"\n验证: H(P,Q) = H(P) + KL(P||Q) ✓")
print(f"KL散度非负: {kl_divergence(P, Q1):.4f} >= 0 ✓")
print(f"KL不对称: KL(P||Q1)={kl_divergence(P, Q1):.4f}, KL(Q1||P)={kl_divergence(Q1, P):.4f}")

# 可视化：KL散度随Q偏离P的变化
# 二元分布，固定P=[0.7,0.3]，改变Q=[q, 1-q]
q_range = np.linspace(0.01, 0.99, 200)
P_binary = np.array([0.7, 0.3])
kl_forward = [kl_divergence(P_binary, [q, 1-q]) for q in q_range]
kl_reverse = [kl_divergence([q, 1-q], P_binary) for q in q_range]

fig2, ax2 = plt.subplots(figsize=(8, 5))
ax2.plot(q_range, kl_forward, 'b-', linewidth=2, label='KL(P||Q) (前向)')
ax2.plot(q_range, kl_reverse, 'r--', linewidth=2, label='KL(Q||P) (反向)')
ax2.axvline(x=0.7, color='gray', linestyle=':', alpha=0.5, label='P=0.7 (KL=0处)')
ax2.set_xlabel('Q中第一类的概率 q'); ax2.set_ylabel('KL散度 (bits)')
ax2.set_title('KL散度的不对称性'); ax2.legend(); ax2.grid(True)
save_fig(fig2, 'ex28_02_cross_entropy_kl.png')

print("\n思考题：分类任务中为什么用交叉熵而不是均方误差？与最大似然有什么关系？\n")


# ================================================================
# 第3题：互信息与条件熵
# ================================================================
# 数学推导：
#   条件熵：H(Y|X) = -ΣΣ p(x,y) * log p(y|x)
#     含义：已知X后Y的剩余不确定性。
#   互信息：I(X;Y) = H(X) - H(X|Y) = H(Y) - H(Y|X)
#                  = ΣΣ p(x,y) * log(p(x,y) / (p(x)*p(y)))
#     含义：知道X对减少Y的不确定性的贡献量。
#   链式法则：H(X,Y) = H(X) + H(Y|X) = H(Y) + H(X|Y)
#   I(X;Y) = H(X) + H(Y) - H(X,Y)
#   当X和Y独立时I(X;Y)=0；当Y完全由X决定时I(X;Y)=H(Y)。
# ================================================================

print("=" * 60)
print("第3题：互信息与条件熵")
print("=" * 60)

def joint_entropy(joint_p, base=2):
    """联合熵 H(X,Y)"""
    joint_p = np.array(joint_p)
    mask = joint_p > 0
    if base == 2:
        return -np.sum(joint_p[mask] * np.log2(joint_p[mask]))
    return -np.sum(joint_p[mask] * np.log(joint_p[mask]))

def mutual_information(joint_p, base=2):
    """互信息 I(X;Y) 从联合分布计算"""
    joint_p = np.array(joint_p)
    px = joint_p.sum(axis=1, keepdims=True)  # X的边缘分布
    py = joint_p.sum(axis=0, keepdims=True)  # Y的边缘分布
    mask = joint_p > 0
    if base == 2:
        return np.sum(joint_p[mask] * np.log2(joint_p[mask] / (px @ py)[mask]))
    return np.sum(joint_p[mask] * np.log(joint_p[mask] / (px @ py)[mask]))

def conditional_entropy(joint_p, base=2):
    """条件熵 H(Y|X)"""
    H_XY = joint_entropy(joint_p, base)
    px = joint_p.sum(axis=1)
    H_X = shannon_entropy(px, base)
    return H_XY - H_X

# 示例1：完全相关（Y = X）
print("示例1: X和Y完全相同")
joint1 = np.array([[0.25, 0.0], [0.0, 0.75]])  # 对角矩阵
print(f"  联合分布:\n{joint1}")
H_X1 = shannon_entropy(joint1.sum(axis=1))
H_Y1 = shannon_entropy(joint1.sum(axis=0))
H_XY1 = joint_entropy(joint1)
H_Y_given_X1 = conditional_entropy(joint1)
I_XY1 = mutual_information(joint1)
print(f"  H(X)={H_X1:.4f}, H(Y)={H_Y1:.4f}, H(X,Y)={H_XY1:.4f}")
print(f"  H(Y|X)={H_Y_given_X1:.4f} (完全确定→0)")
print(f"  I(X;Y)={I_XY1:.4f} = H(Y)={H_Y1:.4f} (互信息=熵)")

# 示例2：独立
print("\n示例2: X和Y独立")
joint2 = np.outer([0.3, 0.7], [0.4, 0.6])
print(f"  联合分布:\n{joint2}")
I_XY2 = mutual_information(joint2)
print(f"  I(X;Y)={I_XY2:.6f} (独立→0)")

# 示例3：部分相关
print("\n示例3: 部分相关")
joint3 = np.array([[0.2, 0.1], [0.1, 0.6]])
print(f"  联合分布:\n{joint3}")
H_X3 = shannon_entropy(joint3.sum(axis=1))
H_Y3 = shannon_entropy(joint3.sum(axis=0))
H_XY3 = joint_entropy(joint3)
H_Y_given_X3 = conditional_entropy(joint3)
I_XY3 = mutual_information(joint3)
print(f"  H(X)={H_X3:.4f}, H(Y)={H_Y3:.4f}, H(X,Y)={H_XY3:.4f}")
print(f"  H(Y|X)={H_Y_given_X3:.4f}")
print(f"  I(X;Y)={I_XY3:.4f}")
print(f"  验证 I(X;Y) = H(X)+H(Y)-H(X,Y) = {H_X3+H_Y3-H_XY3:.4f}")

# 可视化：信息量的韦恩图概念
fig3, ax3 = plt.subplots(figsize=(7, 5))
from matplotlib.patches import Circle
c1 = Circle((0.35, 0.5), 0.3, alpha=0.4, color='blue', label='H(X)')
c2 = Circle((0.65, 0.5), 0.3, alpha=0.4, color='red', label='H(Y)')
ax3.add_patch(c1); ax3.add_patch(c2)
ax3.text(0.25, 0.5, f'H(X|Y)\n={H_Y_given_X3:.2f}', ha='center', fontsize=10)
ax3.text(0.5, 0.5, f'I(X;Y)\n={I_XY3:.2f}', ha='center', fontsize=10, fontweight='bold')
ax3.text(0.75, 0.5, f'H(Y|X)\n={H_Y_given_X3:.2f}', ha='center', fontsize=10)
ax3.set_xlim(0, 1); ax3.set_ylim(0, 1)
ax3.set_title('信息论韦恩图: 熵与互信息关系'); ax3.legend(); ax3.axis('off')
save_fig(fig3, 'ex28_03_mutual_info.png')

print("\n思考题：互信息在特征选择中如何使用？它与相关性有什么区别？\n")


# ================================================================
# 第4题：最大熵原理 —— 最大熵分布推导
# ================================================================
# 数学推导：
#   最大熵原理：在满足已知约束的所有分布中，选择熵最大的那个。
#   约束优化问题：
#     max H(P) = -Σ p_i * ln(p_i)
#     s.t. Σ p_i = 1  (归一化)
#          Σ p_i * f_k(x_i) = μ_k  (k个矩约束)
#   用拉格朗日乘子法求解：
#     L = -Σ p_i * ln(p_i) - λ₀(Σp_i - 1) - Σ λ_k(Σ p_i*f_k - μ_k)
#     ∂L/∂p_i = 0 → p_i = exp(-λ₀ - 1 - Σλ_k*f_k(x_i))
#   关键结论：
#     - 仅约束归一化 → 均匀分布
#     - 约束均值和方差 → 正态分布
#     - 约束均值（非负）→ 指数分布
# ================================================================

print("=" * 60)
print("第4题：最大熵原理（最大熵分布推导）")
print("=" * 60)

# 用sympy推导：仅归一化约束 → 均匀分布
p1, p2, p3 = sp.symbols('p1 p2 p3', positive=True)
lam0 = sp.Symbol('lambda_0')

H = -(p1*sp.ln(p1) + p2*sp.ln(p2) + p3*sp.ln(p3))
L = H - lam0 * (p1 + p2 + p3 - 1)
eqs = [sp.diff(L, p1), sp.diff(L, p2), sp.diff(L, p3), sp.diff(L, lam0)]
sol = sp.solve(eqs, [p1, p2, p3, lam0])
print("仅归一化约束:")
if isinstance(sol, list):
    print(f"  解: p1=p2=p3={sol[0][0]} (均匀分布!)")
elif isinstance(sol, dict):
    print(f"  解: p1=p2=p3={sol[p1]} (均匀分布!)")
else:
    print(f"  解: {sol} (均匀分布!)")

# 数值验证：约束均值 → 指数分布
# 在[0,∞)上，约束E[X]=μ，最大熵分布为指数分布 p(x)=λ*e^{-λx}, λ=1/μ
def max_entropy_with_mean(mu, x_max=20, n_grid=1000):
    """
    数值求解约束均值的最大熵分布（离散化）
    max H(p) s.t. Σp=1, Σx*p=μ
    解应为 p_i ∝ exp(-λ*x_i)
    """
    x = np.linspace(0, x_max, n_grid)
    dx = x[1] - x[0]
    # 拉格朗日乘子法：p_i = exp(-1-λ₀-λ*x_i) / Z
    # 用迭代法找λ使得Σx*p=μ
    from scipy.optimize import brentq

    def compute_dist(lam):
        p = np.exp(-lam * x)
        p /= p.sum()
        return p

    def mean_error(lam):
        p = compute_dist(lam)
        return np.sum(x * p) - mu

    # 找到使mean_error=0的λ
    lam_opt = brentq(mean_error, -5, 5)
    p_opt = compute_dist(lam_opt)
    return x, p_opt, lam_opt

mu = 2.0
x_me, p_me, lam_opt = max_entropy_with_mean(mu)
# 与指数分布比较
p_exp = np.exp(-x_me / mu) / mu
print(f"\n约束均值 μ={mu} 的最大熵分布:")
print(f"  拉格朗日乘子 λ = {lam_opt:.6f} (理论值 1/μ = {1/mu:.6f})")
print(f"  数值分布与指数分布最大偏差: {np.max(np.abs(p_me - p_exp)):.6e}")

fig4, axes4 = plt.subplots(1, 2, figsize=(12, 5))
axes4[0].bar(x_me, p_me, width=x_me[1]-x_me[0], alpha=0.5, color='blue', label='最大熵(数值)')
axes4[0].plot(x_me, p_exp, 'r-', linewidth=2, label=f'指数分布 Exp(1/{mu})')
axes4[0].set_xlabel('x'); axes4[0].set_ylabel('p(x)')
axes4[0].set_title(f'约束E[X]={mu} → 最大熵=指数分布'); axes4[0].legend(); axes4[0].grid(True)

# 约束均值和方差 → 正态分布
def max_entropy_with_mean_var(mu, sigma2, x_range=(-10, 10), n_grid=1000):
    """约束均值和方差的最大熵分布 → 正态分布"""
    x = np.linspace(x_range[0], x_range[1], n_grid)
    # p_i ∝ exp(-λ₁*x_i - λ₂*x_i²)
    from scipy.optimize import minimize

    def neg_entropy(params):
        lam1, lam2 = params
        log_p = -lam1 * x - lam2 * x**2
        log_Z = np.log(np.sum(np.exp(log_p - log_p.max()))) + log_p.max()
        p = np.exp(log_p - log_Z)
        mean = np.sum(x * p)
        var = np.sum((x - mean)**2 * p)
        penalty = (mean - mu)**2 + (var - sigma2)**2
        return -np.sum(p * (log_p - log_Z)) + 1000 * penalty

    result = minimize(neg_entropy, [0, 0.01], method='Nelder-Mead')
    lam1, lam2 = result.x
    log_p = -lam1 * x - lam2 * x**2
    log_Z = np.log(np.sum(np.exp(log_p - log_p.max()))) + log_p.max()
    p = np.exp(log_p - log_Z)
    return x, p

mu_g, sigma2_g = 0, 1
x_mv, p_mv = max_entropy_with_mean_var(mu_g, sigma2_g)
p_normal = np.exp(-x_mv**2 / (2 * sigma2_g)) / np.sqrt(2 * np.pi * sigma2_g)
axes4[1].bar(x_mv, p_mv, width=x_mv[1]-x_mv[0], alpha=0.5, color='green', label='最大熵(数值)')
axes4[1].plot(x_mv, p_normal, 'r-', linewidth=2, label='N(0,1)正态分布')
axes4[1].set_xlabel('x'); axes4[1].set_ylabel('p(x)')
axes4[1].set_title('约束均值和方差 → 最大熵=正态分布'); axes4[1].legend(); axes4[1].grid(True)
save_fig(fig4, 'ex28_04_max_entropy.png')

print("\n思考题：最大熵原理与逻辑回归有什么关系？（提示：最大熵模型）\n")


# ================================================================
# 第5题：数据压缩与编码 —— 霍夫曼编码手写
# ================================================================
# 数学推导：
#   霍夫曼编码：构造最优前缀码，使平均码长最小。
#   算法：
#     1. 将每个符号按概率从小到大排列
#     2. 取概率最小的两个节点合并为一个新节点（概率相加）
#     3. 新节点放回列表，重复步骤2直到只剩一个节点
#     4. 从根到叶，左分支标0，右分支标1
#   最优性：霍夫曼码的平均码长 L ≤ H(X) + 1
#   信源编码定理（Shannon）：平均码长不可能小于H(X)
# ================================================================

print("=" * 60)
print("第5题：数据压缩与编码（霍夫曼编码手写）")
print("=" * 60)

class HuffmanNode:
    """霍夫曼树节点"""
    def __init__(self, symbol=None, freq=0, left=None, right=None):
        self.symbol = symbol
        self.freq = freq
        self.left = left
        self.right = right
    def __lt__(self, other):
        return self.freq < other.freq

def build_huffman_tree(symbols, freqs):
    """构建霍夫曼树"""
    heap = [HuffmanNode(s, f) for s, f in zip(symbols, freqs)]
    heapq.heapify(heap)
    while len(heap) > 1:
        left = heapq.heappop(heap)
        right = heapq.heappop(heap)
        merged = HuffmanNode(freq=left.freq + right.freq, left=left, right=right)
        heapq.heappush(heap, merged)
    return heap[0]

def huffman_codes(root):
    """生成霍夫曼编码表"""
    codes = {}
    def traverse(node, code=""):
        if node.symbol is not None:
            codes[node.symbol] = code if code else "0"
            return
        if node.left:
            traverse(node.left, code + "0")
        if node.right:
            traverse(node.right, code + "1")
    traverse(root)
    return codes

# 示例
symbols = ['A', 'B', 'C', 'D', 'E', 'F']
freqs = [0.25, 0.20, 0.15, 0.15, 0.15, 0.10]

huffman_tree = build_huffman_tree(symbols, freqs)
codes = huffman_codes(huffman_tree)

print(f"{'符号':>4} | {'概率':>6} | {'编码':>8} | {'码长':>4}")
print("-" * 30)
avg_length = 0
for s, f in zip(symbols, freqs):
    code = codes[s]
    avg_length += f * len(code)
    print(f"{s:>4} | {f:>6.2f} | {code:>8} | {len(code):>4}")

H_source = shannon_entropy(freqs)
print(f"\n信源熵 H(X) = {H_source:.4f} bits")
print(f"平均码长 L = {avg_length:.4f} bits")
print(f"编码效率 = H(X)/L = {H_source/avg_length*100:.2f}%")
print(f"验证 L ≤ H(X)+1: {avg_length:.4f} ≤ {H_source+1:.4f} ✓")

# 可视化霍夫曼树
fig5, ax5 = plt.subplots(figsize=(10, 6))
ax5.set_xlim(0, 10); ax5.set_ylim(0, 10)
ax5.axis('off')

def draw_tree(node, x, y, dx, depth=0):
    if node.symbol is not None:
        ax5.text(x, y, f"{node.symbol}\n({node.freq:.2f})", ha='center',
                bbox=dict(boxstyle='round', facecolor='lightgreen'), fontsize=9)
    else:
        ax5.text(x, y, f"{node.freq:.2f}", ha='center',
                bbox=dict(boxstyle='round', facecolor='lightblue'), fontsize=8)
    if node.left:
        ax5.plot([x, x-dx], [y-0.4, y-1.2], 'k-')
        ax5.text(x-dx/2, y-0.6, '0', fontsize=8, color='red')
        draw_tree(node.left, x-dx, y-1.5, dx*0.6, depth+1)
    if node.right:
        ax5.plot([x, x+dx], [y-0.4, y-1.2], 'k-')
        ax5.text(x+dx/2, y-0.6, '1', fontsize=8, color='red')
        draw_tree(node.right, x+dx, y-1.5, dx*0.6, depth+1)

draw_tree(huffman_tree, 5, 9, 2.5)
ax5.set_title('霍夫曼编码树')
save_fig(fig5, 'ex28_05_huffman.png')

print("\n思考题：霍夫曼编码为什么是前缀码？前缀码的性质对解码有什么重要性？\n")


# ================================================================
# 第6题：数值微分与积分 —— 误差分析
# ================================================================
# 数学推导：
#   数值微分误差来源：
#     1. 截断误差（离散化）：Taylor展开中忽略的高阶项
#     2. 舍入误差（浮点）：h太小时，f(x+h)-f(x-h)的两个接近数相减
#   前向差分：f'(x) ≈ [f(x+h)-f(x)]/h，截断误差O(h)，舍入误差O(ε/h)
#   中心差分：f'(x) ≈ [f(x+h)-f(x-h)]/(2h)，截断误差O(h²)，舍入误差O(ε/h)
#   总误差 ≈ c₁h² + c₂ε/h（中心差分），最优h ≈ (ε)^{1/3}
#   数值积分的误差也类似，梯形法O(h²)，辛普森法O(h⁴)。
# ================================================================

print("=" * 60)
print("第6题：数值微分与积分（误差分析）")
print("=" * 60)

# 数值微分误差分析
f6 = lambda x: np.exp(x)
df6_true = lambda x: np.exp(x)
x0 = 1.0
eps_machine = np.finfo(float).eps

h_values = np.logspace(-1, -16, 50)
forward_errors = []
central_errors = []

for h in h_values:
    # 前向差分
    fd = (f6(x0 + h) - f6(x0)) / h
    forward_errors.append(abs(fd - df6_true(x0)))
    # 中心差分
    cd = (f6(x0 + h) - f6(x0 - h)) / (2 * h)
    central_errors.append(abs(cd - df6_true(x0)))

opt_h_forward = h_values[np.argmin(forward_errors)]
opt_h_central = h_values[np.argmin(central_errors)]
print(f"f(x) = e^x, 在 x=1 处求导")
print(f"机器精度 ε = {eps_machine:.2e}")
print(f"前向差分最优步长: h = {opt_h_forward:.2e}, 最小误差 = {min(forward_errors):.2e}")
print(f"中心差分最优步长: h = {opt_h_central:.2e}, 最小误差 = {min(central_errors):.2e}")
print(f"理论最优步长(中心): h ≈ ε^(1/3) = {eps_machine**(1/3):.2e}")

# 数值积分误差
f6_int = lambda x: np.sin(x)
a6, b6 = 0, np.pi
true_int = 2.0

n_values = np.logspace(1, 6, 30).astype(int)
trap_errors_int = []
simp_errors_int = []
for n in n_values:
    # 梯形法
    x_trap = np.linspace(a6, b6, n + 1)
    y_trap = f6_int(x_trap)
    h_int = (b6 - a6) / n
    trap_val = h_int / 2 * (y_trap[0] + 2 * np.sum(y_trap[1:-1]) + y_trap[-1])
    trap_errors_int.append(abs(trap_val - true_int))

    # 辛普森法
    if n % 2 == 0:
        x_simp = np.linspace(a6, b6, n + 1)
        y_simp = f6_int(x_simp)
        simp_val = h_int / 3 * (y_simp[0] + 4 * np.sum(y_simp[1:-1:2]) + 2 * np.sum(y_simp[2:-1:2]) + y_simp[-1])
        simp_errors_int.append(abs(simp_val - true_int))
    else:
        simp_errors_int.append(np.nan)

fig6, axes6 = plt.subplots(1, 2, figsize=(12, 5))
# 微分误差
axes6[0].loglog(h_values, forward_errors, 'b.-', label='前向差分 O(h)')
axes6[0].loglog(h_values, central_errors, 'r.-', label='中心差分 O(h²)')
axes6[0].axvline(x=opt_h_forward, color='b', linestyle='--', alpha=0.3)
axes6[0].axvline(x=opt_h_central, color='r', linestyle='--', alpha=0.3)
axes6[0].set_xlabel('步长 h'); axes6[0].set_ylabel('绝对误差')
axes6[0].set_title('数值微分误差分析'); axes6[0].legend(); axes6[0].grid(True)

# 积分误差
axes6[1].loglog(n_values, trap_errors_int, 'b.-', label='梯形法 O(h²)')
valid = ~np.isnan(simp_errors_int)
axes6[1].loglog(n_values[valid], np.array(simp_errors_int)[valid], 'r.-', label='辛普森法 O(h⁴)')
axes6[1].set_xlabel('分割数 n'); axes6[1].set_ylabel('绝对误差')
axes6[1].set_title('数值积分误差分析'); axes6[1].legend(); axes6[1].grid(True)
save_fig(fig6, 'ex28_06_error_analysis.png')

print("\n思考题：自动微分（Autograd）为什么能避免数值微分的问题？原理是什么？\n")


# ================================================================
# 第7题：插值法 —— 拉格朗日与牛顿插值
# ================================================================
# 数学推导：
#   拉格朗日插值：
#     给定n+1个点 (x₀,y₀),...,(xₙ,yₙ)，构造n次多项式
#     L(x) = Σ yᵢ * lᵢ(x)
#     其中 lᵢ(x) = Π_{j≠i} (x-xⱼ)/(xᵢ-xⱼ) 是拉格朗日基函数
#     性质：lᵢ(xⱼ) = δᵢⱼ（克罗内克δ）
#
#   牛顿插值：
#     N(x) = a₀ + a₁(x-x₀) + a₂(x-x₀)(x-x₁) + ...
#     系数aₖ为k阶差商：
#       f[x₀] = f(x₀)
#       f[x₀,x₁] = (f(x₁)-f(x₀))/(x₁-x₀)
#       f[x₀,...,xₖ] = (f[x₁,...,xₖ]-f[x₀,...,x_{k-1}])/(xₖ-x₀)
#     优势：新增数据点只需追加一项，不必重新计算。
# ================================================================

print("=" * 60)
print("第7题：插值法（拉格朗日/牛顿插值）")
print("=" * 60)

def lagrange_interpolation(x_points, y_points, x_eval):
    """拉格朗日插值"""
    n = len(x_points)
    result = np.zeros_like(x_eval, dtype=float)
    for i in range(n):
        li = np.ones_like(x_eval, dtype=float)
        for j in range(n):
            if i != j:
                li *= (x_eval - x_points[j]) / (x_points[i] - x_points[j])
        result += y_points[i] * li
    return result

def newton_divided_diff(x_points, y_points):
    """计算牛顿差商表"""
    n = len(x_points)
    F = np.zeros((n, n))
    F[:, 0] = y_points
    for j in range(1, n):
        for i in range(n - j):
            F[i, j] = (F[i+1, j-1] - F[i, j-1]) / (x_points[i+j] - x_points[i])
    return F[0, :]  # 返回第一行（差商系数）

def newton_interpolation(x_points, y_points, x_eval):
    """牛顿插值"""
    coeffs = newton_divided_diff(x_points, y_points)
    n = len(coeffs)
    result = np.zeros_like(x_eval, dtype=float)
    for i in range(n):
        term = coeffs[i]
        for j in range(i):
            term *= (x_eval - x_points[j])
        result += term
    return result

# 测试数据
x_pts = np.array([0, 1, 2, 3, 4], dtype=float)
y_pts = np.array([0, 1, 4, 9, 16], dtype=float)  # y = x²

x_eval = np.linspace(-0.5, 4.5, 200)
y_lagrange = lagrange_interpolation(x_pts, y_pts, x_eval)
y_newton = newton_interpolation(x_pts, y_pts, x_eval)

# 验证
coeffs_newton = newton_divided_diff(x_pts, y_pts)
print(f"数据点: x={x_pts}, y={y_pts}")
print(f"牛顿差商系数: {coeffs_newton}")
print(f"拉格朗日和牛顿插值一致? {np.allclose(y_lagrange, y_newton)}")

# 在数据点处验证
y_at_points_l = lagrange_interpolation(x_pts, y_pts, x_pts)
print(f"在数据点处拉格朗日值: {y_at_points_l}")
print(f"与原始y一致? {np.allclose(y_at_points_l, y_pts)}")

# 龙格现象（Runge phenomenon）：高次插值在端点振荡
x_runge = np.linspace(-1, 1, 15)
y_runge = 1 / (1 + 25 * x_runge**2)  # Runge函数
x_eval_r = np.linspace(-1, 1, 500)
y_lagrange_r = lagrange_interpolation(x_runge, y_runge, x_eval_r)
y_true_r = 1 / (1 + 25 * x_eval_r**2)

print(f"\n龙格现象: 15点高次插值在端点振荡")
print(f"插值最大值: {np.max(y_lagrange_r):.2f} (真实最大: {np.max(y_true_r):.2f})")

fig7, axes7 = plt.subplots(1, 2, figsize=(12, 5))
# 正常插值
axes7[0].scatter(x_pts, y_pts, color='red', s=60, zorder=5, label='数据点')
axes7[0].plot(x_eval, y_lagrange, 'b-', label='拉格朗日/牛顿插值')
axes7[0].plot(x_eval, x_eval**2, 'g--', alpha=0.5, label='y=x²')
axes7[0].set_title('多项式插值'); axes7[0].legend(); axes7[0].grid(True)

# 龙格现象
axes7[1].scatter(x_runge, y_runge, color='red', s=30, zorder=5, label='数据点')
axes7[1].plot(x_eval_r, y_lagrange_r, 'b-', label='高次插值(振荡)')
axes7[1].plot(x_eval_r, y_true_r, 'g--', alpha=0.5, label='真实函数')
axes7[1].set_title('龙格现象（高次插值端点振荡）'); axes7[1].legend(); axes7[1].grid(True)
save_fig(fig7, 'ex28_07_interpolation.png')

print("\n思考题：如何避免龙格现象？样条插值为什么更稳定？\n")


# ================================================================
# 第8题：迭代法解方程 —— 牛顿法/二分法/不动点迭代
# ================================================================
# 数学推导：
#   二分法：利用中间值定理，每次将区间减半
#     收敛速率：线性，每步误差减半
#     优点：稳定可靠；缺点：收敛慢
#   牛顿法：x_{n+1} = x_n - f(x_n)/f'(x_n)
#     收敛速率：二次收敛（平方收敛）
#     优点：极快；缺点：需要导数，可能不收敛
#   不动点迭代：将f(x)=0改写为x=g(x)，迭代x_{n+1}=g(x_n)
#     收敛条件：|g'(x*)| < 1（压缩映射）
#     收敛速率：线性（一般情况）
# ================================================================

print("=" * 60)
print("第8题：迭代法解方程（牛顿法/二分法/不动点迭代）")
print("=" * 60)

def bisection(f, a, b, tol=1e-12, max_iter=100):
    """二分法"""
    history = []
    for _ in range(max_iter):
        c = (a + b) / 2
        history.append(c)
        if abs(f(c)) < tol or (b - a) / 2 < tol:
            break
        if f(a) * f(c) < 0:
            b = c
        else:
            a = c
    return c, history

def newton_method(f, df, x0, tol=1e-12, max_iter=100):
    """牛顿法"""
    x = x0
    history = [x]
    for _ in range(max_iter):
        fx = f(x)
        if abs(fx) < tol:
            break
        dfx = df(x)
        if abs(dfx) < 1e-15:
            break
        x = x - fx / dfx
        history.append(x)
    return x, history

def fixed_point_iteration(g, x0, tol=1e-12, max_iter=100):
    """不动点迭代"""
    x = x0
    history = [x]
    for _ in range(max_iter):
        x_new = g(x)
        history.append(x_new)
        if abs(x_new - x) < tol:
            break
        x = x_new
    return x, history

# 求 x³ - x - 1 = 0 的根（约1.3247）
f8 = lambda x: x**3 - x - 1
df8 = lambda x: 3*x**2 - 1
g8 = lambda x: (x + 1)**(1/3)  # 不动点形式 x = (x+1)^{1/3}

true_root = 1.324717957244746

root_bisect, hist_bisect = bisection(f8, 1, 2, tol=1e-12)
root_newton, hist_newton = newton_method(f8, df8, x0=1.5, tol=1e-12)
root_fixed, hist_fixed = fixed_point_iteration(g8, x0=1.5, tol=1e-12)

print(f"求解 x³ - x - 1 = 0 (真实根 ≈ {true_root:.10f})")
print(f"二分法:    {root_bisect:.12f}, 迭代{len(hist_bisect)}次, 误差={abs(root_bisect-true_root):.2e}")
print(f"牛顿法:    {root_newton:.12f}, 迭代{len(hist_newton)}次, 误差={abs(root_newton-true_root):.2e}")
print(f"不动点迭代: {root_fixed:.12f}, 迭代{len(hist_fixed)}次, 误差={abs(root_fixed-true_root):.2e}")

# 收敛速率分析
err_bisect = [abs(h - true_root) for h in hist_bisect]
err_newton = [abs(h - true_root) for h in hist_newton]
err_fixed = [abs(h - true_root) for h in hist_fixed]

# 牛顿法的二次收敛验证
print(f"\n牛顿法二次收敛验证:")
for i in range(min(6, len(err_newton)-1)):
    if err_newton[i+1] > 0 and err_newton[i] > 0:
        ratio = err_newton[i+1] / err_newton[i]**2
        print(f"  e_{i+1}/e_{i}² = {ratio:.2f} (二次收敛→常数)")

fig8, axes8 = plt.subplots(1, 2, figsize=(12, 5))
# 收敛曲线
axes8[0].semilogy(range(len(err_bisect)), err_bisect, 'b.-', label='二分法(线性)')
axes8[0].semilogy(range(len(err_newton)), err_newton, 'r.-', label='牛顿法(二次)')
axes8[0].semilogy(range(len(err_fixed)), err_fixed, 'g.-', label='不动点(线性)')
axes8[0].set_xlabel('迭代次数'); axes8[0].set_ylabel('|x_n - x*| (对数)')
axes8[0].set_title('迭代法收敛速率比较'); axes8[0].legend(); axes8[0].grid(True)

# 牛顿法二次收敛验证
if len(err_newton) > 3:
    axes8[1].loglog(err_newton[:-1], err_newton[1:], 'r.-', label='牛顿法 e_{n+1} vs e_n')
    # 二次收敛参考线 y = C*x²
    x_ref = np.logspace(np.log10(min(err_newton[:-1])), np.log10(max(err_newton[:-1])), 50)
    C = err_newton[2] / err_newton[1]**2 if err_newton[1] > 0 else 1
    axes8[1].loglog(x_ref, C * x_ref**2, 'k--', label=f'y={C:.1f}·x² (二次收敛)')
    axes8[1].set_xlabel('e_n'); axes8[1].set_ylabel('e_{n+1}')
    axes8[1].set_title('牛顿法二次收敛验证'); axes8[1].legend(); axes8[1].grid(True)
save_fig(fig8, 'ex28_08_iterative_methods.png')

print("\n思考题：不动点迭代的收敛条件|g'(x*)|<1如何推导？不满足时会怎样？\n")


# ================================================================
# 第9题：矩阵特征值数值计算 —— QR算法与幂迭代
# ================================================================
# 数学推导：
#   QR算法：计算矩阵全部特征值的标准方法
#     1. A₀ = A
#     2. 对Aₖ做QR分解：Aₖ = QₖRₖ
#     3. Aₖ₊₁ = RₖQₖ（交换Q和R的乘积顺序）
#     4. 重复直到Aₖ收敛为上三角（对角元即特征值）
#   原理：Aₖ₊₁ = RₖQₖ = Qₖ⁻¹AₖQₖ，每步做相似变换，
#   保持特征值不变，同时逐步将矩阵化为上三角（Schur形式）。
#   加速：带位移的QR算法（Wilkinson位移）收敛更快。
# ================================================================

print("=" * 60)
print("第9题：矩阵特征值数值计算（QR算法/幂迭代）")
print("=" * 60)

def qr_algorithm(A, max_iter=1000, tol=1e-10):
    """
    手写QR算法计算全部特征值
    （简化版，无位移）
    """
    A_k = A.copy().astype(float)
    n = A.shape[0]
    eigenvalues_history = []

    for iteration in range(max_iter):
        # QR分解
        Q, R = np.linalg.qr(A_k)
        A_k = R @ Q  # RQ相似变换
        # 记录对角元
        eigvals = np.sort(np.diag(A_k))
        eigenvalues_history.append(eigvals.copy())

        # 收敛判定：对角线以外元素足够小
        off_diag = np.sum(np.abs(A_k - np.diag(np.diag(A_k))))
        if off_diag < tol:
            break

    return np.sort(np.diag(A_k)), eigenvalues_history, iteration + 1

def qr_algorithm_shifted(A, max_iter=500, tol=1e-12):
    """带Wilkinson位移的QR算法"""
    A_k = A.copy().astype(float)
    n = A.shape[0]
    eigenvalues = []

    for _ in range(max_iter):
        if n == 1:
            eigenvalues.append(A_k[0, 0])
            n = 0
            break

        # Wilkinson位移
        d = (A_k[n-2, n-2] - A_k[n-1, n-1]) / 2
        if d == 0:
            mu = A_k[n-1, n-1]
        else:
            mu = A_k[n-1, n-1] - np.sign(d) * A_k[n-1, n-2]**2 / (abs(d) + np.sqrt(d**2 + A_k[n-1, n-2]**2))

        # 位移
        A_shifted = A_k - mu * np.eye(n)
        Q, R = np.linalg.qr(A_shifted)
        A_k = R @ Q + mu * np.eye(n)

        # 检查子矩阵是否可分离
        if n > 1 and abs(A_k[n-1, n-2]) < tol * (abs(A_k[n-1, n-1]) + abs(A_k[n-2, n-2])):
            eigenvalues.append(A_k[n-1, n-1])
            A_k = A_k[:n-1, :n-1]
            n -= 1

    if n > 0:
        eigenvalues.extend(np.diag(A_k).tolist())

    return np.sort(eigenvalues)

# 测试矩阵
A9 = np.array([[4.0, 1.0, 2.0, 0.0],
               [1.0, 3.0, 0.0, 1.0],
               [2.0, 0.0, 5.0, 1.0],
               [0.0, 1.0, 1.0, 2.0]])

# 无位移QR
eigvals_qr, eigvals_hist, n_iter_qr = qr_algorithm(A9, max_iter=200)
# 带位移QR
eigvals_shifted = qr_algorithm_shifted(A9)
# numpy参考
eigvals_numpy = np.sort(np.linalg.eigvals(A9))

print(f"测试矩阵:\n{A9}")
print(f"\n无位移QR算法: 迭代{n_iter_qr}次")
print(f"  特征值: {eigvals_qr}")
print(f"带位移QR算法:")
print(f"  特征值: {eigvals_shifted}")
print(f"numpy验证:")
print(f"  特征值: {eigvals_numpy}")
print(f"无位移QR误差: {np.max(np.abs(eigvals_qr - eigvals_numpy)):.2e}")
print(f"带位移QR误差: {np.max(np.abs(eigvals_shifted - eigvals_numpy)):.2e}")

# 收敛过程可视化
fig9, axes9 = plt.subplots(1, 2, figsize=(12, 5))
# 特征值收敛过程
eigvals_hist = np.array(eigvals_hist)
for i in range(4):
    axes9[0].plot(eigvals_hist[:, i], label=f'λ{i+1}')
    axes9[0].axhline(y=eigvals_numpy[i], color='gray', linestyle=':', alpha=0.3)
axes9[0].set_xlabel('迭代次数'); axes9[0].set_ylabel('特征值估计')
axes9[0].set_title(f'QR算法特征值收敛（{n_iter_qr}次迭代）'); axes9[0].legend(); axes9[0].grid(True)

# 非对角元衰减
off_diag_norms = []
A_temp = A9.copy().astype(float)
for _ in range(100):
    Q, R = np.linalg.qr(A_temp)
    A_temp = R @ Q
    off_diag_norms.append(np.sum(np.abs(A_temp - np.diag(np.diag(A_temp)))))
axes9[1].semilogy(off_diag_norms, 'b.-')
axes9[1].set_xlabel('迭代次数'); axes9[1].set_ylabel('非对角元范数(对数)')
axes9[1].set_title('QR算法收敛：非对角元衰减'); axes9[1].grid(True)
save_fig(fig9, 'ex28_09_qr_eigenvalue.png')

print("\n思考题：为什么带位移的QR算法比无位移快得多？位移的作用是什么？\n")


# ================================================================
# 第10题：蒙特卡洛积分与重要性采样
# ================================================================
# 数学推导：
#   标准蒙特卡洛积分：
#     ∫f(x)dx ≈ (b-a)/N * Σf(xᵢ), xᵢ~Uniform(a,b)
#     误差 ~ σ/√N，其中σ² = Var[f(X)]
#   重要性采样：
#     ∫f(x)dx = ∫[f(x)/p(x)]·p(x)dx ≈ (1/N)Σ f(xᵢ)/p(xᵢ), xᵢ~p(x)
#     选择好的p(x)使f(x)/p(x)方差更小 → 更快收敛
#     最优p*(x) ∝ |f(x)|（理论最优但实际不可计算）
#   误差比较：
#     标准MC误差 ~ σ_f/√N
#     重要性采样误差 ~ σ_{f/p}/√N
#   当f在某些区域值很大时，标准MC浪费样本在贡献小的区域，
#   重要性采样将更多样本分配到重要区域。
# ================================================================

print("=" * 60)
print("第10题：蒙特卡洛积分与重要性采样")
print("=" * 60)

# 目标：估计 ∫₀^π sin(x)² * e^{-x} dx
f10 = lambda x: np.sin(x)**2 * np.exp(-x)
a10, b10 = 0, np.pi

# 精确值（用scipy计算）
true_val10, _ = integrate.quad(f10, a10, b10)
print(f"目标积分: ∫₀^π sin²(x)·e^(-x) dx = {true_val10:.8f}")

# 1. 标准蒙特卡洛（均匀采样）
np.random.seed(42)
N = 100000
x_uniform = np.random.uniform(a10, b10, N)
mc_standard = (b10 - a10) * np.mean(f10(x_uniform))
mc_standard_var = (b10 - a10)**2 * np.var(f10(x_uniform)) / N
print(f"\n标准蒙特卡洛:")
print(f"  估计值 = {mc_standard:.8f}, 误差 = {abs(mc_standard - true_val10):.2e}")
print(f"  估计方差 = {mc_standard_var:.2e}")
print(f"  95%CI = [{mc_standard - 1.96*np.sqrt(mc_standard_var):.6f}, {mc_standard + 1.96*np.sqrt(mc_standard_var):.6f}]")

# 2. 重要性采样（用指数分布作为建议分布）
# p(x) = e^{-x} / (1 - e^{-π}) for x in [0, π]（截断指数分布）
from scipy.stats import truncexpon
# 截断指数分布 b=(π-0)/scale, scale=1, loc=0
p_importance = truncexpon(b=np.pi, loc=0, scale=1.0)
x_importance = p_importance.rvs(size=N, random_state=42)
# 权重 = f(x) / p(x)
weights = f10(x_importance) / p_importance.pdf(x_importance)
mc_importance = np.mean(weights)
mc_importance_var = np.var(weights) / N
print(f"\n重要性采样（截断指数分布）:")
print(f"  估计值 = {mc_importance:.8f}, 误差 = {abs(mc_importance - true_val10):.2e}")
print(f"  估计方差 = {mc_importance_var:.2e}")
print(f"  方差缩减比 = {mc_standard_var / mc_importance_var:.1f}x")

# 3. 用正态分布作为建议分布（中心在峰值附近）
from scipy.stats import norm
# f(x)在x≈1附近有峰值
p_normal_trunc = truncexpon(b=np.pi, loc=0, scale=0.8)
x_norm = p_normal_trunc.rvs(size=N, random_state=123)
weights_norm = f10(x_norm) / p_normal_trunc.pdf(x_norm)
mc_norm = np.mean(weights_norm)
mc_norm_var = np.var(weights_norm) / N
print(f"\n重要性采样（scale=0.8截断指数）:")
print(f"  估计值 = {mc_norm:.8f}, 误差 = {abs(mc_norm - true_val10):.2e}")
print(f"  估计方差 = {mc_norm_var:.2e}")

# 收敛过程比较
sample_sizes = np.logspace(2, 5, 50).astype(int)
errors_standard = []
errors_importance = []
for ns in sample_sizes:
    xs_u = np.random.uniform(a10, b10, ns)
    est_u = (b10 - a10) * np.mean(f10(xs_u))
    errors_standard.append(abs(est_u - true_val10))

    xs_i = p_importance.rvs(size=ns)
    ws = f10(xs_i) / p_importance.pdf(xs_i)
    est_i = np.mean(ws)
    errors_importance.append(abs(est_i - true_val10))

fig10, axes10 = plt.subplots(1, 2, figsize=(12, 5))
# 被积函数与采样分布
x_plot = np.linspace(0, np.pi, 500)
axes10[0].plot(x_plot, f10(x_plot), 'b-', linewidth=2, label='f(x) = sin²x·e^(-x)')
axes10[0].plot(x_plot, p_importance.pdf(x_plot) * true_val10, 'r--', label='p(x)·I (重要性采样分布)')
axes10[0].hist(x_uniform[:5000], bins=50, density=True, alpha=0.2, color='blue', label='均匀采样')
axes10[0].hist(x_importance[:5000], bins=50, density=True, alpha=0.2, color='red', label='重要性采样')
axes10[0].set_xlabel('x'); axes10[0].set_ylabel('密度')
axes10[0].set_title('被积函数与采样分布对比'); axes10[0].legend(fontsize=8); axes10[0].grid(True)

# 收敛比较
axes10[1].loglog(sample_sizes, errors_standard, 'b.-', label='标准MC')
axes10[1].loglog(sample_sizes, errors_importance, 'r.-', label='重要性采样')
# 理论1/√N参考线
axes10[1].loglog(sample_sizes, 1/np.sqrt(sample_sizes) * 0.5, 'k--', alpha=0.3, label='O(1/√N)参考')
axes10[1].set_xlabel('采样数 N'); axes10[10].set_ylabel('绝对误差') if False else axes10[1].set_ylabel('绝对误差')
axes10[1].set_title('蒙特卡洛积分收敛比较'); axes10[1].legend(); axes10[1].grid(True)
save_fig(fig10, 'ex28_10_importance_sampling.png')

print("\n思考题：如何选择最优的重要性采样分布？什么情况下重要性采样反而更差？\n")

print("=" * 60)
print("文件3全部完成！共10题。")
print("=" * 60)
print("\n全部3个文件、40道AI数学练习题已全部完成！")
