// ============================================================
// 阶段九：C++ 进阶编程练习
// 题数：10题
// 创建日期：2026-08-05
// 说明：从C语言基础扩展到C++现代特性，涵盖RAII到元编程
// 编译命令：g++ -std=c++17 -pthread -o 15_cpp 15_cpp.cpp
// ============================================================

#include <iostream>
#include <vector>
#include <map>
#include <unordered_map>
#include <algorithm>
#include <memory>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <functional>
#include <stdexcept>
#include <type_traits>
#include <string>
#include <queue>
#include <numeric>
#include <chrono>
#include <utility>
#include <cmath>
#include <cstring>
#include <cstdint>

using namespace std;

// ============================================================
// 文件作用域定义（类、模板、函数）
// ============================================================

// ---- 第1题：RAII ----
class DynamicArray {
private:
    int* data;
    size_t size;
    size_t capacity;

public:
    // 构造函数：获取资源
    DynamicArray(size_t cap = 10) : size(0), capacity(cap) {
        data = new int[capacity];
        cout << "  [构造] 分配 " << capacity << " 个int的空间" << endl;
    }

    // 析构函数：释放资源（RAII核心）
    ~DynamicArray() {
        delete[] data;
        cout << "  [析构] 释放空间, size=" << size << endl;
    }

    // 拷贝构造：深拷贝
    DynamicArray(const DynamicArray& other)
        : size(other.size), capacity(other.capacity) {
        data = new int[capacity];
        copy(other.data, other.data + size, data);
        cout << "  [拷贝构造] 深拷贝 " << size << " 个元素" << endl;
    }

    // 拷贝赋值：深拷贝 + 自赋值检查
    DynamicArray& operator=(const DynamicArray& other) {
        if (this != &other) {
            delete[] data;
            size = other.size;
            capacity = other.capacity;
            data = new int[capacity];
            copy(other.data, other.data + size, data);
            cout << "  [拷贝赋值] 深拷贝 " << size << " 个元素" << endl;
        }
        return *this;
    }

    // 移动构造：窃取资源（不分配新内存）
    DynamicArray(DynamicArray&& other) noexcept
        : data(other.data), size(other.size), capacity(other.capacity) {
        other.data = nullptr;
        other.size = 0;
        other.capacity = 0;
        cout << "  [移动构造] 窃取资源" << endl;
    }

    // 移动赋值：窃取资源
    DynamicArray& operator=(DynamicArray&& other) noexcept {
        if (this != &other) {
            delete[] data;
            data = other.data;
            size = other.size;
            capacity = other.capacity;
            other.data = nullptr;
            other.size = 0;
            other.capacity = 0;
            cout << "  [移动赋值] 窃取资源" << endl;
        }
        return *this;
    }

    void push(int val) {
        if (size >= capacity) {
            capacity *= 2;
            int* newData = new int[capacity];
            copy(data, data + size, newData);
            delete[] data;
            data = newData;
        }
        data[size++] = val;
    }

    int& operator[](size_t idx) { return data[idx]; }
    const int& operator[](size_t idx) const { return data[idx]; }
    size_t getSize() const { return size; }
};

// ---- 第3题：模板编程 ----

// 函数模板：最大值
template<typename T>
T maxValue(const T& a, const T& b) {
    return (a > b) ? a : b;
}

// 变参模板：递归终止
void printAll() {
    cout << endl;
}

// 变参模板：递归展开参数包
template<typename T, typename... Args>
void printAll(T first, Args... rest) {
    cout << first;
    if constexpr (sizeof...(rest) > 0) {
        cout << ", ";
        printAll(rest...);
    } else {
        cout << endl;
    }
}

// 类模板：通用栈
template<typename T>
class Stack {
private:
    vector<T> data;
public:
    void push(const T& val) { data.push_back(val); }
    void push(T&& val) { data.push_back(move(val)); }

    T pop() {
        if (data.empty()) throw out_of_range("栈为空");
        T val = move(data.back());
        data.pop_back();
        return val;
    }

    const T& top() const {
        if (data.empty()) throw out_of_range("栈为空");
        return data.back();
    }

    bool empty() const { return data.empty(); }
    size_t size() const { return data.size(); }
};

// ---- 第5题：移动语义 ----

// 可移动的字符串类
class MyString {
private:
    char* data;
    size_t len;
public:
    MyString(const char* s = "") {
        len = strlen(s);
        data = new char[len + 1];
        strcpy(data, s);
    }

