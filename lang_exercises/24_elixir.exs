# ============================================================
# 阶段：函数式并发语言 - Elixir语言练习
# 题数：3题
# 创建日期：2026-08-05
# ============================================================

# ============================================================
# 第1题：Elixir基础（模式匹配 / 不可变数据 / 管道运算符）
# ============================================================
# 知识点讲解：
# Elixir是运行在Erlang虚拟机(BEAM)上的函数式语言，继承了Erlang的
# 高并发、高容错能力，同时拥有现代语法。
# 核心特性：
#   - 不可变数据：所有数据结构不可变，"修改"实际上是创建新副本
#   - 模式匹配：用 = 进行模式匹配（不是赋值），解构数据结构
#   - 管道运算符 |>：将前一个表达式的结果作为后一个函数的第一个参数
#   - 一切皆表达式：没有语句，所有结构都返回值
#   - 原子(Atom)：以冒号开头的常量，类似Ruby的Symbol

# --- 基本数据类型 ---
int_val = 42                  # 整数
float_val = 3.14              # 浮点数
atom_val = :ok                # 原子（类似枚举值）
string_val = "Hello"          # 字符串（二进制）
charlist_val = 'Hello'        # 字符列表（单引号，每个元素是整数）
bool_val = true               # 布尔值（true/false是原子）

IO.puts("=== 基本数据类型 ===")
IO.inspect(int_val, label: "整数")
IO.inspect(float_val, label: "浮点数")
IO.inspect(atom_val, label: "原子")
IO.inspect(string_val, label: "字符串")
IO.inspect(bool_val, label: "布尔值")

# --- 模式匹配 ---
# Elixir的 = 是模式匹配，不是赋值
# 左边是模式，右边是值，如果匹配成功则绑定变量

# 基本模式匹配
{x, y, z} = {1, 2, 3}
IO.puts("\n=== 模式匹配 ===")
IO.puts("x=#{x}, y=#{y}, z=#{z}")

# 忽略不需要的值（下划线）
{a, _, c} = {10, 20, 30}
IO.puts("a=#{a}, c=#{c} (忽略了第二个值)")

# 列表模式匹配
[head | tail] = [1, 2, 3, 4, 5]
IO.puts("head=#{head}, tail=#{inspect(tail)}")

# 映射(Map)模式匹配
%{name: name, age: age} = %{name: "Alice", age: 30, city: "NYC"}
IO.puts("name=#{name}, age=#{age}")

# 带守卫的模式匹配
case {1, 2, 3} do
  {1, x, 3} when x > 0 -> IO.puts("匹配到中间值为正数: #{x}")
  {1, _, _}            -> IO.puts("匹配到首元素为1")
  _                    -> IO.puts("其他情况")
end

# --- 不可变数据 ---
IO.puts("\n=== 不可变数据 ===")
original_list = [1, 2, 3]
new_list = [0 | original_list]  # 在头部添加元素，创建新列表
IO.puts("原始列表: #{inspect(original_list)}")  # 仍然是 [1, 2, 3]
IO.puts("新列表: #{inspect(new_list)}")          # [0, 1, 2, 3]

original_map = %{a: 1, b: 2}
updated_map = Map.put(original_map, :c, 3)
IO.puts("原始Map: #{inspect(original_map)}")     # 仍然是 %{a: 1, b: 2}
IO.puts("更新后Map: #{inspect(updated_map)}")     # %{a: 1, b: 2, c: 3}

# --- 管道运算符 |> ---
# 管道运算符将左边的值作为右边函数的第一个参数
# 这让代码读起来像"数据流水线"

IO.puts("\n=== 管道运算符 ===")

# 不用管道的写法（嵌套调用，从内到外读）
result1 = Enum.reverse(Enum.map(Enum.filter([1, 2, 3, 4, 5, 6], fn x -> rem(x, 2) == 0 end), fn x -> x * 10 end))
IO.puts("不用管道: #{inspect(result1)}")

