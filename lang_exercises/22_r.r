# ============================================================
# 阶段：数据科学语言 - R语言练习
# 题数：5题
# 创建日期：2026-08-05
# ============================================================

# ============================================================
# 第1题：R基础（向量 / 数据类型 / 函数）
# ============================================================
# 知识点讲解：
# R语言的核心数据结构是"向量"(vector)，几乎所有运算都面向向量设计。
# R的基本数据类型包括：numeric(数值)、character(字符)、logical(逻辑)、
# integer(整数)、complex(复数)。向量中的所有元素必须是同一类型。
# R使用 <- 进行赋值，函数定义使用 function 关键字。
# R是统计语言，天生支持向量化运算，不需要写循环即可对整个向量操作。

# --- 创建不同类型的向量 ---
numeric_vec <- c(1.5, 2.3, 4.8, 7.1)          # 数值型向量
integer_vec <- c(1L, 2L, 3L, 4L)               # 整数型向量（L后缀）
char_vec    <- c("apple", "banana", "cherry")   # 字符型向量
logic_vec   <- c(TRUE, FALSE, TRUE, TRUE)       # 逻辑型向量

# --- 向量索引（R从1开始计数）---
cat("第二个数值:", numeric_vec[2], "\n")
cat("第2到第4个:", numeric_vec[2:4], "\n")
cat("用逻辑向量筛选:", numeric_vec[logic_vec], "\n")

# --- 向量运算（自动逐元素计算）---
vec_a <- c(1, 2, 3, 4)
vec_b <- c(10, 20, 30, 40)
cat("逐元素相加:", vec_a + vec_b, "\n")
cat("标量乘法:", vec_a * 3, "\n")
cat("逐元素相乘:", vec_a * vec_b, "\n")

# --- 常用向量函数 ---
cat("求和:", sum(vec_a), "\n")
cat("均值:", mean(vec_a), "\n")
cat("最大值:", max(vec_a), "\n")
cat("排序:", sort(c(3, 1, 4, 1, 5, 9, 2, 6)), "\n")

# --- 自定义函数 ---
# 定义一个计算向量统计摘要的函数
summarize_vec <- function(x, name = "数据") {
  result <- list(
    名称 = name,
    元素数 = length(x),
    均值 = mean(x),
    标准差 = sd(x),
    最小值 = min(x),
    最大值 = max(x),
    中位数 = median(x)
  )
  return(result)
}

stats <- summarize_vec(numeric_vec, "示例数据")
print(stats)

# --- 因子(factor)：分类数据的专用类型 ---
gender <- factor(c("男", "女", "男", "男", "女"),
                 levels = c("男", "女"))
cat("因子频数表:\n")
print(table(gender))

# --- 列表(list)：R中最灵活的数据结构，可包含不同类型 ---
person <- list(
  姓名 = "张三",
  年龄 = 28,
  分数 = c(85, 90, 78, 92),
  及格 = TRUE
)
cat("姓名:", person$姓名, "\n")
cat("平均分:", mean(person$分数), "\n")

# 思考题：如果对包含数值和字符的向量执行 c(1, "a", 2)，
#         结果向量的类型是什么？为什么R要这样设计？

# ============================================================
# 第2题：数据框操作（data.frame / dplyr概念）
# ============================================================
# 知识点讲解：
# 数据框(data.frame)是R中最常用的数据结构，类似于数据库表格。
# 每列可以是不同类型，但同一列内类型必须一致。
# dplyr是R中最流行的数据操作包，提供了一套动词式API：
#   filter()  — 按条件筛选行
#   select()  — 选择列
#   mutate()  — 新增/修改列
#   arrange() — 排序
#   summarise() — 汇总统计
#   group_by() — 分组
# 管道运算符 %>% 或原生 |> 可以将前一步结果传递给后一步函数。

# --- 创建数据框 ---
students <- data.frame(
  学号 = 1001:1006,
  姓名 = c("张三", "李四", "王五", "赵六", "钱七", "孙八"),
  班级 = c("A", "A", "B", "B", "A", "B"),
  数学 = c(85, 92, 78, 65, 88, 73),
  英语 = c(78, 85, 90, 72, 95, 68),
  性别 = c("男", "男", "女", "男", "女", "男")
)

cat("数据框结构:\n")
str(students)
cat("\n前几行:\n")
print(head(students))

# --- 基础R方式操作数据框 ---
# 筛选数学大于80的学生
cat("\n数学>80的学生:\n")
print(students[students$数学 > 80, ])

# 选择特定列
cat("\n只看姓名和数学:\n")
print(students[, c("姓名", "数学")])

# 按数学排序（降序）
cat("\n按数学降序排列:\n")
print(students[order(-students$数学), ])

# 新增列
students$总分 <- students$数学 + students$英语
students$平均分 <- round(students$总分 / 2, 1)
cat("\n添加总分和平均分后:\n")
print(students)

