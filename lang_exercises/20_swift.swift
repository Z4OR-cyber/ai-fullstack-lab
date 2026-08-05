// ==============================================================================
// 阶段：Swift 编程练习
// 题数：5
// 创建日期：2026-08-05
// 说明：由浅入深，覆盖 Swift 核心特性——从基础语法到泛型与错误处理
// ==============================================================================

import Foundation

// ==============================================================================
// 第 1 题：Swift 基础（变量类型 / Optional / 字符串）
// ==============================================================================
// 知识点：
//   1. var 声明可变变量，let 声明常量（值不可再赋值）。类型可自动推断。
//   2. Optional（可选类型）是 Swift 最重要的安全特性：用 T? 表示可能为 nil 的值。
//      Optional 本质是枚举：enum Optional<T> { case none; case some(T) }。
//   3. 解包方式：if let（条件绑定）、guard let（提前退出）、??（空合运算符）、!（强制解包）。
//   4. 字符串插值用 \(变量名)，String 是值类型（struct），赋值和传参时是拷贝语义。
//   5. 隐式解包可选（T!）：访问时自动解包，但仍可能为 nil 导致崩溃，慎用。
// ==============================================================================

// --- 变量与常量 ---
var score: Int = 90            // 显式类型
let pi = 3.14159               // 类型推断为 Double
var greeting = "Hello"         // 类型推断为 String
greeting += ", Swift"          // var 可修改

// --- Optional 基础 ---
var name: String? = "Alice"    // 可选类型，可能为 nil
print(name)                    // Optional("Alice")

// 条件绑定（if let）
if let unwrapped = name {
    print("名字是 \(unwrapped)")   // 名字是 Alice
} else {
    print("没有名字")
}

// guard let：提前退出（适合函数中减少嵌套）
func printName(_ n: String?) {
    guard let n = n else {
        print("名字为空")
        return
    }
    print("名字确认：\(n)")
}
printName(nil)                 // 名字为空
printName("Bob")               // 名字确认：Bob

// 空合运算符 ??
let displayName = name ?? "匿名"
print(displayName)             // Alice

name = nil
let fallback = name ?? "匿名"
print(fallback)                // 匿名

// 强制解包（!）：确信非 nil 时使用，否则崩溃
var age: Int? = 25
print(age!)                    // 25

// 可选链（Optional Chaining）：链式调用中任意环节为 nil 则整条返回 nil
struct User {
    var profile: Profile?
}
struct Profile {
    var email: String
}
let user = User(profile: Profile(email: "test@example.com"))
print(user.profile?.email ?? "无邮箱")    // test@example.com

let emptyUser = User(profile: nil)
print(emptyUser.profile?.email ?? "无邮箱") // 无邮箱

// --- 字符串操作 ---
let str = "Hello, Swift"
let count = str.count                       // 字符数（不是字节数）
let upper = str.uppercased()
let parts = str.split(separator: ", ")      // 返回 [Substring]
print("长度=\(count), 大写=\(upper), 分割=\(parts)")

// 多行字符串
let multi = """
第一行
第二行
第三行
"""
print(multi)

// 思考题：Optional 的本质是什么？为什么 Swift 要引入 Optional？
//         if let 和 guard let 分别适合什么场景？

// ==============================================================================
// 第 2 题：值类型与引用类型（struct-vs-class / mutating / 值语义）
// ==============================================================================
// 知识点：
//   1. struct 是值类型：赋值/传参时发生拷贝，互不影响。
//      class  是引用类型：赋值/传参时共享同一引用，修改互相影响。
//   2. struct 的方法默认不能修改自身属性，需用 mutating 关键字声明。
//   3. 值类型的好处：线程安全、无共享状态、推理简单。Apple 推荐"优先用 struct"。
//   4. struct 的 mutating 方法：当 struct 被声明为 let 常量时，无法调用 mutating 方法。
//   5. 引用相等用 ===（同一对象），值相等用 ==（需遵守 Equatable）。
// ==============================================================================

// --- struct（值类型）---
struct Point {
    var x: Double
    var y: Double

    // 非 mutating 方法：只读
    func distance(to other: Point) -> Double {
        let dx = x - other.x
        let dy = y - other.y
        return (dx * dx + dy * dy).squareRoot()
    }

