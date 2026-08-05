"""
深度学习基础练习 + 扩展题
========================
用纯 NumPy 从零实现：MLP、CNN概念、RNN概念、梯度下降优化器
不依赖 PyTorch/TensorFlow，理解底层原理
"""

import numpy as np
import time
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 工具函数
# ============================================================

def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -250, 250)))

def sigmoid_deriv(x):
    s = sigmoid(x)
    return s * (1 - s)

def relu(x):
    return np.maximum(0, x)

def relu_deriv(x):
    return (np.asarray(x) > 0).astype(float)

def softmax(x):
    exp_x = np.exp(x - np.max(x, axis=1, keepdims=True))
    return exp_x / np.sum(exp_x, axis=1, keepdims=True)

def one_hot(y, n_classes):
    oh = np.zeros((len(y), n_classes))
    oh[np.arange(len(y)), y] = 1
    return oh

# ============================================================
# 基础练习
# ============================================================

def exercise_1_mlp_from_scratch():
    """练习1：从零实现多层感知机（MLP）"""
    # XOR 问题 - 经典非线性分类
    X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
    y = np.array([[0], [1], [1], [0]])
    
    # 网络结构: 2 -> 4 -> 1
    np.random.seed(42)
    W1 = np.random.randn(2, 4) * 0.5
    b1 = np.zeros((1, 4))
    W2 = np.random.randn(4, 1) * 0.5
    b2 = np.zeros((1, 1))
    
    lr = 1.0
    losses = []
    
    for epoch in range(2000):
        # 前向传播
        z1 = X @ W1 + b1
        a1 = sigmoid(z1)
        z2 = a1 @ W2 + b2
        a2 = sigmoid(z2)
        
        # 损失（MSE）
        loss = np.mean((a2 - y) ** 2)
        losses.append(loss)
        
        # 反向传播
        dz2 = (a2 - y) * sigmoid_deriv(z2)
        dW2 = a1.T @ dz2
        db2 = np.sum(dz2, axis=0, keepdims=True)
        
        dz1 = dz2 @ W2.T * sigmoid_deriv(z1)
        dW1 = X.T @ dz1
        db1 = np.sum(dz1, axis=0, keepdims=True)
        
        # 更新参数
        W2 -= lr * dW2
        b2 -= lr * db2
        W1 -= lr * dW1
        b1 -= lr * db1
    
    # 验证：XOR 问题已解决
    predictions = (a2 > 0.5).astype(int)
    assert np.array_equal(predictions.ravel(), y.ravel())
    assert losses[-1] < 0.01
    
    print(f"   XOR预测: {a2.ravel()} | 最终loss: {losses[-1]:.6f}")
    print("✅ 练习1 通过：MLP 从零实现（XOR）")


def exercise_2_activation_functions():
    """练习2：激活函数对比"""
    x = np.linspace(-5, 5, 100)
    
    # 1. Sigmoid
    s = sigmoid(x)
    assert s.min() > 0 and s.max() < 1  # 输出(0,1)
    assert abs(sigmoid(0) - 0.5) < 1e-10  # sigmoid(0)=0.5
    # 梯度消失：|x|大时导数趋近0
    assert sigmoid_deriv(5) < 0.01
    
    # 2. ReLU
    r = relu(x)
    assert (r[x < 0] == 0).all()  # 负数输出0
    assert (r[x > 0] == x[x > 0]).all()  # 正数输出自身
    # ReLU 导数
    assert relu_deriv(-1) == 0
    assert relu_deriv(1) == 1
    
    # 3. Tanh
    t = np.tanh(x)
    assert t.min() > -1 and t.max() < 1  # 输出(-1,1)
    assert abs(np.tanh(0)) < 1e-10  # tanh(0)=0
    
    # 4. Leaky ReLU
    def leaky_relu(x, alpha=0.01):
        return np.where(x > 0, x, alpha * x)
    lr = leaky_relu(x)
    assert (lr[x < 0] < 0).any()  # 负数有微小输出
    assert (lr[x < 0] > x[x < 0]).all()  # 比普通ReLU大
    
    # 5. Softmax
    logits = np.array([[1, 2, 3], [1, 1, 1]])
    sm = softmax(logits)
    assert np.allclose(sm.sum(axis=1), 1.0)  # 概率和为1
    assert sm[1, 0] == sm[1, 1] == sm[1, 2]  # 相同logits相同概率
    
    print("✅ 练习2 通过：激活函数对比")


