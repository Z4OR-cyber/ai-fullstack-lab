// ============================================================
// 阶段：函数式JVM语言 - Scala语言练习
// 题数：3题
// 创建日期：2026-08-05
// ============================================================

// ============================================================
// 第1题：Scala基础（case class / 模式匹配 / for推导）
// ============================================================
// 知识点讲解：
// Scala是运行在JVM上的多范式语言，融合了面向对象和函数式编程。
// 核心特性：
//   - case class：不可变数据类，自动生成 equals/hashCode/toString/copy
//   - 模式匹配：比switch强大得多，可匹配类型、结构、守卫条件
//   - for推导式：for-comprehension，类似Haskell的do notation
//     可将 map/flatMap/filter 串联，语法简洁
//   - 不可变集合：List, Vector, Map 等默认不可变
//   - Option：替代null的安全类型，Some(value) 或 None

object ScalaExercises {

  // --- case class：不可变数据类 ---
  // case class 自动生成以下方法：
  //   - apply（可不写new创建实例）
  //   - equals / hashCode
  //   - toString
  //   - copy（创建修改后的副本）
  //   - unapply（用于模式匹配）

  case class Person(name: String, age: Int, city: String)
  case class Book(title: String, author: String, year: Int)
  case class Point(x: Double, y: Double)

  // case object：单例版本的case class，适合做标签/消息
  case object Empty