    ~MyString() { delete[] data; }

    // 拷贝构造（深拷贝）
    MyString(const MyString& other) : len(other.len) {
        data = new char[len + 1];
        strcpy(data, other.data);
    }

    // 移动构造（窃取资源）
    MyString(MyString&& other) noexcept : data(other.data), len(other.len) {
        other.data = nullptr;
        other.len = 0;
    }

    // 拷贝赋值
    MyString& operator=(const MyString& other) {
        if (this != &other) {
            delete[] data;
            len = other.len;
            data = new char[len + 1];
            strcpy(data, other.data);
        }
        return *this;
    }

    // 移动赋值
    MyString& operator=(MyString&& other) noexcept {
        if (this != &other) {
            delete[] data;
            data = other.data;
            len = other.len;
            other.data = nullptr;
            other.len = 0;
        }
        return *this;
    }

    const char* c_str() const { return data ? data : ""; }
    size_t length() const { return len; }

    friend ostream& operator<<(ostream& os, const MyString& s) {
        os << (s.data ? s.data : "");
        return os;
    }
};

// 完美转发所需的函数重载
void processValue(MyString& s) {
    cout << "  [左值引用] 处理: " << s << endl;
}

void processValue(MyString&& s) {
    cout << "  [右值引用] 处理（可移动）: " << s << endl;
}

// 完美转发模板
template<typename T>
void relay(T&& arg) {
    processValue(forward<T>(arg));
}

// ---- 第6题：函数对象 ----
class Multiplier {
private:
    int factor;
public:
    Multiplier(int f) : factor(f) {}
    int operator()(int x) const { return x * factor; }
};

// ---- 第8题：运算符重载 ----
class Complex {
private:
    double real, imag;
public:
    Complex(double r = 0, double i = 0) : real(r), imag(i) {}

    // 加法（成员函数重载）
    Complex operator+(const Complex& other) const {
        return Complex(real + other.real, imag + other.imag);
    }

    // 减法
    Complex operator-(const Complex& other) const {
        return Complex(real - other.real, imag - other.imag);
    }

    // 乘法
    Complex operator*(const Complex& other) const {
        return Complex(
            real * other.real - imag * other.imag,
            real * other.imag + imag * other.real
        );
    }

    // 相等比较
    bool operator==(const Complex& other) const {
        return real == other.real && imag == other.imag;
    }

    // 类型转换运算符：转换为double（取模）
    operator double() const {
        return sqrt(real * real + imag * imag);
    }

    // 下标运算符
    double& operator[](int idx) {
        return idx == 0 ? real : imag;
    }

    // 友元：输出流重载
    friend ostream& operator<<(ostream& os, const Complex& c) {
        os << c.real;
        if (c.imag >= 0) os << "+";
        os << c.imag << "i";
        return os;
    }
};

// ---- 第9题：异常处理 ----

// 自定义异常基类
class MathError : public exception {
protected:
    string msg;
public:
    MathError(const string& m) : msg(m) {}
    const char* what() const noexcept override { return msg.c_str(); }
};

// 派生异常：除零
class DivisionByZero : public MathError {
public:
    DivisionByZero() : MathError("错误：除数不能为零") {}
};

// 派生异常：负数开方
class NegativeSqrt : public MathError {
public:
    NegativeSqrt() : MathError("错误：不能对负数开平方") {}
};

// 安全除法
double safeDivide(double a, double b) {
    if (b == 0) throw DivisionByZero();
    return a / b;
}

// ---- 第10题：元编程与constexpr ----

// constexpr编译期计算
constexpr int factorial(int n) {
    return (n <= 1) ? 1 : n * factorial(n - 1);
}

// 编译期断言
static_assert(factorial(5) == 120, "5的阶乘应为120");

