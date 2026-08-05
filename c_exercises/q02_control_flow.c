/*
 * Q02: 控制流与运算符
 * 知识点: if/switch/for/while、位运算、短路求值
 */
#include <stdio.h>

/* 判断闰年 — if/else 练习 */
static int is_leap_year(int year)
{
    if ((year % 4 == 0 && year % 100 != 0) || (year % 400 == 0))
        return 1;
    return 0;
}

/* 用 switch 实现简单计算器 */
static double calc(double a, double b, char op)
{
    switch (op) {
        case '+': return a + b;
        case '-': return a - b;
        case '*': return a * b;
        case '/': return (b != 0) ? a / b : 0.0;
        default:  return 0.0;
    }
}

/* 短路求值演示: 若左边为假则右边不执行 */
static int check短路(void)
{
    int x = 0, y = 0;
    /* && 短路: x==0 为真才执行 y++ ... 这里 x!=1 为真 */
    if (x != 1 && ++y > 0) {
        printf("  &&短路: x!=1为真, y++被执行, y=%d\n", y);
    }
    /* || 短路: x==0 为真, 后面的 ++y 不执行 */
    int z = 0;
    if (x == 0 || ++z > 0) {
        printf("  ||短路: x==0为真, ++z被跳过, z=%d\n", z);
    }
    return 0;
}

int main(void)
{
    printf("========================================\n");
    printf("  Q02: 控制流与运算符\n");
    printf("========================================\n\n");

    /* 1. if/else — 闰年判断 */
    printf("--- 1. if/else: 闰年判断 ---\n");
    int years[] = {2000, 2020, 2021, 2024, 1900};
    for (int i = 0; i < 5; i++) {
        printf("  %d 年: %s\n", years[i], is_leap_year(years[i]) ? "闰年" : "平年");
    }

    /* 2. switch — 简单计算器 */
    printf("\n--- 2. switch: 简单计算器 ---\n");
    printf("  10 + 3 = %.0f\n", calc(10, 3, '+'));
    printf("  10 / 4 = %.2f\n", calc(10, 4, '/'));
    printf("  7 * 8 = %.0f\n", calc(7, 8, '*'));

    /* 3. 位运算 */
    printf("\n--- 3. 位运算 ---\n");
    unsigned int v1 = 0xF0;   /* 11110000 */
    unsigned int v2 = 0x0F;   /* 00001111 */
    printf("  0xF0 & 0x0F = 0x%02X\n", v1 & v2);
    printf("  0xF0 | 0x0F = 0x%02X\n", v1 | v2);
    printf("  0xF0 ^ 0x0F = 0x%02X (翻转)\n", v1 ^ v2);
    printf("  ~0xF0 = 0x%08X\n", ~v1);
    printf("  0x01 << 4 = 0x%02X (左移)\n", 0x01 << 4);
    printf("  0x80 >> 4 = 0x%02X (右移)\n", 0x80 >> 4);

    /* 位运算技巧: 不用临时变量交换 */
    int a = 15, b = 27;
    a ^= b; b ^= a; a ^= b;
    printf("  位运算交换后: a=%d, b=%d\n", a, b);

    /* 位运算技巧: 判断奇偶 */
    printf("  42 %% 2 -> %s\n", (42 & 1) ? "奇" : "偶");
    printf("  37 %% 2 -> %s\n", (37 & 1) ? "奇" : "偶");

    /* 4. 短路求值 */
    printf("\n--- 4. 短路求值 ---\n");
    check短路();

    /* 5. for / while / do-while */
    printf("\n--- 5. 循环结构 ---\n");
    /* for: 九九乘法表前3行 */
    printf("  九九乘法表(前3行):\n");
    for (int i = 1; i <= 3; i++) {
        printf("  ");
        for (int j = 1; j <= i; j++) {
            printf("%dx%d=%-4d", j, i, i * j);
        }
        printf("\n");
    }

    /* while: 计算2的幂直到超过100 */
    int power = 1;
    printf("  2的幂序列(<=100): ");
    while (power <= 100) {
        printf("%d ", power);
        power *= 2;
    }
    printf("\n");

    /* do-while: 至少执行一次 */
    int n = 0;
    do {
        printf("  do-while: n=%d (至少执行一次)\n", n);
        n++;
    } while (n < 1);

    printf("\n✅ Q02 通过\n");
    return 0;
}