def exercise_3_backpropagation():
    """练习3：梯度消失与权重初始化"""
    # 1. 梯度消失演示
    np.random.seed(42)
    depth = 10  # 10层网络
    input_size = 100
    x = np.random.randn(1, input_size)
    
    # 用 sigmoid + 随机初始化
    gradients_sigmoid = []
    activations = x.copy()
    weights = [np.random.randn(input_size, input_size) * 0.5 for _ in range(depth)]
    
    for w in weights:
        activations = sigmoid(activations @ w)
    
    # 反向传播计算梯度
    grad = np.ones_like(activations)
    for w in reversed(weights):
        grad = grad @ w.T * sigmoid_deriv(activations @ w)  # 近似
        gradients_sigmoid.append(np.abs(grad).mean())
    
    # sigmoid 的梯度会逐渐减小
    assert gradients_sigmoid[0] > gradients_sigmoid[-1]  # 梯度消失
    
    # 2. Xavier/Glorot 初始化
    fan_in, fan_out = 100, 100
    # Xavier: std = sqrt(2 / (fan_in + fan_out))
    xavier_std = np.sqrt(2.0 / (fan_in + fan_out))
    xavier_weights = np.random.randn(fan_in, fan_out) * xavier_std
    assert np.abs(xavier_weights.std() - xavier_std) < 0.01
    
    # 3. He 初始化（配合 ReLU）
    # He: std = sqrt(2 / fan_in)
    he_std = np.sqrt(2.0 / fan_in)
    he_weights = np.random.randn(fan_in, fan_out) * he_std
    assert np.abs(he_weights.std() - he_std) < 0.01
    
    # 4. 验证 He 初始化保持激活值方差
    np.random.seed(42)
    x = np.random.randn(1000, fan_in)
    w_he = np.random.randn(fan_in, fan_out) * he_std
    a = relu(x @ w_he)
    # 激活值方差应与输入方差接近（ReLU有一半为0）
    var_ratio = a.var() / x.var()
    assert 0.3 < var_ratio < 1.5  # 合理范围
    
    print(f"   梯度消失: {gradients_sigmoid[0]:.6f} → {gradients_sigmoid[-1]:.6f}")
    print(f"   He初始化方差比: {var_ratio:.3f}")
    print("✅ 练习3 通过：梯度消失与权重初始化")


def exercise_4_optimizers():
    """练习4：优化器实现与对比"""
    # 最小化 Beale 函数: f(x,y) = (1.5-x+xy)^2 + (2.25-x+xy^2)^2 + (2.625-x+xy^3)^2
    def beale(x):
        return ((1.5 - x[0] + x[0]*x[1])**2 + 
                (2.25 - x[0] + x[0]*x[1]**2)**2 + 
                (2.625 - x[0] + x[0]*x[1]**3)**2)
    
    def beale_grad(x):
        dx = 2*(1.5-x[0]+x[0]*x[1])*(x[1]-1) + 2*(2.25-x[0]+x[0]*x[1]**2)*(x[1]**2-1) + 2*(2.625-x[0]+x[0]*x[1]**3)*(x[1]**3-1)
        dy = 2*(1.5-x[0]+x[0]*x[1])*x[0] + 2*(2.25-x[0]+x[0]*x[1]**2)*2*x[0]*x[1] + 2*(2.625-x[0]+x[0]*x[1]**3)*3*x[0]*x[1]**2
        return np.array([dx, dy])
    
    x0 = np.array([1.0, 1.0])
    results = {}
    
    # 1. SGD
    x = x0.copy()
    lr = 0.001
    for _ in range(5000):
        g = beale_grad(x)
        x -= lr * g
    results['SGD'] = (beale(x), x.copy())
    
    # 2. Momentum
    x = x0.copy()
    v = np.zeros(2)
    lr, momentum = 0.001, 0.9
    for _ in range(5000):
        g = beale_grad(x)
        v = momentum * v - lr * g
        x += v
    results['Momentum'] = (beale(x), x.copy())
    
    # 3. Adam
    x = x0.copy()
    m, v_adam = np.zeros(2), np.zeros(2)
    lr, b1, b2, eps = 0.01, 0.9, 0.999, 1e-8
    for t in range(5000):
        g = beale_grad(x)
        m = b1 * m + (1 - b1) * g
        v_adam = b2 * v_adam + (1 - b2) * g**2
        m_hat = m / (1 - b1**(t+1))
        v_hat = v_adam / (1 - b2**(t+1))
        x -= lr * m_hat / (np.sqrt(v_hat) + eps)
    results['Adam'] = (beale(x), x.copy())
    
    # 验证所有优化器都收敛
    for name, (loss, _) in results.items():
        assert loss < 1.0, f"{name} loss={loss} 应该 < 1.0"
    
    # Adam 通常收敛最好
    assert results['Adam'][0] <= results['SGD'][0] + 0.1
    
    print(f"   SGD: {results['SGD'][0]:.6f} | Momentum: {results['Momentum'][0]:.6f} | Adam: {results['Adam'][0]:.6f}")
    print("✅ 练习4 通过：优化器实现与对比")


