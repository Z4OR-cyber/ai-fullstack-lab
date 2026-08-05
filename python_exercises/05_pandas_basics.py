"""
Pandas 基础练习 + 扩展题
========================
涵盖：Series/DataFrame 创建、索引、筛选、分组聚合、合并、透视表
"""

import pandas as pd
import numpy as np

# ============================================================
# 基础练习
# ============================================================

def exercise_1_series_basics():
    """练习1：Series 基础"""
    # 1. 从列表创建
    s = pd.Series([10, 20, 30, 40, 50], index=['a', 'b', 'c', 'd', 'e'])
    assert s.shape == (5,)
    assert s['c'] == 30
    
    # 2. 从字典创建
    s2 = pd.Series({'苹果': 5, '香蕉': 3, '橙子': 8})
    assert s2['香蕉'] == 3
    
    # 3. 基本属性
    assert s.dtype in [np.int64, np.int32, np.intp]
    assert len(s) == 5
    assert list(s.index) == ['a', 'b', 'c', 'd', 'e']
    
    # 4. 运算
    assert (s + 5)['a'] == 15
    assert (s * 2)['c'] == 60
    assert s.sum() == 150
    assert s.mean() == 30.0
    assert s.max() == 50
    
    # 5. 布尔索引
    filtered = s[s > 25]
    assert len(filtered) == 3
    assert 'd' in filtered.index
    
    # 6. 排序
    sorted_s = s.sort_values(ascending=False)
    assert sorted_s.iloc[0] == 50
    
    # 7. 缺失值处理
    s_nan = pd.Series([1, None, 3, None, 5])
    assert s_nan.isna().sum() == 2
    filled = s_nan.fillna(0)
    assert filled.sum() == 9
    
    print("✅ 练习1 通过：Series 基础")


def exercise_2_dataframe_creation():
    """练习2：DataFrame 创建与基本操作"""
    # 1. 从字典创建
    df = pd.DataFrame({
        '姓名': ['张三', '李四', '王五', '赵六'],
        '年龄': [25, 30, 35, 28],
        '城市': ['北京', '上海', '广州', '深圳'],
        '薪资': [8000, 12000, 15000, 10000]
    })
    assert df.shape == (4, 4)
    assert list(df.columns) == ['姓名', '年龄', '城市', '薪资']
    
    # 2. 从列表创建
    data = [['Alice', 85], ['Bob', 90], ['Charlie', 78]]
    df2 = pd.DataFrame(data, columns=['name', 'score'])
    assert df2.shape == (3, 2)
    
    # 3. 基本信息查看
    assert df.dtypes['年龄'] in [np.int64, np.int32]
    assert len(df) == 4
    
    # 4. 列操作
    assert df['薪资'].mean() == 11250.0
    assert df['年龄'].max() == 35
    
    # 5. 添加列
    df['年薪'] = df['薪资'] * 12
    assert '年薪' in df.columns
    assert df.loc[0, '年薪'] == 96000
    
    # 6. 删除列
    df_dropped = df.drop('年薪', axis=1)
    assert '年薪' not in df_dropped.columns
    
    # 7. 重命名列
    df_renamed = df.rename(columns={'姓名': 'name', '年龄': 'age'})
    assert 'name' in df_renamed.columns
    assert 'age' in df_renamed.columns
    
    print("✅ 练习2 通过：DataFrame 创建与基本操作")


def exercise_3_filtering_selection():
    """练习3：数据筛选与选择"""
    df = pd.DataFrame({
        'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
        'department': ['Tech', 'Sales', 'Tech', 'HR', 'Sales'],
        'salary': [8000, 6000, 12000, 5000, 7000],
        'years': [3, 1, 5, 2, 4]
    })
    
    # 1. loc 标签索引
    row = df.loc[0]
    assert row['name'] == 'Alice'
    
    # 2. iloc 位置索引
    first_two = df.iloc[:2]
    assert len(first_two) == 2
    
    # 3. 条件筛选
    high_salary = df[df['salary'] >= 7000]
    assert len(high_salary) == 3
    
    # 4. 多条件筛选
    tech_high = df[(df['department'] == 'Tech') & (df['salary'] > 10000)]
    assert len(tech_high) == 1
    assert tech_high.iloc[0]['name'] == 'Charlie'
    
    # 5. isin 筛选
    selected = df[df['department'].isin(['Tech', 'HR'])]
    assert len(selected) == 3
    
    # 6. 选择特定列
    subset = df.loc[:, ['name', 'salary']]
    assert list(subset.columns) == ['name', 'salary']
    
    # 7. query 方法
    result = df.query('salary > 6000 and years >= 2')
    assert len(result) == 3
    
    print("✅ 练习3 通过：数据筛选与选择")


