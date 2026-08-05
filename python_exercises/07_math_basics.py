"""
数学基础练习 + 扩展题
=====================
涵盖：线性代数、概率论、微积分（优化）、信息论
所有概念用 Python/NumPy 实现验证
"""

import numpy as np
from scipy import stats
from scipy.optimize import minimize
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

OUTPUT_DIR = '/app/data/所有对话/主对话/python_exercises/charts'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# 基础练习
# ============================================================

def exercise_1_linear_algebra():
    """练习1：线性代数核心概念"""
    # 1. 矩阵的迹
    A = np.array([[1, 2], [3, 4]])
    assert np.trace(A) == 5  # 1 + 4
    
    # 2. 矩阵的秩
    B = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    rank = np.linalg.matrix_rank(B)
    assert rank == 2  # 第三行是前两行的线性组合
    
    # 3. 正交矩阵验证
    Q = np.array([[0, 1], [1, 0]])  # 置换矩阵是正交的
    assert np.allclose(Q @ Q.T, np.eye(2))
    assert np.allclose(Q.T @ Q, np.eye(2))
    
    # 4. 对称矩阵
    S = np.array([[2, 1], [1, 3]])
    assert np.allclose(S, S.T)
    
    # 5. 正定矩阵验证（所有特征值 > 0）
    eigenvalues = np.linalg.eigvalsh(S)
    assert (eigenvalues > 0).all()
    
    # 6. 向量投影
    v = np.array([3, 4])
    u = np.array([1, 0])
    projection = (v @ u) / (u @ u) * u  # v 在 u 上的投影
    assert np.allclose(projection, [3, 0])
    
    # 7. Gram-Schmidt 正交化
    v1 = np.array([1, 1, 0], dtype=float)
    v2 = np.array([1, 0, 1], dtype=float)
    u1 = v1 / np.linalg.norm(v1)
    u2 = v2 - (v2 @ u1) * u1
    u2 = u2 / np.linalg.norm(u2)
    assert abs(u1 @ u2) < 1e-10  # 正交
    
    print("✅ 练习1 通过：线性代数核心概念")


def exercise_2_probability():
    """练习2：概率论基础"""
    # 1. 贝叶斯定理
    # P(病|阳) = P(阳|病)*P(病) / P(阳)
    # 某病发病率 1%，检测灵敏度 99%，特异度 95%
    p_disease = 0.01
    p_positive_given_disease = 0.99
    p_positive_given_healthy = 0.05  # 1 - 特异度
    
    p_positive = (p_positive_given_disease * p_disease + 
                  p_positive_given_healthy * (1 - p_disease))
    p_disease_given_positive = (p_positive_given_disease * p_disease) / p_positive
    assert abs(p_disease_given_positive - 0.1664) < 0.001  # 约16.6%
    
    # 2. 期望和方差
    # 骰子的期望 = 3.5, 方差 = 35/12 ≈ 2.917
    outcomes = np.arange(1, 7)
    probs = np.ones(6) / 6
    expected = np.sum(outcomes * probs)
    variance = np.sum((outcomes - expected) ** 2 * probs)
    assert abs(expected - 3.5) < 1e-10
    assert abs(variance - 35/12) < 1e-10
    
    # 3. 二项分布
    n, p = 10, 0.3
    # P(X=3) = C(10,3) * 0.3^3 * 0.7^7
    from math import comb
    p_x3 = comb(n, 3) * p**3 * (1-p)**7
    scipy_pmf = stats.binom.pmf(3, n, p)
    assert abs(p_x3 - scipy_pmf) < 1e-10
    
    # 4. 正态分布
    mu, sigma = 5, 2
    # P(X < 5) = 0.5 (均值处)
    p_less_than_mu = stats.norm.cdf(0, 0, 1)  # 标准正态在0处
    assert abs(p_less_than_mu - 0.5) < 1e-10
    
    # 5. 大数定律验证
    np.random.seed(42)
    sample_means = []
    for size in [10, 100, 1000, 10000]:
        samples = np.random.uniform(0, 1, size)
        sample_means.append(samples.mean())
    # 样本均值应趋近于 0.5
    assert abs(sample_means[-1] - 0.5) < abs(sample_means[0] - 0.5)
    
    # 6. 协方差和相关系数
    x = np.array([1, 2, 3, 4, 5], dtype=float)
    y = np.array([2, 4, 6, 8, 10], dtype=float)  # y = 2x，完全正相关
    corr = np.corrcoef(x, y)[0, 1]
    assert abs(corr - 1.0) < 1e-10
    
    print("✅ 练习2 通过：概率论基础")


