// ==============================================================================
// 阶段：Kotlin 编程练习
// 题数：5
// 创建日期：2026-08-05
// 说明：由浅入深，覆盖 Kotlin 核心特性——从基础语法到协程与函数式集合
// ==============================================================================

// ==============================================================================
// 第 1 题：Kotlin 基础（val / var / 空安全 / 类型推断）
// ==============================================================================
// 知识点：
//   1. val 不可变引用（类似 final），var 可变引用。优先用 val。
//   2. 类型推断：Kotlin 能根据初始值推断类型，多数情况无需显式声明。
//   3. 空安全是 Kotlin 核心特性：String 不能为 null，String? 才可以。
//   4. 安全调用 ?. / Elvis 运算符 ?: / 非空断言 !! / let 安全作用域。
//   5. 字符串模板：$variable 或 ${expression}。
// ==============================================================================

// --- val vs var ---
val name: String = "Kotlin"      // val 不可变，显式类型
val version = "1.9"              // 类型推断为 String
var count = 0                    // var 可变，类型推断为 Int
count = 10                       // OK，重新赋值
// name = "Java"                 // 编译错误：val 不可重新赋值

println("语言：$name，版本：$version，计数：$count")

// --- 空安全 ---
var nullableStr: String? = "Hello"   // String? 允许 null
var nonNullStr: String = "World"     // String 不允许 null

// nullableStr.length           // 编译错误：可能为 null
println(nullableStr?.length)        // 安全调用：5 或 null

nullableStr = null
println(nullableStr?.length)        // null

// Elvis 运算符：左侧为 null 时取右侧默认值
val len = nullableStr?.length ?: 0
println("长度：$len")                // 0

// 非空断言 !!：确信非 null 时强制解包，为 null 则抛 NPE
// val risky = nullableStr!!      // 此处会抛 NullPointerException，慎用

// let 安全作用域：只有非 null 时才执行
nullableStr = "Back"
nullableStr?.let {
    println("非空，值为 $it，长度 ${it.length}")
}

// --- 字符串模板与多行字符串 ---
val x = 5
val y = 10
println("$x + $y = ${x + y}")       // 5 + 10 = 15

val json = """
{
    "name": "$name",
    "version": "$version"
}
""".trimIndent()
println(json)

// --- 类型转换 ---
val intVal = 42
val longVal: Long = intVal.toLong()   // 必须显式转换，无隐式拓宽
val doubleVal: Double = intVal.toDouble()
val strVal: String = intVal.toString()
println("Long=$longVal, Double=$doubleVal, String=$strVal")

// --- 区间（Range）---
for (i in 1..5) print("$i ")          // 1 2 3 4 5
println()
for (i in 1 until 5) print("$i ")     // 1 2 3 4（不含 5）
println()
for (i in 10 downTo 1 step 3) print("$i ")  // 10 7 4 1
println()
val inRange = 3 in 1..10              // true
println("3 在 1..10 中：$inRange")

// --- when 表达式（增强版 switch）---
fun describe(obj: Any): String = when (obj) {
    1 -> "数字一"
    is String -> "字符串：$obj"
    is Int -> "整数"
    in 2..10 -> "2到10之间的数"
    else -> "未知类型"
}
println(describe("Hello"))            // 字符串：Hello
println(describe(1))                  // 数字一

// 思考题：val 和 const val 有什么区别？为什么有些场景需要 const？
//         Kotlin 的空安全和 Java 的 @Nullable 注解有何本质区别？

// ==============================================================================
// 第 2 题：函数与 Lambda（高阶函数 / inline / 扩展函数）
// ==============================================================================
// 知识点：
//   1. 高阶函数：接收函数作为参数或返回函数的函数。函数类型写作 (T) -> R。
//   2. Lambda 表达式：{ 参数 -> 主体 }，单个参数时可用 it 代替。
//   3. inline 关键字：内联函数，编译时将函数体"粘贴"到调用处，消除 Lambda 开销。
//   4. 扩展函数：为已有类添加新方法，无需继承。语法：fun Type.method()。
//   5. 带接收者的 Lambda：Lambda 体内可用 this 指代接收者（DSL 的基础）。
// ==============================================================================

// --- 普通函数与默认参数 ---
fun greet(name: String, prefix: String = "你好", suffix: String = "！"): String {
    return "$prefix, $name$suffix"
}
println(greet("Kotlin"))                    // 你好, Kotlin！
println(greet("World", prefix = "Hello"))   // Hello, World！
println(greet("函数", suffix = "。"))        // 你好, 函数。

