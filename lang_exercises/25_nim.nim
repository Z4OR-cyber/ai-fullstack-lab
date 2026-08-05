# ============================================================
# 阶段：脚本语言与系统级语言扩展练习
# 语言：Nim
# 题数：3题
# 创建日期：2026-08-05
# ============================================================

import strutils, sequtils, tables, macros

# ============================================================
# 第1题：Nim基础（变量 / 过程 / 类型 / 宏概念）
# ============================================================

# 【知识点讲解】
# Nim是一种静态类型的系统级编程语言，语法受Python影响，性能接近C。
# Nim兼具脚本语言的简洁和编译型语言的性能，编译为C/C/JavaScript。
# 变量声明用var（可变）、let（不可变）、const（编译期常量）。
# 过程（procedure）是Nim的函数，用proc关键字定义。
# Nim支持自定义类型、枚举、对象等丰富的类型系统。

# 1. 变量声明
proc basicVariables() =
  echo "=== 变量与类型 ==="

  # 可变变量
  var name: string = "Nim学习者"
  var age: int = 25
  var pi: float = 3.14159
  var isActive: bool = true

  # 类型推断（省略类型）
  var city = "北京"
  var count = 42

  # 不可变变量（let）
  let greeting = "你好，" & name
  # greeting = "修改"  # 编译错误：let不可重新赋值

  # 编译期常量（const）
  const gravity: float = 9.8

  echo "  name: ", name, ", age: ", age
  echo "  city: ", city, ", pi: ", pi
  echo "  greeting: ", greeting
  echo "  gravity(const): ", gravity

  # 多重赋值（元组交换）
  var (x, y) = (10, 20)
  echo "  交换前: x=", x, ", y=", y
  (x, y) = (y, x)
  echo "  交换后: x=", x, ", y=", y

# 2. 过程（函数）
proc add(a, b: int): int =
  result = a + b

# 默认参数
proc greet(name: string, greeting: string = "你好"): string =
  result = greeting & "，" & name & "！"

# 可变参数（使用varargs）
proc sumAll(nums: varargs[int]): int =
  for n in nums:
    result += n

# 过程作为值传递
proc apply(f: proc(x: int): int, value: int): int =
  f(value)

proc higherOrderDemo() =
  echo "\n=== 过程特性 ==="

  echo "  add(3, 4) = ", add(3, 4)
  echo "  greet(\"张三\") = ", greet("张三")
  echo "  greet(\"李四\", \"早上好\") = ", greet("李四", "早上好")
  echo "  sumAll(1,2,3,4,5) = ", sumAll(1, 2, 3, 4, 5)

  # 匿名过程
  let double = proc(x: int): int = x * 2
  echo "  double(5) = ", apply(double, 5)

  # 方法调用语法（UCS - Uniform Call Syntax）
  let nums = [1, 2, 3, 4, 5]
  echo "  nums.len = ", len(nums)   # 函数式调用
  echo "  nums.len = ", nums.len     # 方法式调用

# 3. 类型系统
# 枚举
type
  Color = enum
    cRed, cGreen, cBlue

  HttpStatus = enum
    httpOk = 200, httpNotFound = 404, httpError = 500

  # 对象
  Person = object
    name: string
    age: int
    email: string

  # 可变对象（引用语义）
  Account = ref object
    id: int
    balance: float

  # distinct类型：类型安全的新类型
  UserId = distinct int

proc typeSystemDemo() =
  echo "\n=== 类型系统 ==="

  # 枚举
  let color = cBlue
  echo "  颜色: ", color, " (序号: ", ord(color), ")"

  let status = httpNotFound
  echo "  HTTP状态: ", status, " (", ord(status), ")"

  # 对象
  var p = Person(name: "王五", age: 30, email: "wangwu@test.com")
  echo "  Person: ", p.name, ", ", p.age, "岁"

  # 修改字段
  p.age = 31
  echo "  修改后年龄: ", p.age

  # 引用对象
  var acc = Account(id: 1, balance: 1000.0)
  acc.balance += 500.0
  echo "  Account余额: ", acc.balance

  # distinct类型
  var uid = UserId(42)
  # uid + 1  # 编译错误：distinct类型不能直接运算
  echo "  UserId: ", int(uid)