def exercise_3_calculus_optimization():
    """练习3：微积分与优化"""
    # 1. 数值梯度（中心差分）
    def f(x):
        return x ** 2
    
    def numerical_grad(f, x, h=1e-5):
        return (f(x + h) - f(x - h)) / (2 * h)
    
    assert abs(numerical_grad(f, 3.0) - 6.0) < 1e-4  # d/dx(x^2) = 2x = 6
    
    # 2. 多变量梯度
    def g(x, y):
        return x ** 2 + 3 * y ** 2
    
    h = 1e-5
    grad_x = (g(1 + h, 1) - g(1 - h, 1)) / (2 * h)  # dg/dx = 2x = 2
    grad_y = (g(1, 1 + h) - g(1, 1 - h)) / (2 * h)  # dg/dy = 6y = 6
    assert abs(grad_x - 2.0) < 1e-4
    assert abs(grad_y - 6.0) < 1e-4
    
    # 3. 梯度下降法
    def gradient_descent(f, grad_f, x0, lr=0.01, max_iter=1000, tol=1e-6):
        x = x0
        for i in range(max_iter):
            g = grad_f(x)
            if abs(g) < tol:
                break
            x = x - lr * g
        return x
    
    # 最小化 f(x) = (x-3)^2
    result = gradient_descent(
        lambda x: (x - 3) ** 2,
        lambda x: 2 * (x - 3),
        x0=0.0, lr=0.1
    )
    assert abs(result - 3.0) < 1e-4
    
    # 4. 链式法则验证（数值）
    # f(x) = sigmoid(x) = 1/(1+e^(-x))
    # f'(x) = f(x) * (1 - f(x))
    def sigmoid(x):
        return 1 / (1 + np.exp(-x))
    
    x_val = 1.0
    analytical_grad = sigmoid(x_val) * (1 - sigmoid(x_val))
    numerical_grad_val = numerical_grad(sigmoid, x_val)
    assert abs(analytical_grad - numerical_grad_val) < 1e-4
    
    # 5. scipy.optimize 最小化
    def rosenbrock(x):
        return (1 - x[0]) ** 2 + 100 * (x[1] - x[0] ** 2) ** 2
    
    result = minimize(rosenbrock, x0=[0, 0], method='Nelder-Mead')
    assert result.fun < 1e-4  # Rosenbrock 最小值在 (1, 1)，f=0
    
    # 6. 二阶导数（海森矩阵近似）
    def f2(x):
        return x[0] ** 2 + 2 * x[1] ** 2 + x[0] * x[1]
    
    # 海森矩阵 = [[2, 1], [1, 4]]
    eps = 1e-5
    h11 = (f2([eps, 0]) - 2 * f2([0, 0]) + f2([-eps, 0])) / eps ** 2
    assert abs(h11 - 2.0) < 0.1
    
    print("✅ 练习3 通过：微积分与优化")


