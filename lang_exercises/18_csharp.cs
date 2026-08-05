// ====================================================================
// 阶段十八：C# 编程练习（8题）
// 题数：8
// 创建日期：2026-08-05
// 说明：全中文注释，代码用英文；代码语法正确，自包含无外部依赖
//       云端无编译器，代码供学习阅读；本地可用 dotnet run 运行
// ====================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace Exercises
{
    // ==================================================================
    // 第1题：C# 基础
    // 知识点：类型系统、变量、表达式、语句
    // ------------------------------------------------------------------
    // C# 是强类型语言，类型分为：
    //   - 值类型：int, double, bool, char, struct, enum（存储在栈上）
    //   - 引用类型：string, class, array, delegate（存储在堆上）
    //   - 指针类型：unsafe 上下文中使用（本练习不涉及）
    //
    // var 关键字：编译时推断类型，等价于显式声明
    // 表达式：由操作数和运算符组成，有值和类型
    // 语句：程序的最小执行单元，以分号结束
    // ==================================================================

    public class CSharpBasics
    {
        public static void Run()
        {
            Console.WriteLine("=== 第1题：C# 基础 ===");

            // --- 1.1 值类型与引用类型 ---
            // 值类型：赋值时复制值本身
            int a = 10;
            int b = a;  // 复制值
            b = 20;
            Console.WriteLine($"值类型: a={a}, b={b}");  // a=10, b=20

            // 引用类型：赋值时复制引用（指向同一对象）
            int[] arr1 = { 1, 2, 3 };
            int[] arr2 = arr1;  // 复制引用
            arr2[0] = 99;
            Console.WriteLine($"引用类型: arr1[0]={arr1[0]}, arr2[0]={arr2[0]}");  // 都是99

            // string 是特殊的引用类型，表现为值语义（不可变性）
            string s1 = "Hello";
            string s2 = s1;
            s2 = "World";
            Console.WriteLine($"字符串不可变: s1={s1}, s2={s2}");  // s1=Hello, s2=World

            // --- 1.2 常用类型转换 ---
            // 隐式转换：小范围 -> 大范围
            int intValue = 100;
            double doubleValue = intValue;  // 隐式转换
            Console.WriteLine($"隐式转换: int {intValue} -> double {doubleValue}");

            // 显式转换（强制转换）：大范围 -> 小范围，可能丢失精度
            double pi = 3.14159;
            int intPi = (int)pi;  // 截断小数部分
            Console.WriteLine($"显式转换: double {pi} -> int {intPi}");

            // Parse / TryParse：字符串转数值
            string numStr = "42";
            if (int.TryParse(numStr, out int parsedNum))
            {
                Console.WriteLine($"TryParse 成功: {parsedNum}");
            }

            // Convert 类
            string boolStr = "true";
            bool parsedBool = Convert.ToBoolean(boolStr);
            Console.WriteLine($"Convert.ToBoolean: {parsedBool}");

            // --- 1.3 运算符与表达式 ---
            int x = 10, y = 3;
            Console.WriteLine($"算术: {x} + {y} = {x + y}");
            Console.WriteLine($"取余: {x} % {y} = {x % y}");
            Console.WriteLine($"整数除法: {x} / {y} = {x / y}");
            Console.WriteLine($"浮点除法: {x} / {y} = {(double)x / y}");

            // 条件运算符（三元）
            int max = x > y ? x : y;
            Console.WriteLine($"较大值: {max}");

            // 空合并运算符 ??
            string name = null;
            string displayName = name ?? "匿名";
            Console.WriteLine($"空合并: {displayName}");

            // 空条件运算符 ?.
            string text = null;
            int? length = text?.Length;
            Console.WriteLine($"空条件: length = {length}");

            // --- 1.4 控制流语句 ---
            // if-else
            int score = 85;
            if (score >= 90)
                Console.WriteLine("优秀");
            else if (score >= 80)
                Console.WriteLine("良好");
            else
                Console.WriteLine("一般");

            // switch
            string day = "Monday";
            switch (day)
            {
                case "Monday":
                case "Tuesday":
                case "Wednesday":
                case "Thursday":
                case "Friday":
                    Console.WriteLine($"{day} 是工作日");
                    break;
                case "Saturday":
                case "Sunday":
                    Console.WriteLine($"{day} 是周末");
                    break;
                default:
                    Console.WriteLine("未知");
                    break;
            }

            // switch 表达式（C# 8.0+）
            string category = score switch
            {
                >= 90 => "A",
                >= 80 => "B",
                >= 70 => "C",
                >= 60 => "D",
                _ => "F"  // _ 是弃元模式，匹配所有其他值
            };
            Console.WriteLine($"switch 表达式: 等级 {category}");

            // for / foreach 循环
            Console.Write("for 循环: ");
            for (int i = 0; i < 5; i++)
            {
                Console.Write(i + " ");
            }
            Console.WriteLine();

            Console.Write("foreach 循环: ");
            int[] numbers = { 10, 20, 30, 40, 50 };
            foreach (int n in numbers)
            {
                Console.Write(n + " ");
            }
            Console.WriteLine();
        }
    }

    // 思考题：
    // 1. 值类型和引用类型作为参数传递时，行为有什么不同？
    // 2. ref 和 out 参数有什么区别？
    // 3. var 和 dynamic 有什么本质区别？


    // ==================================================================
    // 第2题：面向对象
    // 知识点：类、继承、接口、多态
    // ------------------------------------------------------------------
    // 面向对象三大特性：
    //   - 封装：通过访问修饰符（public/private/protected/internal）
    //     控制成员的可见性，隐藏内部实现
    //   - 继承：子类继承父类的成员，实现代码复用
    //   - 多态：同一方法在不同对象上有不同表现
    //
    // 接口：定义契约，类通过实现接口来满足契约
    //   - 接口可以包含方法、属性、事件、索引器
    //   - C# 8.0+ 支持接口默认实现
    //   - 类可以实现多个接口（弥补单继承限制）
    // ==================================================================

    // --- 2.1 抽象基类 ---
    public abstract class Shape
    {
        // 抽象属性：子类必须实现
        public abstract string Name { get; }

        // 抽象方法：子类必须重写
        public abstract double CalculateArea();

        // 虚方法：子类可选择重写
        public virtual string Describe()
        {
            return $"{Name}: 面积 = {CalculateArea():F2}";
        }
    }

    // --- 2.2 接口定义 ---
    public interface IDrawable
    {
        void Draw();  // 接口方法，实现类必须提供
    }

    public interface IResizable
    {
        void Resize(double factor);
    }

    // --- 2.3 继承 + 接口实现 ---
    public class Circle : Shape, IDrawable, IResizable
    {
        public double Radius { get; set; }

        public Circle(double radius)
        {
            Radius = radius;
        }

        // 实现抽象属性
        public override string Name => "圆形";

        // 实现抽象方法
        public override double CalculateArea()
        {
            return Math.PI * Radius * Radius;
        }

        // 实现接口方法
        public void Draw()
        {
            Console.WriteLine($"绘制圆形，半径 = {Radius}");
        }

        // 实现接口方法
        public void Resize(double factor)
        {
            Radius *= factor;
            Console.WriteLine($"调整后半径 = {Radius:F2}");
        }
    }

    public class Rectangle : Shape, IDrawable
    {
        public double Width { get; set; }
        public double Height { get; set; }

        public Rectangle(double width, double height)
        {
            Width = width;
            Height = height;
        }

        public override string Name => "矩形";

        public override double CalculateArea()
        {
            return Width * Height;
        }

        // 重写虚方法
        public override string Describe()
        {
            return $"{Name}: {Width}x{Height}, 面积 = {CalculateArea():F2}";
        }

        public void Draw()
        {
            Console.WriteLine($"绘制矩形，{Width}x{Height}");
        }
    }

    public class OOPDemo
    {
        public static void Run()
        {
            Console.WriteLine("\n=== 第2题：面向对象 ===");

            // 多态：父类引用指向子类对象
            Shape[] shapes = {
                new Circle(5),
                new Rectangle(4, 6),
                new Circle(3)
            };

            // 调用各自重写的方法（多态）
            foreach (Shape shape in shapes)
            {
                Console.WriteLine(shape.Describe());
            }

            // 接口多态：通过接口引用调用
            IDrawable[] drawables = {
                new Circle(2),
                new Rectangle(3, 4)
            };

            foreach (IDrawable drawable in drawables)
            {
                drawable.Draw();
            }

            // 类型检查与转换
            Circle circle = new Circle(10);
            if (circle is IResizable resizable)
            {
                resizable.Resize(0.5);  // 缩小一半
            }

            // as 运算符：安全类型转换，失败返回 null
            Shape s = new Rectangle(2, 3);
            Rectangle rect = s as Rectangle;
            if (rect != null)
            {
                Console.WriteLine($"as 转换成功: {rect.Width}x{rect.Height}");
            }

            // is 运算符 + 模式匹配
            if (s is Circle c)
            {
                Console.WriteLine($"半径: {c.Radius}");
            }
            else
            {
                Console.WriteLine("不是圆形");
            }
        }
    }

    // 思考题：
    // 1. 抽象类和接口有什么区别？什么时候该用哪个？
    // 2. virtual/override 和 new（隐藏）有什么区别？
    // 3. sealed 关键字的作用是什么？为什么要密封类或方法？


    // ==================================================================
    // 第3题：泛型与集合
    // 知识点：泛型方法/类、List<T>、Dictionary<K,V>、泛型约束
    // ------------------------------------------------------------------
    // 泛型允许在定义类型和方法时使用类型参数，实现类型安全的代码复用。
    //   - 泛型类：class Stack<T> { ... }
    //   - 泛型方法：T Max<T>(T a, T b) where T : IComparable<T>
    //   - 泛型约束：限制类型参数的范围
    //     where T : class        （引用类型）
    //     where T : struct       （值类型）
    //     where T : new()        （有无参构造函数）
    //     where T : IComparable  （实现某接口）
    //     where T : BaseClass    （继承某基类）
    //
    // 常用集合：
    //   List<T>：动态数组
    //   Dictionary<K,V>：键值对字典
    //   HashSet<T>：不重复元素集合
    //   Queue<T> / Stack<T>：队列 / 栈
    // ==================================================================

    // --- 3.1 泛型类：自定义栈 ---
    public class CustomStack<T>
    {
        private List<T> _items = new List<T>();
        private int _maxSize;

        // 构造函数
        public CustomStack(int maxSize = 100)
        {
            _maxSize = maxSize;
        }

        public int Count => _items.Count;

        public void Push(T item)
        {
            if (_items.Count >= _maxSize)
                throw new InvalidOperationException("栈已满");
            _items.Add(item);
        }

        public T Pop()
        {
            if (_items.Count == 0)
                throw new InvalidOperationException("栈为空");
            T item = _items[_items.Count - 1];
            _items.RemoveAt(_items.Count - 1);
            return item;
        }

        public T Peek()
        {
            if (_items.Count == 0)
                throw new InvalidOperationException("栈为空");
            return _items[_items.Count - 1];
        }

        public bool IsEmpty => _items.Count == 0;
    }

    // --- 3.2 泛型方法 + 约束 ---
    public class GenericMethods
    {
        // where T : IComparable<T> 约束：T 必须实现 IComparable<T>
        public static T Max<T>(T a, T b) where T : IComparable<T>
        {
            return a.CompareTo(b) >= 0 ? a : b;
        }

        // 多类型参数
        public static KeyValuePair<TKey, TValue> CreatePair<TKey, TValue>(TKey key, TValue value)
        {
            return new KeyValuePair<TKey, TValue>(key, value);
        }

        // where T : new() 约束：T 必须有无参构造函数
        public static T CreateInstance<T>() where T : new()
        {
            return new T();
        }

        // 多重约束
        public static T[] MakeArray<T>(int size, T defaultValue) where T : IComparable<T>
        {
            T[] arr = new T[size];
            for (int i = 0; i < size; i++)
            {
                arr[i] = defaultValue;
            }
            return arr;
        }
    }

    public class CollectionsDemo
    {
        public static void Run()
        {
            Console.WriteLine("\n=== 第3题：泛型与集合 ===");

            // --- 泛型栈使用 ---
            var intStack = new CustomStack<int>(5);
            intStack.Push(10);
            intStack.Push(20);
            intStack.Push(30);
            Console.WriteLine($"栈顶: {intStack.Peek()}");
            Console.WriteLine($"出栈: {intStack.Pop()}");
            Console.WriteLine($"剩余数量: {intStack.Count}");

            var stringStack = new CustomStack<string>(3);
            stringStack.Push("Hello");
            stringStack.Push("World");
            Console.WriteLine($"字符串栈顶: {stringStack.Peek()}");

            // --- 泛型方法 ---
            Console.WriteLine($"Max(3, 7) = {GenericMethods.Max(3, 7)}");
            Console.WriteLine($"Max(\"apple\", \"banana\") = {GenericMethods.Max("apple", "banana")}");
            Console.WriteLine($"Max(3.14, 2.72) = {GenericMethods.Max(3.14, 2.72)}");

            var pair = GenericMethods.CreatePair("age", 25);
            Console.WriteLine($"键值对: {pair.Key} = {pair.Value}");

            // --- List<T> ---
            var fruits = new List<string> { "apple", "banana", "cherry" };
            fruits.Add("date");
            fruits.AddRange(new[] { "elderberry", "fig" });
            fruits.Remove("banana");
            Console.WriteLine($"List 数量: {fruits.Count}");
            Console.WriteLine($"包含 apple: {fruits.Contains("apple")}");
            Console.WriteLine($"cherry 索引: {fruits.IndexOf("cherry")}");

            // 遍历
            Console.Write("所有水果: ");
            foreach (var fruit in fruits)
            {
                Console.Write(fruit + " ");
            }
            Console.WriteLine();

            // --- Dictionary<K, V> ---
            var scores = new Dictionary<string, int>
            {
                { "Alice", 92 },
                { "Bob", 78 },
                { "Charlie", 85 }
            };
            scores["Diana"] = 95;  // 添加或更新

            // 安全访问
            if (scores.TryGetValue("Alice", out int aliceScore))
            {
                Console.WriteLine($"Alice 的分数: {aliceScore}");
            }

            // 遍历键值对
            Console.WriteLine("所有成绩:");
            foreach (var kvp in scores)
            {
                Console.WriteLine($"  {kvp.Key}: {kvp.Value}");
            }

            // --- HashSet<T> ---
            var set1 = new HashSet<int> { 1, 2, 3, 4, 5 };
            var set2 = new HashSet<int> { 3, 4, 5, 6, 7 };
            set1.IntersectWith(set2);  // 交集
            Console.Write("交集: ");
            foreach (var n in set1) Console.Write(n + " ");
            Console.WriteLine();

            // --- Queue<T> 和 Stack<T> ---
            var queue = new Queue<string>();
            queue.Enqueue("任务1");
            queue.Enqueue("任务2");
            queue.Enqueue("任务3");
            Console.WriteLine($"队首: {queue.Peek()}");
            Console.WriteLine($"出队: {queue.Dequeue()}");

            var stack = new Stack<int>();
            stack.Push(100);
            stack.Push(200);
            Console.WriteLine($"栈顶: {stack.Peek()}");
            Console.WriteLine($"出栈: {stack.Pop()}");
        }
    }

    // 思考题：
    // 1. 泛型和非泛型集合（如 ArrayList）相比有什么优势？
    // 2. where T : class 和 where T : struct 约束分别意味着什么？
    // 3. Dictionary 内部是如何实现的？（提示：哈希表）


    // ==================================================================
    // 第4题：LINQ 查询
    // 知识点：where、select、groupBy、join、聚合操作
    // ------------------------------------------------------------------
    // LINQ（Language Integrated Query）是 C# 的内置查询语法，
    // 可以用统一的方式查询各种数据源（集合、数据库、XML 等）。
    //
    // 两种语法：
    //   - 查询语法：from ... where ... select（类似 SQL）
    //   - 方法语法：使用扩展方法（Where、Select、GroupBy 等）
    //   - 两者可以混用，方法语法更灵活
    //
    // 执行时机：
    //   - 延迟执行：Where、Select、OrderBy 等（枚举时才执行）
    //   - 立即执行：ToList、Count、Sum、First 等
    // ==================================================================

    public class Student
    {
        public int Id { get; set; }
        public string Name { get; set; }
        public int Age { get; set; }
        public string Department { get; set; }
        public List<int> Scores { get; set; }
    }

    public class Course
    {
        public int Id { get; set; }
        public string Title { get; set; }
        public string Department { get; set; }
        public int Credits { get; set; }
    }

    public class LinqDemo
    {
        public static void Run()
        {
            Console.WriteLine("\n=== 第4题：LINQ 查询 ===");

            // 准备数据
            var students = new List<Student>
            {
                new Student { Id = 1, Name = "Alice", Age = 20, Department = "CS", Scores = new List<int> { 90, 85, 92 } },
                new Student { Id = 2, Name = "Bob", Age = 22, Department = "Math", Scores = new List<int> { 78, 82, 80 } },
                new Student { Id = 3, Name = "Charlie", Age = 21, Department = "CS", Scores = new List<int> { 95, 88, 91 } },
                new Student { Id = 4, Name = "Diana", Age = 23, Department = "Physics", Scores = new List<int> { 88, 90, 85 } },
                new Student { Id = 5, Name = "Eve", Age = 20, Department = "Math", Scores = new List<int> { 72, 68, 75 } },
                new Student { Id = 6, Name = "Frank", Age = 22, Department = "Physics", Scores = new List<int> { 91, 89, 93 } }
            };

            var courses = new List<Course>
            {
                new Course { Id = 101, Title = "数据结构", Department = "CS", Credits = 4 },
                new Course { Id = 102, Title = "算法设计", Department = "CS", Credits = 3 },
                new Course { Id = 201, Title = "高等数学", Department = "Math", Credits = 5 },
                new Course { Id = 202, Title = "线性代数", Department = "Math", Credits = 4 },
                new Course { Id = 301, Title = "量子力学", Department = "Physics", Credits = 4 }
            };

            // --- 4.1 where：过滤 ---
            // 方法语法
            var csStudents = students.Where(s => s.Department == "CS").ToList();
            Console.WriteLine("CS 学生:");
            csStudents.ForEach(s => Console.WriteLine($"  {s.Name}"));

            // 查询语法
            var youngStudents = from s in students
                                where s.Age < 22
                                select s;
            Console.WriteLine("年龄 < 22 的学生:");
            foreach (var s in youngStudents)
            {
                Console.WriteLine($"  {s.Name} ({s.Age}岁)");
            }

            // --- 4.2 select：投影 ---
            var names = students.Select(s => s.Name).ToList();
            Console.WriteLine($"所有名字: {string.Join(", ", names)}");

            // 匿名类型投影
            var summaries = students.Select(s => new
            {
                s.Name,
                AvgScore = s.Scores.Average(),
                Status = s.Scores.Average() >= 85 ? "优秀" : "普通"
            }).ToList();

            Console.WriteLine("学生概要:");
            summaries.ForEach(s => Console.WriteLine($"  {s.Name}: 均分 {s.AvgScore:F1} [{s.Status}]"));

            // --- 4.3 orderBy：排序 ---
            var sortedByAge = students.OrderBy(s => s.Age).ThenByDescending(s => s.Name);
            Console.WriteLine("按年龄升序、姓名降序:");
            foreach (var s in sortedByAge)
            {
                Console.WriteLine($"  {s.Name} ({s.Age}岁)");
            }

            // --- 4.4 groupBy：分组 ---
            var groupedByDept = students.GroupBy(s => s.Department);
            Console.WriteLine("按院系分组:");
            foreach (var group in groupedByDept)
            {
                Console.WriteLine($"  {group.Key} ({group.Count()}人):");
                foreach (var s in group)
                {
                    Console.WriteLine($"    - {s.Name}");
                }
            }

            // 分组聚合
            var deptStats = students.GroupBy(s => s.Department)
                .Select(g => new
                {
                    Department = g.Key,
                    Count = g.Count(),
                    AvgAge = g.Average(s => s.Age),
                    AvgScore = g.SelectMany(s => s.Scores).Average()
                });
            Console.WriteLine("院系统计:");
            foreach (var stat in deptStats)
            {
                Console.WriteLine($"  {stat.Department}: {stat.Count}人, 平均年龄 {stat.AvgAge:F1}, 平均分 {stat.AvgScore:F1}");
            }

            // --- 4.5 join：连接查询 ---
            // 学生与课程按院系连接
            var studentCourses = from s in students
                                 join c in courses on s.Department equals c.Department
                                 select new
                                 {
                                     StudentName = s.Name,
                                     CourseTitle = c.Title,
                                     s.Department
                                 };
            Console.WriteLine("学生-课程连接:");
            foreach (var sc in studentCourses)
            {
                Console.WriteLine($"  {sc.StudentName} -> {sc.CourseTitle} ({sc.Department})");
            }

            // --- 4.6 聚合操作 ---
            Console.WriteLine("聚合统计:");
            Console.WriteLine($"  学生总数: {students.Count()}");
            Console.WriteLine($"  平均年龄: {students.Average(s => s.Age):F1}");
            Console.WriteLine($"  最大年龄: {students.Max(s => s.Age)}");
            Console.WriteLine($"  最小年龄: {students.Min(s => s.Age)}");

            // 所有分数的总和
            var totalScores = students.SelectMany(s => s.Scores).Sum();
            Console.WriteLine($"  所有分数总和: {totalScores}");

            // --- 4.7 复合查询 ---
            // 找出均分 >= 85 的学生，按均分降序排列，取前三名
            var topStudents = students
                .Select(s => new { s.Name, s.Department, AvgScore = s.Scores.Average() })
                .Where(s => s.AvgScore >= 85)
                .OrderByDescending(s => s.AvgScore)
                .Take(3)
                .ToList();

            Console.WriteLine("Top 3 学生:");
            topStudents.ForEach(s => Console.WriteLine($"  {s.Name} ({s.Department}): {s.AvgScore:F1}"));

            // --- 4.8 First/Single/Any/All ---
            var firstCs = students.First(s => s.Department == "CS");
            Console.WriteLine($"第一个 CS 学生: {firstCs.Name}");

            var anyPhysics = students.Any(s => s.Department == "Physics");
            Console.WriteLine($"有物理系学生: {anyPhysics}");

            var allHaveScores = students.All(s => s.Scores.Count > 0);
            Console.WriteLine($"所有学生都有成绩: {allHaveScores}");
        }
    }

    // 思考题：
    // 1. LINQ 的延迟执行和立即执行有什么区别？如何控制？
    // 2. SelectMany 和 Select 有什么区别？
    // 3. join 和 groupJoin 的区别是什么？


    // ==================================================================
    // 第5题：async/await 异步编程
    // 知识点：Task、async/await、异步模式
    // ------------------------------------------------------------------
    // C# 的异步编程模型：
    //   - Task：表示一个异步操作
    //   - Task<T>：表示一个有返回值的异步操作
    //   - async：标记方法为异步方法
    //   - await：等待异步操作完成（不阻塞线程）
    //
    // 核心原则：
    //   1. async 方法返回 Task 或 Task<T>（或 void，仅限事件处理器）
    //   2. await 只能在 async 方法中使用
    //   3. await 之后的代码相当于回调（continuation）
    //   4. 异步方法命名约定：以 Async 结尾
    //
    // 异常处理：
    //   - 异步方法中的异常被封装在返回的 Task 中
    //   - 使用 try-catch 包裹 await 即可捕获
    // ==================================================================

    public class AsyncDemo
    {
        // --- 5.1 模拟异步操作 ---
        // Task.Delay 相当于异步的 Thread.Sleep
        public static async Task<string> FetchDataAsync(string url, int delayMs)
        {
            Console.WriteLine($"  开始获取: {url}");
            await Task.Delay(delayMs);  // 模拟网络延迟
            Console.WriteLine($"  完成获取: {url}");
            return $"来自 {url} 的数据";
        }

        // --- 5.2 串行 vs 并行 ---
        // 串行：一个接一个执行
        public static async Task RunSequentialAsync()
        {
            Console.WriteLine("--- 串行执行 ---");
            var sw = System.Diagnostics.Stopwatch.StartNew();

            var data1 = await FetchDataAsync("api/users", 100);
            var data2 = await FetchDataAsync("api/posts", 100);
            var data3 = await FetchDataAsync("api/comments", 100);

            sw.Stop();
            Console.WriteLine($"串行总耗时: {sw.ElapsedMilliseconds}ms");
            Console.WriteLine($"  结果: {data1}, {data2}, {data3}");
        }

        // 并行：同时发起所有请求
        public static async Task RunParallelAsync()
        {
            Console.WriteLine("--- 并行执行 ---");
            var sw = System.Diagnostics.Stopwatch.StartNew();

            // Task.WhenAll 等待所有任务完成
            var tasks = new[]
            {
                FetchDataAsync("api/users", 100),
                FetchDataAsync("api/posts", 100),
                FetchDataAsync("api/comments", 100)
            };
            var results = await Task.WhenAll(tasks);

            sw.Stop();
            Console.WriteLine($"并行总耗时: {sw.ElapsedMilliseconds}ms");
            Console.WriteLine($"  结果: {string.Join(", ", results)}");
        }

        // --- 5.3 异步异常处理 ---
        public static async Task<string> RiskyFetchAsync(string url)
        {
            await Task.Delay(50);
            if (url.Contains("error"))
            {
                throw new HttpRequestException($"请求失败: {url}");
            }
            return $"成功: {url}";
        }

        public static async Task HandleAsyncErrorsAsync()
        {
            Console.WriteLine("--- 异步异常处理 ---");

            var urls = new[] { "api/ok1", "api/error", "api/ok2" };

            foreach (var url in urls)
            {
                try
                {
                    var result = await RiskyFetchAsync(url);
                    Console.WriteLine($"  {result}");
                }
                catch (HttpRequestException ex)
                {
                    Console.WriteLine($"  错误: {ex.Message}");
                }
            }
        }

        // --- 5.4 Task.WhenAny：第一个完成即返回 ---
        public static async Task RaceAsync()
        {
            Console.WriteLine("--- Task.WhenAny 竞速 ---");

            var tasks = new[]
            {
                FetchDataAsync("服务器A", 80),
                FetchDataAsync("服务器B", 50),
                FetchDataAsync("服务器C", 120)
            };

            // 第一个完成的任务
            var firstCompleted = await Task.WhenAny(tasks);
            var result = await firstCompleted;
            Console.WriteLine($"  最先完成: {result}");
        }

        // --- 5.5 带取消令牌的异步操作 ---
        public static async Task CancellableOperationAsync(CancellationToken token)
        {
            Console.WriteLine("--- 可取消的异步操作 ---");
            try
            {
                for (int i = 0; i < 10; i++)
                {
                    token.ThrowIfCancellationRequested();  // 检查是否被取消
                    Console.WriteLine($"  步骤 {i + 1}/10...");
                    await Task.Delay(50, token);  // 传入 token，取消时抛出异常
                }
                Console.WriteLine("  操作完成");
            }
            catch (OperationCanceledException)
            {
                Console.WriteLine("  操作被取消");
            }
        }

        public static async Task RunAsync()
        {
            Console.WriteLine("\n=== 第5题：async/await 异步编程 ===");

            await RunSequentialAsync();
            await RunParallelAsync();
            await HandleAsyncErrorsAsync();
            await RaceAsync();

            // 演示取消
            using var cts = new CancellationTokenSource();
            var task = CancellableOperationAsync(cts.Token);

            // 150ms 后取消
            await Task.Delay(150);
            cts.Cancel();

            try
            {
                await task;
            }
            catch (OperationCanceledException)
            {
                // 任务已取消
            }
        }
    }

    // 思考题：
    // 1. async void 和 async Task 有什么区别？为什么不推荐 async void？
    // 2. Task.Run 和直接 await 有什么区别？
    // 3. CancellationToken 是如何实现取消的？


    // ==================================================================
    // 第6题：委托与事件
    // 知识点：delegate、event、Func/Action、Lambda 表达式
    // ------------------------------------------------------------------
    // 委托（Delegate）：类型安全的函数指针，可以引用并调用方法
    //
    // 内置委托类型：
    //   - Action：无返回值（Action<int, string> 接收 int 和 string）
    //   - Func：有返回值（Func<int, string> 接收 int 返回 string）
    //   - Predicate：返回 bool（Predicate<int> 接收 int 返回 bool）
    //
    // 事件（Event）：基于委托的发布-订阅模式
    //   - event 关键字限制外部只能 += 和 -=，不能直接赋值或调用
    //   - 标准事件模式：sender + EventArgs
    // ==================================================================

    // --- 6.1 自定义委托 ---
    public delegate double MathOperation(double x, double y);

    public class DelegateDemo
    {
        // 静态方法可以作为委托目标
        public static double Add(double a, double b) => a + b;
        public static double Subtract(double a, double b) => a - b;
        public static double Multiply(double a, double b) => a * b;
        public static double Divide(double a, double b) =>
            b == 0 ? throw new DivideByZeroException() : a / b;

        public static void Run()
        {
            Console.WriteLine("\n=== 第6题：委托与事件 ===");

            // --- 委托基本用法 ---
            MathOperation op = Add;
            Console.WriteLine($"委托调用 Add(10, 3) = {op(10, 3)}");

            // 切换委托目标
            op = Multiply;
            Console.WriteLine($"委托调用 Multiply(10, 3) = {op(10, 3)}");

            // 多播委托：一个委托可以指向多个方法（按顺序调用）
            Console.WriteLine("--- 多播委托 ---");
            Action<string> logger = msg => Console.WriteLine($"[Log] {msg}");
            logger += msg => Console.WriteLine($"[Debug] {msg}");
            logger += msg => Console.WriteLine($"[Error] {msg}");
            logger("测试消息");  // 三个方法都会被调用

            // 移除一个委托
            logger -= msg => Console.WriteLine($"[Error] {msg}");
            // 注意：Lambda 无法这样移除（每次创建新实例），需用命名方法

            // --- Func 和 Action ---
            Console.WriteLine("--- Func / Action ---");
            Func<int, int, int> addFunc = (a, b) => a + b;
            Console.WriteLine($"Func: {addFunc(5, 3)}");

            Func<int, string> intToString = n => $"数字是 {n}";
            Console.WriteLine(intToString(42));

            Action<string> printAction = s => Console.WriteLine($"Action 输出: {s}");
            printAction("Hello Action");

            Predicate<int> isEven = n => n % 2 == 0;
            Console.WriteLine($"Predicate: 4 是偶数? {isEven(4)}");

            // --- 委托作为参数（回调模式）---
            var result = ApplyOperation(10, 5, (a, b) => a * b + 1);
            Console.WriteLine($"回调结果: {result}");

            // --- 事件演示 ---
            Console.WriteLine("--- 事件演示 ---");
            var heater = new WaterHeater();
            var alarm = new Alarm();
            var display = new Display();

            // 订阅事件
            heater.Boiled += alarm.MakeAlert;
            heater.Boiled += display.ShowTemperature;

            // 触发事件
            heater.BoilWater();

            // 取消订阅
            heater.Boiled -= alarm.MakeAlert;
            heater.Boiled -= display.ShowTemperature;
        }

        // 委托作为方法参数
        public static T ApplyOperation<T>(T a, T b, Func<T, T, T> operation)
        {
            return operation(a, b);
        }
    }

    // --- 6.2 事件发布者 ---
    // 自定义事件参数类
    public class BoiledEventArgs : EventArgs
    {
        public int Temperature { get; }
        public DateTime Time { get; }

        public BoiledEventArgs(int temperature)
        {
            Temperature = temperature;
            Time = DateTime.Now;
        }
    }

    // 水壶（事件发布者）
    public class WaterHeater
    {
        // 声明事件：基于 EventHandler<T> 委托
        public event EventHandler<BoiledEventArgs> Boiled;

        // 保护虚方法，子类可重写以改变事件触发逻辑
        protected virtual void OnBoiled(BoiledEventArgs e)
        {
            // ?. 防止无订阅者时空引用
            Boiled?.Invoke(this, e);
        }

        public void BoilWater()
        {
            int temperature = 20;
            for (int i = 0; i < 5; i++)
            {
                temperature += 20;
                Console.WriteLine($"  水温: {temperature}°C");

                if (temperature >= 100)
                {
                    OnBoiled(new BoiledEventArgs(temperature));
                    break;
                }
            }
        }
    }

    // --- 6.3 事件订阅者 ---
    public class Alarm
    {
        public void MakeAlert(object sender, BoiledEventArgs e)
        {
            Console.WriteLine($"  [警报] 水已烧开! 温度: {e.Temperature}°C, 时间: {e.Time:HH:mm:ss}");
        }
    }

    public class Display
    {
        public void ShowTemperature(object sender, BoiledEventArgs e)
        {
            Console.WriteLine($"  [显示屏] 当前温度: {e.Temperature}°C");
        }
    }

    // 思考题：
    // 1. event 和普通 delegate 字段有什么区别？
    // 2. Func 和 Action 的区别是什么？什么时候用自定义委托？
    // 3. 多播委托的返回值是什么？如果有多个方法，如何获取所有返回值？


    // ==================================================================
    // 第7题：属性与索引器
    // 知识点：自动属性、完整属性、只读属性、索引器
    // ------------------------------------------------------------------
    // 属性（Property）：提供对字段的受控访问，看起来像字段但实际是方法
    //   - 自动属性：{ get; set; } 编译器自动生成后端字段
    //   - 完整属性：手动编写 get/set 逻辑，可加入验证
    //   - 只读属性：只有 get（或 init，C# 9.0+）
    //   - 表达式体属性：=> 简化单行属性
    //
    // 索引器（Indexer）：让对象像数组一样通过索引访问
    //   - this[type index] 语法
    //   - 可重载（不同参数类型）
    // ==================================================================

    public class Temperature
    {
        // --- 7.1 自动属性 ---
        // 编译器自动生成私有后端字段
        public string Location { get; set; }

        // 只读自动属性（只能在构造函数中赋值）
        public DateTime CreatedAt { get; }

        // --- 7.2 完整属性（带验证） ---
        private double _celsius;

        public double Celsius
        {
            get => _celsius;
            set
            {
                // 绝对零度验证
                if (value < -273.15)
                    throw new ArgumentOutOfRangeException(nameof(value), "温度不能低于绝对零度");
                _celsius = value;
            }
        }

        // --- 7.3 计算属性（只读） ---
        public double Fahrenheit => _celsius * 9 / 5 + 32;
        public double Kelvin => _celsius + 273.15;

        // --- 7.4 init 属性（C# 9.0+，只能在初始化时赋值） ---
        public string SensorName { get; init; } = "默认传感器";

        // 构造函数
        public Temperature(string location, double celsius)
        {
            Location = location;
            Celsius = celsius;  // 通过 setter 验证
            CreatedAt = DateTime.Now;
        }
    }

    // --- 7.5 索引器 ---
    public class Matrix
    {
        private double[,] _data;
        public int Rows { get; }
        public int Cols { get; }

        public Matrix(int rows, int cols)
        {
            Rows = rows;
            Cols = cols;
            _data = new double[rows, cols];
        }

        // 整数索引器
        public double this[int row, int col]
        {
            get
            {
                ValidateIndices(row, col);
                return _data[row, col];
            }
            set
            {
                ValidateIndices(row, col);
                _data[row, col] = value;
            }
        }

        private void ValidateIndices(int row, int col)
        {
            if (row < 0 || row >= Rows)
                throw new IndexOutOfRangeException($"行索引 {row} 超出范围");
            if (col < 0 || col >= Cols)
                throw new IndexOutOfRangeException($"列索引 {col} 超出范围");
        }

        // 字符串索引器（重载）
        private Dictionary<string, (int, int)> _namedCells = new Dictionary<string, (int, int)>();

        public double this[string cellName]
        {
            get
            {
                if (_namedCells.TryGetValue(cellName, out var pos))
                    return _data[pos.Item1, pos.Item2];
                throw new KeyNotFoundException($"未找到命名单元格: {cellName}");
            }
            set
            {
                if (_namedCells.ContainsKey(cellName))
                {
                    var pos = _namedCells[cellName];
                    _data[pos.Item1, pos.Item2] = value;
                }
                else
                {
                    throw new KeyNotFoundException($"未找到命名单元格: {cellName}");
                }
            }
        }

        public void NameCell(int row, int col, string name)
        {
            _namedCells[name] = (row, col);
        }

        public override string ToString()
        {
            var sb = new System.Text.StringBuilder();
            for (int i = 0; i < Rows; i++)
            {
                for (int j = 0; j < Cols; j++)
                {
                    sb.Append(_data[i, j].ToString("F1").PadLeft(8));
                }
                sb.AppendLine();
            }
            return sb.ToString();
        }
    }

    public class PropertyDemo
    {
        public static void Run()
        {
            Console.WriteLine("\n=== 第7题：属性与索引器 ===");

            // --- 属性使用 ---
            var temp = new Temperature("北京", 25.0)
            {
                // init 属性只能在初始化时设置
                SensorName = "高精度传感器"
            };

            Console.WriteLine($"位置: {temp.Location}");
            Console.WriteLine($"摄氏: {temp.Celsius}°C");
            Console.WriteLine($"华氏: {temp.Fahrenheit:F1}°F");
            Console.WriteLine($"开尔文: {temp.Kelvin:F2}K");
            Console.WriteLine($"传感器: {temp.SensorName}");
            Console.WriteLine($"创建时间: {temp.CreatedAt:yyyy-MM-dd HH:mm:ss}");

            // 修改属性（通过 setter 验证）
            temp.Celsius = 100;
            Console.WriteLine($"沸点: {temp.Celsius}°C / {temp.Fahrenheit:F1}°F");

            // 验证异常
            try
            {
                temp.Celsius = -300;  // 低于绝对零度
            }
            catch (ArgumentOutOfRangeException ex)
            {
                Console.WriteLine($"验证拦截: {ex.Message}");
            }

            // --- 索引器使用 ---
            var matrix = new Matrix(3, 3);

            // 通过整数索引器赋值
            matrix[0, 0] = 1.0;
            matrix[0, 1] = 2.0;
            matrix[1, 1] = 5.0;
            matrix[2, 2] = 9.0;

            // 命名单元格
            matrix.NameCell(0, 0, "A1");
            matrix.NameCell(1, 1, "B2");
            matrix.NameCell(2, 2, "C3");

            // 通过字符串索引器访问
            Console.WriteLine($"A1 = {matrix["A1"]}");
            Console.WriteLine($"B2 = {matrix["B2"]}");
            Console.WriteLine($"C3 = {matrix["C3"]}");

            Console.WriteLine("矩阵内容:");
            Console.WriteLine(matrix);

            // 索引越界检查
            try
            {
                var val = matrix[10, 10];
            }
            catch (IndexOutOfRangeException ex)
            {
                Console.WriteLine($"越界拦截: {ex.Message}");
            }
        }
    }

    // 思考题：
    // 1. 自动属性的后端字段名是什么？如何访问？
    // 2. init 和 set 的区别是什么？init 有什么优势？
    // 3. 索引器和 Dictionary 有什么区别？什么场景适合用索引器？


    // ==================================================================
    // 第8题：高级特性
    // 知识点：模式匹配、records、可空引用类型、扩展方法
    // ------------------------------------------------------------------
    // C# 持续演进，引入了许多高级特性：
    //
    // 模式匹配（Pattern Matching）：
    //   - 类型模式：is Type variable
    //   - 属性模式：{ Property: value }
    //   - 元组模式：(1, 2) =>
    //   - 位置模式：基于 deconstruct
    //   - when 守卫子句：添加额外条件
    //
    // record（C# 9.0+）：
    //   - 值语义的引用类型（基于值相等性）
    //   - 自动生成 Equals、GetHashCode、ToString
    //   - 不可变性 + with 表达式（非破坏性修改）
    //
    // 可空引用类型（C# 8.0+）：
    //   - 编译时警告可能为 null 的引用
    //   - ? 标注可空，! 断言非空
    //
    // 扩展方法：
    //   - 在不修改原类型的情况下添加方法
    //   - 必须在静态类的静态方法中，第一个参数加 this
    // ==================================================================

    // --- 8.1 record 类型 ---
    // record 自动生成：构造函数、Equals、GetHashCode、ToString、Deconstruct
    public record Point(double X, double Y)
    {
        // 可添加额外成员
        public double DistanceFromOrigin() => Math.Sqrt(X * X + Y * Y);

        // 自定义验证
        public string Quadrant => (X, Y) switch
        {
            ( > 0, > 0) => "第一象限",
            ( < 0, > 0) => "第二象限",
            ( < 0, < 0) => "第三象限",
            ( > 0, < 0) => "第四象限",
            (0, _) => "在Y轴上",
            (_, 0) => "在X轴上",
        };
    }

    // 可变 record（较少使用）
    public record MutableConfig
    {
        public string Host { get; set; }
        public int Port { get; set; }
        public bool Debug { get; set; }
    }

    // --- 8.2 扩展方法 ---
    public static class StringExtensions
    {
        // this string 表示对 string 类型扩展
        public static bool IsNullOrEmpty(this string value)
        {
            return string.IsNullOrEmpty(value);
        }

        public static string Repeat(this string value, int count)
        {
            if (value == null) return null;
            return string.Concat(Enumerable.Repeat(value, count));
        }

        public static string Capitalize(this string value)
        {
            if (string.IsNullOrEmpty(value)) return value;
            return char.ToUpper(value[0]) + value.Substring(1);
        }

        public static int WordCount(this string value)
        {
            if (string.IsNullOrEmpty(value)) return 0;
            return value.Split(new[] { ' ', '\t', '\n', '\r' },
                StringSplitOptions.RemoveEmptyEntries).Length;
        }
    }

    public static class EnumerableExtensions
    {
        // 对 IEnumerable<T> 扩展
        public static string JoinToString<T>(this IEnumerable<T> source, string separator)
        {
            return string.Join(separator, source);
        }

        public static void ForEach<T>(this IEnumerable<T> source, Action<T> action)
        {
            foreach (var item in source)
            {
                action(item);
            }
        }
    }

    public class AdvancedFeaturesDemo
    {
        // --- 8.3 模式匹配 ---
        public static string ClassifyShape(object shape)
        {
            // switch 表达式 + 模式匹配
            return shape switch
            {
                // 类型模式 + 属性模式 + when 守卫
                Circle { Radius: > 10 } => "大圆形",
                Circle c => $"圆形(半径{c.Radius})",
                Rectangle { Width: var w, Height: var h } when w == h => "正方形",
                Rectangle r => $"矩形({r.Width}x{r.Height})",
                null => "空",
                _ => "未知形状"
            };
        }

        // 元组模式
        public static string GetDirection(int dx, int dy)
        {
            return (dx, dy) switch
            {
                (0, 0) => "原点",
                ( > 0, 0) => "东",
                ( < 0, 0) => "西",
                (0, > 0) => "北",
                (0, < 0) => "南",
                ( > 0, > 0) => "东北",
                ( < 0, > 0) => "西北",
                ( > 0, < 0) => "东南",
                ( < 0, < 0) => "西南",
                _ => "未知"
            };
        }

        // 列表模式（C# 11+）
        public static string AnalyzeNumbers(int[] arr)
        {
            return arr switch
            {
                [] => "空数组",
                [single] => $"单元素: {single}",
                [first, second] => $"两元素: {first}, {second}",
                [first, .., last] => $"首尾: {first}...{last}",
                _ => "其他"
            };
        }

        public static void Run()
        {
            Console.WriteLine("\n=== 第8题：高级特性 ===");

            // --- record 使用 ---
            Console.WriteLine("--- record 类型 ---");
            var p1 = new Point(3, 4);
            var p2 = new Point(3, 4);
            var p3 = new Point(-2, 5);

            // 值相等性（自动生成）
            Console.WriteLine($"p1 == p2: {p1 == p2}");  // True
            Console.WriteLine($"p1.Equals(p2): {p1.Equals(p2)}");  // True

            // 自动生成的 ToString
            Console.WriteLine($"ToString: {p1}");

            // with 表达式：非破坏性修改（创建副本）
            var p4 = p1 with { X = 10 };
            Console.WriteLine($"with 修改: {p4} (原: {p1})");

            // 自定义方法
            Console.WriteLine($"距原点距离: {p1.DistanceFromOrigin()}");

            // 模式匹配属性
            Console.WriteLine($"p1 象限: {p1.Quadrant}");
            Console.WriteLine($"p3 象限: {p3.Quadrant}");

            // Deconstruct（自动生成）
            var (x, y) = p1;
            Console.WriteLine($"解构: x={x}, y={y}");

            // --- 模式匹配 ---
            Console.WriteLine("--- 模式匹配 ---");
            Console.WriteLine(ClassifyShape(new Circle(15)));     // 大圆形
            Console.WriteLine(ClassifyShape(new Circle(5)));       // 圆形(半径5)
            Console.WriteLine(ClassifyShape(new Rectangle(4, 4))); // 正方形
            Console.WriteLine(ClassifyShape(new Rectangle(3, 6))); // 矩形(3x6)

            Console.WriteLine($"方向: {GetDirection(1, 0)}");
            Console.WriteLine($"方向: {GetDirection(-1, 1)}");
            Console.WriteLine($"方向: {GetDirection(0, 0)}");

            Console.WriteLine(AnalyzeNumbers(new int[] { }));
            Console.WriteLine(AnalyzeNumbers(new[] { 42 }));
            Console.WriteLine(AnalyzeNumbers(new[] { 1, 2 }));
            Console.WriteLine(AnalyzeNumbers(new[] { 1, 2, 3, 4, 5 }));

            // --- 扩展方法 ---
            Console.WriteLine("--- 扩展方法 ---");
            string text = "hello world from csharp";
            Console.WriteLine($"是否为空: {" ".IsNullOrEmpty()}");  // False
            Console.WriteLine($"是否为空: {"".IsNullOrEmpty()}");   // True
            Console.WriteLine($"重复: {"ab".Repeat(3)}");           // ababab
            Console.WriteLine($"首字母大写: {"hello".Capitalize()}");
            Console.WriteLine($"单词数: {text.WordCount()}");       // 4

            // 对集合的扩展方法
            var nums = new List<int> { 1, 2, 3, 4, 5 };
            Console.WriteLine($"连接: {nums.JoinToString(" - ")}");
            nums.ForEach(n => Console.Write(n + " "));
            Console.WriteLine();

            // --- 可空引用类型 ---
            Console.WriteLine("--- 可空引用类型 ---");

            // string? 表示可能为 null
            string? maybeNull = null;
            string definitelyNotNull = "有值";

            // 空条件访问
            int? len = maybeNull?.Length;
            Console.WriteLine($"可空字符串长度: {len ?? -1}");

            // 空合并赋值
            maybeNull ??= "现在有值了";
            Console.WriteLine($"赋值后: {maybeNull}");

            // ! 断言非空（告诉编译器"我知道它不为 null"）
            string forced = maybeNull!;
            Console.WriteLine($"断言非空: {forced}");
        }
    }

    // 思考题：
    // 1. record 和 class 的区别是什么？什么场景适合用 record？
    // 2. with 表达式是如何实现非破坏性修改的？
    // 3. 扩展方法能访问类型的私有成员吗？为什么？


    // ==================================================================
    // 主程序入口
    // ==================================================================
    public class Program
    {
        public static void Main(string[] args)
        {
            Console.WriteLine("====================================");
            Console.WriteLine("C# 编程练习 - 阶段十八");
            Console.WriteLine("创建日期: 2026-08-05");
            Console.WriteLine("====================================\n");

            // 依次运行各题
            CSharpBasics.Run();
            OOPDemo.Run();
            CollectionsDemo.Run();
            LinqDemo.Run();
            AsyncDemo.RunAsync().Wait();
            DelegateDemo.Run();
            PropertyDemo.Run();
            AdvancedFeaturesDemo.Run();

            Console.WriteLine("\n====================================");
            Console.WriteLine("所有练习执行完毕！");
            Console.WriteLine("====================================");
        }
    }
}
