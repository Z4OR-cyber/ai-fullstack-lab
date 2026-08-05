// ============================================================
// 阶段标题：Go 语言练习 —— 从基础到并发与反射
// 题数：10
// 创建日期：2026-08-05
// 说明：全中文注释，代码用英文；由浅入深，自包含无外部依赖
// ============================================================

package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"reflect"
	"strconv"
	"strings"
	"sync"
	"time"
	"unsafe"
)

// ------------------------------------------------------------
// 第1题：Go 基础 —— 包、变量、常量与 iota
// ------------------------------------------------------------
// 知识点：
// - 每个 Go 文件以 package 声明开头，同一目录下的文件属于同一个包
// - 变量声明方式：var name type、var name = value、短声明 name := value（仅函数内）
// - 常量使用 const 关键字声明，可以是编译期确定的值
// - iota 是常量计数器，在每个 const 块中从 0 开始，每新增一行自动递增
// - Go 支持类型推断，:= 会根据右侧表达式自动推断左侧变量类型

// const + iota 枚举示例
const (
	Sunday    = iota // 0
	Monday            // 1
	Tuesday           // 2
	Wednesday         // 3
	Thursday          // 4
	Friday            // 5
	Saturday          // 6
)

// iota 位运算示例：权限标志
const (
	ReadPermission  = 1 << iota // 1  (二进制 0001)
	WritePermission             // 2  (二进制 0010)
	ExecutePermission           // 4  (二进制 0100)
	DeletePermission            // 8  (二进制 1000)
)

func exercise01Basics() {
	// var 声明
	var name string = "Go"
	var version = 1.21 // 类型推断为 float64
	var isActive bool  // 默认零值 false
	fmt.Printf("name=%s, version=%.2f, isActive=%v\n", name, version, isActive)

	// 短变量声明（仅函数内）
	count := 42
	message := "Hello, Go"
	fmt.Printf("count=%d, message=%s\n", count, message)

	// 多变量同时声明
	a, b, c := 1, 2.5, "three"
	fmt.Printf("a=%d, b=%.1f, c=%s\n", a, b, c)

	// 常量使用
	fmt.Printf("Sunday=%d, Saturday=%d\n", Sunday, Saturday)

	// 权限位运算
	perms := ReadPermission | WritePermission // 组合权限
	fmt.Printf("权限值: %d, 可读=%v, 可写=%v, 可执行=%v\n",
		perms,
		perms&ReadPermission != 0,
		perms&WritePermission != 0,
		perms&ExecutePermission != 0,
	)
}

// 思考题：iota 在每个 const 块中从 0 开始，
// 如果中间用下划线 _ 跳过一行，iota 的值会怎样变化？

// ------------------------------------------------------------
// 第2题：控制结构 —— if / for / switch / defer
// ------------------------------------------------------------
// 知识点：
// - if 语句支持初始化表达式：if x := getValue(); x > 0 { ... }
// - for 是 Go 中唯一的循环结构，支持 for init; cond; post、for cond、for range 三种形式
// - switch 默认不穿透（无需 break），可用 fallthrough 强制穿透到下一个 case
// - type switch 用于接口类型的动态类型判断
// - defer 按后进先出（LIFO）顺序执行，常用于资源释放

func exercise02ControlFlow() {
	// if 带初始化语句
	if num := 15; num%2 == 0 {
		fmt.Printf("%d 是偶数\n", num)
	} else {
		fmt.Printf("%d 是奇数\n", num)
	}

	// for 三种形式
	// 形式1：经典三段式
	sum := 0
	for i := 1; i <= 5; i++ {
		sum += i
	}
	fmt.Printf("1到5的和: %d\n", sum)

	// 形式2：类似 while
	n := 3
	factorial := 1
	for n > 0 {
		factorial *= n
		n--
	}
	fmt.Printf("3的阶乘: %d\n", factorial)

	// 形式3：for range 遍历
	fruits := []string{"apple", "banana", "cherry"}
	for index, fruit := range fruits {
		fmt.Printf("  fruits[%d] = %s\n", index, fruit)
	}

	// switch 语句
	grade := 'B'
	switch grade {
	case 'A':
		fmt.Println("优秀")
	case 'B':
		fmt.Println("良好")
		fmt.Println("（注意：switch 默认不穿透，不需要 break）")
	case 'C':
		fmt.Println("及格")
	default:
		fmt.Println("未知等级")
	}

	// fallthrough 强制穿透
	switch num := 1; num {
	case 1:
		fmt.Print("一 ")
		fallthrough // 强制执行下一个 case
	case 2:
		fmt.Print("二 ")
		fallthrough
	case 3:
		fmt.Println("三")
	}

	// type switch
	var val interface{} = "hello string"
	switch v := val.(type) {
	case int:
		fmt.Printf("类型是 int, 值=%d\n", v)
	case string:
		fmt.Printf("类型是 string, 值=%s\n", v)
	default:
		fmt.Printf("未知类型: %T\n", v)
	}

	// defer LIFO 顺序
	fmt.Println("=== defer 演示 ===")
	deferExample()
}

