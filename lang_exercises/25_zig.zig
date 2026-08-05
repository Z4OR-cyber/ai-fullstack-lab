// ============================================================
// 阶段：脚本语言与系统级语言扩展练习
// 语言：Zig
// 题数：2题
// 创建日期：2026-08-05
// ============================================================

const std = @import("std");

// ============================================================
// 第1题：Zig基础（类型 / 控制流 / 错误集 / comptime）
// ============================================================

// 【知识点讲解】
// Zig是一种系统级编程语言，定位为C的现代替代品。
// Zig没有隐式控制流、没有隐式类型转换、没有隐藏的内存分配。
// 错误处理使用错误集（error set）和 try/catch 机制，而非异常。
// comptime是Zig的独特特性：编译期求值，可以在编译时执行代码。
// Zig没有宏，而是用comptime实现元编程能力。

// 1. 基本类型
fn basicTypes() void {
    // 整数类型
    const a: i32 = 42;
    const b: u8 = 255;
    const c: isize = -100;

    // 浮点类型
    const pi: f64 = 3.14159;
    const e: f32 = 2.71828;

    // 布尔和字符
    const flag: bool = true;
    const ch: u8 = 'A';

    // 数组
    const arr = [_]i32{ 1, 2, 3, 4, 5 };
    const arr_len = arr.len;

    // 字符串（以0结尾的字节数组指针）
    const greeting = "Hello, Zig!";

    std.debug.print("=== 基本类型 ===\n", .{});
    std.debug.print("  i32: {d}, u8: {d}, isize: {d}\n", .{ a, b, c });
    std.debug.print("  f64: {d:.4}, f32: {d:.4}\n", .{ pi, e });
    std.debug.print("  bool: {}, char: {c}\n", .{ flag, ch });
    std.debug.print("  array: {any}, len: {d}\n", .{ arr, arr_len });
    std.debug.print("  string: {s}\n", .{greeting});

    // 常量与变量
    const immutable: i32 = 100;  // 不可变
    var mutable: i32 = 200;       // 可变
    mutable += 50;
    std.debug.print("  const: {d}, var: {d}\n", .{ immutable, mutable });
}

// 2. 控制流
fn controlFlow() void {
    std.debug.print("\n=== 控制流 ===\n", .{});

    // if-else
    const x: i32 = 15;
    if (x > 10) {
        std.debug.print("  x > 10: {d}\n", .{x});
    } else {
        std.debug.print("  x <= 10: {d}\n", .{x});
    }

    // if作为表达式
    const y: i32 = if (x > 10) 1 else -1;
    std.debug.print("  if表达式: {d}\n", .{y});

    // switch
    const color: u8 = 2;
    const color_name = switch (color) {
        0 => "红",
        1 => "绿",
        2 => "蓝",
        3...5 => "其他颜色",
        else => "未知",
    };
    std.debug.print("  switch: {s}\n", .{color_name});

    // 循环：while
    var i: i32 = 0;
    while (i < 5) : (i += 1) {
        std.debug.print("  while {d}\n", .{i});
    }

    // 循环：for（遍历数组）
    const nums = [_]i32{ 10, 20, 30 };
    for (nums, 0..) |num, idx| {
        std.debug.print("  for[{d}] = {d}\n", .{ idx, num });
    }

    // break 和 continue
    var sum: i32 = 0;
    i = 0;
    while (i < 10) : (i += 1) {
        if (i == 3) continue;  // 跳过3
        if (i == 7) break;     // 7时退出
        sum += i;
    }
    std.debug.print("  sum(跳过3,7退出): {d}\n", .{sum});
}

// 3. 错误集与错误处理
const MathError = error{
    DivisionByZero,
    NegativeSqrt,
    Overflow,
};

fn safeDivide(a: i32, b: i32) !i32 {
    if (b == 0) return error.DivisionByZero;
    return @divTrunc(a, b);
}

fn safeSqrt(n: f64) !f64 {
    if (n < 0) return error.NegativeSqrt;
    return @sqrt(n);
}