// --- 单表达式函数 ---
fun square(x: Int) = x * x
fun isEven(n: Int) = n % 2 == 0
println("平方：${square(5)}, 偶数：${isEven(4)}")

// --- 高阶函数 ---
// 接收函数参数
fun operate(a: Int, b: Int, op: (Int, Int) -> Int): Int {
    return op(a, b)
}
println(operate(3, 4) { x, y -> x + y })    // 7
println(operate(3, 4) { x, y -> x * y })    // 12

// 返回函数
fun multiplier(factor: Int): (Int) -> Int {
    return { n -> n * factor }
}
val triple = multiplier(3)
val quintuple = multiplier(5)
println(triple(10))                          // 30
println(quintuple(10))                       // 50

// --- Lambda 与 it ---
val nums = listOf(1, 2, 3, 4, 5)
val doubled = nums.map { it * 2 }            // it 是隐式参数名
val evens = nums.filter { it % 2 == 0 }
val sum = nums.reduce { acc, n -> acc + n }
println("翻倍：$doubled, 偶数：$evens, 求和：$sum")

// --- inline 函数 ---
// inline：编译时内联展开，减少函数调用开销和对象创建
inline fun <T> withTiming(action: () -> T): T {
    val start = System.nanoTime()
    val result = action()
    val elapsed = System.nanoTime() - start
    println("执行耗时：${elapsed / 1_000_000} ms")
    return result
}

val calcResult = withTiming {
    var sum = 0L
    for (i in 1..1_000_000) sum += i
    sum
}
println("计算结果：$calcResult")

// noinline：阻止特定 Lambda 被内联（当需要传递该 Lambda 时）
inline fun mixedInline(inlineBlock: () -> Unit, noinline nonInlineBlock: () -> Unit) {
    inlineBlock()
    nonInlineBlock()
}

// --- 扩展函数 ---
// 为 String 添加方法
fun String.shout(): String = this.uppercase() + "!!!"
fun String.repeat(n: Int): String = this.repeat(n)  // 注：Kotlin 标准库已有 repeat

fun Int.isPrime(): Boolean {
    if (this < 2) return false
    for (i in 2..Math.sqrt(this.toDouble()).toInt()) {
        if (this % i == 0) return false
    }
    return true
}

println("hello".shout())                    // HELLO!!!
println("7 是素数：${7.isPrime()}")          // true
println("12 是素数：${12.isPrime()}")        // false

// 扩展属性
val String.firstChar: Char get() = if (isNotEmpty()) this[0] else ' '
println("Kotlin 的首字母：${"Kotlin".firstChar}")

// --- 带接收者的 Lambda（类似 Groovy/DSL 风格）---
fun buildString(build: StringBuilder.() -> Unit): String {
    val sb = StringBuilder()
    sb.build()                               // 在 sb 上下文中执行
    return sb.toString()
}

val html = buildString {
    append("<div>")
    append("Hello")
    append("</div>")
}
println(html)                                // <div>Hello</div>

// 思考题：inline 函数的性能优势在什么场景下最明显？
//         扩展函数和成员函数在运行时有区别吗？能否被子类覆盖？

// ==============================================================================
// 第 3 题：类与对象（data class / sealed class / object / 伴生对象）
// ==============================================================================
// 知识点：
//   1. data class：自动生成 equals / hashCode / toString / copy / componentN。
//   2. sealed class（密封类）：限制子类在同一文件/模块内，when 可穷举覆盖。
//   3. object：单例声明，线程安全，无需手动实现单例模式。
//   4. companion object：类级别的常量和工厂方法，类似 Java static。
//   5. 枚举类：本质是密封类的特殊形式，可添加属性和方法。
// ==============================================================================

// --- data class ---
data class User(val name: String, val age: Int, val email: String? = null)

val u1 = User("Alice", 30, "alice@example.com")
val u2 = User("Alice", 30, "alice@example.com")
println(u1 == u2)                            // true（data class 自动生成 equals）

// copy：部分修改生成新实例
val u3 = u1.copy(age = 31)
println(u3)                                  // User(name=Alice, age=31, email=alice@example.com)

// 解构声明
val (n, a, e) = u1
println("解构：$n, $a, $e")

// --- sealed class：状态机建模 ---
sealed class UiState<out T> {
    object Loading : UiState<Nothing>()
    data class Success<T>(val data: T) : UiState<T>()
    data class Error(val message: String) : UiState<Nothing>()
}

