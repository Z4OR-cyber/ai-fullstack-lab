"""
NumPy 基础练习 + 扩展题
========================
涵盖：数组创建、索引切片、运算、广播、线性代数、随机数
"""

import numpy as np
import time

# ============================================================
# 基础练习
# ============================================================

def exercise_1_array_creation():
    """练习1：数组创建与基本属性"""
    # 1. 从列表创建一维数组
    arr1 = np.array([1, 2, 3, 4, 5])
    assert arr1.shape == (5,)
    assert arr1.dtype == np.int64
    
    # 2. 创建 3x4 的全零矩阵
    zeros = np.zeros((3, 4))
    assert zeros.shape == (3, 4)
    
    # 3. 创建 3x3 的全一矩阵，类型为 float
    ones = np.ones((3, 3), dtype=np.float64)
    assert ones.dtype == np.float64
    
    # 4. 创建 0-9 的等差数列
    arange_arr = np.arange(0, 10)
    assert np.array_equal(arange_arr, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    
    # 5. 创建 0 到 1 之间均匀分布的 5 个数
    linspace_arr = np.linspace(0, 1, 5)
    assert len(linspace_arr) == 5
    assert abs(linspace_arr[0] - 0.0) < 1e-10
    assert abs(linspace_arr[-1] - 1.0) < 1e-10
    
    # 6. 创建 3x3 的单位矩阵
    identity = np.eye(3)
    assert np.array_equal(identity, np.eye(3))
    
    # 7. 创建对角矩阵
    diag = np.diag([1, 2, 3])
    assert diag.shape == (3, 3)
    assert diag[0, 0] == 1 and diag[1, 1] == 2 and diag[2, 2] == 3
    
    print("✅ 练习1 通过：数组创建与基本属性")


def exercise_2_indexing_slicing():
    """练习2：索引与切片"""
    arr = np.arange(1, 25).reshape(4, 6)
    # arr:
    # [[ 1  2  3  4  5  6]
    #  [ 7  8  9 10 11 12]
    #  [13 14 15 16 17 18]
    #  [19 20 21 22 23 24]]
    
    # 1. 获取第2行
    row2 = arr[1, :]
    assert np.array_equal(row2, [7, 8, 9, 10, 11, 12])
    
    # 2. 获取第3列
    col3 = arr[:, 2]
    assert np.array_equal(col3, [3, 9, 15, 21])
    
    # 3. 获取前2行前3列的子矩阵
    sub = arr[:2, :3]
    assert sub.shape == (2, 3)
    assert np.array_equal(sub, [[1, 2, 3], [7, 8, 9]])
    
    # 4. 布尔索引：获取所有偶数
    evens = arr[arr % 2 == 0]
    assert len(evens) == 12
    
    # 5. 花式索引：获取第0, 2, 3行
    fancy = arr[[0, 2, 3]]
    assert fancy.shape == (3, 6)
    
    # 6. 修改值：将所有大于10的元素设为-1
    arr_copy = arr.copy()
    arr_copy[arr_copy > 10] = -1
    assert (arr_copy > 10).sum() == 0
    
    # 7. 获取对角线元素
    diag_vals = np.diagonal(arr[:3, :3])
    assert np.array_equal(diag_vals, [1, 8, 15])
    
    print("✅ 练习2 通过：索引与切片")


def exercise_3_operations():
    """练习3：数组运算"""
    a = np.array([[1, 2], [3, 4]])
    b = np.array([[5, 6], [7, 8]])
    
    # 1. 元素级加减乘除
    add = a + b
    assert np.array_equal(add, [[6, 8], [10, 12]])
    
    sub = b - a
    assert np.array_equal(sub, [[4, 4], [4, 4]])
    
    mul = a * b  # 元素级乘法
    assert np.array_equal(mul, [[5, 12], [21, 32]])
    
    # 2. 矩阵乘法
    matmul = a @ b  # 或 np.matmul(a, b)
    assert np.array_equal(matmul, [[19, 22], [43, 50]])
    
    # 3. 逐元素平方
    squared = a ** 2
    assert np.array_equal(squared, [[1, 4], [9, 16]])
    
    # 4. 统计运算
    data = np.array([[1, 2, 3], [4, 5, 6]])
    assert data.sum() == 21
    assert data.mean() == 3.5
    assert data.max() == 6
    assert data.min() == 1
    assert data.std() == np.std(data)
    
    # 5. 按轴运算
    assert np.array_equal(data.sum(axis=0), [5, 7, 9])  # 列求和
    assert np.array_equal(data.sum(axis=1), [6, 15])    # 行求和
    
    # 6. 排序
    unsorted = np.array([3, 1, 4, 1, 5, 9, 2, 6])
    sorted_arr = np.sort(unsorted)
    assert np.array_equal(sorted_arr, [1, 1, 2, 3, 4, 5, 6, 9])
    
    # 7. 唯一值
    unique_vals = np.unique(unsorted)
    assert np.array_equal(unique_vals, [1, 2, 3, 4, 5, 6, 9])
    
    print("✅ 练习3 通过：数组运算")


def exercise_4_broadcasting():
    """练习4：广播机制"""
    # 1. 标量与数组
    a = np.array([1, 2, 3])
    result = a + 10
    assert np.array_equal(result, [11, 12, 13])
    
    # 2. 一维数组与二维数组
    matrix = np.array([[1, 2, 3], [4, 5, 6]])
    vector = np.array([10, 20, 30])
    result = matrix + vector  # 广播：vector 扩展为 2x3
    assert np.array_equal(result, [[11, 22, 33], [14, 25, 36]])
    
    # 3. 列向量与行向量
    col = np.array([[1], [2], [3]])  # 3x1
    row = np.array([10, 20, 30])     # (3,) -> 1x3
    result = col + row               # 广播为 3x3
    assert result.shape == (3, 3)
    assert np.array_equal(result, [[11, 21, 31], [12, 22, 32], [13, 23, 33]])
    
    # 4. 广播归一化
    data = np.array([[1, 2, 3], [4, 5, 6]], dtype=float)
    means = data.mean(axis=0)     # 每列均值
    normalized = data - means     # 广播减去列均值
    assert abs(normalized.mean(axis=0).max()) < 1e-10
    
    # 5. 外积通过广播
    a = np.array([1, 2, 3])
    b = np.array([10, 20, 30])
    outer = a[:, np.newaxis] * b[np.newaxis, :]  # 3x3 外积
    assert np.array_equal(outer, [[10, 20, 30], [20, 40, 60], [30, 60, 90]])
    
    print("✅ 练习4 通过：广播机制")


def exercise_5_linear_algebra():
    """练习5：线性代数"""
    # 1. 矩阵乘法
    A = np.array([[1, 2], [3, 4]])
    B = np.array([[5, 6], [7, 8]])
    C = A @ B
    assert np.array_equal(C, [[19, 22], [43, 50]])
    
    # 2. 行列式
    det = np.linalg.det(A)
    assert abs(det - (-2.0)) < 1e-10  # det([[1,2],[3,4]]) = 1*4-2*3 = -2
    
    # 3. 逆矩阵
    A_inv = np.linalg.inv(A)
    identity = A @ A_inv
    assert np.allclose(identity, np.eye(2))
    
    # 4. 解线性方程组 Ax = b
    b = np.array([5, 11])
    x = np.linalg.solve(A, b)
    # 1*x1 + 2*x2 = 5, 3*x1 + 4*x2 = 11 -> x1=1, x2=2
    assert np.allclose(x, [1.0, 2.0])
    
    # 5. 特征值和特征向量
    eigenvalues, eigenvectors = np.linalg.eig(A)
    # 验证 A @ v = lambda * v
    for i in range(len(eigenvalues)):
        v = eigenvectors[:, i]
        assert np.allclose(A @ v, eigenvalues[i] * v)
    
    # 6. SVD 分解
    U, S, Vt = np.linalg.svd(A)
    # 重构原矩阵
    reconstructed = U @ np.diag(S) @ Vt
    assert np.allclose(reconstructed, A)
    
    # 7. 范数
    v = np.array([3, 4])
    assert abs(np.linalg.norm(v) - 5.0) < 1e-10  # 3-4-5 三角形
    
    print("✅ 练习5 通过：线性代数")


# ============================================================
# 扩展题
# ============================================================

def ext_1_vectorized_operations():
    """扩展1：向量化加速 - 对比循环和向量化运算的性能"""
    # 生成大数据
    n = 1_000_000
    data = np.random.randn(n)
    
    # 循环方式
    start = time.time()
    result_loop = np.zeros(n)
    for i in range(n):
        result_loop[i] = data[i] ** 2 + 2 * data[i] + 1
    time_loop = time.time() - start
    
    # 向量化方式
    start = time.time()
    result_vec = data ** 2 + 2 * data + 1
    time_vec = time.time() - start
    
    assert np.allclose(result_loop, result_vec)
    speedup = time_loop / time_vec if time_vec > 0 else float('inf')
    print(f"   循环: {time_loop:.4f}s | 向量化: {time_vec:.4f}s | 加速比: {speedup:.1f}x")
    assert speedup > 10, f"向量化应该快10倍以上，实际 {speedup:.1f}x"
    print("✅ 扩展1 通过：向量化运算加速")


def ext_2_moving_average():
    """扩展2：滑动窗口均值 - 金融数据分析常用"""
    prices = np.array([10, 12, 11, 13, 15, 14, 16, 18, 17, 19], dtype=float)
    window = 3
    
    # 方法1：卷积
    ma_conv = np.convolve(prices, np.ones(window) / window, mode='valid')
    expected = np.array([11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0])
    assert np.allclose(ma_conv, expected)
    
    # 方法2：cumsum
    cumsum = np.cumsum(prices)
    cumsum[window:] = cumsum[window:] - cumsum[:-window]
    ma_cumsum = cumsum[window - 1:] / window
    assert np.allclose(ma_cumsum, expected)
    
    print(f"   3日均线: {ma_conv}")
    print("✅ 扩展2 通过：滑动窗口均值")


def ext_3_image_processing():
    """扩展3：图像处理模拟 - 灰度化、翻转、裁剪"""
    # 模拟 RGB 图像 (4x4x3)
    np.random.seed(42)
    image = np.random.randint(0, 256, (4, 4, 3), dtype=np.uint8)
    
    # 1. 灰度化（加权平均）
    weights = np.array([0.299, 0.587, 0.114])
    gray = np.dot(image, weights).astype(np.uint8)
    assert gray.shape == (4, 4)
    
    # 2. 水平翻转
    flipped_h = image[:, ::-1, :]
    assert np.array_equal(flipped_h[:, 0, :], image[:, -1, :])
    
    # 3. 垂直翻转
    flipped_v = image[::-1, :, :]
    assert np.array_equal(flipped_v[0, :, :], image[-1, :, :])
    
    # 4. 中心裁剪 2x2
    h, w = image.shape[:2]
    cropped = image[h//4:h//4+h//2, w//4:w//4+w//2]
    assert cropped.shape == (2, 2, 3)
    
    # 5. 亮度调整（乘以1.5并裁剪到255）
    brighter = np.clip(image.astype(float) * 1.5, 0, 255).astype(np.uint8)
    assert brighter.dtype == np.uint8
    assert (brighter >= image).all()
    
    print(f"   原始: {image.shape} | 灰度: {gray.shape} | 裁剪: {cropped.shape}")
    print("✅ 扩展3 通过：图像处理模拟")


def ext_4_eigen_decomposition_pca():
    """扩展4：用特征分解实现 PCA 降维"""
    # 生成 2D 数据
    np.random.seed(42)
    n = 100
    angle = np.pi / 4  # 45度旋转
    rotation = np.array([[np.cos(angle), -np.sin(angle)],
                         [np.sin(angle), np.cos(angle)]])
    data = np.random.randn(n, 2) @ rotation.T
    data[:, 0] *= 3  # 拉伸第一维
    
    # 1. 中心化
    data_centered = data - data.mean(axis=0)
    assert abs(data_centered.mean()) < 1e-10
    
    # 2. 计算协方差矩阵
    cov = np.cov(data_centered, rowvar=False)
    assert cov.shape == (2, 2)
    
    # 3. 特征分解
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    
    # 4. 按特征值降序排列
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]
    
    # 5. 投影到主成分
    projected = data_centered @ eigenvectors
    
    # 6. 降维：只保留第一主成分
    reduced = projected[:, 0]
    assert reduced.shape == (n,)
    
    # 验证：第一主成分的方差应该远大于第二主成分
    var_ratio = eigenvalues[0] / eigenvalues.sum()
    assert var_ratio > 0.85, f"第一主成分应解释85%以上方差，实际 {var_ratio:.2%}"
    print(f"   特征值: {eigenvalues} | 方差解释比: {var_ratio:.2%}")
    print("✅ 扩展4 通过：PCA 降维")


def ext_5_broadcasting_knn():
    """扩展5：用广播实现 KNN 算法"""
    # 训练数据 - 两个明显分离的簇
    np.random.seed(42)
    X_train = np.vstack([
        np.random.randn(5, 2) * 0.5,           # class 0: centered at (0,0)
        np.random.randn(5, 2) * 0.5 + [5, 5]   # class 1: centered at (5,5)
    ])
    y_train = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    
    # 测试数据
    X_test = np.array([[0.5, 0.5], [4.5, 4.5]])
    
    # 1. 计算距离矩阵（广播）
    # X_test: (2, 2), X_train: (10, 2) -> distances: (2, 10)
    diff = X_test[:, np.newaxis, :] - X_train[np.newaxis, :, :]  # (2, 10, 2)
    distances = np.sqrt((diff ** 2).sum(axis=2))  # (2, 10)
    
    assert distances.shape == (2, 10)
    
    # 2. 找最近的3个邻居
    k = 3
    nearest_indices = np.argsort(distances, axis=1)[:, :k]
    
    # 3. 投票
    predictions = []
    for i in range(len(X_test)):
        neighbor_labels = y_train[nearest_indices[i]]
        pred = np.bincount(neighbor_labels).argmax()
        predictions.append(pred)
    
    predictions = np.array(predictions)
    
    # [0.1, 0.2] 应该分类为 0（靠近前5个点）
    # [3.0, 3.0] 应该分类为 1（靠近后5个点）
    assert predictions[0] == 0, f"预期0，得到{predictions[0]}"
    assert predictions[1] == 1, f"预期1，得到{predictions[1]}"
    
    print(f"   预测结果: {predictions}")
    print("✅ 扩展5 通过：KNN 广播实现")


# ============================================================
# 主函数
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("NumPy 基础练习")
    print("=" * 60)
    exercise_1_array_creation()
    exercise_2_indexing_slicing()
    exercise_3_operations()
    exercise_4_broadcasting()
    exercise_5_linear_algebra()
    
    print("\n" + "=" * 60)
    print("NumPy 扩展题")
    print("=" * 60)
    ext_1_vectorized_operations()
    ext_2_moving_average()
    ext_3_image_processing()
    ext_4_eigen_decomposition_pca()
    ext_5_broadcasting_knn()
    
    print("\n" + "=" * 60)
    print("全部通过！NumPy 基础 + 扩展 10/10 ✅")
    print("=" * 60)
