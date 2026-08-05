"""
Matplotlib + Seaborn 可视化练习 + 扩展题
========================================
涵盖：折线图、柱状图、散点图、直方图、箱线图、热力图、子图
注意：使用 Agg 后端，图片保存到文件而非显示
"""

import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import os

OUTPUT_DIR = '/app/data/所有对话/主对话/python_exercises/charts'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# 基础练习
# ============================================================

def exercise_1_line_plot():
    """练习1：折线图 - 股价走势"""
    fig, ax = plt.subplots(figsize=(10, 5))
    
    dates = pd.date_range('2025-01-01', periods=30, freq='D')
    stock_a = 100 + np.cumsum(np.random.randn(30) * 2)
    stock_b = 100 + np.cumsum(np.random.randn(30) * 2)
    
    ax.plot(dates, stock_a, label='股票A', color='blue', linewidth=2)
    ax.plot(dates, stock_b, label='股票B', color='red', linewidth=2, linestyle='--')
    
    ax.set_title('股价走势对比', fontsize=14)
    ax.set_xlabel('日期')
    ax.set_ylabel('价格（元）')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'line_plot.png')
    plt.savefig(path, dpi=100)
    plt.close()
    assert os.path.exists(path)
    
    print("✅ 练习1 通过：折线图")


def exercise_2_bar_chart():
    """练习2：柱状图 - 部门薪资对比"""
    fig, ax = plt.subplots(figsize=(8, 5))
    
    departments = ['技术部', '销售部', '市场部', '人事部', '财务部']
    avg_salary = [15000, 12000, 11000, 9000, 13000]
    colors = ['#2196F3', '#4CAF50', '#FF9800', '#9C27B0', '#F44336']
    
    bars = ax.bar(departments, avg_salary, color=colors, edgecolor='black', linewidth=0.5)
    
    # 在柱子上方显示数值
    for bar, val in zip(bars, avg_salary):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 200,
                f'{val:,}', ha='center', va='bottom', fontsize=10)
    
    ax.set_title('各部门平均薪资', fontsize=14)
    ax.set_ylabel('薪资（元）')
    ax.set_ylim(0, max(avg_salary) * 1.2)
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'bar_chart.png')
    plt.savefig(path, dpi=100)
    plt.close()
    assert os.path.exists(path)
    
    print("✅ 练习2 通过：柱状图")


def exercise_3_scatter_plot():
    """练习3：散点图 - 身高体重关系"""
    np.random.seed(42)
    n = 100
    height = np.random.normal(170, 8, n)
    weight = height * 0.6 + np.random.normal(0, 5, n) - 20
    gender = np.random.choice(['男', '女'], n)
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    for g, color in [('男', 'blue'), ('女', 'red')]:
        mask = np.array(gender) == g
        ax.scatter(height[mask], weight[mask], c=color, label=g, alpha=0.6, edgecolors='black')
    
    ax.set_title('身高与体重关系', fontsize=14)
    ax.set_xlabel('身高（cm）')
    ax.set_ylabel('体重（kg）')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'scatter_plot.png')
    plt.savefig(path, dpi=100)
    plt.close()
    assert os.path.exists(path)
    
    print("✅ 练习3 通过：散点图")


def exercise_4_histogram_boxplot():
    """练习4：直方图与箱线图 - 成绩分布"""
    np.random.seed(42)
    scores_class_a = np.random.normal(80, 10, 50)
    scores_class_b = np.random.normal(75, 15, 50)
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # 直方图
    axes[0].hist(scores_class_a, bins=15, alpha=0.6, label='A班', color='blue', edgecolor='black')
    axes[0].hist(scores_class_b, bins=15, alpha=0.6, label='B班', color='orange', edgecolor='black')
    axes[0].set_title('成绩分布直方图')
    axes[0].set_xlabel('分数')
    axes[0].set_ylabel('人数')
    axes[0].legend()
    
    # 箱线图
    bp = axes[1].boxplot([scores_class_a, scores_class_b], labels=['A班', 'B班'],
                         patch_artist=True, widths=0.5)
    bp['boxes'][0].set_facecolor('lightblue')
    bp['boxes'][1].set_facecolor('lightyellow')
    axes[1].set_title('成绩箱线图')
    axes[1].set_ylabel('分数')
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'hist_boxplot.png')
    plt.savefig(path, dpi=100)
    plt.close()
    assert os.path.exists(path)
    
    print("✅ 练习4 通过：直方图与箱线图")


