/*
 * Q09: 函数指针与回调
 * 知识点: 回调函数模式、qsort回调、命令分发器
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* 1. 基本函数指针 */
static int add(int a, int b) { return a + b; }
static int sub(int a, int b) { return a - b; }
static int mul(int a, int b) { return a * b; }
static int my_div(int a, int b) { return b ? a / b : 0; }

/* 2. 回调函数: 比较函数 */
static int cmp_asc(const void *a, const void *b)
{
    return *(const int *)a - *(const int *)b;
}

static int cmp_desc(const void *a, const void *b)
{
    return *(const int *)b - *(const int *)a;
}

/* 3. 回调函数: map 操作 */
static void map_array(int *arr, int n, int (*fn)(int))
{
    for (int i = 0; i < n; i++)
        arr[i] = fn(arr[i]);
}

static int square_val(int x) { return x * x; }
static int double_val(int x) { return x * 2; }
static int negate_val(int x) { return -x; }

/* 4. 命令分发器 */
typedef int (*operation_fn)(int, int);

typedef struct {
    const char *name;
    operation_fn fn;
} command_t;

static command_t commands[] = {
    {"add", add},
    {"sub", sub},
    {"mul", mul},
    {"div", my_div},
};

static operation_fn find_command(const char *name)
{
    for (size_t i = 0; i < sizeof(commands) / sizeof(commands[0]); i++) {
        if (strcmp(commands[i].name, name) == 0)
            return commands[i].fn;
    }
    return NULL;
}

int main(void)
{
    printf("========================================\n");
    printf("  Q09: 函数指针与回调\n");
    printf("========================================\n\n");

    /* 1. 基本函数指针 */
    printf("--- 1. 基本函数指针 ---\n");
    int (*fp)(int, int) = NULL;
    fp = add;
    printf("  add(3, 5) = %d\n", fp(3, 5));
    fp = sub;
    printf("  sub(10, 3) = %d\n", fp(10, 3));
    fp = mul;
    printf("  mul(4, 6) = %d\n", fp(4, 6));
    printf("  sizeof(函数指针) = %zu\n\n", sizeof(fp));

    /* 函数指针数组 */
    printf("  函数指针数组:\n");
    int (*ops[])(int, int) = {add, sub, mul, my_div};
    const char *names[] = {"+", "-", "*", "/"};
    int a = 20, b = 4;
    for (int i = 0; i < 4; i++)
        printf("    %d %s %d = %d\n", a, names[i], b, ops[i](a, b));
    printf("\n");

    /* 2. qsort 回调 */
    printf("--- 2. qsort 回调 ---\n");
    int arr[] = {5, 2, 8, 1, 9, 3, 7, 4, 6};
    size_t n = sizeof(arr) / sizeof(arr[0]);
    printf("  原始: ");
    for (size_t i = 0; i < n; i++) printf("%d ", arr[i]);
    printf("\n");

    qsort(arr, n, sizeof(int), cmp_asc);
    printf("  升序: ");
    for (size_t i = 0; i < n; i++) printf("%d ", arr[i]);
    printf("\n");

    qsort(arr, n, sizeof(int), cmp_desc);
    printf("  降序: ");
    for (size_t i = 0; i < n; i++) printf("%d ", arr[i]);
    printf("\n\n");

    /* 3. map 回调 */
    printf("--- 3. map 回调 ---\n");
    int data[] = {1, 2, 3, 4, 5};
    int dn = 5;

    map_array(data, dn, square_val);
    printf("  平方: ");
    for (int i = 0; i < dn; i++) printf("%d ", data[i]);
    printf("\n");

    map_array(data, dn, double_val);
    printf("  翻倍: ");
    for (int i = 0; i < dn; i++) printf("%d ", data[i]);
    printf("\n");

    map_array(data, dn, negate_val);
    printf("  取反: ");
    for (int i = 0; i < dn; i++) printf("%d ", data[i]);
    printf("\n\n");

    /* 4. 命令分发器 */
    printf("--- 4. 命令分发器 ---\n");
    const char *cmds[] = {"add", "sub", "mul", "div", "unknown"};
    for (int i = 0; i < 5; i++) {
        operation_fn fn = find_command(cmds[i]);
        if (fn)
            printf("  %s(15, 5) = %d\n", cmds[i], fn(15, 5));
        else
            printf("  %s -> 未找到命令\n", cmds[i]);
    }

    printf("\n✅ Q09 通过\n");
    return 0;
}
