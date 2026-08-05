// ============================================================
// 阶段标题：Rust 语言练习 —— 从所有权到并发
// 题数：10
// 创建日期：2026-08-05
// 说明：全中文注释，代码用英文；由浅入深，自包含无外部依赖
// ============================================================

// ------------------------------------------------------------
// 第1题：变量、不可变性与数据类型
// ------------------------------------------------------------
// 知识点：
// - Rust 中变量默认不可变，需用 mut 关键字声明可变变量
// - 基本数据类型包括：i32, u64, f64, bool, char, usize 等
// - &str 是字符串切片（不可变引用），String 是堆上可增长的字符串
// - &str 通常存储在程序只读数据段或栈上，String 则在堆上分配
// - 使用 String::from() 或 to_string() 可将 &str 转为 String

fn exercise_01_basics() {
    // 不可变变量 —— 修改会编译报错
    let x: i32 = 42;
    println!("不可变变量 x = {}", x);

    // 使用 mut 声明可变变量
    let mut y: f64 = 3.14;
    y += 0.01;
    println!("可变变量 y = {}", y);

    // 基本类型示例
    let is_ready: bool = true;
    let grade: char = 'A';
    let count: u64 = 1_000_000; // 下划线分隔，提高可读性
    println!("is_ready={}, grade={}, count={}", is_ready, grade, count);

    // &str 与 String 的区别
    let s1: &str = "hello";        // 字符串字面量，类型为 &str
    let s2: String = String::from(" world"); // 堆上分配的 String
    let s3: String = s1.to_string(); // &str 转 String
    let combined = format!("{}{}", s3, s2);
    println!("拼接结果: {}", combined);

    // 类型推断 —— Rust 编译器能自动推断类型
    let inferred = 1u32 + 2; // 推断为 u32
    println!("类型推断结果: {}", inferred);
}

// 思考题：如果去掉 y 的 mut 关键字，编译会报什么错？
// 又：&str 和 String 在内存布局上有何不同？

// ------------------------------------------------------------
// 第2题：所有权系统 —— 转移、借用与引用规则
// ------------------------------------------------------------
// 知识点：
// - 所有权是 Rust 的核心机制：每个值有且仅有一个所有者
// - 当所有者离开作用域，值被自动释放（Drop）
// - 赋值或传参时，堆数据的所有权"转移"（move），原变量失效
// - 借用（&）允许引用数据而不获取所有权，分为不可变引用 &T 和可变引用 &mut T
// - 规则：同一时刻可以有多个不可变引用，或一个可变引用，二者不可共存

fn exercise_02_ownership() {
    // 所有权转移：String 赋值后原变量失效
    let s1 = String::from("rust");
    let s2 = s1; // 所有权从 s1 转移到 s2
    // println!("{}", s1); // 编译错误：s1 已被 move
    println!("s2 = {}", s2);

    // 基本类型（Copy trait）赋值时是复制而非转移
    let n1 = 10;
    let n2 = n1; // i32 实现了 Copy，n1 仍然可用
    println!("n1={}, n2={}", n1, n2);

    // 不可变借用：可以同时存在多个
    let s3 = String::from("borrow");
    let r1 = &s3;
    let r2 = &s3; // 多个不可变引用合法
    println!("r1={}, r2={}", r1, r2);

    // 可变借用：同一时间只能有一个
    let mut s4 = String::from("mutable");
    let r3 = &mut s4;
    r3.push_str(" borrow");
    println!("可变借用后: {}", s4);

    // 函数传参也会发生所有权转移
    let s5 = String::from("transfer");
    takes_ownership(s5);
    // println!("{}", s5); // 编译错误：s5 已被 move 进函数

    // 通过引用避免所有权转移
    let s6 = String::from("keep");
    borrows_value(&s6); // 借用，不转移所有权
    println!("s6 在函数调用后仍可用: {}", s6);
}

