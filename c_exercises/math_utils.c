/*
 * math_utils.c — 数学工具函数实现
 * 演示 static 函数限制文件内可见性
 */
#include "math_utils.h"

/* static 函数: 仅本文件可见, 不导出到符号表 */
static int abs_val(int x)
{
    return x < 0 ? -x : x;
}

int math_gcd(int a, int b)
{
    a = abs_val(a);
    b = abs_val(b);
    while (b) {
        int t = b;
        b = a % b;
        a = t;
    }
    return a;
}

int math_lcm(int a, int b)
{
    if (a == 0 || b == 0) return 0;
    int g = math_gcd(a, b);
    return abs_val(a) / g * abs_val(b);
}

int math_is_prime(int n)
{
    if (n < 2) return 0;
    if (n < 4) return 1;
    if (n % 2 == 0) return 0;
    for (int i = 3; (long)i * i <= n; i += 2) {
        if (n % i == 0) return 0;
    }
    return 1;
}

long math_pow_long(long base, int exp)
{
    if (exp < 0) return 0;
    long result = 1;
    while (exp > 0) {
        if (exp & 1)
            result *= base;
        base *= base;
        exp >>= 1;
    }
    return result;
}

long math_factorial(int n)
{
    if (n < 0) return 0;
    long result = 1;
    for (int i = 2; i <= n; i++)
        result *= i;
    return result;
}