// 编译期斐波那契
constexpr int fibonacci(int n) {
    if (n <= 0) return 0;
    if (n == 1) return 1;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

static_assert(fibonacci(10) == 55, "fib(10)应为55");

// ============================================================
// 练习函数
// ============================================================

// ===== 第1题：RAII与资源管理 =====
// 知识点：
// RAII（Resource Acquisition Is Initialization）是C++最核心的资源管理思想。
// 资源获取在构造函数中完成，释放在析构函数中完成，利用栈对象的生命周期
// 自动管理资源。遵循"Rule of Five"：自定义析构函数时，通常也需要自定义
// 拷贝构造、拷贝赋值、移动构造、移动赋值。
void exercise1() {
    cout << "===== 第1题：RAII与资源管理 =====" << endl;

    DynamicArray arr1;
    for (int i = 1; i <= 5; i++) arr1.push(i * 10);

    cout << "  arr1内容: ";
    for (size_t i = 0; i < arr1.getSize(); i++) cout << arr1[i] << " ";
    cout << endl;

    DynamicArray arr2 = arr1;           // 拷贝构造（深拷贝）
    DynamicArray arr3 = move(arr1);     // 移动构造（窃取资源）

    cout << "  arr2[0] = " << arr2[0] << ", arr3[2] = " << arr3[2] << endl;
    cout << "  arr1.size = " << arr1.getSize() << " (移动后应为0)" << endl;

    // 修改arr2不影响arr3（深拷贝的独立性）
    arr2[0] = 999;
    cout << "  修改arr2后: arr2[0]=" << arr2[0] << ", arr3[0]=" << arr3[0] << endl;

    // 思考题：如果忘记写移动构造函数，move(arr1)会调用什么？
    // 提示：没有移动构造时，编译器退而使用拷贝构造，无法窃取资源。
    cout << endl;
}

// ===== 第2题：STL容器与算法 =====
// 知识点：
// STL（Standard Template Library）是C++标准库的核心，包含容器、算法、迭代器。
// vector是动态数组，map基于红黑树（有序O(logn)），unordered_map基于哈希表（O(1)）。
// algorithm头文件提供sort/find/count/accumulate等通用算法，配合迭代器使用。
void exercise2() {
    cout << "===== 第2题：STL容器与算法 =====" << endl;

    // 1. vector + algorithm
    cout << "--- 1. vector与算法 ---" << endl;
    vector<int> vec = {5, 2, 8, 1, 9, 3, 7, 4, 6, 0};
    sort(vec.begin(), vec.end());
    cout << "  排序后: ";
    for (int v : vec) cout << v << " ";
    cout << endl;

    auto it = find(vec.begin(), vec.end(), 7);
    cout << "  find(7): " << (it != vec.end() ? "找到" : "未找到") << endl;

    int sum = accumulate(vec.begin(), vec.end(), 0);
    cout << "  累加和: " << sum << endl;

    // 2. map（有序，基于红黑树）
    cout << "--- 2. map（有序映射）---" << endl;
    map<string, int> scores;
    scores["Alice"] = 95;
    scores["Bob"] = 87;
    scores["Charlie"] = 92;
    scores["David"] = 88;

    for (const auto& [name, score] : scores) {  // C++17结构化绑定
        cout << "  " << name << ": " << score << endl;
    }
    cout << "  (map按键自动排序)" << endl;

    // 3. unordered_map（哈希表）
    cout << "--- 3. unordered_map（哈希表）---" << endl;
    unordered_map<string, int> cache;
    cache["one"] = 1;
    cache["two"] = 2;
    cache["three"] = 3;
    cout << "  bucket_count = " << cache.bucket_count() << endl;
    cout << "  load_factor = " << cache.load_factor() << endl;
    cout << "  (unordered_map平均O(1)，map为O(log n))" << endl;

    // 4. algorithm进阶
    cout << "--- 4. algorithm进阶 ---" << endl;
    vector<int> data = {3, 1, 4, 1, 5, 9, 2, 6, 5, 3};

    auto minIt = min_element(data.begin(), data.end());
    auto maxIt = max_element(data.begin(), data.end());
    cout << "  最小值: " << *minIt << ", 最大值: " << *maxIt << endl;
    cout << "  值为5的个数: " << count(data.begin(), data.end(), 5) << endl;

    // 擦除-移除惯用法（Erase-Remove Idiom）
    auto last = remove_if(data.begin(), data.end(), [](int n) { return n < 3; });
    data.erase(last, data.end());
    cout << "  移除<3后: ";
    for (int v : data) cout << v << " ";
    cout << endl;

    // unique去重（需先排序）
    sort(data.begin(), data.end());
    auto ulast = unique(data.begin(), data.end());
    data.erase(ulast, data.end());
    cout << "  去重后: ";
    for (int v : data) cout << v << " ";
    cout << endl;

    // 思考题：为什么remove_if不真正删除元素，而是返回新结尾迭代器？
    // 提示：STL算法不修改容器大小，只移动元素，删除需配合erase。
    cout << endl;
}

// ===== 第3题：模板编程 =====
// 知识点：
// 模板是C++泛型编程的基础，允许编写与类型无关的代码。
// 函数模板根据参数类型自动推导，类模板需显式指定或推导。
// 变参模板（Variadic Template）使用参数包（...）接受任意数量参数，
// 通过递归展开或折叠表达式处理。
void exercise3() {
    cout << "===== 第3题：模板编程 =====" << endl;

    // 1. 函数模板
    cout << "--- 1. 函数模板 ---" << endl;
    cout << "  max(3, 7) = " << maxValue(3, 7) << endl;
    cout << "  max(3.14, 2.72) = " << maxValue(3.14, 2.72) << endl;
    cout << "  max(\"hello\", \"world\") = " << maxValue(string("hello"), string("world")) << endl;

    // 2. 类模板
    cout << "--- 2. 类模板（栈）---" << endl;
    Stack<int> intStack;
    intStack.push(10);
    intStack.push(20);
    intStack.push(30);
    cout << "  栈顶: " << intStack.top() << endl;
    cout << "  弹出: " << intStack.pop() << endl;
    cout << "  弹出: " << intStack.pop() << endl;
    cout << "  剩余大小: " << intStack.size() << endl;

    Stack<string> strStack;
    strStack.push("Hello");
    strStack.push("World");
    cout << "  字符串栈顶: " << strStack.top() << endl;

    // 3. 变参模板
    cout << "--- 3. 变参模板 ---" << endl;
    cout << "  printAll: ";
    printAll(1, 2.5, "hello", 'A');
    cout << "  printAll: ";
    printAll("单个参数");
    cout << "  printAll: ";
    printAll(1, 2, 3, 4, 5);

    // 思考题：sizeof...(args)在编译期还是运行期求值？
    // 提示：编译期。sizeof...是编译期运算符，返回参数包中的类型数量。
    cout << endl;
}

// ===== 第4题：智能指针 =====
// 知识点：
// 智能指针是RAII在动态内存管理上的应用，自动释放内存避免泄漏。
// unique_ptr：独占所有权，不可拷贝，只能移动（零开销抽象）。
// shared_ptr：共享所有权，通过引用计数管理，最后一个引用销毁时释放。
// weak_ptr：弱引用，不增加引用计数，用于打破shared_ptr循环引用。
void exercise4() {
    cout << "===== 第4题：智能指针 =====" << endl;

    // 1. unique_ptr：独占所有权
    cout << "--- 1. unique_ptr（独占所有权）---" << endl;
    unique_ptr<int> up1 = make_unique<int>(42);
    cout << "  up1 = " << *up1 << endl;
    // unique_ptr<int> up2 = up1;  // 错误：不能拷贝
    unique_ptr<int> up2 = move(up1);  // 只能移动转移所有权
    cout << "  移动后 up2 = " << *up2 << endl;
    cout << "  移动后 up1 = " << (up1 ? "有效" : "空") << endl;

    // 2. shared_ptr：共享所有权
    cout << "--- 2. shared_ptr（共享所有权）---" << endl;
    auto sp1 = make_shared<int>(100);
    auto sp2 = sp1;  // 引用计数+1
    auto sp3 = sp1;  // 引用计数+1
    cout << "  *sp1 = " << *sp1 << ", 引用计数 = " << sp1.use_count() << endl;
    sp3.reset();  // 引用计数-1
    cout << "  reset sp3后, 引用计数 = " << sp1.use_count() << endl;

    // 3. weak_ptr：弱引用，不增加引用计数
    cout << "--- 3. weak_ptr（弱引用）---" << endl;
    auto shared = make_shared<int>(999);
    weak_ptr<int> weak = shared;  // 不增加引用计数
    cout << "  shared引用计数 = " << shared.use_count() << " (weak不影响计数)" << endl;

    // 使用前需要lock()提升为shared_ptr
    if (auto locked = weak.lock()) {
        cout << "  weak.lock()成功: " << *locked << endl;
    }

    shared.reset();  // 释放对象
    cout << "  shared.reset()后, weak.expired() = " << boolalpha << weak.expired() << endl;

    // 4. 自定义删除器
    cout << "--- 4. 自定义删除器 ---" << endl;
    int* rawArray = new int[5]{1, 2, 3, 4, 5};
    shared_ptr<int> arrayPtr(rawArray, [](int* p) {
        delete[] p;
        cout << "  [自定义删除器] 数组已释放" << endl;
    });
    cout << "  数组元素: ";
    for (int i = 0; i < 5; i++) cout << arrayPtr.get()[i] << " ";
    cout << endl;

    // 5. unique_ptr管理数组
    cout << "--- 5. unique_ptr管理动态数组 ---" << endl;
    auto arrPtr = make_unique<int[]>(5);
    for (int i = 0; i < 5; i++) arrPtr[i] = i * i;
    cout << "  平方数组: ";
    for (int i = 0; i < 5; i++) cout << arrPtr[i] << " ";
    cout << endl;

    // 思考题：shared_ptr的引用计数是线程安全的吗？它指向的对象呢？
    // 提示：引用计数操作是原子的（线程安全），但对象的读写需要额外同步。
    cout << endl;
}

// ===== 第5题：移动语义 =====
// 知识点：
// 移动语义允许转移资源所有权而非拷贝，避免不必要的深拷贝。
// 右值引用（T&&）绑定到右值（临时对象），std::move将左值转为右值引用。
// 完美转发（Perfect Forwarding）使用通用引用（T&&）和std::forward<T>，
// 保持参数的左右值属性，使包装函数能正确调用对应的重载。
void exercise5() {
    cout << "===== 第5题：移动语义 =====" << endl;

    // 1. 左值与右值
    cout << "--- 1. 左值与右值 ---" << endl;
    int x = 10;       // x是左值（有名字、可取地址）
    int& lref = x;    // 左值引用
    int&& rref = 42;  // 右值引用（绑定到右值）
    cout << "  左值 x = " << x << endl;
    cout << "  右值引用 rref = " << rref << endl;

    // 2. std::move：将左值转为右值引用
    cout << "--- 2. std::move ---" << endl;
    MyString s1("Hello, C++");
    cout << "  移动前: s1 = \"" << s1 << "\", len=" << s1.length() << endl;
    MyString s2 = move(s1);  // 移动构造
    cout << "  移动后: s2 = \"" << s2 << "\", len=" << s2.length() << endl;
    cout << "  移动后: s1 = \"" << s1 << "\", len=" << s1.length() << " (已被掏空)" << endl;

    // 3. 移动赋值
    cout << "--- 3. 移动赋值 ---" << endl;
    MyString s3("World");
    cout << "  赋值前: s3 = \"" << s3 << "\"" << endl;
    s3 = MyString("Moved World");  // 移动赋值
    cout << "  赋值后: s3 = \"" << s3 << "\"" << endl;

    // 4. 完美转发
    cout << "--- 4. 完美转发 ---" << endl;
    MyString lv("左值字符串");
    relay(lv);                     // 传递左值 → 调用左值版本
    relay(MyString("右值字符串"));  // 传递右值 → 调用右值版本

    // 思考题：为什么移动构造函数要标记为noexcept？
    // 提示：vector扩容时，若移动构造非noexcept，会退用拷贝构造保证异常安全。
    cout << endl;
}

// ===== 第6题：Lambda表达式与函数对象 =====
// 知识点：
// Lambda是C++11引入的匿名函数，语法：[捕获](参数) -> 返回类型 { 函数体 }
// 捕获方式：[]不捕获、[=]值捕获所有、[&]引用捕获所有、[x]值捕获x、[&x]引用捕获x
// 函数对象（Functor）是重载operator()的类，Lambda本质是编译器生成的函数对象。
// std::function可存储任意可调用对象，实现类型擦除。
void exercise6() {
    cout << "===== 第6题：Lambda表达式与函数对象 =====" << endl;

    vector<int> nums = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};

    // 1. 基本Lambda
    cout << "--- 1. 基本Lambda ---" << endl;
    auto isEven = [](int n) { return n % 2 == 0; };
    cout << "  偶数个数: " << count_if(nums.begin(), nums.end(), isEven) << endl;

    // 2. 各种捕获方式
    cout << "--- 2. 各种捕获方式 ---" << endl;
    int threshold = 5;

    // 值捕获
    auto above1 = [threshold](int n) { return n > threshold; };
    // 引用捕获
    int sum = 0;
    auto accumulate_ref = [&sum](int n) { sum += n; };

    for_each(nums.begin(), nums.end(), accumulate_ref);
    cout << "  总和(引用捕获): " << sum << endl;
    cout << "  大于" << threshold << "的个数: "
         << count_if(nums.begin(), nums.end(), above1) << endl;

    // 3. Lambda与STL算法配合
    cout << "--- 3. Lambda与STL算法 ---" << endl;
    vector<int> sortedNums = nums;
    sort(sortedNums.begin(), sortedNums.end(), [](int a, int b) {
        return a > b;  // 降序
    });
    cout << "  降序排序: ";
    for (int n : sortedNums) cout << n << " ";
    cout << endl;

    // transform：每个元素乘以2
    vector<int> doubled(nums.size());
    transform(nums.begin(), nums.end(), doubled.begin(), [](int n) { return n * 2; });
    cout << "  翻倍: ";
    for (int n : doubled) cout << n << " ";
    cout << endl;

    // 4. 函数对象（仿函数）
    cout << "--- 4. 函数对象（仿函数）---" << endl;
    Multiplier mul3(3);
    vector<int> tripled(nums.size());
    transform(nums.begin(), nums.end(), tripled.begin(), mul3);
    cout << "  三倍(仿函数): ";
    for (int n : tripled) cout << n << " ";
    cout << endl;

    // 5. std::function存储Lambda
    cout << "--- 5. std::function ---" << endl;
    function<int(int)> operations[] = {
        [](int x) { return x + 10; },
        [](int x) { return x * x; },
        [](int x) { return x - 1; }
    };
    const char* names[] = {"+10", "平方", "-1"};
    for (int i = 0; i < 3; i++) {
        cout << "  操作" << names[i] << "(5) = " << operations[i](5) << endl;
    }

    // 思考题：[=]捕获的变量在Lambda创建后修改，Lambda内用的是新值还是旧值？
    // 提示：值捕获在Lambda创建时拷贝，之后修改原变量不影响Lambda内的副本。
    cout << endl;
}

