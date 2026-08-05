# ============================================================
# 阶段：科学计算语言 - Julia语言练习
# 题数：5题
# 创建日期：2026-08-05
# ============================================================

# ============================================================
# 第1题：Julia基础（类型 / 函数 / 多重派发）
# ============================================================
# 知识点讲解：
# Julia是为科学计算设计的高性能语言，语法接近Python/MATLAB，
# 但速度接近C。Julia的核心特性是"多重派发"(Multiple Dispatch)：
# 函数的行为由所有参数的类型共同决定，而不仅仅是第一个参数(像OOP那样)。
# Julia的基本类型：Int64, Float64, String, Bool, Char, Array, Tuple。
# 类型系统是Julia性能的基础——编译器能根据类型生成高效机器码。

# --- 变量与基本类型 ---
x = 42              # Int64
y = 3.14            # Float64
name = "Julia"      # String
flag = true         # Bool
ch = 'J'            # Char

println("整数类型: ", typeof(x))
println("浮点类型: ", typeof(y))
println("字符串类型: ", typeof(name))
println("布尔类型: ", typeof(flag))
println("字符类型: ", typeof(ch))

# --- 字符串操作 ---
greeting = "Hello, " * name * "!"   # * 用于字符串拼接
println(greeting)
println("大写: ", uppercase(name))
println("长度: ", length(name))
println("插值: $name 的版本号是 $(1.10)")

# --- 数组（Julia的数组索引从1开始）---
arr = [1, 2, 3, 4, 5]
arr2d = [1 2 3; 4 5 6]  # 2行3列矩阵

println("\n一维数组: ", arr)
println("数组类型: ", typeof(arr))
println("矩阵:\n", arr2d)
println("第二行: ", arr2d[2, :])
println("第二列: ", arr2d[:, 2])

# --- 元组与具名元组 ---
tuple1 = (1, "hello", 3.14)
named_tuple = (姓名="张三", 年龄=25, 城市="北京")
println("\n元组: ", tuple1)
println("具名元组: ", named_tuple)
println("姓名字段: ", named_tuple.姓名)

# --- 函数定义 ---
# 标准函数定义
function add(a, b)
    return a + b
end

# 简洁的单行函数定义
square(x) = x^2

# 匿名函数
cube = x -> x^3

println("\nadd(3, 4) = ", add(3, 4))
println("square(5) = ", square(5))
println("cube(2) = ", cube(2))

# --- 多重派发：同名函数根据参数类型有不同行为 ---
# 定义 greet 的多个方法
greet(name::String) = "你好, $name!"
greet(name::String, times::Int) = repeat("你好, $name! ", times)
greet(num::Int) = "数字不能打招呼: $num"

println("\n--- 多重派发演示 ---")
println(greet("世界"))
println(greet("Julia", 3))
println(greet(42))

# 查看函数的所有方法
println("\ngreet 的方法列表:")
println(methods(greet))

# --- 默认参数和关键字参数 ---
function compute_stats(data; verbose=false)
    m = mean_val(data)
    v = var_val(data)
    if verbose
        println("  数据: $data")
        println("  均值: $m")
        println("  方差: $v")
    end
    return (mean=m, variance=v)
end

# 辅助函数
mean_val(d) = sum(d) / length(d)
var_val(d) = sum((d .- mean_val(d)).^2) / length(d)

println("\n--- 带关键字参数的函数 ---")
result = compute_stats([1.0, 2.0, 3.0, 4.0, 5.0], verbose=true)

# --- 多返回值 ---
function min_max(arr)
    return minimum(arr), maximum(arr)
end

lo, hi = min_max([3, 1, 4, 1, 5, 9, 2, 6])
println("\n最小值: $lo, 最大值: $hi")

# 思考题：Julia的多重派发和面向对象语言中的方法重载有什么本质区别？
#         为什么说多重派发让Julia既灵活又高性能？

# ============================================================
# 第2题：类型系统（参数类型 / 抽象类型 / Union）
# ============================================================
# 知识点讲解：
# Julia的类型系统是其性能的关键。主要概念：
#   - 抽象类型(Abstract Type)：不能实例化，用作类型层次的节点
#   - 具体类型(Concrete Type)：可以实例化，如 struct、Int64 等
#   - 参数类型(Parametric Type)：带类型参数的泛型类型，如 Vector{T}
#   - Union：联合类型，表示"可能是A或B类型"
#   - 类型注解：用 :: 指定类型，帮助编译器优化
# Julia的类型系统是"动态但有注解"——不注解也能运行，但注解后性能更好。