// when 对密封类可穷举匹配，编译器检查完整性
fun <T> handleState(state: UiState<T>): String = when (state) {
    is UiState.Loading -> "加载中..."
    is UiState.Success -> "成功：${state.data}"
    is UiState.Error -> "错误：${state.message}"
    // 不需要 else 分支——编译器知道所有情况已覆盖
}

println(handleState(UiState.Loading))                    // 加载中...
println(handleState(UiState.Success("数据已加载")))       // 成功：数据已加载
println(handleState(UiState.Error("网络超时")))           // 错误：网络超时

// --- object：单例 ---
object AppConfig {
    val version = "1.0.0"
    val debug = true

    fun printConfig() {
        println("版本=$version, 调试模式=$debug")
    }
}
AppConfig.printConfig()                      // 版本=1.0.0, 调试模式=true

// object 表达式：匿名对象（类似 Java 匿名内部类）
val clickListener = object {
    fun onClick() = println("被点击了")
}
clickListener.onClick()

// --- companion object：类级别成员 ---
class Database {
    companion object {
        const val MAX_CONNECTIONS = 10

        // 工厂方法
        fun create(): Database = Database()

        fun defaultConfig(): Map<String, Any> = mapOf(
            "host" to "localhost",
            "port" to 5432,
            "maxConn" to MAX_CONNECTIONS
        )
    }

    fun connect() = println("数据库已连接")
}

println("最大连接数：${Database.MAX_CONNECTIONS}")
val db = Database.create()
db.connect()
println(Database.defaultConfig())

// --- 枚举类 ---
enum class HttpStatus(val code: Int, val description: String) {
    OK(200, "成功"),
    NOT_FOUND(404, "未找到"),
    SERVER_ERROR(500, "服务器错误");

    fun isSuccess() = code in 200..299
}

println("${HttpStatus.OK.code} - ${HttpStatus.OK.description}")   // 200 - 成功
println("是否成功：${HttpStatus.OK.isSuccess()}")                  // true
println("所有状态：${HttpStatus.values().joinToString { it.name }}")

// --- 类继承与接口 ---
interface Shape {
    fun area(): Double
    fun describe() = "形状面积为 ${area()}"   // 接口默认实现
}

open class Circle(val radius: Double) : Shape {
    override fun area() = Math.PI * radius * radius
}

class Square(val side: Double) : Shape {
    override fun area() = side * side
}

val shapes = listOf(Circle(5.0), Square(4.0))
shapes.forEach { println(it.describe()) }

// 思考题：data class 自动生成的方法有哪些？为什么普通 class 不自动生成？
//         sealed class 相比抽象类有什么优势？在 when 表达式中如何体现？

// ==============================================================================
// 第 4 题：协程（coroutine / suspend / Flow）
// ==============================================================================
// 知识点：
//   1. 协程是轻量级线程，挂起（suspend）时不阻塞线程，由调度器管理恢复。
//   2. suspend 函数：只能在协程或其他 suspend 函数中调用。
//   3. launch：启动不返回结果的协程（fire-and-forget）。
//      async：启动返回结果的协程，用 await 获取值。
//   4. Flow：协程版的冷数据流（类似 RxJava 的 Observable），按需生产数据。
//   5. withContext：切换协程上下文（如切换到 IO 线程），结束时自动切回。
// ==============================================================================
// 注意：以下代码需要 kotlinx-coroutines-core 依赖。
//       import kotlinx.coroutines.*
//       import kotlinx.coroutines.flow.*

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

// --- suspend 函数 ---
suspend fun fetchData(id: Int): String {
    delay(500)                        // 模拟网络延迟（挂起，不阻塞线程）
    return "数据 #$id"
}

// --- launch + async 基础 ---
fun coroutineBasic() = runBlocking {        // runBlocking：桥接阻塞世界与协程世界
    // launch：启动协程，返回 Job
    val job = launch {
        repeat(3) { i ->
            delay(200)
            println("launch 任务 $i 执行")
        }
    }

    // async：启动协程，返回 Deferred<T>，可 await
    val deferred1 = async { fetchData(1) }
    val deferred2 = async { fetchData(2) }

    // 并行执行后等待结果
    val result1 = deferred1.await()
    val result2 = deferred2.await()
    println("结果：$result1, $result2")

    job.join()                              // 等待 job 完成
}
coroutineBasic()

