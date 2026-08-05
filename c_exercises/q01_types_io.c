/*
 * Q01: 变量、类型与I/O
 * 知识点: 基本数据类型、printf/scanf、类型转换、sizeof
 */
#include <stdio.h>
#include <limits.h>
#include <float.h>

int main(void)
{
    printf("========================================\n");
    printf("  Q01: 变量、类型与I/O\n");
    printf("========================================\n\n");

    /* 1. 基本数据类型及 sizeof */
    printf("--- 1. 基本数据类型与 sizeof ---\n");
    char        c = 'A';
    short       s = 32767;
    int         i = 100;
    long        l = 999999L;
    float       f = 3.14f;
    double      d = 2.718281828;
    long double ld = 1.0L;

    printf("char      : %c (size=%zu, range=%d..%d)\n",
           c, sizeof(char), CHAR_MIN, CHAR_MAX);
    printf("short     : %hd (size=%zu)\n", s, sizeof(short));
    printf("int       : %d (size=%zu, range=%d..%d)\n", i, sizeof(int), INT_MIN, INT_MAX);
    printf("long      : %ld (size=%zu)\n", l, sizeof(long));
    printf("float     : %.2f (size=%zu, precision=%d digits)\n", f, sizeof(float), FLT_DIG);
    printf("double    : %.9f (size=%zu, precision=%d digits)\n", d, sizeof(double), DBL_DIG);
    printf("long double: %.2Lf (size=%zu)\n", ld, sizeof(long double));
    printf("unsigned   : size=%zu\n\n", sizeof(unsigned));

    /* 2. 隐式与显式类型转换 */
    printf("--- 2. 类型转换 ---\n");
    int a = 10, b = 3;
    /* 隐式转换: int/int -> int, 截断小数 */
    float bad_div = a / b;
    /* 显式转换: (float)a / b -> float */
    float good_div = (float)a / b;
    printf("隐式: %d / %d = %.2f (截断!)\n", a, b, bad_div);
    printf("显式: (float)%d / %d = %.6f\n\n", a, b, good_div);

    /* 整数提升示例 */
    char c1 = 100, c2 = 100;
    int sum = c1 + c2;  /* char 自动提升为 int */
    printf("char %d + char %d = int %d (整数提升)\n", c1, c2, sum);

    /* 3. printf 格式化输出进阶 */
    printf("\n--- 3. printf 格式化进阶 ---\n");
    printf("八进制: %o (0%o)\n", 255, 255);
    printf("十六进制: %x (0x%X)\n", 255, 255);
    printf("科学计数法: %e\n", 123456.789);
    printf("左对齐宽度10: |%-10d|\n", 42);
    printf("右对齐宽度10: |%10d|\n", 42);
    printf("前导零: |%010d|\n", 42);
    printf("精度控制: |%.3f|\n", 3.14159265);

    /* 4. scanf 简单演示 (用 sscanf 模拟输入) */
    printf("\n--- 4. sscanf 模拟 scanf ---\n");
    int parsed_int;
    float parsed_float;
    char parsed_str[32];
    const char *input = "42 3.14 hello";
    int count = sscanf(input, "%d %f %31s", &parsed_int, &parsed_float, parsed_str);
    printf("输入: \"%s\"\n", input);
    printf("解析到 %d 个值: int=%d, float=%.2f, str=\"%s\"\n",
           count, parsed_int, parsed_float, parsed_str);

    printf("\n✅ Q01 通过\n");
    return 0;
}