# --- 抽象类型与类型层次 ---
# Julia的数值类型层次：Number > Real > Number > Integer > Int64
println("=== 类型层次 ===")
println("Int64 <: Integer: ", Int64 <: Integer)
println("Integer <: Number: ", Integer <: Number)
println("Float64 <: Real: ", Float64 <: Real)
println("String <: Number: ", String <: Number)

# --- 自定义抽象类型 ---
abstract type Shape end
abstract type AbstractCircle <: Shape end
abstract type AbstractPolygon <: Shape end

# --- 自定义结构体（具体类型）---
struct Point
    x::Float64
    y::Float64
end

# 不可变结构体(struct) vs 可变结构体(mutable struct)
mutable struct MutablePoint
    x::Float64
    y::Float64
end

# --- 参数类型（泛型）---
struct Vec2D{T}
    x::T
    y::T
end

# 不同类型参数创建不同具体类型
v_int = Vec2D{Int}(3, 4)
v_float = Vec2D{Float64}(1.5, 2.5)
println("\n整数向量类型: ", typeof(v_int))
println("浮点向量类型: ", typeof(v_float))

# 为参数类型定义方法
function magnitude(v::Vec2D{T}) where T
    return sqrt(v.x^2 + v.y^2)
end

println("v_int 的模: ", magnitude(v_int))
println("v_float 的模: ", magnitude(v_float))

# --- 带内联构造器的结构体 ---
struct Circle <: AbstractCircle
    center::Point
    radius::Float64

    # 内联构造函数
    function Circle(center::Point, radius::Float64)
        radius > 0 || error("半径必须为正数")
        return new(center, radius)
    end
end

c = Circle(Point(0.0, 0.0), 5.0)
println("\n圆: 中心($(c.center.x), $(c.center.y)), 半径=$(c.radius)")

# 为 Circle 定义 area 方法
area(c::Circle) = π * c.radius^2
println("圆面积: ", area(c))

# --- mutable struct 与修改 ---
mp = MutablePoint(1.0, 2.0)
mp.x = 10.0   # 可变结构体允许修改字段
println("\n修改后: ($(mp.x), $(mp.y))")

# struct 是不可变的，以下会报错：
# p = Point(1.0, 2.0)
# p.x = 10.0  # ERROR: setfield! immutable

# --- Union类型 ---
# 表示一个值可以是多种类型之一
IntOrString = Union{Int, String}

function describe(val::IntOrString)
    if val isa Int
        return "整数: $val"
    else
        return "字符串: \"$val\""
    end
end

println("\n", describe(42))
println(describe("hello"))

# --- Tuple和NamedTuple的类型 ---
println("\n=== 元组类型 ===")
t1 = (1, "a", 3.14)
println("元组类型: ", typeof(t1))  # Tuple{Int64, String, Float64}

nt = (x=1, y=2.0)
println("具名元组类型: ", typeof(nt))

# --- 类型转换 ---
println("\n=== 类型转换 ===")
println("Int(3.7) = ", Int(3.7))        # 截断为3
println("Float64(5) = ", Float64(5))
println("convert(Float64, 3) = ", convert(Float64, 3))

# --- Nothing类型（类似null/None）---
function find_first_even(arr)
    for x in arr
        iseven(x) && return x
    end
    return nothing
end

result = find_first_even([1, 3, 5, 4, 7])
println("\n第一个偶数: ", result)
result2 = find_first_even([1, 3, 5])
println("全奇数的结果: ", result2, " (类型: ", typeof(result2), ")")

# 思考题：Julia中 struct（不可变）和 mutable struct 在内存布局和性能上
#         有什么区别？为什么Julia推荐优先使用不可变结构体？

# ============================================================
# 第3题：多重派发深入（方法重载 / 性能优势）
# ============================================================
# 知识点讲解：
# 多重派发是Julia最独特的设计。在OOP语言中，方法调用 obj.method(args)
# 是基于obj（接收者）的类型来分派的——这叫"单分派"。
# Julia的所有参数都参与分派——这叫"多重派发"。
# 优势：
#   1. 扩展性：可以为已有类型添加新函数，无需修改类型定义
#   2. 性能：编译器能根据类型生成特化代码
#   3. 表达力：自然地表达不同类型组合的不同行为

# --- 定义几何类型体系 ---
abstract type Animal end
abstract type Shape2D end

# --- 多重派发：运算符重载 ---
struct Vector2D
    x::Float64
    y::Float64
end

# 重载 + 运算符
import Base: +, -, *, show

function +(a::Vector2D, b::Vector2D)
    return Vector2D(a.x + b.x, a.y + b.y)
end