fn errorHandling() void {
    std.debug.print("\n=== 错误处理 ===\n", .{});

    // try：传播错误（在函数中）
    // catch：捕获并处理错误

    const result1 = safeDivide(10, 3) catch |err| {
        std.debug.print("  除法错误: {}\n", .{err});
        return;
    };
    std.debug.print("  10 / 3 = {d}\n", .{result1});

    // 捕获特定错误
    const result2 = safeDivide(10, 0) catch |err| switch (err) {
        error.DivisionByZero => -1,
        else => unreachable,
    };
    std.debug.print("  10 / 0 (捕获) = {d}\n", .{result2});

    // 错误联合类型（!T）
    const MaybeInt = error{Invalid}!i32;
    const val: MaybeInt = 42;
    const unwrapped = val catch 0;
    std.debug.print("  错误联合: {d}\n", .{unwrapped});

    // errdefer：出错时清理资源
    {
        std.debug.print("  开始分配资源...\n", .{});
        errdefer std.debug.print("  清理资源（因错误）\n", .{});
        // 如果此处发生错误返回，errdefer会执行
        std.debug.print("  资源正常使用\n", .{});
    }
}

// 4. comptime：编译期计算
fn comptimeFactorial(comptime n: u64) u64 {
    if (n == 0) return 1;
    return n * comptimeFactorial(n - 1);
}

// 编译期生成类型
fn IntType(comptime bits: u16) type {
    return std.meta.Int(.signed, bits);
}

fn comptimeDemo() void {
    std.debug.print("\n=== comptime ===\n", .{});

    // 编译期计算
    const fact5 = comptime comptimeFactorial(5);
    std.debug.print("  5! = {d}\n", .{fact5});

    // 编译期生成类型
    const I8 = IntType(8);
    const I16 = IntType(16);
    var v8: I8 = 100;
    var v16: I16 = 30000;
    std.debug.print("  I8: {d}, I16: {d}\n", .{ v8, v16 });

    // 编译期数组操作
    const comptime_arr = comptime blk: {
        var arr: [5]i32 = undefined;
        var i: usize = 0;
        while (i < 5) : (i += 1) {
            arr[i] = @intCast(i * i);
        }
        break :blk arr;
    };
    std.debug.print("  编译期数组: {any}\n", .{comptime_arr});

    // 内联循环
    inline for (.{ "one", "two", "three" }, 0..) |s, idx| {
        std.debug.print("  inline[{d}] = {s}\n", .{ idx, s });
    }
}

// 【思考题】
// 1. Zig的错误处理与异常（try/catch）有什么本质区别？为什么Zig选择这种方式？
// 2. comptime和C++的constexpr有什么异同？comptime如何替代宏的功能？

// ============================================================
// 第2题：内存管理（分配器 / 手动内存管理 / defer）
// ============================================================

// 【知识点讲解】
// Zig没有垃圾回收（GC），内存管理完全手动。
// Zig不使用malloc/free，而是通过Allocator接口管理内存。
// 标准库提供多种分配器：GeneralPurposeAllocator、ArenaAllocator、FixedBufferAllocator。
// defer关键字确保资源在作用域结束时释放（类似Go的defer）。
// Zig的内存安全理念：没有隐藏的分配，所有分配都显式可见。

// 1. GeneralPurposeAllocator：通用分配器
fn generalAllocatorDemo() !void {
    std.debug.print("=== GeneralPurposeAllocator ===\n", .{});

    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();  // 退出时检查内存泄漏
    const allocator = gpa.allocator();

    // 分配单个值
    const ptr = try allocator.create(i32);
    defer allocator.destroy(ptr);  // 确保释放
    ptr.* = 42;
    std.debug.print("  分配的值: {d}\n", .{ptr.*});

    // 分配数组
    const arr = try allocator.alloc(u8, 5);
    defer allocator.free(arr);  // 确保释放
    for (arr, 0..) |*byte, i| {
        byte.* = @intCast(i + 1);
    }
    std.debug.print("  分配的数组: {any}\n", .{arr});
}

// 2. ArenaAllocator：竞技场分配器（一次性释放全部）
fn arenaAllocatorDemo() !void {
    std.debug.print("\n=== ArenaAllocator ===\n", .{});

    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();  // 一次性释放所有分配
    const allocator = arena.allocator();

    // 可以连续分配，无需逐个释放
    var list = std.ArrayList(i32).init(allocator);
    // defer list.deinit(); // Arena模式下不需要

    for (0..5) |i| {
        try list.append(@intCast(i * 10));
    }

    std.debug.print("  Arena列表: {any}\n", .{list.items});

    // 再分配其他内存，同样由Arena管理
    const str = try allocator.dupe(u8, "Arena分配的字符串");
    std.debug.print("  Arena字符串: {s}\n", .{str});
    // 无需 free，arena.deinit() 统一释放
}

