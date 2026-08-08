"""A/B 测试框架 — 统计显著性检验的实验对比.

核心组件::

    ┌──────────────────────────────────────────────────────┐
    │  ABTest       — A/B 测试实验（配置+运行+收集数据）       │
    │  ABTestResult — 实验结果统计分析（均值/置信区间/p值）     │
    │  StatisticalSignificance — 统计显著性检验工具           │
    └──────────────────────────────────────────────────────┘

统计方法（纯 numpy 实现）：
- **Welch's t-test**: 不假设等方差的 t 检验，适合样本量不等的 A/B 测试.
- **Mann-Whitney U 检验**: 非参数检验，不要求正态分布假设.
- **Bootstrap 置信区间**: 通过重采样估计置信区间，适用于任意分布.
- **效应量 (Cohen's d)**: 衡量差异的实际意义，而不仅仅是统计显著性.

Usage::

    test = ABTest(
        name="prompt_v2_vs_v1",
        variant_a_name="v1_baseline",
        variant_b_name="v2_optimized",
    )

    # 添加实验数据
    test.add_result_a(0.85)
    test.add_result_a(0.90)
    test.add_result_b(0.92)
    test.add_result_b(0.95)

    # 分析结果
    result = test.analyze()
    print(result.summary())
    print(result.is_significant())  # True/False
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


# ═══════════════════════════════════════════════════════════════
#  Statistical Significance Tests (pure numpy)
# ═══════════════════════════════════════════════════════════════


class StatisticalSignificance:
    """统计显著性检验工具集（纯 numpy 实现）.

    所有方法接受两组样本数据，返回检验统计量和 p 值.
    """

    @staticmethod
    def welch_t_test(
        a: Sequence[float], b: Sequence[float]
    ) -> Tuple[float, float]:
        """Welch's t-test（不假设等方差）.

        Args:
            a: 样本 A.
            b: 样本 B.

        Returns:
            (t_statistic, p_value) 元组.
            p_value < 0.05 通常表示差异显著.
        """
        a_arr = np.array(a, dtype=float)
        b_arr = np.array(b, dtype=float)
        n_a, n_b = len(a_arr), len(b_arr)

        if n_a < 2 or n_b < 2:
            return 0.0, 1.0

        mean_a, mean_b = np.mean(a_arr), np.mean(b_arr)
        var_a, var_b = np.var(a_arr, ddof=1), np.var(b_arr, ddof=1)

        # Welch's t 统计量
        se = np.sqrt(var_a / n_a + var_b / n_b)
        if se == 0:
            return 0.0, 1.0
        t_stat = (mean_b - mean_a) / se

        # Welch-Satterthwaite 自由度
        num = (var_a / n_a + var_b / n_b) ** 2
        denom = (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
        if denom == 0:
            df = n_a + n_b - 2
        else:
            df = num / denom

        # 双侧 p 值（使用正态近似，当 df 足够大时 t 分布接近正态）
        # 对于小样本，使用修正的近似
        p_value = 2.0 * (1.0 - _t_cdf_approx(abs(t_stat), df))

        return round(float(t_stat), 6), round(float(p_value), 6)

    @staticmethod
    def mann_whitney_u(
        a: Sequence[float], b: Sequence[float]
    ) -> Tuple[float, float]:
        """Mann-Whitney U 检验（非参数）.

        Args:
            a: 样本 A.
            b: 样本 B.

        Returns:
            (u_statistic, p_value) 元组.
        """
        a_arr = np.array(a, dtype=float)
        b_arr = np.array(b, dtype=float)
        n_a, n_b = len(a_arr), len(b_arr)

        if n_a == 0 or n_b == 0:
            return 0.0, 1.0

        # 合并并排序
        combined = np.concatenate([a_arr, b_arr])
        ranks = _rank_data(combined)

        rank_sum_a = np.sum(ranks[:n_a])
        rank_sum_b = np.sum(ranks[n_a:])

        u_a = rank_sum_a - n_a * (n_a + 1) / 2
        u_b = rank_sum_b - n_b * (n_b + 1) / 2
        u_stat = min(u_a, u_b)

        # 正态近似 p 值（当样本量 > 10 时适用）
        mean_u = n_a * n_b / 2
        std_u = np.sqrt(n_a * n_b * (n_a + n_b + 1) / 12)

        if std_u == 0:
            return float(u_stat), 1.0

        z = (u_stat - mean_u) / std_u
        # 双侧 p 值
        p_value = 2.0 * (1.0 - _normal_cdf(abs(z)))

        return round(float(u_stat), 6), round(float(p_value), 6)

    @staticmethod
    def bootstrap_ci(
        data: Sequence[float],
        n_bootstrap: int = 10000,
        confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """Bootstrap 置信区间.

        通过重采样估计均值的置信区间.

        Args:
            data: 原始数据.
            n_bootstrap: 重采样次数.
            confidence: 置信水平（0.0–1.0）.

        Returns:
            (lower, upper) 置信区间.
        """
        arr = np.array(data, dtype=float)
        n = len(arr)
        if n == 0:
            return 0.0, 0.0

        rng = np.random.default_rng(42)  # 固定种子保证可复现
        bootstrap_means = np.array([
            np.mean(rng.choice(arr, size=n, replace=True))
            for _ in range(n_bootstrap)
        ])

        alpha = 1.0 - confidence
        lower = float(np.percentile(bootstrap_means, alpha / 2 * 100))
        upper = float(np.percentile(bootstrap_means, (1 - alpha / 2) * 100))

        return round(lower, 6), round(upper, 6)

    @staticmethod
    def cohens_d(
        a: Sequence[float], b: Sequence[float]
    ) -> float:
        """Cohen's d 效应量.

        衡量两组均值差异相对于合并标准差的大小.

        解释：
        - |d| < 0.2: 微小效应
        - 0.2 ≤ |d| < 0.5: 小效应
        - 0.5 ≤ |d| < 0.8: 中等效应
        - |d| ≥ 0.8: 大效应

        Returns:
            Cohen's d 值（正数表示 B 优于 A）.
        """
        a_arr = np.array(a, dtype=float)
        b_arr = np.array(b, dtype=float)

        if len(a_arr) < 2 or len(b_arr) < 2:
            return 0.0

        mean_a, mean_b = np.mean(a_arr), np.mean(b_arr)
        var_a, var_b = np.var(a_arr, ddof=1), np.var(b_arr, ddof=1)
        n_a, n_b = len(a_arr), len(b_arr)

        # 合并标准差
        pooled_std = np.sqrt(
            ((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2)
        )

        if pooled_std == 0:
            # 方差为零但均值不同 → 效应量为无穷大（返回大数表示极大效应）
            if mean_a != mean_b:
                return 10.0 if mean_b > mean_a else -10.0
            return 0.0

        d = (mean_b - mean_a) / pooled_std
        return round(float(d), 6)

    @staticmethod
    def power_analysis(
        effect_size: float,
        n_per_group: int,
        alpha: float = 0.05,
    ) -> float:
        """统计功效分析（近似）.

        估算在给定效应量和样本量下，检测到真实效应的概率.

        Args:
            effect_size: Cohen's d 效应量.
            n_per_group: 每组样本量.
            alpha: 显著性水平.

        Returns:
            统计功效 (0.0–1.0).
        """
        if effect_size == 0 or n_per_group == 0:
            return 0.0

        # 非中心 t 分布的近似功效计算
        # 使用正态近似
        z_alpha = _inverse_normal_cdf(1 - alpha / 2)
        noncentrality = effect_size * np.sqrt(n_per_group / 2)
        power = 1.0 - _normal_cdf(z_alpha - noncentrality)

        return round(float(power), 6)


# ═══════════════════════════════════════════════════════════════
#  Helper Functions for Statistical Distributions
# ═══════════════════════════════════════════════════════════════


def _normal_cdf(x: float) -> float:
    """标准正态分布的累积分布函数（使用 erf 近似）."""
    # 使用 Abramowitz and Stegun 近似
    return 0.5 * (1.0 + _erf_approx(x / np.sqrt(2)))


def _erf_approx(x: float) -> float:
    """误差函数的近似计算 (Abramowitz and Stegun 7.1.26)."""
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1.0 if x >= 0 else -1.0
    x = abs(x)

    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * np.exp(-x * x)

    return sign * y


def _inverse_normal_cdf(p: float) -> float:
    """标准正态分布的反累积分布函数（Beasley-Springer-Moro 近似）."""
    if p <= 0:
        return -10.0
    if p >= 1:
        return 10.0
    if p < 0.5:
        return -_inverse_normal_cdf(1 - p)

    # Beasley-Springer-Moro 算法
    a = [
        -3.969683028665376e+01,
        2.209460984245205e+02,
        -2.759285104469687e+02,
        1.383577518672690e+02,
        -3.066479806614716e+01,
        2.506628277459239e+00,
    ]
    b = [
        -5.447609879822406e+01,
        1.615858368580409e+02,
        -1.556989798598866e+02,
        6.680131188771972e+01,
        -1.328068155288572e+01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e+00,
        -2.549732539343734e+00,
        4.374664141464968e+00,
        2.938163982698783e+00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e+00,
        3.754408661907416e+00,
    ]

    p_low = 0.02425
    p_high = 1 - p_low

    if p < p_low:
        q = np.sqrt(-2 * np.log(p))
        x_val = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        x_val = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
                (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    else:
        q = np.sqrt(-2 * np.log(1 - p))
        x_val = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                 ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)

    return float(x_val)


def _t_cdf_approx(t: float, df: float) -> float:
    """t 分布 CDF 的近似计算.

    使用正态分布近似 + Cornish-Fisher 展开修正.
    对于大 df, t 分布趋近于正态分布.
    """
    if df > 200:
        return _normal_cdf(t)

    # 使用 Cornish-Fisher 展开将 t 分位数转换为正态分位数
    # z ≈ t + (t^3 + t) / (4*df)  (将 t 值放大以匹配正态)
    # 但 CDF 方向相反: P(T ≤ t) ≈ Φ(z) 其中 z = t + (t^3 + t)/(4*df)
    z = t + (t ** 3 + t) / (4 * df)
    return _normal_cdf(z)


def _rank_data(data: np.ndarray) -> np.ndarray:
    """计算数据的秩（平均秩处理并列值）."""
    sorter = np.argsort(data, kind="mergesort")
    inv = np.empty(sorter.size, dtype=int)
    inv[sorter] = np.arange(sorter.size)

    arr = data[sorter]
    obs = np.r_[True, arr[1:] != arr[:-1]]
    dense = obs.cumsum()[inv]

    # 平均秩
    count = np.r_[np.nonzero(obs)[0], len(obs)]
    ranks = 0.5 * (count[dense] + count[dense - 1] + 1)
    return ranks


# ═══════════════════════════════════════════════════════════════
#  AB Test Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class ABTestResult:
    """A/B 测试结果统计分析.

    Attributes:
        test_id:          测试 ID.
        test_name:        测试名称.
        variant_a_name:   变体 A 名称.
        variant_b_name:   变体 B 名称.
        results_a:        变体 A 的原始数据.
        results_b:        变体 B 的原始数据.
        mean_a:           变体 A 均值.
        mean_b:           变体 B 均值.
        std_a:            变体 A 标准差.
        std_b:            变体 B 标准差.
        delta:            均值差异 (B - A).
        relative_improvement:  相对提升率 ((B - A) / A).
        t_statistic:      Welch's t 统计量.
        p_value:          双侧 p 值.
        cohens_d:         Cohen's d 效应量.
        ci_a:             变体 A 的 95% Bootstrap 置信区间.
        ci_b:             变体 B 的 95% Bootstrap 置信区间.
        ci_delta:         差异的 95% 置信区间.
        power:            统计功效.
        is_significant_flag: 是否统计显著 (p < alpha).
        alpha:            显著性水平.
        timestamp:        分析时间戳.
        recommendation:   基于分析的建议.
    """

    test_id: str = ""
    test_name: str = ""
    variant_a_name: str = "A"
    variant_b_name: str = "B"
    results_a: List[float] = field(default_factory=list)
    results_b: List[float] = field(default_factory=list)
    mean_a: float = 0.0
    mean_b: float = 0.0
    std_a: float = 0.0
    std_b: float = 0.0
    delta: float = 0.0
    relative_improvement: float = 0.0
    t_statistic: float = 0.0
    p_value: float = 1.0
    cohens_d: float = 0.0
    ci_a: Tuple[float, float] = (0.0, 0.0)
    ci_b: Tuple[float, float] = (0.0, 0.0)
    ci_delta: Tuple[float, float] = (0.0, 0.0)
    power: float = 0.0
    is_significant_flag: bool = False
    alpha: float = 0.05
    timestamp: float = 0.0
    recommendation: str = ""

    def __post_init__(self):
        if not self.test_id:
            self.test_id = f"abtest_{uuid.uuid4().hex[:12]}"
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def is_significant(self) -> bool:
        """是否统计显著."""
        return self.is_significant_flag

    def effect_size_label(self) -> str:
        """效应量的定性描述."""
        d = abs(self.cohens_d)
        if d < 0.2:
            return "negligible"
        elif d < 0.5:
            return "small"
        elif d < 0.8:
            return "medium"
        else:
            return "large"

    def summary(self) -> str:
        """人类可读的摘要."""
        lines = [
            f"A/B Test: {self.test_name}",
            f"  Variant A ({self.variant_a_name}): mean={self.mean_a:.4f}, "
            f"std={self.std_a:.4f}, n={len(self.results_a)}",
            f"  Variant B ({self.variant_b_name}): mean={self.mean_b:.4f}, "
            f"std={self.std_b:.4f}, n={len(self.results_b)}",
            f"  Delta: {self.delta:+.4f} ({self.relative_improvement:+.2%})",
            f"  Welch's t = {self.t_statistic:.4f}, p = {self.p_value:.4f}",
            f"  Cohen's d = {self.cohens_d:.4f} ({self.effect_size_label()})",
            f"  Power = {self.power:.4f}",
            f"  Significant (α={self.alpha}): {'Yes' if self.is_significant_flag else 'No'}",
            f"  Recommendation: {self.recommendation}",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "test_name": self.test_name,
            "variant_a_name": self.variant_a_name,
            "variant_b_name": self.variant_b_name,
            "mean_a": self.mean_a,
            "mean_b": self.mean_b,
            "std_a": self.std_a,
            "std_b": self.std_b,
            "delta": self.delta,
            "relative_improvement": self.relative_improvement,
            "t_statistic": self.t_statistic,
            "p_value": self.p_value,
            "cohens_d": self.cohens_d,
            "ci_a": list(self.ci_a),
            "ci_b": list(self.ci_b),
            "ci_delta": list(self.ci_delta),
            "power": self.power,
            "is_significant": self.is_significant_flag,
            "alpha": self.alpha,
            "sample_size_a": len(self.results_a),
            "sample_size_b": len(self.results_b),
            "timestamp": self.timestamp,
            "recommendation": self.recommendation,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ═══════════════════════════════════════════════════════════════
#  AB Test
# ═══════════════════════════════════════════════════════════════


class ABTest:
    """A/B 测试实验.

    收集两个变体的数据，进行统计显著性检验.

    Usage::

        test = ABTest(
            name="prompt_v2_vs_v1",
            variant_a_name="v1_baseline",
            variant_b_name="v2_optimized",
            alpha=0.05,
        )

        # 添加数据
        test.add_result_a(0.85)
        test.add_results_a([0.90, 0.88, 0.87])
        test.add_results_b([0.92, 0.95, 0.93])

        # 分析
        result = test.analyze()
        print(result.is_significant())
        print(result.summary())
    """

    def __init__(
        self,
        name: str = "ab_test",
        variant_a_name: str = "A",
        variant_b_name: str = "B",
        alpha: float = 0.05,
        description: str = "",
    ):
        """
        Args:
            name: 测试名称.
            variant_a_name: 变体 A 名称（基线）.
            variant_b_name: 变体 B 名称（实验组）.
            alpha: 显著性水平（默认 0.05）.
            description: 测试描述.
        """
        self.name = name
        self.variant_a_name = variant_a_name
        self.variant_b_name = variant_b_name
        self.alpha = alpha
        self.description = description
        self._results_a: List[float] = []
        self._results_b: List[float] = []

    # ── 数据收集 ──────────────────────────────────────────

    def add_result_a(self, value: float) -> "ABTest":
        """添加变体 A 的单个结果."""
        self._results_a.append(float(value))
        return self

    def add_result_b(self, value: float) -> "ABTest":
        """添加变体 B 的单个结果."""
        self._results_b.append(float(value))
        return self

    def add_results_a(self, values: Sequence[float]) -> "ABTest":
        """批量添加变体 A 的结果."""
        self._results_a.extend(float(v) for v in values)
        return self

    def add_results_b(self, values: Sequence[float]) -> "ABTest":
        """批量添加变体 B 的结果."""
        self._results_b.extend(float(v) for v in values)
        return self

    @property
    def results_a(self) -> List[float]:
        return list(self._results_a)

    @property
    def results_b(self) -> List[float]:
        return list(self._results_b)

    @property
    def sample_size_a(self) -> int:
        return len(self._results_a)

    @property
    def sample_size_b(self) -> int:
        return len(self._results_b)

    # ── 分析 ──────────────────────────────────────────────

    def analyze(self) -> ABTestResult:
        """执行统计分析，返回 ABTestResult."""
        a = self._results_a
        b = self._results_b

        mean_a = float(np.mean(a)) if a else 0.0
        mean_b = float(np.mean(b)) if b else 0.0
        std_a = float(np.std(a, ddof=1)) if len(a) > 1 else 0.0
        std_b = float(np.std(b, ddof=1)) if len(b) > 1 else 0.0

        delta = mean_b - mean_a
        relative_improvement = (delta / mean_a) if mean_a != 0 else 0.0

        # Welch's t-test
        t_stat, p_value = StatisticalSignificance.welch_t_test(a, b)

        # Cohen's d
        d = StatisticalSignificance.cohens_d(a, b)

        # Bootstrap 置信区间
        ci_a = StatisticalSignificance.bootstrap_ci(a) if len(a) >= 2 else (mean_a, mean_a)
        ci_b = StatisticalSignificance.bootstrap_ci(b) if len(b) >= 2 else (mean_b, mean_b)

        # 差异的置信区间（近似）
        if len(a) >= 2 and len(b) >= 2:
            se_diff = np.sqrt(std_a ** 2 / len(a) + std_b ** 2 / len(b))
            z = _inverse_normal_cdf(1 - self.alpha / 2)
            ci_delta = (
                round(float(delta - z * se_diff), 6),
                round(float(delta + z * se_diff), 6),
            )
        else:
            ci_delta = (delta, delta)

        # 统计功效
        n_per_group = min(len(a), len(b))
        power = StatisticalSignificance.power_analysis(d, n_per_group, self.alpha)

        # 显著性判断
        is_sig = p_value < self.alpha and len(a) >= 2 and len(b) >= 2

        # 生成建议
        recommendation = self._generate_recommendation(
            delta, relative_improvement, p_value, d, is_sig, power
        )

        return ABTestResult(
            test_name=self.name,
            variant_a_name=self.variant_a_name,
            variant_b_name=self.variant_b_name,
            results_a=list(a),
            results_b=list(b),
            mean_a=round(mean_a, 6),
            mean_b=round(mean_b, 6),
            std_a=round(std_a, 6),
            std_b=round(std_b, 6),
            delta=round(delta, 6),
            relative_improvement=round(relative_improvement, 6),
            t_statistic=t_stat,
            p_value=p_value,
            cohens_d=d,
            ci_a=ci_a,
            ci_b=ci_b,
            ci_delta=ci_delta,
            power=round(power, 6),
            is_significant_flag=is_sig,
            alpha=self.alpha,
            recommendation=recommendation,
        )

    # ── 持久化 ────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "variant_a_name": self.variant_a_name,
            "variant_b_name": self.variant_b_name,
            "alpha": self.alpha,
            "description": self.description,
            "results_a": self._results_a,
            "results_b": self._results_b,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> "ABTest":
        test = cls(
            name=d.get("name", "ab_test"),
            variant_a_name=d.get("variant_a_name", "A"),
            variant_b_name=d.get("variant_b_name", "B"),
            alpha=d.get("alpha", 0.05),
            description=d.get("description", ""),
        )
        test._results_a = list(d.get("results_a", []))
        test._results_b = list(d.get("results_b", []))
        return test

    # ── 内部方法 ──────────────────────────────────────────

    def _generate_recommendation(
        self,
        delta: float,
        rel_improvement: float,
        p_value: float,
        cohens_d: float,
        is_significant: bool,
        power: float,
    ) -> str:
        """基于分析结果生成建议."""
        if len(self._results_a) < 2 or len(self._results_b) < 2:
            return (
                f"Insufficient data (A={len(self._results_a)}, "
                f"B={len(self._results_b)}). Need at least 2 samples per group."
            )

        if not is_significant:
            if power < 0.8:
                return (
                    f"Not significant (p={p_value:.4f}) with low power ({power:.2f}). "
                    "Consider collecting more data to increase statistical power."
                )
            return (
                f"Not significant (p={p_value:.4f}) with adequate power ({power:.2f}). "
                "No meaningful difference detected between variants."
            )

        # 显著的情况
        if delta > 0:
            effect = abs(cohens_d)
            if effect >= 0.8:
                return (
                    f"Significant improvement: Variant B is better by "
                    f"{rel_improvement:+.2%} (p={p_value:.4f}, d={cohens_d:.2f}, "
                    "large effect). Recommend adopting Variant B."
                )
            elif effect >= 0.5:
                return (
                    f"Significant improvement: Variant B is better by "
                    f"{rel_improvement:+.2%} (p={p_value:.4f}, d={cohens_d:.2f}, "
                    "medium effect). Recommend adopting Variant B."
                )
            else:
                return (
                    f"Significant but small improvement: Variant B is better by "
                    f"{rel_improvement:+.2%} (p={p_value:.4f}, d={cohens_d:.2f}). "
                    "Consider cost-benefit before adopting."
                )
        else:
            return (
                f"Significant degradation: Variant B is worse by "
                f"{rel_improvement:+.2%} (p={p_value:.4f}, d={cohens_d:.2f}). "
                "Do not adopt Variant B."
            )
