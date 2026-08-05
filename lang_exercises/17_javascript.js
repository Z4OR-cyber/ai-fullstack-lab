// ====================================================================
// 阶段十七：JavaScript 编程练习（10题）
// 题数：10
// 创建日期：2026-08-05
// 说明：全中文注释，代码用英文；所有代码可用 node 直接运行
// ====================================================================

// ====================================================================
// 第1题：作用域与闭包
// 知识点：词法作用域、闭包陷阱、IIFE（立即执行函数表达式）
// --------------------------------------------------------------------
// JavaScript 采用词法作用域（也叫静态作用域），即变量的作用域在
// 代码编写时就确定了，而不是在调用时确定。闭包是指一个函数能够
// 访问其外部函数作用域中的变量，即使外部函数已经执行完毕。
// 经典陷阱：在 for 循环中使用 var 声明的变量，所有闭包共享同一
// 个变量引用，导致输出都是最终值。用 let 可以解决此问题。
// IIFE（Immediately Invoked Function Expression）可以创建一个
// 独立的作用域，避免变量污染全局命名空间。
// ====================================================================

// --- 1.1 词法作用域演示 ---
var globalVar = "我是全局变量";

function outerFunction() {
    var outerVar = "我是外层函数变量";

    function innerFunction() {
        // 内层函数可以访问外层函数的变量（词法作用域）
        console.log(globalVar);       // 我是全局变量
        console.log(outerVar);        // 我是外层函数变量
    }

    innerFunction();
}

outerFunction();

// --- 1.2 闭包陷阱：var vs let ---
// 经典面试题：使用 var 时，循环结束后 i 变成 5，所有定时器共享同一个 i
function closureTrapVar() {
    console.log("--- 使用 var 的闭包陷阱 ---");
    for (var i = 0; i < 3; i++) {
        setTimeout(function () {
            console.log("var i =", i); // 输出：3, 3, 3（都是最终值）
        }, 100);
    }
}

// 使用 let 时，每次迭代都会创建一个新的绑定
function closureTrapLet() {
    console.log("--- 使用 let 解决闭包陷阱 ---");
    for (let i = 0; i < 3; i++) {
        setTimeout(function () {
            console.log("let i =", i); // 输出：0, 1, 2（各自独立）
        }, 100);
    }
}

closureTrapVar();
closureTrapLet();

// --- 1.3 利用 IIFE 创建独立作用域 ---
// IIFE 语法：(function(){ ... })()  或  (() => { ... })()
var counter = (function () {
    var count = 0; // 私有变量，外部无法直接访问

    return {
        increment: function () {
            count++;
            return count;
        },
        decrement: function () {
            count--;
            return count;
        },
        getCount: function () {
            return count;
        }
    };
})();

console.log("--- IIFE 计数器 ---");
console.log(counter.increment()); // 1
console.log(counter.increment()); // 2
console.log(counter.decrement()); // 1
console.log(counter.getCount());  // 1
// console.log(count); // ReferenceError: count is not defined

// --- 1.4 闭包实现函数工厂 ---
function createMultiplier(factor) {
    // 返回的函数记住了 factor 的值，这就是闭包
    return function (num) {
        return num * factor;
    };
}

var double = createMultiplier(2);
var triple = createMultiplier(3);
console.log("--- 函数工厂 ---");
console.log(double(5));  // 10
console.log(triple(5));  // 15

// 思考题：
// 1. 词法作用域和动态作用域的区别是什么？JavaScript 使用哪种？
// 2. 如果把 IIFE 中的 var count 改成 let count，结果会有什么不同？
// 3. 闭包会导致内存泄漏吗？在什么场景下需要特别注意？


// ====================================================================
// 第2题：原型链
// 知识点：prototype、__proto__、原型继承
// --------------------------------------------------------------------
// JavaScript 是基于原型的语言。每个对象都有一个内部链接指向另一个
// 对象——它的原型（prototype）。当访问对象的属性时，如果对象本身
// 没有该属性，引擎会沿着原型链向上查找，直到找到或到达 null。
//
// 核心关系：
//   - 每个函数都有 prototype 属性，指向一个原型对象
//   - 原型对象的 constructor 属性指回函数本身
//   - 通过 new 创建的对象，其 __proto__ 指向构造函数的 prototype
//   - Object.prototype 是所有对象的根原型，其 __proto__ 为 null
//
// 原型链：obj -> Constructor.prototype -> Object.prototype -> null
// ====================================================================

// --- 2.1 原型链基本结构 ---
function Animal(name) {
    this.name = name;
}

// 在原型上添加方法，所有实例共享
Animal.prototype.eat = function () {
    console.log(this.name + " is eating.");
};

var animal = new Animal("Cat");
console.log("--- 原型链基本结构 ---");
console.log(animal.__proto__ === Animal.prototype);           // true
console.log(Animal.prototype.constructor === Animal);         // true
console.log(animal.__proto__.__proto__ === Object.prototype); // true
console.log(Object.prototype.__proto__);                      // null（原型链终点）

// --- 2.2 原型继承 ---
// 子类继承父类的原型方法
function Dog(name, breed) {
    Animal.call(this, name); // 调用父类构造函数，继承实例属性
    this.breed = breed;
}

// 关键步骤：将子类原型指向父类实例，建立原型链
Dog.prototype = Object.create(Animal.prototype);
Dog.prototype.constructor = Dog; // 修正 constructor 指向

Dog.prototype.bark = function () {
    console.log(this.name + " (" + this.breed + ") says: Woof!");
};

var dog = new Dog("Rex", "Labrador");
console.log("--- 原型继承 ---");
dog.eat();  // Rex is eating.（继承自 Animal）
dog.bark(); // Rex (Labrador) says: Woof!
console.log(dog instanceof Animal); // true
console.log(dog instanceof Dog);    // true