func deferExample() {
	fmt.Println("开始")
	defer fmt.Println("defer 1 (最后执行)")
	defer fmt.Println("defer 2 (倒数第二)")
	defer fmt.Println("defer 3 (最先执行)")
	fmt.Println("结束")
	// 输出顺序：开始 → 结束 → defer 3 → defer 2 → defer 1
}

// 思考题：如果 defer 语句引用了外部变量，变量的值是在 defer 声明时确定，
// 还是在 defer 实际执行时确定？（提示：参数在声明时求值）

// ------------------------------------------------------------
// 第3题：函数 —— 多返回值、命名返回值、可变参数、闭包
// ------------------------------------------------------------
// 知识点：
// - Go 函数支持多返回值，通常用于返回 (result, error) 模式
// - 命名返回值在函数开头声明并初始化为零值，return 时可裸返回
// - 可变参数使用 ...T 语法，在函数内部作为切片处理
// - 匿名函数：func(params) { ... }，可赋值给变量或立即调用
// - 闭包：匿名函数捕获外部变量，Go 中闭包按引用捕获

// 多返回值 + 命名返回值
func divide(a, b float64) (result float64, err error) {
	if b == 0 {
		err = fmt.Errorf("除数不能为零")
		return // 裸返回：返回命名返回值的当前值
	}
	result = a / b
	return
}

// 可变参数
func sumAll(nums ...int) int {
	total := 0
	for _, n := range nums {
		total += n
	}
	return total
}

// 闭包：返回一个函数，捕获外部变量
func makeCounter() func() int {
	count := 0
	return func() int {
		count++
		return count
	}
}

// 闭包：生成器模式
func makeFibonacci() func() int {
	a, b := 0, 1
	return func() int {
		result := a
		a, b = b, a+b
		return result
	}
}

func exercise03Functions() {
	// 多返回值
	result, err := divide(10, 3)
	if err != nil {
		fmt.Println("错误:", err)
	} else {
		fmt.Printf("10 / 3 = %.2f\n", result)
	}

	_, err2 := divide(5, 0)
	fmt.Println("除以零:", err2)

	// 可变参数
	fmt.Println("求和:", sumAll(1, 2, 3, 4, 5))
	fmt.Println("空参求和:", sumAll())

	// 可变参数传切片
	nums := []int{10, 20, 30}
	fmt.Println("切片展开求和:", sumAll(nums...))

	// 闭包：计数器
	counter := makeCounter()
	fmt.Println(counter(), counter(), counter()) // 1 2 3

	// 闭包：斐波那契生成器
	fib := makeFibonacci()
	fmt.Print("斐波那契: ")
	for i := 0; i < 8; i++ {
		fmt.Printf("%d ", fib())
	}
	fmt.Println()

	// 立即调用的匿名函数
	result2 := func(x, y int) int {
		return x*x + y*y
	}(3, 4)
	fmt.Printf("3² + 4² = %d\n", result2)
}

// 思考题：Go 的闭包是按引用捕获变量还是按值捕获？
// 如果在循环中创建多个闭包引用循环变量，会发生什么？

// ------------------------------------------------------------
// 第4题：数据结构 —— 切片、map 与 struct
// ------------------------------------------------------------
// 知识点：
// - 数组是固定长度的值类型，切片是对数组的引用视图（引用类型）
// - 切片底层结构包含：指针、长度(len)、容量(cap)，make() 可预分配
// - append 可能触发底层数组扩容（cap < 1024 时翻倍，之后约 1.25 倍）
// - map 是 Go 的哈希表实现，必须用 make 初始化，非线程安全
// - struct 是值类型，赋值和传参会复制整个结构体

type Person struct {
	Name string
	Age  int
}

// 嵌套结构体
type Team struct {
	Name    string
	Members []Person
	Leader  *Person // 指针字段，避免复制
}