# --- 模拟dplyr风格的链式操作（使用原生管道符 |>）---
# 注意：实际使用dplyr需要 install.packages("dplyr") 并 library(dplyr)
# 这里用基础R模拟dplyr的核心操作逻辑

# 等价于：students |> filter(数学 > 70) |> select(姓名, 班级, 数学) |> arrange(数学)
result <- students[students$数学 > 70, c("姓名", "班级", "数学")]
result <- result[order(result$数学), ]
cat("\ndplyr风格筛选+排序:\n")
print(result)

# --- 分组汇总 ---
# 按班级计算各科平均分
cat("\n按班级分组汇总:\n")
for (cls in unique(students$班级)) {
  subset_data <- students[students$班级 == cls, ]
  cat(sprintf("  班级%s: 数学均值=%.1f, 英语均值=%.1f\n",
              cls, mean(subset_data$数学), mean(subset_data$英语)))
}

# 使用 aggregate 函数实现分组汇总
cat("\naggregate分组汇总:\n")
print(aggregate(cbind(数学, 英语) ~ 班级, data = students, FUN = mean))

# --- 合并数据框 ---
extra_info <- data.frame(
  学号 = 1001:1006,
  出勤率 = c(0.95, 0.88, 0.92, 0.75, 0.98, 0.83)
)
merged <- merge(students, extra_info, by = "学号")
cat("\n合并出勤率后:\n")
print(merged[, c("姓名", "班级", "平均分", "出勤率")])

# 思考题：dplyr的管道运算符 %>% 和R原生的 |> 有什么区别？
#         在什么场景下应该用 lapply 而不是 for 循环处理数据框的列？

# ============================================================
# 第3题：数据可视化（ggplot2概念 / 基础绘图）
# ============================================================
# 知识点讲解：
# R有两套绘图系统：基础绘图系统(graphics包)和ggplot2。
# ggplot2基于"图形语法"(Grammar of Graphics)理念，通过分层叠加构建图形：
#   ggplot(data) + aes(映射) + geom_*(几何对象) + theme_*(主题)
# 核心概念：
#   - 数据(data)：要可视化的数据框
#   - 美学映射(aes)：将数据列映射到x、y、color、size等视觉属性
#   - 几何对象(geom)：点图、线图、柱状图、直方图等
#   - 分面(facet)：按某变量拆分子图
#   - 标度(scale)：控制坐标轴、颜色等映射规则
#   - 主题(theme)：控制非数据元素的外观

# --- 基础绘图系统 ---
# 生成模拟数据
set.seed(42)
n <- 50
x_vals <- 1:n
y_vals <- 2 * x_vals + rnorm(n, mean = 0, sd = 10)

# 基础散点图
plot(x_vals, y_vals,
     main = "基础散点图示例",
     xlab = "X值", ylab = "Y值",
     col = "steelblue", pch = 19)

# 叠加回归线
abline(lm(y_vals ~ x_vals), col = "red", lwd = 2)

# 直方图
hist(rnorm(1000, mean = 50, sd = 10),
     main = "正态分布直方图",
     xlab = "数值", col = "lightgreen",
     breaks = 30)

# 箱线图
group_a <- rnorm(50, mean = 70, sd = 10)
group_b <- rnorm(50, mean = 75, sd = 12)
boxplot(list(A组 = group_a, B组 = group_b),
        main = "两组数据对比箱线图",
        col = c("skyblue", "salmon"))

# --- ggplot2概念演示（伪代码，需安装ggplot2包）---
# 实际使用时取消注释并安装：install.packages("ggplot2")
#
# library(ggplot2)
#
# # 构建可视化数据
# plot_data <- data.frame(
#   x = x_vals,
#   y = y_vals,
#   group = sample(c("A", "B"), n, replace = TRUE)
# )
#
# # 散点图 + 回归线
# ggplot(plot_data, aes(x = x, y = y, color = group)) +
#   geom_point(size = 3, alpha = 0.7) +
#   geom_smooth(method = "lm", se = TRUE) +
#   labs(title = "ggplot2散点图与回归线",
#        x = "自变量", y = "因变量") +
#   theme_minimal()
#
# # 分面直方图
# ggplot(plot_data, aes(x = y, fill = group)) +
#   geom_histogram(bins = 20, alpha = 0.6, position = "identity") +
#   facet_wrap(~ group) +
#   labs(title = "分组直方图（分面展示）") +
#   theme_bw()

# --- 手动实现简单散点图矩阵概念 ---
# 展示多变量关系
multi_data <- data.frame(
  身高 = c(165, 170, 175, 160, 180, 172, 168, 178),
  体重 = c(55, 65, 70, 50, 80, 68, 58, 75),
  年龄 = c(20, 25, 30, 22, 35, 28, 24, 32)
)