// --- 2.3 原型链查找过程演示 ---
var lookupObj = {
    ownProp: "我是自身属性"
};
// 给原型添加属性
Object.prototype.protoProp = "我是原型属性";

console.log("--- 原型链查找过程 ---");
console.log(lookupObj.ownProp);   // 自身属性，直接找到
console.log(lookupObj.protoProp); // 沿原型链找到 Object.prototype 上的属性
console.log(lookupObj.toString);  // Object.prototype 上的内置方法

// 清理刚才添加的原型属性（实际开发中不要修改内置原型）
delete Object.prototype.protoProp;

// --- 2.4 Object.create 实现纯原型继承 ---
var vehicleProto = {
    init: function (wheels) {
        this.wheels = wheels;
        return this;
    },
    describe: function () {
        return "Vehicle with " + this.wheels + " wheels";
    }
};

var bike = Object.create(vehicleProto).init(2);
var car = Object.create(vehicleProto).init(4);
console.log("--- Object.create 继承 ---");
console.log(bike.describe()); // Vehicle with 2 wheels
console.log(car.describe());  // Vehicle with 4 wheels

// 思考题：
// 1. 为什么 Dog.prototype = new Animal() 不是最佳的原型继承方式？
//    （提示：会执行父类构造函数，可能产生副作用）
// 2. __proto__ 和 prototype 有什么区别？
// 3. Object.create(null) 创建的对象有什么特殊性？


// ====================================================================
// 第3题：this 绑定
// 知识点：默认绑定、隐式绑定、显式绑定、new绑定、箭头函数
// --------------------------------------------------------------------
// this 的指向取决于函数的调用方式，而不是定义方式。五条规则按
// 优先级从高到低排列：
//   1. new 绑定：new Foo() 中的 this 指向新创建的对象
//   2. 显式绑定：call/apply/bind 指定的 this
//   3. 隐式绑定：obj.method() 中的 this 指向 obj
//   4. 默认绑定：独立调用函数，this 指向 undefined（严格模式）或全局对象
//   5. 箭头函数：没有自己的 this，继承外层作用域的 this
// ====================================================================

// --- 3.1 默认绑定 ---
function showThis() {
    console.log("默认绑定 this:", this === global ? "global" : this);
}
showThis(); // 非严格模式下指向全局对象

// --- 3.2 隐式绑定 ---
var obj = {
    name: "隐式绑定对象",
    show: function () {
        console.log("隐式绑定 this.name:", this.name);
    }
};
obj.show(); // this 指向 obj

// 隐式丢失：将方法赋值给变量后独立调用
var lostShow = obj.show;
// lostShow(); // this 不再指向 obj，变为默认绑定

// --- 3.3 显式绑定：call / apply / bind ---
function greet(greeting, punctuation) {
    console.log(greeting + ", " + this.name + punctuation);
}

var person = { name: "Alice" };

// call：第一个参数是 this，后续参数逐个传递
greet.call(person, "Hello", "!");    // Hello, Alice!

// apply：第一个参数是 this，第二个参数是参数数组
greet.apply(person, ["Hi", "."]);    // Hi, Alice.

// bind：返回一个永久绑定 this 的新函数
var boundGreet = greet.bind(person, "Hey");
boundGreet("?"); // Hey, Alice?

// --- 3.4 new 绑定 ---
function Player(name, level) {
    // new 操作符创建新对象，this 指向新对象
    this.name = name;
    this.level = level;
    // 如果不显式 return 对象，自动返回 this
}

var player = new Player("Hero", 10);
console.log("--- new 绑定 ---");
console.log(player.name, player.level); // Hero 10
console.log(player instanceof Player);  // true

// --- 3.5 箭头函数的 this ---
// 箭头函数没有自己的 this，继承定义时外层的 this
var timer = {
    seconds: 0,
    start: function () {
        // 普通函数中 this 指向调用者
        var self = this;

        // 箭头函数继承外层 this（即 timer 对象）
        setInterval(() => {
            this.seconds++;
            if (this.seconds <= 3) {
                console.log("箭头函数 this.seconds:", this.seconds);
            }
        }, 100);

        // 对比：普通函数会丢失 this
        // setInterval(function () {
        //     this.seconds++; // this 不指向 timer！
        // }, 100);
    }
};

console.log("--- 箭头函数 this ---");
timer.start();

// --- 3.6 绑定优先级演示 ---
function priorityCheck() {
    console.log("this.name:", this.name);
}

var ctx1 = { name: "隐式" };
var ctx2 = { name: "显式" };

// 隐式绑定 vs 显式绑定：显式优先
priorityCheck.call(ctx1); // this.name: 隐式

var bound = priorityCheck.bind(ctx2);
var ctx3 = { name: "新对象", fn: bound };
ctx3.fn(); // this.name: 显式（bind 优先级高于隐式）

// 思考题：
// 1. 箭头函数能使用 call/apply/bind 改变 this 吗？为什么？
// 2. new 绑定和 bind 的优先级谁更高？
// 3. 在事件回调中，为什么推荐使用箭头函数而不是普通函数？


// ====================================================================
// 第4题：异步编程
// 知识点：Promise、async/await、事件循环
// --------------------------------------------------------------------
// JavaScript 是单线程的，通过事件循环实现非阻塞异步。
//
// 事件循环模型：
//   - 调用栈：同步代码在此执行
//   - 微任务队列：Promise.then/catch/finally、queueMicrotask
//   - 宏任务队列：setTimeout、setInterval、I/O
//   - 执行顺序：同步代码 -> 微任务（清空）-> 一个宏任务 -> 微任务（清空）-> ...
//
// Promise 三种状态：pending -> fulfilled / rejected
// async/await 是 Promise 的语法糖，让异步代码看起来像同步代码。
// ====================================================================