func exercise04DataStructures() {
	// --- 数组 vs 切片 ---
	var arr [3]int = [3]int{1, 2, 3} // 数组：长度是类型的一部分
	fmt.Printf("数组: %v, 长度: %d\n", arr, len(arr))

	// 切片：从数组创建
	slice1 := arr[1:] // 从索引1到末尾
	fmt.Printf("切片: %v, len=%d, cap=%d\n", slice1, len(slice1), cap(slice1))

	// make 创建切片：指定长度和容量
	slice2 := make([]int, 3, 10) // len=3, cap=10
	fmt.Printf("make切片: %v, len=%d, cap=%d\n", slice2, len(slice2), cap(slice2))

	// append 扩容演示
	slice3 := make([]int, 0, 2)
	for i := 1; i <= 5; i++ {
		slice3 = append(slice3, i)
		fmt.Printf("  append %d: %v, len=%d, cap=%d\n", i, slice3, len(slice3), cap(slice3))
	}

	// copy 函数
	src := []int{1, 2, 3, 4, 5}
	dst := make([]int, 3)
	n := copy(dst, src) // 只复制 min(len(dst), len(src)) 个元素
	fmt.Printf("copy: dst=%v, 复制了%d个\n", dst, n)

	// --- map ---
	scores := make(map[string]int)
	scores["Alice"] = 95
	scores["Bob"] = 87
	scores["Charlie"] = 92

	// 遍历 map（顺序不保证）
	for name, score := range scores {
		fmt.Printf("  %s: %d\n", name, score)
	}

	// 检查键是否存在
	score, exists := scores["David"]
	fmt.Printf("David 存在=%v, 值=%d\n", exists, score)

	// 删除键
	delete(scores, "Bob")
	fmt.Printf("删除Bob后: %v\n", scores)

	// map 字面量初始化
	colors := map[string]string{
		"red":   "#FF0000",
		"green": "#00FF00",
		"blue":  "#0000FF",
	}
	fmt.Printf("颜色表: %v\n", colors)

	// --- struct ---
	p1 := Person{Name: "Alice", Age: 30}
	p2 := p1 // 值复制：p2 是独立的副本
	p2.Age = 25
	fmt.Printf("p1=%+v, p2=%+v (struct赋值是复制)\n", p1, p2)

	// 嵌套结构体与指针
	leader := Person{Name: "Boss", Age: 50}
	team := Team{
		Name:    "Go团队",
		Leader:  &leader,
		Members: []Person{{"Alice", 30}, {"Bob", 25}},
	}
	fmt.Printf("团队: %+v\n", team)
	fmt.Printf("队长: %s (年龄: %d)\n", team.Leader.Name, team.Leader.Age)

	// 修改指针指向的值
	leader.Age = 51
	fmt.Printf("修改后队长年龄: %d (指针共享同一份数据)\n", team.Leader.Age)
}

// 思考题：为什么 Go 的 map 不保证遍历顺序？
// 又：切片的 cap 和 len 有什么区别？为什么需要 cap？

// ------------------------------------------------------------
// 第5题：方法与接口
// ------------------------------------------------------------
// 知识点：
// - 方法的接收者可以是值类型或指针类型，决定了方法是否可以修改接收者
// - 指针接收者：方法可以修改原对象，且避免大结构体复制
// - 值接收者：方法操作的是副本，不影响原对象
// - 接口在 Go 中是隐式实现的：类型只要实现了接口中所有方法就自动满足接口
// - 类型断言用于从接口值中提取具体类型；空接口 interface{} 可接收任意类型

// 定义接口
type Shape interface {
	Area() float64
	Perimeter() float64
}

// 定义 Stringer 接口（与 fmt.Stringer 一致）
type Describer interface {
	Describe() string
}

// 矩形：使用指针接收者
type Rectangle struct {
	Width, Height float64
}

func (r *Rectangle) Area() float64 {
	return r.Width * r.Height
}

func (r *Rectangle) Perimeter() float64 {
	return 2 * (r.Width + r.Height)
}

func (r *Rectangle) Describe() string {
	return fmt.Sprintf("矩形(宽=%.1f, 高=%.1f)", r.Width, r.Height)
}

// 圆形：使用值接收者
type Circle struct {
	Radius float64
}

func (c Circle) Area() float64 {
	return 3.14159 * c.Radius * c.Radius
}

func (c Circle) Perimeter() float64 {
	return 2 * 3.14159 * c.Radius
}

func (c Circle) Describe() string {
	return fmt.Sprintf("圆形(半径=%.1f)", c.Radius)
}

// 使用接口类型的函数
func printShapeInfo(s Shape, d Describer) {
	fmt.Printf("%s → 面积=%.2f, 周长=%.2f\n", d.Describe(), s.Area(), s.Perimeter())
}

func exercise05MethodsInterfaces() {
	// 指针接收者
	rect := &Rectangle{Width: 10, Height: 5}
	printShapeInfo(rect, rect)

	// 值接收者
	circle := Circle{Radius: 3}
	printShapeInfo(circle, circle)

	// 接口切片：存储不同类型
	shapes := []Shape{
		&Rectangle{Width: 4, Height: 3},
		Circle{Radius: 5},
	}
	for _, s := range shapes {
		fmt.Printf("面积=%.2f\n", s.Area())
	}

	// 类型断言
	var i interface{} = "hello world"
	if str, ok := i.(string); ok {
		fmt.Printf("类型断言成功: %s, 长度=%d\n", str, len(str))
	}

	// type switch 处理空接口
	printType(42)
	printType(3.14)
	printType("Go")
	printType([]int{1, 2, 3})
	printType(true)

	// 空接口作为通用容器
	data := map[string]interface{}{
		"name":    "Alice",
		"age":     30,
		"active":  true,
		"scores":  []int{90, 85, 92},
	}
	fmt.Printf("通用数据: %+v\n", data)
}