def exercise_4_groupby_aggregation():
    """练习4：分组聚合"""
    df = pd.DataFrame({
        'department': ['Tech', 'Sales', 'Tech', 'HR', 'Sales', 'Tech'],
        'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank'],
        'salary': [8000, 6000, 12000, 5000, 7000, 9000],
        'bonus': [2000, 1000, 3000, 500, 1500, 2000]
    })
    
    # 1. 基本分组
    grouped = df.groupby('department')
    assert len(grouped) == 3  # Tech, Sales, HR
    
    # 2. 聚合函数
    dept_salary = df.groupby('department')['salary'].mean()
    assert dept_salary['Tech'] == (8000 + 12000 + 9000) / 3
    
    # 3. 多列聚合
    stats = df.groupby('department').agg({
        'salary': ['mean', 'min', 'max'],
        'bonus': 'sum'
    })
    assert ('salary', 'mean') in stats.columns
    
    # 4. 自定义聚合
    def salary_range(x):
        return x.max() - x.min()
    
    ranges = df.groupby('department')['salary'].agg(salary_range)
    assert ranges['Tech'] == 12000 - 8000  # 4000
    
    # 5. transform - 保持原始形状
    df['dept_avg_salary'] = df.groupby('department')['salary'].transform('mean')
    assert len(df['dept_avg_salary']) == len(df)
    
    # 6. 多层分组
    df['level'] = ['Senior', 'Junior', 'Senior', 'Junior', 'Junior', 'Senior']
    multi = df.groupby(['department', 'level'])['salary'].mean()
    assert isinstance(multi.index, pd.MultiIndex)
    
    # 7. 排序
    top_paid = df.groupby('department')['salary'].max().sort_values(ascending=False)
    assert top_paid.iloc[0] == 12000  # Tech
    
    print("✅ 练习4 通过：分组聚合")


def exercise_5_merge_join():
    """练习5：合并与连接"""
    employees = pd.DataFrame({
        'emp_id': [1, 2, 3, 4, 5],
        'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
        'dept_id': [10, 20, 10, 30, 20]
    })
    
    departments = pd.DataFrame({
        'dept_id': [10, 20, 30, 40],
        'dept_name': ['Tech', 'Sales', 'HR', 'Finance']
    })
    
    # 1. inner merge
    merged = pd.merge(employees, departments, on='dept_id', how='inner')
    assert len(merged) == 5  # 所有员工都有对应部门
    assert 'dept_name' in merged.columns
    
    # 2. left merge
    left = pd.merge(employees, departments, on='dept_id', how='left')
    assert len(left) == 5
    
    # 3. right merge
    right = pd.merge(employees, departments, on='dept_id', how='right')
    assert len(right) == 6  # dept10×2 + dept20×2 + dept30×1 + dept40×1(无员工)
    
    # 4. outer merge
    outer = pd.merge(employees, departments, on='dept_id', how='outer')
    assert len(outer) == 6  # 5个员工 + 1个Finance部门
    
    # 5. concat 纵向拼接
    df1 = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})
    df2 = pd.DataFrame({'A': [5, 6], 'B': [7, 8]})
    concatenated = pd.concat([df1, df2], ignore_index=True)
    assert len(concatenated) == 4
    
    # 6. join on index
    left_df = pd.DataFrame({'A': [1, 2, 3]}, index=['a', 'b', 'c'])
    right_df = pd.DataFrame({'B': [4, 5, 6]}, index=['a', 'b', 'd'])
    joined = left_df.join(right_df, how='inner')
    assert len(joined) == 2  # 只有 a, b 共有
    
    print("✅ 练习5 通过：合并与连接")


# ============================================================
# 扩展题
# ============================================================

def ext_1_pivot_table():
    """扩展1：透视表与交叉表 - 销售数据分析"""
    np.random.seed(42)
    n = 100
    df = pd.DataFrame({
        '日期': pd.date_range('2025-01-01', periods=n, freq='D'),
        '产品': np.random.choice(['手机', '电脑', '平板'], n),
        '地区': np.random.choice(['华北', '华东', '华南', '西部'], n),
        '销售额': np.random.randint(1000, 10000, n),
        '数量': np.random.randint(1, 20, n)
    })
    
    # 1. 透视表：产品 × 地区的平均销售额
    pivot = pd.pivot_table(df, values='销售额', index='产品', columns='地区', aggfunc='mean')
    assert pivot.shape == (3, 4)
    
    # 2. 多聚合函数
    multi_agg = pd.pivot_table(df, values='销售额', index='产品', 
                                aggfunc=['mean', 'sum', 'count'])
    assert ('mean', '销售额') in multi_agg.columns
    
    # 3. 交叉表：产品 × 地区的频数
    cross = pd.crosstab(df['产品'], df['地区'])
    assert cross.sum().sum() == n
    
    # 4. 添加 margins
    cross_margin = pd.crosstab(df['产品'], df['地区'], margins=True)
    assert 'All' in cross_margin.columns
    assert 'All' in cross_margin.index
    
    # 5. 计算销售额占比
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0)
    assert np.allclose(pivot_pct.sum(axis=1), 1.0)
    
    print(f"   透视表形状: {pivot.shape} | 交叉表总计: {cross.sum().sum()}")
    print("✅ 扩展1 通过：透视表与交叉表")