// --- withContext：线程切换 ---
suspend fun saveToDisk(data: String): String = withContext(Dispatchers.IO) {
    // 在 IO 线程执行
    delay(100)
    "已保存：$data"
}

// --- 异常处理与超时 ---
fun coroutineAdvanced() = runBlocking {
    // withTimeout：设置超时
    try {
        val result = withTimeout(1000) {
            fetchData(999)
        }
        println(result)
    } catch (e: TimeoutCancellationException) {
        println("请求超时")
    }

    // supervisorScope：子协程异常不会取消其他子协程
    supervisorScope {
        val child1 = launch {
            delay(100)
            throw RuntimeException("子协程1崩溃")
        }
        val child2 = launch {
            delay(200)
            println("子协程2正常完成")
        }
    }
}
coroutineAdvanced()

// --- Flow：冷数据流 ---
// 生产者定义数据流，消费者订阅后才执行
fun numberFlow(): Flow<Int> = flow {
    for (i in 1..5) {
        delay(300)                        // 模拟生产耗时
        emit(i)                           // 发射数据
    }
}

fun flowBasic() = runBlocking {
    // 收集 Flow
    numberFlow().collect { value ->
        println("收到：$value")
    }

    // Flow 操作符链
    val result = numberFlow()
        .map { it * it }                  // 变换：平方
        .filter { it > 4 }                // 过滤
        .toList()                         // 收集为列表
    println("Flow 处理结果：$result")      // [9, 16, 25]
}
flowBasic()

// --- Flow 进阶：背压与缓冲 ---
fun flowAdvanced() = runBlocking {
    // buffer：让生产和消费并行（不互相等待）
    val time1 = measureTimeMillis {
        numberFlow()
            .collect { value ->
                delay(300)                // 消费者处理慢
                println("处理：$value")
            }
    }

    // 使用 buffer 优化
    val time2 = measureTimeMillis {
        numberFlow()
            .buffer()                     // 添加缓冲区
            .collect { value ->
                delay(300)
                println("缓冲处理：$value")
            }
    }

    println("无缓冲：${time1}ms, 有缓冲：${time2}ms")

    // conflate：只保留最新值（跳过中间值）
    numberFlow()
        .conflate()
        .collect { println("conflate 收到：$it") }
}
flowAdvanced()

// --- StateFlow / SharedFlow（热数据流） ---
// 热流：无论有无消费者，数据持续流动
fun hotFlowDemo() = runBlocking {
    val state = MutableStateFlow(0)

    // 启动一个协程持续更新状态
    val job = launch {
        for (i in 1..3) {
            delay(200)
            state.value = i               // 更新状态
        }
    }

    // 收集状态变化
    state.collect { value ->
        println("StateFlow 当前值：$value")
        if (value == 3) cancel()          // 收到 3 后取消收集
    }

    job.join()
}
hotFlowDemo()

// 思考题：协程和线程有什么本质区别？为什么说协程是"轻量级"的？
//         Flow 的冷流和热流（StateFlow/SharedFlow）有什么区别？各自适合什么场景？

// ==============================================================================
// 第 5 题：集合操作（序列 / 操作符 / 函数式编程）
// ==============================================================================
// 知识点：
//   1. Kotlin 集合分只读（List/Set/Map）和可变（MutableList/MutableSet/MutableMap）。
//   2. Sequence（序列）：惰性求值，类似 Java Stream，中间操作不立即执行。
//   3. 常用操作符：map / filter / reduce / fold / flatMap / groupBy / chunked / windowed。
//   4. 函数式风格：组合操作符完成数据处理管线，代码声明式、可读性强。
//   5. asSequence() vs List 操作链：大量数据时 Sequence 更高效（减少中间集合）。
// ==============================================================================

// --- 集合基础 ---
val fruits = listOf("apple", "banana", "cherry", "date", "elderberry")

// 只读集合操作
println("长度：${fruits.size}")
println("首元素：${fruits.first()}")
println("末元素：${fruits.last()}")
println("包含 banana：${fruits.contains("banana")}")

// 可变集合
val mutableList = mutableListOf(1, 2, 3)
mutableList.add(4)
mutableList.removeAt(0)
println("可变列表：$mutableList")          // [2, 3, 4]

// --- 核心操作符 ---
val numbers = (1..10).toList()

// map：变换
val squared = numbers.map { it * it }
println("平方：$squared")

// filter：过滤
val evens = numbers.filter { it % 2 == 0 }
println("偶数：$evens")