fn takes_ownership(s: String) {
    println!("函数获取了所有权: {}", s);
} // s 离开作用域，String 被释放

fn borrows_value(s: &String) {
    println!("函数只是借用: {}", s);
} // s 是引用，不释放任何东西

// 思考题：为什么 Rust 不允许同时存在可变引用和不可变引用？
// 这在编译期避免了什么类型的 bug？

// ------------------------------------------------------------
// 第3题：结构体与方法
// ------------------------------------------------------------
// 知识点：
// - struct 用于定义自定义数据结构，支持命名字段
// - impl 块为结构体实现方法和关联函数（类似其他语言的构造函数）
// - 关联函数（无 self 参数）通过 :: 调用，方法（含 self 参数）通过 . 调用
// - 元组结构体：字段没有名字，通过索引访问，适合给元组起类型名
// - 方法中 &self 表示不可变借用，&mut self 表示可变借用，self 表示获取所有权

struct Rectangle {
    width: f64,
    height: f64,
}

impl Rectangle {
    // 关联函数（构造函数），类似 Rectangle::new()
    fn new(width: f64, height: f64) -> Rectangle {
        Rectangle { width, height }
    }

    // 不可变方法：计算面积
    fn area(&self) -> f64 {
        self.width * self.height
    }

    // 可变方法：缩放
    fn scale(&mut self, factor: f64) {
        self.width *= factor;
        self.height *= factor;
    }

    // 关联函数：创建正方形
    fn square(size: f64) -> Rectangle {
        Rectangle { width: size, height: size }
    }
}

// 元组结构体
struct Color(i32, i32, i32);

fn exercise_03_struct() {
    let mut rect = Rectangle::new(10.0, 5.0);
    println!("面积: {}", rect.area());

    rect.scale(2.0);
    println!("缩放后面积: {}", rect.area());

    let sq = Rectangle::square(3.0);
    println!("正方形面积: {}", sq.area());

    // 元组结构体使用
    let red = Color(255, 0, 0);
    println!("颜色: R={}, G={}, B={}", red.0, red.1, red.2);
}

// 思考题：如果 area 方法的参数从 &self 改成 self，会对调用者产生什么影响？

// ------------------------------------------------------------
// 第4题：枚举与模式匹配
// ------------------------------------------------------------
// 知识点：
// - enum 定义枚举类型，每个变体可携带不同类型和数量的数据
// - Option<T> 是 Rust 标准库的核心枚举，替代 null，分为 Some(T) 和 None
// - Result<T, E> 用于错误处理，分为 Ok(T) 和 Err(E)
// - match 表达式对枚举进行穷尽匹配，必须覆盖所有变体
// - if let 和 while let 用于简洁地匹配单个模式，忽略其他情况

// 自定义枚举：Web 请求状态
enum HttpStatus {
    Ok,
    NotFound,
    ServerError(String),
    Redirect { url: String, permanent: bool },
}

fn describe_status(status: &HttpStatus) -> String {
    match status {
        HttpStatus::Ok => String::from("200 OK"),
        HttpStatus::NotFound => String::from("404 Not Found"),
        HttpStatus::ServerError(msg) => format!("500 Server Error: {}", msg),
        HttpStatus::Redirect { url, permanent } => {
            let code = if *permanent { "301" } else { "302" };
            format!("{} Redirect to {}", code, url)
        }
    }
}

fn exercise_04_enum() {
    let statuses = [
        HttpStatus::Ok,
        HttpStatus::NotFound,
        HttpStatus::ServerError(String::from("数据库连接失败")),
        HttpStatus::Redirect { url: String::from("/new-path"), permanent: true },
    ];

    for s in &statuses {
        println!("{}", describe_status(s));
    }

    // Option 与 if let
    let maybe_name: Option<&str> = Some("Alice");
    if let Some(name) = maybe_name {
        println!("名字是: {}", name);
    } else {
        println!("没有名字");
    }

    // Result 与 while let
    let results: Vec<Result<i32, &str>> = vec![Ok(1), Ok(2), Err("出错了"), Ok(3)];
    for r in &results {
        match r {
            Ok(val) => println!("成功: {}", val),
            Err(e) => println!("失败: {}", e),
        }
    }

    // while let 示例：持续取出 Option
    let mut stack = vec![Some(1), Some(2), None, Some(3)];
    while let Some(Some(top)) = stack.pop() {
        println!("栈顶: {}", top);
    }
}

