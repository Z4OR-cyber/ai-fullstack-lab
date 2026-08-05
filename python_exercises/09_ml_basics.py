"""
机器学习基础练习 + 扩展题
========================
涵盖：线性回归、逻辑回归、决策树、随机森林、SVM、K-Means、朴素贝叶斯
使用 scikit-learn 实现，每个算法含原理验证
"""

import numpy as np
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.cluster import KMeans
from sklearn.naive_bayes import GaussianNB
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.metrics import (accuracy_score, precision_score, recall_score, 
                             f1_score, confusion_matrix, roc_auc_score, 
                             mean_squared_error, r2_score, classification_report)
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.pipeline import Pipeline
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 基础练习
# ============================================================

def exercise_1_linear_regression():
    """练习1：线性回归"""
    # 生成数据: y = 3x + 2 + noise
    np.random.seed(42)
    X = np.random.uniform(0, 10, 100)
    y = 3 * X + 2 + np.random.normal(0, 1, 100)
    X = X.reshape(-1, 1)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 1. 训练模型
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    # 2. 参数估计
    assert abs(model.coef_[0] - 3.0) < 0.3  # 斜率接近3
    assert abs(model.intercept_ - 2.0) < 0.5  # 截距接近2
    
    # 3. 预测与评估
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    assert mse < 2.0  # MSE应该较小
    assert r2 > 0.95  # R²应该很高
    
    # 4. 多项式回归
    # y = x^2 的非线性关系
    X_poly = np.random.uniform(-3, 3, 100)
    y_poly = X_poly ** 2 + np.random.normal(0, 0.5, 100)
    X_poly = X_poly.reshape(-1, 1)
    
    # 线性模型（欠拟合）
    linear_model = LinearRegression()
    linear_model.fit(X_poly, y_poly)
    r2_linear = r2_score(y_poly, linear_model.predict(X_poly))
    assert r2_linear < 0.5  # 线性模型无法拟合二次关系
    
    # 多项式模型
    poly_features = PolynomialFeatures(degree=2, include_bias=False)
    X_poly_feat = poly_features.fit_transform(X_poly)
    poly_model = LinearRegression()
    poly_model.fit(X_poly_feat, y_poly)
    r2_poly = r2_score(y_poly, poly_model.predict(X_poly_feat))
    assert r2_poly > 0.9  # 多项式模型拟合良好
    
    print(f"   斜率: {model.coef_[0]:.2f}(真实3.0) | R²: {r2:.4f} | 多项式R²: {r2_poly:.4f}")
    print("✅ 练习1 通过：线性回归")


def exercise_2_logistic_regression():
    """练习2：逻辑回归与分类评估"""
    # 生成二分类数据
    np.random.seed(42)
    n = 200
    X = np.random.randn(n, 2)
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    
    # 1. 训练逻辑回归
    model = LogisticRegression()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    
    # 2. 分类指标
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    rec = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    
    assert acc > 0.9  # 简单数据应该高准确率
    assert 0 <= prec <= 1
    assert 0 <= rec <= 1
    assert 0 <= f1 <= 1
    
    # 3. 混淆矩阵
    cm = confusion_matrix(y_test, y_pred)
    assert cm.shape == (2, 2)
    assert cm.sum() == len(y_test)
    
    # 4. ROC AUC
    y_proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_proba)
    assert auc > 0.9  # AUC应该很高
    
    # 5. 正则化对比
    # L1 正则化（Lasso）可以做特征选择
    model_l1 = LogisticRegression(penalty='l1', solver='liblinear', C=0.1)
    model_l1.fit(X_train, y_train)
    # L2 正则化（Ridge）
    model_l2 = LogisticRegression(penalty='l2', C=0.1)
    model_l2.fit(X_train, y_train)
    
    assert accuracy_score(y_test, model_l1.predict(X_test)) > 0.8
    assert accuracy_score(y_test, model_l2.predict(X_test)) > 0.8
    
    print(f"   Acc: {acc:.3f} | Prec: {prec:.3f} | Rec: {rec:.3f} | F1: {f1:.3f} | AUC: {auc:.3f}")
    print("✅ 练习2 通过：逻辑回归与分类评估")