// 组合链：过滤 → 映射 → 排序
val processed = numbers
    .filter { it % 2 == 1 }              // 奇数
    .map { it * 10 }                      // 乘 10
    .sortedDescending()                   // 降序
println("处理链：$processed")             // [90, 70, 50, 30, 10]

// reduce：归约（无初始值）
val product = numbers.take(5).reduce { acc, n -> acc * n }
println("前5个数的积：$product")           // 120

// fold：归约（带初始值）
val sumWithInit = numbers.take(5).fold(100) { acc, n -> acc + n }
println("fold 结果：$sumWithInit")        // 115

// --- flatMap：展平嵌套 ---
val nested = listOf(listOf(1, 2), listOf(3, 4), listOf(5))
val flat = nested.flatten()
println("展平：$flat")                     // [1, 2, 3, 4, 5]

val sentences = listOf("Hello World", "Kotlin Programming")
val words = sentences.flatMap { it.split(" ") }
println("分词：$words")                    // [Hello, World, Kotlin, Programming]

// --- groupBy：分组 ---
data class Person(val name: String, val city: String, val age: Int)

val people = listOf(
    Person("Alice", "Beijing", 30),
    Person("Bob", "Shanghai", 25),
    Person("Charlie", "Beijing", 35),
    Person("Diana", "Shanghai", 28),
    Person("Eve", "Beijing", 22)
)

val byCity = people.groupBy { it.city }
println("按城市分组：")
byCity.forEach { (city, group) ->
    println("  $city: ${group.map { it.name }}")
}

// partition：分成两组
val (adults, young) = people.partition { it.age >= 30 }
println("30岁以上：${adults.map { it.name }}, 30岁以下：${young.map { it.name }}")

// --- chunked / windowed ---
val range = (1..10).toList()

// chunked：分块
println("分块：${range.chunked(3)}")       // [[1,2,3], [4,5,6], [7,8,9], [10]]

// windowed：滑动窗口
println("窗口：${range.windowed(3, step = 2)}")  // [[1,2,3], [3,4,5], [5,6,7], [7,8,9], [9,10]]
// 注意：最后一个窗口不足3个元素时，部分包含

// --- Sequence：惰性求值 ---
// asSequence 把 List 转为 Sequence，中间操作不创建中间集合
val seqResult = (1..1_000_000)
    .asSequence()
    .filter { it % 2 == 0 }              // 惰性：不立即执行
    .map { it * it }                      // 惰性
    .take(5)                              // 只取前 5 个
    .toList()                             // 终端操作触发执行
println("Sequence 结果：$seqResult")      // [4, 16, 36, 64, 100]

// --- 实战：综合函数式数据处理 ---
data class Order(val id: Int, val customer: String, val amount: Double, val category: String)

val orders = listOf(
    Order(1, "Alice", 100.0, "Books"),
    Order(2, "Bob", 250.0, "Electronics"),
    Order(3, "Alice", 50.0, "Books"),
    Order(4, "Charlie", 300.0, "Electronics"),
    Order(5, "Bob", 75.0, "Clothing"),
    Order(6, "Alice", 200.0, "Electronics")
)

// 统计每位客户的总消费
val totalByCustomer = orders
    .groupBy { it.customer }
    .mapValues { (_, orders) -> orders.sumOf { it.amount } }
println("客户消费统计：$totalByCustomer")

// 按类别统计订单数和总金额
val statsByCategory = orders
    .groupBy { it.category }
    .mapValues { (_, orders) ->
        mapOf(
            "count" to orders.size,
            "total" to orders.sumOf { it.amount }
        )
    }
println("类别统计：$statsByCategory")

// 找出消费最高的客户
val topCustomer = orders
    .groupBy { it.customer }
    .maxByOrNull { (_, orders) -> orders.sumOf { it.amount } }
    ?.key
println("消费最高的客户：$topCustomer")

// 每个类别中金额最大的订单
val maxOrderPerCategory = orders
    .groupBy { it.category }
    .mapValues { (_, orders) -> orders.maxByOrNull { it.amount } }
println("各类别最大订单：")
maxOrderPerCategory.forEach { (cat, order) ->
    println("  $cat: 订单#${order?.id}, 金额 ${order?.amount}")
}

// 思考题：List 操作链和 Sequence 操作链在性能上有什么区别？
//         什么场景下应该用 asSequence()？什么场景下用普通 List 链更合适？