// 思考题：match 表达式为什么要求穷尽所有变体？这一设计带来了什么好处？

// ------------------------------------------------------------
// 第5题：集合与错误处理
// ------------------------------------------------------------
// 知识点：
// - Vec<T> 是 Rust 的动态数组，存储在堆上，支持自动扩容
// - HashMap<K, V> 是哈希表，通过键存储值，需要键实现 Hash 和 Eq trait
// - ? 操作符：在 Result 上使用时，Ok 则解包取值，Err 则提前返回错误
// - ? 操作符支持链式调用，极大简化错误传播代码
// - 自定义错误类型：通过实现 std::error::Error trait 创建可组合的错误体系

use std::collections::HashMap;
use std::fmt;

// 自定义错误类型
#[derive(Debug)]
enum AppError {
    NotFound(String),
    InvalidInput(String),
}

impl fmt::Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AppError::NotFound(msg) => write!(f, "未找到: {}", msg),
            AppError::InvalidInput(msg) => write!(f, "无效输入: {}", msg),
        }
    }
}

impl std::error::Error for AppError {}

// 使用 ? 操作符进行错误传播
fn find_value(map: &HashMap<String, i32>, key: &str) -> Result<i32, AppError> {
    map.get(key)
        .copied()
        .ok_or_else(|| AppError::NotFound(format!("键 '{}' 不存在", key)))
}

fn validate_and_double(map: &HashMap<String, i32>, key: &str) -> Result<i32, AppError> {
    let val = find_value(map, key)?; // ? 操作符：出错则提前返回
    if val < 0 {
        return Err(AppError::InvalidInput(format!("值 {} 不能为负数", val)));
    }
    Ok(val * 2)
}

fn exercise_05_collections() {
    // Vec 基本操作
    let mut numbers: Vec<i32> = Vec::new();
    numbers.push(10);
    numbers.push(20);
    numbers.push(30);
    println!("Vec: {:?}, 长度: {}", numbers, numbers.len());

    // 使用宏创建 Vec
    let fruits = vec!["apple", "banana", "cherry"];
    for (i, fruit) in fruits.iter().enumerate() {
        println!("索引 {}: {}", i, fruit);
    }

    // HashMap 操作
    let mut scores: HashMap<String, i32> = HashMap::new();
    scores.insert(String::from("Alice"), 95);
    scores.insert(String::from("Bob"), 87);
    scores.entry(String::from("Alice")).or_insert(60); // 不覆盖已有值
    println!("HashMap: {:?}", scores);

    // 错误处理链式调用
    match validate_and_double(&scores, "Alice") {
        Ok(result) => println!("结果: {}", result),
        Err(e) => println!("错误: {}", e),
    }

    // 测试错误路径
    match validate_and_double(&scores, "Charlie") {
        Ok(result) => println!("结果: {}", result),
        Err(e) => println!("错误: {}", e),
    }
}

// 思考题：如果不使用 ? 操作符，find_value 和 validate_and_double 的代码会变成什么样？

// ------------------------------------------------------------
// 第6题：Trait 与泛型
// ------------------------------------------------------------
// 知识点：
// - trait 定义共享行为，类似其他语言的接口，声明方法签名
// - 实现 trait 时必须为每个方法提供具体实现，也可提供默认实现
// - 泛型函数通过 trait bound 限制类型参数必须实现特定 trait
// - trait bound 语法：fn func<T: TraitName>(item: T)
// - trait 对象（dyn Trait）允许在运行时处理不同类型，但有动态分发开销