def ext_2_time_series():
    """扩展2：时间序列分析 - 股价模拟"""
    np.random.seed(42)
    dates = pd.date_range('2025-01-01', periods=60, freq='D')
    prices = 100 + np.cumsum(np.random.randn(60) * 2)
    
    df = pd.DataFrame({
        '日期': dates,
        '收盘价': prices,
        '成交量': np.random.randint(10000, 50000, 60)
    }).set_index('日期')
    
    # 1. 重采样：周均价
    weekly = df['收盘价'].resample('W').mean()
    assert len(weekly) < len(df)
    
    # 2. 滑动窗口
    df['MA5'] = df['收盘价'].rolling(window=5).mean()
    df['MA20'] = df['收盘价'].rolling(window=20).mean()
    assert df['MA5'].isna().sum() == 4  # 前4个没有窗口
    
    # 3. 指数加权移动平均
    df['EWMA'] = df['收盘价'].ewm(span=5).mean()
    assert df['EWMA'].isna().sum() == 0  # EWMA没有NaN
    
    # 4. 日收益率
    df['收益率'] = df['收盘价'].pct_change()
    assert df['收益率'].isna().sum() == 1  # 第一个没有前一日
    
    # 5. 月度统计
    monthly = df['收盘价'].resample('ME').agg(['first', 'last', 'mean', 'std'])
    assert len(monthly) == 3  # 60天 ≈ 2个月，加上部分3月
    
    # 6. 累计最大值
    df['历史最高'] = df['收盘价'].cummax()
    assert (df['历史最高'] >= df['收盘价']).all()
    
    print(f"   周线数据点: {len(weekly)} | 月度统计: {len(monthly)}行")
    print("✅ 扩展2 通过：时间序列分析")


def ext_3_data_cleaning():
    """扩展3：数据清洗实战 - 脏数据处理"""
    # 模拟脏数据
    df = pd.DataFrame({
        '姓名': ['张三', '李四', ' 王五 ', '赵六', '张三', None, '李四'],
        '手机号': ['13800138000', '13900139000', '13800138000', 'abc123', None, '13700137000', '13900139000'],
        '邮箱': ['a@b.com', 'c@d.com', 'a@b.com', 'e@f.com', 'invalid', 'g@h.com', 'c@d.com'],
        '年龄': [25, -5, 35, 200, 25, 30, None],
        '薪资': [8000, 12000, None, 5000, 8000, 9000, '12000']
    })
    
    # 1. 去除字符串首尾空格
    df['姓名'] = df['姓名'].str.strip()
    
    # 2. 删除完全重复的行
    before = len(df)
    df = df.drop_duplicates()
    after = len(df)
    assert after <= before
    
    # 3. 处理缺失值
    df['年龄'] = pd.to_numeric(df['年龄'], errors='coerce')
    # 年龄不合理值设为NaN
    df.loc[(df['年龄'] < 0) | (df['年龄'] > 150), '年龄'] = np.nan
    df['年龄'] = df['年龄'].fillna(df['年龄'].median())
    assert df['年龄'].isna().sum() == 0
    assert (df['年龄'] >= 0).all() and (df['年龄'] <= 150).all()
    
    # 4. 统一薪资为数值
    df['薪资'] = pd.to_numeric(df['薪资'], errors='coerce')
    df['薪资'] = df['薪资'].fillna(df['薪资'].median())
    assert df['薪资'].dtype in [np.float64, np.int64, float]
    
    # 5. 手机号格式验证
    phone_valid = df['手机号'].str.match(r'^1\d{10}$', na=False)
    valid_count = phone_valid.sum()
    assert valid_count < len(df)  # 应该有无效手机号
    
    # 6. 邮箱格式验证
    email_valid = df['邮箱'].str.match(r'^[^@]+@[^@]+\.[^@]+$', na=False)
    assert email_valid.sum() < len(df)
    
    print(f"   清洗前: {before}行 → 清洗后: {after}行 | 有效手机号: {valid_count}个")
    print("✅ 扩展3 通过：数据清洗实战")