// --- 4.1 事件循环执行顺序 ---
console.log("--- 事件循环执行顺序 ---");
console.log("1. 同步代码");

setTimeout(function () {
    console.log("4. 宏任务");
}, 0);

Promise.resolve().then(function () {
    console.log("3. 微任务");
});

console.log("2. 同步代码");
// 输出顺序：1 -> 2 -> 3 -> 4（微任务先于宏任务）

// --- 4.2 Promise 基本用法 ---
function delay(ms) {
    return new Promise(function (resolve, reject) {
        if (ms < 0) {
            reject(new Error("延迟时间不能为负数"));
        } else {
            setTimeout(function () {
                resolve("延迟 " + ms + "ms 完成");
            }, ms);
        }
    });
}

// 链式调用
delay(100)
    .then(function (result) {
        console.log("--- Promise 链式调用 ---");
        console.log(result); // 延迟 100ms 完成
        return delay(50);
    })
    .then(function (result) {
        console.log(result); // 延迟 50ms 完成
    })
    .catch(function (error) {
        console.error("捕获错误:", error.message);
    });

// --- 4.3 Promise 并行控制 ---
// Promise.all：所有完成才完成，任一失败即失败
// Promise.race：第一个完成（成功或失败）即结束
// Promise.allSettled：等待所有完成，无论成功失败
var p1 = Promise.resolve("结果1");
var p2 = Promise.resolve("结果2");
var p3 = Promise.reject("错误3");

Promise.all([p1, p2])
    .then(function (results) {
        console.log("--- Promise.all ---");
        console.log(results); // ["结果1", "结果2"]
    });

Promise.allSettled([p1, p2, p3])
    .then(function (results) {
        console.log("--- Promise.allSettled ---");
        results.forEach(function (r) {
            console.log(r.status, r.value || r.reason);
        });
    });

// --- 4.4 async/await ---
// 用同步的方式写异步代码
function fetchData(id) {
    return new Promise(function (resolve) {
        setTimeout(function () {
            resolve({ id: id, name: "数据" + id });
        }, 100);
    });
}

async function loadData() {
    console.log("--- async/await ---");
    try {
        var data1 = await fetchData(1); // 等待 Promise 完成
        console.log("获取到:", data1.name);

        var data2 = await fetchData(2);
        console.log("获取到:", data2.name);

        // 并行加载多个
        var [d1, d2] = await Promise.all([fetchData(3), fetchData(4)]);
        console.log("并行获取:", d1.name, d2.name);

        return "全部加载完成";
    } catch (error) {
        console.error("加载失败:", error);
    }
}

loadData().then(function (result) {
    console.log(result);
});

// --- 4.5 模拟请求重试 ---
async function fetchWithRetry(url, maxRetries) {
    for (var i = 0; i < maxRetries; i++) {
        try {
            // 模拟请求：随机成功或失败
            var success = Math.random() > 0.5;
            if (success) {
                return "成功获取 " + url;
            }
            throw new Error("请求失败，第 " + (i + 1) + " 次");
        } catch (error) {
            console.log("重试:", error.message);
            if (i === maxRetries - 1) {
                throw error; // 最后一次失败，抛出错误
            }
            await delay(50 * (i + 1)); // 指数退避
        }
    }
}

fetchWithRetry("https://api.example.com/data", 3)
    .then(function (r) {
        console.log("重试结果:", r);
    })
    .catch(function (e) {
        console.log("最终失败:", e.message);
    });

// 思考题：
// 1. 微任务和宏任务的执行优先级是怎样的？为什么 Promise.then 先于 setTimeout？
// 2. async 函数的返回值是什么？await 后面只能跟 Promise 吗？
// 3. 如何实现并发限制（同时最多 N 个请求）？


// ====================================================================
// 第5题：ES6+ 特性
// 知识点：let/const、解构赋值、模板字符串、Symbol
// --------------------------------------------------------------------
// ES6（ES2015）引入了大量语法增强，后续每年持续更新。
// let/const 提供块级作用域；解构赋值简化数据提取；模板字符串支持
// 多行文本和插值；Symbol 提供唯一标识符，用于避免属性名冲突。
// ====================================================================

// --- 5.1 let 与 const ---
{
    let letVar = "块级作用域";
    const CONST_VAR = "不可重新赋值";

    // const 声明的对象，属性仍可修改（引用不变，内容可变）
    const config = { debug: true };
    config.debug = false; // 合法：修改属性
    console.log("--- let/const ---");
    console.log(config.debug); // false

    // constVar = "新值"; // TypeError: Assignment to constant variable
}
// console.log(letVar); // ReferenceError: letVar is not defined

// --- 5.2 解构赋值 ---
// 数组解构
var [a, b, c] = [1, 2, 3];
console.log("--- 数组解构 ---");
console.log(a, b, c); // 1 2 3

// 默认值与跳过
var [x, , z = 10] = [1, 2];
console.log(x, z); // 1 10

// 对象解构
var user = { name: "Bob", age: 25, city: "Beijing" };
var { name, age, city = "Shanghai" } = user;
console.log("--- 对象解构 ---");
console.log(name, age, city); // Bob 25 Beijing

// 重命名解构
var { name: fullName } = user;
console.log("重命名:", fullName); // Bob

// 嵌套解构
var response = {
    data: { users: [{ name: "Alice" }] }
};
var {
    data: {
        users: [{ name: firstName }]
    }
} = response;
console.log("嵌套解构:", firstName); // Alice

// 函数参数解构
function createUser({ name, age, role = "user" }) {
    return name + " (" + age + ") - " + role;
}
console.log(createUser({ name: "Charlie", age: 30 })); // Charlie (30) - user