def exercise_3_decision_tree():
    """练习3：决策树与随机森林"""
    # 生成数据
    np.random.seed(42)
    n = 300
    X = np.random.randn(n, 4)
    y = (X[:, 0] ** 2 + X[:, 1] > 1).astype(int)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    
    # 1. 决策树
    dt = DecisionTreeClassifier(max_depth=5, random_state=42)
    dt.fit(X_train, y_train)
    dt_acc = accuracy_score(y_test, dt.predict(X_test))
    assert dt_acc > 0.85
    
    # 2. 特征重要性
    importances = dt.feature_importances_
    assert len(importances) == 4
    assert abs(importances.sum() - 1.0) < 1e-6
    # X[:,0] 和 X[:,1] 是关键特征
    assert importances[0] + importances[1] > 0.8
    
    # 3. 随机森林
    rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    rf.fit(X_train, y_train)
    rf_acc = accuracy_score(y_test, rf.predict(X_test))
    assert rf_acc > 0.85
    
    # 4. 随机森林通常不差于单棵决策树
    assert rf_acc >= dt_acc - 0.05
    
    # 5. GBDT
    gb = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
    gb.fit(X_train, y_train)
    gb_acc = accuracy_score(y_test, gb.predict(X_test))
    assert gb_acc > 0.85
    
    # 6. 交叉验证
    cv_scores = cross_val_score(rf, X, y, cv=5)
    assert cv_scores.mean() > 0.8
    assert cv_scores.std() < 0.1  # 各折差异不应太大
    
    print(f"   DT: {dt_acc:.3f} | RF: {rf_acc:.3f} | GBDT: {gb_acc:.3f} | CV: {cv_scores.mean():.3f}±{cv_scores.std():.3f}")
    print("✅ 练习3 通过：决策树与随机森林")