func printType(v interface{}) {
	switch t := v.(type) {
	case int:
		fmt.Printf("  int: %d\n", t)
	case float64:
		fmt.Printf("  float64: %.2f\n", t)
	case string:
		fmt.Printf("  string: %q\n", t)
	case []int:
		fmt.Printf("  []int: %v\n", t)
	case bool:
		fmt.Printf("  bool: %v\n", t)
	default:
		fmt.Printf("  未知类型: %T\n", t)
	}
}

// 思考题：如果 Rectangle 使用值接收者实现 Area()，
// 那么 *Rectangle 是否还满足 Shape 接口？反过来呢？

// ------------------------------------------------------------
// 第6题：错误处理 —— error 接口与 panic-recover
// ------------------------------------------------------------
// 知识点：
// - Go 的 error 是一个内置接口：type error interface { Error() string }
// - 自定义错误类型只需实现 Error() string 方法
// - errors.New() 创建简单文本错误；fmt.Errorf() 支持格式化
// - panic 用于不可恢复的错误（如程序状态不一致），recover 在 defer 中捕获 panic
// - panic-recover 模式类似 try-catch，但 Go 鼓励显式错误处理而非异常

// 自定义错误类型
type ValidationError struct {
	Field   string
	Message string
}

func (e *ValidationError) Error() string {
	return fmt.Sprintf("验证失败 [%s]: %s", e.Field, e.Message)
}

// 另一个自定义错误类型
type NotFoundError struct {
	Resource string
}

func (e *NotFoundError) Error() string {
	return fmt.Sprintf("资源未找到: %s", e.Resource)
}

// 返回自定义错误
func validateAge(age int) error {
	if age < 0 {
		return &ValidationError{Field: "age", Message: "年龄不能为负数"}
	}
	if age > 150 {
		return &ValidationError{Field: "age", Message: "年龄不合理"}
	}
	return nil
}

func findUser(id int) (string, error) {
	users := map[int]string{1: "Alice", 2: "Bob"}
	if name, ok := users[id]; ok {
		return name, nil
	}
	return "", &NotFoundError{Resource: fmt.Sprintf("用户ID=%d", id)}
}

// 使用 fmt.Errorf 包装错误（Go 1.13+ 支持 %w 用于错误链）
func getUserAge(id int) (int, error) {
	name, err := findUser(id)
	if err != nil {
		return 0, fmt.Errorf("获取用户年龄失败: %w", err)
	}
	fmt.Printf("  找到用户: %s\n", name)
	return 30, nil // 模拟返回年龄
}

// panic-recover 模式
func safeDivision(a, b int) (result int, err error) {
	// 使用 defer + recover 捕获 panic
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("panic 被恢复: %v", r)
			result = 0
		}
	}()

	if b == 0 {
		panic("除数不能为零") // 主动 panic
	}
	return a / b, nil
}

func exercise06Errors() {
	// 基本错误检查
	if err := validateAge(-5); err != nil {
		fmt.Println("错误:", err)
		// 类型断言检查具体错误类型
		if ve, ok := err.(*ValidationError); ok {
			fmt.Printf("  字段: %s, 消息: %s\n", ve.Field, ve.Message)
		}
	}

	// errors.Is 检查错误链
	_, err := getUserAge(999)
	var notFoundErr *NotFoundError
	if errors.As(err, &notFoundErr) {
		fmt.Printf("  资源: %s\n", notFoundErr.Resource)
	}

	// panic-recover
	result, err := safeDivision(10, 0)
	if err != nil {
		fmt.Println("安全除法错误:", err)
	} else {
		fmt.Printf("10 / 0 = %d\n", result)
	}

	result2, err2 := safeDivision(10, 2)
	if err2 != nil {
		fmt.Println("错误:", err2)
	} else {
		fmt.Printf("10 / 2 = %d\n", result2)
	}

	// errors.New 简单错误
	simpleErr := errors.New("这是一个简单错误")
	fmt.Println("简单错误:", simpleErr)
}

// 思考题：什么时候应该用 panic，什么时候应该用 error 返回值？
// Go 社区对此有什么惯例？