// 定义一个 trait
trait Summary {
    fn summarize(&self) -> String;

    // 默认实现：类型可以选择覆盖
    fn summarize_short(&self) -> String {
        self.summarize() // 默认行为
    }
}

// 为结构体实现 trait
struct Article {
    title: String,
    content: String,
}

impl Summary for Article {
    fn summarize(&self) -> String {
        format!("{}: {}", self.title, self.content)
    }
}

struct Tweet {
    username: String,
    text: String,
}

impl Summary for Tweet {
    fn summarize(&self) -> String {
        format!("@{}: {}", self.username, self.text)
    }
    // 覆盖默认实现
    fn summarize_short(&self) -> String {
        format!("@{}", self.username)
    }
}

// 泛型函数 with trait bound
fn print_summary<T: Summary>(item: &T) {
    println!("{}", item.summarize());
}

// 多重 trait bound 使用 + 号
fn display_and_summarize<T: Summary + std::fmt::Display>(item: &T) {
    println!("Display: {}", item);
    println!("Summary: {}", item.summarize());
}

// 为实现了 Display 的类型提供 blanket implementation
impl<T: std::fmt::Display> Summary for Wrapper<T> {
    fn summarize(&self) -> String {
        format!("Wrapped: {}", self.0)
    }
}

struct Wrapper<T>(T);

// 为 Wrapper 实现 Display
impl<T: std::fmt::Display> std::fmt::Display for Wrapper<T> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Wrapper({})", self.0)
    }
}

fn exercise_06_traits() {
    let article = Article {
        title: String::from("Rust 入门"),
        content: String::from("Rust 是一门系统编程语言"),
    };
    let tweet = Tweet {
        username: String::from("dev"),
        text: String::from("今天学了 Rust"),
    };

    print_summary(&article);
    print_summary(&tweet);

    println!("文章简短摘要: {}", article.summarize_short());
    println!("推文简短摘要: {}", tweet.summarize_short()); // 使用覆盖的默认实现

    // 测试多重 trait bound
    let wrapped = Wrapper(42i32);
    display_and_summarize(&wrapped);
}

// 思考题：泛型 + trait bound（静态分发）和 trait 对象（动态分发）各有什么优缺点？

// ------------------------------------------------------------
// 第7题：生命周期深入
// ------------------------------------------------------------
// 知识点：
// - 生命周期标注用于告诉编译器引用之间的存活关系，不改变实际存活时间
// - 函数中的生命周期：当参数和返回值都是引用时，需标注生命周期
// - 结构体中的生命周期：如果结构体持有引用，必须标注生命周期参数
// - 生命周期省略规则：编译器有三条规则可自动推断，不满足时需手动标注
// - 'static 是特殊生命周期，表示引用在整个程序运行期间有效

// 1. 函数中的生命周期标注
// 返回的引用与两个输入引用中较短的那个同生命周期
fn longest<'a>(s1: &'a str, s2: &'a str) -> &'a str {
    if s1.len() > s2.len() {
        s1
    } else {
        s2
    }
}

// 2. 结构体中的生命周期
struct TextEditor<'a> {
    text: &'a str, // 结构体持有引用，必须标注生命周期
    cursor: usize,
}