def exercise_4_svm():
    """练习4：SVM 支持向量机"""
    # 生成线性可分数据
    np.random.seed(42)
    n = 200
    X = np.vstack([
        np.random.randn(n//2, 2) + [3, 3],
        np.random.randn(n//2, 2) + [-3, -3]
    ])
    y = np.array([0] * (n//2) + [1] * (n//2))
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    
    # 1. 线性 SVM
    svm_linear = SVC(kernel='linear', C=1.0)
    svm_linear.fit(X_train, y_train)
    acc_linear = accuracy_score(y_test, svm_linear.predict(X_test))
    assert acc_linear > 0.95
    
    # 2. RBF 核 SVM
    svm_rbf = SVC(kernel='rbf', C=1.0, gamma='scale')
    svm_rbf.fit(X_train, y_train)
    acc_rbf = accuracy_score(y_test, svm_rbf.predict(X_test))
    assert acc_rbf > 0.95
    
    # 3. 非线性数据测试
    # 环形数据
    np.random.seed(42)
    n = 200
    angles = np.random.uniform(0, 2 * np.pi, n)
    r_inner = 1 + np.random.normal(0, 0.1, n // 2)
    r_outer = 3 + np.random.normal(0, 0.1, n // 2)
    X_ring = np.vstack([
        np.column_stack([r_inner * np.cos(angles[:n//2]), r_inner * np.sin(angles[:n//2])]),
        np.column_stack([r_outer * np.cos(angles[n//2:]), r_outer * np.sin(angles[n//2:])])
    ])
    y_ring = np.array([0] * (n//2) + [1] * (n//2))
    
    X_train_r, X_test_r, y_train_r, y_test_r = train_test_split(X_ring, y_ring, test_size=0.3, random_state=42)
    
    # 线性核在环形数据上表现差
    svm_lin_ring = SVC(kernel='linear')
    svm_lin_ring.fit(X_train_r, y_train_r)
    acc_lin_ring = accuracy_score(y_test_r, svm_lin_ring.predict(X_test_r))
    
    # RBF核在环形数据上表现好
    svm_rbf_ring = SVC(kernel='rbf')
    svm_rbf_ring.fit(X_train_r, y_train_r)
    acc_rbf_ring = accuracy_score(y_test_r, svm_rbf_ring.predict(X_test_r))
    
    assert acc_rbf_ring > acc_lin_ring  # RBF应该明显更好
    assert acc_rbf_ring > 0.9
    
    # 4. 标准化的重要性
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_ring)
    X_train_s, X_test_s, y_train_s, y_test_s = train_test_split(X_scaled, y_ring, test_size=0.3, random_state=42)
    svm_scaled = SVC(kernel='rbf')
    svm_scaled.fit(X_train_s, y_train_s)
    assert accuracy_score(y_test_s, svm_scaled.predict(X_test_s)) > 0.9
    
    print(f"   线性SVM: {acc_linear:.3f} | RBF环形: {acc_rbf_ring:.3f} vs 线性环形: {acc_lin_ring:.3f}")
    print("✅ 练习4 通过：SVM 支持向量机")


def exercise_5_clustering_bayes():
    """练习5：K-Means 聚类与朴素贝叶斯"""
    # 1. K-Means 聚类
    np.random.seed(42)
    n = 300
    X = np.vstack([
        np.random.randn(n//3, 2) + [0, 0],
        np.random.randn(n//3, 2) + [5, 5],
        np.random.randn(n//3, 2) + [-5, 5]
    ])
    
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    kmeans.fit(X)
    
    # 验证聚类中心
    centers = kmeans.cluster_centers_
    assert centers.shape == (3, 2)
    
    # 聚类中心应该接近 [0,0], [5,5], [-5,5]
    sorted_centers = centers[np.argsort(centers[:, 0])]  # 按x排序
    assert abs(sorted_centers[0][0] - (-5)) < 1.0
    assert abs(sorted_centers[1][0] - 0) < 1.0
    assert abs(sorted_centers[2][0] - 5) < 1.0
    
    # Inertia 越小越好
    assert kmeans.inertia_ < 1000
    
    # 2. 朴素贝叶斯
    # 文本分类模拟
    np.random.seed(42)
    n = 200
    # 模拟特征：词频
    X_nb = np.random.randint(0, 10, (n, 5))
    y_nb = (X_nb[:, 0] + X_nb[:, 1] > 8).astype(int)  # 简单规则
    
    X_train, X_test, y_train, y_test = train_test_split(X_nb, y_nb, test_size=0.3, random_state=42)
    
    nb = GaussianNB()
    nb.fit(X_train, y_train)
    nb_acc = accuracy_score(y_test, nb.predict(X_test))
    assert nb_acc > 0.7
    
    # 3. 肘部法则选择K
    inertias = []
    for k in range(1, 8):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(X)
        inertias.append(km.inertia_)
    
    # inertia应该递减
    for i in range(len(inertias) - 1):
        assert inertias[i] > inertias[i + 1]
    
    # 4. 管道 Pipeline
    pipe = Pipeline([
        ('scaler', StandardScaler()),
        ('kmeans', KMeans(n_clusters=3, random_state=42, n_init=10))
    ])
    pipe.fit(X)
    assert hasattr(pipe, 'named_steps')
    
    print(f"   K-Means inertia: {kmeans.inertia_:.1f} | NB准确率: {nb_acc:.3f}")
    print("✅ 练习5 通过：K-Means 聚类与朴素贝叶斯")


# ============================================================
# 扩展题
# ============================================================

def ext_1_overfitting_regularization():
    """扩展1：过拟合与正则化对比"""
    np.random.seed(42)
    n = 30
    X = np.random.uniform(-3, 3, (n, 1))
    y = np.sin(X.ravel()) * 2 + np.random.normal(0, 0.5, n)  # 更少数据+更多噪声
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    
    # 1. 欠拟合：深度=1
    dt_under = DecisionTreeRegressor(max_depth=1, random_state=42)
    dt_under.fit(X_train, y_train)
    mse_under_train = mean_squared_error(y_train, dt_under.predict(X_train))
    mse_under_test = mean_squared_error(y_test, dt_under.predict(X_test))
    
    # 2. 适拟合：深度=4
    dt_good = DecisionTreeRegressor(max_depth=4, random_state=42)
    dt_good.fit(X_train, y_train)
    mse_good_train = mean_squared_error(y_train, dt_good.predict(X_train))
    mse_good_test = mean_squared_error(y_test, dt_good.predict(X_test))
    
    # 3. 过拟合：无限制深度
    dt_over = DecisionTreeRegressor(random_state=42)  # 无max_depth
    dt_over.fit(X_train, y_train)
    mse_over_train = mean_squared_error(y_train, dt_over.predict(X_train))
    mse_over_test = mean_squared_error(y_test, dt_over.predict(X_test))
    
    # 验证过拟合特征：训练误差极低但测试误差高
    assert mse_over_train < 0.01  # 几乎完美拟合训练集
    assert mse_over_test > mse_good_test  # 测试集不如适拟合
    
    # 4. 正则化：限制深度 + min_samples_leaf
    dt_reg = DecisionTreeRegressor(max_depth=4, min_samples_leaf=5, random_state=42)
    dt_reg.fit(X_train, y_train)
    mse_reg_test = mean_squared_error(y_test, dt_reg.predict(X_test))
    
    # 5. 交叉验证选择最佳深度
    depths = range(1, 15)
    cv_scores = []
    for d in depths:
        dt = DecisionTreeRegressor(max_depth=d, random_state=42)
        scores = cross_val_score(dt, X, y, cv=5, scoring='neg_mean_squared_error')
        cv_scores.append(-scores.mean())
    
    best_depth = depths[np.argmin(cv_scores)]
    assert 2 <= best_depth <= 10  # 合理范围内
    
    print(f"   欠拟合: train={mse_under_train:.3f} test={mse_under_test:.3f}")
    print(f"   适拟合: train={mse_good_train:.3f} test={mse_good_test:.3f}")
    print(f"   过拟合: train={mse_over_train:.3f} test={mse_over_test:.3f}")
    print(f"   最佳深度(CV): {best_depth}")
    print("✅ 扩展1 通过：过拟合与正则化")


def ext_2_grid_search():
    """扩展2：网格搜索调参"""
    np.random.seed(42)
    n = 300
    X, y = make_classification_like(n)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    
    # 1. 网格搜索
    param_grid = {
        'n_estimators': [50, 100, 200],
        'max_depth': [3, 5, 7],
        'learning_rate': [0.01, 0.1, 0.2]
    }
    
    gb = GradientBoostingClassifier(random_state=42)
    grid_search = GridSearchCV(gb, param_grid, cv=3, scoring='accuracy', n_jobs=-1)
    grid_search.fit(X_train, y_train)
    
    # 2. 最佳参数
    best_params = grid_search.best_params_
    assert 'n_estimators' in best_params
    assert 'max_depth' in best_params
    assert 'learning_rate' in best_params
    
    # 3. 最佳模型性能
    best_model = grid_search.best_estimator_
    best_acc = accuracy_score(y_test, best_model.predict(X_test))
    assert best_acc > 0.6
    
    # 4. CV 分数
    cv_results = grid_search.cv_results_
    assert 'mean_test_score' in cv_results
    
    # 5. 对比默认参数
    default_gb = GradientBoostingClassifier(random_state=42)
    default_gb.fit(X_train, y_train)
    default_acc = accuracy_score(y_test, default_gb.predict(X_test))
    
    # 调参后应该不差于默认
    assert best_acc >= default_acc - 0.15  # 调参后不应大幅差于默认
    
    print(f"   最佳参数: {best_params}")
    print(f"   调参Acc: {best_acc:.3f} | 默认Acc: {default_acc:.3f}")
    print("✅ 扩展2 通过：网格搜索调参")


def ext_3_feature_engineering():
    """扩展3：特征工程实战"""
    np.random.seed(42)
    n = 500
    
    # 原始特征
    area = np.random.uniform(50, 200, n)
    age = np.random.randint(0, 30, n)
    floor = np.random.randint(1, 30, n)
    rooms = np.random.randint(1, 5, n)
    
    # 房价 = f(面积, 房间数, 房龄, 楼层, 交互项)
    price = (area * 3 + rooms * 15 - age * 2 + floor * 0.5 + 
             area * rooms * 0.1 +  # 交互项
             np.random.normal(0, 20, n))
    
    X_raw = np.column_stack([area, age, floor, rooms])
    X_train, X_test, y_train, y_test = train_test_split(X_raw, price, test_size=0.3, random_state=42)
    
    # 1. 原始特征
    model_raw = LinearRegression()
    model_raw.fit(X_train, y_train)
    r2_raw = r2_score(y_test, model_raw.predict(X_test))
    
    # 2. 标准化
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    model_scaled = LinearRegression()
    model_scaled.fit(X_train_s, y_train)
    r2_scaled = r2_score(y_test, model_scaled.predict(X_test_s))
    
    # 3. 多项式特征（含交互项）
    poly = PolynomialFeatures(degree=2, interaction_only=False, include_bias=False)
    X_train_p = poly.fit_transform(X_train)
    X_test_p = poly.transform(X_test)
    model_poly = LinearRegression()
    model_poly.fit(X_train_p, y_train)
    r2_poly = r2_score(y_test, model_poly.predict(X_test_p))
    
    # 4. 特征组合应该提升性能
    assert r2_poly > r2_raw  # 多项式特征更好
    
    # 5. Pipeline 组合
    pipe = Pipeline([
        ('poly', PolynomialFeatures(degree=2, include_bias=False)),
        ('scaler', StandardScaler()),
        ('reg', LinearRegression())
    ])
    pipe.fit(X_train, y_train)
    r2_pipe = r2_score(y_test, pipe.predict(X_test))
    assert r2_pipe > 0.9
    
    print(f"   原始R²: {r2_raw:.4f} | 标准化R²: {r2_scaled:.4f} | 多项式R²: {r2_poly:.4f}")
    print("✅ 扩展3 通过：特征工程")


def ext_4_model_comparison():
    """扩展4：多模型对比评估"""
    np.random.seed(42)
    n = 400
    X, y = make_classification_like(n, n_features=10, n_informative=5)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    
    models = {
        'Logistic': LogisticRegression(max_iter=1000),
        'DT': DecisionTreeClassifier(max_depth=5, random_state=42),
        'RF': RandomForestClassifier(n_estimators=100, random_state=42),
        'GBDT': GradientBoostingClassifier(n_estimators=100, random_state=42),
        'SVM': SVC(kernel='rbf', random_state=42),
        'NB': GaussianNB()
    }
    
    results = {}
    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average='weighted')
        cv = cross_val_score(model, X, y, cv=5).mean()
        results[name] = {'acc': acc, 'f1': f1, 'cv': cv}
    
    # 1. 所有模型都应该比随机猜测好
    for name, r in results.items():
        assert r['acc'] > 0.6, f"{name} acc={r['acc']:.3f} 应该 > 0.6"
    
    # 2. 集成方法通常表现好
    assert results['RF']['acc'] > 0.7
    assert results['GBDT']['acc'] > 0.7
    
    # 3. 打印对比表
    print(f"   {'模型':<10} {'Acc':<8} {'F1':<8} {'CV':<8}")
    for name, r in results.items():
        print(f"   {name:<10} {r['acc']:<8.3f} {r['f1']:<8.3f} {r['cv']:<8.3f}")
    
    print("✅ 扩展4 通过：多模型对比评估")


def ext_5_from_scratch():
    """扩展5：从零实现逻辑回归 - 理解算法本质"""
    np.random.seed(42)
    n = 200
    X = np.random.randn(n, 2)
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    
    # 添加偏置项
    X_b = np.column_stack([np.ones(n), X])
    
    # 1. Sigmoid 函数
    def sigmoid(z):
        return 1 / (1 + np.exp(-np.clip(z, -250, 250)))
    
    # 2. 损失函数（交叉熵）
    def compute_loss(X, y, w):
        m = len(y)
        h = sigmoid(X @ w)
        loss = -np.mean(y * np.log(h + 1e-10) + (1 - y) * np.log(1 - h + 1e-10))
        return loss
    
    # 3. 梯度下降
    w = np.zeros(X_b.shape[1])
    lr = 0.1
    n_iter = 1000
    losses = []
    
    for i in range(n_iter):
        h = sigmoid(X_b @ w)
        gradient = X_b.T @ (h - y) / len(y)
        w -= lr * gradient
        losses.append(compute_loss(X_b, y, w))
    
    # 4. 损失应该递减
    assert losses[-1] < losses[0]
    assert losses[-1] < 0.5  # 最终损失应该较低
    
    # 5. 预测
    y_pred_proba = sigmoid(X_b @ w)
    y_pred = (y_pred_proba >= 0.5).astype(int)
    acc = accuracy_score(y, y_pred)
    assert acc > 0.9
    
    # 6. 与 sklearn 对比
    sklearn_lr = LogisticRegression()
    sklearn_lr.fit(X, y)
    sklearn_acc = accuracy_score(y, sklearn_lr.predict(X))
    
    assert abs(acc - sklearn_acc) < 0.05  # 性能应该接近
    
    print(f"   手写LR Acc: {acc:.3f} | sklearn LR Acc: {sklearn_acc:.3f}")
    print(f"   权重: {w} (bias, w1, w2)")
    print("✅ 扩展5 通过：从零实现逻辑回归")


def make_classification_like(n_samples=200, n_features=4, n_informative=3):
    """生成分类数据"""
    np.random.seed(42)
    X = np.random.randn(n_samples, n_features)
    # 用前 n_informative 个特征决定标签
    weights = np.random.randn(n_informative)
    logits = X[:, :n_informative] @ weights
    y = (logits + np.random.normal(0, 0.3, n_samples) > 0).astype(int)
    return X, y


# ============================================================
# 主函数
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("机器学习基础练习")
    print("=" * 60)
    exercise_1_linear_regression()
    exercise_2_logistic_regression()
    exercise_3_decision_tree()
    exercise_4_svm()
    exercise_5_clustering_bayes()
    
    print("\n" + "=" * 60)
    print("机器学习扩展题")
    print("=" * 60)
    ext_1_overfitting_regularization()
    ext_2_grid_search()
    ext_3_feature_engineering()
    ext_4_model_comparison()
    ext_5_from_scratch()
    
    print("\n" + "=" * 60)
    print("全部通过！机器学习基础 + 扩展 10/10 ✅")
    print("=" * 60)