// --- 5.3 模板字符串 ---
var itemName = "咖啡";
var price = 28;
var multiLine = `--- 模板字符串 ---
商品：${itemName}
价格：¥${price}
总价：¥${price * 1.1}`;
console.log(multiLine);

// 标签模板
function tag(strings, ...values) {
    var result = "";
    strings.forEach(function (str, i) {
        result += str;
        if (i < values.length) {
            result += "[" + values[i] + "]";
        }
    });
    return result;
}
var tagged = tag`Hello ${"World"} count ${42}`;
console.log("标签模板:", tagged); // Hello [World] count [42]

// --- 5.4 Symbol ---
// Symbol 创建唯一标识符，常用于定义对象的私有/特殊属性
var sym1 = Symbol("id");
var sym2 = Symbol("id");
console.log("--- Symbol ---");
console.log(sym1 === sym2); // false（每个 Symbol 都是唯一的）

// 用 Symbol 作为对象属性键
var objWithSymbol = {
    [sym1]: "Symbol 属性值",
    normalProp: "普通属性"
};
console.log(objWithSymbol[sym1]); // Symbol 属性值
console.log(Object.keys(objWithSymbol)); // ["normalProp"]（Symbol 不被枚举）
console.log(Object.getOwnPropertySymbols(objWithSymbol)); // [Symbol(id)]

// Symbol.for 全局注册
var sharedSym1 = Symbol.for("global");
var sharedSym2 = Symbol.for("global");
console.log("Symbol.for:", sharedSym1 === sharedSym2); // true
console.log("Symbol.keyFor:", Symbol.keyFor(sharedSym1)); // global

// --- 5.5 展开运算符与剩余参数 ---
// 数组展开
var arr1 = [1, 2, 3];
var arr2 = [...arr1, 4, 5]; // [1, 2, 3, 4, 5]
console.log("--- 展开运算符 ---");
console.log(arr2);

// 对象展开（ES2018）
var defaults = { theme: "light", fontSize: 14 };
var custom = { ...defaults, fontSize: 16 };
console.log(custom); // { theme: "light", fontSize: 16 }

// 剩余参数
function sum(...numbers) {
    return numbers.reduce(function (total, n) {
        return total + n;
    }, 0);
}
console.log("剩余参数:", sum(1, 2, 3, 4, 5)); // 15

// 思考题：
// 1. const 声明的数组能用 push 修改吗？为什么？
// 2. Symbol 在迭代器协议中扮演什么角色？（提示：Symbol.iterator）
// 3. 标签模板字符串有什么实际用途？


// ====================================================================
// 第6题：模块系统
// 知识点：CommonJS、ESM（ES Modules）、import/export
// --------------------------------------------------------------------
// JavaScript 有两大模块系统：
//   - CommonJS：Node.js 传统模块系统，使用 require/module.exports
//   - ESM：ES6 标准模块系统，使用 import/export
//
// 主要区别：
//   - CommonJS 是同步加载，运行时确定依赖；ESM 是异步加载，编译时确定依赖
//   - CommonJS 导出的是值的拷贝；ESM 导出的是值的引用（实时绑定）
//   - CommonJS 中 this 指向 module.exports；ESM 中 this 是 undefined
//
// 注意：本文件使用 CommonJS（.js 文件用 node 运行默认支持），
// ESM 需要 .mjs 扩展名或 package.json 中设置 "type": "module"
// ====================================================================

// --- 6.1 CommonJS 模块演示 ---
// 以下代码模拟模块的导出与导入，实际使用时拆分到不同文件

// 模拟 mathModule.js 的内容
var mathModule = (function createMathModule() {
    // 私有变量（模块内部使用，不导出）
    var PI = 3.14159265;

    // 私有函数
    function validate(n) {
        if (typeof n !== "number" || isNaN(n)) {
            throw new TypeError("参数必须是数字");
        }
    }

    // 导出的函数
    function add(a, b) {
        validate(a);
        validate(b);
        return a + b;
    }

    function multiply(a, b) {
        validate(a);
        validate(b);
        return a * b;
    }

    function circleArea(radius) {
        validate(radius);
        return PI * radius * radius;
    }

    // module.exports 的等价模拟
    return { add: add, multiply: multiply, circleArea: circleArea };
})();

// 模拟 require 的使用
var math = mathModule;
console.log("--- CommonJS 模块 ---");
console.log(math.add(2, 3));        // 5
console.log(math.multiply(4, 5));   // 20
console.log(math.circleArea(2));    // 12.5663706
// console.log(math.PI); // undefined（未导出）
// console.log(math.validate(1)); // TypeError（未导出）

// --- 6.2 CommonJS 值的拷贝 vs ESM 值的引用 ---
// CommonJS 导出值的拷贝示例
function createCounterModule() {
    var count = 0;

    function increment() {
        count++;
        return count;
    }

    function getCount() {
        return count;
    }

    // 导出的是当前值的快照
    var exported = {
        increment: increment,
        getCount: getCount
    };

    return exported;
}

var counterModule = createCounterModule();
console.log("--- CommonJS 值拷贝 ---");
counterModule.increment();
counterModule.increment();
console.log(counterModule.getCount()); // 2（通过方法访问，闭包保持引用）

// --- 6.3 ESM 导入导出语法演示（注释说明，无法直接运行） ---
/*
// === mathUtils.mjs ===

// 命名导出
export function add(a, b) {
    return a + b;
}

export function subtract(a, b) {
    return a - b;
}

// 默认导出（每个模块只能有一个默认导出）
export default function multiply(a, b) {
    return a * b;
}

// 导出常量
export const MAX_VALUE = 100;

// 聚合导出（re-export）
export { add as plus } from "./mathUtils.mjs";


// === main.mjs ===

// 导入默认导出
import multiply from "./mathUtils.mjs";

// 导入命名导出
import { add, subtract } from "./mathUtils.mjs";

// 导入时重命名
import { add as plus } from "./mathUtils.mjs";

// 导入全部（命名空间导入）
import * as math from "./mathUtils.mjs";
console.log(math.add(1, 2));
console.log(math.default(3, 4));

// 动态导入（返回 Promise）
const module = await import("./mathUtils.mjs");
console.log(module.add(1, 2));
*/

