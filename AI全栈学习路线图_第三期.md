# AI全栈学习路线图 — 第三期：全语言精通 + AI数学深化

> 创建时间：2026-08-05
> 前置完成：第一期216题 + 第二期60题 = 276题
> 本期目标：~205题，完成后累计~481题

---

## Part A：编程语言精通（~135题）

### 设计原则
- 每个语言覆盖：基本语法 → 控制流 → 函数/闭包 → 数据结构 → 错误处理 → 并发(如适用) → 语言独特特性 → 最佳实践
- 云端可运行：Python✅ Node.js✅ G++✅ Java(仅runtime)✅ Perl✅
- 云端不可运行：Rust/Go/Ruby/Swift/Kotlin/R/Julia/Haskell/Elixir/Scala/PHP/Lua/Dart/Zig/Nim/OCaml/Erlang/Clojure
- 不可运行的语言：创建带详细中文注释的教学代码，用户可在ANYIN9安装运行时后运行

### 阶段一览

| 阶段 | 语言 | 题数 | 文件 | 可运行 | 重点 |
|------|------|------|------|--------|------|
| 十三 | Rust | 10 | 13_rust.rs | ❌ | 所有权/借用/生命周期/trait/错误处理/并发 |
| 十四 | Go | 10 | 14_go.go | ❌ | goroutine/channel/接口/错误处理/并发模式 |
| 十五 | C++ | 10 | 15_cpp.cpp | ✅ | RAII/STL/模板/智能指针/移动语义/多线程 |
| 十六 | Java | 10 | 16_java.java | ⚠️ | JVM/OOP/泛型/Stream/并发/异常处理 |
| 十七 | JavaScript | 10 | 17_javascript.js | ✅ | 闭包/原型链/异步/Promise/ES6+/DOM |
| 十八 | C# | 8 | 18_csharp.cs | ❌ | LINQ/async/await/委托/泛型/属性 |
| 十九 | Ruby | 5 | 19_ruby.rb | ❌ | 元编程/块/模块/Duck Typing |
| 二十 | Swift | 5 | 20_swift.swift | ❌ | Optional/协议/值类型/泛型/错误处理 |
| 二十一 | Kotlin | 5 | 21_kotlin.kt | ❌ | 空安全/协程/扩展函数/数据类 |
| 二十二 | R | 5 | 22_r.r | ❌ | 数据框/ggplot/统计函数/向量化 |
| 二十三 | Julia | 5 | 23_julia.jl | ❌ | 多重派发/类型系统/宏/性能 |
| 二十四 | 函数式语言 | 15 | 24_functional/ | ❌ | Haskell(5)+Elixir(3)+Scala(3)+Clojure(2)+Erlang(2) |
| 二十五 | 脚本与系统语言 | 17 | 25_scripting/ | Perl✅ | Lua(3)+PHP(3)+Perl(3)+Dart(3)+Zig(2)+Nim(3) |

**Part A 小计：135题**

---

## Part B：AI数学模型深化（~70题）

### 设计原则
- 全部用Python实现，可在云端直接运行
- 纯numpy/scipy/sympy实现，无PyTorch/TensorFlow依赖
- 每题：数学推导 → 代码实现 → 可视化(如适用) → 思考题

### 阶段一览

| 阶段 | 主题 | 题数 | 文件 | 重点 |
|------|------|------|------|------|
| 二十六 | 线性代数与概率统计深化 | 15 | 26_linear_algebra_prob_stats.py | 矩阵分解(SVD/QR/特征分解)/概率分布/贝叶斯/假设检验 |
| 二十七 | 微积分与优化理论 | 15 | 27_calculus_optimization.py | 导数/偏导/链式法则/梯度下降/凸优化/拉格朗日 |
| 二十八 | 信息论与数值方法 | 10 | 28_info_theory_numerical.py | 熵/KL散度/互信息/数值积分/插值/蒙特卡洛 |
| 二十九 | 机器学习模型数学 | 15 | 29_ml_model_math.py | 线性回归/逻辑回归/SVM/决策树/随机森林/GBDT/K-means/朴素贝叶斯/PCA |
| 三十 | 深度学习模型数学 | 15 | 30_dl_model_math.py | 神经网络反向传播/CNN卷积池化/RNN-LSTM/Transformer注意力/Diffusion/GAN |

**Part B 小计：70题**

---

## 总览

| 期数 | 阶段 | 题数 | 累计 |
|------|------|------|------|
| 第一期 | 一~七 | 216 | 216 |
| 第二期 | 八~十二 | 60 | 276 |
| **第三期 Part A** | 十三~二十五 | 135 | 411 |
| **第三期 Part B** | 二十六~三十 | 70 | **481** |

## 执行计划

### 第一批（并行）
1. Rust + Go（阶段十三+十四，20题）
2. C++ + Java（阶段十五+十六，20题）
3. JavaScript + C#（阶段十七+十八，18题）
4. Ruby + Swift + Kotlin（阶段十九~二十一，15题）
5. R + Julia + 函数式语言（阶段二十二~二十四，25题）
6. 脚本与系统语言（阶段二十五，17题）

### 第二批（并行）
7. 线性代数 + 概率统计（阶段二十六，15题）
8. 微积分 + 优化理论（阶段二十七，15题）
9. 信息论 + 数值方法（阶段二十八，10题）
10. ML模型数学（阶段二十九，15题）
11. DL模型数学（阶段三十，15题）