// ===== 第7题：多线程编程 =====
// 知识点：
// C++11引入了标准线程库：<thread>创建线程，<mutex>保护共享数据，
// <condition_variable>实现线程间等待/通知，<atomic>提供无锁原子操作。
// 生产者-消费者模式：生产者加锁放入数据并notify，消费者wait并加锁取出数据。
void exercise7() {
    cout << "===== 第7题：多线程编程 =====" << endl;

    // 1. 生产者-消费者模式
    cout << "--- 1. 生产者-消费者（mutex + condition_variable）---" << endl;
    queue<int> buffer;
    mutex mtx;
    condition_variable cv;
    bool productionDone = false;

    auto producer = [&]() {
        for (int i = 1; i <= 5; i++) {
            {
                lock_guard<mutex> lock(mtx);
                buffer.push(i);
                cout << "  [生产者] 放入: " << i << endl;
            }
            cv.notify_one();  // 通知消费者
            this_thread::sleep_for(chrono::milliseconds(50));
        }
        {
            lock_guard<mutex> lock(mtx);
            productionDone = true;
        }
        cv.notify_one();  // 通知消费者结束
    };

    auto consumer = [&]() {
        while (true) {
            unique_lock<mutex> lock(mtx);
            cv.wait(lock, [&] { return !buffer.empty() || productionDone; });
            if (buffer.empty() && productionDone) break;
            int val = buffer.front();
            buffer.pop();
            cout << "  [消费者] 取出: " << val << endl;
        }
    };

    thread prodThread(producer);
    thread consThread(consumer);
    prodThread.join();
    consThread.join();

    // 2. atomic原子操作
    cout << "--- 2. atomic原子计数器 ---" << endl;
    atomic<int> counter{0};
    vector<thread> threads;
    for (int i = 0; i < 4; i++) {
        threads.emplace_back([&counter]() {
            for (int j = 0; j < 1000; j++) {
                counter.fetch_add(1, memory_order_relaxed);
            }
        });
    }
    for (auto& t : threads) t.join();
    cout << "  4线程各加1000, 结果 = " << counter.load() << " (应为4000)" << endl;

    // 3. lock_guard vs unique_lock
    cout << "--- 3. lock_guard vs unique_lock ---" << endl;
    mutex m;
    {
        lock_guard<mutex> lg(m);  // 构造时加锁，析构时解锁（简单场景）
        cout << "  lock_guard: 自动加锁/解锁" << endl;
    }
    {
        unique_lock<mutex> ul(m);  // 可手动解锁/重新加锁（配合condition_variable）
        cout << "  unique_lock: 灵活控制" << endl;
        ul.unlock();  // 手动解锁
        cout << "  unique_lock: 手动解锁后" << endl;
    }

    // 思考题：如果cv.wait不加谓词（谓词版lambda），可能发生什么问题？
    // 提示：虚假唤醒（spurious wakeup）可能导致消费者在没有数据时被唤醒。
    cout << endl;
}