function -(a::Vector2D, b::Vector2D)
    return Vector2D(a.x - b.x, a.y - b.y)
end

# 标量乘法：两种参数顺序都定义
function *(s::Number, v::Vector2D)
    return Vector2D(s * v.x, s * v.y)
end

function *(v::Vector2D, s::Number)
    return s * v  # 复用上面的定义
end

function show(io::IO, v::Vector2D)
    print(io, "Vec2D($(v.x), $(v.y))")
end

# 测试运算符重载
v1 = Vector2D(1.0, 2.0)
v2 = Vector2D(3.0, 4.0)
println("v1 + v2 = ", v1 + v2)
println("v2 - v1 = ", v2 - v1)
println("3 * v1 = ", 3 * v1)
println("v1 * 2 = ", v1 * 2)

# --- 多重派发实现"访问者模式" ---
# 定义不同形状
struct CircleS <: Shape2D
    radius::Float64
end

struct RectangleS <: Shape2D
    width::Float64
    height::Float64
end

struct TriangleS <: Shape2D
    a::Float64
    b::Float64
    c::Float64
end

# 通过多重派发为每种形状定义面积函数
area(s::CircleS) = π * s.radius^2

function area(s::RectangleS)
    return s.width * s.height
end

function area(s::TriangleS)
    # 海伦公式
    s_semi = (s.a + s.b + s.c) / 2
    return sqrt(s_semi * (s_semi - s.a) * (s_semi - s.b) * (s_semi - s.c))
end

# 周长函数也通过多重派发
perimeter(s::CircleS) = 2π * s.radius
perimeter(s::RectangleS) = 2 * (s.width + s.height)
perimeter(s::TriangleS) = s.a + s.b + s.c

shapes = [CircleS(3.0), RectangleS(4.0, 5.0), TriangleS(3.0, 4.0, 5.0)]

println("\n--- 多重派发：形状计算 ---")
for s in shapes
    println("$(typeof(s)): 面积=$(round(area(s), digits=2)), 周长=$(round(perimeter(s), digits=2))")
end

# --- 为已有类型扩展新函数 ---
# Julia允许为内置类型添加新方法（这是多重派发的威力）
# 为 Number 类型添加一个 myfunc 方法
myfunc(x::Integer) = "整数: $x，平方为 $(x^2)"
myfunc(x::AbstractFloat) = "浮点数: $x，四舍五入为 $(round(Int, x))"
myfunc(x::Complex) = "复数: $x，模为 $(abs(x))"

println("\n--- 扩展内置类型 ---")
println(myfunc(5))
println(myfunc(3.7))
println(myfunc(3 + 4im))

# --- 多重派发的歧义检测 ---
# 当两个方法都能匹配时，Julia会报歧义错误
# 以下展示如何避免歧义：
function collide(a::CircleS, b::CircleS)
    dist = abs(a.radius - b.radius)  # 简化：仅比较半径差
    return dist < max(a.radius, b.radius)
end

function collide(a::CircleS, b::RectangleS)
    return "圆与矩形碰撞检测（简化）"
end

function collide(a::RectangleS, b::CircleS)
    return collide(b, a)  # 对称性：复用
end

println("\n--- 多重派发：碰撞检测 ---")
println(collide(CircleS(3.0), CircleS(5.0)))
println(collide(CircleS(3.0), RectangleS(4.0, 5.0)))
println(collide(RectangleS(4.0, 5.0), CircleS(3.0)))

# --- @which 查看具体调用了哪个方法 ---
println("\n--- 查看方法分派 ---")
println("area(CircleS) 的具体方法:")
println(@which area(CircleS(1.0)))

# 思考题：如果Julia只有单分派(像Python/Java)，上面的形状系统会怎么设计？
#         多重派发如何避免了"表达式问题"(Expression Problem)？

# ============================================================
# 第4题：宏与元编程（表达式 / 宏定义）
# ============================================================
# 知识点讲解：
# Julia的元编程允许在编译时操作代码本身。核心概念：
#   - 表达式(Expr)：Julia代码在内部表示为Expr对象
#   - 引用(quote)：:(...) 或 quote...end 创建表达式而不执行
#   - 宏(Macro)：接收表达式作为输入，返回变换后的表达式
#   - 宏在编译期展开，不产生运行时开销
#   - @time, @assert, @show 等都是宏
# 宏用于：代码生成、性能测量、DSL构建、编译期检查。

# --- 表达式基础 ---
# :(...) 语法创建表达式
expr1 = :(1 + 2 * 3)
println("表达式: ", expr1)
println("表达式类型: ", typeof(expr1))
println("求值结果: ", eval(expr1))