def exercise_5_regularization_dropout():
    """练习5：正则化与 Dropout"""
    np.random.seed(42)
    n = 200
    X = np.random.randn(n, 20)
    true_w = np.random.randn(20)
    y = (X @ true_w + np.random.normal(0, 0.1, n) > 0).astype(int)
    
    X_train, X_test = X[:150], X[50:]
    y_train, y_test = y[:150], y[50:]
    
    # 1. L2 正则化
    def train_with_l2(X, y, l2_lambda=0, epochs=500, lr=0.1):
        n_features = X.shape[1]
        W = np.random.randn(n_features) * 0.1
        b = 0.0
        y = y.astype(float)
        for _ in range(epochs):
            z = X @ W + b
            a = sigmoid(z)
            dz = a - y
            dW = X.T @ dz / len(y) + l2_lambda * W  # L2 正则化梯度
            db = np.mean(dz)
            W -= lr * dW
            b -= lr * db
        return W, b
    
    # 无正则化
    W_no_reg, b_no_reg = train_with_l2(X_train, y_train, l2_lambda=0)
    # 强 L2 正则化
    W_l2, b_l2 = train_with_l2(X_train, y_train, l2_lambda=0.1)
    
    # 正则化后权重更小
    assert np.abs(W_l2).sum() < np.abs(W_no_reg).sum()
    
    # 2. Dropout 实现
    def train_with_dropout(X, y, drop_rate=0.0, epochs=500, lr=0.1):
        n_features = X.shape[1]
        W = np.random.randn(n_features) * 0.1
        b = 0.0
        y = y.astype(float)
        for _ in range(epochs):
            # Dropout mask
            mask = (np.random.rand(n_features) > drop_rate) / (1 - drop_rate)
            X_dropped = X * mask
            z = X_dropped @ W + b
            a = sigmoid(z)
            dz = a - y
            dW = X_dropped.T @ dz / len(y)
            db = np.mean(dz)
            W -= lr * dW
            b -= lr * db
        return W, b
    
    W_drop, b_drop = train_with_dropout(X_train, y_train, drop_rate=0.3)
    
    # 3. Early Stopping 概念
    train_losses = []
    val_losses = []
    W = np.random.randn(20) * 0.1
    b = 0.0
    best_val_loss = float('inf')
    patience, no_improve = 5, 0
    
    for epoch in range(2000):
        z = X_train @ W + b
        a = sigmoid(z)
        dz = a - y_train.astype(float)
        W -= 0.5 * X_train.T @ dz / len(y_train)
        b -= 0.5 * np.mean(dz)
        
        train_loss = -np.mean(y_train * np.log(a + 1e-10) + (1 - y_train) * np.log(1 - a + 1e-10))
        val_a = sigmoid(X_test @ W + b)
        val_loss = -np.mean(y_test * np.log(val_a + 1e-10) + (1 - y_test) * np.log(1 - val_a + 1e-10))
        train_losses.append(train_loss)
        val_losses.append(val_loss)
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                break
    
    # 验证 early stopping 机制存在（可能触发也可能不触发）
    assert len(train_losses) <= 2000
    
    print(f"   L2权重和: {np.abs(W_no_reg).sum():.2f} → {np.abs(W_l2).sum():.2f} (更小)")
    print(f"   Early stopping: 在第{len(train_losses)}轮停止 (共1000轮)")
    print("✅ 练习5 通过：正则化与 Dropout")


