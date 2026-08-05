// ============================================================
// 阶段：脚本语言与系统级语言扩展练习
// 语言：Dart
// 题数：3题
// 创建日期：2026-08-05
// ============================================================

import 'dart:async';

// ============================================================
// 第1题：Dart基础（类型 / 空安全 / 函数）
// ============================================================

// 【知识点讲解】
// Dart是Google开发的客户端优化语言，也是Flutter的编程语言。
// Dart是强类型语言，但支持类型推断（var/final/const）。
// 空安全（null safety）是Dart的核心特性，类型默认不可为null。
// 可空类型用 ? 标记，如 int? 表示可以为null的整型。
// Dart的函数是一等公民，支持箭头函数、可选参数、命名参数等。

// 1. 变量与类型
void basicTypes() {
  // 类型推断
  var name = 'Dart学习者';      // 自动推断为String
  var age = 25;                  // 自动推断为int
  var pi = 3.14159;              // 自动推断为double
  var isActive = true;           // 自动推断为bool

  // 显式类型声明
  String language = 'Dart';
  int year = 2026;
  double temperature = 36.5;
  List<String> skills = ['Flutter', 'Dart', 'Firebase'];
  Map<String, int> scores = {'数学': 90, '语文': 85, '英语': 92};

  // final 和 const
  final String currentDate = '2026-08-05';  // 运行时常量
  const double gravity = 9.8;                // 编译时常量

  print('=== 基础类型 ===');
  print('  name: $name, age: $age');
  print('  语言: $language, 年份: $year');
  print('  技能: $skills');
  print('  成绩: $scores');
  print('  final: $currentDate, const: $gravity');
}

// 2. 空安全
void nullSafety() {
  print('\n=== 空安全 ===');

  // 非空类型
  String nonNull = '我不能为null';

  // 可空类型
  String? maybeNull;
  print('  maybeNull初始: $maybeNull');  // null

  // 空值赋值操作符 ??
  maybeNull = null;
  String display = maybeNull ?? '默认值';
  print('  ?? 操作符: $display');

  // 安全调用操作符 ?.
  int? length = maybeNull?.length;
  print('  ?. 操作符: $length');

  // 非空断言操作符 !（谨慎使用）
  maybeNull = '现在有值了';
  print('  ! 操作符: ${maybeNull!.length}');

  // late关键字：延迟初始化的非空变量
  late String description;
  description = '我被延迟初始化了';
  print('  late: $description');
}

// 3. 函数特性
// 命名参数与默认值
String greet({
  required String name,
  String greeting = '你好',
  int? times,
}) {
  var count = times ?? 1;
  var result = StringBuffer();
  for (var i = 0; i < count; i++) {
    result.write('$greeting，$name！');
    if (i < count - 1) result.write(' ');
  }
  return result.toString();
}

// 可选位置参数
String formatNumber(num value, [int? decimals, String? suffix]) {
  var formatted = decimals != null
      ? value.toStringAsFixed(decimals)
      : value.toString();
  return formatted + (suffix ?? '');
}

// 箭头函数
int square(int n) => n * n;

void functionFeatures() {
  print('\n=== 函数特性 ===');

  // 命名参数
  print(greet(name: '张三'));
  print(greet(name: '李四', greeting: '早上好', times: 3));

  // 可选位置参数
  print(formatNumber(3.14159, 2, 'm'));
  print(formatNumber(100));

  // 箭头函数
  print('5的平方: ${square(5)}');

  // 匿名函数
  var numbers = [1, 2, 3, 4, 5];
  var doubled = numbers.map((n) => n * 2).toList();
  var evens = numbers.where((n) => n % 2 == 0).toList();
  var sum = numbers.fold(0, (acc, n) => acc + n);

  print('  原数组: $numbers');
  print('  翻倍: $doubled');
  print('  偶数: $evens');
  print('  总和: $sum');

  // 闭包
  Function makeAdder(int addend) {
    return (int n) => n + addend;
  }

  var addTen = makeAdder(10);
  print('  闭包 addTen(5) = ${addTen(5)}');
}

// 【思考题】
// 1. final 和 const 的区别是什么？什么场景下应该使用 const？
// 2. Dart的空安全如何帮助减少运行时错误？late关键字有哪些潜在风险？

// ============================================================
// 第2题：异步编程（Future / Stream / async-await）
// ============================================================