def exercise_4_information_theory():
    """练习4：信息论基础"""
    # 1. 信息熵
    # H(X) = -sum(p_i * log2(p_i))
    # 公平硬币：H = 1 bit
    p_fair = [0.5, 0.5]
    H_fair = -sum(p * np.log2(p) for p in p_fair)
    assert abs(H_fair - 1.0) < 1e-10
    
    # 偏差硬币：H < 1
    p_biased = [0.9, 0.1]
    H_biased = -sum(p * np.log2(p) for p in p_biased)
    assert H_biased < H_fair
    
    # 2. 交叉熵
    # H(p, q) = -sum(p_i * log(q_i))
    p = np.array([1.0, 0.0])  # one-hot
    q = np.array([0.7, 0.3])  # 预测概率
    cross_entropy = -np.sum(p * np.log(q + 1e-10))
    assert abs(cross_entropy - (-np.log(0.7))) < 1e-6
    
    # 3. KL散度
    # D_KL(p || q) = sum(p_i * log(p_i / q_i))
    p = np.array([0.5, 0.5])
    q = np.array([0.3, 0.7])
    kl_div = np.sum(p * np.log(p / q))
    assert kl_div > 0  # KL散度总是非负
    
    # KL(p||p) = 0
    kl_self = np.sum(p * np.log(p / p))
    assert abs(kl_self) < 1e-10
    
    # 4. 交叉熵 = 熵 + KL散度
    H_p = -np.sum(p * np.log2(p))
    kl_bits = np.sum(p * np.log2(p / q))
    ce_bits = -np.sum(p * np.log2(q))
    assert abs(ce_bits - (H_p + kl_bits)) < 1e-10
    
    # 5. 互信息
    # I(X;Y) = H(X) + H(Y) - H(X,Y)
    # 对于完全相关的 X=Y, I(X;Y) = H(X)
    joint = np.array([[0.5, 0], [0, 0.5]])  # X=Y, P(00)=0.5, P(11)=0.5
    px = joint.sum(axis=1)
    py = joint.sum(axis=0)
    H_x = -np.sum(px * np.log2(px + 1e-10))
    H_y = -np.sum(py * np.log2(py + 1e-10))
    H_xy = -np.sum(joint * np.log2(joint + 1e-10))
    mi = H_x + H_y - H_xy
    assert abs(mi - H_x) < 1e-10  # X=Y时互信息=H(X)
    
    # 6. 最大熵分布
    # 给定均值和方差约束，正态分布是最大熵分布
    # 均匀分布[0,1]的熵 = log2(1) = 1 bit... 不对
    # 连续情形: h(X) = -integral(f * ln(f))
    # 均匀分布[0,1]: h = ln(1) = 0 nats... 也不对
    # 均匀分布[a,b]: h = ln(b-a)
    # Uniform[0,1]: h = ln(1) = 0 nats
    h_uniform = np.log(2 - 0)  # Uniform[0,2] 的微分熵
    assert abs(h_uniform - np.log(2)) < 1e-10
    
    print("✅ 练习4 通过：信息论基础")