    // mutating 方法：修改自身属性
    mutating func moveBy(dx: Double, dy: Double) {
        x += dx
        y += dy
    }
}

var p1 = Point(x: 0, y: 0)
var p2 = p1              // 拷贝：p2 是独立的副本
p1.moveBy(dx: 3, dy: 4)  // 只改了 p1
print("p1=(\(p1.x), \(p1.y))")   // (3.0, 4.0)
print("p2=(\(p2.x), \(p2.y))")   // (0.0, 0.0) —— 不受影响

let dist = p1.distance(to: p2)
print("距离 = \(dist)")           // 5.0

// --- class（引用类型）---
class Counter {
    var count: Int = 0

    func increment() {
        count += 1            // class 方法无需 mutating
    }

    func reset() {
        count = 0
    }
}

let c1 = Counter()
let c2 = c1              // 共享引用：c2 和 c1 指向同一对象
c1.increment()
print(c2.count)          // 1 —— c2 也看到了变化（引用共享）

// --- 值语义 vs 引用语义对比 ---
struct ValueType {
    var data: [Int]
}
class RefType {
    var data: [Int]
    init(_ data: [Int]) { self.data = data }
}

var v1 = ValueType(data: [1, 2, 3])
var v2 = v1
v2.data.append(4)
print(v1.data)           // [1, 2, 3] —— 值拷贝，互不影响

var r1 = RefType([1, 2, 3])
var r2 = r1
r2.data.append(4)
print(r1.data)           // [1, 2, 3, 4] —— 引用共享

// --- 遵守 Equatable 协议 ---
extension Point: Equatable {
    static func == (lhs: Point, rhs: Point) -> Bool {
        lhs.x == rhs.x && lhs.y == rhs.y
    }
}
print(Point(x: 1, y: 2) == Point(x: 1, y: 2))   // true（值相等）
print(c1 === c2)                                  // true（引用相等）

// 思考题：为什么 Apple 建议"优先用 struct"？
//         如果 struct 中包含 class 类型的属性，它还是纯粹的值语义吗？

// ==============================================================================
// 第 3 题：协议与面向协议编程（protocol / extension / 默认实现）
// ==============================================================================
// 知识点：
//   1. 协议（Protocol）定义方法/属性的蓝图，类似 Java 接口但更强大。
//   2. protocol extension 可提供默认实现，实现面向协议编程（POP）的核心。
//   3. 协议可作为类型使用：数组元素类型、函数参数类型等。
//   4. 协议可组合：用 & 组合多个协议要求，如 Drivable & Flyable。
//   5. associatedtype：协议中的关联类型，让协议具备泛型能力（下一题深入）。
// ==============================================================================

// --- 定义协议 ---
protocol Describable {
    var description: String { get }
}

protocol Comparable2 {
    func isGreaterThan(_ other: Self) -> Bool   // Self 指代实现类型
}

// --- 协议扩展：默认实现 ---
extension Describable {
    // 提供默认实现，遵守者可覆盖
    var description: String {
        "默认描述"
    }

    func printDescription() {
        print("【描述】\(description)")
    }
}

// --- 实现 ---
struct Product: Describable, Comparable2 {
    let name: String
    let price: Double

    // 覆盖默认的 description
    var description: String {
        "\(name) - ¥\(price)"
    }

    func isGreaterThan(_ other: Product) -> Bool {
        price > other.price
    }
}

let laptop = Product(name: "MacBook", price: 9999)
let phone = Product(name: "iPhone", price: 5999)
laptop.printDescription()              // 【描述】MacBook - ¥9999.0
print(laptop.isGreaterThan(phone))     // true

// --- 协议作为类型 ---
let items: [Describable] = [
    Product(name: "键盘", price: 299),
    Product(name: "鼠标", price: 99)
]

for item in items {
    item.printDescription()
}

// --- 协议组合 ---
protocol Serializable {
    func serialize() -> String
}

protocol Cacheable {
    func cacheKey() -> String
}

// 用 & 组合两个协议
func process<T: Describable & Serializable>(_ item: T) {
    print("处理：\(item.description), 序列化：\(item.serialize())")
}

struct Article: Describable, Serializable {
    let title: String