// ------------------------------------------------------------
// 第7题：Goroutine 与 Channel
// ------------------------------------------------------------
// 知识点：
// - go 关键字启动 goroutine，是轻量级用户态线程（初始栈仅 2KB）
// - 无缓冲通道：发送和接收同步阻塞，直到另一方准备好（同步通信）
// - 有缓冲通道：缓冲区满时发送阻塞，空时接收阻塞（异步通信）
// - select 语句可以同时等待多个 channel 操作，哪个先就绪就执行哪个
// - range channel 持续接收直到通道被 close

func exercise07Goroutines() {
	// --- 基本 goroutine ---
	done := make(chan bool)
	go func() {
		fmt.Println("  goroutine 正在工作...")
		time.Sleep(50 * time.Millisecond)
		done <- true // 通知完成
	}()
	<-done // 阻塞等待通知
	fmt.Println("  goroutine 完成")

	// --- 无缓冲通道：同步通信 ---
	ch := make(chan string)
	go func() {
		msg := <-ch // 接收方准备好后发送方才能发送
		fmt.Printf("  无缓冲通道收到: %s\n", msg)
	}()
	ch <- "同步消息" // 阻塞直到接收方准备好

	// --- 有缓冲通道：异步通信 ---
	buffered := make(chan int, 3)
	for i := 1; i <= 3; i++ {
		buffered <- i // 不会阻塞，缓冲区未满
	}
	fmt.Printf("  缓冲通道长度: %d, 容量: %d\n", len(buffered), cap(buffered))

	go func() {
		for v := range buffered { // range 持续接收
			fmt.Printf("  从缓冲通道取出: %d\n", v)
		}
		fmt.Println("  缓冲通道已关闭，range 结束")
	}()

	// --- select 多路复用 ---
	ch1 := make(chan string)
	ch2 := make(chan string)

	go func() {
		time.Sleep(10 * time.Millisecond)
		ch1 <- "来自通道1"
	}()
	go func() {
		time.Sleep(20 * time.Millisecond)
		ch2 <- "来自通道2"
	}()

	// 接收先到达的消息
	for i := 0; i < 2; i++ {
		select {
		case msg1 := <-ch1:
			fmt.Printf("  select 收到: %s\n", msg1)
		case msg2 := <-ch2:
			fmt.Printf("  select 收到: %s\n", msg2)
		}
	}

	// --- close + range ---
	sender := make(chan int, 5)
	go func() {
		for i := 1; i <= 5; i++ {
			sender <- i
		}
		close(sender) // 发送完毕后关闭通道
	}()

	for num := range sender { // 通道关闭后 range 自动结束
		fmt.Printf("  range channel: %d\n", num)
	}

	// --- select 超时控制 ---
	result := make(chan string, 1)
	go func() {
		time.Sleep(100 * time.Millisecond) // 模拟慢操作
		result <- "操作完成"
	}()

	select {
	case res := <-result:
		fmt.Printf("  结果: %s\n", res)
	case <-time.After(50 * time.Millisecond):
		fmt.Println("  超时！操作太慢了")
	}

	time.Sleep(60 * time.Millisecond) // 等待上面的 goroutine 结束
}

// 思考题：无缓冲通道和有缓冲通道的区别是什么？
// 如果向一个已关闭的通道发送数据会发生什么？

// ------------------------------------------------------------
// 第8题：并发模式 —— Worker Pool / Fan-In / Pipeline / WaitGroup
// ------------------------------------------------------------
// 知识点：
// - Worker Pool 模式：固定数量的 worker goroutine 从任务队列消费任务
// - Fan-In 模式：多个 goroutine 产生数据，合并到一个输出通道
// - Pipeline 模式：数据经过多阶段处理，每阶段一个 goroutine，通过 channel 连接
// - 超时控制：使用 select + time.After 实现超时退出
// - WaitGroup：等待一组 goroutine 全部完成，Add/Done/Wait 三件套

// Worker Pool 模式
func worker(id int, jobs <-chan int, results chan<- int, wg *sync.WaitGroup) {
	defer wg.Done()
	for job := range jobs {
		fmt.Printf("  Worker %d 处理任务 %d\n", id, job)
		time.Sleep(10 * time.Millisecond) // 模拟工作
		results <- job * job               // 返回平方
	}
}

func runWorkerPool() {
	numJobs := 5
	numWorkers := 3
	jobs := make(chan int, numJobs)
	results := make(chan int, numJobs)

	var wg sync.WaitGroup

	// 启动 worker
	for w := 1; w <= numWorkers; w++ {
		wg.Add(1)
		go worker(w, jobs, results, &wg)
	}

	// 发送任务
	for j := 1; j <= numJobs; j++ {
		jobs <- j
	}
	close(jobs) // 关闭任务通道，worker 的 range 会自动结束

	// 等待所有 worker 完成，然后关闭结果通道
	go func() {
		wg.Wait()
		close(results)
	}()

	// 收集结果
	for r := range results {
		fmt.Printf("  结果: %d\n", r)
	}
}

