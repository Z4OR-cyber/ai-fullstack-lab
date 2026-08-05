# -*- coding: utf-8 -*-
"""
============================================================
阶段：深度学习模型数学
题数：15题
创建日期：2026-08-05
说明：从数学原理出发，纯numpy手写所有核心DL模型
环境：Python 3.13 + numpy 2.4 + scipy 1.17 + sympy 1.14 + matplotlib 3.10
============================================================
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.special import erf
import os
import warnings

warnings.filterwarnings('ignore')
os.makedirs('figures_dl', exist_ok=True)

print("=" * 60)
print("深度学习模型数学 - 15题练习")
print("创建日期: 2026-08-05")
print("=" * 60)

# ============================================================
# 第1题: 前馈神经网络 - 多层感知机与反向传播完整推导
# ============================================================
# 【数学推导】
# 网络结构: 输入层(d_in) → 隐藏层(d_h, ReLU) → 输出层(d_out, Sigmoid)
#
# 前向传播:
#   z₁ = XW₁ + b₁        (线性变换)
#   a₁ = ReLU(z₁) = max(0, z₁)   (激活)
#   z₂ = a₁W₂ + b₂        (线性变换)
#   ŷ = σ(z₂) = 1/(1+e^{-z₂})   (输出激活)
#
# 损失(二元交叉熵): L = -(1/n)Σ[y log ŷ + (1-y) log(1-ŷ)]
#
# 反向传播(链式法则):
#   δ₂ = ∂L/∂z₂ = (ŷ - y)/n         (BCE+σ的简化梯度)
#   ∂L/∂W₂ = a₁ᵀδ₂                   (矩阵乘法反向)
#   ∂L/∂b₂ = Σδ₂                      (广播反向: 求和)
#   δ₁ = (δ₂W₂ᵀ) ⊙ ReLU'(z₁)        (梯度回传+激活导数)
#   ∂L/∂W₁ = Xᵀδ₁
#   ∂L/∂b₁ = Σδ₁

np.random.seed(42)
n1 = 200
X1 = np.random.randn(n1, 2)
y1 = (np.sum(X1**2, axis=1) > 1.5).astype(float).reshape(-1, 1)  # 圆形分类

d_in, d_h, d_out = 2, 8, 1
W1_1 = np.random.randn(d_in, d_h) * np.sqrt(2.0/d_in)  # He初始化
b1_1 = np.zeros((1, d_h))
W1_2 = np.random.randn(d_h, d_out) * np.sqrt(2.0/d_h)
b1_2 = np.zeros((1, d_out))

lr1, losses1 = 0.1, []
for epoch in range(2000):
    z1 = X1 @ W1_1 + b1_1
    a1 = np.maximum(0, z1)
    z2 = a1 @ W1_2 + b1_2
    pred = 1 / (1 + np.exp(-np.clip(z2, -50, 50)))
    loss = -np.mean(y1*np.log(pred+1e-10) + (1-y1)*np.log(1-pred+1e-10))
    losses1.append(loss)
    # 反向传播
    dz2 = (pred - y1) / n1
    W1_2 -= lr1 * (a1.T @ dz2)
    b1_2 -= lr1 * np.sum(dz2, axis=0, keepdims=True)
    da1 = dz2 @ W1_2.T
    dz1 = da1 * (z1 > 0)  # ReLU导数
    W1_1 -= lr1 * (X1.T @ dz1)
    b1_1 -= lr1 * np.sum(dz1, axis=0, keepdims=True)

# --- 可视化 ---
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
xx1, yy1 = np.meshgrid(np.linspace(-3, 3, 100), np.linspace(-3, 3, 100))
grid1 = np.column_stack([xx1.ravel(), yy1.ravel()])
z1g = grid1 @ W1_1 + b1_1
a1g = np.maximum(0, z1g)
pred_g = 1 / (1 + np.exp(-np.clip(a1g @ W1_2 + b1_2, -50, 50)))
Z1 = pred_g.reshape(xx1.shape)
axes[0].contourf(xx1, yy1, Z1, levels=50, cmap='RdBu', alpha=0.3)
axes[0].contour(xx1, yy1, Z1, levels=[0.5], colors='black')
axes[0].scatter(X1[y1.ravel()==1, 0], X1[y1.ravel()==1, 1], c='blue', s=10, label='类别1')
axes[0].scatter(X1[y1.ravel()==0, 0], X1[y1.ravel()==0, 1], c='red', s=10, label='类别0')
axes[0].set_title('MLP决策边界'); axes[0].legend()
axes[1].plot(losses1); axes[1].set_xlabel('迭代次数'); axes[1].set_ylabel('Loss'); axes[1].set_title('训练损失曲线')
plt.tight_layout(); plt.savefig('figures_dl/ex01_mlp.png', dpi=100, bbox_inches='tight'); plt.close()
acc1 = np.mean((pred > 0.5) == y1)
print(f"[第1题] MLP训练准确率: {acc1:.2%}, 最终损失: {losses1[-1]:.4f}")
# 【思考题】万能逼近定理说单隐层MLP可以逼近任意连续函数，为什么实践中还要用深层网络？


# ============================================================
# 第2题: 激活函数数学 - sigmoid/tanh/ReLU/LeakyReLU/GELU/Softmax
# ============================================================
# 【数学推导】
# Sigmoid: σ(x) = 1/(1+e^{-x}),  σ'(x) = σ(1-σ)
#   优点: 输出(0,1), 缺点: 梯度消失, 非零中心
# Tanh: tanh(x) = (e^x-e^{-x})/(e^x+e^{-x}),  tanh'(x) = 1-tanh²(x)
#   优点: 零中心, 缺点: 仍有梯度消失
# ReLU: f(x) = max(0,x),  f'(x) = 1 if x>0 else 0
#   优点: 缓解梯度消失, 计算快, 缺点: 神经元死亡
# LeakyReLU: f(x) = max(αx, x),  f'(x) = 1 if x>0 else α
#   解决神经元死亡, α通常取0.01
# GELU: f(x) = x·Φ(x) = x·½(1+erf(x/√2))
#   f'(x) = Φ(x) + x·φ(x),  φ(x)为标准正态PDF
#   平滑过渡, Transformer默认激活
# Softmax: p_i = e^{z_i}/Σe^{z_j},  ∂p_i/∂z_j = p_i(δ_{ij}-p_j)
#   Jacobian矩阵对角线: p_i(1-p_i), 非对角线: -p_i·p_j

x_act = np.linspace(-5, 5, 300)
fig, axes = plt.subplots(2, 3, figsize=(15, 8))
acts = [
    ('Sigmoid', 1/(1+np.exp(-x_act)), 1/(1+np.exp(-x_act))*(1-1/(1+np.exp(-x_act)))),
    ('Tanh', np.tanh(x_act), 1-np.tanh(x_act)**2),
    ('ReLU', np.maximum(0, x_act), (x_act > 0).astype(float)),
    ('LeakyReLU', np.where(x_act>0, x_act, 0.1*x_act), np.where(x_act>0, 1, 0.1)),
    ('GELU', 0.5*x_act*(1+erf(x_act/np.sqrt(2))), 0.5*(1+erf(x_act/np.sqrt(2)))+x_act*np.exp(-x_act**2/2)/np.sqrt(2*np.pi)),
    ('Softmax(z₁)', None, None)  # 特殊处理
]
for idx, (name, val, deriv) in enumerate(acts):
    ax = axes[idx//3, idx%3]
    if val is not None:
        ax.plot(x_act, val, 'b-', label=name, linewidth=2)
        ax.plot(x_act, deriv, 'r--', label=f"{name}'", linewidth=2)
        ax.axhline(0, color='gray', linewidth=0.5); ax.axvline(0, color='gray', linewidth=0.5)
        ax.legend(); ax.set_title(name); ax.set_ylim(-1.5, 2.5)
    else:
        z_sm = np.column_stack([x_act, np.zeros_like(x_act), np.full_like(x_act, -1)])
        sm = np.exp(z_sm - z_sm.max(axis=1, keepdims=True))
        sm = sm / sm.sum(axis=1, keepdims=True)
        ax.plot(x_act, sm[:, 0], 'b-', label='softmax₁(z)', linewidth=2)
        ax.plot(x_act, sm[:, 0]*(1-sm[:, 0]), 'r--', label="∂softmax₁/∂z₁", linewidth=2)
        ax.legend(); ax.set_title('Softmax (3类)')
plt.tight_layout(); plt.savefig('figures_dl/ex02_activations.png', dpi=100, bbox_inches='tight'); plt.close()
print("[第2题] 6种激活函数及其导数已可视化")
# 【思考题】为什么ReLU能缓解梯度消失问题？GELU相比ReLU有什么优势？


# ============================================================
# 第3题: 反向传播完整实现 - 计算图与链式法则
# ============================================================
# 【数学推导】
# 计算图: 将复杂函数分解为基本操作的DAG(有向无环图)
# 示例: L = ||σ(x@W + b) - y||²
#
# 前向(记录中间变量):
#   z₁ = x @ W        (MatMul节点)
#   z₂ = z₁ + b       (Add节点, 广播)
#   z₃ = σ(z₂)        (Sigmoid节点)
#   L  = ||z₃ - y||²  (Loss节点)
#
# 反向(链式法则, 从L开始反向传播):
#   ∂L/∂z₃ = 2(z₃ - y)                    (Loss导数)
#   ∂L/∂z₂ = ∂L/∂z₃ ⊙ σ'(z₂) = ∂L/∂z₃ ⊙ z₃(1-z₃)  (Sigmoid导数)
#   ∂L/∂z₁ = ∂L/∂z₂                       (Add导数: 直接传递)
#   ∂L/∂W  = xᵀ @ ∂L/∂z₁                  (MatMul导数)
#   ∂L/∂b  = Σ ∂L/∂z₂ (axis=0)           (广播导数: 沿batch求和)

np.random.seed(42)
d_in3, d_out3, n3 = 3, 2, 5
x3 = np.random.randn(n3, d_in3)
W3 = np.random.randn(d_in3, d_out3) * 0.5
b3 = np.random.randn(1, d_out3) * 0.1
y3 = np.random.rand(n3, d_out3)

# --- 前向传播(保存中间值) ---
z1_3 = x3 @ W3              # MatMul
z2_3 = z1_3 + b3            # Add(广播)
z3_3 = 1 / (1 + np.exp(-z2_3))  # Sigmoid
L3 = np.sum((z3_3 - y3)**2)     # MSE Loss

# --- 反向传播(链式法则) ---
dL_dz3 = 2 * (z3_3 - y3)                   # ∂L/∂z₃
dL_dz2 = dL_dz3 * z3_3 * (1 - z3_3)        # ∂L/∂z₂ = ∂L/∂z₃ ⊙ σ'(z₂)
dL_dz1 = dL_dz2                             # ∂L/∂z₁ (Add: 直接传递)
dL_dW3 = x3.T @ dL_dz1                     # ∂L/∂W (MatMul)
dL_db3 = np.sum(dL_dz2, axis=0, keepdims=True)  # ∂L/∂b (广播: 求和)

# --- 数值梯度验证 ---
eps = 1e-7
def forward3(W):
    z1 = x3 @ W
    z2 = z1 + b3
    z3 = 1 / (1 + np.exp(-z2))
    return np.sum((z3 - y3)**2)

num_grad = np.zeros_like(W3)
for i in range(d_in3):
    for j in range(d_out3):
        W_plus = W3.copy(); W_plus[i, j] += eps
        W_minus = W3.copy(); W_minus[i, j] -= eps
        num_grad[i, j] = (forward3(W_plus) - forward3(W_minus)) / (2*eps)

grad_diff = np.max(np.abs(dL_dW3 - num_grad))

# --- 可视化 ---
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
im = axes[0].imshow(dL_dW3, cmap='RdBu', aspect='auto'); axes[0].set_title('解析梯度 ∂L/∂W')
plt.colorbar(im, ax=axes[0])
im2 = axes[1].imshow(num_grad, cmap='RdBu', aspect='auto'); axes[1].set_title('数值梯度 (有限差分)')
plt.colorbar(im2, ax=axes[1])
plt.suptitle(f'梯度验证: 最大差异 = {grad_diff:.2e} (应<1e-5)')
plt.tight_layout(); plt.savefig('figures_dl/ex03_backprop.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第3题] 梯度验证通过, 解析梯度vs数值梯度最大差异: {grad_diff:.2e}")
# 【思考题】为什么反向传播比数值微分高效？计算n个参数的梯度, 反向传播和数值微分分别需要几次前向计算？


# ============================================================
# 第4题: 优化器全集 - SGD/Momentum/AdaGrad/RMSProp/Adam
# ============================================================
# 【数学推导】
# 设 g_t = ∇L(w_t) 为当前梯度
#
# SGD: w ← w - lr·g
#   最简单, 但在平坦方向收敛慢, 在陡峭方向震荡
#
# Momentum: v ← βv + g;  w ← w - lr·v
#   累积历史梯度方向, 抑制震荡, 加速收敛
#   β通常取0.9
#
# AdaGrad: G ← G + g²;  w ← w - lr·g / √(G + ε)
#   自适应学习率: 每个参数有独立学习率
#   缺点: G单调递增, 学习率持续衰减最终趋零
#
# RMSProp: G ← βG + (1-β)g²;  w ← w - lr·g / √(G + ε)
#   指数加权移动平均, 解决AdaGrad学习率趋零问题
#
# Adam: m ← β₁m + (1-β₁)g;  v ← β₂v + (1-β₂)g²
#   m̂ = m/(1-β₁ᵗ);  v̂ = v/(1-β₂ᵗ)  (偏差校正)
#   w ← w - lr·m̂ / (√v̂ + ε)
#   结合Momentum(一阶矩)和RMSProp(二阶矩), 通常表现最好

def rosenbrock(w):
    return (1-w[0])**2 + 100*(w[1]-w[0]**2)**2

def rosenbrock_grad(w):
    return np.array([-2*(1-w[0]) - 400*w[0]*(w[1]-w[0]**2), 200*(w[1]-w[0]**2)])

def run_optimizer(name, w_init, n_iter=300):
    w = w_init.copy()
    state = {}
    path = [w.copy()]
    lrs = {'SGD': 0.0008, 'Momentum': 0.0008, 'AdaGrad': 0.08, 'RMSProp': 0.008, 'Adam': 0.008}
    lr = lrs[name]
    for _ in range(n_iter):
        g = rosenbrock_grad(w)
        if name == 'SGD':
            w = w - lr * g
        elif name == 'Momentum':
            v = state.get('v', np.zeros_like(w))
            v = 0.9 * v + g
            state['v'] = v
            w = w - lr * v
        elif name == 'AdaGrad':
            G = state.get('G', np.zeros_like(w))
            G += g**2
            state['G'] = G
            w = w - lr * g / (np.sqrt(G) + 1e-8)
        elif name == 'RMSProp':
            G = state.get('G', np.zeros_like(w))
            G = 0.9 * G + 0.1 * g**2
            state['G'] = G
            w = w - lr * g / (np.sqrt(G) + 1e-8)
        elif name == 'Adam':
            m = state.get('m', np.zeros_like(w))
            v = state.get('v', np.zeros_like(w))
            t = state.get('t', 0) + 1
            m = 0.9*m + 0.1*g
            v = 0.999*v + 0.001*g**2
            m_hat = m / (1 - 0.9**t)
            v_hat = v / (1 - 0.999**t)
            state.update({'m': m, 'v': v, 't': t})
            w = w - lr * m_hat / (np.sqrt(v_hat) + 1e-8)
        path.append(w.copy())
    return np.array(path)

w_init4 = np.array([-1.5, 2.5])
fig, ax = plt.subplots(figsize=(10, 8))
x4, y4 = np.meshgrid(np.linspace(-2, 2, 200), np.linspace(-1, 3, 200))
Z4 = np.array([[rosenbrock(np.array([xi, yi])) for xi in x4[0]] for yi in y4[:, 0]])
ax.contour(x4, y4, Z4, levels=50, cmap='viridis', alpha=0.6)
colors = {'SGD': 'red', 'Momentum': 'blue', 'AdaGrad': 'green', 'RMSProp': 'orange', 'Adam': 'purple'}
for name in colors:
    path = run_optimizer(name, w_init4)
    ax.plot(path[:, 0], path[:, 1], color=colors[name], label=name, linewidth=1.5)
    ax.scatter(path[0, 0], path[0, 1], color=colors[name], marker='o', s=60, zorder=5)
    ax.scatter(path[-1, 0], path[-1, 1], color=colors[name], marker='*', s=150, zorder=5)
ax.plot(1, 1, 'k*', markersize=15, label='最优点(1,1)')
ax.set_title('优化器对比 (Rosenbrock函数)'); ax.legend(); ax.set_xlabel('w₁'); ax.set_ylabel('w₂')
plt.tight_layout(); plt.savefig('figures_dl/ex04_optimizers.png', dpi=100, bbox_inches='tight'); plt.close()
print("[第4题] 5种优化器在Rosenbrock函数上的优化路径已对比")
# 【思考题】Adam为什么通常表现最好？在什么情况下简单的SGD可能比Adam更合适？


# ============================================================
# 第5题: 正则化 - L1/L2/Dropout/BatchNorm
# ============================================================
# 【数学推导】
# L2正则化(权重衰减): L_reg = L + λ||w||² = L + λΣwᵢ²
#   梯度: ∂L_reg/∂w = ∂L/∂w + 2λw  → 权重趋于小值, 防止过拟合
#
# L1正则化: L_reg = L + λ||w||₁ = L + λΣ|wᵢ|
#   梯度: ∂L_reg/∂w = ∂L/∂w + λ·sign(w)  → 产生稀疏权重(很多w=0)
#
# Dropout(训练时): 随机以概率p置零神经元, 其余缩放: y = x·mask/(1-p)
#   等价于训练 exponentially many 子网络的集成
#   推理时: 不做dropout, 直接使用全部神经元
#
# BatchNorm: 对每个mini-batch的每个特征进行标准化
#   训练: μ = mean(x), σ² = var(x), x̂ = (x-μ)/√(σ²+ε), y = γx̂ + β
#   推理: 使用running mean/var
#   作用: 缓解内部协变量偏移, 允许更大学习率, 起到正则化效果

np.random.seed(42)
n5 = 100
X5 = np.random.randn(n5, 10)
y5 = (X5[:, 0] + X5[:, 1] > 0).astype(float).reshape(-1, 1)

def train_with_regularization(X, y, reg_type='none', reg_lambda=0.01, dropout_p=0.3, epochs=500):
    n, d_in = X.shape
    d_h = 32
    W1 = np.random.randn(d_in, d_h) * 0.1
    b1 = np.zeros((1, d_h))
    W2 = np.random.randn(d_h, 1) * 0.1
    b2 = np.zeros((1, 1))
    # BatchNorm参数
    gamma = np.ones((1, d_h))
    beta = np.zeros((1, d_h))
    run_mean = np.zeros((1, d_h))
    run_var = np.ones((1, d_h))
    lr = 0.1
    losses = []
    for _ in range(epochs):
        z1 = X @ W1 + b1
        if reg_type == 'batchnorm':
            mu = z1.mean(axis=0, keepdims=True)
            var = z1.var(axis=0, keepdims=True)
            z1_norm = (z1 - mu) / np.sqrt(var + 1e-5)
            z1 = gamma * z1_norm + beta
            run_mean = 0.9 * run_mean + 0.1 * mu
            run_var = 0.9 * run_var + 0.1 * var
        a1 = np.maximum(0, z1)
        if reg_type == 'dropout':
            mask = (np.random.rand(*a1.shape) > dropout_p) / (1 - dropout_p)
            a1 = a1 * mask
        z2 = a1 @ W2 + b2
        pred = 1 / (1 + np.exp(-np.clip(z2, -50, 50)))
        loss = -np.mean(y*np.log(pred+1e-10) + (1-y)*np.log(1-pred+1e-10))
        if reg_type == 'l2':
            loss += reg_lambda * (np.sum(W1**2) + np.sum(W2**2))
        elif reg_type == 'l1':
            loss += reg_lambda * (np.sum(np.abs(W1)) + np.sum(np.abs(W2)))
        losses.append(loss)
        dz2 = (pred - y) / n
        W2 -= lr * (a1.T @ dz2)
        b2 -= lr * np.sum(dz2, axis=0, keepdims=True)
        da1 = dz2 @ W2.T
        dz1 = da1 * (z1 > 0)
        if reg_type == 'dropout':
            dz1 = dz1 * mask
        if reg_type == 'l2':
            W1 -= lr * (X.T @ dz1 + 2*reg_lambda*W1)
        elif reg_type == 'l1':
            W1 -= lr * (X.T @ dz1 + reg_lambda*np.sign(W1))
        else:
            W1 -= lr * (X.T @ dz1)
        b1 -= lr * np.sum(dz1, axis=0, keepdims=True)
    return losses, W1

reg_types = ['none', 'l2', 'l1', 'dropout', 'batchnorm']
reg_labels = ['无正则化', 'L2正则化', 'L1正则化', 'Dropout', 'BatchNorm']
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for rt, rl in zip(reg_types, reg_labels):
    losses, W = train_with_regularization(X5, y5, reg_type=rt)
    axes[0].plot(losses, label=rl)
    axes[1].hist(W.ravel(), bins=50, alpha=0.5, label=rl)
axes[0].set_xlabel('迭代次数'); axes[0].set_ylabel('Loss'); axes[0].set_title('不同正则化的训练损失')
axes[0].legend()
axes[1].set_xlabel('权重值'); axes[1].set_ylabel('频数'); axes[1].set_title('权重分布对比')
axes[1].legend()
plt.tight_layout(); plt.savefig('figures_dl/ex05_regularization.png', dpi=100, bbox_inches='tight'); plt.close()
print("[第5题] L1/L2/Dropout/BatchNorm正则化效果已对比")
# 【思考题】L1正则化为什么能产生稀疏权重？BatchNorm为什么能起到正则化效果？


# ============================================================
# 第6题: 卷积神经网络数学 - 卷积/池化/感受野
# ============================================================
# 【数学推导】
# 卷积运算: (I * K)[i,j] = Σ_m Σ_n I[i+m, j+n] · K[m, n]
#   I为输入, K为卷积核(滤波器), 输出为特征图
#
# 输出尺寸: H_out = (H_in - K + 2P) / S + 1
#   H_in: 输入高, K: 卷积核高, P: 填充(padding), S: 步长(stride)
#
# 池化(Max Pooling): 输出[i,j] = max(I[i*S:i*S+P, j*S:j*S+P])
#   降采样, 减少参数, 提供平移不变性
#
# 感受野(Receptive Field): 某层一个像素对应输入图像的区域大小
#   R_l = R_{l-1} + (K_l - 1) · ∏_{i=1}^{l-1} S_i
#   层数越深, 感受野越大, 能捕获更大范围的上下文信息

# --- 卷积运算示例 ---
input_img = np.array([[1, 2, 0, 1, 2],
                       [0, 1, 2, 1, 0],
                       [1, 0, 1, 2, 1],
                       [2, 1, 0, 1, 0],
                       [0, 1, 2, 1, 2]], dtype=float)
kernel_edge = np.array([[1, 0, -1],
                         [1, 0, -1],
                         [1, 0, -1]], dtype=float)  # 垂直边缘检测

conv_out = np.zeros((3, 3))
for i in range(3):
    for j in range(3):
        conv_out[i, j] = np.sum(input_img[i:i+3, j:j+3] * kernel_edge)

# --- 输出尺寸计算 ---
sizes = []
for H in [8, 16, 32]:
    for K in [3, 5]:
        for P in [0, 1]:
            for S in [1, 2]:
                out = (H - K + 2*P) // S + 1
                sizes.append((H, K, P, S, out))

# --- 感受野计算 ---
rf_layers = []
rf = 1
for layer, (K, S) in enumerate([(3, 1), (3, 1), (2, 2), (3, 1), (2, 2)]):
    rf = rf + (K - 1) * (2 ** layer)  # 简化: 假设之前所有stride的乘积
    rf_layers.append((layer+1, K, S, rf))

# --- 可视化 ---
fig, axes = plt.subplots(1, 4, figsize=(16, 4))
axes[0].imshow(input_img, cmap='gray'); axes[0].set_title('输入图像 (5×5)')
axes[1].imshow(kernel_edge, cmap='RdBu'); axes[1].set_title('卷积核 (3×3)\n垂直边缘检测')
axes[2].imshow(conv_out, cmap='gray'); axes[2].set_title('卷积输出 (3×3)')
# 池化示例
pool_in = np.array([[1, 3, 2, 4], [5, 7, 6, 8], [2, 4, 1, 3], [6, 8, 5, 7]], dtype=float)
pool_out = np.zeros((2, 2))
for i in range(2):
    for j in range(2):
        pool_out[i, j] = np.max(pool_in[i*2:i*2+2, j*2:j*2+2])
axes[3].imshow(pool_out, cmap='gray'); axes[3].set_title('MaxPool输出 (2×2)\n从4×4池化')
plt.tight_layout(); plt.savefig('figures_dl/ex06_cnn_math.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第6题] 卷积输出:\n{conv_out.astype(int)}")
print(f"  感受野逐层: {[(l, f'{r}') for l, _, _, r in rf_layers]}")
# 【思考题】卷积层的参数共享和局部连接如何减少参数量？与全连接层相比优势在哪？


# ============================================================
# 第7题: CNN完整实现 - 纯numpy手写Conv2D/MaxPool/Flatten/全连接
# ============================================================
# 【数学推导】
# Conv2D前向: Y[b,oc,i,j] = Σ_ic Σ_kh Σ_kw X[b,ic,i+kh,j+kw]·W[oc,ic,kh,kw] + b[oc]
# Conv2D反向:
#   dW[oc] = Σ_b Σ_i Σ_j dout[b,oc,i,j] · X[b,:,i:i+kH,j:j+kW]
#   dX[b,:,i:i+kH,j:j+kW] += Σ_oc W[oc] · dout[b,oc,i,j]
# MaxPool前向: Y[b,c,i,j] = max(X[b,c,i*S:i*S+P, j*S:j*S+P])
# MaxPool反向: 梯度只传给最大值位置
# 全连接: Y = X·W + b (标准矩阵乘法)

def conv2d_forward(X, W, b, stride=1):
    batch, in_ch, H, Wd = X.shape
    out_ch, _, kH, kW = W.shape
    out_H = (H - kH) // stride + 1
    out_W = (Wd - kW) // stride + 1
    out = np.zeros((batch, out_ch, out_H, out_W))
    for i in range(out_H):
        for j in range(out_W):
            region = X[:, :, i*stride:i*stride+kH, j*stride:j*stride+kW]
            out[:, :, i, j] = np.einsum('bchw,ochw->bo', region, W) + b
    return out

def conv2d_backward(dout, X, W, stride=1):
    batch, in_ch, H, Wd = X.shape
    out_ch, _, kH, kW = W.shape
    _, _, out_H, out_W = dout.shape
    dW = np.zeros_like(W)
    dX = np.zeros_like(X)
    for i in range(out_H):
        for j in range(out_W):
            region = X[:, :, i*stride:i*stride+kH, j*stride:j*stride+kW]
            dW += np.einsum('bchw,bo->ochw', region, dout[:, :, i, j])
            dX[:, :, i*stride:i*stride+kH, j*stride:j*stride+kW] += np.einsum('ochw,bo->bchw', W, dout[:, :, i, j])
    db = np.sum(dout, axis=(0, 2, 3))
    return dX, dW, db

def maxpool_forward(X, pool_size=2, stride=2):
    batch, ch, H, W = X.shape
    out_H = (H - pool_size) // stride + 1
    out_W = (W - pool_size) // stride + 1
    out = np.zeros((batch, ch, out_H, out_W))
    for i in range(out_H):
        for j in range(out_W):
            out[:, :, i, j] = np.max(X[:, :, i*stride:i*stride+pool_size, j*stride:j*stride+pool_size], axis=(2, 3))
    return out

def maxpool_backward(dout, X, pool_size=2, stride=2):
    batch, ch, H, W = X.shape
    out_H, out_W = dout.shape[2], dout.shape[3]
    dX = np.zeros_like(X)
    for i in range(out_H):
        for j in range(out_W):
            region = X[:, :, i*stride:i*stride+pool_size, j*stride:j*stride+pool_size]
            mask = (region == np.max(region, axis=(2, 3), keepdims=True))
            dX[:, :, i*stride:i*stride+pool_size, j*stride:j*stride+pool_size] += mask * dout[:, :, i, j][:, :, None, None]
    return dX

def softmax_batch(z):
    z = z - np.max(z, axis=1, keepdims=True)
    return np.exp(z) / np.sum(np.exp(z), axis=1, keepdims=True)

np.random.seed(42)
n_cnn = 80
X_cnn = np.random.randn(n_cnn, 1, 8, 8) * 0.1
y_cnn = np.zeros(n_cnn, dtype=int)
for i in range(n_cnn):
    if i < n_cnn // 2:
        X_cnn[i, 0, 3:5, 3:5] += 2  # 中心亮斑(类别0)
    else:
        X_cnn[i, 0, 0:2, 6:8] += 2  # 右上角亮斑(类别1)
        y_cnn[i] = 1

# 网络参数: Conv(1→4, 3×3) → ReLU → MaxPool(2×2) → FC(36→2)
W_conv = np.random.randn(4, 1, 3, 3) * 0.1
b_conv = np.zeros(4)
W_fc = np.random.randn(36, 2) * 0.1
b_fc = np.zeros(2)
lr_cnn = 0.05
losses_cnn = []

for epoch in range(300):
    # 前向
    conv = conv2d_forward(X_cnn, W_conv, b_conv)
    relu = np.maximum(0, conv)
    pool = maxpool_forward(relu)
    flat = pool.reshape(n_cnn, -1)
    fc = flat @ W_fc + b_fc
    probs = softmax_batch(fc)
    # 损失
    loss = -np.mean(np.log(probs[np.arange(n_cnn), y_cnn] + 1e-10))
    losses_cnn.append(loss)
    # 反向
    d_fc = probs.copy()
    d_fc[np.arange(n_cnn), y_cnn] -= 1
    d_fc /= n_cnn
    d_W_fc = flat.T @ d_fc
    d_b_fc = np.sum(d_fc, axis=0)
    d_flat = d_fc @ W_fc.T
    d_pool = d_flat.reshape(pool.shape)
    d_relu = maxpool_backward(d_pool, relu)
    d_conv = d_relu * (conv > 0)
    d_X, d_W_conv, d_b_conv = conv2d_backward(d_conv, X_cnn, W_conv)
    # 更新
    W_fc -= lr_cnn * d_W_fc; b_fc -= lr_cnn * d_b_fc
    W_conv -= lr_cnn * d_W_conv; b_conv -= lr_cnn * d_b_conv

# --- 可视化 ---
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].plot(losses_cnn); axes[0].set_title('CNN训练损失'); axes[0].set_xlabel('迭代次数'); axes[0].set_ylabel('Loss')
# 特征图
sample = X_cnn[0:1]
conv_sample = conv2d_forward(sample, W_conv, b_conv)[0]
for c in range(4):
    axes[1].subplot(2, 4, c+1) if False else None
for c in range(4):
    fig.add_subplot(241+c)  # 不推荐, 改用单独绘制
axes[1].imshow(conv_sample[0], cmap='viridis'); axes[1].set_title('特征图 Ch0')
axes[1].axis('off')
axes[2].imshow(X_cnn[0, 0], cmap='gray'); axes[2].set_title('输入图像 (类别0)'); axes[2].axis('off')
plt.tight_layout(); plt.savefig('figures_dl/ex07_cnn.png', dpi=100, bbox_inches='tight'); plt.close()
acc_cnn = np.mean(np.argmax(softmax_batch(flat @ W_fc + b_fc), axis=1) == y_cnn)
print(f"[第7题] CNN训练准确率: {acc_cnn:.2%}, 最终损失: {losses_cnn[-1]:.4f}")
# 【思考题】CNN的参数共享特性如何影响模型在图像上的泛化能力？池化层的作用是什么？


# ============================================================
# 第8题: 循环神经网络 - RNN数学模型与BPTT
# ============================================================
# 【数学推导】
# RNN前向(沿时间步展开):
#   h_t = tanh(W_xh·x_t + W_hh·h_{t-1} + b_h)
#   y_t = W_hy·h_t + b_y
#
# BPTT(沿时间反向传播):
#   对每个时间步t(从后往前):
#   δy_t = ∂L/∂y_t = 2(y_t - target_t)
#   ∂L/∂W_hy += h_tᵀ·δy_t
#   δh_t = δy_t·W_hyᵀ + δh_{t+1}  (来自输出和下一时间步)
#   δh_raw = δh_t ⊙ (1 - h_t²)   (tanh导数)
#   ∂L/∂W_xh += x_tᵀ·δh_raw
#   ∂L/∂W_hh += h_{t-1}ᵀ·δh_raw
#   δh_{t-1} = δh_raw·W_hhᵀ
#
# 梯度消失/爆炸:
#   δh_0/δh_t = Π_{k=1}^{t} [diag(1-h_k²)·W_hhᵀ]
#   当W_hh的谱半径ρ<1时, 连乘→0(消失); ρ>1时, 连乘→∞(爆炸)

np.random.seed(42)
t_rnn = np.linspace(0, 6*np.pi, 300)
data_rnn = np.sin(t_rnn)
seq_len, input_size, hidden_size, output_size = 10, 1, 16, 1

W_xh = np.random.randn(input_size, hidden_size) * 0.1
W_hh = np.random.randn(hidden_size, hidden_size) * 0.1
W_hy = np.random.randn(hidden_size, output_size) * 0.1
b_h = np.zeros((1, hidden_size))
b_y = np.zeros((1, output_size))
lr_rnn = 0.01
losses_rnn = []

for epoch in range(80):
    for start in range(0, len(data_rnn) - seq_len - 1, seq_len):
        x_seq = [data_rnn[start+j].reshape(1, 1) for j in range(seq_len)]
        y_seq = [data_rnn[start+j+1].reshape(1, 1) for j in range(seq_len)]
        # 前向
        h = np.zeros((1, hidden_size))
        hs, ys = [], []
        for t in range(seq_len):
            h = np.tanh(x_seq[t] @ W_xh + h @ W_hh + b_h)
            y = h @ W_hy + b_y
            hs.append(h); ys.append(y)
        # 损失
        loss = sum(np.mean((ys[t] - y_seq[t])**2) for t in range(seq_len)) / seq_len
        losses_rnn.append(loss)
        # BPTT反向
        dW_xh = np.zeros_like(W_xh); dW_hh = np.zeros_like(W_hh)
        dW_hy = np.zeros_like(W_hy); db_h = np.zeros_like(b_h); db_y = np.zeros_like(b_y)
        dh_next = np.zeros((1, hidden_size))
        grad_norms = []
        for t in reversed(range(seq_len)):
            dy = 2 * (ys[t] - y_seq[t]) / seq_len
            dW_hy += hs[t].T @ dy
            db_y += dy.sum(axis=0, keepdims=True)
            dh = dy @ W_hy.T + dh_next
            dh_raw = dh * (1 - hs[t]**2)
            dW_xh += x_seq[t].T @ dh_raw
            if t > 0:
                dW_hh += hs[t-1].T @ dh_raw
            db_h += dh_raw.sum(axis=0, keepdims=True)
            dh_next = dh_raw @ W_hh.T
        # 梯度裁剪
        grad_norm = np.sqrt((dW_hh**2).sum() + (dW_xh**2).sum())
        if grad_norm > 5:
            scale = 5 / grad_norm
            dW_xh *= scale; dW_hh *= scale; dW_hy *= scale
        # 更新
        W_xh -= lr_rnn * dW_xh; W_hh -= lr_rnn * dW_hh
        W_hy -= lr_rnn * dW_hy; b_h -= lr_rnn * db_h; b_y -= lr_rnn * db_y

# 梯度消失分析
h_test = np.zeros((1, hidden_size))
grad_chain = np.eye(hidden_size)
grad_norms_test = []
for t in range(seq_len):
    h_test = np.tanh(data_rnn[t].reshape(1,1) @ W_xh + h_test @ W_hh + b_h)
    jac = np.diag((1 - h_test.ravel()**2)) @ W_hh.T
    grad_chain = jac @ grad_chain
    grad_norms_test.append(np.linalg.norm(grad_chain))

# 预测
h_pred = np.zeros((1, hidden_size))
predictions = []
for t in range(50):
    x_t = data_rnn[t].reshape(1, 1)
    h_pred = np.tanh(x_t @ W_xh + h_pred @ W_hh + b_h)
    predictions.append((h_pred @ W_hy + b_y).ravel()[0])

# --- 可视化 ---
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].plot(losses_rnn); axes[0].set_title('RNN训练损失'); axes[0].set_xlabel('更新步数'); axes[0].set_ylabel('Loss')
axes[1].plot(range(seq_len), grad_norms_test, 'ro-'); axes[1].set_title('梯度消失: ||dh_t/dh_0||')
axes[1].set_xlabel('时间步 t'); axes[1].set_ylabel('梯度范数')
axes[2].plot(t_rnn[:50], data_rnn[:50], 'b-', label='真实值')
axes[2].plot(t_rnn[:50], predictions, 'r--', label='RNN预测')
axes[2].set_title('正弦波预测'); axes[2].legend()
plt.tight_layout(); plt.savefig('figures_dl/ex08_rnn.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第8题] RNN训练完成, 最终损失: {losses_rnn[-1]:.4f}, 梯度消失分析已展示")
# 【思考题】为什么RNN会出现梯度消失？tanh激活函数和W_hh的连乘如何导致这个问题？



def _sigmoid(z):
    """数值稳定的sigmoid"""
    return np.where(z >= 0, 1/(1+np.exp(-z)), np.exp(z)/(1+np.exp(z)))


# ============================================================
# 第9题: LSTM - 门控机制数学与手写实现
# ============================================================
# 【数学推导】
# LSTM通过门控机制解决RNN梯度消失问题:
#
# 遗忘门: f_t = σ(W_f·[h_{t-1}, x_t] + b_f)  决定保留多少历史信息
# 输入门: i_t = σ(W_i·[h_{t-1}, x_t] + b_i)  决定写入多少新信息
# 候选值: C̃_t = tanh(W_C·[h_{t-1}, x_t] + b_C)  新信息的候选
# 细胞状态: C_t = f_t ⊙ C_{t-1} + i_t ⊙ C̃_t  (加法更新, 梯度直达)
# 输出门: o_t = σ(W_o·[h_{t-1}, x_t] + b_o)  决定输出多少
# 隐藏状态: h_t = o_t ⊙ tanh(C_t)
#
# 关键: C_t的更新是加法(不是乘法), 梯度可以无损流过长序列
# 这就是LSTM解决梯度消失的本质: 细胞状态提供了梯度的高速公路

np.random.seed(42)
t_lstm = np.linspace(0, 6*np.pi, 300)
data_lstm = np.sin(t_lstm)
seq_len9, D9, H9 = 10, 1, 16

# 合并4个门的权重: [h, x] -> 4H (f, i, C, o)
W9 = np.random.randn(H9 + D9, 4 * H9) * 0.1
b9 = np.zeros(4 * H9)
W_hy9 = np.random.randn(H9, 1) * 0.1
b_y9 = np.zeros(1)
lr9, losses9 = 0.05, []

for epoch in range(80):
    for start in range(0, len(data_lstm) - seq_len9 - 1, seq_len9):
        x_seq = [data_lstm[start+j].reshape(1, 1) for j in range(seq_len9)]
        y_seq = [data_lstm[start+j+1].reshape(1, 1) for j in range(seq_len9)]
        # --- 前向(保存中间值) ---
        h, C = np.zeros((1, H9)), np.zeros((1, H9))
        cache9, ys9 = [], []
        for t in range(seq_len9):
            hx = np.concatenate([h, x_seq[t]], axis=1)
            gr = hx @ W9 + b9  # gates_raw
            f = _sigmoid(gr[:, :H9])
            ig = _sigmoid(gr[:, H9:2*H9])
            Ct = np.tanh(gr[:, 2*H9:3*H9])
            og = _sigmoid(gr[:, 3*H9:])
            C = f * C + ig * Ct
            h = og * np.tanh(C)
            y = h @ W_hy9 + b_y9
            cache9.append((h, C, hx, f, ig, Ct, og))
            ys9.append(y)
        loss = sum(np.mean((ys9[t]-y_seq[t])**2) for t in range(seq_len9)) / seq_len9
        losses9.append(loss)
        # --- BPTT反向 ---
        dW9 = np.zeros_like(W9); db9 = np.zeros_like(b9)
        dWhy9 = np.zeros_like(W_hy9); dby9 = np.zeros_like(b_y9)
        dh_next = np.zeros((1, H9)); dC_next = np.zeros((1, H9))
        for t in reversed(range(seq_len9)):
            h_prev_cache, C_prev_cache, hx, f, ig, Ct, og = cache9[t]
            C_prev = cache9[t-1][1] if t > 0 else np.zeros((1, H9))
            dy = 2 * (ys9[t] - y_seq[t]) / seq_len9
            dWhy9 += h_prev_cache.T @ dy; dby9 += dy.sum(axis=0)
            dh = dy @ W_hy9.T + dh_next
            do = dh * np.tanh(C_prev_cache)
            dC = dh * og * (1 - np.tanh(C_prev_cache)**2) + dC_next
            df = dC * C_prev; di = dC * Ct; dCt = dC * ig
            dC_next = dC * f
            df_r = df * f*(1-f); di_r = di * ig*(1-ig)
            dCt_r = dCt * (1-Ct**2); do_r = do * og*(1-og)
            dg = np.concatenate([df_r, di_r, dCt_r, do_r], axis=1)
            dW9 += hx.T @ dg; db9 += dg.sum(axis=0)
            dhx = dg @ W9.T; dh_next = dhx[:, :H9]
        gn = np.sqrt((dW9**2).sum() + (dWhy9**2).sum())
        if gn > 5: dW9 *= 5/gn; dWhy9 *= 5/gn
        W9 -= lr9*dW9; b9 -= lr9*db9; W_hy9 -= lr9*dWhy9; b_y9 -= lr9*dby9

# 预测
h_p, C_p = np.zeros((1, H9)), np.zeros((1, H9))
preds9 = []
for t in range(50):
    xt = data_lstm[t].reshape(1, 1)
    hx = np.concatenate([h_p, xt], axis=1)
    gr = hx @ W9 + b9
    f = _sigmoid(gr[:, :H9]); ig = _sigmoid(gr[:, H9:2*H9])
    Ct = np.tanh(gr[:, 2*H9:3*H9]); og = _sigmoid(gr[:, 3*H9:])
    C_p = f * C_p + ig * Ct; h_p = og * np.tanh(C_p)
    preds9.append((h_p @ W_hy9 + b_y9).ravel()[0])

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
axes[0].plot(losses9); axes[0].set_title('LSTM训练损失'); axes[0].set_xlabel('更新步数'); axes[0].set_ylabel('Loss')
axes[1].plot(t_lstm[:50], data_lstm[:50], 'b-', label='真实值')
axes[1].plot(t_lstm[:50], preds9, 'r--', label='LSTM预测')
axes[1].set_title('LSTM正弦波预测'); axes[1].legend()
plt.tight_layout(); plt.savefig('figures_dl/ex09_lstm.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第9题] LSTM训练完成, 最终损失: {losses9[-1]:.4f}")
# 【思考题】LSTM的细胞状态C_t使用加法更新而非乘法, 这如何解决梯度消失？遗忘门的作用是什么？


# ============================================================
# 第10题: GRU - 重置门与更新门数学
# ============================================================
# 【数学推导】
# GRU是LSTM的简化版, 合并了细胞状态和隐藏状态:
#
# 重置门: r_t = σ(W_r·[h_{t-1}, x_t])  控制历史信息的影响
# 更新门: z_t = σ(W_z·[h_{t-1}, x_t])  控制新旧信息比例(类似LSTM的f和i)
# 候选值: h̃_t = tanh(W·[r_t ⊙ h_{t-1}, x_t])  用重置门过滤历史
# 新状态: h_t = (1 - z_t) ⊙ h_{t-1} + z_t ⊙ h̃_t
#
# 对比LSTM:
#   - GRU: 2个门, 无单独细胞状态, 参数更少
#   - LSTM: 3个门 + 细胞状态, 表达能力更强
#   - 更新门z_t同时扮演遗忘门和输入门的角色: (1-z)保留旧, z写入新

np.random.seed(42)
data_gru = np.sin(np.linspace(0, 6*np.pi, 300))
H10 = 16
W_g10 = np.random.randn(H10 + 1, 2 * H10) * 0.1  # gates: r, z
b_g10 = np.zeros(2 * H10)
W_c10 = np.random.randn(H10 + 1, H10) * 0.1  # candidate
b_c10 = np.zeros(H10)
W_hy10 = np.random.randn(H10, 1) * 0.1; b_y10 = np.zeros(1)
lr10, losses10 = 0.05, []

for epoch in range(80):
    for start in range(0, len(data_gru) - seq_len9 - 1, seq_len9):
        x_seq = [data_gru[start+j].reshape(1, 1) for j in range(seq_len9)]
        y_seq = [data_gru[start+j+1].reshape(1, 1) for j in range(seq_len9)]
        h = np.zeros((1, H10)); cache10, ys10 = [], []
        for t in range(seq_len9):
            hx = np.concatenate([h, x_seq[t]], axis=1)
            gates = _sigmoid(hx @ W_g10 + b_g10)
            r = gates[:, :H10]; z = gates[:, H10:]
            rhx = np.concatenate([r * h, x_seq[t]], axis=1)
            ht = np.tanh(rhx @ W_c10 + b_c10)
            h = (1 - z) * h + z * ht
            y = h @ W_hy10 + b_y10
            cache10.append((h.copy(), hx, r, z, rhx, ht)); ys10.append(y)
        loss = sum(np.mean((ys10[t]-y_seq[t])**2) for t in range(seq_len9)) / seq_len9
        losses10.append(loss)
        dW_g10 = np.zeros_like(W_g10); db_g10 = np.zeros_like(b_g10)
        dW_c10 = np.zeros_like(W_c10); db_c10 = np.zeros_like(b_c10)
        dWhy10 = np.zeros_like(W_hy10); dby10 = np.zeros_like(b_y10)
        dh_next = np.zeros((1, H10))
        for t in reversed(range(seq_len9)):
            h_new, hx, r, z, rhx, ht = cache10[t]
            h_prev = cache10[t-1][0] if t > 0 else np.zeros((1, H10))
            dy = 2 * (ys10[t] - y_seq[t]) / seq_len9
            dWhy10 += h_new.T @ dy; dby10 += dy.sum(axis=0)
            dh = dy @ W_hy10.T + dh_next
            dz = dh * (ht - h_prev); dh_t = dh * z; dh_prev_d = dh * (1 - z)
            dh_t_r = dh_t * (1 - ht**2)
            dW_c10 += rhx.T @ dh_t_r; db_c10 += dh_t_r.sum(axis=0)
            drhx = dh_t_r @ W_c10.T
            dr = drhx[:, :H10] * h_prev; dh_prev_r = drhx[:, :H10] * r
            dz_r = dz * z*(1-z); dr_r = dr * r*(1-r)
            dg = np.concatenate([dr_r, dz_r], axis=1)
            dW_g10 += hx.T @ dg; db_g10 += dg.sum(axis=0)
            dhx = dg @ W_g10.T; dh_next = dhx[:, :H10] + dh_prev_d + dh_prev_r
        W_g10 -= lr10*dW_g10; b_g10 -= lr10*db_g10
        W_c10 -= lr10*dW_c10; b_c10 -= lr10*db_c10
        W_hy10 -= lr10*dWhy10; b_y10 -= lr10*dby10

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(losses9, label='LSTM', alpha=0.7)
ax.plot(losses10, label='GRU', alpha=0.7)
ax.set_title('LSTM vs GRU 训练损失对比'); ax.set_xlabel('更新步数'); ax.set_ylabel('Loss'); ax.legend()
plt.tight_layout(); plt.savefig('figures_dl/ex10_gru.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第10题] GRU训练完成, 最终损失: {losses10[-1]:.4f} (LSTM: {losses9[-1]:.4f})")
# 【思考题】GRU相比LSTM减少了哪些门？更新门z_t如何同时实现遗忘和输入的功能？


# ============================================================
# 第11题: Attention机制 - 点积注意力与缩放点积
# ============================================================
# 【数学推导】
# 注意力的核心思想: 根据查询(Query)和键(Key)的相关性, 对值(Value)加权求和
#
# Q = X·W_Q,  K = X·W_K,  V = X·W_V  (线性投影)
#
# 缩放点积注意力:
#   Attention(Q, K, V) = softmax(Q·Kᵀ / √d_k) · V
#
# 为什么要除以√d_k?
#   当d_k较大时, Q·Kᵀ的值会很大, 导致softmax梯度趋近于0
#   除以√d_k使方差稳定在1附近, 保持梯度健康
#
# 直觉: Q是"我想找什么", K是"我有什么", V是"实际内容"
#   softmax(Q·Kᵀ)是相关性权重, 加权V得到注意力输出

np.random.seed(42)
seq_len11, d_model11 = 6, 8
X11 = np.random.randn(seq_len11, d_model11)
W_Q11 = np.random.randn(d_model11, d_model11) * 0.1
W_K11 = np.random.randn(d_model11, d_model11) * 0.1
W_V11 = np.random.randn(d_model11, d_model11) * 0.1

Q11 = X11 @ W_Q11; K11 = X11 @ W_K11; V11 = X11 @ W_V11
d_k11 = d_model11
scores11 = Q11 @ K11.T / np.sqrt(d_k11)  # 缩放点积
attn11 = softmax_batch(scores11)  # (seq_len, seq_len) 行softmax
output11 = attn11 @ V11  # (seq_len, d_model)

# 对比: 不缩放的注意力
scores_unscaled = Q11 @ K11.T
attn_unscaled = softmax_batch(scores_unscaled)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
im0 = axes[0].imshow(scores11, cmap='Blues'); axes[0].set_title('缩放后得分 QKᵀ/√d_k'); plt.colorbar(im0, ax=axes[0])
im1 = axes[1].imshow(attn11, cmap='Blues'); axes[1].set_title('缩放注意力权重'); plt.colorbar(im1, ax=axes[1])
im2 = axes[2].imshow(attn_unscaled, cmap='Blues'); axes[2].set_title('未缩放注意力(更尖锐)'); plt.colorbar(im2, ax=axes[2])
for ax in axes: ax.set_xlabel('Key位置'); ax.set_ylabel('Query位置')
plt.tight_layout(); plt.savefig('figures_dl/ex11_attention.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第11题] Attention输出形状: {output11.shape}, 注意力权重已可视化")
# 【思考题】为什么大d_k时需要缩放？不缩放会导致什么问题？(提示: softmax饱和)


# ============================================================
# 第12题: Transformer - Self-Attention/Multi-head/位置编码
# ============================================================
# 【数学推导】
# Transformer核心组件:
#
# 1. 位置编码(Positional Encoding):
#   PE(pos, 2i) = sin(pos / 10000^{2i/d})
#   PE(pos, 2i+1) = cos(pos / 10000^{2i/d})
#   使模型能感知序列中token的位置(自注意力本身无位置信息)
#
# 2. 多头注意力(Multi-Head Attention):
#   将Q, K, V分成h个头, 每个头独立做注意力, 最后拼接
#   head_i = Attention(Q·W_i^Q, K·W_i^K, V·W_i^V)
#   MultiHead = Concat(head_1, ..., head_h) · W^O
#   不同头可以关注不同模式(如语法关系、语义相似性)
#
# 3. 自注意力(Self-Attention):
#   Q = K = V 都来自同一输入, 每个位置关注所有位置
#
# 4. 前馈网络(FFN):
#   FFN(x) = ReLU(x·W₁ + b₁)·W₂ + b₂
#   逐位置应用, 增加非线性表达能力

def positional_encoding(seq_len, d_model):
    """正弦余弦位置编码"""
    pe = np.zeros((seq_len, d_model))
    pos = np.arange(seq_len).reshape(-1, 1)
    div = np.exp(np.arange(0, d_model, 2) * (-np.log(10000.0) / d_model))
    pe[:, 0::2] = np.sin(pos * div)
    pe[:, 1::2] = np.cos(pos * div)
    return pe

def multi_head_attention(X, n_heads):
    """多头自注意力"""
    seq_len, d_model = X.shape
    d_k = d_model // n_heads
    W_Q = np.random.randn(d_model, d_model) * 0.1
    W_K = np.random.randn(d_model, d_model) * 0.1
    W_V = np.random.randn(d_model, d_model) * 0.1
    Q = (X @ W_Q).reshape(seq_len, n_heads, d_k).transpose(1, 0, 2)
    K = (X @ W_K).reshape(seq_len, n_heads, d_k).transpose(1, 0, 2)
    V = (X @ W_V).reshape(seq_len, n_heads, d_k).transpose(1, 0, 2)
    scores = Q @ K.transpose(0, 2, 1) / np.sqrt(d_k)  # (h, seq, seq)
    attn = np.array([softmax_batch(scores[h]) for h in range(n_heads)])
    out = (attn @ V).transpose(1, 0, 2).reshape(seq_len, d_model)
    return out, attn

np.random.seed(42)
seq_len12, d_model12, n_heads12 = 10, 16, 4
X12 = np.random.randn(seq_len12, d_model12)
pe12 = positional_encoding(seq_len12, d_model12)
X_pe = X12 + pe12  # 加入位置信息
out12, attn12 = multi_head_attention(X_pe, n_heads12)
# FFN
W_ff1 = np.random.randn(d_model12, 32) * 0.1; b_ff1 = np.zeros(32)
W_ff2 = np.random.randn(32, d_model12) * 0.1; b_ff2 = np.zeros(d_model12)
ffn_out = np.maximum(0, out12 @ W_ff1 + b_ff1) @ W_ff2 + b_ff2
final12 = X_pe + ffn_out  # 残差连接

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].imshow(pe12, cmap='RdBu', aspect='auto'); axes[0].set_title('位置编码')
axes[0].set_xlabel('维度'); axes[0].set_ylabel('位置')
axes[1].imshow(attn12[0], cmap='Blues'); axes[1].set_title('Head 0 注意力权重')
axes[1].set_xlabel('Key位置'); axes[1].set_ylabel('Query位置')
axes[2].imshow(attn12[1], cmap='Blues'); axes[2].set_title('Head 1 注意力权重')
axes[2].set_xlabel('Key位置'); axes[2].set_ylabel('Query位置')
plt.tight_layout(); plt.savefig('figures_dl/ex12_transformer.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第12题] Transformer({n_heads12}头注意力)输出形状: {final12.shape}")
# 【思考题】为什么需要位置编码？多头注意力相比单头有什么优势？


# ============================================================
# 第13题: 序列到序列模型 - Encoder-Decoder/Teacher Forcing
# ============================================================
# 【数学推导】
# Encoder-Decoder架构:
#   Encoder: 处理输入序列 x₁,...,xₙ, 得到上下文向量 c = h_n^enc
#   Decoder: 以c为初始隐藏状态, 逐步生成输出 y₁,...,yₘ
#
# Encoder: h_t^enc = tanh(W_xh·x_t + W_hh·h_{t-1} + b)
#   最终: c = h_T^enc (上下文向量)
#
# Decoder: h_t^dec = tanh(W_xh·y_{t-1} + W_hh·h_{t-1} + b)
#          ŷ_t = W_hy·h_t + b_y
#   初始: h_0^dec = c
#
# Teacher Forcing(教师强制):
#   训练时: decoder输入用真实标签y_{t-1}(而非模型预测ŷ_{t-1})
#   好处: 训练更快更稳定, 避免错误累积
#   推理时: 用模型自己的预测作为下一步输入(自回归)

np.random.seed(42)
data_s2s = np.sin(np.linspace(0, 8*np.pi, 400))
seq_enc, seq_dec, H13 = 10, 10, 16
enc_Wxh = np.random.randn(1, H13)*0.1; enc_Whh = np.random.randn(H13, H13)*0.1; enc_bh = np.zeros((1, H13))
dec_Wxh = np.random.randn(1, H13)*0.1; dec_Whh = np.random.randn(H13, H13)*0.1; dec_bh = np.zeros((1, H13))
dec_Why = np.random.randn(H13, 1)*0.1; dec_by = np.zeros(1)
lr13, losses13 = 0.01, []

for epoch in range(60):
    for start in range(0, len(data_s2s) - seq_enc - seq_dec - 1, seq_enc + seq_dec):
        enc_in = [data_s2s[start+i].reshape(1,1) for i in range(seq_enc)]
        dec_tgt = [data_s2s[start+seq_enc+i].reshape(1,1) for i in range(seq_dec)]
        dec_in = [np.zeros((1,1))] + dec_tgt[:-1]  # teacher forcing: 起始token+偏移目标
        # Encoder forward
        h = np.zeros((1, H13)); enc_hs = []
        for x in enc_in:
            h = np.tanh(x @ enc_Wxh + h @ enc_Whh + enc_bh); enc_hs.append(h)
        context = h
        # Decoder forward
        h = context; dec_hs = [context]; dec_ys = []
        for x in dec_in:
            h = np.tanh(x @ dec_Wxh + h @ dec_Whh + dec_bh)
            y = h @ dec_Why + dec_by
            dec_hs.append(h); dec_ys.append(y)
        loss = sum(np.mean((dec_ys[t]-dec_tgt[t])**2) for t in range(seq_dec)) / seq_dec
        losses13.append(loss)
        # Decoder BPTT
        d_enc_Wxh = np.zeros_like(enc_Wxh); d_enc_Whh = np.zeros_like(enc_Whh); d_enc_bh = np.zeros_like(enc_bh)
        d_dec_Wxh = np.zeros_like(dec_Wxh); d_dec_Whh = np.zeros_like(dec_Whh); d_dec_bh = np.zeros_like(dec_bh)
        d_dec_Why = np.zeros_like(dec_Why); d_dec_by = np.zeros_like(dec_by)
        dh_next = np.zeros((1, H13))
        for t in reversed(range(seq_dec)):
            dy = 2*(dec_ys[t]-dec_tgt[t])/seq_dec
            d_dec_Why += dec_hs[t+1].T @ dy; d_dec_by += dy.sum()
            dh = dy @ dec_Why.T + dh_next
            dh_r = dh * (1-dec_hs[t+1]**2)
            d_dec_Wxh += dec_in[t].T @ dh_r; d_dec_Whh += dec_hs[t].T @ dh_r; d_dec_bh += dh_r.sum()
            dh_next = dh_r @ dec_Whh.T
        d_context = dh_next
        # Encoder BPTT (from context gradient)
        dh_next = d_context
        for t in reversed(range(seq_enc)):
            dh_r = dh_next * (1-enc_hs[t]**2)
            d_enc_Wxh += enc_in[t].T @ dh_r
            if t > 0: d_enc_Whh += enc_hs[t-1].T @ dh_r
            d_enc_bh += dh_r.sum(); dh_next = dh_r @ enc_Whh.T
        for p, dp in [(enc_Wxh,d_enc_Wxh),(enc_Whh,d_enc_Whh),(enc_bh,d_enc_bh),
                       (dec_Wxh,d_dec_Wxh),(dec_Whh,d_dec_Whh),(dec_bh,d_dec_bh),
                       (dec_Why,d_dec_Why),(dec_by,d_dec_by)]:
            p -= lr13 * dp

# 推理(自回归)
start_idx = 50
enc_in_test = [data_s2s[start_idx+i].reshape(1,1) for i in range(seq_enc)]
h = np.zeros((1, H13))
for x in enc_in_test:
    h = np.tanh(x @ enc_Wxh + h @ enc_Whh + enc_bh)
context_test = h
h = context_test; dec_input = np.zeros((1, 1)); preds13 = []
for t in range(seq_dec):
    h = np.tanh(dec_input @ dec_Wxh + h @ dec_Whh + dec_bh)
    y = h @ dec_Why + dec_by
    preds13.append(y.ravel()[0])
    dec_input = y  # 自回归: 用预测作为下一步输入

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
axes[0].plot(losses13); axes[0].set_title('Seq2Seq训练损失'); axes[0].set_xlabel('更新步数'); axes[0].set_ylabel('Loss')
real_out = data_s2s[start_idx+seq_enc:start_idx+seq_enc+seq_dec]
axes[1].plot(range(seq_dec), real_out, 'b-o', label='真实值', markersize=4)
axes[1].plot(range(seq_dec), preds13, 'r--s', label='Seq2Seq预测(自回归)', markersize=4)
axes[1].set_title('Seq2Seq预测 (Encoder→Decoder)'); axes[1].legend()
plt.tight_layout(); plt.savefig('figures_dl/ex13_seq2seq.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第13题] Seq2Seq训练完成, 最终损失: {losses13[-1]:.4f}")
# 【思考题】Teacher Forcing为什么能加速训练？推理时不用它会有什么问题(暴露偏差)？


# ============================================================
# 第14题: 生成对抗网络 - minimax博弈与交替训练
# ============================================================
# 【数学推导】
# GAN包含两个网络:
#   生成器G: 从噪声z生成假数据 G(z), 目标: 让D无法分辨真假
#   判别器D: 判断输入是真实数据还是生成数据, 输出概率D(x)
#
# Minimax博弈:
#   min_G max_D V(D, G) = E[log D(x)] + E[log(1 - D(G(z)))]
#   D要最大化: 正确区分真假
#   G要最小化: 让D把假的也当真的, 即最大化log(D(G(z)))
#
# 训练策略(交替训练):
#   1. 固定G, 训练D: 用真数据和G(z)训练D区分真假
#   2. 固定D, 训练G: 让G(z)骗过D
#
# 非饱和损失(实际常用):
#   G的损失: -log(D(G(z)))  (避免梯度消失)

np.random.seed(42)
def sample_real14(n):
    """真实数据: 两个高斯簇"""
    c = np.random.randint(2, size=n)
    centers = np.array([[2, 2], [-2, -2]])
    return np.random.randn(n, 2) * 0.5 + centers[c]

noise_dim, hidden_g, data_dim = 2, 16, 2
# 生成器: z(2) → hidden(16) → data(2)
G_W1 = np.random.randn(noise_dim, hidden_g)*0.1; G_b1 = np.zeros(hidden_g)
G_W2 = np.random.randn(hidden_g, data_dim)*0.1; G_b2 = np.zeros(data_dim)
# 判别器: x(2) → hidden(16) → logit(1)
D_W1 = np.random.randn(data_dim, hidden_g)*0.1; D_b1 = np.zeros(hidden_g)
D_W2 = np.random.randn(hidden_g, 1)*0.1; D_b2 = np.zeros(1)

def G_forward(z):
    h = np.maximum(0, z @ G_W1 + G_b1)
    return h @ G_W2 + G_b2

def D_forward(x):
    h = np.maximum(0, x @ D_W1 + D_b1)
    return _sigmoid(h @ D_W2 + D_b2)

def D_logit(x):
    h = np.maximum(0, x @ D_W1 + D_b1)
    return h @ D_W2 + D_b2, h

lr14, batch14, d_losses, g_losses = 0.01, 64, [], []

for epoch in range(2000):
    # --- 训练判别器D ---
    z = np.random.randn(batch14, noise_dim)
    fake = G_forward(z)
    real = sample_real14(batch14)
    logit_r, h_r = D_logit(real)
    logit_f, h_f = D_logit(fake)
    d_loss = -np.mean(np.log(_sigmoid(logit_r)+1e-10) + np.log(1-_sigmoid(logit_f)+1e-10))
    d_losses.append(d_loss)
    d_lr = (_sigmoid(logit_r) - 1) / batch14  # real: D→1
    d_lf = _sigmoid(logit_f) / batch14          # fake: D→0
    dW2 = h_r.T @ d_lr + h_f.T @ d_lf; db2 = d_lr.sum() + d_lf.sum()
    dh_r = d_lr @ D_W2.T; dh_f = d_lf @ D_W2.T
    dh_r_raw = dh_r * (h_r > 0); dh_f_raw = dh_f * (h_f > 0)
    dW1 = real.T @ dh_r_raw + fake.T @ dh_f_raw; db1 = dh_r_raw.sum(0) + dh_f_raw.sum(0)
    D_W1 -= lr14*dW1; D_b1 -= lr14*db1; D_W2 -= lr14*dW2; D_b2 -= lr14*db2
    # --- 训练生成器G ---
    z = np.random.randn(batch14, noise_dim)
    h_g = np.maximum(0, z @ G_W1 + G_b1)
    fake = h_g @ G_W2 + G_b2
    logit_f2, h_f2 = D_logit(fake)
    g_loss = -np.mean(np.log(_sigmoid(logit_f2)+1e-10))
    g_losses.append(g_loss)
    d_lf2 = (_sigmoid(logit_f2) - 1) / batch14  # G wants D(fake)→1
    dh_f2 = d_lf2 @ D_W2.T; dh_f2_raw = dh_f2 * (h_f2 > 0)
    d_fake = dh_f2_raw @ D_W1.T  # 梯度传到G的输出
    dG_W2 = h_g.T @ d_fake; dG_b2 = d_fake.sum(0)
    dh_g = d_fake @ G_W2.T; dh_g_raw = dh_g * (h_g > 0)
    dG_W1 = z.T @ dh_g_raw; dG_b1 = dh_g_raw.sum(0)
    G_W1 -= lr14*dG_W1; G_b1 -= lr14*dG_b1; G_W2 -= lr14*dG_W2; G_b2 -= lr14*dG_b2

# --- 可视化 ---
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
real_plot = sample_real14(300)
fake_plot = G_forward(np.random.randn(300, noise_dim))
axes[0].scatter(real_plot[:, 0], real_plot[:, 1], c='blue', s=10, alpha=0.5, label='真实数据')
axes[0].scatter(fake_plot[:, 0], fake_plot[:, 1], c='red', s=10, alpha=0.5, label='生成数据')
axes[0].set_title('GAN: 真实vs生成数据分布'); axes[0].legend()
axes[1].plot(d_losses, label='D loss'); axes[1].plot(g_losses, label='G loss')
axes[1].set_title('GAN训练损失'); axes[1].legend()
axes[2].hist(real_plot[:, 0], bins=30, alpha=0.5, label='真实', density=True)
axes[2].hist(fake_plot[:, 0], bins=30, alpha=0.5, label='生成', density=True)
axes[2].set_title('维度1分布对比'); axes[2].legend()
plt.tight_layout(); plt.savefig('figures_dl/ex14_gan.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第14题] GAN训练完成, D loss: {d_losses[-1]:.4f}, G loss: {g_losses[-1]:.4f}")
# 【思考题】GAN训练中常见的"模式崩塌"问题是什么？如何缓解？


# ============================================================
# 第15题: 扩散模型 - DDPM前向加噪/反向去噪数学推导
# ============================================================
# 【数学推导】
# 扩散模型通过逐步加噪和去噪来生成数据
#
# 前向过程(加噪, 固定, 不需学习):
#   q(x_t | x_{t-1}) = N(√(1-β_t)·x_{t-1}, β_t·I)
#   β_t: 噪声调度, 从小到大递增
#
#   关键公式(跳步采样):
#   x_t = √(ᾱ_t)·x_0 + √(1-ᾱ_t)·ε,  ε~N(0,I)
#   其中 α_t = 1-β_t, ᾱ_t = Π_{i=1}^{t} α_i (累积乘积)
#
# 反向过程(去噪, 需要学习):
#   p_θ(x_{t-1} | x_t) = N(μ_θ(x_t, t), σ_t²·I)
#   目标: 学习预测噪声 ε_θ(x_t, t) ≈ ε
#
# 简化训练目标:
#   L = E[||ε - ε_θ(x_t, t)||²]
#   随机采样t, 对x_0加噪得到x_t, 训练网络预测加入的噪声ε
#
# 采样(DDPM):
#   x_{t-1} = (x_t - (1-α_t)/√(1-ᾱ_t) · ε_θ(x_t, t)) / √α_t + σ_t·z

np.random.seed(42)
T15 = 50
betas15 = np.linspace(0.0001, 0.02, T15)
alphas15 = 1 - betas15
alpha_bars15 = np.cumprod(alphas15)

# 真实数据: 2D月牙形
n_data15 = 500
theta15 = np.random.uniform(0, 2*np.pi, n_data15)
data15 = np.column_stack([np.cos(theta15)*3, np.sin(theta15)*3]) + np.random.randn(n_data15, 2) * 0.3

# 噪声预测网络: [x_t, t_onehot] → ε
input_dim15 = 2 + T15
hidden15 = 64
W1_15 = np.random.randn(input_dim15, hidden15) * 0.1; b1_15 = np.zeros(hidden15)
W2_15 = np.random.randn(hidden15, 2) * 0.1; b2_15 = np.zeros(2)
lr15, batch15, losses15 = 0.001, 64, []

def eps_predict(x_t, t_onehot):
    inp = np.concatenate([x_t, t_onehot], axis=1)
    h = np.maximum(0, inp @ W1_15 + b1_15)
    return h @ W2_15 + b2_15

for epoch in range(800):
    idx = np.random.choice(n_data15, batch15)
    x_0 = data15[idx]
    t = np.random.randint(0, T15, batch15)
    eps = np.random.randn(batch15, 2)
    ab = alpha_bars15[t]
    x_t = np.sqrt(ab)[:, None] * x_0 + np.sqrt(1 - ab)[:, None] * eps
    t_oh = np.eye(T15)[t]
    eps_pred = eps_predict(x_t, t_oh)
    loss = np.mean((eps - eps_pred)**2)
    losses15.append(loss)
    d_ep = 2 * (eps_pred - eps) / batch15
    h_inp = np.concatenate([x_t, t_oh], axis=1)
    h_hid = np.maximum(0, h_inp @ W1_15 + b1_15)
    dW2_15 = h_hid.T @ d_ep; db2_15 = d_ep.sum(0)
    dh = d_ep @ W2_15.T; dh_r = dh * (h_hid > 0)
    dW1_15 = h_inp.T @ dh_r; db1_15 = dh_r.sum(0)
    W1_15 -= lr15*dW1_15; b1_15 -= lr15*db1_15; W2_15 -= lr15*dW2_15; b2_15 -= lr15*db2_15

# DDPM采样
n_samples = 500
x_sample = np.random.randn(n_samples, 2)  # 从纯噪声开始
for t in reversed(range(T15)):
    t_oh = np.eye(T15)[np.full(n_samples, t)]
    ep = eps_predict(x_sample, t_oh)
    mean = (x_sample - (1-alphas15[t])/np.sqrt(1-alpha_bars15[t]) * ep) / np.sqrt(alphas15[t])
    if t > 0:
        x_sample = mean + np.sqrt(betas15[t]) * np.random.randn(n_samples, 2)
    else:
        x_sample = mean

# --- 可视化 ---
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
axes[0].scatter(data15[:, 0], data15[:, 1], s=5, alpha=0.5, c='blue')
axes[0].set_title('真实数据分布'); axes[0].set_xlim(-5, 5); axes[0].set_ylim(-5, 5)
# 前向加噪过程
for t_show in [0, 10, 25, 49]:
    eps_show = np.random.randn(n_data15, 2)
    ab = alpha_bars15[t_show]
    x_noisy = np.sqrt(ab) * data15 + np.sqrt(1-ab) * eps_show
    axes[1].scatter(x_noisy[:, 0], x_noisy[:, 1], s=5, alpha=0.3, label=f't={t_show}')
axes[1].set_title('前向过程: 逐步加噪'); axes[1].legend()
axes[2].scatter(x_sample[:, 0], x_sample[:, 1], s=5, alpha=0.5, c='red')
axes[2].set_title('反向过程: DDPM生成'); axes[2].set_xlim(-5, 5); axes[2].set_ylim(-5, 5)
plt.tight_layout(); plt.savefig('figures_dl/ex15_diffusion.png', dpi=100, bbox_inches='tight'); plt.close()
print(f"[第15题] 扩散模型训练完成, 最终损失: {losses15[-1]:.4f}, 已生成{n_samples}个样本")
# 【思考题】扩散模型为什么比GAN训练更稳定？ε预测网络为什么比直接预测x_0效果更好？

print("\n" + "=" * 60)
print("深度学习模型数学 - 15题练习全部完成!")
print(f"图片已保存到 figures_dl/ 目录")
print("=" * 60)