  def main(args: Array[String]): Unit = {

    println("=== case class 演示 ===")

    // 创建实例（不需要 new）
    val alice = Person("Alice", 30, "NYC")
    val bob = Person("Bob", 25, "LA")

    // 自动生成的 toString
    println(s"Alice: $alice")
    println(s"Bob: $bob")

    // copy 方法：创建修改后的副本
    val olderAlice = alice.copy(age = 31)
    println(s" Older Alice: $olderAlice")

    // 自动生成的 equals
    println(s"alice == alice.copy(): ${alice == alice.copy()}")

    // 解构（通过 unapply）
    val Person(name, age, _) = alice
    println(s"解构: name=$name, age=$age")

    // --- 模式匹配 ---
    println("\n=== 模式匹配 ===")

    // 1. 匹配case class
    def describePerson(p: Person): String = p match {
      case Person(n, a, _) if a < 18 => s"$n 是未成年人"
      case Person(n, a, "NYC")       => s"$n 住在纽约，年龄$a"
      case Person(n, _, city)        => s"$n 住在$city"
    }

    println(describePerson(alice))
    println(describePerson(bob))
    println(describePerson(Person("Charlie", 15, "Boston")))

    // 2. 匹配类型
    def process(x: Any): String = x match {
      case i: Int      => s"整数: $i, 平方: ${i * i}"
      case s: String   => s"字符串: $s, 长度: ${s.length}"
      case d: Double   => s"浮点数: $d"
      case p: Person   => s"人物: ${p.name}"
      case Some(v)     => s"Option有值: $v"
      case None        => "Option为空"
      case Nil         => "空列表"
      case head :: tail => s"非空列表, 头部: $head"
      case _           => "未知类型"
    }

    println(process(42))
    println(process("Hello"))
    println(process(3.14))
    println(process(Some("value")))
    println(process(None))
    println(process(List(1, 2, 3)))

    // 3. 匹配密封类型(Sealed Trait)
    sealed trait Shape
    case class Circle(radius: Double) extends Shape
    case class Rectangle(width: Double, height: Double) extends Shape
    case class Triangle(a: Double, b: Double, c: Double) extends Shape

    def area(shape: Shape): Double = shape match {
      case Circle(r)         => math.Pi * r * r
      case Rectangle(w, h)   => w * h
      case Triangle(a, b, c) =>
        val s = (a + b + c) / 2
        math.sqrt(s * (s - a) * (s - b) * (s - c))
    }

    println("\n=== 密封类型模式匹配 ===")
    val shapes: List[Shape] = List(
      Circle(3.0),
      Rectangle(4.0, 5.0),
      Triangle(3.0, 4.0, 5.0)
    )
    shapes.foreach { s =>
      println(s"  ${s.getClass.getSimpleName}: 面积 = ${f"${area(s)}%.2f"}")
    }

    // --- for 推导式 ---
    // for推导式会被编译器翻译为 map/flatMap/filter 的组合
    println("\n=== for 推导式 ===")

    // 基础for循环（副作用）
    for (i <- 1 to 5) {
      print(s"$i ")
    }
    println()

    // for推导式（yield生成新集合）
    val squares = for (x <- 1 to 5) yield x * x
    println(s"平方: $squares")

    // 带过滤条件的for推导式
    val evens = for {
      x <- 1 to 20
      if x % 2 == 0
    } yield x
    println(s"偶数: $evens")

    // 多生成器的for推导式（等价于flatMap + map）
    val pairs = for {
      x <- 1 to 3
      y <- 1 to 3
      if x + y == 4
    } yield (x, y)
    println(s"和为4的数对: $pairs")

    // for推导式处理Option
    def parseInt(s: String): Option[Int] =
      scala.util.Try(s.toInt).toOption

    val results = for {
      a <- parseInt("10")
      b <- parseInt("20")
      c <- parseInt("30")
    } yield a + b + c

    println(s"\nOption for推导: $results")  // Some(60)

    // 如果有一个解析失败
    val failedResults = for {
      a <- parseInt("10")
      b <- parseInt("abc")  // 解析失败
      c <- parseInt("30")
    } yield a + b + c

    println(s"有失败的Option for推导: $failedResults")  // None

    // --- Option 类型 ---
    println("\n=== Option 类型 ===")

    val maybeName: Option[String] = Some("Alice")
    val maybeAge: Option[Int] = None

    // map: 对Some中的值应用函数
    println(s"map: ${maybeName.map(_.toUpperCase)}")   // Some(ALICE)
    println(s"map None: ${maybeAge.map(_ * 2)}")       // None

    // getOrElse: 提供默认值
    println(s"getOrElse: ${maybeName.getOrElse("无名")}")
    println(s"getOrElse None: ${maybeAge.getOrElse(0)}")

    // flatMap: 链式Option操作
    def getPerson(id: Int): Option[Person] = id match {
      case 1 => Some(Person("Alice", 30, "NYC"))
      case 2 => Some(Person("Bob", 25, "LA"))
      case _ => None
    }

    val personName = getPerson(1).flatMap(p => Some(p.name))
    println(s"flatMap: $personName")

    // filter
    val filtered = getPerson(1).filter(_.age > 25)
    println(s"filter: $filtered")

    // --- 集合操作 ---
    println("\n=== 集合操作 ===")

    val nums = (1 to 10).toList

    // map / filter / reduce / fold
    println(s"map: ${nums.map(_ * 2)}")
    println(s"filter: ${nums.filter(_ % 3 == 0)}")
    println(s"reduce: ${nums.reduce(_ + _)}")
    println(s"foldLeft: ${nums.foldLeft(0)(_ + _)}")
    println(s"groupBy: ${nums.groupBy(_ % 2 == 0)}")

    // 柯里化风格的集合操作链
    val pipeline = nums
      .filter(_ > 3)
      .map(_ * 2)
      .take(5)
      .sum
    println(s"管道结果: $pipeline")

    // --- 偏函数(PartialFunction) ---
    println("\n=== 偏函数 ===")

    val doubleEvens: PartialFunction[Int, Int] = {
      case x if x % 2 == 0 => x * 2
    }

    val tripleOdds: PartialFunction[Int, Int] = {
      case x if x % 2 != 0 => x * 3
    }

    // 组合偏函数
    val processNum = doubleEvens.orElse(tripleOdds)

    println(s"处理 4: ${processNum(4)}")   // 8
    println(s"处理 3: ${processNum(3)}")   // 9

    // collect 使用偏函数过滤+映射
    val collected = nums.collect {
      case x if x % 2 == 0 => s"偶数$x"
      case x if x % 3 == 0 => s"奇数3的倍数$x"
    }
    println(s"collect: $collected")
  }
}