# 4. 序列和表（集合类型）
proc collectionsDemo() =
  echo "\n=== 集合类型 ==="

  # 序列（seq）- 动态数组
  var nums: seq[int] = @[]
  nums.add(10)
  nums.add(20)
  nums.add(30)
  echo "  seq: ", nums

  # 序列构建（循环方式）
  var squares: seq[int] = @[]
  for n in 1..5:
    squares.add(n * n)
  echo "  平方序列: ", squares

  # 过滤与映射
  let evens = filter(squares, proc(x: int): bool = x mod 2 == 0)
  echo "  偶数平方: ", evens

  let doubled = map(squares, proc(x: int): int = x * 2)
  echo "  翻倍平方: ", doubled

  # Table（哈希表）
  var scores = initTable[string, int]()
  scores["数学"] = 90
  scores["语文"] = 85
  scores["英语"] = 92

  echo "  Table项数: ", scores.len
  for k, v in scores.pairs:
    echo "    ", k, ": ", v

  # 遍历序列带索引
  echo "  带索引遍历:"
  for i, v in nums:
    echo "    [", i, "] = ", v

# 5. 字符串处理
proc stringDemo() =
  echo "\n=== 字符串处理 ==="

  let s = "Hello, Nim World!"
  echo "  原文: ", s
  echo "  长度: ", s.len
  echo "  大写: ", s.toUpper()
  echo "  小写: ", s.toLower()
  echo "  包含'Nim': ", "Nim" in s
  echo "  分割: ", s.split(", ")
  echo "  替换: ", s.replace("World", "编程")

  # 字符串格式化（拼接方式）
  let name = "张三"
  let age = 25
  echo "  格式化: " & name & "今年" & $age & "岁"

# 【思考题】
# 1. Nim的 var、let、const 三种变量声明方式的区别是什么？分别在什么场景下使用？
# 2. Nim的 UCS（Uniform Call Syntax）特性带来了什么好处？它如何模糊了函数和方法的界限？

# ============================================================
# 第2题：元编程（模板 / 宏 / AST）
# ============================================================

# 【知识点讲解】
# Nim的元编程能力是其最强大的特性之一，远超大多数编程语言。
# 模板（template）：编译期文本替换，零运行时开销，类似C的宏但更安全。
# 宏（macro）：操作AST（抽象语法树），可以在编译时生成代码。
# Nim的AST通过NimNode类型表示，宏可以检查和构建AST节点。
# 元编程使得Nim可以创造新的语法结构和DSL（领域特定语言）。

# 1. 模板基础
template `:=`(name, value: untyped): untyped =
  # 自定义赋值操作符：声明并赋值
  var name = value

template unless(cond: typed, body: untyped): untyped =
  # unless：反向if
  if not cond:
    body

template swap(a, b: untyped): untyped =
  # 交换两个变量的值
  let tmp = a
  a = b
  b = tmp

proc templateDemo() =
  echo "=== 模板基础 ==="

  # 使用自定义 := 操作符
  x := 42
  y := "Hello"
  echo "  x = ", x, ", y = ", y

  # 使用 unless
  let flag = false
  unless flag:
    echo "  flag为false时执行"

  # 使用 swap
  var a = 10
  var b = 20
  echo "  交换前: a=", a, ", b=", b
  swap(a, b)
  echo "  交换后: a=", a, ", b=", b

# 2. 模板与代码生成
template repeatIt(n: int, body: untyped): untyped =
  # 类似Ruby的n.times，注入it变量
  for i in 0 ..< n:
    let it {.inject.} = i
    body

template debug(args: varargs[typed]): untyped =
  # 编译时条件调试输出
  when defined(debug):
    echo "  [DEBUG] ", args

proc templateCodeGenDemo() =
  echo "\n=== 模板代码生成 ==="

  # 使用repeatIt
  repeatIt(3):
    echo "  第", it, "次迭代"

  # 编译时条件
  debug("这是一条调试信息")

  # when编译时分支
  when sizeof(int) == 8:
    echo "  64位系统"
  else:
    echo "  32位系统"

# 3. 宏基础：AST操作
macro echoAst(node: typed): untyped =
  # 打印AST结构（开发调试用）
  echo "  AST树形结构:"
  echo treeRepr(node)
  result = node  # 原样返回

macro defineGetter(typeName: typedesc, fieldName: untyped): untyped =
  # 宏：自动生成getter方法
  let getterName = ident("get" & $fieldName)
  let selfParam = ident("self")
  quote do:
    proc `getterName`(`selfParam`: `typeName`): auto =
      `selfParam`.`fieldName`