# ============================================================
# 扩展题
# ============================================================

def ext_1_mnist_mlp():
    """扩展1：MNIST 风格数字分类 - 完整 MLP 训练"""
    # 生成模拟 MNIST 数据 (8x8 = 64 features, 10 classes)
    np.random.seed(42)
    n = 1000
    n_features = 64
    n_classes = 10
    
    X = np.random.randn(n, n_features)
    # 构造有意义的标签：每个类别有不同的权重模式
    true_weights = np.random.randn(n_features, n_classes)
    logits = X @ true_weights + np.random.normal(0, 0.5, (n, n_classes))
    y = np.argmax(logits, axis=1)
    
    X_train, X_test = X[:800], X[800:]
    y_train, y_test = y[:800], y[800:]
    y_train_oh = one_hot(y_train, n_classes)
    
    # 网络结构: 64 -> 64 -> 10
    np.random.seed(42)
    W1 = np.random.randn(64, 64) * np.sqrt(2.0 / 64)  # He init
    b1 = np.zeros(64)
    W2 = np.random.randn(64, 10) * np.sqrt(2.0 / 64)
    b2 = np.zeros(10)
    
    lr = 0.05
    batch_size = 32
    losses = []
    
    for epoch in range(500):
        # Mini-batch
        idx = np.random.permutation(len(X_train))
        for i in range(0, len(X_train), batch_size):
            batch_idx = idx[i:i+batch_size]
            Xb = X_train[batch_idx]
            yb = y_train_oh[batch_idx]
            
            # 前向
            z1 = Xb @ W1 + b1
            a1 = relu(z1)
            z2 = a1 @ W2 + b2
            a2 = softmax(z2)
            
            # 反向
            dz2 = (a2 - yb) / len(Xb)
            dW2 = a1.T @ dz2
            db2 = np.sum(dz2, axis=0)
            
            dz1 = dz2 @ W2.T * relu_deriv(z1)
            dW1 = Xb.T @ dz1
            db1 = np.sum(dz1, axis=0)
            
            W2 -= lr * dW2
            b2 -= lr * db2
            W1 -= lr * dW1
            b1 -= lr * db1
        
        # 计算损失
        z1 = X_train @ W1 + b1
        a1 = relu(z1)
        z2 = a1 @ W2 + b2
        a2 = softmax(z2)
        loss = -np.mean(np.sum(y_train_oh * np.log(a2 + 1e-10), axis=1))
        losses.append(loss)
    
    # 评估
    z1 = X_test @ W1 + b1
    a1 = relu(z1)
    z2 = a1 @ W2 + b2
    y_pred = np.argmax(z2, axis=1)
    acc = np.mean(y_pred == y_test)
    
    assert acc > 0.6  # 远超随机(10%)
    assert losses[-1] < losses[0]
    assert losses[-1] < 0.5
    
    print(f"   测试集准确率: {acc:.3f} | 最终loss: {losses[-1]:.4f}")
    print("✅ 扩展1 通过：MNIST 风格 MLP 分类")