// 思考题：case class 和普通 class 有什么区别？
//         为什么Scala推荐用Option替代null？
//         for推导式如何被翻译为flatMap/map？这种翻译规则有什么好处？

// ============================================================
// 第2题：类型系统（泛型 / 上下界 / 隐式参数）
// ============================================================
// 知识点讲解：
// Scala拥有强大的类型系统，融合了OOP和FP的类型特性：
//   - 泛型(Generic)：参数化类型，如 List[T], Map[K, V]
//   - 上界(T <: Upper)：T必须是Upper的子类型
//   - 下界(T >: Lower)：T必须是Lower的父类型
//   - 上下文界(T: ClassTag)：需要一个隐式参数
//   - 视界(T <% String)：T可隐式转换为String（已弃用）
//   - 隐式参数(Implicit Parameter)：编译器自动注入参数
//   - 隐式转换(Implicit Conversion)：自动类型转换
//   - 协变[+T] / 逆变[-T]：类型参数的变体标注

object TypeSystemExercises {

  // --- 泛型类 ---
  // 一个简单的栈实现
  class Stack[T] {
    private var elements: List[T] = Nil

    def push(x: T): Unit = elements = x :: elements
    def pop(): Option[T] = elements match {
      case Nil     => None
      case x :: xs => elements = xs; Some(x)
    }
    def peek: Option[T] = elements.headOption
    def size: Int = elements.length
    override def toString: String = s"Stack($elements)"
  }

  // --- 上界(Upper Bound) ---
  // T <: Comparable[T] 表示T必须是Comparable[T]的子类型
  // 这样可以在函数中使用Comparable的方法
  def maxOf[T <: Comparable[T]](a: T, b: T): T =
    if (a.compareTo(b) >= 0) a else b

  // --- 下界(Lower Bound) ---
  // T >: Animal 表示T必须是Animal的父类型
  // 常用于协变类型中安全地添加元素
  class Box[+T](val content: T) {
    // 下界允许将子类型放入父类型的Box中
    def put[U >: T](item: U): Box[U] = new Box(item)
  }

  // --- 变体(Variance) ---
  // 协变[+T]：如果Dog是Animal的子类，则Box[Dog]是Box[Animal]的子类
  // 逆变[-T]：如果Dog是Animal的子类，则Handler[Animal]是Handler[Dog]的子类
  // 不变[T]：没有子类型关系

  // 协变示例
  class CovariantBox[+T](val value: T)
  // CovariantBox[Dog] 是 CovariantBox[Animal] 的子类

  // 逆变示例
  trait Printer[-T] {
    def print(value: T): Unit
  }
  // Printer[Animal] 是 Printer[Dog] 的子类
  // 因为能打印Animal的打印机，也能打印Dog

  // --- 隐式参数 ---
  // 编译器会在调用点自动查找匹配的隐式值并注入
  case class DatabaseConfig(url: String, timeout: Int)

  // 比较器trait
  trait Comparator[T] {
    def compare(a: T, b: T): Int
  }

  // 隐式比较器实例
  object Comparators {
    implicit val intComparator: Comparator[Int] = (a: Int, b: Int) => a - b
    implicit val stringComparator: Comparator[String] = (a: String, b: String) => a.compareTo(b)
    implicit val doubleComparator: Comparator[Double] = (a: Double, b: Double) => a.compareTo(b)
  }

  // 使用隐式参数的排序函数
  def sortWith[T](list: List[T])(implicit cmp: Comparator[T]): List[T] = {
    list.sortWith((a, b) => cmp.compare(a, b) < 0)
  }

  // 上下文界定：T: Comparator 等价于隐式参数
  def maxInList[T: Comparator](list: List[T]): Option[T] = {
    val cmp = implicitly[Comparator[T]]
    list.reduceOption((a, b) => if (cmp.compare(a, b) >= 0) a else b)
  }

  // --- 类型类模式 ---
  // Scala的类型类通过trait + 隐式参数实现
  // 比OOP的继承更灵活：可以为已有类型添加新行为

  // 定义类型类
  trait JsonSerializable[T] {
    def toJson(value: T): String
  }