// Fan-In 模式：合并多个通道
func fanIn(channels ...<-chan string) <-chan string {
	merged := make(chan string)
	var wg sync.WaitGroup

	for _, ch := range channels {
		wg.Add(1)
		go func(c <-chan string) {
			defer wg.Done()
			for msg := range c {
				merged <- msg
			}
		}(ch)
	}

	go func() {
		wg.Wait()
		close(merged)
	}()

	return merged
}

// Pipeline 模式：阶段1 → 阶段2 → 阶段3
func pipelineStage1(nums <-chan int) <-chan int {
	out := make(chan int)
	go func() {
		defer close(out)
		for n := range nums {
			out <- n + 1 // 每个数加1
		}
	}()
	return out
}

func pipelineStage2(in <-chan int) <-chan int {
	out := make(chan int)
	go func() {
		defer close(out)
		for n := range in {
			out <- n * 2 // 每个数乘2
		}
	}()
	return out
}

func pipelineStage3(in <-chan int) <-chan string {
	out := make(chan string)
	go func() {
		defer close(out)
		for n := range in {
			out <- fmt.Sprintf("最终结果: %d", n) // 格式化输出
		}
	}()
	return out
}

func exercise08ConcurrencyPatterns() {
	fmt.Println("  --- Worker Pool ---")
	runWorkerPool()

	fmt.Println("  --- Fan-In ---")
	ch1 := make(chan string)
	ch2 := make(chan string)
	ch3 := make(chan string)

	go func() {
		ch1 <- "生产者A-1"
		ch1 <- "生产者A-2"
		close(ch1)
	}()
	go func() {
		ch2 <- "生产者B-1"
		close(ch2)
	}()
	go func() {
		ch3 <- "生产者C-1"
		ch3 <- "生产者C-2"
		close(ch3)
	}()

	merged := fanIn(ch1, ch2, ch3)
	for msg := range merged {
		fmt.Printf("  Fan-In 收到: %s\n", msg)
	}

	fmt.Println("  --- Pipeline ---")
	source := make(chan int, 5)
	go func() {
		for i := 1; i <= 5; i++ {
			source <- i
		}
		close(source)
	}()

	// 流水线：源 → 加1 → 乘2 → 格式化
	stage1 := pipelineStage1(source)
	stage2 := pipelineStage2(stage1)
	stage3 := pipelineStage3(stage2)

	for result := range stage3 {
		fmt.Printf("  %s\n", result)
	}

	fmt.Println("  --- WaitGroup 超时控制 ---")
	done := make(chan struct{})
	go func() {
		var wg sync.WaitGroup
		for i := 1; i <= 3; i++ {
			wg.Add(1)
			go func(id int) {
				defer wg.Done()
				time.Sleep(time.Duration(id*20) * time.Millisecond)
				fmt.Printf("  任务 %d 完成\n", id)
			}(i)
		}
		wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		fmt.Println("  所有任务完成")
	case <-time.After(100 * time.Millisecond):
		fmt.Println("  超时！未全部完成")
	}
}

// 思考题：Worker Pool 模式中，为什么要在 wg.Wait() 之后才 close(results)？
// 如果先关闭 results 通道会发生什么？

// ------------------------------------------------------------
// 第9题：标准库实战 —— io / bufio / strings / strconv / json
// ------------------------------------------------------------
// 知识点：
// - io.Reader 和 io.Writer 是 Go 最核心的接口，大量标准库围绕它们构建
// - bufio 提供缓冲读写，减少系统调用次数，提高性能
// - strings 包提供字符串操作（Split, Join, Contains, Replace 等）
// - strconv 包用于字符串与基本类型之间的转换
// - encoding/json 用于 JSON 序列化和反序列化，通过结构体标签控制映射

// JSON 结构体标签
type User struct {
	ID       int      `json:"id"`
	Name     string   `json:"name"`
	Email    string   `json:"email,omitempty"` // omitempty: 空值时省略
	Roles    []string `json:"roles"`
	Active   bool     `json:"active"`
	Password string   `json:"-"` // - 表示完全忽略此字段
}