# 用管道的写法（从上到下读，清晰自然）
result2 = [1, 2, 3, 4, 5, 6]
  |> Enum.filter(fn x -> rem(x, 2) == 0 end)
  |> Enum.map(fn x -> x * 10 end)
  |> Enum.reverse()
IO.puts("用管道: #{inspect(result2)}")

# --- 函数定义 ---
# 命名函数用 def 定义（在模块内），匿名函数用 fn ... end

defmodule MathUtils do
  # 公有函数
  def square(x), do: x * x

  # 多个子句：模式匹配
  def area(:circle, radius), do: 3.14159 * radius * radius
  def area(:rectangle, w, h), do: w * h
  def area(:triangle, base, height), do: 0.5 * base * height

  # 带默认参数
  def greet(name, greeting \\ "你好") do
    "#{greeting}, #{name}!"
  end

  # 私有函数
  defp helper(x), do: x + 1

  # 递归：计算阶乘
  def factorial(0), do: 1
  def factorial(n) when n > 0, do: n * factorial(n - 1)

  # 尾递归优化版本（累加器模式）
  def factorial_tr(n), do: do_factorial(n, 1)
  defp do_factorial(0, acc), do: acc
  defp do_factorial(n, acc) when n > 0, do: do_factorial(n - 1, n * acc)
end

IO.puts("\n=== 函数定义 ===")
IO.puts("square(5) = #{MathUtils.square(5)}")
IO.puts("circle area = #{MathUtils.area(:circle, 3)}")
IO.puts("rectangle area = #{MathUtils.area(:rectangle, 4, 5)}")
IO.puts("greet = #{MathUtils.greet("Elixir")}")
IO.puts("greet custom = #{MathUtils.greet("World", "Hello")}"
)
IO.puts("factorial(5) = #{MathUtils.factorial(5)}")
IO.puts("factorial_tr(5) = #{MathUtils.factorial_tr(5)}")

# --- 匿名函数 ---
IO.puts("\n=== 匿名函数 ===")
add = fn a, b -> a + b end
IO.puts("add(3, 4) = #{add.(3, 4)}")

# 捕获运算符 &（简写匿名函数）
square = &(&1 * &1)
double = &(&1 * 2)
IO.puts("square(6) = #{square.(6)}")
IO.puts("double(7) = #{double.(7)}")

# --- Enum模块：列表操作 ---
IO.puts("\n=== Enum模块 ===")
nums = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

IO.puts("求和: #{Enum.sum(nums)}")
IO.puts("平均值: #{Enum.sum(nums) / Enum.count(nums)}")
IO.puts("最大值: #{Enum.max(nums)}")
IO.puts("偶数: #{inspect(Enum.filter(nums, fn x -> rem(x, 2) == 0 end))}"
)
IO.puts("平方: #{inspect(Enum.map(nums, fn x -> x * x end))}")
IO.puts("reduce求积: #{Enum.reduce(nums, 1, fn x, acc -> x * acc end)}")
IO.puts("分组奇偶: #{inspect(Enum.group_by(nums, fn x -> if rem(x, 2) == 0, do: :even, else: :odd end))}")