// --- 6.4 动态 require 模拟 ---
// CommonJS 支持运行时动态加载
function dynamicModuleLoader(moduleName) {
    var modules = {
        "string-utils": {
            uppercase: function (s) { return s.toUpperCase(); },
            reverse: function (s) { return s.split("").reverse().join(""); }
        },
        "number-utils": {
            isEven: function (n) { return n % 2 === 0; },
            factorial: function (n) {
                return n <= 1 ? 1 : n * this.factorial(n - 1);
            }
        }
    };

    if (modules[moduleName]) {
        return modules[moduleName];
    }
    throw new Error("找不到模块: " + moduleName);
}

var strUtils = dynamicModuleLoader("string-utils");
var numUtils = dynamicModuleLoader("number-utils");
console.log("--- 动态模块加载 ---");
console.log(strUtils.uppercase("hello"));  // HELLO
console.log(strUtils.reverse("world"));    // dlrow
console.log(numUtils.isEven(4));           // true
console.log(numUtils.factorial(5));        // 120

// 思考题：
// 1. CommonJS 的 require 是同步的，浏览器中能用吗？为什么？
// 2. ESM 中 export const 和 export default 有什么区别？
// 3. 为什么 ESM 导出的是"引用"而不是"拷贝"？这有什么实际意义？


// ====================================================================
// 第7题：数组方法
// 知识点：map、filter、reduce、find、some、every
// --------------------------------------------------------------------
// JavaScript 数组提供了丰富的函数式方法，掌握它们可以大幅提升
// 代码的表达力和可读性。这些方法不会修改原数组（除 forEach 外）。
//
// 方法分类：
//   - 转换类：map（映射）、flatMap（扁平映射）
//   - 过滤类：filter（过滤）
//   - 聚合类：reduce（归约）、reduceRight（反向归约）
//   - 查找类：find（找第一个）、findIndex（找索引）
//   - 判断类：some（存在满足）、every（全部满足）
//   - 遍历类：forEach（遍历无返回值）
// ====================================================================

var students = [
    { name: "Alice", age: 20, score: 92, subjects: ["Math", "Physics"] },
    { name: "Bob", age: 22, score: 78, subjects: ["Biology", "Chemistry"] },
    { name: "Charlie", age: 21, score: 85, subjects: ["Math", "CS"] },
    { name: "Diana", age: 23, score: 95, subjects: ["Math", "Physics", "CS"] },
    { name: "Eve", age: 20, score: 60, subjects: ["Art"] }
];

// --- 7.1 map：对每个元素进行映射转换 ---
var names = students.map(function (s) {
    return s.name;
});
console.log("--- map ---");
console.log(names); // ["Alice", "Bob", "Charlie", "Diana", "Eve"]

var summaries = students.map(function (s) {
    return s.name + ": " + s.score + "分 (" + s.age + "岁)";
});
console.log(summaries);

// --- 7.2 filter：过滤满足条件的元素 ---
var passed = students.filter(function (s) {
    return s.score >= 80;
});
console.log("--- filter ---");
console.log(passed.map(function (s) { return s.name; })); // ["Alice", "Charlie", "Diana"]

var mathStudents = students.filter(function (s) {
    return s.subjects.includes("Math");
});
console.log("选了Math的:", mathStudents.map(function (s) { return s.name; }));

// --- 7.3 reduce：将数组归约为单个值 ---
var totalScore = students.reduce(function (sum, s) {
    return sum + s.score;
}, 0);
console.log("--- reduce ---");
console.log("总分:", totalScore); // 410
console.log("平均分:", totalScore / students.length); // 82

// reduce 高级用法：分组
var groupedByAge = students.reduce(function (groups, s) {
    var key = s.age;
    if (!groups[key]) {
        groups[key] = [];
    }
    groups[key].push(s.name);
    return groups;
}, {});
console.log("按年龄分组:", groupedByAge);
// { "20": ["Alice", "Eve"], "21": ["Charlie"], "22": ["Bob"], "23": ["Diana"] }

// reduce 高级用法：统计科目出现次数
var subjectCount = students.reduce(function (counts, s) {
    s.subjects.forEach(function (subject) {
        counts[subject] = (counts[subject] || 0) + 1;
    });
    return counts;
}, {});
console.log("科目统计:", subjectCount);

// --- 7.4 find / findIndex：查找第一个满足条件的元素 ---
var topStudent = students.find(function (s) {
    return s.score >= 95;
});
console.log("--- find ---");
console.log("最高分学生:", topStudent ? topStudent.name : "无"); // Diana

var topIndex = students.findIndex(function (s) {
    return s.score >= 95;
});
console.log("索引:", topIndex); // 3

// --- 7.5 some / every：条件判断 ---
var hasFailing = students.some(function (s) {
    return s.score < 60;
});
console.log("--- some/every ---");
console.log("有不及格的吗:", hasFailing); // false（60 不算不及格）

var allAdults = students.every(function (s) {
    return s.age >= 18;
});
console.log("都是成年人吗:", allAdults); // true

// --- 7.6 链式调用组合使用 ---
// 找出选了 Math 的学生，按分数降序排列，取前两名
var topMathStudents = students
    .filter(function (s) { return s.subjects.includes("Math"); })
    .sort(function (a, b) { return b.score - a.score; })
    .slice(0, 2)
    .map(function (s) { return s.name + " (" + s.score + ")"; });
