%% ============================================================
%% 阶段：函数式并发语言 - Erlang语言练习
%% 题数：2题
%% 创建日期：2026-08-05
%% ============================================================

%% ============================================================
%% 第1题：Erlang基础（模式匹配 / 递归 / 列表）
%% ============================================================
%% 知识点讲解：
%% Erlang是为电信系统设计的高并发、高容错函数式语言。
%% 核心特征：
%%   - 变量不可变：一旦绑定就不能修改（大写开头是变量）
%%   - 模式匹配：= 是模式匹配而非赋值，用于解构数据
%%   - 没有循环：一切递归实现，编译器做尾递归优化
%%   - 列表操作：头部(Head)和尾部(Tail)是核心操作
%%     [H|T] 将列表分为第一个元素和剩余部分
%%   - 原子(Atom)：小写开头的标识符，类似枚举值
%%   - 元组(Tuple)：固定大小的容器 {a, b, c}
%%   - 每个表达式以句号(.)结尾
%%
%% Erlang的命名约定：
%%   - 变量：大写字母开头（如 Name, Count, X）
%%   - 原子：小写字母开头（如 ok, error, true）
%%   - 函数：小写字母开头（如 sum, factorial）

-module(erlang_exercises).
-export([run/0]).

%% --- 基本数据类型 ---

