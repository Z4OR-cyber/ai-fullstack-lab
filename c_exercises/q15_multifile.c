/*
 * Q15: 多文件项目与Makefile
 * 知识点: 头文件分离、extern/static、静态库vs动态库
 *
 * 项目结构:
 *   math_utils.h / math_utils.c    — 数学工具
 *   string_utils.h / string_utils.c — 字符串工具
 *   q15_multifile.c                 — 主程序
 *   Makefile                        — 构建脚本
 *
 * 编译: make
 * 运行: ./q15_multifile
 */
#include <stdio.h>
#include <string.h>
#include "math_utils.h"
#include "string_utils.h"

/* extern 引用外部全局变量 (定义在 math_utils.c 中是不需要的,
   这里演示 extern 的用法, 引用一个声明在别处的变量) */
extern int math_gcd(int, int);  /* 函数声明也可以用 extern, 但通常省略 */

/* static 全局变量: 仅本文件可见 */
static int call_count = 0;

static void print_separator(const char *title)
{
    printf("\n--- %s ---\n", title);
}

int main(void)
{
    printf("========================================\n");
    printf("  Q15: 多文件项目与Makefile\n");
    printf("========================================\n\n");

    /* 1. 使用 math_utils 模块 */
    print_separator("1. math_utils 模块");
    printf("  GCD(48, 36) = %d\n", math_gcd(48, 36));
    printf("  LCM(12, 18) = %d\n", math_lcm(12, 18));

    printf("  素数检查 (1-20):\n  ");
    for (int i = 1; i <= 20; i++) {
        if (math_is_prime(i))
            printf("%d ", i);
    }
    printf("\n");

    printf("  2^10 = %ld (快速幂)\n", math_pow_long(2, 10));
    printf("  10! = %ld\n", math_factorial(10));

    call_count++;
    printf("  call_count = %d (static变量)\n", call_count);

    /* 2. 使用 string_utils 模块 */
    print_separator("2. string_utils 模块");

    char buf[64];
    strcpy(buf, "Hello, World!");
    printf("  原始: \"%s\"\n", buf);
    printf("  'l' 出现次数: %zu\n", str_count_char(buf, 'l'));

    str_reverse(buf);
    printf("  反转: \"%s\"\n", buf);
    str_reverse(buf);

    str_to_upper(buf);
    printf("  大写: \"%s\"\n", buf);
    str_to_lower(buf);
    printf("  小写: \"%s\"\n", buf);

    const char *words[] = {"level", "hello", "racecar"};
    for (int i = 0; i < 3; i++) {
        printf("  \"%s\" 回文? %s\n", words[i],
               str_is_palindrome(words[i]) ? "是" : "否");
    }

    strcpy(buf, "   Hello   ");
    printf("  trim 前: \"%s\" (len=%zu)\n", buf, strlen(buf));
    str_trim(buf);
    printf("  trim 后: \"%s\" (len=%zu)\n", buf, strlen(buf));

    /* 3. Makefile 与构建流程说明 */
    print_separator("3. Makefile 与构建流程");
    printf("  项目文件结构:\n");
    printf("    math_utils.h      (接口声明)\n");
    printf("    math_utils.c      (实现, static函数限可见性)\n");
    printf("    string_utils.h    (接口声明)\n");
    printf("    string_utils.c    (实现)\n");
    printf("    q15_multifile.c   (主程序)\n");
    printf("    Makefile          (构建脚本)\n\n");

    printf("  Makefile 关键概念:\n");
    printf("    - 目标: 依赖 命令 (Tab缩进)\n");
    printf("    - 变量: CC=gcc, CFLAGS=-Wall -g\n");
    printf("    - 自动变量: $@ (目标), $< (第一个依赖), $^ (所有依赖)\n");
    printf("    - .PHONY: 声明伪目标 (clean)\n\n");

    printf("  静态库 vs 动态库:\n");
    printf("    静态库 (.a):\n");
    printf("      ar rcs libmath.a math_utils.o\n");
    printf("      gcc main.c -L. -lmath -o prog\n");
    printf("      代码嵌入可执行文件, 独立运行, 体积大\n");
    printf("    动态库 (.so):\n");
    printf("      gcc -shared -fPIC -o libmath.so math_utils.c\n");
    printf("      gcc main.c -L. -lmath -o prog\n");
    printf("      运行时加载, 多程序共享, 需配置 LD_LIBRARY_PATH\n\n");

    printf("  extern 关键字:\n");
    printf("    - 引用在其他文件中定义的全局变量/函数\n");
    printf("    - extern int x;  声明但不定义\n");
    printf("  static 关键字:\n");
    printf("    - static全局变量/函数: 限制在当前文件可见\n");
    printf("    - static局部变量: 函数间保持状态\n");

    printf("\n✅ Q15 通过\n");
    return 0;
}
