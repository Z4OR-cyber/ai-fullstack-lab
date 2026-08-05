<?php
// ============================================================
// 阶段：脚本语言与系统级语言扩展练习
// 语言：PHP
// 题数：3题
// 创建日期：2026-08-05
// ============================================================

// ============================================================
// 第1题：PHP基础（变量 / 数组 / 函数 / 超全局）
// ============================================================

/**
 * 【知识点讲解】
 * PHP是Web开发领域最流行的服务端脚本语言之一。
 * 变量以$开头，弱类型，不需要声明类型。
 * 数组在PHP中实际上是有序映射，可以同时作为索引数组和关联数组。
 * PHP提供了丰富的超全局变量：$_GET、$_POST、$_SERVER、$_SESSION等。
 * 函数支持默认参数、类型声明、可变参数等特性。
 */

// 1. 变量与数据类型
$intVar = 42;                         // 整型
$floatVar = 3.14159;                  // 浮点型
$stringVar = "Hello PHP";             // 字符串
$boolVar = true;                      // 布尔型
$nullVar = null;                      // null
$arrayVar = [1, 2, 3];                // 数组（短语法）

// 类型判断
echo "=== 变量类型 ===" . PHP_EOL;
echo "intVar 类型: " . gettype($intVar) . PHP_EOL;
echo "floatVar 类型: " . gettype($floatVar) . PHP_EOL;

// 类型转换
$strNum = "123";
$numInt = (int)$strNum;
echo "字符串 '123' 转整型: {$numInt}" . PHP_EOL;

// 2. 数组操作
// 索引数组
$colors = ["红", "绿", "蓝"];
echo "数组长度: " . count($colors) . PHP_EOL;

// 关联数组
$user = [
    "name" => "李四",
    "age" => 30,
    "role" => "开发者"
];

// 遍历关联数组
echo "=== 用户信息 ===" . PHP_EOL;
foreach ($user as $key => $value) {
    echo "  {$key}: {$value}" . PHP_EOL;
}

// 数组函数
$numbers = [3, 1, 4, 1, 5, 9, 2, 6];
sort($numbers);                                    // 排序
echo "排序后: " . implode(", ", $numbers) . PHP_EOL;
echo "最大值: " . max($numbers) . PHP_EOL;
echo "平均值: " . (array_sum($numbers) / count($numbers)) . PHP_EOL;

// 数组映射与过滤
$squared = array_map(fn($n) => $n * $n, $numbers);  // 箭头函数
$evens = array_filter($numbers, fn($n) => $n % 2 === 0);
echo "平方: " . implode(", ", $squared) . PHP_EOL;
echo "偶数: " . implode(", ", $evens) . PHP_EOL;

// 3. 函数：默认参数、类型声明、可变参数
function greet(string $name, string $greeting = "你好"): string {
    return "{$greeting}，{$name}！";
}
echo greet("王五") . PHP_EOL;
echo greet("赵六", "早上好") . PHP_EOL;

// 可变参数
function sumAll(int ...$nums): int {
    return array_sum($nums);
}
echo "sumAll(1,2,3,4,5) = " . sumAll(1, 2, 3, 4, 5) . PHP_EOL;

// 匿名函数与闭包
$multiplier = function($factor) {
    return function($n) use ($factor) {
        return $n * $factor;
    };
};
$triple = $multiplier(3);
echo "triple(5) = " . $triple(5) . PHP_EOL;

// 4. 超全局变量（概念演示）
echo "=== 超全局变量 ===" . PHP_EOL;
echo "当前脚本: " . ($_SERVER['PHP_SELF'] ?? 'CLI模式') . PHP_EOL;
echo "PHP版本: " . PHP_VERSION . PHP_EOL;

// 模拟 $_GET 解析
$queryString = "name=张三&age=25&city=北京";
parse_str($queryString, $getParams);
echo "解析查询字符串:" . PHP_EOL;
foreach ($getParams as $k => $v) {
    echo "  \$_GET['{$k}'] = {$v}" . PHP_EOL;
}