# quote...end 创建多行表达式
expr2 = quote
    x = 10
    y = 20
    x + y
end
println("\n多行表达式求值: ", eval(expr2))

# 检查表达式结构
expr3 = :(a + b * c)
println("\n表达式头部: ", expr3.head)   # :call
println("表达式参数: ", expr3.args)     # [:+, :a, :(b * c)]

# --- 程序化构造表达式 ---
# 动态构建一个函数调用
func_name = :println
arg_expr = :("动态生成的调用")
dynamic_call = Expr(:call, func_name, arg_expr)
println("\n动态构造的表达式: ", dynamic_call)
eval(dynamic_call)

# --- 宏定义基础 ---
# 宏以 macro 关键字定义，参数是表达式
macro sayhi(name)
    return :(println("你好, ", $name, "!"))
end

@sayhi "Julia"
@sayhi "元编程"

# --- 实用宏：计时器 ---
macro timeit(ex)
    return quote
        local t0 = time()
        local val = $(esc(ex))
        local t1 = time()
        println("执行耗时: ", round(t1 - t0, digits=6), " 秒")
        val
    end
end

# 测试计时宏
result = @timeit sum(1:1_000_000)
println("结果: ", result)

# --- 宏：unless（unless 的反逻辑实现）---
macro unless(cond, block)
    return quote
        if !($(esc(cond)))
            $(esc(block))
        end
    end
end

x = 5
@unless x > 10 begin
    println("x 不大于 10，执行了 unless 块")
end

# --- 宏：类型安全的属性访问 ---
macro accessed(field)
    return :(getfield(this, $(QuoteNode(field))))
end

# --- 宏展开检查 ---
# @macroexpand 查看宏展开后的代码
println("\n@sayhi 展开后:")
println(@macroexpand @sayhi "test")

# --- 字符串插值宏：自定义格式化 ---
macro fmt(fmt_str, args...)
    # 简化版：将 {0}, {1} 替换为参数
    result = string(fmt_str)
    for (i, arg) in enumerate(args)
        result = replace(result, "{$(i-1)}" => string(arg))
    end
    return :(println($result))
end

@fmt "姓名: {0}, 年龄: {1}" "张三" 25
@fmt "{0} + {1} = {2}" 3 5 8

# --- 代码生成：批量定义方法 ---
# 使用 @eval 动态生成函数
for op in (:+, :-, :*)
    @eval begin
        function ($op)(a::Vector2D, b::Vector2D)
            return Vector2D(($op)(a.x, b.x), ($op)(a.y, b.y))
        end
    end
end

v3 = Vector2D(1.0, 2.0)
v4 = Vector2D(3.0, 4.0)
println("\n代码生成的运算:")
println("v3 + v4 = ", v3 + v4)
println("v3 - v4 = ", v3 - v4)

# --- 宏卫生性(Hygiene)演示 ---
# 宏内变量默认是局部的，不会污染调用域
macro swap(a, b)
    return quote
        local tmp = $(esc(a))
        $(esc(a)) = $(esc(b))
        $(esc(b)) = tmp
    end
end

p = 1
q = 2
@swap p q
println("\n交换后: p=$p, q=$q")

# 思考题：宏和函数有什么本质区别？为什么宏在编译期展开而非运行期？
#         什么是宏的"卫生性"(Hygiene)？它解决了什么问题？

# ============================================================
# 第5题：性能优化（类型稳定性 / 内存布局 / @inbounds）
# ============================================================
# 知识点讲解：
# Julia的性能秘诀在于让编译器能生成最优代码。关键原则：
#   1. 类型稳定性(Type Stability)：函数对同一类型输入返回同一类型输出
#      编译器能推断返回类型，无需运行时类型检查
#   2. 避免全局变量：全局变量类型不确定，用 const 或局部变量
#   3. 内存布局：不可变结构体在栈上分配，数组的元素类型一致
#   4. @inbounds：跳过数组边界检查（确保安全时使用）
#   5. @fastmath：允许编译器重排浮点运算（可能改变精度）
#   6. 避免类型不稳定：不要在同一函数中返回不同类型

# --- 类型稳定性示例 ---
# 类型不稳定的函数（差）：可能返回 Int 或 Float
function unstable_sum(arr)
    s = 0          # Int
    for x in arr
        s += x     # 如果x是Float，s变成Float；如果x是Int，s保持Int
    end
    return s       # 返回类型取决于输入，编译器无法优化
end

# 类型稳定的函数（好）：始终返回Float64
function stable_sum(arr)
    s = 0.0        # Float64，明确
    for x in arr
        s += x     # 总是Float64 + Float64
    end
    return s       # 返回类型确定