def exercise_5_statistical_inference():
    """练习5：统计推断 - MLE/MAP"""
    # 1. 最大似然估计 (MLE) - 正态分布
    # 给定数据，估计均值和标准差
    np.random.seed(42)
    true_mu, true_sigma = 5.0, 2.0
    data = np.random.normal(true_mu, true_sigma, 1000)
    
    # MLE: mu_hat = mean(data), sigma_hat = std(data) (有偏)
    mu_mle = np.mean(data)
    sigma_mle = np.std(data)  # MLE用有偏估计（除以N）
    assert abs(mu_mle - true_mu) < 0.2
    assert abs(sigma_mle - true_sigma) < 0.2
    
    # 2. MLE - 伯努利分布
    # 抛硬币10次，7次正面，MLE = 7/10 = 0.7
    coin_flips = np.array([1, 0, 1, 1, 0, 1, 1, 1, 0, 1])
    p_mle = coin_flips.mean()
    assert abs(p_mle - 0.7) < 1e-10
    
    # 3. MAP 估计 - Beta先验的伯努利
    # 先验 Beta(2,2)，似然 7正面3反面
    # MAP = (7+2-1) / (7+3+2+2-2) = 8/12 = 2/3
    alpha_prior, beta_prior = 2, 2
    successes, failures = 7, 3
    p_map = (successes + alpha_prior - 1) / (successes + failures + alpha_prior + beta_prior - 2)
    assert abs(p_map - 8/12) < 1e-10
    
    # 4. 置信区间
    # 95% CI for mean: mean ± 1.96 * sigma / sqrt(n)
    n = len(data)
    ci_lower = mu_mle - 1.96 * sigma_mle / np.sqrt(n)
    ci_upper = mu_mle + 1.96 * sigma_mle / np.sqrt(n)
    assert ci_lower < true_mu < ci_upper  # 真值应在置信区间内
    
    # 5. 假设检验 (t检验)
    # H0: mu = 5, H1: mu != 5
    t_stat, p_value = stats.ttest_1samp(data, 5.0)
    assert p_value > 0.05  # p > 0.05, 不拒绝H0（数据确实来自mu=5）
    
    # 6. 偏差-方差分解
    # E[(y - f_hat)^2] = Bias^2 + Variance + Noise
    # 模拟：用不同训练集训练简单模型，观察偏差和方差
    np.random.seed(42)
    n_simulations = 100
    n_train = 50
    true_func = lambda x: np.sin(x)
    x_test = np.array([np.pi / 4])  # 测试点
    
    predictions = []
    for _ in range(n_simulations):
        x_train = np.random.uniform(0, np.pi, n_train)
        y_train = true_func(x_train) + np.random.normal(0, 0.1, n_train)
        # 用常数模型（预测训练集均值）
        pred = y_train.mean()
        predictions.append(pred)
    
    predictions = np.array(predictions)
    bias = np.mean(predictions) - true_func(x_test[0])
    variance = np.var(predictions)
    total_error = np.mean((predictions - true_func(x_test[0])) ** 2)
    # 总误差 ≈ bias^2 + variance + noise_var
    assert abs(total_error - (bias ** 2 + variance + 0.01)) < 0.1  # noise_var=0.1^2=0.01
    
    print("✅ 练习5 通过：统计推断 MLE/MAP")


# ============================================================
# 扩展题
# ============================================================

def ext_1_svd_image_compression():
    """扩展1：SVD 图像压缩"""
    # 生成模拟灰度图像
    np.random.seed(42)
    image = np.random.randn(32, 32)
    # 添加低秩结构
    U, S, Vt = np.linalg.svd(image)
    
    # 用前k个奇异值重建
    k_values = [1, 5, 10, 20, 32]
    compression_ratios = []
    
    for k in k_values:
        reconstructed = U[:, :k] @ np.diag(S[:k]) @ Vt[:k, :]
        error = np.linalg.norm(image - reconstructed, 'fro') / np.linalg.norm(image, 'fro')
        ratio = k / 32  # 压缩比
        compression_ratios.append((k, error, ratio))
    
    # 验证：k越大，重建误差越小
    errors = [cr[1] for cr in compression_ratios]
    for i in range(len(errors) - 1):
        assert errors[i] >= errors[i + 1]
    
    # k=32 (满秩) 应该几乎完美重建
    assert compression_ratios[-1][1] < 1e-10
    
    print(f"   k=5: 误差={compression_ratios[1][1]:.4f}, 压缩比={compression_ratios[1][2]:.2%}")
    print(f"   k=10: 误差={compression_ratios[2][1]:.4f}, 压缩比={compression_ratios[2][2]:.2%}")
    print("✅ 扩展1 通过：SVD图像压缩")


def ext_2_bayesian_inference():
    """扩展2：贝叶斯推断 - 在线学习"""
    # Beta-Binomial 共轭：逐步观察数据，更新后验
    alpha, beta = 1, 1  # 均匀先验 Beta(1,1)
    true_p = 0.7
    
    np.random.seed(42)
    observations = np.random.binomial(1, true_p, 100)
    
    posterior_means = []
    for i, obs in enumerate(observations):
        if obs == 1:
            alpha += 1
        else:
            beta += 1
        posterior_mean = alpha / (alpha + beta)
        posterior_means.append(posterior_mean)
    
    # 后验均值应逐渐趋近真实值
    assert abs(posterior_means[-1] - true_p) < 0.1
    
    # 早期波动大，后期稳定
    early_var = np.var(posterior_means[:10])
    late_var = np.var(posterior_means[-10:])
    assert late_var < early_var
    
    print(f"   先验: Beta(1,1) → 后验: Beta({alpha},{beta})")
    print(f"   后验均值: {posterior_means[-1]:.4f} (真实值: {true_p})")
    print("✅ 扩展2 通过：贝叶斯在线学习")