// ===== 第8题：运算符重载与类型转换 =====
// 知识点：
// 运算符重载让自定义类型支持类似内置类型的运算语法。
// 成员函数重载：左操作数是对象本身（如a+b等价于a.operator+(b)）。
// 友元函数重载：左操作数可以是任意类型（如cout<<a需要ostream在左）。
// 类型转换运算符（operator T()）允许隐式/显式类型转换。
// 注意：不要滥用运算符重载，语义应与内置运算符一致。
void exercise8() {
    cout << "===== 第8题：运算符重载与类型转换 =====" << endl;

    Complex a(3, 4), b(1, 2);

    // 1. 算术运算符
    cout << "--- 1. 算术运算符 ---" << endl;
    cout << "  a = " << a << ", b = " << b << endl;
    cout << "  a + b = " << (a + b) << endl;
    cout << "  a - b = " << (a - b) << endl;
    cout << "  a * b = " << (a * b) << endl;

    // 2. 比较运算符
    cout << "--- 2. 比较运算符 ---" << endl;
    Complex c(3, 4);
    cout << "  a == c: " << boolalpha << (a == c) << endl;
    cout << "  a == b: " << (a == b) << endl;

    // 3. 类型转换运算符
    cout << "--- 3. 类型转换 ---" << endl;
    double modulus = a;  // 隐式调用 operator double()
    cout << "  |a| = " << modulus << " (隐式转换)" << endl;
    cout << "  (double)b = " << (double)b << " (显式转换)" << endl;

    // 4. 下标运算符
    cout << "--- 4. 下标运算符 ---" << endl;
    cout << "  a[0] = " << a[0] << " (实部)" << endl;
    cout << "  a[1] = " << a[1] << " (虚部)" << endl;

    // 5. 链式运算
    cout << "--- 5. 链式运算 ---" << endl;
    Complex result = a + b + c;
    cout << "  a + b + c = " << result << endl;

    // 思考题：为什么输出流运算符<<通常重载为友元函数而不是成员函数？
    // 提示：作为成员函数时左操作数必须是Complex，而我们需要ostream在左。
    cout << endl;
}