console.log("--- 链式调用 ---");
console.log(topMathStudents); // ["Diana (95)", "Alice (92)"]

// --- 7.7 flatMap：映射后扁平化 ---
var allSubjects = students.flatMap(function (s) {
    return s.subjects;
});
console.log("--- flatMap ---");
console.log(allSubjects);
// ["Math", "Physics", "Biology", "Chemistry", "Math", "CS", "Math", "Physics", "CS", "Art"]

var uniqueSubjects = Array.from(new Set(allSubjects));
console.log("去重科目:", uniqueSubjects);

// 思考题：
// 1. map 和 forEach 的区别是什么？什么时候该用哪个？
// 2. reduce 的初始值省略时会发生什么？有什么风险？
// 3. 如何用 reduce 实现 map 和 filter 的功能？


// ====================================================================
// 第8题：对象与类
// 知识点：对象字面量增强、类语法、getter/setter、类继承
// --------------------------------------------------------------------
// ES6 引入了 class 关键字，但 JavaScript 的类本质上仍然是基于
// 原型的语法糖。class 语法更接近传统面向对象语言的写法。
//
// 核心概念：
//   - 对象字面量增强：计算属性名、方法简写、属性简写
//   - class 语法：constructor、实例方法、静态方法
//   - getter/setter：通过 get/set 关键字定义访问器
//   - extends/super：类继承与父类调用
//   - 私有字段：#field 语法（ES2022）
// ====================================================================

// --- 8.1 对象字面量增强 ---
var propName = "dynamicMethod";
var value = 42;

var enhancedObj = {
    // 属性简写
    value,
    // 方法简写
    greet() {
        return "Hello!";
    },
    // 计算属性名
    [propName]() {
        return "动态方法被调用";
    },
    // 计算属性名 + 表达式
    ["key_" + 1 + 2]: "key_12"
};

console.log("--- 对象字面量增强 ---");
console.log(enhancedObj.value);        // 42
console.log(enhancedObj.greet());      // Hello!
console.log(enhancedObj.dynamicMethod()); // 动态方法被调用
console.log(enhancedObj.key_12);       // key_12

// --- 8.2 类的基本语法 ---
class Person2 {
    // 私有字段（ES2022，需要 Node.js 12+）
    #ssn = "";

    constructor(name, age) {
        this.name = name;   // 公开属性
        this.age = age;
        this.#ssn = "XXX-XX-" + Math.floor(Math.random() * 10000);
    }

    // 实例方法
    introduce() {
        return `我叫${this.name}，今年${this.age}岁`;
    }

    // getter
    get info() {
        return `${this.name} (${this.age})`;
    }

    // setter
    set setAge(newAge) {
        if (newAge < 0 || newAge > 150) {
            throw new RangeError("年龄不合法");
        }
        this.age = newAge;
    }

    // 静态方法
    static create(name) {
        return new Person2(name, 0);
    }

    // 访问私有字段的方法
    getSSN() {
        return this.#ssn;
    }
}

var p = new Person2("Alice", 30);
console.log("--- 类基本语法 ---");
console.log(p.introduce());  // 我叫Alice，今年30岁
console.log(p.info);         // Alice (30)（通过 getter 访问）
p.setAge = 31;
console.log(p.info);         // Alice (31)
console.log(Person2.create("Baby").info); // Baby (0)
// console.log(p.#ssn); // SyntaxError: 私有字段不能直接访问
console.log("SSN:", p.getSSN());

// --- 8.3 类继承 ---
class Student2 extends Person2 {
    constructor(name, age, grade) {
        super(name, age); // 必须在 this 之前调用 super
        this.grade = grade;
    }

    // 重写父类方法
    introduce() {
        return super.introduce() + `，就读${this.grade}年级`;
    }

    // 子类特有方法
    study(subject) {
        return `${this.name}正在学习${subject}`;
    }

    // 静态方法也可以继承和重写
    static create(name) {
        return new Student2(name, 0, 1);
    }
}

var student2 = new Student2("Bob", 15, 9);
console.log("--- 类继承 ---");
console.log(student2.introduce());   // 我叫Bob，今年15岁，就读9年级
console.log(student2.study("Math")); // Bob正在学习Math
console.log(student2 instanceof Person2); // true
console.log(student2 instanceof Student2); // true

var babyStudent = Student2.create("Tom");
console.log(babyStudent.introduce()); // 我叫Tom，今年0岁，就读1年级

// --- 8.4 混入（Mixin）模式 ---
// JavaScript 不支持多继承，可通过混入实现代码复用
const Serializable = {
    serialize() {
        return JSON.stringify(this);
    },
    deserialize(jsonStr) {
        return Object.assign(Object.create(Object.getPrototypeOf(this)), JSON.parse(jsonStr));
    }
};

const Validatable = {
    validate() {
        var errors = [];
        for (var key in this) {
            if (this[key] === undefined || this[key] === null) {
                errors.push(key + " 不能为空");
            }
        }
        return errors.length === 0 ? "验证通过" : errors;
    }
};

class Product {
    constructor(name, price) {
        this.name = name;
        this.price = price;
    }
}

// 将混入方法复制到原型上
Object.assign(Product.prototype, Serializable, Validatable);

var product = new Product("笔记本", 5999);
console.log("--- Mixin 模式 ---");
console.log(product.serialize()); // {"name":"笔记本","price":5999}
console.log(product.validate());  // 验证通过

// 思考题：
// 1. class 语法和构造函数+原型有什么本质区别？
// 2. super 在构造函数和方法中分别有什么作用？
// 3. #private 字段和约定使用 _prefix 有什么优劣？