run() ->
    %% 变量绑定（变量首字母大写）
    IntVal = 42,
    FloatVal = 3.14,
    AtomVal = ok,
    StringVal = "Hello",        %% Erlang的字符串就是整数列表
    TupleVal = {person, "Alice", 30},
    ListVal = [1, 2, 3, 4, 5],

    io:format("=== 基本数据类型 ===~n"),
    io:format("整数: ~p~n", [IntVal]),
    io:format("浮点: ~p~n", [FloatVal]),
    io:format("原子: ~p~n", [AtomVal]),
    io:format("字符串: ~p (实际是列表)~n", [StringVal]),
    io:format("元组: ~p~n", [TupleVal]),
    io:format("列表: ~p~n", [ListVal]),

    %% --- 模式匹配 ---
    io:format("~n=== 模式匹配 ===~n"),

    %% 基本模式匹配
    {Type, Name, Age} = TupleVal,
    io:format("解构元组: Type=~p, Name=~s, Age=~p~n", [Type, Name, Age]),

    %% 列表模式匹配
    [Head | Tail] = ListVal,
    io:format("列表头: ~p, 尾: ~p~n", [Head, Tail]),

    %% 多元素头部匹配
    [A, B | Rest] = ListVal,
    io:format("前两个: ~p, ~p, 剩余: ~p~n", [A, B, Rest]),

    %% 忽略不需要的值（下划线）
    {_, OnlyName, _} = TupleVal,
    io:format("只取名字: ~s~n", [OnlyName]),

    %% --- case 表达式 ---
    io:format("~n=== case 表达式 ===~n"),
    Result1 = case Age of
        N when N < 18 -> "未成年";
        N when N < 30 -> "青年";
        N when N < 50 -> "中年";
        _             -> "老年"
    end,
    io:format("年龄~p的分类: ~s~n", [Age, Result1]),

    %% --- 函数子句与模式匹配 ---
    io:format("~n=== 函数与模式匹配 ===~n"),
    io:format("factorial(5) = ~p~n", [factorial(5)]),
    io:format("factorial_tr(5) = ~p~n", [factorial_tr(5)]),
    io:format("fibonacci(10) = ~p~n", [fibonacci(10)]),

    %% --- 列表操作 ---
    io:format("~n=== 列表操作 ===~n"),
    Nums = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    io:format("列表: ~p~n", [Nums]),
    io:format("长度: ~p~n", [my_length(Nums)]),
    io:format("求和: ~p~n", [my_sum(Nums)]),
    io:format("反转: ~p~n", [my_reverse(Nums)]),
    io:format("偶数: ~p~n", [filter_even(Nums)]),
    io:format("平方: ~p~n", [map_square(Nums)]),
    io:format("最大值: ~p~n", [my_max(Nums)]),

    %% --- 列表推导式 ---
    io:format("~n=== 列表推导式 ===~n"),
    Squares = [X * X || X <- lists:seq(1, 10)],
    io:format("平方: ~p~n", [Squares]),

    EvenSquares = [X * X || X <- lists:seq(1, 10), X rem 2 == 0],
    io:format("偶数平方: ~p~n", [EvenSquares]),

    %% 笛卡尔积
    Pairs = [{X, Y} || X <- [1, 2, 3], Y <- [a, b]],
    io:format("笛卡尔积: ~p~n", [Pairs]),

    %% --- 记录(Record) ---
    io:format("~n=== Record ===~n"),
    Person = #person{name = "Alice", age = 30, city = "NYC"},
    io:format("Person: ~p~n", [Person]),
    io:format("名字: ~s~n", [Person#person.name]),
    UpdatedPerson = Person#person{age = 31},
    io:format("更新后: ~p~n", [UpdatedPerson]),

    %% --- 映射(Map) ---
    io:format("~n=== Map ===~n"),
    User = #{name => "Bob", age => 25, role => admin},
    io:format("Map: ~p~n", [User]),
    io:format("name: ~p~n", [maps:get(name, User)]),
    UpdatedMap = User#{age => 26},
    io:format("更新: ~p~n", [UpdatedMap]),

    %% Map模式匹配
    #{name := MatchedName, age := MatchedAge} = User,
    io:format("模式匹配: name=~s, age=~p~n", [MatchedName, MatchedAge]),

    ok.

%% --- 递归函数 ---

%% 阶乘：基础递归
factorial(0) -> 1;
factorial(N) when N > 0 -> N * factorial(N - 1).

%% 阶乘：尾递归版本（使用累加器）
%% 尾递归不会增长调用栈，适合处理大数据
factorial_tr(N) -> factorial_tr(N, 1).
factorial_tr(0, Acc) -> Acc;
factorial_tr(N, Acc) when N > 0 -> factorial_tr(N - 1, N * Acc).

%% 斐波那契：基础递归（效率低，指数复杂度）
fibonacci(0) -> 0;
fibonacci(1) -> 1;
fibonacci(N) when N > 1 -> fibonacci(N - 1) + fibonacci(N - 2).

%% 斐波那契：尾递归版本（线性复杂度）
fibonacci_tr(N) -> fib_helper(N, 0, 1).
fib_helper(0, A, _) -> A;
fib_helper(N, A, B) -> fib_helper(N - 1, B, A + B).

%% --- 列表递归函数 ---

%% 计算列表长度
my_length([]) -> 0;
my_length([_ | T]) -> 1 + my_length(T).

%% 尾递归版长度
my_length_tr(List) -> my_length_tr(List, 0).
my_length_tr([], Acc) -> Acc;
my_length_tr([_ | T], Acc) -> my_length_tr(T, Acc + 1).

%% 列表求和
my_sum([]) -> 0;
my_sum([H | T]) -> H + my_sum(T).

%% 尾递归求和
my_sum_tr(List) -> my_sum_tr(List, 0).
my_sum_tr([], Acc) -> Acc;
my_sum_tr([H | T], Acc) -> my_sum_tr(T, Acc + H).

%% 反转列表（尾递归）
my_reverse(List) -> my_reverse(List, []).
my_reverse([], Acc) -> Acc;
my_reverse([H | T], Acc) -> my_reverse(T, [H | Acc]).

%% 过滤偶数
filter_even([]) -> [];
filter_even([H | T]) ->
    case H rem 2 of
        0 -> [H | filter_even(T)];
        _ -> filter_even(T)
    end.

%% 尾递归版过滤偶数
filter_even_tr(List) -> filter_even_tr(List, []).
filter_even_tr([], Acc) -> my_reverse(Acc);
filter_even_tr([H | T], Acc) ->
    case H rem 2 of
        0 -> filter_even_tr(T, [H | Acc]);
        _ -> filter_even_tr(T, Acc)
    end.

%% 映射：对每个元素应用函数
map_square([]) -> [];
map_square([H | T]) -> [H * H | map_square(T)].

%% 通用map函数
my_map(_, []) -> [];
my_map(F, [H | T]) -> [F(H) | my_map(F, T)].

%% 通用filter函数
my_filter(_, []) -> [];
my_filter(Pred, [H | T]) ->
    case Pred(H) of
        true  -> [H | my_filter(Pred, T)];
        false -> my_filter(Pred, T)
    end.

%% 通用foldl函数
my_foldl(_, Acc, []) -> Acc;
my_foldl(F, Acc, [H | T]) -> my_foldl(F, F(H, Acc), T).

%% 求最大值
my_max([H | T]) -> my_max(T, H).
my_max([], Max) -> Max;
my_max([H | T], Max) when H > Max -> my_max(T, H);
my_max([_ | T], Max) -> my_max(T, Max).

%% --- 列表拼接（++ 运算符的实现原理）---
my_append([], List2) -> List2;
my_append([H | T], List2) -> [H | my_append(T, List2)].

%% --- 快速排序（展示列表推导式的优雅）---
quicksort([]) -> [];
quicksort([Pivot | Rest]) ->
    {Smaller, Larger} = partition(Pivot, Rest),
    quicksort(Smaller) ++ [Pivot] ++ quicksort(Larger).

partition(Pivot, List) ->
    Smaller = [X || X <- List, X < Pivot],
    Larger  = [X || X <- List, X >= Pivot],
    {Smaller, Larger}.

%% --- 二叉树（Erlang中的递归数据结构）---
%% Erlang中没有专门的数据结构定义语法
%% 用元组表示树节点：{node, Value, Left, Right}
%% 空树用原子 nil 表示

%% 插入节点
tree_insert(nil, Value) -> {node, Value, nil, nil};
tree_insert({node, V, Left, Right}, Value) ->
    if
        Value < V -> {node, V, tree_insert(Left, Value), Right};
        Value > V -> {node, V, Left, tree_insert(Right, Value)};
        true      -> {node, V, Left, Right}  %% 已存在，不插入
    end.

%% 中序遍历（左-根-右）
tree_inorder(nil) -> [];
tree_inorder({node, V, Left, Right}) ->
    tree_inorder(Left) ++ [V] ++ tree_inorder(Right).

%% 从列表构建二叉搜索树
tree_from_list(List) ->
    lists:foldl(fun tree_insert/2, nil, List).

%% 计算树的高度
tree_height(nil) -> 0;
tree_height({node, _, Left, Right}) ->
    1 + max(tree_height(Left), tree_height(Right)).

%% --- 高阶函数演示 ---
%% Erlang中函数可以作为参数传递
demo_higher_order() ->
    Nums = [1, 2, 3, 4, 5],
    Doubled = my_map(fun(X) -> X * 2 end, Nums),
    Evens = my_filter(fun(X) -> X rem 2 == 0 end, Nums),
    Sum = my_foldl(fun(X, Acc) -> Acc + X end, 0, Nums),
    {Doubled, Evens, Sum}.

%% --- Record定义 ---
%% Record是带标签的元组，编译期展开为元组操作
-record(person, {name, age, city}).

%% 思考题：Erlang中变量为什么是不可变的？不可变性对并发编程有什么好处？
%%         尾递归优化是什么？为什么Erlang中没有for/while循环？
%%         [H|T] 模式匹配在列表操作中为什么如此重要？

%% ============================================================
%% 第2题：并发编程（spawn / 消息传递 / OTP概念）
%% ============================================================
%% 知识点讲解：
%% Erlang的并发模型基于Actor模型，核心概念：
%%   - 进程(Process)：Erlang的进程是用户态的轻量级进程（约300字节），
%%     不是操作系统线程。一台机器可以运行数百万个进程。
%%   - spawn/3：创建新进程，返回PID（进程标识符）
%%   - 消息传递：进程间通过 ! 运算符发送消息，用 receive 接收
%%   - 进程不共享内存，完全隔离
%%   - receive：模式匹配接收消息，可设置超时
%%   - 链接(link)：两个进程绑定，一个退出另一个也退出
%%   - 监控(monitor)：单向监控，被监控进程退出时收到通知
%%
%% OTP(Open Telecom Platform)：
%%   - gen_server：通用服务器行为(Behaviour)
%%   - supervisor：监控树，负责进程重启
%%   - application：应用管理
%%   - Behaviour = 设计模式 + 框架代码，开发者只需实现回调

%% --- 运行并发演示 ---
run_concurrency() ->
    io:format("=== 基础进程操作 ===~n"),

    %% spawn/1 创建匿名进程
    Pid1 = spawn(fun() ->
        io:format("  [进程~p] 你好，我是新进程！~n", [self()])
    end),

    %% 等待一下让进程执行
    timer:sleep(100),

    %% spawn/3 创建指定模块函数的进程
    Pid2 = spawn(?MODULE, counter_process, [0]),
    io:format("创建计数器进程: ~p~n", [Pid2]),

    %% --- 发送和接收消息 ---
    io:format("~n=== 消息传递 ===~n"),

    %% 发送消息给计数器进程
    Pid2 ! {increment, self()},
    Pid2 ! {increment, self()},
    Pid2 ! {increment, self()},
    Pid2 ! {get_value, self()},

    %% 接收计数器的回复
    receive
        {value, N} -> io:format("计数器当前值: ~p~n", [N])
    after 1000 -> io:format("超时~n")
    end,

    %% 发送递减消息
    Pid2 ! {decrement, self()},
    Pid2 ! {get_value, self()},
    receive
        {value, N2} -> io:format("递减后值: ~p~n", [N2])
    after 1000 -> io:format("超时~n")
    end,

    %% 停止进程
    Pid2 ! stop,
    timer:sleep(100),

    %% --- 多进程并行计算 ---
    io:format("~n=== 多进程并行计算 ===~n"),
    parallel_fibonacci(),

    %% --- 进程链接 ---
    io:format("~n=== 进程链接 ===~n"),
    demo_link(),

    %% --- receive超时 ---
    io:format("~n=== receive超时 ===~n"),
    demo_timeout(),

    %% --- selective receive（选择性接收）---
    io:format("~n=== 选择性接收 ===~n"),
    demo_selective_receive(),

    %% --- gen_server概念 ---
    io:format("~n=== gen_server 概念 ===~n"),
    io:format("(以下是概念说明，实际运行需要OTP行为模式)~n~n"),
    gen_server_concept(),

    %% --- Supervisor概念 ---
    io:format("~n=== Supervisor 概念 ===~n~n"),
    supervisor_concept(),

    ok.

%% --- 计数器进程 ---
%% 这是一个简单的无限循环进程，通过模式匹配处理不同消息
counter_process(InitialValue) ->
    receive
        {increment, From} ->
            NewValue = InitialValue + 1,
            From ! {ack, incremented},
            counter_process(NewValue);

        {decrement, From} ->
            NewValue = InitialValue - 1,
            From ! {ack, decremented},
            counter_process(NewValue);

        {get_value, From} ->
            From ! {value, InitialValue},
            counter_process(InitialValue);

        {set_value, NewValue, From} ->
            From ! {ack, value_set},
            counter_process(NewValue);

        stop ->
            io:format("  [计数器] 进程停止，最终值: ~p~n", [InitialValue]),
            ok;

        _Other ->
            io:format("  [计数器] 未知消息: ~p~n", [_Other]),
            counter_process(InitialValue)
    end.

%% --- 并行计算斐波那契 ---
parallel_fibonacci() ->
    %% 为每个数字创建一个进程并行计算
    Nums = [10, 20, 15, 25, 30, 35],

    %% 记录开始时间
    StartTime = erlang:monotonic_time(millisecond),

    %% 为每个数字spawn一个进程
    Pids = [spawn_worker(self(), Num) || Num <- Nums],

    %% 收集所有结果
    Results = [receive_result(Pid) || Pid <- Pids],

    EndTime = erlang:monotonic_time(millisecond),

    lists:foreach(fun({Num, Fib}) ->
        io:format("  fib(~p) = ~p~n", [Num, Fib])
    end, Results),

    io:format("  并行计算~p个斐波那契，总耗时: ~pms~n", [length(Nums), EndTime - StartTime]).

%% 生成一个工作进程
spawn_worker(Parent, N) ->
    spawn(fun() ->
        Result = fibonacci_tr(N),
        Parent ! {result, self(), {N, Result}}
    end).

%% 接收工作进程的结果
receive_result(Pid) ->
    receive
        {result, Pid, Result} -> Result
    after 5000 -> {error, timeout}
    end.

%% --- 进程链接演示 ---
demo_link() ->
    %% spawn_link 创建链接进程
    %% 如果链接的进程崩溃，当前进程也会退出
    io:format("  创建一个会崩溃的链接进程...~n"),

    %% 使用catch捕获退出信号
    process_flag(trap_exit, true),

    Pid = spawn_link(fun() ->
        timer:sleep(100),
        exit(crash_demo)  %% 模拟崩溃
    end),

    receive
        {'EXIT', Pid, Reason} ->
            io:format("  收到退出信号: 进程~p因~p退出~n", [Pid, Reason])
    after 2000 ->
        io:format("  超时未收到退出信号~n")
    end,

    process_flag(trap_exit, false).

%% --- receive超时演示 ---
demo_timeout() ->
    io:format("  等待消息(超时500ms)...~n"),
    receive
        _Msg -> io:format("  收到消息: ~p~n", [_Msg])
    after 500 ->
        io:format("  超时，没有消息到达~n")
    end,

    %% 超时0用于非阻塞接收（检查邮箱是否有消息）
    io:format("  非阻塞检查邮箱...~n"),
    receive
        _Msg2 -> io:format("  邮箱中有消息: ~p~n", [_Msg2])
    after 0 ->
        io:format("  邮箱为空~n")
    end.

%% --- 选择性接收演示 ---
demo_selective_receive() ->
    %% 发送多条消息到当前进程的邮箱
    self() ! msg_c,
    self() ! msg_a,
    self() ! msg_b,
    self() ! msg_d,

    %% receive会按模式匹配顺序取出消息，不是按到达顺序
    io:format("  选择性接收（按模式优先级）:~n"),

    %% 先接收msg_a
    receive
        msg_a -> io:format("    收到 msg_a~n")
    after 100 -> io:format("    msg_a 超时~n")
    end,

    %% 再接收msg_b
    receive
        msg_b -> io:format("    收到 msg_b~n")
    after 100 -> io:format("    msg_b 超时~n")
    end,

    %% 接收剩余所有消息
    flush_messages().

%% 清空邮箱中的剩余消息
flush_messages() ->
    receive
        Msg ->
            io:format("    清理消息: ~p~n", [Msg]),
            flush_messages()
    after 0 ->
        io:format("    邮箱已清空~n")
    end.

%% --- gen_server 概念说明 ---
gen_server_concept() ->
    io:format("""
gen_server 是Erlang OTP的核心行为模式(Behaviour)，封装了：
  - 客户端-服务器的消息循环
  - 同步调用(call)和异步通知(cast)
  - 状态管理
  - 错误处理和代码热更新

  使用方式（伪代码）：

  -module(my_server).
  -behaviour(gen_server).

  %% API
  start_link() ->
      gen_server:start_link({local, ?MODULE}, ?MODULE, [], []).

  %% 回调函数
  init([]) ->
      {ok, #state{count = 0}}.

  handle_call({increment}, _From, State) ->
      NewCount = State#state.count + 1,
      {reply, NewCount, State#state{count = NewCount}};

  handle_call({get}, _From, State) ->
      {reply, State#state.count, State}.

  handle_cast({set, Value}, State) ->
      {noreply, State#state{count = Value}}.

  %% 客户端调用：
  %% gen_server:call(?MODULE, {increment})  %% 同步
  %% gen_server:cast(?MODULE, {set, 100})   %% 异步
""").

%% --- Supervisor 概念说明 ---
supervisor_concept() ->
    io:format("""
Supervisor 是OTP的监控树行为模式，负责：
  - 启动和监控子进程
  - 子进程崩溃时按策略重启
  - 构建层次化的容错结构

  重启策略：
  - one_for_one:  只重启崩溃的子进程
  - one_for_all:  重启所有子进程
  - rest_for_one: 重启崩溃进程及其后面的进程
  - simple_one_for_one: 动态添加同类型子进程

  使用方式（伪代码）：

  -module(my_supervisor).
  -behaviour(supervisor).

  init([]) ->
      Children = [
          #{id => my_server,
            start => {my_server, start_link, []},
            restart => permanent,    %% 崩溃总是重启
            shutdown => 2000,        %% 优雅关闭超时
            type => worker,
            modules => [my_server]}
      ],
      %% 策略：每5秒最多重启3次，超过则整个Supervisor退出
      {ok, {#{strategy => one_for_one,
              intensity => 3,
              period => 5}, Children}}.

  监控树架构：
  +-- main_supervisor
      +-- server_1 (worker)
      +-- server_2 (worker)
      +-- sub_supervisor
          +-- server_3 (worker)
          +-- server_4 (worker)
""").

%% --- 进程注册演示 ---
demo_registration() ->
    %% 注册进程名，方便通过名字发送消息
    Pid = spawn(fun() ->
        receive
            {ping, From} -> From ! pong
        end
    end),
    register(ping_server, Pid),

    %% 通过注册名发送消息
    ping_server ! {ping, self()},
    receive
        pong -> io:format("收到pong~n")
    after 1000 -> ok
    end.

%% --- 进程间通信：请求-响应模式 ---
rpc(Pid, Request) ->
    Ref = make_ref(),  %% 创建唯一引用
    Pid ! {Request, self(), Ref},
    receive
        {response, Ref, Response} -> Response
    after 5000 ->
        {error, timeout}
    end.

%% --- 生产者-消费者模式 ---
producer_consumer_demo() ->
    %% 创建共享队列进程
    QueuePid = spawn(fun() -> queue_loop([]) end),

    %% 生产者
    Producer = spawn(fun() ->
        lists:foreach(fun(N) ->
            QueuePid ! {push, N},
            timer:sleep(50)
        end, lists:seq(1, 10)),
        QueuePid ! done
    end),

    %% 消费者
    Consumer = spawn(fun() ->
        consumer_loop(QueuePid)
    end),

    {Producer, Consumer}.

queue_loop(Items) ->
    receive
        {push, Item} ->
            queue_loop(Items ++ [Item]);
        {pop, From} ->
            case Items of
                [] ->
                    From ! {empty},
                    queue_loop(Items);
                [H | T] ->
                    From ! {item, H},
                    queue_loop(T)
            end;
        done ->
            ok
    end.

consumer_loop(QueuePid) ->
    QueuePid ! {pop, self()},
    receive
        {item, H} ->
            io:format("  消费: ~p~n", [H]),
            consumer_loop(QueuePid);
        {empty} ->
            timer:sleep(100),
            consumer_loop(QueuePid)
    after 2000 ->
        io:format("  消费者结束~n")
    end.

%% 思考题：Erlang的进程和操作系统线程有什么区别？为什么Erlang能创建百万级进程？
%%         "Let it crash"（让它崩溃）哲学如何改变了错误处理的方式？
%%         Supervisor的监控树如何实现系统的自愈能力？
%%         选择性receive(selective receive)和普通的队列消息有什么区别？