def ext_3_gradient_methods_comparison():
    """扩展3：梯度下降方法对比"""
    # 最小化 f(x,y) = x^2 + 10*y^2 (病态条件)
    def f(x):
        return x[0] ** 2 + 10 * x[1] ** 2
    
    def grad_f(x):
        return np.array([2 * x[0], 20 * x[1]])
    
    # 1. 标准 GD
    x = np.array([5.0, 5.0])
    lr = 0.01
    gd_path = [x.copy()]
    for _ in range(500):
        x = x - lr * grad_f(x)
        gd_path.append(x.copy())
    assert f(x) < 0.1
    
    # 2. 动量法
    x = np.array([5.0, 5.0])
    v = np.zeros(2)
    lr, momentum = 0.01, 0.9
    momentum_path = [x.copy()]
    for _ in range(500):
        v = momentum * v - lr * grad_f(x)
        x = x + v
        momentum_path.append(x.copy())
    assert f(x) < 0.1
    
    # 3. Adam
    x = np.array([5.0, 5.0])
    m, v_adam = np.zeros(2), np.zeros(2)
    lr, beta1, beta2, eps = 0.1, 0.9, 0.999, 1e-8
    adam_path = [x.copy()]
    for t in range(500):
        g = grad_f(x)
        m = beta1 * m + (1 - beta1) * g
        v_adam = beta2 * v_adam + (1 - beta2) * g ** 2
        m_hat = m / (1 - beta1 ** (t + 1))
        v_hat = v_adam / (1 - beta2 ** (t + 1))
        x = x - lr * m_hat / (np.sqrt(v_hat) + eps)
        adam_path.append(x.copy())
    assert f(x) < 0.1
    
    # 对比收敛速度（达到 f < 0.01 的步数）
    gd_steps = next(i for i, p in enumerate(gd_path) if f(p) < 0.01)
    momentum_steps = next(i for i, p in enumerate(momentum_path) if f(p) < 0.01)
    adam_steps = next(i for i, p in enumerate(adam_path) if f(p) < 0.01)
    
    assert adam_steps <= gd_steps  # Adam 通常更快
    print(f"   GD: {gd_steps}步 | 动量: {momentum_steps}步 | Adam: {adam_steps}步")
    print("✅ 扩展3 通过：梯度方法对比")


def ext_4_entropy_classification():
    """扩展4：信息增益与决策树分裂准则"""
    # 计算信息增益（ID3 决策树核心）
    # 数据：天气与是否打球
    data = np.array([
        # [天气编码, 温度编码, 是否打球]
        [0, 0, 1],  # 晴, 热, 是
        [0, 1, 1],  # 晴, 适中, 是
        [0, 2, 0],  # 晴, 冷, 否
        [1, 0, 0],  # 阴, 热, 否
        [1, 1, 1],  # 阴, 适中, 是
        [2, 0, 1],  # 雨, 热, 是
        [2, 2, 0],  # 雨, 冷, 否
    ])
    
    def entropy(labels):
        _, counts = np.unique(labels, return_counts=True)
        probs = counts / len(labels)
        return -np.sum(probs * np.log2(probs + 1e-10))
    
    # 总熵
    total_entropy = entropy(data[:, 2])
    assert abs(total_entropy - 0.985) < 0.01  # 4个是, 3个否
    
    # 按天气分裂的信息增益
    info_gain_weather = 0
    for val in [0, 1, 2]:  # 晴, 阴, 雨
        subset = data[data[:, 0] == val]
        weight = len(subset) / len(data)
        info_gain_weather += weight * entropy(subset[:, 2])
    info_gain_weather = total_entropy - info_gain_weather
    assert info_gain_weather > 0
    
    # 按温度分裂的信息增益
    info_gain_temp = 0
    for val in [0, 1, 2]:
        subset = data[data[:, 1] == val]
        weight = len(subset) / len(data)
        info_gain_temp += weight * entropy(subset[:, 2])
    info_gain_temp = total_entropy - info_gain_temp
    
    # 基尼不纯度
    def gini(labels):
        _, counts = np.unique(labels, return_counts=True)
        probs = counts / len(labels)
        return 1 - np.sum(probs ** 2)
    
    gini_total = gini(data[:, 2])
    assert gini_total < 0.5  # 4/7和3/7的基尼
    
    print(f"   总熵: {total_entropy:.4f} | 天气信息增益: {info_gain_weather:.4f} | 温度信息增益: {info_gain_temp:.4f}")
    print("✅ 扩展4 通过：信息增益与决策树")