// 【知识点讲解】
// Dart是单线程事件循环模型，异步编程通过Future和Stream实现。
// Future表示一个可能还没完成的异步操作的结果。
// Stream是一系列异步事件的序列，类似于RxJS的Observable。
// async/await是语法糖，让异步代码看起来像同步代码。
// Dart的事件循环（Event Loop）处理微任务队列和事件队列。

// 1. Future基础
Future<String> fetchUserData(int userId) async {
  // 模拟网络延迟
  await Future.delayed(Duration(milliseconds: 100));
  if (userId < 0) {
    throw ArgumentError('用户ID不能为负数');
  }
  return '用户数据-$userId';
}

// 2. Future链式调用
Future<void> futureDemo() async {
  print('=== Future基础 ===');

  // async/await 方式
  try {
    var data = await fetchUserData(42);
    print('  获取数据: $data');
  } catch (e) {
    print('  错误: $e');
  }

  // Future.then 链式
  fetchUserData(100).then((data) {
    print('  链式调用: $data');
  }).catchError((e) {
    print('  链式错误: $e');
  });

  // Future.wait 并行执行
  var results = await Future.wait([
    fetchUserData(1),
    fetchUserData(2),
    fetchUserData(3),
  ]);
  print('  并行结果: $results');

  // Future.any 取最先完成的
  var fastest = await Future.any([
    Future.delayed(Duration(milliseconds: 50), () => '快速'),
    Future.delayed(Duration(milliseconds: 200), () => '慢速'),
  ]);
  print('  最先完成: $fastest');
}

// 3. Stream基础
Stream<int> numberStream(int max) async* {
  for (var i = 1; i <= max; i++) {
    await Future.delayed(Duration(milliseconds: 10));
    yield i;
  }
}

Future<void> streamDemo() async {
  print('\n=== Stream基础 ===');

  // 监听Stream
  var sum = 0;
  await for (var n in numberStream(5)) {
    sum += n;
    print('  收到: $n, 累计: $sum');
  }

  // Stream变换
  var doubled = numberStream(3).map((n) => n * 2);
  print('  变换后:');
  await for (var n in doubled) {
    print('    $n');
  }

  // Stream广播（多监听器）
  var controller = StreamController<int>.broadcast();
  controller.stream.listen((n) => print('  监听器A: $n'));
  controller.stream.listen((n) => print('  监听器B: $n'));

  controller.add(10);
  controller.add(20);
  await controller.close();
}

// 4. 实战：模拟异步数据管道
class DataPipeline {
  // 模拟数据源
  Stream<int> source() async* {
    for (var i = 1; i <= 10; i++) {
      await Future.delayed(Duration(milliseconds: 10));
      yield i;
    }
  }

  // 过滤偶数
  Stream<int> filter(Stream<int> input) {
    return input.where((n) => n % 2 == 0);
  }

  // 转换：平方
  Stream<int> transform(Stream<int> input) {
    return input.map((n) => n * n);
  }

  // 汇聚：收集到列表
  Future<List<int>> collect(Stream<int> input) async {
    return await input.toList();
  }

  Future<void> run() async {
    print('\n=== 数据管道 ===');
    var pipeline = collect(transform(filter(source())));
    var result = await pipeline;
    print('  1-10中偶数的平方: $result');
  }
}

// 【思考题】
// 1. Future和Stream的核心区别是什么？什么场景下应该用Stream而不是Future？
// 2. async* 和 yield 在Dart中的作用是什么？与普通 async 函数有何不同？

// ============================================================
// 第3题：面向对象（类 / 混入 / 扩展方法 / 泛型）
// ============================================================

// 【知识点讲解】
// Dart的OOP支持类、继承、抽象类、接口（隐式接口）、混入（mixin）。
// 每个类都隐式定义了一个接口，其他类可以implement它。
// mixin是一段可复用的代码，通过with关键字混入类中，解决单继承限制。
// 扩展方法（extension）可以为已有类型添加新方法，无需修改源码。
// 泛型提供类型安全的容器和算法。

// 1. 抽象类与继承
abstract class Animal {
  final String name;
  final int age;

  Animal({required this.name, required this.age});

  // 抽象方法
  String makeSound();

  // 普通方法
  String describe() => '$name，$age岁';

  // 工厂构造函数
  factory Animal.create(String type, String name, int age) {
    switch (type) {
      case 'dog':
        return Dog(name: name, age: age);
      case 'cat':
        return Cat(name: name, age: age);
      default:
        throw ArgumentError('未知动物类型: $type');
    }
  }
}

class Dog extends Animal {
  Dog({required super.name, required super.age});

  @override
  String makeSound() => '汪汪！';