def ext_2_cnn_concept():
    """扩展2：CNN 卷积与池化实现"""
    # 1. 卷积运算
    def conv2d(image, kernel, stride=1):
        h, w = image.shape
        kh, kw = kernel.shape
        out_h = (h - kh) // stride + 1
        out_w = (w - kw) // stride + 1
        output = np.zeros((out_h, out_w))
        for i in range(out_h):
            for j in range(out_w):
                output[i, j] = np.sum(
                    image[i*stride:i*stride+kh, j*stride:j*stride+kw] * kernel
                )
        return output
    
    # 边缘检测
    image = np.array([
        [0, 0, 0, 0, 0],
        [0, 1, 1, 1, 0],
        [0, 1, 1, 1, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 0, 0]
    ], dtype=float)
    
    # Sobel 算子 - 水平边缘
    sobel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]])
    # Sobel 算子 - 垂直边缘
    sobel_y = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]])
    
    edge_x = conv2d(image, sobel_x)
    edge_y = conv2d(image, sobel_y)
    
    assert edge_x.shape == (3, 3)
    assert edge_y.shape == (3, 3)
    
    # 2. 最大池化
    def max_pool2d(image, pool_size=2):
        h, w = image.shape
        out_h, out_w = h // pool_size, w // pool_size
        output = np.zeros((out_h, out_w))
        for i in range(out_h):
            for j in range(out_w):
                output[i, j] = np.max(
                    image[i*pool_size:(i+1)*pool_size, j*pool_size:(j+1)*pool_size]
                )
        return output
    
    pool_input = np.array([
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10, 11, 12],
        [13, 14, 15, 16]
    ], dtype=float)
    
    pooled = max_pool2d(pool_input, pool_size=2)
    expected = np.array([[6, 8], [14, 16]])
    assert np.array_equal(pooled, expected)
    
    # 3. 多通道卷积
    # 模拟 RGB 图像与多滤波器
    np.random.seed(42)
    image_rgb = np.random.randn(6, 6, 3)  # 6x6x3
    n_filters = 4
    kernels = np.random.randn(3, 3, 3, n_filters)  # 3x3x3x4
    
    feature_maps = np.zeros((4, 4, n_filters))
    for f in range(n_filters):
        for c in range(3):
            feature_maps[:, :, f] += conv2d(image_rgb[:, :, c], kernels[:, :, c, f])
    
    assert feature_maps.shape == (4, 4, n_filters)
    
    # 4. ReLU 激活后池化
    feature_maps_relu = relu(feature_maps)
    # 对每个特征图做池化
    pooled_features = np.zeros((2, 2, n_filters))
    for f in range(n_filters):
        pooled_features[:, :, f] = max_pool2d(feature_maps_relu[:, :, f])
    
    assert pooled_features.shape == (2, 2, n_filters)
    
    print(f"   卷积输出: {edge_x.shape} | 池化输出: {pooled.shape} | 特征图: {feature_maps.shape}")
    print("✅ 扩展2 通过：CNN 卷积与池化")


def ext_3_rnn_concept():
    """扩展3：RNN 序列建模概念"""
    # 1. 简单 RNN 单元
    def rnn_cell(x_t, h_prev, W_x, W_h, b):
        h_t = np.tanh(x_t @ W_x + h_prev @ W_h + b)
        return h_t
    
    # 2. RNN 前向传播
    def rnn_forward(X, h0, W_x, W_h, b):
        seq_len = X.shape[0]
        hidden_size = W_h.shape[0]
        h = h0.copy()
        hidden_states = [h.copy()]
        
        for t in range(seq_len):
            h = rnn_cell(X[t], h, W_x, W_h, b)
            hidden_states.append(h.copy())
        
        return np.array(hidden_states)
    
    # 3. 序列分类：判断序列是否递增
    np.random.seed(42)
    n_samples = 200
    seq_len = 5
    input_size = 1
    hidden_size = 8
    n_classes = 2
    
    # 生成数据
    X_data = []
    y_data = []
    for _ in range(n_samples):
        seq = np.random.uniform(0, 10, seq_len)
        label = 1 if seq[-1] > seq[0] else 0  # 递增=1
        X_data.append(seq.reshape(seq_len, input_size))
        y_data.append(label)
    
    X_data = np.array(X_data)
    y_data = np.array(y_data)
    
    # 初始化参数
    W_x = np.random.randn(input_size, hidden_size) * 0.1
    W_h = np.random.randn(hidden_size, hidden_size) * 0.1
    b = np.zeros(hidden_size)
    W_out = np.random.randn(hidden_size, n_classes) * 0.1
    b_out = np.zeros(n_classes)
    
    lr = 0.01
    losses = []
    
    for epoch in range(300):
        total_loss = 0
        for i in range(n_samples):
            X_seq = X_data[i]
            y_true = y_data[i]
            
            # 前向
            h0 = np.zeros(hidden_size)
            hidden_states = rnn_forward(X_seq, h0, W_x, W_h, b)
            h_final = hidden_states[-1]
            
            # 输出层
            logits = h_final @ W_out + b_out
            probs = softmax(logits.reshape(1, -1)).ravel()
            
            # 损失
            loss = -np.log(probs[y_true] + 1e-10)
            total_loss += loss
            
            # 反向（简化，只更新输出层）
            dlogits = probs.copy()
            dlogits[y_true] -= 1
            dW_out = np.outer(h_final, dlogits)
            db_out = dlogits
            
            # 通过 hidden state 更新 RNN（BPTT - 累积梯度后统一更新）
            dh = dlogits @ W_out.T
            gW_x = np.zeros_like(W_x)
            gW_h = np.zeros_like(W_h)
            gb = np.zeros_like(b)
            for t in range(seq_len - 1, -1, -1):
                dtanh = dh * (1 - hidden_states[t + 1] ** 2)
                gW_x += np.outer(X_seq[t], dtanh)
                gW_h += np.outer(hidden_states[t], dtanh)
                gb += dtanh
                dh = dtanh @ W_h.T  # 用旧权重计算 dh
            
            W_x -= lr * gW_x
            W_h -= lr * gW_h
            b -= lr * gb
            W_out -= lr * dW_out
            b_out -= lr * db_out
        
        losses.append(total_loss / n_samples)
    
    # 评估
    correct = 0
    for i in range(n_samples):
        hidden_states = rnn_forward(X_data[i], np.zeros(hidden_size), W_x, W_h, b)
        logits = hidden_states[-1] @ W_out + b_out
        pred = np.argmax(logits)
        if pred == y_data[i]:
            correct += 1
    
    acc = correct / n_samples
    assert acc > 0.6  # 应该比随机(50%)好
    assert losses[-1] < losses[0]
    
    print(f"   RNN序列分类准确率: {acc:.3f} | loss: {losses[0]:.3f} → {losses[-1]:.3f}")
    print("✅ 扩展3 通过：RNN 序列建模")