// 【思考题】
// 1. PHP中 == 和 === 的区别是什么？什么场景下应该使用严格比较？
// 2. array_map 和 foreach 各自的适用场景是什么？性能上有何差异？

// ============================================================
// 第2题：面向对象（类 / 接口 / trait / 命名空间）
// ============================================================

/**
 * 【知识点讲解】
 * PHP的OOP支持类、继承、接口、抽象类、trait等完整特性。
 * trait解决单继承语言的多重代码复用问题，类似于其他语言的mixin。
 * 命名空间（namespace）用于解决类名冲突，组织代码结构。
 * PHP 8引入了构造函数属性提升、match表达式、命名参数等现代特性。
 */

namespace App\Exercises {

    // 1. 定义接口
    interface Comparable {
        public function compareTo(object $other): int;
    }

    // 2. 定义trait：日志能力（可复用的代码片段）
    trait Logger {
        private array $logs = [];

        protected function log(string $message): void {
            $timestamp = date('Y-m-d H:i:s');
            $this->logs[] = "[{$timestamp}] {$message}";
        }

        public function getLogs(): array {
            return $this->logs;
        }
    }

    // 3. 抽象基类
    abstract class Shape implements Comparable {
        use Logger;  // 使用trait

        public function __construct(
            protected string $name = "形状"
        ) {}

        // 抽象方法：子类必须实现
        abstract public function area(): float;

        // 普通方法
        public function describe(): string {
            $a = number_format($this->area(), 2);
            $msg = "{$this->name}，面积 = {$a}";
            $this->log("调用了 describe()，返回: {$msg}");
            return $msg;
        }

        // 实现接口方法
        public function compareTo(object $other): int {
            if (!$other instanceof Shape) {
                throw new \InvalidArgumentException("只能与Shape比较");
            }
            $diff = $this->area() - $other->area();
            return $diff > 0 ? 1 : ($diff < 0 ? -1 : 0);
        }
    }

    // 4. 子类：圆形
    class Circle extends Shape {
        public function __construct(
            private float $radius
        ) {
            parent::__construct("圆形");
        }

        public function area(): float {
            return M_PI * $this->radius ** 2;
        }
    }

    // 5. 子类：矩形
    class Rectangle extends Shape {
        public function __construct(
            private float $width,
            private float $height
        ) {
            parent::__construct("矩形");
        }

        public function area(): float {
            return $this->width * $this->height;
        }
    }

    // 6. 测试
    $circle = new Circle(5);
    $rect = new Rectangle(4, 6);

    echo $circle->describe() . PHP_EOL;
    echo $rect->describe() . PHP_EOL;

    // 比较两个形状
    $cmp = $circle->compareTo($rect);
    $result = match($cmp) {
        1 => "圆形更大",
        -1 => "矩形更大",
        0 => "面积相等",
    };
    echo "比较结果: {$result}" . PHP_EOL;

    // 查看日志（来自trait）
    echo "=== 日志记录 ===" . PHP_EOL;
    foreach ($circle->getLogs() as $log) {
        echo "  {$log}" . PHP_EOL;
    }
}

// 【思考题】
// 1. trait和接口有什么本质区别？trait解决了什么设计问题？
// 2. 如果两个trait中有同名方法，PHP如何处理冲突？

// ============================================================
// 第3题：Web开发实战（$_GET / $_POST / 会话 / JSON）
// ============================================================

/**
 * 【知识点讲解】
 * PHP原生支持Web开发，无需框架即可处理HTTP请求。
 * $_GET和$_POST分别接收URL参数和表单数据。
 * session机制通过$_SESSION超全局变量实现跨请求状态保持。
 * JSON是现代Web API的数据交换标准，PHP提供json_encode/json_decode。
 * 本题模拟一个简单的RESTful API端点。
 */

// 1. 模拟路由分发器
class SimpleRouter {
    private array $routes = [];

    // 注册路由
    public function addRoute(string $method, string $path, callable $handler): void {
        $this->routes[$method . " " . $path] = $handler;
    }