    var description: String { title }
    func serialize() -> String { "{\"title\":\"\(title)\"}" }
}

process(Article(title: "Swift POP 实战"))

// --- 面向协议编程示例：为协议添加条件扩展 ---
extension Collection where Element: Describable {
    func describeAll() -> String {
        map { $0.description }.joined(separator: "\n")
    }
}

let products: [Product] = [
    Product(name: "充电器", price: 59),
    Product(name: "数据线", price: 39)
]
print(products.describeAll())

// 思考题：协议扩展的默认实现和基类继承有什么区别？
//         面向协议编程（POP）相比面向对象编程（OOP）有什么优势？

// ==============================================================================
// 第 4 题：泛型与关联类型（泛型函数 / 类型约束 / 关联类型）
// ==============================================================================
// 知识点：
//   1. 泛型函数：<T> 声明类型参数，调用时自动推断具体类型。
//   2. 类型约束：<T: SomeProtocol> 限制 T 必须遵守某协议或继承某类。
//   3. 关联类型（associatedtype）：协议中的"占位类型"，由实现者具体化。
//   4. 泛型类型：自定义泛型 struct/class/enum。
//   5. where 子句：对泛型参数施加更精细的约束。
// ==============================================================================

// --- 泛型函数 ---
func swapValues<T>(_ a: inout T, _ b: inout T) {
    let temp = a
    a = b
    b = temp
}

var x = 10
var y = 20
swapValues(&x, &y)
print("x=\(x), y=\(y)")         // x=20, y=10

var s1 = "A"
var s2 = "B"
swapValues(&s1, &s2)
print("s1=\(s1), s2=\(s2)")     // s1=B, s2=A

// --- 类型约束：要求 T 必须遵守 Comparable ---
func findMax<T: Comparable>(_ array: [T]) -> T? {
    guard !array.isEmpty else { return nil }
    var maxVal = array[0]
    for element in array.dropFirst() {
        if element > maxVal {
            maxVal = element
        }
    }
    return maxVal
}

print(findMax([3, 7, 2, 9, 1])!)         // 9
print(findMax(["banana", "apple", "cherry"])!)  // cherry

// --- 泛型类型：自定义栈 ---
struct Stack<T> {
    private var items: [T] = []

    mutating func push(_ item: T) {
        items.append(item)
    }

    mutating func pop() -> T? {
        items.popLast()
    }

    var peek: T? {
        items.last
    }

    var isEmpty: Bool {
        items.isEmpty
    }
}

var intStack = Stack<Int>()
intStack.push(1)
intStack.push(2)
intStack.push(3)
print(intStack.pop()!)           // 3
print(intStack.peek!)            // 2

var stringStack = Stack<String>()
stringStack.push("Hello")
print(stringStack.pop()!)        // Hello

// --- 关联类型 ---
protocol Container {
    associatedtype Item           // 关联类型：由实现者确定
    var count: Int { get }
    mutating func append(_ item: Item)
    subscript(i: Int) -> Item { get }
}

// 用泛型类型实现带关联类型的协议
class GenericContainer<T>: Container {
    typealias Item = T            // 明确关联类型为 T

    private var storage: [T] = []

    var count: Int { storage.count }

    func append(_ item: T) {
        storage.append(item)
    }

    subscript(i: Int) -> T {
        storage[i]
    }
}

let container = GenericContainer<Int>()
container.append(10)
container.append(20)
container.append(30)
print("容器大小：\(container.count)")   // 3
print("索引1：\(container[1])")          // 20

// --- where 子句：对关联类型施加约束 ---
extension Container where Item: Numeric {
    func sum() -> Item {
        var total: Item = 0
        for i in 0..<count {
            total += self[i]
        }
        return total
    }
}

let numContainer = GenericContainer<Int>()
numContainer.append(1)
numContainer.append(2)
numContainer.append(3)
print("总和：\(numContainer.sum())")     // 6

// 思考题：关联类型和泛型参数有什么区别？各自适合什么场景？
//         where 子句解决了什么问题？

