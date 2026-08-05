/*
 * math_utils.h — 数学工具函数声明
 * 演示头文件分离、include guard
 */
#ifndef MATH_UTILS_H
#define MATH_UTILS_H

/* GCD: 最大公约数 */
int math_gcd(int a, int b);

/* LCM: 最小公倍数 */
int math_lcm(int a, int b);

/* 判断素数 */
int math_is_prime(int n);

/* 快速幂 */
long math_pow_long(long base, int exp);

/* 阶乘 */
long math_factorial(int n);

#endif /* MATH_UTILS_H */