def ext_4_apply_map():
    """扩展4：apply、map、applymap 的高效使用"""
    df = pd.DataFrame({
        '语文': [85, 72, 90, 68, 88],
        '数学': [92, 85, 78, 95, 70],
        '英语': [78, 88, 82, 75, 90]
    }, index=['张三', '李四', '王五', '赵六', '钱七'])
    
    # 1. map - 对单个 Series 操作
    def grade(score):
        if score >= 90: return 'A'
        elif score >= 80: return 'B'
        elif score >= 70: return 'C'
        else: return 'D'
    
    chinese_grade = df['语文'].map(grade)
    assert chinese_grade['张三'] == 'B'  # 85 -> B
    assert chinese_grade['王五'] == 'A'  # 90 -> A
    
    # 2. apply - 对行或列操作
    df['总分'] = df.apply(lambda row: row.sum(), axis=1)
    assert df.loc['张三', '总分'] == 85 + 92 + 78  # 255
    
    # 3. apply 按列
    max_subject = df[['语文', '数学', '英语']].apply(lambda col: col.max())
    assert max_subject['语文'] == 90
    
    # 4. map 字典映射
    df['排名'] = df['总分'].rank(ascending=False).astype(int)
    assert df.loc[df['总分'].idxmax(), '排名'] == 1
    
    # 5. 自定义复杂函数
    def analyze_student(row):
        avg = row[['语文', '数学', '英语']].mean()
        std = row[['语文', '数学', '英语']].std()
        if avg >= 85:
            return '优秀'
        elif avg >= 75:
            return '良好'
        elif avg >= 60:
            return '及格'
        else:
            return '不及格'
    
    df['评价'] = df.apply(analyze_student, axis=1)
    assert '优秀' in df['评价'].values or '良好' in df['评价'].values
    
    print(f"   平均分最高: {df['总分'].max()} | 评价分布: {df['评价'].value_counts().to_dict()}")
    print("✅ 扩展4 通过：apply/map 高级用法")


def ext_5_multi_index():
    """扩展5：多级索引操作"""
    # 创建多级索引 DataFrame
    index = pd.MultiIndex.from_tuples([
        ('2025', 'Q1'), ('2025', 'Q2'), ('2025', 'Q3'), ('2025', 'Q4'),
        ('2026', 'Q1'), ('2026', 'Q2'),
    ], names=['年', '季度'])
    
    df = pd.DataFrame({
        '收入': [100, 120, 150, 130, 160, 180],
        '成本': [60, 70, 85, 75, 90, 100],
        '利润': [40, 50, 65, 55, 70, 80]
    }, index=index)
    
    # 1. 选择外层索引
    data_2025 = df.loc['2025']
    assert len(data_2025) == 4
    
    # 2. 选择内层索引
    q1_data = df.xs('Q1', level='季度')
    assert len(q1_data) == 2  # 2025 Q1 和 2026 Q1
    
    # 3. 计算利润率
    df['利润率'] = df['利润'] / df['收入']
    assert (df['利润率'] > 0).all()
    assert (df['利润率'] < 1).all()
    
    # 4. 按年汇总
    yearly = df.groupby(level='年').sum()
    assert yearly.loc['2025', '收入'] == 100 + 120 + 150 + 130
    assert yearly.loc['2026', '收入'] == 160 + 180
    
    # 5. 环比增长率
    df['收入环比'] = df['收入'].pct_change()
    assert df.loc[('2025', 'Q1'), '收入环比'] is np.nan or pd.isna(df.loc[('2025', 'Q1'), '收入环比'])
    
    # 6. unstack
    unstacked = df['收入'].unstack(level='季度')
    assert 'Q1' in unstacked.columns
    assert 'Q4' in unstacked.columns
    
    print(f"   2025年收入: {yearly.loc['2025', '收入']} | 2026上半年: {yearly.loc['2026', '收入']}")
    print("✅ 扩展5 通过：多级索引操作")


# ============================================================
# 主函数
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Pandas 基础练习")
    print("=" * 60)
    exercise_1_series_basics()
    exercise_2_dataframe_creation()
    exercise_3_filtering_selection()
    exercise_4_groupby_aggregation()
    exercise_5_merge_join()
    
    print("\n" + "=" * 60)
    print("Pandas 扩展题")
    print("=" * 60)
    ext_1_pivot_table()
    ext_2_time_series()
    ext_3_data_cleaning()
    ext_4_apply_map()
    ext_5_multi_index()
    
    print("\n" + "=" * 60)
    print("全部通过！Pandas 基础 + 扩展 10/10 ✅")
    print("=" * 60)