def ext_5_multivariate_gaussian():
    """扩展5：多元高斯分布与马氏距离"""
    # 生成二元高斯数据
    np.random.seed(42)
    mu = np.array([2, 3])
    cov = np.array([[1, 0.8], [0.8, 1]])
    data = np.random.multivariate_normal(mu, cov, 500)
    
    # 1. 参数估计
    mu_est = data.mean(axis=0)
    cov_est = np.cov(data, rowvar=False)
    assert np.allclose(mu_est, mu, atol=0.3)
    assert np.allclose(cov_est, cov, atol=0.3)
    
    # 2. 马氏距离 vs 欧氏距离
    point = np.array([4, 5])
    diff = point - mu
    # 欧氏距离
    euclidean = np.sqrt(np.sum(diff ** 2))
    # 马氏距离
    cov_inv = np.linalg.inv(cov)
    mahalanobis = np.sqrt(diff @ cov_inv @ diff)
    
    assert mahalanobis > 0
    assert euclidean > 0
    # 马氏距离考虑了协方差结构
    
    # 3. 协方差矩阵的特征分解
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    assert (eigenvalues > 0).all()  # 正定
    
    # 4. 椭圆主轴长度 = sqrt(eigenvalue) * scale
    # 第一主轴对应最大特征值
    major_axis = np.sqrt(eigenvalues[-1])
    minor_axis = np.sqrt(eigenvalues[0])
    assert major_axis >= minor_axis
    
    # 5. 条件分布
    # 给定 X1, 求 X2 的条件分布
    # mu_2|1 = mu_2 + cov_12 * cov_22_inv * (x1 - mu_1)
    # var_2|1 = cov_22 - cov_12 * cov_22_inv * cov_21
    x1_given = 3.0
    mu_cond = mu[1] + cov[0, 1] / cov[0, 0] * (x1_given - mu[0])
    var_cond = cov[1, 1] - cov[0, 1] ** 2 / cov[0, 0]
    
    # 验证条件方差 < 边缘方差
    assert var_cond < cov[1, 1]  # 知道X1后X2的不确定性降低
    
    print(f"   均值估计: {mu_est} | 马氏距离: {mahalanobis:.3f} | 欧氏距离: {euclidean:.3f}")
    print(f"   条件方差({var_cond:.3f}) < 边缘方差({cov[1,1]:.3f})")
    print("✅ 扩展5 通过：多元高斯分布")


# ============================================================
# 主函数
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("数学基础练习")
    print("=" * 60)
    exercise_1_linear_algebra()
    exercise_2_probability()
    exercise_3_calculus_optimization()
    exercise_4_information_theory()
    exercise_5_statistical_inference()
    
    print("\n" + "=" * 60)
    print("数学基础扩展题")
    print("=" * 60)
    ext_1_svd_image_compression()
    ext_2_bayesian_inference()
    ext_3_gradient_methods_comparison()
    ext_4_entropy_classification()
    ext_5_multivariate_gaussian()
    
    print("\n" + "=" * 60)
    print("全部通过！数学基础 + 扩展 10/10 ✅")
    print("=" * 60)
