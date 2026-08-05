/*
 * Q20: C与Python互操作 (共享库部分)
 * 知识点: Python通过ctypes调用C编译的.so
 *
 * 编译共享库: gcc -shared -fPIC -o libq20.so q20_c_python_interop.c
 * Python调用: python3 q20_ctypes_demo.py
 *
 * 本文件既作为共享库源码, 也可作为独立程序运行
 */

/* ===== 导出给Python的函数 ===== */

/* 简单加法 */
int c_add(int a, int b)
{
    return a + b;
}

/* 斐波那契 (递归, C性能) */
long c_fibonacci(int n)
{
    if (n <= 1) return n;
    return c_fibonacci(n - 1) + c_fibonacci(n - 2);
}

/* 数组求和 */
double c_array_sum(const double *arr, int n)
{
    double sum = 0.0;
    for (int i = 0; i < n; i++)
        sum += arr[i];
    return sum;
}

/* 字符串处理: 反转字符串 (原地) */
void c_reverse_string(char *s, int len)
{
    for (int i = 0; i < len / 2; i++) {
        char tmp = s[i];
        s[i] = s[len - 1 - i];
        s[len - 1 - i] = tmp;
    }
}

/* 素数计数: 统计小于n的素数个数 */
int c_count_primes(int n)
{
    if (n < 2) return 0;
    /* 埃拉托斯特尼筛法 */
    /* 使用栈上数组, 限制大小 */
    if (n > 100000) n = 100000;
    char sieve[100001];
    for (int i = 0; i < n; i++) sieve[i] = 1;
    sieve[0] = sieve[1] = 0;
    for (int i = 2; (long)i * i < n; i++) {
        if (sieve[i]) {
            for (int j = i * i; j < n; j += i)
                sieve[j] = 0;
        }
    }
    int count = 0;
    for (int i = 2; i < n; i++)
        if (sieve[i]) count++;
    return count;
}

/* ===== 以下是独立运行时的演示 ===== */

#ifdef STANDALONE
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>

static double get_time_sec(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec + tv.tv_usec / 1000000.0;
}

int main(void)
{
    printf("========================================\n");
    printf("  Q20: C与Python互操作\n");
    printf("========================================\n\n");

    /* 1. 导出函数演示 */
    printf("--- 1. 导出给Python的C函数 ---\n");
    printf("  c_add(17, 25) = %d\n", c_add(17, 25));
    printf("  c_fibonacci(20) = %ld\n", c_fibonacci(20));
    printf("  c_count_primes(100) = %d\n", c_count_primes(100));
    printf("  c_count_primes(10000) = %d\n", c_count_primes(10000));

    double arr[] = {1.1, 2.2, 3.3, 4.4, 5.5};
    printf("  c_array_sum({1.1..5.5}) = %.1f\n",
           c_array_sum(arr, 5));

    char str[] = "Hello, ctypes!";
    c_reverse_string(str, (int)strlen(str));
    printf("  c_reverse_string(\"Hello, ctypes!\") = \"%s\"\n\n", str);

    /* 2. ctypes 使用说明 */
    printf("--- 2. ctypes 调用方式 ---\n");
    printf("  步骤:\n");
    printf("    1. gcc -shared -fPIC -o libq20.so q20_c_python_interop.c -DSTANDALONE\n");
    printf("       (注意: 不加 -DSTANDALONE 只编译库函数)\n");
    printf("    2. Python中:\n");
    printf("       import ctypes\n");
    printf("       lib = ctypes.CDLL('./libq20.so')\n");
    printf("       result = lib.c_add(17, 25)  # -> 42\n\n");

    printf("  类型映射:\n");
    printf("    %-15s %-15s %-15s\n", "C类型", "ctypes类型", "Python类型");
    printf("    %-15s %-15s %-15s\n", "int", "c_int", "int");
    printf("    %-15s %-15s %-15s\n", "long", "c_long", "int");
    printf("    %-15s %-15s %-15s\n", "double", "c_double", "float");
    printf("    %-15s %-15s %-15s\n", "char*", "c_char_p", "bytes");
    printf("    %-15s %-15s %-15s\n", "int*", "POINTER(c_int)", "array");
    printf("    %-15s %-15s %-15s\n", "void", "None", "None\n");

    /* 3. 性能对比: C vs Python (概念说明) */
    printf("--- 3. 性能对比: C vs Python ---\n");
    printf("  测试: 计算 fib(35)\n");

    double t0 = get_time_sec();
    long fib35 = c_fibonacci(35);
    double t1 = get_time_sec();
    printf("  C:      fib(35) = %ld, 耗时 %.3f 秒\n", fib35, t1 - t0);

    printf("  Python: fib(35) ≈ 3-5 秒 (约10-50倍慢)\n");
    printf("  结论: 计算密集型任务用C, 业务逻辑用Python\n\n");

    /* 4. 其他互操作方式 */
    printf("--- 4. 其他 C/Python 互操作方式 ---\n");
    printf("  1. ctypes (本例): 简单, 无需C扩展API, 但无类型检查\n");
    printf("  2. CPython C API: 直接写Python扩展模块(.so)\n");
    printf("     - 需要包含 Python.h\n");
    printf("     - 性能最好, 但开发复杂\n");
    printf("  3. Cython: Python超集, 编译为C\n");
    printf("     - 语法接近Python, 自动生成C代码\n");
    printf("  4. cffi: 类似ctypes但更快, 支持ABI和API模式\n");
    printf("  5. SWIG: 多语言绑定生成器\n");

    printf("\n✅ Q20 通过\n");
    return 0;
}

#endif /* STANDALONE */