  // 类型类实例
  object JsonInstances {
    implicit val personJson: JsonSerializable[Person] = (p: Person) =>
      s"""{"name":"${p.name}","age":${p.age},"city":"${p.city}"}"""

    implicit val intJson: JsonSerializable[Int] = (i: Int) => i.toString

    implicit val stringJson: JsonSerializable[String] = (s: String) => s""""$s""""

    implicit def listJson[T](implicit js: JsonSerializable[T]): JsonSerializable[List[T]] =
      (list: List[T]) => list.map(js.toJson).mkString("[", ",", "]")
  }

  // 使用类型类的函数
  def toJson[T](value: T)(implicit js: JsonSerializable[T]): String =
    js.toJson(value)

  // --- 存在类型 ---
  // List[_] 等价于 List[?]，表示元素类型未知
  def printList(lst: List[_]): Unit = lst.foreach(println)

  // --- 枚举(Scala 3风格，这里用sealed trait模拟) ---
  sealed trait Color {
    def hex: String
  }
  object Color {
    case object Red extends Color { val hex = "#FF0000" }
    case object Green extends Color { val hex = "#00FF00" }
    case object Blue extends Color { val hex = "#0000FF" }
    val values: List[Color] = List(Red, Green, Blue)
  }

  // --- 上下文界定实践 ---
  // Ordering是Scala标准库的类型类
  def sortUsingOrdering[T: Ordering](list: List[T]): List[T] =
    list.sorted

  def main(args: Array[String]): Unit = {
    import Comparators._

    println("=== 泛型类 ===")
    val stack = new Stack[Int]
    stack.push(1)
    stack.push(2)
    stack.push(3)
    println(s"栈: $stack")
    println(s"弹出: ${stack.pop()}")
    println(s"栈顶: ${stack.peek}")

    println("\n=== 隐式参数排序 ===")
    println(sortWith(List(3, 1, 4, 1, 5, 9, 2, 6)))
    println(sortWith(List("banana", "apple", "cherry")))
    println(sortWith(List(3.14, 1.41, 2.72)))

    println("\n=== 上下文界定 ===")
    println(maxInList(List(3, 7, 1, 9, 4)))
    println(maxInList(List("zebra", "apple", "mango")))

    println("\n=== 类型类 ===")
    import JsonInstances._
    val alice = Person("Alice", 30, "NYC")
    println(toJson(alice))
    println(toJson(42))
    println(toJson("Hello"))
    println(toJson(List(1, 2, 3)))
    println(toJson(List("a", "b", "c")))

    println("\n=== Ordering ===")
    println(sortUsingOrdering(List(5, 3, 8, 1, 9)))
    println(sortUsingOrdering(List("cherry", "apple", "banana")))

    println("\n=== 变体演示 ===")
    // 协变：子类型关系传递
    class Animal { def name: String = "Animal" }
    class Dog extends Animal { override def name: String = "Dog" }

    val dogBox: CovariantBox[Dog] = new CovariantBox(new Dog)
    val animalBox: CovariantBox[Animal] = dogBox  // 协变允许
    println(s"协变Box内容: ${animalBox.value.name}")

    println("\n=== 密封类型枚举 ===")
    Color.values.foreach(c => println(s"  ${c.getClass.getSimpleName}: ${c.hex}"))
  }
}

// 思考题：Scala的协变[+T]和逆变[-T]在什么场景下使用？
//         隐式参数和依赖注入(DI)有什么关系？
//         类型类(Typeclass)模式和OOP继承相比，有什么优势和劣势？

// ============================================================
// 第3题：并发（Future / Akka概念 / 并行集合）
// ============================================================
// 知识点讲解：
// Scala的并发模型主要有三个层次：
//
// 1. Future / Promise：
//    - Future：异步计算的占位符，代表一个未来可用的结果
//    - Promise：Future的生产者端，用于手动完成Future
//    - 基于回调或for推导式组合多个Future
//    - 需要隐式的 ExecutionContext 执行
//
// 2. Akka（Actor模型）：
//    - 轻量级Actor，通过消息传递通信
//    - Actor有独立状态，不共享内存
//    - Supervisor策略：监控和重启子Actor
//    - 适用于高并发、高容错系统
//
// 3. 并行集合：
//    - .par 将普通集合转为并行集合
//    - map/filter/reduce 等操作自动并行执行
//    - 注意线程安全和副作用问题