func exercise09StdLib() {
	// --- strings 包 ---
	s := "Hello,Go,World,Programming"
	parts := strings.Split(s, ",")
	fmt.Printf("  Split: %v\n", parts)
	joined := strings.Join(parts, " | ")
	fmt.Printf("  Join: %s\n", joined)
	fmt.Printf("  Contains 'World': %v\n", strings.Contains(s, "World"))
	fmt.Printf("  Replace: %s\n", strings.Replace(s, ",", ";", -1))
	fmt.Printf("  ToUpper: %s\n", strings.ToUpper(s))
	fmt.Printf("  TrimSpace: '%s'\n", strings.TrimSpace("  hello  "))

	// --- strconv 包 ---
	numStr := "42"
	num, err := strconv.Atoi(numStr)
	fmt.Printf("  Atoi('%s') = %d, err=%v\n", numStr, num, err)

	floatStr := "3.14159"
	f, _ := strconv.ParseFloat(floatStr, 64)
	fmt.Printf("  ParseFloat('%s') = %.5f\n", floatStr, f)

	fmt.Printf("  Itoa(255) = %s\n", strconv.Itoa(255))
	fmt.Printf("  FormatFloat(3.14, 'f', 2, 64) = %s\n", strconv.FormatFloat(3.14159, 'f', 2, 64))

	// --- io.Reader / Writer ---
	// 使用 bytes.Buffer 作为内存中的 Writer
	var buf bytes.Buffer
	buf.WriteString("Hello ")
	buf.WriteString("io.Writer")
	fmt.Printf("  Buffer 内容: %s\n", buf.String())

	// 从 Reader 读取数据
	reader := strings.NewReader("这是从 Reader 读取的数据")
	data, _ := io.ReadAll(reader)
	fmt.Printf("  ReadAll 结果: %s\n", string(data))

	// --- bufio 包 ---
	// bufio.Scanner 按行读取
	text := "第一行\n第二行\n第三行"
	scanner := bufio.NewScanner(strings.NewReader(text))
	lineNum := 0
	for scanner.Scan() {
		lineNum++
		fmt.Printf("  第%d行: %s\n", lineNum, scanner.Text())
	}

	// bufio.Writer 缓冲写入
	var buf2 bytes.Buffer
	writer := bufio.NewWriter(&buf2)
	writer.WriteString("缓冲写入 ")
	writer.WriteString("提高性能")
	writer.Flush() // 必须调用 Flush 将缓冲数据写入底层 Writer
	fmt.Printf("  bufio.Writer: %s\n", buf2.String())

	// --- encoding/json ---
	user := User{
		ID:       1,
		Name:     "Alice",
		Email:    "alice@example.com",
		Roles:    []string{"admin", "user"},
		Active:   true,
		Password: "secret123", // 不会出现在 JSON 中
	}

	// 序列化
	jsonBytes, _ := json.Marshal(user)
	fmt.Printf("  JSON: %s\n", string(jsonBytes))

	// 美化输出
	jsonPretty, _ := json.MarshalIndent(user, "  ", "  ")
	fmt.Printf("  JSON (pretty):\n  %s\n", string(jsonPretty))

	// 反序列化
	jsonStr := `{"id":2,"name":"Bob","email":"","roles":["user"],"active":false}`
	var user2 User
	json.Unmarshal([]byte(jsonStr), &user2)
	fmt.Printf("  反序列化: %+v\n", user2)
	fmt.Printf("  Email 被省略(omitempty): '%s'\n", user2.Email)

	// JSON 解码到 map
	jsonStr2 := `{"name":"Charlie","age":25,"city":"Beijing"}`
	var generic map[string]interface{}
	json.Unmarshal([]byte(jsonStr2), &generic)
	fmt.Printf("  解码到map: %+v\n", generic)
}

// 思考题：json:"-" 和 json:"field,omitempty" 有什么区别？
// 又：为什么 bufio.Writer 需要手动调用 Flush()？

// ------------------------------------------------------------
// 第10题：反射与 unsafe
// ------------------------------------------------------------
// 知识点：
// - reflect 包提供运行时类型检查和操作能力
// - reflect.TypeOf() 返回 reflect.Type，包含类型信息
// - reflect.ValueOf() 返回 reflect.Value，包含值信息，可通过 Interface() 还原
// - 结构体标签通过 reflect 获取，常用于 ORM/JSON/验证等框架
// - unsafe.Pointer 是底层指针操作，绕过类型系统，不安全但有时必要（如高性能场景）

// 带标签的结构体
type Config struct {
	Host     string `json:"host" env:"DB_HOST" default:"localhost"`
	Port     int    `json:"port" env:"DB_PORT" default:"3306"`
	Password string `json:"password" env:"DB_PASS"`
	Debug    bool   `json:"debug" env:"DEBUG" default:"false"`
}