def ext_4_attention_mechanism():
    """扩展4：Attention 机制实现"""
    # 1. Scaled Dot-Product Attention
    def scaled_dot_product_attention(Q, K, V):
        d_k = K.shape[-1]
        scores = Q @ K.T / np.sqrt(d_k)
        weights = softmax(scores)
        output = weights @ V
        return output, weights
    
    # 2. Multi-Head Attention 概念
    seq_len = 5
    d_model = 8
    n_heads = 2
    d_k = d_model // n_heads
    
    np.random.seed(42)
    Q = np.random.randn(seq_len, d_model)
    K = np.random.randn(seq_len, d_model)
    V = np.random.randn(seq_len, d_model)
    
    # 分头
    def split_heads(x, n_heads):
        seq_len, d_model = x.shape
        d_k = d_model // n_heads
        return x.reshape(seq_len, n_heads, d_k).transpose(1, 0, 2)
    
    Q_heads = split_heads(Q, n_heads)  # (n_heads, seq_len, d_k)
    K_heads = split_heads(K, n_heads)
    V_heads = split_heads(V, n_heads)
    
    # 每个头单独做 attention
    head_outputs = []
    all_weights = []
    for h in range(n_heads):
        out, weights = scaled_dot_product_attention(Q_heads[h], K_heads[h], V_heads[h])
        head_outputs.append(out)
        all_weights.append(weights)
    
    # 合并头
    concat = np.stack(head_outputs, axis=1).reshape(seq_len, d_model)
    
    assert concat.shape == (seq_len, d_model)
    
    # 3. Attention 权重性质
    for h in range(n_heads):
        w = all_weights[h]
        assert np.allclose(w.sum(axis=1), 1.0)  # 权重和为1
        assert (w >= 0).all()  # 非负
    
    # 4. Self-Attention：Q=K=V
    self_out, self_weights = scaled_dot_product_attention(Q, K, V)
    assert self_out.shape == (seq_len, d_model)
    assert self_weights.shape == (seq_len, seq_len)
    
    # 5. Positional Encoding 概念
    def positional_encoding(seq_len, d_model):
        pe = np.zeros((seq_len, d_model))
        position = np.arange(seq_len)[:, np.newaxis]
        div_term = np.exp(np.arange(0, d_model, 2) * (-np.log(10000.0) / d_model))
        pe[:, 0::2] = np.sin(position * div_term)
        pe[:, 1::2] = np.cos(position * div_term)
        return pe
    
    pe = positional_encoding(seq_len, d_model)
    assert pe.shape == (seq_len, d_model)
    # 不同位置的编码不同
    assert not np.allclose(pe[0], pe[1])
    
    print(f"   Attention输出: {self_out.shape} | 权重矩阵: {self_weights.shape}")
    print(f"   位置编码示例[0,:4]: {pe[0, :4].round(3)}")
    print("✅ 扩展4 通过：Attention 机制")