proc macroDemo() =
  echo "\n=== 宏基础 ==="

  type
    Point = object
      x, y: float

  # 使用宏生成getter
  defineGetter(Point, x)

  let p = Point(x: 3.0, y: 4.0)
  echo "  Point.x = ", getx(p)

# 4. 宏实战：JSON序列化概念
macro serializeFields(objIdent: typed): untyped =
  # 概念演示：自动遍历对象字段生成序列化代码
  let objType = objIdent.getType()
  result = quote do:
    var parts: seq[string] = @[]
    # 实际宏实现会遍历类型定义生成字段访问代码
    parts.add("\"type\": \"" & $typeof(`objIdent`) & "\"")
    result = "{" & parts.join(", ") & "}"

proc macroSerializeDemo() =
  echo "\n=== 宏实战 ==="

  type
    User = object
      id: int
      name: string
      active: bool

  let u = User(id: 1, name: "张三", active: true)
  echo "  手动序列化: id=", u.id, ", name=", u.name, ", active=", u.active

# 5. 编译期计算
const computedValue = block:
  var s = 0
  for i in 1..100:
    s += i
  s

proc staticPower(base: static[int], exp: static[int]): int =
  var r = 1
  for i in 1..exp:
    r *= base
  r

proc compileTimeDemo() =
  echo "\n=== 编译期计算 ==="
  echo "  1到100的和(const) = ", computedValue

  const pow = staticPower(2, 10)
  echo "  2^10(const) = ", pow

# 【思考题】
# 1. 模板（template）和宏（macro）的核心区别是什么？各自适合什么场景？
# 2. Nim的AST操作与Lisp的宏系统有何异同？为什么说宏是Nim最强大的特性？

# ============================================================
# 第3题：系统编程（指针 / 内存管理 / FFI概念）
# ============================================================

# 【知识点讲解】
# Nim虽然是高级语言，但完全支持底层系统编程。
# Nim的内存管理：支持GC（默认）、ARC（自动引用计数）、ORC、手动管理。
# 指针操作：ptr类型（非空指针）、pointer类型（裸指针）。
# FFI（外部函数接口）：Nim可以直接调用C库，通过 {.importc.} 和 {.cdecl.} 等编译指示。
# Nim编译为C，因此可以无缝与C生态集成。

# 1. 指针操作
proc pointerDemo() =
  echo "=== 指针操作 ==="

  var x: int = 42
  var p: ptr int = addr(x)  # 取地址

  echo "  x的值: ", x
  echo "  p指向的值: ", p[]

  # 通过指针修改
  p[] = 100
  echo "  通过指针修改后: x = ", x

  # 裸指针（无类型指针）
  var rawPtr: pointer = addr(x)
  echo "  裸指针地址: ", cast[int](rawPtr)

  # 类型转换指针
  var intPtr = cast[ptr int](rawPtr)
  echo "  转换回int指针: ", intPtr[]

# 2. 内存管理策略
type
  HeapObj = ref object
    value: int
    label: string

proc memoryManagementDemo() =
  echo "\n=== 内存管理 ==="

  # 栈分配（值类型）
  var stackVar: int = 10
  echo "  栈变量: ", stackVar

  # 堆分配（使用new，由GC管理）
  var heapObj = HeapObj(value: 42, label: "堆对象")
  echo "  堆对象: ", heapObj.label, " = ", heapObj.value

  # 手动内存管理（alloc/free）
  var buf = alloc(100)  # 分配100字节
  var intBuf = cast[ptr int](buf)
  intBuf[] = 12345
  echo "  手动分配内存中的值: ", intBuf[]
  dealloc(buf)  # 必须手动释放
  echo "  手动内存已释放"

# 3. 对象变体（类似C的union）
type
  ShapeKind = enum
    skCircle, skRectangle, skTriangle

  Shape = object
    case kind: ShapeKind
    of skCircle:
      radius: float
    of skRectangle:
      width, height: float
    of skTriangle:
      base, triHeight: float

proc area(s: Shape): float =
  case s.kind
  of skCircle:
    result = 3.14159 * s.radius * s.radius
  of skRectangle:
    result = s.width * s.height
  of skTriangle:
    result = 0.5 * s.base * s.triHeight