// 使用反射遍历结构体字段和标签
func inspectStruct(v interface{}) {
	t := reflect.TypeOf(v)
	val := reflect.ValueOf(v)

	// 确保是结构体
	if t.Kind() == reflect.Ptr {
		t = t.Elem()
		val = val.Elem()
	}
	if t.Kind() != reflect.Struct {
		fmt.Println("  不是结构体")
		return
	}

	fmt.Printf("  类型: %s, 字段数: %d\n", t.Name(), t.NumField())
	for i := 0; i < t.NumField(); i++ {
		field := t.Field(i)
		fieldValue := val.Field(i)
		jsonTag := field.Tag.Get("json")
		envTag := field.Tag.Get("env")
		defaultTag := field.Tag.Get("default")

		fmt.Printf("    字段[%d]: %s (%s) = %v → json:%s, env:%s, default:%s\n",
			i, field.Name, field.Type, fieldValue, jsonTag, envTag, defaultTag)
	}
}

// 使用反射动态设置字段值
func setField(obj interface{}, fieldName string, newValue interface{}) error {
	v := reflect.ValueOf(obj)
	if v.Kind() != reflect.Ptr {
		return fmt.Errorf("必须传入指针")
	}
	v = v.Elem()
	field := v.FieldByName(fieldName)
	if !field.IsValid() {
		return fmt.Errorf("字段 %s 不存在", fieldName)
	}
	if !field.CanSet() {
		return fmt.Errorf("字段 %s 不可设置", fieldName)
	}
	field.Set(reflect.ValueOf(newValue))
	return nil
}

func exercise10ReflectionUnsafe() {
	// --- 基本反射 ---
	var x float64 = 3.14
	fmt.Printf("  TypeOf: %s\n", reflect.TypeOf(x))
	fmt.Printf("  ValueOf: %v\n", reflect.ValueOf(x))
	fmt.Printf("  Kind: %s\n", reflect.TypeOf(x).Kind())

	// --- 结构体反射 ---
	config := Config{
		Host:     "localhost",
		Port:     5432,
		Password: "secret",
		Debug:    true,
	}
	inspectStruct(config)

	// --- 动态设置字段值 ---
	fmt.Println("  --- 动态修改字段 ---")
	err := setField(&config, "Host", "newhost.example.com")
	if err != nil {
		fmt.Println("  错误:", err)
	}
	err = setField(&config, "Port", 3306)
	if err != nil {
		fmt.Println("  错误:", err)
	}
	fmt.Printf("  修改后: %+v\n", config)

	// --- 反射调用方法 ---
	// reflect 还可以动态调用方法（此处演示类型检查）
	t := reflect.TypeOf(config)
	fmt.Printf("  Config 类型名: %s, Kind: %s\n", t.Name(), t.Kind())

	// --- unsafe.Pointer ---
	// unsafe.Pointer 可以在不同指针类型间转换
	// 注意：这是不安全操作，实际项目慎用
	var num int = 42
	// 将 int 指针转为 int64 指针（仅演示，在不同平台可能有问题）
	ptr := unsafe.Pointer(&num)
	int64Ptr := (*int64)(ptr)
	fmt.Printf("  unsafe: int=%d, 通过int64指针读取=%d\n", num, *int64Ptr)

	// unsafe.Sizeof 查看类型大小
	fmt.Printf("  sizeof(int)=%d, sizeof(string)=%d, sizeof(bool)=%d, sizeof(Config)=%d\n",
		unsafe.Sizeof(int(0)),
		unsafe.Sizeof(""),
		unsafe.Sizeof(true),
		unsafe.Sizeof(Config{}),
	)

	// 使用 unsafe 修改字符串内容（仅演示，实际中非常危险）
	// 这里只是展示 unsafe.Pointer 的能力，不实际修改只读数据
	fmt.Printf("  unsafe.Offsetof(Config.Port)=%d\n", unsafe.Offsetof(Config{}.Port))
}

// 思考题：反射会带来什么性能开销？在什么场景下应该避免使用反射？
// 又：unsafe.Pointer 为什么被称为"不安全"？它能绕过哪些 Go 的安全保证？

// ============================================================
// 主函数：运行所有练习
// ============================================================
func main() {
	fmt.Println("===== 第1题：Go基础 =====")
	exercise01Basics()

	fmt.Println("\n===== 第2题：控制结构 =====")
	exercise02ControlFlow()

	fmt.Println("\n===== 第3题：函数 =====")
	exercise03Functions()

	fmt.Println("\n===== 第4题：数据结构 =====")
	exercise04DataStructures()

	fmt.Println("\n===== 第5题：方法与接口 =====")
	exercise05MethodsInterfaces()

	fmt.Println("\n===== 第6题：错误处理 =====")
	exercise06Errors()

	fmt.Println("\n===== 第7题：Goroutine与Channel =====")
	exercise07Goroutines()

	fmt.Println("\n===== 第8题：并发模式 =====")
	exercise08ConcurrencyPatterns()

	fmt.Println("\n===== 第9题：标准库实战 =====")
	exercise09StdLib()

	fmt.Println("\n===== 第10题：反射与unsafe =====")
	exercise10ReflectionUnsafe()
}