# --- 字符串操作 ---
IO.puts("\n=== 字符串操作 ===")
sentence = "Elixir is a functional language"
words = String.split(sentence, " ")
IO.puts("单词数: #{length(words)}")
IO.puts("大写: #{String.upcase(sentence)}")
IO.puts("替换: #{String.replace(sentence, "functional", "concurrent")}"
)
IO.puts("包含?: #{String.contains?(sentence, "Elixir")}"

# --- with表达式：链式模式匹配 ---
IO.puts("\n=== with表达式 ===")
defmodule UserService do
  defp find_user(id) do
    users = %{1 => %{name: "Alice", active: true}, 2 => %{name: "Bob", active: false}}
    Map.get(users, id)
  end

  defp check_active(%{active: true} = user), do: {:ok, user}
  defp check_active(%{active: false}), do: {:error, :inactive}
  defp check_active(nil), do: {:error, :not_found}

  def get_active_user(id) do
    with {:ok, user} <- find_user(id) |> case do
          nil -> {:error, :not_found}
          u -> {:ok, u}
        end,
         {:ok, active_user} <- check_active(user) do
      {:ok, "活跃用户: #{active_user.name}"}
    else
      {:error, :not_found} -> {:error, "用户不存在"}
      {:error, :inactive} -> {:error, "用户未激活"}
    end
  end
end

IO.inspect(UserService.get_active_user(1), label: "用户1")
IO.inspect(UserService.get_active_user(2), label: "用户2")
IO.inspect(UserService.get_active_user(3), label: "用户3")

# 思考题：Elixir的 = 是"赋值"还是"模式匹配"？
#         管道运算符 |> 如何改变了代码的阅读方式？
#         什么是"尾递归优化"？为什么Elixir推荐使用累加器模式？

# ============================================================
# 第2题：并发与OTP（GenServer / 进程 / 消息传递）
# ============================================================
# 知识点讲解：
# Elixir的并发模型基于Actor模型，每个"进程"是轻量级的（约2KB内存），
# 可以创建数百万个。进程间通过消息传递通信，不共享内存。
#
# OTP(Open Telecom Platform)是Erlang/Elixir的并发框架，核心组件：
#   - GenServer：通用服务器行为，封装了进程的收发消息循环
#   - Supervisor：监控器，负责进程的启动、停止和重启
#   - Application：应用，由Supervisor树组成
#
# GenServer的标准模式：
#   1. 客户端API：调用 GenServer.call/cast
#   2. 服务端回调：handle_call/handle_cast/handle_info
#   - call：同步请求，等待回复
#   - cast：异步请求，不等待回复（fire and forget）

# --- 基础进程操作 ---
IO.puts("=== 基础进程 ===")

# spawn 创建新进程，返回PID
pid = spawn(fn ->
  receive do
    {:hello, sender} ->
      send(sender, {:response, "你好！"})
    {:bye, _sender} ->
      IO.puts("收到再见消息")
  end
end)

# 发送消息
send(pid, {:hello, self()})

# 接收回复
receive do
  {:response, msg} -> IO.puts("收到回复: #{msg}")
after
  1000 -> IO.puts("超时")
end

# --- 进程链接 ---
IO.puts("\n=== 进程链接 ===")

# spawn_link 创建链接进程，一个退出另一个也退出
# spawn_monitor 创建监控进程，一个退出另一个收到通知
defmodule ProcessDemo do
  def monitor_demo do
    # 创建被监控的进程
    {pid, ref} = spawn_monitor(fn ->
      Process.sleep(100)
      # 模拟崩溃
      exit(:boom)
    end)

    # 接收监控消息
    receive do
      {:DOWN, ^ref, :process, ^pid, reason} ->
        IO.puts("进程 #{inspect(pid)} 退出，原因: #{reason}")
    end
  end
end

ProcessDemo.monitor_demo()

# --- GenServer实现：计数器 ---
# GenServer是OTP的核心组件，封装了进程通信的模板代码

defmodule Counter do
  use GenServer

  # === 客户端API ===

  def start_link(initial \\ 0) do
    GenServer.start_link(__MODULE__, initial, name: __MODULE__)
  end

  def increment, do: GenServer.cast(__MODULE__, :increment)
  def decrement, do: GenServer.cast(__MODULE__, :decrement)
  def value, do: GenServer.call(__MODULE__, :value)
  def set_value(new_val), do: GenServer.cast(__MODULE__, {:set, new_val})

  # === 服务端回调 ===

  @impl true
  def init(initial) do
    {:ok, initial}
  end

  # 同步请求：handle_call(请求, 发送者PID, 当前状态)
  @impl true
  def handle_call(:value, _from, state) do
    {:reply, state, state}
  end

  # 异步请求：handle_cast(请求, 当前状态)
  @impl true
  def handle_cast(:increment, state) do
    {:noreply, state + 1}
  end

  @impl true
  def handle_cast(:decrement, state) do
    {:noreply, state - 1}
  end

  @impl true
  def handle_cast({:set, new_val}, _state) do
    {:noreply, new_val}
  end

  # 处理普通消息（非GenServer请求）
  @impl true
  def handle_info(msg, state) do
    IO.puts("收到消息: #{inspect(msg)}")
    {:noreply, state}
  end
end

# --- 使用计数器 ---
# 注意：实际运行需要在一个Application或iex会话中
IO.puts("\n=== GenServer计数器（概念演示）===")
IO.puts("""
# 启动计数器
{:ok, _pid} = Counter.start_link(0)

# 操作计数器
Counter.increment()
Counter.increment()
Counter.increment()
Counter.decrement()

# 查询当前值
Counter.value()  # => 2

# 设置值
Counter.set_value(100)
Counter.value()  # => 100
""")

# --- GenServer实现：键值存储 ---
defmodule KVStore do
  use GenServer

  # 客户端API
  def start_link do
    GenServer.start_link(__MODULE__, %{}, name: __MODULE__)
  end

  def put(key, value), do: GenServer.cast(__MODULE__, {:put, key, value})
  def get(key), do: GenServer.call(__MODULE__, {:get, key})
  def delete(key), do: GenServer.cast(__MODULE__, {:delete, key})
  def all, do: GenServer.call(__MODULE__, :all)

  # 服务端回调
  @impl true
  def init(_), do: {:ok, %{}}

  @impl true
  def handle_call({:get, key}, _from, state) do
    {:reply, Map.get(state, key), state}
  end

  @impl true
  def handle_call(:all, _from, state) do
    {:reply, state, state}
  end

  @impl true
  def handle_cast({:put, key, value}, state) do
    {:noreply, Map.put(state, key, value)}
  end

  @impl true
  def handle_cast({:delete, key}, state) do
    {:noreply, Map.delete(state, key)}
  end
end

IO.puts("\n=== GenServer键值存储（概念演示）===")
IO.puts("""
# 启动KV存储
{:ok, _} = KVStore.start_link()

# 存取数据
KVStore.put(:name, "Alice")
KVStore.put(:age, 30)
KVStore.get(:name)     # => "Alice"
KVStore.get(:age)      # => 30
KVStore.all()          # => %{name: "Alice", age: 30}
KVStore.delete(:age)
KVStore.get(:age)      # => nil
""")

# --- Supervisor概念 ---
IO.puts("\n=== Supervisor概念 ===")
IO.puts("""
# Supervisor负责监控和重启进程
# 子进程规格(child_spec)定义了启动方式和重启策略

defmodule MyApp.Supervisor do
  use Supervisor

  def start_link do
    Supervisor.start_link(__MODULE__, :ok, name: __MODULE__)
  end

  def init(:ok) do
    children = [
      {Counter, 0},        # 子进程1：计数器
      {KVStore, []},       # 子进程2：键值存储
    ]

    # 重启策略：
    # :one_for_one  - 只重启崩溃的进程
    # :one_for_all  - 重启所有子进程
    # :rest_for_one - 重启崩溃进程及其后面的进程
    Supervisor.init(children, strategy: :one_for_one)
  end
end
""")

# --- Task：轻量级并发任务 ---
IO.puts("=== Task并发 ===")

# Task用于执行一次性并发任务
# async创建任务，await等待结果
results =
  1..5
  |> Enum.map(fn n -> Task.async(fn -> n * n end) end)
  |> Enum.map(fn task -> Task.await(task) end)

IO.puts("并发计算平方: #{inspect(results)}")

# Task.async_stream：流式并发处理
stream_results =
  1..10
  |> Task.async_stream(fn n -> n * 2 end, max_concurrency: 4)
  |> Enum.map(fn {:ok, result} -> result end)

IO.puts("流式并发: #{inspect(stream_results)}")

# --- Agent：简化状态管理 ---
IO.puts("\n=== Agent ===")

# Agent是GenServer的简化版，适合简单的状态存储
{:ok, agent} = Agent.start_link(fn -> [] end)

Agent.update(agent, fn state -> ["item1" | state] end)
Agent.update(agent, fn state -> ["item2" | state] end)
current = Agent.get(agent, fn state -> state end)
IO.puts("Agent状态: #{inspect(current)}")

# 思考题：Elixir的进程和操作系统的线程/进程有什么区别？
#         GenServer的call和cast有什么区别？各自适用于什么场景？
#         Supervisor的重启策略(:one_for_one vs :one_for_all)在什么场景下选择哪个？

# ============================================================
# 第3题：宏与元编程（quote / unquote / 宏定义）
# ============================================================
# 知识点讲解：
# Elixir的元编程基于Lisp的 homoiconicity 特性——代码即数据。
# 代码在编译前会被解析为抽象语法树(AST)，而AST本身就是Elixir数据结构。
#
# 核心概念：
#   - quote：将代码转换为AST（不执行，返回表达式元组）
#   - unquote：在quote内部注入变量的值（类似于字符串插值）
#   - macro：编译期执行的函数，接收AST输入，返回变换后的AST
#   - @moduledoc / @doc：文档注解
#
# 宏在编译期展开，不产生运行时开销。
# 宏的常见用途：DSL构建、代码生成、控制结构扩展。

# --- quote：将代码表示为数据 ---
IO.puts("=== quote基础 ===")

# quote 将代码转为AST表示
quoted_expr = quote do
  1 + 2 * 3
end

IO.puts("quote后的AST:")
IO.inspect(quoted_expr)
# 输出类似: {:+, [context: ...], [1, {:*, [...], [2, 3]}]}

# eval引用的表达式
IO.puts("求值结果: #{Code.eval_quoted(quoted_expr) |> elem(0)}")

# --- unquote：在quote中注入值 ---
x = 42

# 不用unquote：x只是AST中的一个变量引用
quoted_without_unq = quote do
  x + 1
end
IO.puts("\n不用unquote的AST:")
IO.inspect(quoted_without_unq)

# 用unquote：将x的值注入AST
quoted_with_unq = quote do
  unquote(x) + 1
end
IO.puts("用unquote的AST:")
IO.inspect(quoted_with_unq)
IO.puts("求值结果: #{Code.eval_quoted(quoted_with_unq) |> elem(0)}")

# --- 宏定义 ---
# 宏用 defmacro 定义，在编译期执行

defmodule MyMacros do
  # 宏：unless（如果条件为假则执行）
  defmacro my_unless(condition, do: body) do
    quote do
      if !unquote(condition) do
        unquote(body)
      end
    end
  end

  # 宏：带日志的函数调用
  defmacro logged(do: body) do
    quote do
      IO.puts(">>> 开始执行: #{unquote(Macro.to_string(body))}")
      result = unquote(body)
      IO.puts("<<< 执行完成，结果: #{inspect(result)}")
      result
    end
  end

  # 宏：计时执行
  defmacro time_it(do: body) do
    quote do
      start = System.monotonic_time(:millisecond)
      result = unquote(body)
      finish = System.monotonic_time(:millisecond)
      IO.puts("耗时: #{finish - start}ms")
      result
    end
  end

  # 宏：生成重复执行的代码
  defmacro repeat(n, do: body) do
    quote do
      Enum.each(1..unquote(n), fn _ ->
        unquote(body)
      end)
    end
  end

  # 宏：交换两个变量的值
  defmacro swap(a, b) do
    quote do
      temp = unquote(a)
      unquote(a) = unquote(b)
      unquote(b) = temp
    end
  end
end

# --- 使用自定义宏 ---
IO.puts("\n=== 使用宏 ===")

# my_unless
val = 5
MyMacros.my_unless val > 10 do
  IO.puts("val (#{val}) 不大于 10")
end

# logged 宏
MyMacros.logged do
  Enum.sum([1, 2, 3, 4, 5])
end

# time_it 宏
MyMacros.time_it do
  Enum.sum(1..100_000)
end

# repeat 宏
IO.puts("重复执行:")
MyMacros.repeat(3) do
  IO.puts("  执行一次!")
end

# --- 使用 defmodule 动态生成代码 ---
# 宏可以生成整个函数定义

defmodule MetaProgramming do
  # 使用 @before_compile 注入回调
  # 在模块编译前执行，可以动态添加函数

  # 为每种数据类型生成验证函数
  defmacro defvalidators do
    types = [:string, :integer, :boolean, :float]

    for type <- types do
      validator_name = String.to_atom("validate_#{type}")

      quote do
        def unquote(validator_name)(value) do
          case value do
            v when is_binary(v) and unquote(type) == :string -> {:ok, v}
            v when is_integer(v) and unquote(type) == :integer -> {:ok, v}
            v when is_boolean(v) and unquote(type) == :boolean -> {:ok, v}
            v when is_float(v) and unquote(type) == :float -> {:ok, v}
            _ -> {:error, "不是有效的 #{unquote(type)}"}
          end
        end
      end
    end
  end
end

defmodule DataValidator do
  import MetaProgramming

  # 一行宏调用生成多个验证函数
  defvalidators()
end

IO.puts("\n=== 动态生成的验证函数 ===")
IO.inspect(DataValidator.validate_string("hello"), label: "validate_string")
IO.inspect(DataValidator.validate_integer(42), label: "validate_integer")
IO.inspect(DataValidator.validate_integer("not a number"), label: "validate_integer(错误)")
IO.inspect(DataValidator.validate_boolean(true), label: "validate_boolean")

# --- 宏展开检查 ---
IO.puts("\n=== 宏展开检查 ===")

# Macro.expand 展开宏
expanded = quote do
  MyMacros.my_unless 1 > 2 do
    :executed
  end
end
|> Macro.expand_once(%{})

IO.puts("my_unless 展开后:")
IO.inspect(expanded)

# --- __using__ 宏：实现 use 行为 ---
# use 模块时会调用该模块的 __using__ 宏

defmodule Greetable do
  defmacro __using__(_opts) do
    quote do
      def greet(name), do: "你好, #{name}!"

      def greet_formal(name), do: "尊敬的 #{name}，您好。"

      defp internal_greet(name), do: "(内部) 你好 #{name}"
    end
  end
end

defmodule MyApp.Greeter do
  use Greetable
  # use 自动注入 greet/1, greet_formal/1, internal_greet/1
end

IO.puts("\n=== use 注入的函数 ===")
IO.puts(MyApp.Greeter.greet("Elixir"))
IO.puts(MyApp.Greeter.greet_formal("World"))

# --- DSL构建：简单查询语言 ---
defmodule QueryDSL do
  defmacro from(table, opts) do
    where = Keyword.get(opts, :where, true)
    select = Keyword.get(opts, :select, :*)

    quote do
      fn data ->
        data
        |> Enum.filter(fn row ->
          row.__table__ == unquote(table) and
          (case unquote(where) do
            true -> true
            _ -> unquote(where)
          end)
        end)
        |> Enum.map(fn row ->
          case unquote(select) do
            :* -> row
            field -> Map.get(row, field)
          end
        end)
      end
    end
  end
end

IO.puts("\n=== DSL查询语言 ===")
IO.puts("""
# 概念演示：用宏构建查询DSL
#
# import QueryDSL
#
# query = from :users,
#   where: row.age > 18,
#   select: :name
#
# query.(users_data)  # 返回所有18岁以上用户的名字
""")

# 思考题：quote/unquote 的关系类似于字符串模板中的什么操作？
#         宏在编译期展开，这意味着什么？它和普通函数有什么本质区别？
#         use 模块 时发生了什么？__using__ 宏如何实现代码注入？