end

# 使用 @code_warntype 检查类型稳定性
# @code_warntype unstable_sum([1.0, 2.0, 3.0])  # 会看到红色类型标注
# @code_warntype stable_sum([1.0, 2.0, 3.0])     # 全绿色，类型稳定

test_arr = [1.0, 2.0, 3.0, 4.0, 5.0]
println("不稳定版结果: ", unstable_sum(test_arr))
println("稳定版结果: ", stable_sum(test_arr))

# --- 全局变量 vs 局部变量 ---
# 全局变量（差）：类型不确定
global_var = 0.0  # 全局变量，编译器不知道类型是否会变

function bad_global_loop(n)
    for i in 1:n
        global_var += i   # 每次都做运行时类型检查
    end
end

# const 全局变量（好）：类型固定
const CONST_VAR = 0.0

function good_const_loop(n)
    s = 0.0
    for i in 1:n
        s += i
    end
    return s
end

# --- 数组预分配 ---
# 差：逐步 push! 到数组（频繁重新分配内存）
function build_array_bad(n)
    arr = Int[]
    for i in 1:n
        push!(arr, i)
    end
    return arr
end

# 好：预分配大小
function build_array_good(n)
    arr = Vector{Int}(undef, n)  # 预分配
    for i in 1:n
        arr[i] = i
    end
    return arr
end

println("\n预分配数组（前5个）: ", build_array_good(10)[1:5])

# --- @inbounds 跳过边界检查 ---
function sum_inbounds(arr)
    s = zero(eltype(arr))
    @inbounds for i in 1:length(arr)
        s += arr[i]
    end
    return s
end

function sum_checked(arr)
    s = zero(eltype(arr))
    for i in 1:length(arr)
        s += arr[i]
    end
    return s
end

big_arr = rand(1_000_000)
println("\n@inbounds 求和: ", sum_inbounds(big_arr))
println("普通求和: ", sum_checked(big_arr))
println("内置sum: ", sum(big_arr))

# --- 列推导式 vs 循环 vs map ---
n = 100000
data = rand(n)

# 推导式（通常已足够快）
result_comp = [x^2 for x in data if x > 0.5]

# 循环版
function filter_square_loop(data)
    result = Float64[]
    for x in data
        if x > 0.5
            push!(result, x^2)
        end
    end
    return result
end

# 预分配版
function filter_square_prealloc(data)
    result = Vector{Float64}(undef, length(data))
    count = 0
    @inbounds for i in 1:length(data)
        if data[i] > 0.5
            count += 1
            result[count] = data[i]^2
        end
    end
    return result[1:count]
end

result_loop = filter_square_loop(data)
result_pre = filter_square_prealloc(data)
println("\n推导式长度: ", length(result_comp))
println("循环版长度: ", length(result_loop))
println("预分配版长度: ", length(result_pre))

# --- 结构体内存布局 ---
# 不可变结构体的字段紧密排列在内存中（栈分配）
struct Pixel
    r::UInt8
    g::UInt8
    b::UInt8
end

# 创建像素数组，内存连续
pixels = [Pixel(rand(0:255), rand(0:255), rand(0:255)) for _ in 1:1000]

# 计算平均亮度
function avg_brightness(pixels)
    total = 0
    @inbounds for p in pixels
        total += (Int(p.r) + Int(p.g) + Int(p.b)) ÷ 3
    end
    return total ÷ length(pixels)
end

println("\n平均亮度: ", avg_brightness(pixels))

# --- @views 避免数组拷贝 ---
# 不使用 @view：切片会复制数据
function process_slice_copy(arr)
    sub = arr[1:length(arr)÷2]  # 复制
    return sum(sub)
end

# 使用 @view：零拷贝视图
function process_slice_view(arr)
    sub = @view arr[1:length(arr)÷2]  # 不复制
    return sum(sub)
end

println("\n切片拷贝求和: ", process_slice_copy(big_arr))
println("视图求和: ", process_slice_view(big_arr))

# --- 性能分析工具（注释形式展示）---
# @time sum(big_arr)              # 基本计时
# @btime sum($big_arr)            # BenchmarkTools 更精确的计时
# @profile sum(big_arr);          # 性能分析
# Profile.print()                 # 查看火焰图数据
# @code_warntype stable_sum(test_arr)  # 检查类型不稳定性

# 思考题：为什么 @inbounds 能提升性能？在什么情况下使用它是危险的？
#         "类型稳定性"为什么是Julia性能的核心？如何用 @code_warntype 检测？