import scala.concurrent.{Future, Promise, Await}
import scala.concurrent.duration._
import scala.concurrent.ExecutionContext.Implicits.global
import scala.util.{Success, Failure}

object ConcurrencyExercises {

  // --- Future基础 ---
  def asyncSquare(n: Int): Future[Int] = Future {
    Thread.sleep(100)  // 模拟耗时操作
    n * n
  }

  def asyncFetchUser(id: Int): Future[Person] = Future {
    Thread.sleep(50)
    id match {
      case 1 => Person("Alice", 30, "NYC")
      case 2 => Person("Bob", 25, "LA")
      case _ => throw new RuntimeException(s"用户 $id 不存在")
    }
  }

  // --- Future组合 ---
  def fetchMultipleUsers(ids: List[Int]): Future[List[Person]] = {
    // 将多个Future[Person]组合为Future[List[Person]]
    Future.sequence(ids.map(asyncFetchUser))
  }

  // --- Promise：手动完成Future ---
  def timeoutFuture[T](duration: FiniteDuration, value: T): Future[T] = {
    val promise = Promise[T]()
    val scheduler = java.util.concurrent.Executors.newScheduledThreadPool(1)
    scheduler.schedule(
      new Runnable { def run(): Unit = promise.success(value) },
      duration.toMillis,
      java.util.concurrent.TimeUnit.MILLISECONDS
    )
    promise.future
  }

  // --- 错误处理 ---
  def safeFetchUser(id: Int): Future[Option[Person]] = {
    asyncFetchUser(id)
      .map(Some(_))           // 成功：包装为Some
      .recover { case _ => None }  // 失败：返回None
  }

  // --- 并行集合 ---
  def parallelSum(nums: List[Int]): Int = {
    // 使用并行集合加速求和
    nums.par.sum
  }

  def parallelMap(nums: List[Int]): List[Int] = {
    nums.par.map(_ * 2).toList
  }

  // --- Akka Actor概念（伪代码，需要akka-actor依赖） ---
  /*
  import akka.actor._

  // 定义Actor消息
  case class Greeting(name: String)
  case object GetCount

  // 定义Actor
  class GreeterActor extends Actor {
    var count = 0

    def receive: Receive = {
      case Greeting(name) =>
        count += 1
        println(s"你好, $name! (第${count}次问候)")

      case GetCount =>
        sender() ! count  // 回复消息给发送者
    }
  }

  // Actor系统
  val system = ActorSystem("MySystem")
  val greeter = system.actorOf(Props[GreeterActor], "greeter")

  // 发送消息
  greeter ! Greeting("Alice")
  greeter ! Greeting("Bob")

  // 请求-响应模式
  import akka.pattern.ask
  import akka.util.Timeout
  implicit val timeout: Timeout = 5.seconds
  val futureCount = greeter ? GetCount
  futureCount.onComplete {
    case Success(count) => println(s"总问候次数: $count")
    case Failure(e)     => println(s"错误: ${e.getMessage}")
  }
  */