def exercise_5_subplots():
    """练习5：子图布局 - 多图组合"""
    np.random.seed(42)
    x = np.linspace(0, 10, 100)
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # 左上：正弦余弦
    axes[0, 0].plot(x, np.sin(x), label='sin', color='blue')
    axes[0, 0].plot(x, np.cos(x), label='cos', color='red')
    axes[0, 0].set_title('三角函数')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # 右上：指数衰减
    axes[0, 1].plot(x, np.exp(-x/2), color='green', linewidth=2)
    axes[0, 1].set_title('指数衰减')
    axes[0, 1].set_yscale('log')
    axes[0, 1].grid(True, alpha=0.3)
    
    # 左下：柱状图
    categories = ['A', 'B', 'C', 'D', 'E']
    values = np.random.randint(10, 50, 5)
    axes[1, 0].bar(categories, values, color='purple', alpha=0.7)
    axes[1, 0].set_title('随机柱状图')
    
    # 右下：散点图
    axes[1, 1].scatter(np.random.randn(50), np.random.randn(50), 
                        c=np.random.randn(50), cmap='viridis', alpha=0.6)
    axes[1, 1].set_title('随机散点图')
    
    plt.suptitle('多图组合展示', fontsize=16, y=1.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'subplots.png')
    plt.savefig(path, dpi=100)
    plt.close()
    assert os.path.exists(path)
    
    print("✅ 练习5 通过：子图布局")


# ============================================================
# 扩展题
# ============================================================

def ext_1_heatmap_corr():
    """扩展1：热力图 - 相关性矩阵"""
    # 生成房价相关数据
    np.random.seed(42)
    n = 200
    area = np.random.normal(100, 30, n)
    rooms = np.random.randint(1, 6, n)
    age = np.random.randint(0, 30, n)
    floor = np.random.randint(1, 30, n)
    # 房价与面积、房间数正相关，与房龄负相关
    price = area * 3 + rooms * 20 - age * 5 + np.random.normal(0, 50, n)
    
    df = pd.DataFrame({'面积': area, '房间数': rooms, '房龄': age, '楼层': floor, '价格': price})
    
    # 计算相关系数矩阵
    corr = df.corr()
    
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', 
                center=0, square=True, ax=ax, linewidths=0.5)
    ax.set_title('房价特征相关性热力图', fontsize=14)
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'heatmap_corr.png')
    plt.savefig(path, dpi=100)
    plt.close()
    assert os.path.exists(path)
    
    # 验证面积与价格正相关
    assert corr.loc['面积', '价格'] > 0.5
    
    print(f"   面积-价格相关系数: {corr.loc['面积', '价格']:.3f}")
    print("✅ 扩展1 通过：相关性热力图")


