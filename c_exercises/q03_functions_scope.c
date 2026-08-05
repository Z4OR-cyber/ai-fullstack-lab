/*
 * Q03: 函数与作用域
 * 知识点: 参数传递(值传递)、static/auto、递归
 */
#include <stdio.h>

/* 值传递: 函数内修改不影响调用者 */
static void try_modify(int x)
{
    x = 999;
    printf("  函数内 x = %d (修改不影响调用者)\n", x);
}

/* static 局部变量: 函数调用间保持状态 */
static int counter(void)
{
    static int count = 0;   /* 只初始化一次 */
    auto int temp = 10;     /* auto 可省略, 存储在栈上 */
    count++;
    return count * temp / 10;  /* 等于 count */
}

/* 递归: 阶乘 */
static long factorial(int n)
{
    if (n <= 1) return 1;
    return (long)n * factorial(n - 1);
}

/* 递归: 斐波那契 */
static int fib(int n)
{
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}

/* 递归: 汉诺塔 */
static void hanoi(int n, char from, char to, char aux)
{
    if (n == 1) {
        printf("  移动盘 1: %c -> %c\n", from, to);
        return;
    }
    hanoi(n - 1, from, aux, to);
    printf("  移动盘 %d: %c -> %c\n", n, from, to);
    hanoi(n - 1, aux, to, from);
}

/* 全局变量 vs 局部变量 */
static int global_var = 100;   /* 全局, 存储在数据段 */

int main(void)
{
    printf("========================================\n");
    printf("  Q03: 函数与作用域\n");
    printf("========================================\n\n");

    /* 1. 值传递 */
    printf("--- 1. 值传递 ---\n");
    int val = 42;
    printf("  调用前 val = %d\n", val);
    try_modify(val);
    printf("  调用后 val = %d\n", val);

    /* 2. static 局部变量 */
    printf("\n--- 2. static 局部变量 ---\n");
    for (int i = 0; i < 5; i++) {
        printf("  第 %d 次调用 counter() = %d\n", i + 1, counter());
    }

    /* 3. 全局变量 vs 局部变量 */
    printf("\n--- 3. 全局变量 vs 局部变量 ---\n");
    int local_var = 50;   /* 局部, 存储在栈上 */
    printf("  全局变量 global_var = %d\n", global_var);
    printf("  局部变量 local_var = %d\n", local_var);
    {
        int inner = 30;   /* 块作用域 */
        printf("  块作用域 inner = %d\n", inner);
    }

    /* 4. 递归: 阶乘 */
    printf("\n--- 4. 递归: 阶乘 ---\n");
    for (int i = 0; i <= 10; i++) {
        printf("  %d! = %ld\n", i, factorial(i));
    }

    /* 5. 递归: 斐波那契 */
    printf("\n--- 5. 递归: 斐波那契 ---\n");
    printf("  ");
    for (int i = 0; i < 12; i++) {
        printf("%d ", fib(i));
    }
    printf("\n");

    /* 6. 递归: 汉诺塔 (3层) */
    printf("\n--- 6. 递归: 汉诺塔(3层) ---\n");
    hanoi(3, 'A', 'C', 'B');

    printf("\n✅ Q03 通过\n");
    return 0;
}