# pairs函数绘制散点图矩阵
pairs(multi_data, main = "多变量散点图矩阵",
      col = "darkorange", pch = 19)

# 思考题：ggplot2中 aes() 映射放在 ggplot() 里和放在 geom_*() 里有什么区别？
#         如何用 ggplot2 绘制一个分面的密度图来比较不同组别的数据分布？

# ============================================================
# 第4题：统计分析（描述统计 / 假设检验 / 线性回归）
# ============================================================
# 知识点讲解：
# R作为统计编程语言的鼻祖，内置了大量统计函数：
#   - 描述统计：summary(), mean(), sd(), median(), quantile(), var()
#   - 假设检验：t.test()(t检验), chisq.test()(卡方检验),
#              wilcox.test()(Wilcoxon检验), aov()(方差分析)
#   - 线性回归：lm() 函数，配合 summary() 查看详细结果
#   - 相关系数：cor(), cor.test()
# 统计分析是R语言的核心应用场景，理解p值、置信区间等概念非常重要。

# --- 描述性统计 ---
set.seed(2026)
exam_scores <- rnorm(100, mean = 75, sd = 12)

cat("=== 描述性统计 ===\n")
cat("样本量:", length(exam_scores), "\n")
cat("均值:", round(mean(exam_scores), 2), "\n")
cat("中位数:", round(median(exam_scores), 2), "\n")
cat("标准差:", round(sd(exam_scores), 2), "\n")
cat("方差:", round(var(exam_scores), 2), "\n")
cat("最小值:", round(min(exam_scores), 2), "\n")
cat("最大值:", round(max(exam_scores), 2), "\n")
cat("四分位数:\n")
print(quantile(exam_scores, probs = c(0, 0.25, 0.5, 0.75, 1)))

# summary函数一次性给出摘要
cat("\nsummary()输出:\n")
print(summary(exam_scores))

# --- 单样本t检验 ---
# 检验样本均值是否显著不同于70
cat("\n=== 单样本t检验 ===\n")
t_result <- t.test(exam_scores, mu = 70)
print(t_result)
cat("p值:", round(t_result$p.value, 4), "\n")
cat("95%置信区间:", round(t_result$conf.int, 2), "\n")

# --- 双样本t检验 ---
group_x <- rnorm(50, mean = 72, sd = 10)
group_y <- rnorm(50, mean = 78, sd = 10)

cat("\n=== 双样本t检验 ===\n")
t2_result <- t.test(group_x, group_y, var.equal = TRUE)
print(t2_result)
cat("p值:", round(t2_result$p.value, 4), "\n")
if (t2_result$p.value < 0.05) {
  cat("结论：在显著性水平0.05下，两组均值有显著差异\n")
} else {
  cat("结论：在显著性水平0.05下，两组均值无显著差异\n")
}

# --- 卡方检验（独立性检验）---
cat("\n=== 卡方独立性检验 ===\n")
survey <- matrix(c(30, 20, 15, 35), nrow = 2, byrow = TRUE)
rownames(survey) <- c("男性", "女性")
colnames(survey) <- c("喜欢", "不喜欢")
cat("列联表:\n")
print(survey)
chi_result <- chisq.test(survey)
cat("卡方统计量:", round(chi_result$statistic, 4), "\n")
cat("p值:", round(chi_result$p.value, 4), "\n")

# --- 线性回归 ---
cat("\n=== 线性回归 ===\n")
# 生成回归数据
n <- 100
study_hours <- runif(n, min = 1, max = 10)
scores <- 50 + 4 * study_hours + rnorm(n, mean = 0, sd = 5)
reg_data <- data.frame(学习时长 = study_hours, 考试成绩 = scores)

# 拟合线性模型
model <- lm(考试成绩 ~ 学习时长, data = reg_data)
cat("回归结果摘要:\n")
print(summary(model))

# 提取关键指标
cat("\n截距:", round(coef(model)[1], 2), "\n")
cat("斜率:", round(coef(model)[2], 2), "\n")
cat("R方:", round(summary(model)$r.squared, 4), "\n")

# 绘制回归图
plot(reg_data$学习时长, reg_data$考试成绩,
     main = "学习时长与考试成绩的线性回归",
     xlab = "学习时长(小时)", ylab = "考试成绩",
     col = "steelblue", pch = 19)
abline(model, col = "red", lwd = 2)

# --- 相关系数 ---
cat("\n=== 相关系数 ===\n")
cor_val <- cor(study_hours, scores)
cat("Pearson相关系数:", round(cor_val, 4), "\n")
cor_test <- cor.test(study_hours, scores)
cat("相关检验p值:", round(cor_test$p.value, 6), "\n")

# 思考题：t检验中"方差齐性"假设是什么意思？
#         var.equal=TRUE 和 FALSE 的结果会有什么不同？
#         如何判断线性回归模型是否满足基本假设？