impl<'a> TextEditor<'a> {
    fn new(text: &'a str) -> TextEditor<'a> {
        TextEditor { text, cursor: 0 }
    }

    // 返回的引用生命周期与结构体中的 text 相同
    fn current_char(&self) -> Option<char> {
        self.text.chars().nth(self.cursor)
    }

    fn advance(&mut self) {
        self.cursor += 1;
    }
}

// 3. 生命周期省略规则示例
// 这里的编译器能自动推断生命周期，无需手动标注
fn first_word(s: &str) -> &str {
    // 省略规则：只有一个输入引用，输出引用与之同生命周期
    let bytes = s.as_bytes();
    for (i, &byte) in bytes.iter().enumerate() {
        if byte == b' ' {
            return &s[..i];
        }
    }
    s
}

// 4. 'static 生命周期
fn static_example() {
    // 字符串字面量的生命周期是 'static
    let s: &'static str = "我活在程序的整个生命周期";
    println!("{}", s);
}

fn exercise_07_lifetimes() {
    // 函数生命周期
    let s1 = String::from("long string");
    let s2 = String::from("short");
    let result = longest(s1.as_str(), s2.as_str());
    println!("较长的字符串: {}", result);

    // 结构体生命周期
    let text = String::from("Hello, Rust world!");
    let mut editor = TextEditor::new(&text);
    println!("当前字符: {:?}", editor.current_char());
    editor.advance();
    println!("前进后的字符: {:?}", editor.current_char());

    // 生命周期省略
    let sentence = "hello world from rust";
    let word = first_word(sentence);
    println!("第一个单词: {}", word);

    // 'static
    static_example();
}

// 思考题：为什么以下代码会编译失败？
//   let r;
//   { let s = String::from("hi"); r = &s; }
//   println!("{}", r);
// 提示：思考 s 的生命周期是否足够长。

// ------------------------------------------------------------
// 第8题：闭包与迭代器
// ------------------------------------------------------------
// 知识点：
// - 闭包是匿名函数，可以捕获外部变量，语法：|参数| -> 返回类型 { 体 }
// - 闭包按捕获方式分为三种 trait：Fn（不可变借用）、FnMut（可变借用）、FnOnce（获取所有权）
// - Rust 的迭代器是惰性的：只有调用消费方法（如 collect）才会真正执行
// - 常见迭代器适配器：map（转换）、filter（过滤）、enumerate（带索引）、zip（配对）
// - collect 可将迭代器收集为多种集合类型，需通过类型标注指定目标类型

fn exercise_08_closures_iterators() {
    // --- 闭包基础 ---
    // 无捕获的闭包
    let add = |a: i32, b: i32| -> i32 { a + b };
    println!("闭包加法: {}", add(3, 4));

    // Fn：不可变借用外部变量
    let multiplier = 10;
    let multiply = |x: i32| x * multiplier; // 借用 multiplier
    println!("闭包乘法: {}", multiply(5));

    // FnMut：可变借用外部变量
    let mut counter = 0;
    let mut increment = || { counter += 1; };
    increment();
    increment();
    println!("FnMut 计数器: {}", counter);

    // FnOnce：获取外部变量所有权
    let name = String::from("Alice");
    let consume = move || { // move 关键字强制转移所有权
        println!("FnOnce 消费了: {}", name);
    };
    consume();
    // println!("{}", name); // 编译错误：name 已被 move

    // --- 迭代器基础 ---
    let nums = vec![1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

    // map + filter + collect 链式调用
    let doubled_evens: Vec<i32> = nums
        .iter()
        .filter(|&&x| x % 2 == 0)   // 过滤偶数
        .map(|&x| x * 2)            // 每个翻倍
        .collect();                  // 收集为 Vec
    println!("偶数翻倍: {:?}", doubled_evens);

    // enumerate 带索引迭代
    for (index, value) in nums.iter().enumerate() {
        if index < 3 {
            println!("索引 {} 的值: {}", index, value);
        }
    }

    // fold（类似 reduce）：累加
    let sum: i32 = nums.iter().fold(0, |acc, &x| acc + x);
    println!("总和: {}", sum);

    // zip：将两个迭代器配对
    let names = vec!["Alice", "Bob", "Charlie"];
    let ages = vec![25, 30, 35];
    let people: Vec<(&str, i32)> = names.iter().zip(ages.iter()).map(|(n, a)| (*n, *a)).collect();
    println!("配对结果: {:?}", people);

    // 自定义迭代器适配器链
    let result: i32 = (1..=5)
        .map(|x| x * x)        // 1,4,9,16,25
        .filter(|x| x > 5)     // 9,16,25
        .sum();                 // 50
    println!("链式结果: {}", result);
}

// 思考题：闭包的 move 关键字在什么场景下必须使用？
// 又：迭代器的惰性意味着什么？如果不调用 collect，map 中的代码会执行吗？

// ------------------------------------------------------------
// 第9题：智能指针 —— Box / Rc / RefCell
// ------------------------------------------------------------
// 知识点：
// - Box<T> 将数据分配在堆上，用于递归类型或大数据的所有权转移
// - Rc<T> 引用计数智能指针，允许多个所有者共享同一数据（不可变共享）
// - RefCell<T> 提供内部可变性，将借用检查从编译期推迟到运行期
// - Rc<RefCell<T>> 组合可实现多所有者的可变共享（常见模式）
// - Deref trait 允许智能指针像普通引用一样被解引用；Drop trait 定义值被释放时的行为

use std::rc::Rc;
use std::cell::RefCell;

// Box 用于递归类型：链表节点
#[derive(Debug)]
enum List {
    Cons(i32, Box<List>),
    Nil,
}

use List::{Cons, Nil};

// Deref trait 演示
struct MyBox<T>(T);

impl<T> std::ops::Deref for MyBox<T> {
    type Target = T;
    fn deref(&self) -> &T {
        &self.0
    }
}

impl<T> Drop for MyBox<T> {
    fn drop(&mut self) {
        println!("MyBox 被释放了");
    }
}

fn exercise_09_smart_pointers() {
    // --- Box<T> ---
    let b = Box::new(5);
    println!("Box 中的值: {}", b); // 自动解引用

    // 递归类型：使用 Box 构建链表
    let list = Cons(1, Box::new(Cons(2, Box::new(Cons(3, Box::new(Nil))))));
    println!("链表: {:?}", list);

    // --- Rc<T>：多所有者共享 ---
    let data = Rc::new(String::from("共享数据"));
    let r1 = Rc::clone(&data);
    let r2 = Rc::clone(&data);
    println!("引用计数: {}", Rc::strong_count(&data));
    println!("r1={}, r2={}", r1, r2);
    // data、r1、r2 三个所有者指向同一份数据

    // --- RefCell<T>：内部可变性 ---
    let cell = RefCell::new(vec![1, 2, 3]);
    {
        let mut borrowed = cell.borrow_mut(); // 运行期借用检查
        borrowed.push(4);
        borrowed.push(5);
    }
    println!("RefCell 内容: {:?}", cell.borrow());

    // --- Rc<RefCell<T>>：多所有者可变共享 ---
    let shared_list = Rc::new(RefCell::new(vec![10, 20]));
    let owner1 = Rc::clone(&shared_list);
    let owner2 = Rc::clone(&shared_list);

    owner1.borrow_mut().push(30); // owner1 修改
    owner2.borrow_mut().push(40); // owner2 修改
    println!("共享可变列表: {:?}", shared_list.borrow());

    // --- Deref 强制转换 ---
    let x = 5;
    let my_box = MyBox(x);
    // 自动解引用：MyBox<i32> -> i32
    println!("Deref: {}", *my_box);
}

// 思考题：RefCell 在运行期借用检查失败时会怎样？
// 又：为什么不能直接用 Rc<T> 实现可变共享，而需要 Rc<RefCell<T>>？

// ------------------------------------------------------------
// 第10题：并发编程 —— 线程、Mutex、Arc、Channel
// ------------------------------------------------------------
// 知识点：
// - thread::spawn 创建新线程，闭包中的代码在新线程执行
// - Mutex<T> 提供互斥锁，保证同一时刻只有一个线程能访问内部数据
// - Arc<T> 是原子引用计数，线程安全版的 Rc<T>，用于跨线程共享所有权
// - mpsc（多生产者单消费者）channel 用于线程间消息传递
// - Send trait 表示类型可以在线程间转移所有权，Sync 表示可以在线程间共享引用

use std::thread;
use std::sync::{Arc, Mutex, mpsc};
use std::time::Duration;

fn exercise_10_concurrency() {
    // --- 基本线程创建 ---
    let handle = thread::spawn(|| {
        for i in 1..4 {
            println!("子线程: {}", i);
            thread::sleep(Duration::from_millis(10));
        }
        42 // 返回值
    });

    for i in 1..3 {
        println!("主线程: {}", i);
        thread::sleep(Duration::from_millis(10));
    }

    let result = handle.join().unwrap(); // 等待子线程结束
    println!("子线程返回: {}", result);

    // --- move 闭包：转移所有权到线程 ---
    let data = vec![1, 2, 3];
    let handle2 = thread::spawn(move || {
        println!("线程中获取了数据所有权: {:?}", data);
    });
    handle2.join().unwrap();

    // --- Arc + Mutex：多线程共享可变数据 ---
    let counter = Arc::new(Mutex::new(0));
    let mut handles = vec![];

    for _ in 0..5 {
        let counter = Arc::clone(&counter);
        let handle = thread::spawn(move || {
            let mut num = counter.lock().unwrap(); // 获取锁
            *num += 1;
            // 锁在 num 离开作用域时自动释放
        });
        handles.push(handle);
    }

    for h in handles {
        h.join().unwrap();
    }
    println!("Arc+Mutex 计数结果: {}", *counter.lock().unwrap());

    // --- Channel：线程间消息传递 ---
    let (tx, rx) = mpsc::channel();

    // 多生产者：通过 clone 创建多个发送端
    let tx2 = tx.clone();

    let producer1 = thread::spawn(move || {
        let msgs = vec!["来自生产者1-A", "来自生产者1-B"];
        for msg in msgs {
            tx.send(msg).unwrap();
            thread::sleep(Duration::from_millis(5));
        }
    });

    let producer2 = thread::spawn(move || {
        let msgs = vec!["来自生产者2-X", "来自生产者2-Y"];
        for msg in msgs {
            tx2.send(msg).unwrap();
            thread::sleep(Duration::from_millis(5));
        }
    });

    // 接收端：持续接收直到通道关闭
    for received in rx {
        println!("收到消息: {}", received);
    }

    producer1.join().unwrap();
    producer2.join().unwrap();

    // --- Send 与 Sync 的理解 ---
    // String 实现了 Send + Sync，可以安全地跨线程使用
    // Rc<T> 没有实现 Send，因此不能跨线程使用（必须用 Arc 替代）
    let safe_string = String::from("我可以在多线程间传递");
    let h = thread::spawn(move || {
        println!("线程中安全使用: {}", safe_string);
    });
    h.join().unwrap();
}

// 思考题：为什么 Mutex 不单独使用 Arc 就不能在多线程间共享？
// 又：mpsc channel 的"多生产者单消费者"模型中，如果想要多消费者应该怎么做？

// ============================================================
// 主函数：运行所有练习
// ============================================================
fn main() {
    println!("===== 第1题：基础 =====");
    exercise_01_basics();

    println!("\n===== 第2题：所有权 =====");
    exercise_02_ownership();

    println!("\n===== 第3题：结构体与方法 =====");
    exercise_03_struct();

    println!("\n===== 第4题：枚举与模式匹配 =====");
    exercise_04_enum();

    println!("\n===== 第5题：集合与错误处理 =====");
    exercise_05_collections();

    println!("\n===== 第6题：Trait 与泛型 =====");
    exercise_06_traits();

    println!("\n===== 第7题：生命周期 =====");
    exercise_07_lifetimes();

    println!("\n===== 第8题：闭包与迭代器 =====");
    exercise_08_closures_iterators();

    println!("\n===== 第9题：智能指针 =====");
    exercise_09_smart_pointers();

    println!("\n===== 第10题：并发编程 =====");
    exercise_10_concurrency();
}