  def main(args: Array[String]): Unit = {

    // --- Future基础 ---
    println("=== Future基础 ===")

    val future1 = asyncSquare(5)
    val future2 = asyncSquare(10)

    // 回调方式处理结果
    future1.onComplete {
      case Success(result) => println(s"5的平方 = $result")
      case Failure(e)      => println(s"错误: ${e.getMessage}")
    }

    // 阻塞等待（仅用于演示，生产环境应避免）
    val result2 = Await.result(future2, 2.seconds)
    println(s"10的平方 = $result2")

    // --- for推导式组合Future ---
    println("\n=== for推导式组合Future ===")

    val combinedFuture = for {
      a <- asyncSquare(3)
      b <- asyncSquare(4)
      c <- asyncSquare(5)
    } yield a + b + c

    val combined = Await.result(combinedFuture, 5.seconds)
    println(s"3² + 4² + 5² = $combined")  // 9 + 16 + 25 = 50

    // --- Future.sequence ---
    println("\n=== Future.sequence ===")

    val userFuture = fetchMultipleUsers(List(1, 2))
    userFuture.onComplete {
      case Success(users) => println(s"获取到 ${users.size} 个用户: $users")
      case Failure(e)     => println(s"错误: ${e.getMessage}")
    }

    val users = Await.result(userFuture, 5.seconds)
    users.foreach(u => println(s"  - ${u.name}, ${u.age}岁"))

    // --- 错误处理 ---
    println("\n=== Future错误处理 ===")

    val safeResult = Await.result(safeFetchUser(1), 2.seconds)
    println(s"用户1: $safeResult")

    val safeResult2 = Await.result(safeFetchUser(999), 2.seconds)
    println(s"用户999: $safeResult2")

    // recoverWith：用另一个Future恢复
    val recoveredFuture = asyncFetchUser(999)
      .recoverWith {
        case _ => Future.successful(Person("Unknown", 0, "Nowhere"))
      }
    val recovered = Await.result(recoveredFuture, 2.seconds)
    println(s"恢复后: $recovered")

    // --- Promise使用 ---
    println("\n=== Promise ===")

    val timeoutFuture1 = timeoutFuture(100.millis, "超时结果")
    val timeoutResult = Await.result(timeoutFuture1, 2.seconds)
    println(s"Promise结果: $timeoutResult")

    // --- 并行集合 ---
    println("\n=== 并行集合 ===")

    val bigList = (1 to 1000000).toList

    // 普通集合操作
    val t0 = System.currentTimeMillis()
    val sum1 = bigList.filter(_ % 2 == 0).map(_ * 2).sum
    val t1 = System.currentTimeMillis()
    println(s"普通集合: sum=$sum1, 耗时=${t1 - t0}ms")

    // 并行集合操作
    val t2 = System.currentTimeMillis()
    val sum2 = bigList.par.filter(_ % 2 == 0).map(_ * 2).sum
    val t3 = System.currentTimeMillis()
    println(s"并行集合: sum=$sum2, 耗时=${t3 - t2}ms")

    // --- Future.zip：并行执行两个任务 ---
    println("\n=== Future.zip ===")

    val f1 = asyncFetchUser(1)
    val f2 = asyncFetchUser(2)
    val zipped = f1.zip(f2)
    val (u1, u2) = Await.result(zipped, 5.seconds)
    println(s"用户1: ${u1.name}, 用户2: ${u2.name}")

    // --- 先到先得：Future.firstCompletedOf ---
    println("\n=== firstCompletedOf ===")

    val fast = Future { Thread.sleep(50); "快速" }
    val slow = Future { Thread.sleep(200); "慢速" }
    val first = Await.result(Future.firstCompletedOf(List(fast, slow)), 5.seconds)
    println(s"先完成的结果: $first")

    // --- 折叠多个Future ---
    println("\n=== Future.fold ===")

    val futures = List(asyncSquare(1), asyncSquare(2), asyncSquare(3))
    val folded = Await.result(Future.fold(futures)(0)(_ + _), 5.seconds)
    println(s"1² + 2² + 3² = $folded")

    println("\n=== Akka概念 ===")
    println("""
    |Akka Actor模型要点：
    |1. Actor是并发的基本单元，有独立状态，不共享内存
    |2. Actor之间通过异步消息通信（! 发送, ? 请求-响应）
    |3. 每个Actor一次只处理一条消息，无需锁
    |4. Supervisor策略决定子Actor失败时的处理方式
    |5. ActorSystem管理Actor的生命周期
    |
    |适用场景：
    |- 高并发服务端应用
    |- 事件驱动系统
    |- 分布式计算
    |- 需要容错的系统
    """.stripMargin)

    // 等待异步回调完成
    Thread.sleep(500)
  }
}

// 思考题：Future和Promise的关系是什么？谁是生产者谁是消费者？
//         为什么for推导式能优雅地组合多个Future？它背后的map/flatMap如何工作？
//         并行集合(.par)在什么情况下会比普通集合慢？有什么注意事项？