# ============================================================
# 第5题：向量化与性能（向量化运算 / apply家族）
# ============================================================
# 知识点讲解：
# R的性能核心在于"向量化"——避免显式循环，利用C层面优化的向量运算。
# apply家族是一组高阶函数，用于替代循环：
#   apply()   — 对矩阵/数组的行或列应用函数
#   lapply()  — 对列表每个元素应用函数，返回列表
#   sapply()  — lapply的简化版，尝试返回向量
#   vapply()  — 类似sapply但指定返回类型，更安全
#   mapply()  — 多参数版本的sapply
#   tapply()  — 按分组应用函数
# 性能建议：优先向量化 > apply家族 > for循环

# --- 向量化 vs 循环性能对比 ---
n <- 100000
vec <- rnorm(n)

# 方法1：for循环求平方和（慢）
system.time({
  total_loop <- 0
  for (i in 1:n) {
    total_loop <- total_loop + vec[i]^2
  }
})

# 方法2：向量化运算（快）
system.time({
  total_vec <- sum(vec^2)
})

cat("循环结果:", round(total_loop, 4), "\n")
cat("向量化结果:", round(total_vec, 4), "\n")

# --- apply：矩阵行/列运算 ---
mat <- matrix(rnorm(20), nrow = 4, ncol = 5)
cat("\n矩阵:\n")
print(round(mat, 2))

cat("每列均值(apply, MARGIN=2):", round(apply(mat, 2, mean), 4), "\n")
cat("每行均值(apply, MARGIN=1):", round(apply(mat, 1, mean), 4), "\n")
cat("每列标准差:", round(apply(mat, 2, sd), 4), "\n")

# --- lapply：对列表元素逐一应用函数 ---
my_list <- list(
  向量A = c(1, 2, 3, 4, 5),
  向量B = c(10, 20, 30),
  向量C = c(100, 200, 300, 400)
)

cat("\nlapply求各向量均值:\n")
print(lapply(my_list, mean))

# sapply返回向量形式（更紧凑）
cat("sapply求各向量均值:", sapply(my_list, mean), "\n")
cat("sapply求各向量长度:", sapply(my_list, length), "\n")

# --- vapply：类型安全的sapply ---
cat("\nvapply(指定返回类型):\n")
print(vapply(my_list, mean, numeric(1)))

# --- tapply：分组应用函数 ---
cat("\ntapply分组统计:\n")
category <- rep(c("A", "B", "C"), each = 10)
values <- rnorm(30, mean = 50, sd = 10)
cat("各分组均值:", round(tapply(values, category, mean), 2), "\n")
cat("各分组标准差:", round(tapply(values, category, sd), 2), "\n")

# --- mapply：多参数并行应用 ---
# 同时对两个向量做逐元素运算
vec1 <- c(1, 2, 3, 4)
vec2 <- c(10, 20, 30, 40)
cat("\nmapply多参数运算:\n")
cat("向量相加:", mapply(function(a, b) a + b, vec1, vec2), "\n")
cat("向量拼接:", mapply(function(a, b) paste(a, b, sep = "-"), vec1, vec2), "\n")

# --- replicate：重复执行并收集结果 ---
# 模拟1000次掷骰子的均值
dice_means <- replicate(1000, mean(sample(1:6, 10, replace = TRUE)))
cat("\n1000次模拟骰子均值分布:\n")
cat("  均值的均值:", round(mean(dice_means), 4), "\n")
cat("  均值的标准差:", round(sd(dice_means), 4), "\n")

# --- 实战：用向量化计算移动平均 ---
# 向量化实现滑动窗口均值
series <- rnorm(50)
window_size <- 5
# 使用 filter 函数实现移动平均
ma_result <- filter(series, rep(1 / window_size, window_size), sides = 1)
cat("\n移动平均(前10个值):\n")
print(round(head(ma_result, 10), 4))

# --- Reduce：逐步归约 ---
cat("\nReduce逐步累加:", Reduce(`+`, 1:10), "\n")
cat("Reduce逐步拼接:", Reduce(function(a, b) paste0(a, "-", b),
                               letters[1:5]), "\n")

# --- 向量化条件赋值：ifelse / case_when概念 ---
scores_vec <- c(85, 60, 92, 45, 78, 30, 95)
grade <- ifelse(scores_vec >= 90, "优秀",
         ifelse(scores_vec >= 80, "良好",
         ifelse(scores_vec >= 60, "及格", "不及格")))
cat("\n成绩等级:\n")
print(data.frame(成绩 = scores_vec, 等级 = grade))

# 思考题：apply家族函数和for循环在性能上真的有很大差距吗？
#         在什么情况下for循环反而比apply更合适？
#         如何用 Vectorize() 将一个标量函数转化为向量函数？