// ===== 第9题：异常处理 =====
// 知识点：
// C++异常通过try/catch/throw机制处理运行时错误。
// 自定义异常应继承std::exception并重写what()方法。
// 异常捕获顺序：从派生类到基类（先catch子类再catch父类）。
// RAII保证异常发生时资源自动释放（析构函数总会被调用），
// 这是C++异常安全的核心机制。noexcept声明函数不抛出异常。
void exercise9() {
    cout << "===== 第9题：异常处理 =====" << endl;

    // 1. 基本try/catch
    cout << "--- 1. 基本异常捕获 ---" << endl;
    try {
        throw runtime_error("这是一个运行时错误");
    } catch (const exception& e) {
        cout << "  捕获异常: " << e.what() << endl;
    }

    // 2. 自定义异常
    cout << "--- 2. 自定义异常 ---" << endl;
    try {
        cout << "  计算 10 / 0..." << endl;
        safeDivide(10, 0);
    } catch (const DivisionByZero& e) {
        cout << "  捕获: " << e.what() << endl;
    }

    // 3. RAII异常安全
    cout << "--- 3. RAII异常安全 ---" << endl;
    mutex mtx;
    try {
        lock_guard<mutex> guard(mtx);  // RAII：构造时加锁
        cout << "  临界区内操作..." << endl;
        throw runtime_error("临界区内抛出异常！");
        // 即使抛出异常，guard析构时也会自动解锁
    } catch (const exception& e) {
        cout << "  捕获: " << e.what() << endl;
        cout << "  锁已通过RAII自动释放" << endl;
    }

    // 4. 异常捕获顺序（从派生到基类）
    cout << "--- 4. 异常捕获顺序（从派生到基类）---" << endl;
    try {
        throw NegativeSqrt();
    } catch (const DivisionByZero& e) {
        cout << "  捕获 DivisionByZero: " << e.what() << endl;
    } catch (const MathError& e) {
        cout << "  捕获 MathError: " << e.what() << endl;
    } catch (const exception& e) {
        cout << "  捕获 exception: " << e.what() << endl;
    }

    // 5. 异常嵌套与rethrow
    cout << "--- 5. 异常嵌套与rethrow ---" << endl;
    try {
        try {
            throw MathError("内层异常");
        } catch (const MathError& e) {
            cout << "  内层捕获: " << e.what() << endl;
            throw;  // 重新抛出
        }
    } catch (const exception& e) {
        cout << "  外层捕获: " << e.what() << endl;
    }

    // 思考题：在构造函数中抛出异常，析构函数会被调用吗？
    // 提示：构造函数抛出异常时，对象析构函数不会被调用，
    //       但已构造完成的成员和基类的析构函数会被调用。
    cout << endl;
}