    // 分发请求
    public function dispatch(string $method, string $path, array $params = []): string {
        $key = $method . " " . $path;
        if (!isset($this->routes[$key])) {
            return json_encode([
                "status" => 404,
                "error" => "路由不存在: {$path}"
            ], JSON_UNESCAPED_UNICODE);
        }
        try {
            $data = ($this->routes[$key])($params);
            return json_encode([
                "status" => 200,
                "data" => $data
            ], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
        } catch (\Exception $e) {
            return json_encode([
                "status" => 500,
                "error" => $e->getMessage()
            ], JSON_UNESCAPED_UNICODE);
        }
    }
}

// 2. 模拟会话管理
class SessionManager {
    private static array $store = [];  // 模拟session存储

    public static function start(string $sessionId): void {
        if (!isset(self::$store[$sessionId])) {
            self::$store[$sessionId] = [];
        }
    }

    public static function set(string $sessionId, string $key, mixed $value): void {
        self::$store[$sessionId][$key] = $value;
    }

    public static function get(string $sessionId, string $key): mixed {
        return self::$store[$sessionId][$key] ?? null;
    }

    public static function destroy(string $sessionId): void {
        unset(self::$store[$sessionId]);
    }
}

// 3. 模拟数据库
$database = [
    ["id" => 1, "name" => "张三", "email" => "zhangsan@test.com"],
    ["id" => 2, "name" => "李四", "email" => "lisi@test.com"],
    ["id" => 3, "name" => "王五", "email" => "wangwu@test.com"],
];

// 4. 创建路由并注册API
$router = new SimpleRouter();

// GET /users - 获取用户列表
$router->addRoute("GET", "/users", function() use ($database) {
    return array_map(fn($u) => [
        "id" => $u["id"],
        "name" => $u["name"]
    ], $database);
});

// POST /users - 创建新用户（模拟$_POST处理）
$router->addRoute("POST", "/users", function($params) use (&$database) {
    if (empty($params["name"]) || empty($params["email"])) {
        throw new \InvalidArgumentException("name和email不能为空");
    }
    $newUser = [
        "id" => count($database) + 1,
        "name" => $params["name"],
        "email" => $params["email"]
    ];
    $database[] = $newUser;
    return $newUser;
});

// POST /login - 模拟登录（设置session）
$router->addRoute("POST", "/login", function($params) {
    $username = $params["username"] ?? "";
    $password = $params["password"] ?? "";

    if ($username === "admin" && $password === "123456") {
        $sessionId = bin2hex(random_bytes(16));
        SessionManager::start($sessionId);
        SessionManager::set($sessionId, "user", $username);
        SessionManager::set($sessionId, "login_time", date("Y-m-d H:i:s"));
        return ["message" => "登录成功", "session_id" => $sessionId];
    }
    throw new \RuntimeException("用户名或密码错误");
});

// 5. 测试API
echo "=== GET /users ===" . PHP_EOL;
echo $router->dispatch("GET", "/users") . PHP_EOL;

echo "=== POST /users ===" . PHP_EOL;
echo $router->dispatch("POST", "/users", [
    "name" => "赵六",
    "email" => "zhaoliu@test.com"
]) . PHP_EOL;

echo "=== POST /login（正确密码）===" . PHP_EOL;
echo $router->dispatch("POST", "/login", [
    "username" => "admin",
    "password" => "123456"
]) . PHP_EOL;

echo "=== POST /login（错误密码）===" . PHP_EOL;
echo $router->dispatch("POST", "/login", [
    "username" => "admin",
    "password" => "wrong"
]) . PHP_EOL;

echo "=== GET /unknown（404测试）===" . PHP_EOL;
echo $router->dispatch("GET", "/unknown") . PHP_EOL;

// 【思考题】
// 1. 在真实的Web环境中，$_SESSION的工作原理是什么？Cookie和Session的关系是怎样的？
// 2. json_encode的JSON_UNESCAPED_UNICODE选项有什么作用？为什么在处理中文时很重要？
