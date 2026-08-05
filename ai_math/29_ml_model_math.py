# -*- coding: utf-8 -*-
"""
============================================================
阶段：机器学习模型数学
题数：15题
创建日期：2026-08-05
说明：从数学原理出发，纯numpy手写所有核心ML模型
环境：Python 3.13 + numpy 2.4 + scipy 1.17 + sympy 1.14 + matplotlib 3.10
============================================================
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.spatial.distance import cdist
from scipy.cluster.hierarchy import dendrogram
import os
import warnings

warnings.filterwarnings('ignore')
os.makedirs('figures_ml', exist_ok=True)

print("=" * 60)
print("机器学习模型数学 - 15题练习")
print("创建日期: 2026-08-05")
print("=" * 60)

# ============================================================
# 第1题: 线性回归 - 最小二乘法
# ============================================================
# 【数学推导】
# 线性模型: ŷ = Xw, 其中 X ∈ R^{n×(d+1)} (含偏置列), w ∈ R^{d+1}
# 目标函数(残差平方和): J(w) = ||Xw - y||² = (Xw - y)ᵀ(Xw - y)
#
# 方法一 - 正规方程(解析解):
#   对 J(w) 求导: ∂J/∂w = 2Xᵀ(Xw - y) = 0
#   => XᵀXw = Xᵀy => w = (XᵀX)⁻¹Xᵀy
#
# 方法二 - 梯度下降:
#   ∂J/∂w = (2/n)·Xᵀ(Xw - y)
#   更新规则: w ← w - α·(1/n)·Xᵀ(Xw - y)

np.random.seed(42)
n1 = 100
X1 = np.random.uniform(0, 10, n1)
y1 = 3.0 * X1 + 2.0 + np.random.randn(n1) * 2.0
X1_b = np.column_stack([np.ones(n1), X1])

# --- 正规方程 ---
w1_ne = np.linalg.inv(X1_b.T @ X1_b) @ X1_b.T @ y1

# --- 梯度下降 ---
w1_gd = np.zeros(2)
lr1, losses1 = 0.01, []
for _ in range(1000):
    pred = X1_b @ w1_gd
    w1_gd -= lr1 * X1_b.T @ (pred - y1) / n1
    losses1.append(np.mean((pred - y1) ** 2))

# --- 可视化 ---
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
axes[0].scatter(X1, y1, s=10, alpha=0.5, label='数据点')
xl = np.array([0, 10])
axes[0].plot(xl, w1_ne[1]*xl + w1_ne[0], 'r-', label=f'正规方程: y={w1_ne[1]:.2f}x+{w1_ne[0]:.2f}')
axes[0].plot(xl, w1_gd[1]*xl + w1_gd[0], 'g--', label=f'梯度下降: y={w1_gd[1]:.2f}x+{w1_gd[0]:.2f}')
axes[0].set_xlabel('X'); axes[0].set_ylabel('y'); axes[0].legend(); axes[0].set_title('线性回归拟合')
axes[1].plot(losses1); axes[1].set_xlabel('迭代次数'); axes[1].set_ylabel('MSE'); axes[1].set_title('梯度下降损失曲线')
plt.tight_layout(); plt.savefig('figures_ml/ex01_linear_regression.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第1题] 正规方程 w={w1_ne.round(3)}, 梯度下降 w={w1_gd.round(3)}, 真实 w=[2, 3]")
# 【思考题】当特征维度 d >> 样本数 n 时，XᵀX 不可逆，此时该如何求解？(提示: 正则化/伪逆)


# ============================================================
# 第2题: 逻辑回归 - sigmoid与最大似然
# ============================================================
# 【数学推导】
# 模型: P(y=1|x) = σ(wᵀx) = 1/(1+e^{-wᵀx})
# 似然函数: L(w) = ∏ σ(zᵢ)^{yᵢ} [1-σ(zᵢ)]^{1-yᵢ},  zᵢ = wᵀxᵢ
# 对数似然: ℓ(w) = Σ [yᵢ log σ(zᵢ) + (1-yᵢ) log(1-σ(zᵢ))]
# 负对数似然(损失): J(w) = -(1/n)·ℓ(w)
# 梯度: ∂J/∂w = (1/n)·Xᵀ(σ(Xw) - y)
# 更新: w ← w - α·∂J/∂w  (梯度下降，最小化损失)

np.random.seed(42)
n2 = 100
X2 = np.vstack([np.random.randn(n2//2, 2) + [2, 2], np.random.randn(n2//2, 2) + [-2, -2]])
y2 = np.array([1]*(n2//2) + [0]*(n2//2))
X2_b = np.column_stack([np.ones(n2), X2])

def sigmoid(z):
    """数值稳定的sigmoid: 避免大数溢出"""
    return np.where(z >= 0, 1/(1+np.exp(-z)), np.exp(z)/(1+np.exp(z)))

w2 = np.zeros(3); lr2 = 0.1
for _ in range(1000):
    p2 = sigmoid(X2_b @ w2)
    w2 -= lr2 * X2_b.T @ (p2 - y2) / n2

# --- 可视化 ---
fig, ax = plt.subplots(figsize=(8, 6))
ax.scatter(X2[y2==1, 0], X2[y2==1, 1], c='blue', label='类别1', s=20, edgecolors='black')
ax.scatter(X2[y2==0, 0], X2[y2==0, 1], c='red', label='类别0', s=20, edgecolors='black')
x1r = np.linspace(-5, 5, 100)
ax.plot(x1r, -(w2[0] + w2[1]*x1r) / w2[2], 'g-', linewidth=2, label='决策边界')
ax.set_xlabel('特征1'); ax.set_ylabel('特征2'); ax.set_title('逻辑回归决策边界'); ax.legend()
plt.tight_layout(); plt.savefig('figures_ml/ex02_logistic_regression.png', dpi=100, bbox_inches='tight'); plt.close()
acc2 = np.mean((sigmoid(X2_b @ w2) > 0.5) == y2)
print(f"[第2题] 训练准确率: {acc2:.2%}, w={w2.round(3)}")
# 【思考题】逻辑回归的决策边界是线性的，如何扩展为非线性决策边界？(提示: 特征映射/多项式特征)


# ============================================================
# 第3题: Softmax回归 - 多分类与交叉熵
# ============================================================
# 【数学推导】
# 模型: p_k = softmax(z_k) = e^{z_k} / Σ_j e^{z_j},  z_k = w_kᵀx
# 数值稳定softmax: 先减去最大值再求exp, 避免上溢
#   p_k = e^{z_k - max(z)} / Σ_j e^{z_j - max(z)}
# 交叉熵损失: J(W) = -(1/n) Σ_i Σ_k y_{ik} log p_{ik}  (y为one-hot)
# 梯度: ∂J/∂W = (1/n)·Xᵀ(P - Y)   其中 P=softmax(XWᵀ), Y=one-hot标签
# 更新: W ← W - α·(∂J/∂W)ᵀ

np.random.seed(42)
n3 = 150
centers3 = [np.array([2, 2]), np.array([-2, 2]), np.array([0, -2])]
X3 = np.vstack([np.random.randn(50, 2) + c for c in centers3])
y3 = np.array([0]*50 + [1]*50 + [2]*50)
Y3 = np.eye(3)[y3]
X3_b = np.column_stack([np.ones(n3), X3])

def softmax(z):
    """数值稳定的softmax"""
    z = z - np.max(z, axis=1, keepdims=True)
    exp_z = np.exp(z)
    return exp_z / np.sum(exp_z, axis=1, keepdims=True)

W3 = np.zeros((3, 3)); lr3 = 0.1  # 3特征(含偏置) × 3类
for _ in range(1000):
    P3 = softmax(X3_b @ W3.T)
    grad3 = X3_b.T @ (P3 - Y3) / n3
    W3 -= lr3 * grad3.T

# --- 可视化 ---
fig, ax = plt.subplots(figsize=(8, 6))
xx3, yy3 = np.meshgrid(np.linspace(-5, 5, 100), np.linspace(-5, 5, 100))
grid3 = np.column_stack([np.ones(10000), xx3.ravel(), yy3.ravel()])
Z3 = np.argmax(softmax(grid3 @ W3.T), axis=1).reshape(xx3.shape)
ax.contourf(xx3, yy3, Z3, alpha=0.3, cmap='Set1')
ax.scatter(X3[:, 0], X3[:, 1], c=y3, cmap='Set1', edgecolors='black', s=30)
ax.set_title('Softmax回归决策边界'); ax.set_xlabel('特征1'); ax.set_ylabel('特征2')
plt.tight_layout(); plt.savefig('figures_ml/ex03_softmax.png', dpi=100, bbox_inches='tight'); plt.close()
acc3 = np.mean(np.argmax(softmax(X3_b @ W3.T), axis=1) == y3)
print(f"[第3题] 训练准确率: {acc3:.2%}")
# 【思考题】Softmax回归与逻辑回归的关系是什么？当类别数为2时两者等价吗？


# ============================================================
# 第4题: SVM线性分类器 - hinge loss与简化SMO
# ============================================================
# 【数学推导】
# 原始问题: min (1/2)||w||² + C·Σξᵢ  s.t. yᵢ(wᵀxᵢ+b) ≥ 1-ξᵢ, ξᵢ≥0
#   - (1/2)||w||² 最大化间隔 (间隔 = 2/||w||)
#   - C·Σξᵢ 惩罚违反间隔的样本 (hinge loss: max(0, 1-yᵢf(xᵢ)))
#
# 对偶问题: max Σαᵢ - (1/2)ΣΣ αᵢαⱼyᵢyⱼK(xᵢ,xⱼ)
#   s.t. 0≤αᵢ≤C, Σαᵢyᵢ=0
#
# KKT条件:
#   αᵢ=0  → yᵢf(xᵢ)≥1  (分类正确, 间隔外)
#   0<αᵢ<C → yᵢf(xᵢ)=1  (支持向量, 在间隔边界)
#   αᵢ=C  → yᵢf(xᵢ)≤1  (间隔内或误分类)
#
# 决策函数: f(x) = ΣαᵢyᵢK(xᵢ,x) + b
#
# 简化SMO算法:
#   1. 遍历样本, 检查KKT条件是否违反
#   2. 选取违反KKT的αᵢ, 随机选另一个αⱼ
#   3. 固定其他α, 解析求解αᵢ,αⱼ的二次规划子问题
#   4. 更新偏置b, 重复直至收敛

def simplified_smo(X, y, C, kernel_func, tol=1e-3, max_passes=5):
    """简化版序列最小优化(SMO)算法"""
    n = len(y)
    alpha = np.zeros(n)
    b = 0.0
    K = kernel_func(X, X)  # 预计算核矩阵 n×n
    passes = 0
    while passes < max_passes:
        num_changed = 0
        for i in range(n):
            # 计算预测误差 E_i = f(x_i) - y_i
            f_i = np.sum(alpha * y * K[:, i]) + b
            E_i = f_i - y[i]
            # 检查KKT条件
            if (y[i]*E_i < -tol and alpha[i] < C) or (y[i]*E_i > tol and alpha[i] > 0):
                j = np.random.randint(n)
                while j == i:
                    j = np.random.randint(n)
                E_j = np.sum(alpha * y * K[:, j]) + b - y[j]
                a_i_old, a_j_old = alpha[i], alpha[j]
                # 计算L,H边界
                if y[i] != y[j]:
                    L, H = max(0, alpha[j]-alpha[i]), min(C, C+alpha[j]-alpha[i])
                else:
                    L, H = max(0, alpha[i]+alpha[j]-C), min(C, alpha[i]+alpha[j])
                if L == H:
                    continue
                eta = 2*K[i, j] - K[i, i] - K[j, j]
                if eta >= 0:
                    continue
                # 更新alpha_j
                alpha[j] -= y[j] * (E_i - E_j) / eta
                alpha[j] = np.clip(alpha[j], L, H)
                if abs(alpha[j] - a_j_old) < 1e-5:
                    continue
                # 更新alpha_i (满足等式约束 Σαᵢyᵢ=0)
                alpha[i] += y[i] * y[j] * (a_j_old - alpha[j])
                # 更新偏置b
                b1 = b - E_i - y[i]*(alpha[i]-a_i_old)*K[i,i] - y[j]*(alpha[j]-a_j_old)*K[i,j]
                b2 = b - E_j - y[i]*(alpha[i]-a_i_old)*K[i,j] - y[j]*(alpha[j]-a_j_old)*K[j,j]
                b = b1 if 0 < alpha[i] < C else (b2 if 0 < alpha[j] < C else (b1+b2)/2)
                num_changed += 1
        passes = passes + 1 if num_changed == 0 else 0
    return alpha, b

def linear_kernel(A, B):
    """线性核: K(x,z) = xᵀz"""
    return A @ B.T

np.random.seed(42)
n4 = 60
X4 = np.vstack([np.random.randn(n4//2, 2) + [2, 2], np.random.randn(n4//2, 2) + [-2, -2]])
y4 = np.array([1]*(n4//2) + [-1]*(n4//2))
alpha4, b4 = simplified_smo(X4, y4, C=1.0, kernel_func=linear_kernel)
w4 = np.sum(alpha4[:, None] * y4[:, None] * X4, axis=0)  # w = Σαᵢyᵢxᵢ
sv4 = np.where(alpha4 > 1e-5)[0]

# --- 可视化 ---
fig, ax = plt.subplots(figsize=(8, 6))
ax.scatter(X4[y4==1, 0], X4[y4==1, 1], c='blue', label='类别+1', s=20)
ax.scatter(X4[y4==-1, 0], X4[y4==-1, 1], c='red', label='类别-1', s=20)
ax.scatter(X4[sv4, 0], X4[sv4, 1], s=120, facecolors='none', edgecolors='lime', linewidths=2, label='支持向量')
xl = np.linspace(-5, 5, 100)
ax.plot(xl, -(w4[0]*xl+b4)/w4[1], 'k-', label='决策边界 f(x)=0')
ax.plot(xl, -(w4[0]*xl+b4-1)/w4[1], 'k--', alpha=0.5, label='间隔边界 f(x)=±1')
ax.plot(xl, -(w4[0]*xl+b4+1)/w4[1], 'k--', alpha=0.5)
ax.set_title(f'SVM线性分类器 (支持向量: {len(sv4)}个)'); ax.legend()
plt.tight_layout(); plt.savefig('figures_ml/ex04_svm_smo.png', dpi=100, bbox_inches='tight'); plt.close()
acc4 = np.mean(np.sign(X4 @ w4 + b4) == y4)
print(f"[第4题] 支持向量: {len(sv4)}个, 训练准确率: {acc4:.2%}")
# 【思考题】支持向量如何决定决策边界？移除非支持向量会影响模型吗？为什么？


# ============================================================
# 第5题: 核SVM - 多项式核与RBF核
# ============================================================
# 【数学推导】
# 核技巧: K(x, z) = φ(x)ᵀφ(z), 无需显式计算高维映射φ(x)
#   对偶问题中只需K(xᵢ, xⱼ), 决策函数也只需核函数
#
# 多项式核: K(x, z) = (xᵀz + c)^d
#   映射到多项式特征空间, c控制常数项, d控制阶数
#
# RBF核(高斯核): K(x, z) = exp(-γ||x - z||²)
#   γ = 1/(2σ²) 控制局部性: γ大→模型复杂(过拟合), γ小→模型简单(欠拟合)
#   RBF核对应无限维特征空间
#
# 决策函数: f(x) = ΣαᵢyᵢK(xᵢ, x) + b

def rbf_kernel(A, B, gamma=0.5):
    """RBF核: K(x,z) = exp(-γ||x-z||²)"""
    sq_dists = cdist(A, B, 'sqeuclidean')
    return np.exp(-gamma * sq_dists)

np.random.seed(42)
n5 = 80
# 生成环形数据(非线性可分)
angles = np.random.uniform(0, 2*np.pi, n5//2)
r_in, r_out = 1.0, 3.0
X5 = np.vstack([
    np.column_stack([r_in*np.cos(angles), r_in*np.sin(angles)]),
    np.column_stack([r_out*np.cos(angles), r_out*np.sin(angles)])
])
y5 = np.array([1]*(n5//2) + [-1]*(n5//2))

alpha5, b5 = simplified_smo(X5, y5, C=1.0, kernel_func=rbf_kernel)
sv5 = np.where(alpha5 > 1e-5)[0]

# --- 可视化 ---
fig, ax = plt.subplots(figsize=(8, 8))
xx5, yy5 = np.meshgrid(np.linspace(-5, 5, 100), np.linspace(-5, 5, 100))
grid5 = np.column_stack([xx5.ravel(), yy5.ravel()])
K5_test = rbf_kernel(grid5, X5)
Z5 = (K5_test @ (alpha5 * y5) + b5).reshape(xx5.shape)
ax.contourf(xx5, yy5, Z5, levels=50, cmap='RdBu', alpha=0.3)
ax.contour(xx5, yy5, Z5, levels=[0], colors='black', linewidths=2)
ax.scatter(X5[y5==1, 0], X5[y5==1, 1], c='blue', s=20, label='类别+1')
ax.scatter(X5[y5==-1, 0], X5[y5==-1, 1], c='red', s=20, label='类别-1')
ax.scatter(X5[sv5, 0], X5[sv5, 1], s=120, facecolors='none', edgecolors='lime', linewidths=2, label='支持向量')
ax.set_title(f'核SVM (RBF核, 支持向量: {len(sv5)}个)'); ax.legend()
plt.tight_layout(); plt.savefig('figures_ml/ex05_kernel_svm.png', dpi=100, bbox_inches='tight'); plt.close()
acc5 = np.mean(np.sign(rbf_kernel(X5, X5) @ (alpha5 * y5) + b5) == y5)
print(f"[第5题] RBF核SVM, 支持向量: {len(sv5)}个, 训练准确率: {acc5:.2%}")
# 【思考题】γ参数如何影响RBF核SVM的决策边界？过大或过小分别会导致什么问题？


# ============================================================
# 第6题: 决策树 - 信息增益与基尼系数
# ============================================================
# 【数学推导】
# 熵(Entropy): H(S) = -Σ_k p_k log₂(p_k)
#   度量集合S的不纯度, 越大越混乱
#
# 基尼系数(Gini): Gini(S) = 1 - Σ_k p_k²
#   也是不纯度度量, 计算更高效(无需log)
#
# 信息增益(Info Gain): IG(S, A) = H(S) - Σ_v (|S_v|/|S|)·H(S_v)
#   选择使信息增益最大的特征和阈值进行分裂
#
# 递归构建: 对每个子集递归分裂, 直到:
#   - 子集纯净(单一类别)
#   - 达到最大深度
#   - 样本数少于阈值

def gini_impurity(y):
    """计算基尼系数"""
    _, counts = np.unique(y, return_counts=True)
    p = counts / len(y)
    return 1 - np.sum(p ** 2)

def find_best_split(X, y, feat_subset=None):
    """寻找最佳分裂点(最大信息增益)"""
    n_feat = X.shape[1]
    features = feat_subset if feat_subset is not None else range(n_feat)
    best_gain, best_f, best_t = -1, None, None
    parent_gini = gini_impurity(y)
    for f in features:
        for t in np.unique(X[:, f]):
            left = X[:, f] <= t
            right = ~left
            if left.sum() == 0 or right.sum() == 0:
                continue
            gain = parent_gini - (left.sum()/len(y))*gini_impurity(y[left]) \
                                   - (right.sum()/len(y))*gini_impurity(y[right])
            if gain > best_gain:
                best_gain, best_f, best_t = gain, f, t
    return best_f, best_t, best_gain

def build_tree(X, y, max_depth=5, min_samples=2, depth=0, max_features=None):
    """递归构建决策树"""
    n_feat = X.shape[1]
    if depth >= max_depth or len(y) < min_samples or len(np.unique(y)) == 1:
        return {'leaf': True, 'val': int(np.bincount(y).argmax())}
    feat_subset = np.random.choice(n_feat, max_features, replace=False) if max_features else None
    f, t, gain = find_best_split(X, y, feat_subset)
    if f is None or gain <= 0:
        return {'leaf': True, 'val': int(np.bincount(y).argmax())}
    left = X[:, f] <= t
    return {'leaf': False, 'feat': f, 'thresh': t,
            'left': build_tree(X[left], y[left], max_depth, min_samples, depth+1, max_features),
            'right': build_tree(X[~left], y[~left], max_depth, min_samples, depth+1, max_features)}

def tree_predict_one(tree, x):
    """单样本预测"""
    while not tree['leaf']:
        tree = tree['left'] if x[tree['feat']] <= tree['thresh'] else tree['right']
    return tree['val']

np.random.seed(42)
n6 = 120
X6 = np.vstack([np.random.randn(40, 2) + [2, 2], np.random.randn(40, 2) + [-2, 2], np.random.randn(40, 2) + [0, -2]])
y6 = np.array([0]*40 + [1]*40 + [2]*40)
tree6 = build_tree(X6, y6, max_depth=5)

# --- 可视化 ---
fig, ax = plt.subplots(figsize=(8, 6))
xx6, yy6 = np.meshgrid(np.linspace(-5, 5, 100), np.linspace(-5, 5, 100))
grid6 = np.column_stack([xx6.ravel(), yy6.ravel()])
Z6 = np.array([tree_predict_one(tree6, g) for g in grid6]).reshape(xx6.shape)
ax.contourf(xx6, yy6, Z6, alpha=0.3, cmap='Set1')
ax.scatter(X6[:, 0], X6[:, 1], c=y6, cmap='Set1', edgecolors='black', s=30)
ax.set_title('决策树决策边界 (Gini系数)'); ax.set_xlabel('特征1'); ax.set_ylabel('特征2')
plt.tight_layout(); plt.savefig('figures_ml/ex06_decision_tree.png', dpi=100, bbox_inches='tight'); plt.close()
acc6 = np.mean([tree_predict_one(tree6, x) == y for x, y in zip(X6, y6)])
print(f"[第6题] 决策树训练准确率: {acc6:.2%}")
# 【思考题】决策树容易过拟合，有哪些剪枝策略？预剪枝和后剪枝有何区别？


# ============================================================
# 第7题: 随机森林 - Bagging与特征随机选择
# ============================================================
# 【数学推导】
# Bagging(Bootstrap Aggregating):
#   1. 从训练集中有放回采样n个样本 (Bootstrap)
#   2. 对每个Bootstrap样本训练一棵决策树
#   3. 多棵树投票(分类)或平均(回归)
#
# 特征随机选择:
#   每次分裂时, 只考虑 √d 个随机特征 (d为总特征数)
#   降低树之间的相关性, 增加多样性
#
# 偏差-方差分解:
#   单棵树: 高方差, 低偏差
#   随机森林: 通过平均降低方差, 同时保持低偏差
#   泛化误差 ≈ Bias² + Variance + Noise

np.random.seed(42)
X7, y7, n7 = X6, y6, n6
n_trees = 20
max_feat = max(1, int(np.sqrt(X7.shape[1])))
trees7 = []
for _ in range(n_trees):
    idx = np.random.choice(n7, n7, replace=True)  # Bootstrap采样
    tree = build_tree(X7[idx], y7[idx], max_depth=5, max_features=max_feat)
    trees7.append(tree)

def rf_predict(trees, X):
    """随机森林预测: 多数投票"""
    preds = np.array([[tree_predict_one(t, x) for x in X] for t in trees])
    return np.array([np.bincount(preds[:, i].astype(int)).argmax() for i in range(len(X))])

# --- 可视化 ---
fig, ax = plt.subplots(figsize=(8, 6))
xx7, yy7 = np.meshgrid(np.linspace(-5, 5, 80), np.linspace(-5, 5, 80))
grid7 = np.column_stack([xx7.ravel(), yy7.ravel()])
Z7 = rf_predict(trees7, grid7).reshape(xx7.shape)
ax.contourf(xx7, yy7, Z7, alpha=0.3, cmap='Set1')
ax.scatter(X7[:, 0], X7[:, 1], c=y7, cmap='Set1', edgecolors='black', s=30)
ax.set_title(f'随机森林决策边界 ({n_trees}棵树)'); ax.set_xlabel('特征1'); ax.set_ylabel('特征2')
plt.tight_layout(); plt.savefig('figures_ml/ex07_random_forest.png', dpi=100, bbox_inches='tight'); plt.close()
acc7 = np.mean(rf_predict(trees7, X7) == y7)
print(f"[第7题] 随机森林({n_trees}棵树)训练准确率: {acc7:.2%}")
# 【思考题】随机森林如何通过Bagging和特征随机化降低方差？为什么树之间需要"不相关"？


# ============================================================
# 第8题: GBDT梯度提升 - 加法模型与负梯度拟合
# ============================================================
# 【数学推导】
# 加法模型: F_m(x) = F_{m-1}(x) + ν·h_m(x)
#   F_0 = 初始值(如均值), h_m为第m棵回归树, ν为学习率(shrinkage)
#
# 负梯度拟合(核心思想):
#   损失函数 L(y, F(x)) 对 F 求导, 得到负梯度 r_i = -∂L/∂F(xᵢ)
#   第m轮: 用回归树拟合 {(xᵢ, rᵢ)}, 得到 h_m
#   MSE损失: L = (1/2)(y-F)², 负梯度 r_i = y_i - F(xᵢ)  (即残差)
#
# Shrinkage(收缩/学习率):
#   F_m = F_{m-1} + ν·h_m,  ν ∈ (0, 1]
#   小学习率+多棵树 → 更好的泛化, 类似SGD中的小步长

def find_best_split_reg(X, y):
    """回归树: 寻找最小化MSE的分裂点"""
    n_feat = X.shape[1]
    best_mse, best_f, best_t = float('inf'), None, None
    for f in range(n_feat):
        for t in np.unique(X[:, f]):
            left = X[:, f] <= t
            right = ~left
            if left.sum() == 0 or right.sum() == 0:
                continue
            mse = (np.sum((y[left]-y[left].mean())**2) + np.sum((y[right]-y[right].mean())**2)) / len(y)
            if mse < best_mse:
                best_mse, best_f, best_t = mse, f, t
    return best_f, best_t

def build_reg_tree(X, y, max_depth=3, depth=0):
    """构建回归树"""
    if depth >= max_depth or len(y) < 2:
        return {'leaf': True, 'val': y.mean()}
    f, t = find_best_split_reg(X, y)
    if f is None:
        return {'leaf': True, 'val': y.mean()}
    left = X[:, f] <= t
    return {'leaf': False, 'feat': f, 'thresh': t,
            'left': build_reg_tree(X[left], y[left], max_depth, depth+1),
            'right': build_reg_tree(X[~left], y[~left], max_depth, depth+1)}

def reg_tree_predict(tree, X):
    """回归树批量预测"""
    def _pred(t, x):
        while not t['leaf']:
            t = t['left'] if x[t['feat']] <= t['thresh'] else t['right']
        return t['val']
    return np.array([_pred(tree, x) for x in X])

np.random.seed(42)
n8 = 100
X8 = np.sort(np.random.uniform(0, 10, n8)).reshape(-1, 1)
y8 = np.sin(X8.ravel()) + np.random.randn(n8) * 0.1

# GBDT训练
F8 = np.full(n8, y8.mean())  # F_0 = 均值
lr8, losses8, n_est8 = 0.1, [], 50
for _ in range(n_est8):
    residual = y8 - F8  # 负梯度 = 残差 (MSE损失)
    tree = build_reg_tree(X8, residual, max_depth=3)
    F8 += lr8 * reg_tree_predict(tree, X8)
    losses8.append(np.mean((y8 - F8)**2))

# --- 可视化 ---
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
axes[0].scatter(X8, y8, s=10, alpha=0.5, label='数据点')
axes[0].plot(X8, F8, 'r-', linewidth=2, label=f'GBDT拟合({n_est8}轮)')
axes[0].set_title('GBDT梯度提升回归'); axes[0].legend()
axes[1].plot(losses8); axes[1].set_xlabel('迭代次数'); axes[1].set_ylabel('MSE'); axes[1].set_title('损失曲线')
plt.tight_layout(); plt.savefig('figures_ml/ex08_gbdt.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第8题] GBDT({n_est8}轮, lr={lr8}), 最终MSE: {losses8[-1]:.6f}")
# 【思考题】shrinkage(小学习率)为什么能提升泛化性能？学习率与迭代次数的关系是什么？



# ============================================================
# 第9题: K-Means聚类 - Lloyd算法与肘部法则
# ============================================================
# 【数学推导】
# 目标函数(簇内平方和WCSS): J = Σ_k Σ_{x∈C_k} ||x - μ_k||²
#   μ_k = (1/|C_k|) Σ_{x∈C_k} x  (簇均值)
#
# Lloyd算法(交替优化):
#   1. 分配步骤: 将每个点分配到最近的簇中心
#      C_k = {xᵢ : k = argmin_j ||xᵢ - μ_j||²}
#   2. 更新步骤: 重新计算每个簇的中心
#      μ_k ← (1/|C_k|) Σ_{x∈C_k} x
#   3. 重复直到中心不再变化
#
# K-Means++初始化: 按距离平方的概率选择初始中心, 避免随机初始化的坏运气
#
# 肘部法则: 绘制J随k变化的曲线, 选择"拐点"处的k值

np.random.seed(42)
n9 = 300
centers9 = np.array([[0, 0], [5, 5], [-5, 5]])
X9 = np.vstack([np.random.randn(100, 2) + c for c in centers9])

def kmeans(X, k, max_iter=100):
    """K-Means聚类 (Lloyd算法 + K-Means++初始化)"""
    n = len(X)
    # K-Means++ 初始化
    centers = [X[np.random.randint(n)]]
    for _ in range(1, k):
        dists = np.array([np.sum((X - c)**2, axis=1) for c in centers])
        min_dists = np.min(dists, axis=0)
        probs = min_dists / min_dists.sum()
        centers.append(X[np.random.choice(n, p=probs)])
    centers = np.array(centers)
    # Lloyd迭代
    for _ in range(max_iter):
        labels = np.argmin(cdist(X, centers), axis=1)  # 分配
        new_centers = np.array([X[labels == i].mean(axis=0) if np.any(labels == i) else centers[i]
                                for i in range(k)])  # 更新
        if np.allclose(centers, new_centers):
            break
        centers = new_centers
    inertia = sum(np.sum((X[labels == i] - centers[i])**2) for i in range(k))
    return labels, centers, inertia

labels9, centers9_res, inertia9 = kmeans(X9, k=3)
# 肘部法则
inertias9 = [kmeans(X9, k)[2] for k in range(1, 8)]

# --- 可视化 ---
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
axes[0].scatter(X9[:, 0], X9[:, 1], c=labels9, cmap='Set1', s=10)
axes[0].scatter(centers9_res[:, 0], centers9_res[:, 1], c='black', marker='X', s=100, label='簇中心')
axes[0].set_title('K-Means聚类结果'); axes[0].legend()
axes[1].plot(range(1, 8), inertias9, 'bo-')
axes[1].set_xlabel('簇数 k'); axes[1].set_ylabel('Inertia (WCSS)'); axes[1].set_title('肘部法则')
plt.tight_layout(); plt.savefig('figures_ml/ex09_kmeans.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第9题] K-Means(k=3), Inertia: {inertia9:.2f}, 肘部法则建议k=3")
# 【思考题】K-Means++初始化相比随机初始化有什么优势？为什么能避免糟糕的局部最优？


# ============================================================
# 第10题: 层次聚类 - 单链接与全链接
# ============================================================
# 【数学推导】
# 凝聚层次聚类(自底向上):
#   1. 初始: 每个点自成一簇
#   2. 计算所有簇间距离
#   3. 合并距离最小的两个簇
#   4. 更新距离矩阵, 重复直到只剩一个簇
#
# 簇间距离(连接方式):
#   单链接(Single): d(A,B) = min_{a∈A,b∈B} d(a,b)  (最近距离)
#   全链接(Complete): d(A,B) = max_{a∈A,b∈B} d(a,b)  (最远距离)
#   平均链接(Average): d(A,B) = (1/|A||B|) Σ d(a,b)
#
# 单链接容易产生"链式效应", 全链接偏好紧凑的簇

np.random.seed(42)
n10 = 30
X10 = np.vstack([np.random.randn(n10//3, 2) + [0, 0],
                 np.random.randn(n10//3, 2) + [5, 5],
                 np.random.randn(n10//3, 2) + [0, 5]])

def agglomerative_clustering(X, linkage='single'):
    """凝聚层次聚类, 返回scipy格式的linkage矩阵"""
    n = len(X)
    members = {i: [i] for i in range(n)}
    active = list(range(n))
    dist_matrix = cdist(X, X)
    Z = []
    next_id = n
    for _ in range(n - 1):
        min_d, min_a, min_b = np.inf, -1, -1
        for ia in range(len(active)):
            for ib in range(ia + 1, len(active)):
                a, b = active[ia], active[ib]
                d_ab = dist_matrix[np.ix_(members[a], members[b])]
                d = d_ab.min() if linkage == 'single' else d_ab.max()
                if d < min_d:
                    min_d, min_a, min_b = d, a, b
        new_members = members[min_a] + members[min_b]
        Z.append([min_a, min_b, min_d, len(new_members)])
        del members[min_a]; del members[min_b]
        members[next_id] = new_members
        active = [c for c in active if c != min_a and c != min_b] + [next_id]
        next_id += 1
    return np.array(Z)

Z10_single = agglomerative_clustering(X10, 'single')
Z10_complete = agglomerative_clustering(X10, 'complete')

# --- 可视化 ---
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
dendrogram(Z10_single, ax=axes[0]); axes[0].set_title('层次聚类树状图 (单链接)')
dendrogram(Z10_complete, ax=axes[1]); axes[1].set_title('层次聚类树状图 (全链接)')
plt.tight_layout(); plt.savefig('figures_ml/ex10_hierarchical.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第10题] 层次聚类完成, 单链接vs全链接树状图已生成")
# 【思考题】单链接和全链接在什么情况下会产生不同的聚类结果？链式效应是什么？


# ============================================================
# 第11题: 朴素贝叶斯 - 高斯NB/伯努利NB/拉普拉斯平滑
# ============================================================
# 【数学推导】
# 贝叶斯定理: P(y|x) = P(x|y)·P(y) / P(x)
# 朴素假设: 特征条件独立 → P(x|y) = ∏ P(xᵢ|y)
# 预测: ŷ = argmax_y P(y) ∏ P(xᵢ|y)
#
# 高斯NB(连续特征): P(xᵢ|y) = (1/√(2πσ²)) exp(-(xᵢ-μ)²/(2σ²))
#   μ, σ² 为类别y下特征i的均值和方差
#
# 伯努利NB(二值特征): P(xᵢ|y) = p^{xᵢ} (1-p)^{1-xᵢ}
#
# 拉普拉斯平滑: p = (count + α) / (n + 2α)  避免零概率问题
#
# 对数预测(避免下溢): log P(y|x) ∝ log P(y) + Σ log P(xᵢ|y)

np.random.seed(42)
n11 = 150
X11 = np.vstack([np.random.randn(50, 2) + [2, 2], np.random.randn(50, 2) + [-2, 2], np.random.randn(50, 2) + [0, -2]])
y11 = np.array([0]*50 + [1]*50 + [2]*50)
classes11 = np.unique(y11)

# --- 高斯朴素贝叶斯 ---
class GaussianNB_scratch:
    def fit(self, X, y):
        self.classes = np.unique(y)
        self.mean = {}; self.var = {}; self.prior = {}
        for c in self.classes:
            Xc = X[y == c]
            self.mean[c] = Xc.mean(axis=0)
            self.var[c] = Xc.var(axis=0) + 1e-9  # 避免除零
            self.prior[c] = len(Xc) / len(y)
    def predict(self, X):
        log_probs = np.zeros((len(X), len(self.classes)))
        for i, c in enumerate(self.classes):
            log_lik = -0.5 * np.sum(np.log(2*np.pi*self.var[c]) + (X - self.mean[c])**2 / self.var[c], axis=1)
            log_probs[:, i] = np.log(self.prior[c]) + log_lik
        return self.classes[np.argmax(log_probs, axis=1)]

gnb = GaussianNB_scratch()
gnb.fit(X11, y11)
acc11 = np.mean(gnb.predict(X11) == y11)

# --- 伯努利朴素贝叶斯(二值特征) ---
n11b = 100
X11b = (np.random.rand(n11b, 5) > 0.5).astype(float)
y11b = np.array([0]*50 + [1]*50)
X11b[y11b == 1, :3] = (np.random.rand(50, 3) > 0.3).astype(float)  # 类别1前3个特征概率更高

class BernoulliNB_scratch:
    def fit(self, X, y, alpha=1.0):  # alpha: 拉普拉斯平滑参数
        self.classes = np.unique(y)
        self.feat_log_prob = {}; self.class_log_prior = {}
        for c in self.classes:
            Xc = X[y == c]
            # 拉普拉斯平滑: P(xᵢ=1|y) = (count + α) / (n + 2α)
            counts = Xc.sum(axis=0) + alpha
            total = len(Xc) + 2 * alpha
            self.feat_log_prob[c] = np.log(counts / total)
            self.class_log_prior[c] = np.log(len(Xc) / len(y))
    def predict(self, X):
        log_probs = np.zeros((len(X), len(self.classes)))
        for i, c in enumerate(self.classes):
            log_p = self.feat_log_prob[c]
            log_1mp = np.log1p(-np.exp(log_p))
            log_probs[:, i] = self.class_log_prior[c] + X @ log_p + (1 - X) @ log_1mp
        return self.classes[np.argmax(log_probs, axis=1)]

bnb = BernoulliNB_scratch()
bnb.fit(X11b, y11b, alpha=1.0)
acc11b = np.mean(bnb.predict(X11b) == y11b)

# --- 可视化 ---
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
xx11, yy11 = np.meshgrid(np.linspace(-5, 5, 100), np.linspace(-5, 5, 100))
grid11 = np.column_stack([xx11.ravel(), yy11.ravel()])
Z11 = gnb.predict(grid11).reshape(xx11.shape)
axes[0].contourf(xx11, yy11, Z11, alpha=0.3, cmap='Set1')
axes[0].scatter(X11[:, 0], X11[:, 1], c=y11, cmap='Set1', edgecolors='black', s=20)
axes[0].set_title(f'高斯朴素贝叶斯 (准确率: {acc11:.2%})')
axes[1].bar(['特征1', '特征2', '特征3', '特征4', '特征5'],
            [np.exp(bnb.feat_log_prob[1][i]) - np.exp(bnb.feat_log_prob[0][i]) for i in range(5)])
axes[1].set_title('伯努利NB: 类别1 vs 类别0 特征概率差'); axes[1].set_ylabel('P(x|y=1) - P(x|y=0)')
plt.tight_layout(); plt.savefig('figures_ml/ex11_naive_bayes.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第11题] 高斯NB准确率: {acc11:.2%}, 伯努利NB准确率: {acc11b:.2%}")
# 【思考题】朴素贝叶斯为什么叫"朴素"？特征条件独立假设在什么情况下不合理？


# ============================================================
# 第12题: PCA主成分分析 - 协方差矩阵特征分解与SVD
# ============================================================
# 【数学推导】
# 目标: 找到投影方向w, 使投影后方差最大
#   max wᵀΣw  s.t. ||w||=1,  Σ为协方差矩阵
#
# 方法一 - 协方差矩阵特征分解:
#   中心化: X_c = X - μ
#   协方差矩阵: Σ = (1/n) X_cᵀX_c
#   特征分解: Σ = VΛVᵀ
#   主成分: V的列(按特征值降序排列)
#   投影: Z = X_c · V[:, :k]
#
# 方法二 - SVD:
#   X_c = UΣVᵀ  (奇异值分解)
#   协方差矩阵特征值: λᵢ = Sᵢ²/n  (S为奇异值)
#   主成分: V的列(右奇异向量)
#
# 解释方差比: λᵢ / Σλⱼ  (衡量各主成分保留的信息量)

np.random.seed(42)
n12 = 200
X12 = np.random.randn(n12, 3)
X12[:, 2] = 0.5 * X12[:, 0] + 0.3 * X12[:, 1] + 0.1 * np.random.randn(n12)
X12_c = X12 - X12.mean(axis=0)

# 方法一: 协方差矩阵特征分解
cov12 = (X12_c.T @ X12_c) / n12
eigvals12, eigvecs12 = np.linalg.eigh(cov12)
idx12 = np.argsort(eigvals12)[::-1]
eigvals12, eigvecs12 = eigvals12[idx12], eigvecs12[:, idx12]

# 方法二: SVD
U12, S12, Vt12 = np.linalg.svd(X12_c, full_matrices=False)
# 验证: SVD的奇异值²/n = 协方差矩阵特征值
print(f"  协方差特征值: {eigvals12.round(4)}, SVD验证: {(S12**2/n12).round(4)}")

# 投影到2D
X12_pca = X12_c @ eigvecs12[:, :2]
evr12 = eigvals12 / eigvals12.sum()

# --- 可视化 ---
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
axes[0].scatter(X12_pca[:, 0], X12_pca[:, 1], s=10, alpha=0.5, c='steelblue')
axes[0].set_title('PCA降维到2D'); axes[0].set_xlabel(f'PC1 ({evr12[0]:.1%})'); axes[0].set_ylabel(f'PC2 ({evr12[1]:.1%})')
axes[1].bar(['PC1', 'PC2', 'PC3'], evr12, color=['steelblue', 'orange', 'green'])
axes[1].set_title('各主成分解释方差比'); axes[1].set_ylabel('方差比例')
plt.tight_layout(); plt.savefig('figures_ml/ex12_pca.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第12题] PCA解释方差比: {evr12.round(4)}, 前2维累计: {evr12[:2].sum():.2%}")
# 【思考题】PCA是无监督方法，为什么不考虑类别标签？这与LDA有什么本质区别？


# ============================================================
# 第13题: LDA线性判别分析 - 类间/类内散度矩阵
# ============================================================
# 【数学推导】
# 目标(费舍尔判别): 找到投影方向w, 最大化类间方差/类内方差
#   max J(w) = wᵀS_B w / wᵀS_W w
#
# 类内散度矩阵: S_W = Σ_c Σ_{x∈C_c} (x - μ_c)(x - μ_c)ᵀ
#   度量各类内部样本的分散程度
#
# 类间散度矩阵: S_B = Σ_c n_c (μ_c - μ)(μ_c - μ)ᵀ
#   度量各类中心之间的分散程度
#
# 求解: 对 S_W⁻¹S_B 做特征分解, 取最大特征值对应的特征向量
#   S_W⁻¹S_B w = λw
#   最优投影方向: w* = argmax J(w)
#   最大投影维度: min(n_classes-1, n_features)

np.random.seed(42)
n13 = 150
X13 = np.vstack([np.random.randn(50, 2) + [2, 2], np.random.randn(50, 2) + [-2, 2], np.random.randn(50, 2) + [0, -2]])
y13 = np.array([0]*50 + [1]*50 + [2]*50)
classes13 = np.unique(y13)
mean_all13 = X13.mean(axis=0)

S_W13 = np.zeros((2, 2))
S_B13 = np.zeros((2, 2))
class_means13 = {}
for c in classes13:
    Xc = X13[y13 == c]
    mc = Xc.mean(axis=0)
    class_means13[c] = mc
    diff = Xc - mc
    S_W13 += diff.T @ diff  # 类内散度
    dm = (mc - mean_all13).reshape(-1, 1)
    S_B13 += len(Xc) * (dm @ dm.T)  # 类间散度

# 求解 S_W^{-1} S_B 的特征值
eigvals13, eigvecs13 = np.linalg.eigh(np.linalg.inv(S_W13) @ S_B13)
idx13 = np.argsort(eigvals13)[::-1]
W13 = eigvecs13[:, idx13[:1]]  # 3类→最多2维, 取1维投影
X13_lda = X13 @ W13

# --- 可视化 ---
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
colors = ['red', 'blue', 'green']
for c in classes13:
    axes[0].scatter(X13[y13==c, 0], X13[y13==c, 1], c=colors[c], s=15, alpha=0.6, label=f'类别{c}')
# 绘制LDA投影方向
scale = 8
axes[0].arrow(0, 0, W13[0, 0]*scale, W13[1, 0]*scale, head_width=0.3, color='black', linewidth=2)
axes[0].set_title('LDA投影方向'); axes[0].legend()
for c in classes13:
    axes[1].hist(X13_lda[y13==c, 0], bins=15, alpha=0.6, color=colors[c], label=f'类别{c}')
axes[1].set_title('LDA 1D投影分布'); axes[1].set_xlabel('投影值'); axes[1].legend()
plt.tight_layout(); plt.savefig('figures_ml/ex13_lda.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第13题] LDA特征值: {eigvals13[idx13].round(4)}, 投影方向: {W13.ravel().round(3)}")
# 【思考题】LDA最多能投影到多少维？为什么？与PCA相比，LDA在什么场景下更有优势？


# ============================================================
# 第14题: KNN K近邻 - 距离度量与kd树
# ============================================================
# 【数学推导】
# KNN: 给定测试样本x, 找到训练集中最近的k个样本, 投票决定类别
#   ŷ = mode(y_{i₁}, y_{i₂}, ..., y_{i_k})  (多数投票)
#
# 距离度量:
#   欧氏距离: d(x,z) = √(Σ(xᵢ-zᵢ)²)  (L2范数)
#   曼哈顿距离: d(x,z) = Σ|xᵢ-zᵢ|  (L1范数)
#   余弦距离: d(x,z) = 1 - (x·z)/(||x||·||z||)  (方向差异)
#
# kd树: 对k维空间数据进行划分的数据结构
#   - 每次选一个维度取中位数进行分裂
#   - 查询复杂度: O(log n) (低维高效)
#   - 高维时退化为暴力搜索 (维度灾难)

np.random.seed(42)
n14 = 150
X14 = np.vstack([np.random.randn(50, 2) + [2, 2], np.random.randn(50, 2) + [-2, 2], np.random.randn(50, 2) + [0, -2]])
y14 = np.array([0]*50 + [1]*50 + [2]*50)

def knn_predict(X_train, y_train, X_test, k=5, metric='euclidean'):
    """KNN分类 (暴力搜索)"""
    if metric == 'euclidean':
        dists = cdist(X_test, X_train)
    elif metric == 'manhattan':
        dists = cdist(X_test, X_train, 'cityblock')
    elif metric == 'cosine':
        dists = cdist(X_test, X_train, 'cosine')
    preds = []
    for i in range(len(X_test)):
        knn_idx = np.argsort(dists[i])[:k]
        knn_labels = y_train[knn_idx].astype(int)
        preds.append(np.bincount(knn_labels).argmax())
    return np.array(preds)

# 不同k值和距离度量的准确率
for k_test in [1, 3, 5, 7]:
    for m_test in ['euclidean', 'manhattan', 'cosine']:
        acc = np.mean(knn_predict(X14, y14, X14, k=k_test, metric=m_test) == y14)

# --- 可视化 (k=5, 欧氏距离) ---
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
xx14, yy14 = np.meshgrid(np.linspace(-5, 5, 80), np.linspace(-5, 5, 80))
grid14 = np.column_stack([xx14.ravel(), yy14.ravel()])
for ax, k_val, title in [(axes[0], 1, 'KNN (k=1)'), (axes[1], 5, 'KNN (k=5)')]:
    Z14 = knn_predict(X14, y14, grid14, k=k_val).reshape(xx14.shape)
    ax.contourf(xx14, yy14, Z14, alpha=0.3, cmap='Set1')
    ax.scatter(X14[:, 0], X14[:, 1], c=y14, cmap='Set1', edgecolors='black', s=20)
    ax.set_title(title)
plt.tight_layout(); plt.savefig('figures_ml/ex14_knn.png', dpi=100, bbox_inches='tight'); plt.close()
acc14 = np.mean(knn_predict(X14, y14, X14, k=5) == y14)
print(f"[第14题] KNN(k=5,欧氏距离)准确率: {acc14:.2%}, k=1过拟合, k=5更平滑")
# 【思考题】k值如何影响KNN的偏差-方差权衡？什么是维度灾难？kd树在高维下为什么失效？


# ============================================================
# 第15题: 感知机 - PLA算法与口袋算法
# ============================================================
# 【数学推导】
# 感知机模型: f(x) = sign(wᵀx + b)
# 损失函数(误分类点到决策边界的距离):
#   L = -Σ_{i∈M} yᵢ(wᵀxᵢ + b),  M为误分类集合
#
# PLA (Perceptron Learning Algorithm):
#   随机选取误分类点 (xᵢ, yᵢ), 更新: w ← w + yᵢxᵢ, b ← b + yᵢ
#   收敛定理: 若数据线性可分, PLA在有限步内收敛 (Novikoff定理)
#   误分类次数上界: (R/γ)², R=max||xᵢ||, γ=最小间隔
#
# 口袋算法(Pocket): 数据不可分时, 保留最优w
#   每次更新后比较当前w与口袋中w的准确率, 保留更优的

np.random.seed(42)
n15 = 100
X15 = np.vstack([np.random.randn(n15//2, 2) + [2, 2], np.random.randn(n15//2, 2) + [-2, -2]])
y15 = np.array([1]*(n15//2) + [-1]*(n15//2))
X15_b = np.column_stack([np.ones(n15), X15])

# --- PLA算法 ---
w15_pla = np.zeros(3)
acc_history = []
for epoch in range(100):
    errors = 0
    for i in range(n15):
        if y15[i] * (X15_b[i] @ w15_pla) <= 0:  # 误分类
            w15_pla += y15[i] * X15_b[i]  # 更新权重
            errors += 1
    acc = np.mean(np.sign(X15_b @ w15_pla) == y15)
    acc_history.append(acc)
    if errors == 0:
        break

# --- 口袋算法 ---
w15_pocket = np.zeros(3)
best_acc = 0
for _ in range(2000):
    i = np.random.randint(n15)
    if y15[i] * (X15_b[i] @ w15_pocket) <= 0:
        w_new = w15_pocket + y15[i] * X15_b[i]
        acc = np.mean(np.sign(X15_b @ w_new) == y15)
        if acc > best_acc:
            w15_pocket = w_new.copy()
            best_acc = acc

# --- 可视化 ---
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
axes[0].scatter(X15[y15==1, 0], X15[y15==1, 1], c='blue', s=20, label='类别+1')
axes[0].scatter(X15[y15==-1, 0], X15[y15==-1, 1], c='red', s=20, label='类别-1')
xl = np.linspace(-5, 5, 100)
axes[0].plot(xl, -(w15_pla[0]+w15_pla[1]*xl)/w15_pla[2], 'g-', label=f'PLA (acc={acc_history[-1]:.2%})')
axes[0].plot(xl, -(w15_pocket[0]+w15_pocket[1]*xl)/w15_pocket[2], 'm--', label=f'Pocket (acc={best_acc:.2%})')
axes[0].set_title('感知机决策边界'); axes[0].legend()
axes[1].plot(acc_history, 'g-'); axes[1].set_xlabel('迭代轮次'); axes[1].set_ylabel('准确率'); axes[1].set_title('PLA收敛曲线')
plt.tight_layout(); plt.savefig('figures_ml/ex15_perceptron.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第15题] PLA准确率: {acc_history[-1]:.2%} (收敛于第{len(acc_history)}轮), Pocket准确率: {best_acc:.2%}")
# 【思考题】感知机与SVM有什么联系和区别？为什么感知机的解不唯一而SVM的解是唯一的？

print("\n" + "=" * 60)
print("机器学习模型数学 - 15题练习全部完成!")
print(f"图片已保存到 figures_ml/ 目录")
print("=" * 60)