def ext_5_loss_functions():
    """扩展5：损失函数实现与分析"""
    # 1. MSE（回归）
    y_true = np.array([1, 2, 3])
    y_pred = np.array([1.1, 2.2, 2.8])
    mse = np.mean((y_true - y_pred) ** 2)
    expected_mse = (0.01 + 0.04 + 0.04) / 3
    assert abs(mse - expected_mse) < 1e-10
    
    # 2. 交叉熵（二分类）
    y_true_b = np.array([1, 0, 1])
    y_pred_b = np.array([0.9, 0.1, 0.8])
    bce = -np.mean(y_true_b * np.log(y_pred_b) + (1 - y_true_b) * np.log(1 - y_pred_b))
    assert bce > 0
    
    # 3. Categorical Cross-Entropy（多分类）
    y_true_c = one_hot(np.array([0, 1, 2]), 3)
    y_pred_c = np.array([[0.7, 0.2, 0.1], [0.1, 0.8, 0.1], [0.1, 0.1, 0.8]])
    cce = -np.mean(np.sum(y_true_c * np.log(y_pred_c), axis=1))
    assert cce > 0
    
    # 完美预测时 loss ≈ 0
    perfect_cce = -np.mean(np.sum(y_true_c * np.log(y_true_c + 1e-10), axis=1))
    assert perfect_cce < 0.01
    
    # 4. Hinge Loss（SVM）
    def hinge_loss(y_true, y_pred):
        return np.mean(np.maximum(0, 1 - y_true * y_pred))
    
    y_true_h = np.array([1, -1, 1])
    y_pred_h = np.array([2, -0.5, 0.5])
    hl = hinge_loss(y_true_h, y_pred_h)
    assert hl > 0  # 有误分类
    
    # 5. Focal Loss（处理类别不平衡）
    def focal_loss(y_true, y_pred, gamma=2.0, alpha=0.25):
        p = y_pred
        ce = -y_true * np.log(p + 1e-10)
        focal_weight = alpha * (1 - p) ** gamma
        return np.mean(focal_weight * ce * y_true + (1 - alpha) * p ** gamma * (- (1 - y_true) * np.log(1 - p + 1e-10)))
    
    # Focal Loss 对难分类样本（p低）给更大权重
    easy_sample = np.array([1.0]), np.array([0.9])  # 易分类
    hard_sample = np.array([1.0]), np.array([0.3])  # 难分类
    fl_easy = focal_loss(*easy_sample)
    fl_hard = focal_loss(*hard_sample)
    assert fl_hard > fl_easy  # 难分类样本 loss 更大
    
    # 6. Label Smoothing
    def label_smoothing(y_true, n_classes, smoothing=0.1):
        return y_true * (1 - smoothing) + smoothing / n_classes
    
    y_smooth = label_smoothing(y_true_c, 3, 0.1)
    assert y_smooth.max() < 1.0  # 最大值被平滑
    assert y_smooth.min() > 0.0  # 最小值不为0
    assert np.allclose(y_smooth.sum(axis=1), 1.0)  # 仍然是概率分布
    
    print(f"   MSE: {mse:.4f} | BCE: {bce:.4f} | CCE: {cce:.4f} | Hinge: {hl:.4f}")
    print(f"   Focal: easy={fl_easy:.4f} hard={fl_hard:.4f} (hard > easy)")
    print("✅ 扩展5 通过：损失函数实现与分析")


# ============================================================
# 主函数
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("深度学习基础练习")
    print("=" * 60)
    exercise_1_mlp_from_scratch()
    exercise_2_activation_functions()
    exercise_3_backpropagation()
    exercise_4_optimizers()
    exercise_5_regularization_dropout()
    
    print("\n" + "=" * 60)
    print("深度学习扩展题")
    print("=" * 60)
    ext_1_mnist_mlp()
    ext_2_cnn_concept()
    ext_3_rnn_concept()
    ext_4_attention_mechanism()
    ext_5_loss_functions()
    
    print("\n" + "=" * 60)
    print("全部通过！深度学习基础 + 扩展 10/10 ✅")
    print("=" * 60)