// ==============================================================================
// 第 5 题：错误处理（throws / try-catch / Result / defer）
// ==============================================================================
// 知识点：
//   1. Swift 错误用遵守 Error 协议的枚举表示，语义清晰。
//   2. throwing 函数用 throws 标记，调用时用 try（配合 do-catch 或 ?/!）。
//   3. try?：将错误转为 Optional（成功返回值，失败返回 nil）。
//      try!：断言不会出错，出错则崩溃。
//   4. Result<Success, Failure> 枚举：把成功/失败作为值传递，适合异步回调场景。
//   5. defer：无论是否出错，退出当前作用域时都会执行的清理代码。
// ==============================================================================

// --- 定义错误类型 ---
enum FileError: Error {
    case fileNotFound(String)
    case permissionDenied
    case invalidFormat(reason: String)
}

// --- throwing 函数 ---
func readFile(atPath path: String) throws -> String {
    // 模拟文件读取
    if path.isEmpty {
        throw FileError.fileNotFound(path)
    }
    if path.contains("secret") {
        throw FileError.permissionDenied
    }
    return "文件内容：\(path) 的数据"
}

// --- do-catch 处理 ---
do {
    let content = try readFile(atPath: "data.txt")
    print(content)
} catch FileError.fileNotFound(let path) {
    print("文件未找到：\(path)")
} catch FileError.permissionDenied {
    print("权限不足")
} catch {
    print("未知错误：\(error)")
}

// --- try? 和 try! ---
let result1 = try? readFile(atPath: "")          // nil（失败转 Optional）
print(result1 ?? "读取失败")                      // 读取失败

let result2 = try? readFile(atPath: "config.txt")
print(result2 ?? "读取失败")                      // 文件内容：config.txt 的数据

// try!：确定不会出错时使用，出错则崩溃（仅用于确信安全的场景）
// let risky = try! readFile(atPath: "")  // 会崩溃，不推荐随意使用

// --- Result 类型 ---
func fetchUser(id: Int) -> Result<String, FileError> {
    if id <= 0 {
        return .failure(.invalidFormat(reason: "ID 必须为正数"))
    }
    return .success("用户 #\(id)")
}

let userResult = fetchUser(id: 42)
switch userResult {
case .success(let user):
    print("成功：\(user)")
case .failure(let error):
    print("失败：\(error)")
}

// Result 的链式处理
let mapped = fetchUser(id: -1)
    .map { $0.uppercased() }
    .mapError { $0 }
switch mapped {
case .success(let value):
    print("映射后：\(value)")
case .failure(let error):
    print("映射失败：\(error)")       // invalidFormat
}

// --- defer：资源清理 ---
func processFile(path: String) {
    print("打开文件：\(path)")
    var fileHandle: Int? = 42         // 模拟文件句柄

    defer {
        // 无论函数从哪里返回（正常/异常），都会执行
        if fileHandle != nil {
            print("关闭文件句柄")
            fileHandle = nil
        }
    }

    do {
        let content = try readFile(atPath: path)
        print("处理内容：\(content)")
    } catch {
        print("读取失败：\(error)")
        // 即使出错，defer 也会执行
    }
    // 函数结束时 defer 自动执行
}

processFile(path: "secret/data.txt")
// 输出：
// 打开文件：secret/data.txt
// 读取失败：permissionDenied
// 关闭文件句柄

// --- 多个 defer 的执行顺序（LIFO：后进先出）---
func multiDefer() {
    defer { print("第一个 defer（最后执行）") }
    defer { print("第二个 defer（先执行）") }
    defer { print("第三个 defer（最先执行）") }
    print("函数主体")
}

multiDefer()
// 输出：
// 函数主体
// 第三个 defer（最先执行）
// 第二个 defer（先执行）
// 第一个 defer（最后执行）

// --- 实战：结合 Result + defer 的资源管理 ---
func safeOperation() -> Result<Int, FileError> {
    print("=== 开始安全操作 ===")
    var resource: String? = "已分配资源"

    defer {
        print("清理资源")
        resource = nil
    }

    // 模拟可能失败的操作
    let success = Bool.random()
    if success {
        return .success(200)
    } else {
        return .failure(.permissionDenied)
    }
}

let op = safeOperation()
switch op {
case .success(let code):
    print("操作成功，代码：\(code)")
case .failure(let error):
    print("操作失败：\(error)")
}

// 思考题：Result 和 throws 有什么各自的使用场景？
//         defer 的 LIFO 执行顺序有什么实际意义？