// ====================================================================
// 第9题：生成器与迭代器
// 知识点：generator、iterator、yield、Symbol.iterator
// --------------------------------------------------------------------
// 迭代器协议：一个对象实现 next() 方法，返回 { value, done }
// 可迭代协议：一个对象实现 [Symbol.iterator]() 方法，返回迭代器
//
// 生成器函数 function* 是创建迭代器的简便方式：
//   - yield 暂停执行并返回值
//   - yield* 委托给另一个可迭代对象
//   - next(value) 可以向生成器传入值
//   - return() 和 throw() 可以提前终止
// ====================================================================

// --- 9.1 手动实现迭代器 ---
function createRangeIterator(start, end, step) {
    var current = start;
    return {
        next: function () {
            if (current < end) {
                var value = current;
                current += step;
                return { value: value, done: false };
            }
            return { value: undefined, done: true };
        }
    };
}

console.log("--- 手动迭代器 ---");
var rangeIter = createRangeIterator(1, 5, 1);
console.log(rangeIter.next()); // { value: 1, done: false }
console.log(rangeIter.next()); // { value: 2, done: false }
console.log(rangeIter.next()); // { value: 3, done: false }
console.log(rangeIter.next()); // { value: 4, done: false }
console.log(rangeIter.next()); // { value: undefined, done: true }

// --- 9.2 生成器函数基础 ---
function* simpleGenerator() {
    yield "第一步";
    yield "第二步";
    yield "第三步";
    return "完成";
}

console.log("--- 生成器基础 ---");
var gen = simpleGenerator();
console.log(gen.next()); // { value: "第一步", done: false }
console.log(gen.next()); // { value: "第二步", done: false }
console.log(gen.next()); // { value: "第三步", done: false }
console.log(gen.next()); // { value: "完成", done: true }

// 生成器可用于 for...of 循环
for (var val of simpleGenerator()) {
    console.log("for...of:", val); // 第一步, 第二步, 第三步（return 的值不会被遍历）
}

// --- 9.3 用生成器实现 range ---
function* range(start, end, step) {
    step = step || 1;
    for (var i = start; i < end; i += step) {
        yield i;
    }
}

console.log("--- 生成器 range ---");
console.log(Array.from(range(0, 10, 2))); // [0, 2, 4, 6, 8]
console.log([...range(1, 5)]);             // [1, 2, 3, 4]

// --- 9.4 yield 双向通信 ---
function* conversationGenerator() {
    var question = yield "你好，你是谁？"; // yield 返回 next() 传入的值
    console.log("收到回答:", question);
    var mood = yield "你今天" + question + "了吗？";
    console.log("心情:", mood);
    return "对话结束";
}

console.log("--- yield 双向通信 ---");
var conv = conversationGenerator();
console.log(conv.next());           // { value: "你好，你是谁？", done: false }
console.log(conv.next("小明"));      // 收到回答: 小明 -> { value: "你今天小明了吗？", done: false }
console.log(conv.next("很开心"));    // 心情: 很开心 -> { value: "对话结束", done: true }

// --- 9.5 yield* 委托生成器 ---
function* innerGen() {
    yield "A";
    yield "B";
}

function* outerGen() {
    yield 1;
    yield* innerGen(); // 委托给内部生成器
    yield 2;
    yield* "XYZ";      // 委托给字符串（也是可迭代的）
}

console.log("--- yield* 委托 ---");
console.log([...outerGen()]); // [1, "A", "B", 2, "X", "Y", "Z"]

// --- 9.6 自定义可迭代对象 ---
class NumberSequence {
    constructor(start, end) {
        this.start = start;
        this.end = end;
    }

    // 实现 Symbol.iterator 使对象可迭代
    [Symbol.iterator]() {
        var current = this.start;
        var end = this.end;
        return {
            next() {
                return current <= end
                    ? { value: current++, done: false }
                    : { value: undefined, done: true };
            }
        };
    }
}

console.log("--- 自定义可迭代对象 ---");
var seq = new NumberSequence(5, 10);
for (var num of seq) {
    console.log(num); // 5, 6, 7, 8, 9, 10
}
console.log([...new NumberSequence(1, 3)]); // [1, 2, 3]

// --- 9.7 无限序列生成器 ---
function* fibonacci() {
    var a = 0, b = 1;
    while (true) {
        yield a;
        [a, b] = [b, a + b];
    }
}

console.log("--- 无限序列生成器 ---");
var fib = fibonacci();
var fibFirst10 = [];
for (var i = 0; i < 10; i++) {
    fibFirst10.push(fib.next().value);
}
console.log("斐波那契前10项:", fibFirst10); // [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]

// 思考题：
// 1. 生成器和数组有什么区别？什么场景下用生成器更合适？
// 2. for...of 和 for...in 的区别是什么？
// 3. 如何实现一个惰性求值的管道（pipe）？


// ====================================================================
// 第10题：错误处理与调试
// 知识点：try-catch-finally、Error 类型、自定义错误、调试技巧
// --------------------------------------------------------------------
// JavaScript 的错误处理机制：
//   - try-catch-finally：捕获同步错误
//   - 异步错误需要用 Promise.catch 或 try-catch 包裹 await
//   - Error 是所有错误的基类，子类包括 TypeError、RangeError、
//     SyntaxError、ReferenceError 等
//   - 可继承 Error 创建自定义错误类，增加语义化错误处理
//
// 调试技巧：
//   - console.log/warn/error 分级输出
//   - console.table 表格化输出
//   - console.trace 打印调用栈
//   - throw 主动抛出错误，提供有意义的错误信息
// ====================================================================

