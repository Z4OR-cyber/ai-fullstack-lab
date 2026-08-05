-- ============================================================
-- 阶段：脚本语言与系统级语言扩展练习
-- 语言：Lua
-- 题数：3题
-- 创建日期：2026-08-05
-- ============================================================

-- ============================================================
-- 第1题：Lua基础（变量 / table / 函数）
-- ============================================================

-- 【知识点讲解】
-- Lua是一种轻量级脚本语言，核心数据结构只有一种：table（表）。
-- table既可以当数组用（以1为起始索引），也可以当字典用（键值对）。
-- Lua变量默认是全局的，加local关键字才是局部变量。
-- Lua支持多返回值、可变参数、闭包等函数式特性。
-- Lua没有类的概念，但table + 函数可以模拟面向对象。

-- 1. 局部变量与全局变量
local name = "Lua学习者"      -- 局部变量，作用域有限
local age = 18                 -- 局部变量
local pi = 3.14159             -- 局部变量

-- 2. table作为数组（索引从1开始）
local fruits = {"苹果", "香蕉", "橙子"}
print("水果数量: " .. #fruits)  -- #获取数组长度
for i, v in ipairs(fruits) do  -- ipairs遍历数组部分
    print("  " .. i .. ": " .. v)
end

-- 3. table作为字典（键值对）
local person = {
    name = "张三",
    age = 25,
    ["favorite-color"] = "蓝色"  -- 非合法标识符的键需要用方括号
}
person.email = "zhangsan@example.com"  -- 动态添加字段

-- 遍历字典
for k, v in pairs(person) do
    print("  " .. k .. " = " .. tostring(v))
end

-- 4. 函数：多返回值、可变参数、闭包
local function divide(a, b)
    if b == 0 then
        return nil, "除数不能为零"
    end
    return a / b, nil
end

local result, err = divide(10, 3)
if err then
    print("错误: " .. err)
else
    print("10 / 3 = " .. result)
end

-- 可变参数函数
local function sum(...)
    local args = {...}          -- 收集为table
    local total = 0
    for _, v in ipairs(args) do
        total = total + v
    end
    return total
end
print("sum(1,2,3,4,5) = " .. sum(1, 2, 3, 4, 5))

-- 闭包：函数捕获外部局部变量
local function makeCounter()
    local count = 0
    return function()
        count = count + 1
        return count
    end
end

local counter = makeCounter()
print("计数器: " .. counter() .. ", " .. counter() .. ", " .. counter())

-- 【思考题】
-- 1. ipairs 和 pairs 的区别是什么？如果一个table同时包含数组部分和字典部分，两者遍历行为有何不同？
-- 2. Lua中为什么推荐使用local而不是全局变量？从性能和作用域角度思考。

-- ============================================================
-- 第2题：元表与面向对象（metatable / 继承 / 多态）
-- ============================================================

-- 【知识点讲解】
-- Lua没有内置的类系统，但通过元表（metatable）可以实现面向对象。
-- 元表是一个普通的table，定义了原table在特定操作下的行为。
-- __index元方法：当访问table中不存在的键时，会查找元表的__index。
-- 利用__index可以实现继承：子类找不到的方法/属性会去父类查找。
-- 多态通过重写父类方法实现。

-- 1. 定义基类：Animal
local Animal = {}
Animal.__index = Animal  -- 设置元表的__index指向自身，实现方法查找

-- 构造函数
function Animal.new(name, sound)
    local self = setmetatable({}, Animal)
    self.name = name
    self.sound = sound
    return self
end

-- 实例方法（使用冒号语法，隐式传递self）
function Animal:speak()
    return self.name .. "发出声音: " .. self.sound
end

function Animal:introduce()
    return "我是" .. self.name
end

-- 2. 定义子类：Dog，继承自Animal
local Dog = setmetatable({}, {__index = Animal})
Dog.__index = Dog  -- Dog自身的元表__index指向Dog

-- 子类构造函数
function Dog.new(name)
    local self = Animal.new(name, "汪汪")  -- 调用父类构造函数
    setmetatable(self, Dog)                 -- 重新设置元表为Dog
    return self
end

-- 重写父类方法（多态）
function Dog:introduce()
    return "我是一只狗，我叫" .. self.name
end

-- 子类新增方法
function Dog:fetch()
    return self.name .. "把球捡回来了！"
end

-- 3. 定义另一个子类：Cat
local Cat = setmetatable({}, {__index = Animal})
Cat.__index = Cat

function Cat.new(name)
    local self = Animal.new(name, "喵喵")
    setmetatable(self, Cat)
    return self
end

function Cat:introduce()
    return "我是一只高冷的猫，我叫" .. self.name
end

-- 4. 测试多态
local animals = {
    Dog.new("旺财"),
    Cat.new("咪咪"),
    Animal.new("未知生物", "..."),
}

for _, animal in ipairs(animals) do
    print(animal:introduce())       -- 多态：不同类型调用同名方法，行为不同
    print("  " .. animal:speak())   -- 继承：子类复用父类方法
end

-- 5. 元运算符重载示例
local Vector = {}
Vector.__index = Vector

function Vector.new(x, y)
    return setmetatable({x = x, y = y}, Vector)
end

-- 重载加法运算符
Vector.__add = function(a, b)
    return Vector.new(a.x + b.x, a.y + b.y)
end

-- 重载tostring
Vector.__tostring = function(v)
    return "(" .. v.x .. ", " .. v.y .. ")"
end

local v1 = Vector.new(1, 2)
local v2 = Vector.new(3, 4)
local v3 = v1 + v2  -- 触发__add
print("向量加法: " .. tostring(v1) .. " + " .. tostring(v2) .. " = " .. tostring(v3))

-- 【思考题】
-- 1. setmetatable({}, Animal) 和 setmetatable({}, {__index = Animal}) 有什么区别？
-- 2. 如果Dog也想有自己的__add元方法，应该如何设置？元表链是如何查找的？

-- ============================================================
-- 第3题：协程与嵌入（coroutine / 沙盒 / C API概念）
-- ============================================================

-- 【知识点讲解】
-- Lua的协程（coroutine）是一种协作式多任务机制，比线程轻量。
-- coroutine.create创建协程，coroutine.resume唤醒，coroutine.yield挂起。
-- 协程不是真正的并发，同一时刻只有一个协程在运行。
-- Lua设计为可嵌入C程序的脚本语言，通过C API可以创建Lua状态机、注册C函数。
-- 沙盒（sandbox）通过限制可用函数和环境，防止恶意代码访问系统资源。

-- 1. 基础协程：生产者-消费者模式
local function producer()
    for i = 1, 5 do
        coroutine.yield("产品-" .. i)  -- 挂起并产出值
    end
end

local co = coroutine.create(producer)
while coroutine.status(co) ~= "dead" do
    local ok, value = coroutine.resume(co)  -- 唤醒协程
    if value then
        print("消费者收到: " .. value)
    end
end

-- 2. 协程实现迭代器
local function rangeGen(start, stop, step)
    return coroutine.wrap(function()
        for i = start, stop, step do
            coroutine.yield(i)
        end
    end)
end

io.write("rangeGen(1,10,2): ")
for n in rangeGen(1, 10, 2) do
    io.write(n .. " ")  -- 输出: 1 3 5 7 9
end
io.write("\n")

-- 3. 协程实现异步任务调度模拟
local tasks = {}

-- 创建任务
local function createTask(taskName, duration)
    local co = coroutine.create(function()
        for i = 1, duration do
            print("  [" .. taskName .. "] 执行第 " .. i .. "/" .. duration .. " 步")
            coroutine.yield()
        end
        print("  [" .. taskName .. "] 完成！")
    end)
    table.insert(tasks, {name = taskName, co = co})
end

createTask("任务A", 3)
createTask("任务B", 5)
createTask("任务C", 2)

-- 简单的调度器：轮询所有任务
print("=== 任务调度开始 ===")
while #tasks > 0 do
    local i = 1
    while i <= #tasks do
        local task = tasks[i]
        if coroutine.status(task.co) == "dead" then
            table.remove(tasks, i)
        else
            coroutine.resume(task.co)
            i = i + 1
        end
    end
end
print("=== 所有任务完成 ===")

-- 4. 沙盒环境示例
-- 通过创建受限环境来执行不受信任的代码
local function createSandbox()
    -- 创建一个安全的环境，只暴露必要的函数
    local env = {
        print = print,
        pairs = pairs,
        ipairs = ipairs,
        tostring = tostring,
        tonumber = tonumber,
        type = type,
        math = { floor = math.floor, abs = math.abs, pi = math.pi },
        string = { upper = string.upper, lower = string.lower, len = string.len },
        -- 注意：不暴露 io、os、debug、loadfile 等危险函数
    }
    return env
end

-- 在沙盒中执行代码（概念演示）
-- load函数可以指定环境，不同Lua版本语法不同
-- Lua 5.1: loadstring(code) 然后 setfenv(func, env)
-- Lua 5.2+: load(code, nil, nil, env)
local sandboxCode = "print('沙盒中的代码执行成功') local x = math.floor(3.7) print('floor(3.7) = ' .. x)"
local sandboxEnv = createSandbox()

-- 尝试加载并执行（根据Lua版本选择API）
local func, loadErr
-- Lua 5.2+ 方式
func, loadErr = load(sandboxCode, "sandbox", "t", sandboxEnv)
if func then
    func()
else
    print("加载失败: " .. tostring(loadErr))
    -- 如果是Lua 5.1环境，使用以下方式：
    -- func = loadstring(sandboxCode)
    -- if func then setfenv(func, sandboxEnv) func() end
end

-- 5. C API 嵌入概念说明（伪代码，展示Lua与C交互的设计思想）
--[[
-- 在C程序中嵌入Lua的基本流程（伪代码）：

-- #include <lua.h>
-- #include <lualib.h>
-- #include <lauxlib.h>
--
-- int main() {
--     // 1. 创建Lua状态机
--     lua_State *L = luaL_newstate();
--
--     // 2. 打开标准库
--     luaL_openlibs(L);
--
--     // 3. 注册C函数供Lua调用
--     lua_register(L, "c_add", l_add);
--
--     // 4. 执行Lua脚本
--     luaL_dofile(L, "script.lua");
--
--     // 5. 调用Lua函数
--     lua_getglobal(L, "lua_func");
--     lua_pushnumber(L, 42);
--     lua_call(L, 1, 1);
--
--     // 6. 清理
--     lua_close(L);
--     return 0;
-- }
--
-- Lua的嵌入设计哲学：
-- 1. 极简内核 + 可扩展库，适合嵌入到游戏引擎、应用中
-- 2. C API通过栈（stack）传递值，所有数据交换都经过栈
-- 3. 沙盒机制让Lua成为安全的嵌入式脚本方案
]]

-- 【思考题】
-- 1. Lua协程与操作系统线程的本质区别是什么？协程在什么场景下更有优势？
-- 2. 如果要在沙盒中禁止访问文件系统，需要移除哪些库或函数？