  String fetch() => '$name把球捡回来了';
}

class Cat extends Animal {
  Cat({required super.name, required super.age});

  @override
  String makeSound() => '喵喵~';

  String purr() => '$name在呼噜呼噜';
}

// 2. Mixin：可复用能力
mixin Swimmer {
  String swim() => '${runtimeType.toString()}正在游泳';
}

mixin Flyer {
  String fly() => '${runtimeType.toString()}正在飞行';
}

mixin Walker {
  String walk() => '${runtimeType.toString()}正在走路';
}

// 通过with混入多个mixin
class Duck extends Animal with Swimmer, Flyer, Walker {
  Duck({required super.name, required super.age});

  @override
  String makeSound() => '嘎嘎！';
}

// 3. 隐式接口与实现
class Robot implements Animal {
  @override
  final String name;

  @override
  final int age;

  Robot(this.name, this.age);

  @override
  String makeSound() => '嘀嘀嘀...电子音';

  @override
  String describe() => '机器人$name，型号$age代';
}

// 4. 泛型
class Stack<T> {
  final List<T> _items = [];

  void push(T item) => _items.add(item);

  T pop() {
    if (_items.isEmpty) {
      throw StateError('栈为空');
    }
    return _items.removeLast();
  }

  T get peek => _items.last;

  bool get isEmpty => _items.isEmpty;

  int get size => _items.length;

  @override
  String toString() => 'Stack($_items)';
}

// 泛型方法
T firstOrDefault<T>(List<T> list, T defaultValue) {
  return list.isNotEmpty ? list.first : defaultValue;
}

// 5. 扩展方法
extension StringExtensions on String {
  String capitalize() {
    if (isEmpty) return this;
    return this[0].toUpperCase() + substring(1);
  }

  bool get isEmail => contains('@') && contains('.');

  String repeatStr(int times) => List.filled(times, this).join();
}

extension ListExtensions<T> on List<T> {
  T? get firstOrNull => isEmpty ? null : first;
}

// 6. 枚举（增强枚举）
enum HttpStatus {
  ok(200, '成功'),
  notFound(404, '未找到'),
  serverError(500, '服务器错误');

  final int code;
  final String message;
  const HttpStatus(this.code, this.message);

  bool get isError => code >= 400;
}

void oopDemo() {
  // 测试继承与多态
  print('=== 继承与多态 ===');
  List<Animal> animals = [
    Dog(name: '旺财', age: 3),
    Cat(name: '咪咪', age: 2),
    Animal.create('dog', '小黑', 5),
  ];

  for (var animal in animals) {
    print('  ${animal.describe()} -> ${animal.makeSound()}');
  }

  // 测试Mixin
  print('\n=== Mixin ===');
  var duck = Duck(name: '唐老鸭', age: 5);
  print('  ${duck.describe()} -> ${duck.makeSound()}');
  print('  ${duck.swim()}');
  print('  ${duck.fly()}');

  // 测试接口实现
  print('\n=== 接口实现 ===');
  var robot = Robot('R2D2', 3);
  print('  ${robot.describe()} -> ${robot.makeSound()}');

  // 测试泛型
  print('\n=== 泛型 ===');
  var stack = Stack<int>();
  stack.push(1);
  stack.push(2);
  stack.push(3);
  print('  $stack');
  print('  pop: ${stack.pop()}');
  print('  peek: ${stack.peek}');

  var defaultVal = firstOrDefault<String>([], '默认');
  print('  firstOrDefault: $defaultVal');

  // 测试扩展方法
  print('\n=== 扩展方法 ===');
  print('  capitalize: ${"hello".capitalize()}');
  print('  isEmail: ${"test@example.com".isEmail}');
  print('  repeat: ${"Ab".repeatStr(3)}');

  // 测试枚举
  print('\n=== 枚举 ===');
  for (var status in HttpStatus.values) {
    print('  ${status.name}(${status.code}): ${status.message} ${status.isError ? "[错误]" : "[正常]"}');
  }
}

// 【思考题】
// 1. Dart中 extends、implements、with 三者的区别是什么？分别在什么场景下使用？
// 2. 扩展方法和直接在类中添加方法相比，有什么优势和局限性？

// ============================================================
// 主函数：依次运行所有练习
// ============================================================
void main() async {
  // 第1题：Dart基础
  basicTypes();
  nullSafety();
  functionFeatures();

  // 第2题：异步编程
  await futureDemo();
  await streamDemo();
  await DataPipeline().run();

  // 第3题：面向对象
  oopDemo();
}