// --- 10.1 try-catch-finally ---
function riskyOperation(input) {
    try {
        if (typeof input !== "number") {
            throw new TypeError("期望数字类型，得到: " + typeof input);
        }
        if (input < 0) {
            throw new RangeError("输入不能为负数: " + input);
        }
        return Math.sqrt(input);
    } catch (error) {
        // error 对象包含 name、message、stack 属性
        console.log("--- try-catch ---");
        console.log("错误类型:", error.name);
        console.log("错误信息:", error.message);
        return null;
    } finally {
        // 无论是否出错都会执行
        console.log("finally: 清理资源");
    }
}

console.log("--- try-catch-finally ---");
console.log("结果:", riskyOperation(16));   // 4
console.log("结果:", riskyOperation(-1));   // null（RangeError）
console.log("结果:", riskyOperation("abc")); // null（TypeError）

// --- 10.2 内置 Error 类型 ---
function demonstrateErrorTypes() {
    var errors = [];

    // TypeError：类型不匹配
    try {
        null.foo;
    } catch (e) {
        errors.push({ type: e.name, message: e.message });
    }

    // RangeError：值超出范围
    try {
        var arr = new Array(-1);
    } catch (e) {
        errors.push({ type: e.name, message: e.message });
    }

    // ReferenceError：引用未定义的变量
    try {
        // eslint-disable-next-line
        undefinedVariable;
    } catch (e) {
        errors.push({ type: e.name, message: e.message });
    }

    // SyntaxError：语法错误（需用 eval 触发，实际开发中罕见）
    try {
        eval("var x = ;");
    } catch (e) {
        errors.push({ type: e.name, message: e.message });
    }

    console.log("--- 内置 Error 类型 ---");
    console.table(errors);
}

demonstrateErrorTypes();

// --- 10.3 自定义错误类 ---
class ValidationError extends Error {
    constructor(field, message) {
        super(message);
        this.name = "ValidationError";
        this.field = field; // 自定义属性
    }

    toString() {
        return `${this.name}[${this.field}]: ${this.message}`;
    }
}

class NetworkError extends Error {
    constructor(url, statusCode) {
        super(`请求 ${url} 失败，状态码: ${statusCode}`);
        this.name = "NetworkError";
        this.url = url;
        this.statusCode = statusCode;
    }

    isRetryable() {
        // 5xx 错误通常可以重试
        return this.statusCode >= 500;
    }
}

// 使用自定义错误
function validateUser(user) {
    if (!user.name || user.name.trim() === "") {
        throw new ValidationError("name", "用户名不能为空");
    }
    if (!user.email || !user.email.includes("@")) {
        throw new ValidationError("email", "邮箱格式不正确");
    }
    if (user.age < 0 || user.age > 150) {
        throw new ValidationError("age", "年龄必须在 0-150 之间");
    }
    return "验证通过";
}

function simulateRequest(url) {
    var statusCode = Math.floor(Math.random() * 5) + 500; // 500-504
    throw new NetworkError(url, statusCode);
}

// 统一错误处理
function handleErrors(fn) {
    try {
        return fn();
    } catch (error) {
        if (error instanceof ValidationError) {
            console.log("--- 自定义错误: ValidationError ---");
            console.log("验证失败 - 字段:", error.field, "原因:", error.message);
        } else if (error instanceof NetworkError) {
            console.log("--- 自定义错误: NetworkError ---");
            console.log("网络错误:", error.message);
            console.log("是否可重试:", error.isRetryable());
        } else if (error instanceof Error) {
            console.log("--- 通用错误 ---");
            console.log("错误:", error.name, "-", error.message);
        }
        return null;
    }
}

handleErrors(function () { return validateUser({ name: "", email: "test@test.com", age: 25 }); });
handleErrors(function () { return validateUser({ name: "Alice", email: "bad-email", age: 25 }); });
handleErrors(function () { return simulateRequest("https://api.example.com/data"); });

// --- 10.4 异步错误处理 ---
async function asyncErrorHandling() {
    console.log("--- 异步错误处理 ---");

    // Promise.catch 方式
    Promise.reject(new Error("Promise 中的错误"))
        .catch(function (e) {
            console.log("Promise.catch 捕获:", e.message);
        });

    // async/await + try-catch 方式
    async function failingAsync() {
        throw new Error("async 函数中的错误");
    }

    try {
        await failingAsync();
    } catch (e) {
        console.log("await 捕获:", e.message);
    }

    // 全局未捕获 Promise 错误（仅作演示，实际监听会持续生效）
    // process.on("unhandledRejection", function (reason) {
    //     console.log("未处理的 Promise 拒绝:", reason);
    // });
}

asyncErrorHandling();

// --- 10.5 调试辅助工具 ---
var debugUtils = {
    // 断言：条件为 false 时输出警告
    assert(condition, message) {
        if (!condition) {
            console.error("断言失败:", message);
            console.trace(); // 打印调用栈
        }
    },

    // 计时器
    timer(label) {
        var start = Date.now();
        return function () {
            var elapsed = Date.now() - start;
            console.log(`[计时] ${label}: ${elapsed}ms`);
            return elapsed;
        };
    },

    // 分组日志
    group(label, fn) {
        console.group(label);
        var result = fn();
        console.groupEnd();
        return result;
    }
};

console.log("--- 调试工具 ---");
debugUtils.assert(1 + 1 === 2, "数学应该是对的");
debugUtils.assert(1 + 1 === 3, "这个断言会失败");

var stop = debugUtils.timer("循环100万次");
var sum = 0;
for (var i = 0; i < 1000000; i++) {
    sum += i;
}
stop();

debugUtils.group("用户数据处理", function () {
    console.log("步骤1: 加载数据");
    console.log("步骤2: 转换格式");
    console.log("步骤3: 保存结果");
});

// 思考题：
// 1. try-catch 能捕获异步错误吗？什么情况下不能？
// 2. 自定义错误类为什么要设置 this.name？不设置会怎样？
// 3. 在生产环境中，应该如何优雅地处理未捕获的异常？