def ext_2_pairplot_regression():
    """扩展2：Seaborn pairplot + 回归图"""
    # 生成 Iris 风格数据
    np.random.seed(42)
    n = 60
    species = np.repeat(['setosa', 'versicolor', 'virginica'], n // 3)
    
    data = {
        'species': species,
        'sepal_length': np.concatenate([
            np.random.normal(5.0, 0.3, n // 3),
            np.random.normal(5.9, 0.3, n // 3),
            np.random.normal(6.5, 0.3, n // 3)
        ]),
        'sepal_width': np.concatenate([
            np.random.normal(3.5, 0.2, n // 3),
            np.random.normal(2.8, 0.2, n // 3),
            np.random.normal(3.0, 0.2, n // 3)
        ]),
        'petal_length': np.concatenate([
            np.random.normal(1.4, 0.1, n // 3),
            np.random.normal(4.3, 0.2, n // 3),
            np.random.normal(5.5, 0.3, n // 3)
        ])
    }
    df = pd.DataFrame(data)
    
    # 回归图
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.regplot(data=df, x='sepal_length', y='petal_length', 
                scatter_kws={'alpha': 0.5}, line_kws={'color': 'red'}, ax=ax)
    ax.set_title('花萼长度 vs 花瓣长度 回归分析', fontsize=14)
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'regression_plot.png')
    plt.savefig(path, dpi=100)
    plt.close()
    assert os.path.exists(path)
    
    # 验证正相关
    corr = df['sepal_length'].corr(df['petal_length'])
    assert corr > 0.7
    
    print(f"   相关系数: {corr:.3f}")
    print("✅ 扩展2 通过：回归分析图")


def ext_3_facetgrid():
    """扩展3：Seaborn FacetGrid 分面图"""
    np.random.seed(42)
    n = 120
    df = pd.DataFrame({
        '月份': np.tile(np.arange(1, 13), 10),
        '销售额': np.random.normal(50, 15, n).cumsum() / 10 + np.arange(n) * 0.5,
        '地区': np.repeat(np.random.choice(['华北', '华东', '华南'], 10), 12),
        '产品': np.repeat(np.random.choice(['手机', '电脑'], 10), 12)
    })
    
    # 分面图
    g = sns.FacetGrid(df, col='地区', row='产品', height=3, aspect=1.5)
    g.map_dataframe(sns.lineplot, x='月份', y='销售额', marker='o')
    g.set_titles('{col_name} | {row_name}')
    g.set_axis_labels('月份', '销售额（万元）')
    
    path = os.path.join(OUTPUT_DIR, 'facetgrid.png')
    g.savefig(path, dpi=100)
    plt.close()
    assert os.path.exists(path)
    
    print("✅ 扩展3 通过：分面图")


def ext_4_custom_style():
    """扩展4：自定义样式与双Y轴"""
    np.random.seed(42)
    months = np.arange(1, 13)
    revenue = [120, 135, 150, 165, 180, 200, 220, 210, 195, 175, 160, 190]
    growth_rate = [0, 12.5, 11.1, 10.0, 9.1, 11.1, 10.0, -4.5, -7.1, -10.3, -8.6, 18.8]
    
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    # 左Y轴：柱状图（营收）
    color1 = '#2196F3'
    bars = ax1.bar(months, revenue, color=color1, alpha=0.7, label='营收（万元）')
    ax1.set_xlabel('月份')
    ax1.set_ylabel('营收（万元）', color=color1)
    ax1.tick_params(axis='y', labelcolor=color1)
    
    # 右Y轴：折线图（增长率）
    ax2 = ax1.twinx()
    color2 = '#F44336'
    ax2.plot(months, growth_rate, color=color2, marker='o', linewidth=2, label='增长率（%）')
    ax2.set_ylabel('增长率（%）', color=color2)
    ax2.tick_params(axis='y', labelcolor=color2)
    ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    
    # 合并图例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    ax1.set_title('月度营收与增长率双Y轴图', fontsize=14)
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'dual_axis.png')
    plt.savefig(path, dpi=100)
    plt.close()
    assert os.path.exists(path)
    
    print("✅ 扩展4 通过：双Y轴自定义样式")


def ext_5_dashboard():
    """扩展5：数据看板 - 综合可视化"""
    np.random.seed(42)
    
    fig = plt.figure(figsize=(16, 10))
    
    # 生成数据
    n = 365
    dates = pd.date_range('2025-01-01', periods=n, freq='D')
    visitors = np.random.poisson(1000, n) + np.sin(np.arange(n) * 2 * np.pi / 365) * 200 + np.arange(n) * 0.5
    revenue = visitors * np.random.uniform(0.5, 1.5, n)
    channels = np.random.choice(['搜索', '直接', '社交', '广告', '推荐'], n)
    
    df = pd.DataFrame({'日期': dates, '访客数': visitors, '营收': revenue, '渠道': channels})
    
    # 1. 左上：日访客趋势（折线+滚动均值）
    ax1 = fig.add_subplot(2, 3, 1)
    df['MA7'] = df['访客数'].rolling(7).mean()
    ax1.plot(df['日期'], df['访客数'], alpha=0.3, color='blue', label='日访客')
    ax1.plot(df['日期'], df['MA7'], color='red', linewidth=2, label='7日均值')
    ax1.set_title('访客趋势')
    ax1.legend(fontsize=8)
    
    # 2. 中上：渠道分布（饼图）
    ax2 = fig.add_subplot(2, 3, 2)
    channel_count = df['渠道'].value_counts()
    ax2.pie(channel_count, labels=channel_count.index, autopct='%1.1f%%', startangle=90)
    ax2.set_title('渠道分布')
    
    # 3. 右上：营收分布（直方图）
    ax3 = fig.add_subplot(2, 3, 3)
    ax3.hist(df['营收'], bins=30, color='green', alpha=0.7, edgecolor='black')
    ax3.set_title('营收分布')
    ax3.axvline(df['营收'].mean(), color='red', linestyle='--', label=f'均值: {df["营收"].mean():.0f}')
    ax3.legend(fontsize=8)
    
    # 4. 左下：月度汇总（柱状图）
    ax4 = fig.add_subplot(2, 3, 4)
    monthly = df.set_index('日期')['营收'].resample('ME').sum()
    ax4.bar(range(len(monthly)), monthly.values, color='orange', alpha=0.8)
    ax4.set_title('月度营收汇总')
    ax4.set_xticks(range(len(monthly)))
    ax4.set_xticklabels([f'{i+1}月' for i in range(len(monthly))], rotation=45, fontsize=8)
    
    # 5. 中下：渠道×月份热力图
    ax5 = fig.add_subplot(2, 3, 5)
    df['月份'] = df['日期'].dt.month
    pivot = df.pivot_table(values='访客数', index='渠道', columns='月份', aggfunc='sum')
    sns.heatmap(pivot, cmap='YlOrRd', ax=ax5, fmt='.0f')
    ax5.set_title('渠道×月份热力图')
    
    # 6. 右下：关键指标
    ax6 = fig.add_subplot(2, 3, 6)
    ax6.axis('off')
    metrics = [
        f"总访客: {df['访客数'].sum():,.0f}",
        f"总营收: ¥{df['营收'].sum():,.0f}",
        f"日均访客: {df['访客数'].mean():.0f}",
        f"日均营收: ¥{df['营收'].mean():.0f}",
        f"最高单日: {df['访客数'].max():,.0f}",
        f"转化效率: ¥{df['营收'].sum()/df['访客数'].sum():.2f}/人"
    ]
    for i, m in enumerate(metrics):
        ax6.text(0.1, 0.8 - i * 0.13, m, fontsize=12, transform=ax6.transAxes,
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    ax6.set_title('关键指标', fontsize=12)
    
    plt.suptitle('2025年度运营数据看板', fontsize=16, y=1.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'dashboard.png')
    plt.savefig(path, dpi=100, bbox_inches='tight')
    plt.close()
    assert os.path.exists(path)
    
    print(f"   总访客: {df['访客数'].sum():,.0f} | 总营收: ¥{df['营收'].sum():,.0f}")
    print("✅ 扩展5 通过：综合数据看板")


# ============================================================
# 主函数
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Matplotlib + Seaborn 基础练习")
    print("=" * 60)
    exercise_1_line_plot()
    exercise_2_bar_chart()
    exercise_3_scatter_plot()
    exercise_4_histogram_boxplot()
    exercise_5_subplots()
    
    print("\n" + "=" * 60)
    print("Matplotlib + Seaborn 扩展题")
    print("=" * 60)
    ext_1_heatmap_corr()
    ext_2_pairplot_regression()
    ext_3_facetgrid()
    ext_4_custom_style()
    ext_5_dashboard()
    
    print("\n" + "=" * 60)
    print("全部通过！可视化 基础 + 扩展 10/10 ✅")
    print(f"图表保存目录: {OUTPUT_DIR}")
    print("=" * 60)