// ===== 第10题：元编程与constexpr =====
// 知识点：
// constexpr允许在编译期进行计算，将运行时开销转移到编译期。
// constexpr函数既可在编译期也可在运行期调用（取决于参数是否为常量表达式）。
// type_traits提供编译期类型查询（is_integral、is_pointer等）。
// if constexpr（C++17）在编译期选择分支，未选中的分支不会被实例化。
// static_assert在编译期进行断言检查，提前发现错误。
void exercise10() {
    cout << "===== 第10题：元编程与constexpr =====" << endl;

    // 1. constexpr函数
    cout << "--- 1. constexpr编译期计算 ---" << endl;
    constexpr int f5 = factorial(5);
    cout << "  5! = " << f5 << " (编译期计算)" << endl;
    cout << "  fib(10) = " << fibonacci(10) << endl;

    // 运行期也可以调用constexpr函数
    int n = 7;
    cout << "  7! = " << factorial(n) << " (运行期调用，参数非常量)" << endl;

    // 2. 编译期常量表达式
    cout << "--- 2. 编译期常量 ---" << endl;
    constexpr int sum = factorial(3) + factorial(4);  // 6 + 24 = 30
    static_assert(sum == 30, "3!+4!应为30");
    cout << "  3! + 4! = " << sum << " (编译期验证通过)" << endl;

    // 3. type_traits类型特征
    cout << "--- 3. type_traits类型特征 ---" << endl;
    cout << "  is_integral<int> = " << boolalpha << is_integral_v<int> << endl;
    cout << "  is_integral<double> = " << is_integral_v<double> << endl;
    cout << "  is_floating_point<float> = " << is_floating_point_v<float> << endl;
    cout << "  is_pointer<int*> = " << is_pointer_v<int*> << endl;
    cout << "  is_same<int, int32_t> = " << is_same_v<int, int32_t> << endl;

    // 4. if constexpr（编译期分支）
    cout << "--- 4. if constexpr（编译期分支）---" << endl;
    auto processValue = [](auto val) {
        if constexpr (is_integral_v<decltype(val)>) {
            cout << "  整数: " << val << " (平方=" << val * val << ")" << endl;
        } else if constexpr (is_floating_point_v<decltype(val)>) {
            cout << "  浮点: " << val << " (取整=" << (int)val << ")" << endl;
        } else {
            cout << "  其他类型: " << val << endl;
        }
    };
    processValue(42);
    processValue(3.14);
    processValue("hello");

    // 5. conditional类型选择
    cout << "--- 5. conditional类型选择 ---" << endl;
    using LargeInt = conditional_t<sizeof(void*) == 8, int64_t, int32_t>;
    cout << "  指针大小=" << sizeof(void*) << "字节, 选择类型大小=" << sizeof(LargeInt) << "字节" << endl;
    cout << "  (根据指针大小在编译期选择int64_t或int32_t)" << endl;

    // 6. enable_if（SFINAE）
    cout << "--- 6. enable_if条件启用 ---" << endl;
    cout << "  (enable_if通过SFINAE在编译期选择函数重载)" << endl;
    cout << "  (例如：仅对整数类型启用某个模板函数)" << endl;

    // 思考题：constexpr函数和const函数有什么区别？
    // 提示：const修饰运行期行为（不修改对象），constexpr修饰编译期行为（可编译期求值）。
    cout << endl;
}

// ============================================================
// 主函数
// ============================================================
int main() {
    cout << "========================================" << endl;
    cout << "  C++ 进阶编程练习 - 10题" << endl;
    cout << "  创建日期：2026-08-05" << endl;
    cout << "========================================" << endl;
    cout << endl;

    exercise1();
    exercise2();
    exercise3();
    exercise4();
    exercise5();
    exercise6();
    exercise7();
    exercise8();
    exercise9();
    exercise10();

    cout << "========================================" << endl;
    cout << "  全部练习完成！" << endl;
    cout << "========================================" << endl;

    return 0;
}
