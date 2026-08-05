/*
 * Q11: 内存布局与段错误
 * 知识点: 代码段/数据段/BSS/堆/栈、段错误调试
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* 全局已初始化变量 -> 数据段 (Data Segment) */
int global_init = 42;

/* 全局未初始化变量 -> BSS段 */
int global_uninit;

/* 静态已初始化 -> 数据段 */
static int static_init = 100;

/* 静态未初始化 -> BSS段 */
static int static_uninit;

/* const 全局 -> 代码段/只读数据段 */
static const char *readonly_str = "Read-only string";

/* 安全的字符串拷贝函数 */
static void safe_copy(char *dest, size_t dest_size, const char *src)
{
    if (dest_size == 0) return;
    size_t i;
    for (i = 0; i < dest_size - 1 && src[i]; i++)
        dest[i] = src[i];
    dest[i] = '\0';
}

int main(void)
{
    printf("========================================\n");
    printf("  Q11: 内存布局与段错误\n");
    printf("========================================\n\n");

    /* 1. 内存布局概览 */
    printf("--- 1. 内存布局 ---\n");
    printf("  ┌─────────────────── 高地址 ┐\n");
    printf("  │ 栈 (Stack)  ↓ 向下增长    │\n");
    printf("  │  局部变量、函数参数        │\n");
    printf("  ├────────────────────────── │\n");
    printf("  │ ↓ (空闲)                  │\n");
    printf("  │ ↑ (空闲)                  │\n");
    printf("  ├────────────────────────── │\n");
    printf("  │ 堆 (Heap)  ↑ 向上增长     │\n");
    printf("  │  malloc/free 管理的内存   │\n");
    printf("  ├────────────────────────── │\n");
    printf("  │ BSS段: 未初始化的全局/static│\n");
    printf("  ├────────────────────────── │\n");
    printf("  │ 数据段: 已初始化的全局/static│\n");
    printf("  ├────────────────────────── │\n");
    printf("  │ 代码段: 程序指令、只读常量 │\n");
    printf("  └─────────────────── 低地址 ┘\n\n");

    /* 2. 各段变量地址 */
    printf("--- 2. 各段变量地址 ---\n");
    int local_var = 7;                    /* 栈 */
    int *heap_ptr = malloc(sizeof(int));  /* 堆 */
    *heap_ptr = 99;

    printf("  代码段 (函数地址):  main = %p\n", (void *)main);
    printf("  数据段 (全局已初始化): global_init = %p -> %d\n",
           (void *)&global_init, global_init);
    printf("  数据段 (static已初始化): static_init = %p -> %d\n",
           (void *)&static_init, static_init);
    printf("  BSS段 (全局未初始化): global_uninit = %p -> %d\n",
           (void *)&global_uninit, global_uninit);
    printf("  BSS段 (static未初始化): static_uninit = %p -> %d\n",
           (void *)&static_uninit, static_uninit);
    printf("  堆:   *heap_ptr = %p -> %d\n", (void *)heap_ptr, *heap_ptr);
    printf("  栈:   local_var = %p -> %d\n", (void *)&local_var, local_var);
    printf("  只读: readonly_str = %p -> \"%s\"\n\n",
           (void *)readonly_str, readonly_str);

    free(heap_ptr);

    /* 3. 段错误常见原因 */
    printf("--- 3. 段错误常见原因 (说明, 不触发) ---\n");
    printf("  1. 解引用 NULL 指针\n");
    printf("     int *p = NULL; *p = 5;  // SIGSEGV!\n");
    printf("  2. 写入只读内存\n");
    printf("     char *s = \"hello\"; s[0] = 'H';  // SIGSEGV!\n");
    printf("  3. 访问已释放内存\n");
    printf("     free(p); *p = 5;  // 未定义行为\n");
    printf("  4. 数组越界\n");
    printf("     int a[10]; a[100000] = 5;  // 可能SIGSEGV\n");
    printf("  5. 栈溢出 (无限递归)\n");
    printf("     void f(){ f(); }  // 栈耗尽\n\n");

    /* 4. 安全编码实践 */
    printf("--- 4. 安全编码实践 ---\n");

    /* 安全: 使用 snprintf 而非 sprintf */
    char buf[8];
    snprintf(buf, sizeof(buf), "%s", "A very long string that would overflow");
    printf("  snprintf 安全截断: \"%s\" (buf大小=%zu)\n", buf, sizeof(buf));

    /* 安全: 自定义安全拷贝 */
    char safe_buf[10];
    safe_copy(safe_buf, sizeof(safe_buf), "This is too long!");
    printf("  safe_copy 安全截断: \"%s\" (buf大小=%zu)\n", safe_buf, sizeof(safe_buf));

    /* 安全: 检查 malloc 返回值 */
    int *p = malloc(4 * sizeof(int));
    if (p == NULL) {
        fprintf(stderr, "  malloc 失败\n");
        return 1;
    }
    p[0] = 1; p[1] = 2; p[2] = 3; p[3] = 4;
    printf("  malloc后检查: [%d, %d, %d, %d]\n", p[0], p[1], p[2], p[3]);
    free(p);
    p = NULL;  /* 悬挂指针置 NULL */
    printf("  free 后置 p = NULL (防止 use-after-free)\n\n");

    /* 5. printf 调试技巧 */
    printf("--- 5. printf 调试技巧 ---\n");
    printf("  技巧1: 打印变量值和地址\n");
    int debug_var = 123;
    printf("    [DEBUG] %s:%d var=%d &var=%p\n",
           __FILE__, __LINE__, debug_var, (void *)&debug_var);
    printf("  技巧2: 用宏控制调试输出\n");
    printf("  技巧3: 打印指针值定位内存位置\n");
    printf("  技巧4: 检查函数返回值和 errno\n");

    printf("\n✅ Q11 通过\n");
    return 0;
}
