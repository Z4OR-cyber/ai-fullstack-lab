/*
 * Q05: 预处理器与编译流程
 * 知识点: #define/#include、宏函数、gcc四阶段
 */
#include <stdio.h>
#include <math.h>

/* 1. 对象式宏 */
#define PI          3.14159265358979
#define MAX_BUF     256
#define APP_NAME    "CLearn"
#define VERSION     "1.0"

/* 2. 函数式宏 */
#define SQUARE(x)       ((x) * (x))
#define MAX(a, b)       ((a) > (b) ? (a) : (b))
#define MIN(a, b)       ((a) < (b) ? (a) : (b))
#define ABS(x)          ((x) < 0 ? -(x) : (x))

/* 3. 多行宏 */
#define PRINT_ARR(arr, n) do { \
    printf("  ["); \
    for (int _i = 0; _i < (n); _i++) \
        printf("%s%d", (_i > 0 ? ", " : ""), (arr)[_i]); \
    printf("]\n"); \
} while (0)

/* 4. 条件编译 */
#define DEBUG 1

/* 5. 字符串化与拼接 */
#define STR(x)      #x
#define XSTR(x)     STR(x)
#define CONCAT(a,b) a##b

/* 6. 可变参数宏 */
#define LOG(fmt, ...) printf("  [LOG] " fmt "\n", ##__VA_ARGS__)

int main(void)
{
    printf("========================================\n");
    printf("  Q05: 预处理器与编译流程\n");
    printf("========================================\n\n");

    /* 1. 对象式宏 */
    printf("--- 1. 对象式宏 ---\n");
    printf("  %s v%s\n", APP_NAME, VERSION);
    printf("  PI = %.14f\n", PI);
    printf("  MAX_BUF = %d\n\n", MAX_BUF);

    /* 2. 函数式宏 */
    printf("--- 2. 函数式宏 ---\n");
    printf("  SQUARE(5) = %d\n", SQUARE(5));
    printf("  SQUARE(3.5) = %.2f\n", SQUARE(3.5));
    printf("  MAX(10, 20) = %d\n", MAX(10, 20));
    printf("  MIN(10, 20) = %d\n", MIN(10, 20));
    printf("  ABS(-42) = %d\n", ABS(-42));
    printf("  ABS(42) = %d\n\n", ABS(42));

    /* 3. 多行宏 */
    printf("--- 3. 多行宏 PRINT_ARR ---\n");
    int arr[] = {1, 2, 3, 4, 5};
    PRINT_ARR(arr, 5);
    printf("\n");

    /* 4. 条件编译 */
    printf("--- 4. 条件编译 ---\n");
#if DEBUG
    printf("  DEBUG 模式开启 (DEBUG=%d)\n", DEBUG);
#else
    printf("  Release 模式\n");
#endif
    printf("\n");

    /* 5. 字符串化与拼接 */
    printf("--- 5. 字符串化 # 与拼接 ## ---\n");
    int CONCAT(var, 1) = 100;
    printf("  STR(1+2) = \"%s\"\n", STR(1+2));
    printf("  XSTR(PI) = \"%s\" (宏先展开再字符串化)\n", XSTR(PI));
    printf("  CONCAT(var,1) = %d\n\n", var1);

    /* 6. 可变参数宏 */
    printf("--- 6. 可变参数宏 ---\n");
    LOG("简单日志");
    LOG("带参数: x=%d, y=%.2f", 42, 3.14);
    printf("\n");

    /* 7. 预定义宏 */
    printf("--- 7. 预定义宏 ---\n");
    printf("  __FILE__ = %s\n", __FILE__);
    printf("  __LINE__ = %d\n", __LINE__);
    printf("  __DATE__ = %s\n", __DATE__);
    printf("  __TIME__ = %s\n", __TIME__);
    printf("  __STDC__ = %d\n\n", __STDC__);

    /* 8. 编译四阶段说明 */
    printf("--- 8. GCC 编译四阶段 ---\n");
    printf("  阶段1: 预处理 (gcc -E)    -> .i 文件 (展开宏、包含头文件)\n");
    printf("  阶段2: 编译   (gcc -S)    -> .s 文件 (生成汇编代码)\n");
    printf("  阶段3: 汇编   (gcc -c)    -> .o 文件 (生成目标文件)\n");
    printf("  阶段4: 链接   (gcc)       -> 可执行文件 (链接库)\n");

    printf("\n✅ Q05 通过\n");
    return 0;
}