proc unionDemo() =
  echo "\n=== 对象变体（union）==="

  let circle = Shape(kind: skCircle, radius: 5.0)
  let rect = Shape(kind: skRectangle, width: 4.0, height: 6.0)
  let tri = Shape(kind: skTriangle, base: 3.0, triHeight: 8.0)

  echo "  圆形面积: ", area(circle)
  echo "  矩形面积: ", area(rect)
  echo "  三角形面积: ", area(tri)

# 4. FFI概念演示：调用C函数
# Nim可以直接声明并调用C标准库函数

# 声明C函数（FFI）
proc cPrintf(format: cstring): cint {.importc: "printf", header: "<stdio.h>", varargs.}
proc cSqrt(x: cdouble): cdouble {.importc: "sqrt", header: "<math.h>".}

proc ffiDemo() =
  echo "\n=== FFI（外部函数接口）==="

  # 直接调用C的printf
  discard cPrintf("  C printf: %d + %d = %d\n".cstring, 10, 20, 30)

  # 调用C的sqrt
  let result = cSqrt(144.0)
  echo "  C sqrt(144) = ", result

  # 概念说明：Nim调用C库的方式
  echo "\n  FFI概念说明:"
  echo "  1. {.importc: \"函数名\", header: \"头文件\".} 声明C函数"
  echo "  2. {.cdecl.} 指定C调用约定"
  echo "  3. {.stdcall.} 指定Windows API调用约定"
  echo "  4. cstring, cint, cdouble等是C兼容类型"
  echo "  5. 编译时用 --passC / --passL 传递链接选项"

# 5. 位操作与底层控制
proc bitwiseDemo() =
  echo "\n=== 位操作 ==="

  let a: uint8 = 0b11001100
  let b: uint8 = 0b10101010

  echo "  a = 0b", toBin(a, 8)
  echo "  b = 0b", toBin(b, 8)
  echo "  a AND b = 0b", toBin(a and b, 8)
  echo "  a OR b  = 0b", toBin(a or b, 8)
  echo "  a XOR b = 0b", toBin(a xor b, 8)
  echo "  NOT a   = 0b", toBin((not a) and 0xFF, 8)
  echo "  a SHL 2 = 0b", toBin(a shl 2, 8)

  # 位域操作
  var flags: uint8 = 0
  flags = flags or 0b00000001  # 设置第0位
  flags = flags or 0b00000100  # 设置第2位
  echo "  flags = 0b", toBin(flags, 8)
  echo "  第0位: ", (flags and 1) != 0
  echo "  第1位: ", (flags and 2) != 0
  echo "  第2位: ", (flags and 4) != 0

  # 清除位
  flags = flags and (not 0b00000001'u8)
  echo "  清除第0位后: 0b", toBin(flags, 8)

# 6. 内存安全与GC控制
proc gcControlDemo() =
  echo "\n=== GC控制 ==="

  # GC相关信息
  echo "  当前内存: ", getOccupiedMem(), " 字节"
  echo "  最大内存: ", getMaxMem(), " 字节"

  # 手动触发GC
  GC_fullCollect()
  echo "  GC已手动触发"
  echo "  GC后内存: ", getOccupiedMem(), " 字节"

  # 概念说明
  echo "\n  Nim内存管理选项:"
  echo "  - --gc:arc    自动引用计数（无GC暂停）"
  echo "  - --gc:orc     ORC（ARC + 循环收集）"
  echo "  - --gc:boehm   Boehm GC"
  echo "  - --gc:none    无GC（完全手动管理）"

# 【思考题】
# 1. Nim的ARC/ORC内存管理与传统GC（如Java/Go的GC）有什么本质区别？各自的优势和劣势是什么？
# 2. FFI使得Nim可以直接调用C库，这在系统编程中带来了什么优势？与手动绑定相比有什么便利？

# ============================================================
# 主函数：依次运行所有练习
# ============================================================
proc main() =
  # 第1题：Nim基础
  basicVariables()
  higherOrderDemo()
  typeSystemDemo()
  collectionsDemo()
  stringDemo()

  # 第2题：元编程
  templateDemo()
  templateCodeGenDemo()
  macroDemo()
  macroSerializeDemo()
  compileTimeDemo()

  # 第3题：系统编程
  pointerDemo()
  memoryManagementDemo()
  unionDemo()
  ffiDemo()
  bitwiseDemo()
  gcControlDemo()

  echo "\n所有Nim练习完成！"

main()