// 3. FixedBufferAllocator：固定缓冲区分配器
fn fixedBufferDemo() !void {
    std.debug.print("\n=== FixedBufferAllocator ===\n", .{});

    var buffer: [100]u8 = undefined;
    var fba = std.heap.FixedBufferAllocator.init(&buffer);
    const allocator = fba.allocator();

    // 在固定缓冲区内分配
    const data1 = try allocator.alloc(u8, 20);
    @memset(data1, 0xAA);
    std.debug.print("  data1长度: {d}\n", .{data1.len});

    const data2 = try allocator.alloc(u8, 30);
    @memset(data2, 0xBB);
    std.debug.print("  data2长度: {d}\n", .{data2.len});

    // 缓冲区剩余空间
    std.debug.print("  剩余空间: {d}字节\n", .{buffer.len - fba.end_index});

    // 尝试超出缓冲区大小会失败
    const result = allocator.alloc(u8, 200);
    if (result) |_| {
        std.debug.print("  不应该到这里\n", .{});
    } else |_| {
        std.debug.print("  预期的分配失败（缓冲区不足）\n", .{});
    }
}

// 4. defer 和 errdefer
fn deferDemo() !void {
    std.debug.print("\n=== defer / errdefer ===\n", .{});

    // defer：作用域结束时执行（无论成功或失败）
    {
        defer std.debug.print("  defer-1 (最后执行)\n", .{});
        defer std.debug.print("  defer-2 (先执行)\n", .{});
        std.debug.print("  正常代码\n", .{});
        // LIFO顺序：先打印"defer-2"，再打印"defer-1"
    }

    // errdefer：仅在错误发生时执行
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const maybe_fail = false;
    const ptr = try allocator.create(i32);
    errdefer {
        allocator.destroy(ptr);
        std.debug.print("  errdefer执行（清理分配）\n", .{});
    }

    if (maybe_fail) {
        return error.SomethingWrong;  // 此时会触发errdefer
    }

    ptr.* = 999;
    std.debug.print("  成功赋值: {d}\n", .{ptr.*});
    allocator.destroy(ptr);  // 手动释放
}

// 5. 自定义数据结构与内存管理
const Node = struct {
    value: i32,
    next: ?*Node,  // 可空指针

    fn create(allocator: std.mem.Allocator, value: i32) !*Node {
        const node = try allocator.create(Node);
        node.* = .{ .value = value, .next = null };
        return node;
    }
};

const LinkedList = struct {
    head: ?*Node = null,
    allocator: std.mem.Allocator,

    fn init(allocator: std.mem.Allocator) LinkedList {
        return .{ .allocator = allocator };
    }

    fn prepend(self: *LinkedList, value: i32) !void {
        const node = try Node.create(self.allocator, value);
        node.next = self.head;
        self.head = node;
    }

    fn print(self: *LinkedList) void {
        var current = self.head;
        std.debug.print("  链表: ", .{});
        while (current) |node| {
            std.debug.print("{d} -> ", .{node.value});
            current = node.next;
        }
        std.debug.print("null\n", .{});
    }

    fn deinit(self: *LinkedList) void {
        var current = self.head;
        while (current) |node| {
            const next = node.next;
            self.allocator.destroy(node);
            current = next;
        }
    }
};

fn linkedListDemo() !void {
    std.debug.print("\n=== 自定义链表 ===\n", .{});

    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    var list = LinkedList.init(allocator);
    defer list.deinit();  // 确保所有节点被释放

    try list.prepend(10);
    try list.prepend(20);
    try list.prepend(30);
    try list.prepend(40);

    list.print();
}

// 【思考题】
// 1. ArenaAllocator和GeneralPurposeAllocator各自适合什么场景？为什么Arena适合短生命周期的批量分配？
// 2. defer和errdefer的区别是什么？如果在一个函数中既有defer又有errdefer，它们的执行顺序是怎样的？

// ============================================================
// 主函数：依次运行所有练习
// ============================================================
pub fn main() !void {
    // 第1题：Zig基础
    basicTypes();
    controlFlow();
    errorHandling();
    comptimeDemo();

    // 第2题：内存管理
    try generalAllocatorDemo();
    try arenaAllocatorDemo();
    try fixedBufferDemo();
    try deferDemo();
    try linkedListDemo();
}
