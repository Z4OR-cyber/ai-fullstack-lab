/*
 * Q08: 动态内存管理
 * 知识点: malloc/calloc/realloc/free、内存泄漏、堆vs栈
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* 动态创建一维数组 */
static int *create_array(size_t n)
{
    int *arr = malloc(n * sizeof(int));
    if (arr == NULL) {
        fprintf(stderr, "malloc 失败\n");
        return NULL;
    }
    for (size_t i = 0; i < n; i++)
        arr[i] = (int)(i * i);
    return arr;
}

/* 动态创建二维数组 */
static int **create_matrix(size_t rows, size_t cols)
{
    int **m = malloc(rows * sizeof(int *));
    if (!m) return NULL;
    for (size_t i = 0; i < rows; i++) {
        m[i] = malloc(cols * sizeof(int));
        if (!m[i]) {
            /* 释放已分配的行 */
            for (size_t j = 0; j < i; j++)
                free(m[j]);
            free(m);
            return NULL;
        }
        for (size_t j = 0; j < cols; j++)
            m[i][j] = (int)(i * cols + j);
    }
    return m;
}

static void free_matrix(int **m, size_t rows)
{
    for (size_t i = 0; i < rows; i++)
        free(m[i]);
    free(m);
}

int main(void)
{
    printf("========================================\n");
    printf("  Q08: 动态内存管理\n");
    printf("========================================\n\n");

    /* 1. malloc: 分配未初始化内存 */
    printf("--- 1. malloc ---\n");
    size_t n = 5;
    int *arr = create_array(n);
    if (arr) {
        printf("  malloc 数组(%zu元素): ", n);
        for (size_t i = 0; i < n; i++)
            printf("%d ", arr[i]);
        printf("\n");
        free(arr);
        arr = NULL;
        printf("  已 free 释放\n\n");
    }

    /* 2. calloc: 分配并清零 */
    printf("--- 2. calloc (初始化为零) ---\n");
    int *carr = calloc(5, sizeof(int));
    if (carr) {
        printf("  calloc 数组(5元素, 全0): ");
        for (int i = 0; i < 5; i++)
            printf("%d ", carr[i]);
        printf("\n");
        /* 填入数据 */
        for (int i = 0; i < 5; i++)
            carr[i] = (i + 1) * 10;
        printf("  填入数据后: ");
        for (int i = 0; i < 5; i++)
            printf("%d ", carr[i]);
        printf("\n\n");
    }

    /* 3. realloc: 调整大小 */
    printf("--- 3. realloc ---\n");
    printf("  原数组(5元素): ");
    for (int i = 0; i < 5; i++)
        printf("%d ", carr[i]);
    printf("\n");

    int *new_arr = realloc(carr, 8 * sizeof(int));
    if (new_arr) {
        carr = new_arr;
        /* 新增部分未初始化 */
        for (int i = 5; i < 8; i++)
            carr[i] = (i + 1) * 10;
        printf("  realloc到8元素后: ");
        for (int i = 0; i < 8; i++)
            printf("%d ", carr[i]);
        printf("\n");
    }
    free(carr);
    carr = NULL;
    printf("\n");

    /* 4. 动态二维数组 */
    printf("--- 4. 动态二维数组 ---\n");
    size_t rows = 3, cols = 4;
    int **matrix = create_matrix(rows, cols);
    if (matrix) {
        printf("  %zux%zu 矩阵:\n", rows, cols);
        for (size_t i = 0; i < rows; i++) {
            printf("    ");
            for (size_t j = 0; j < cols; j++)
                printf("%3d ", matrix[i][j]);
            printf("\n");
        }
        free_matrix(matrix, rows);
        printf("  已释放\n\n");
    }

    /* 5. 堆 vs 栈 */
    printf("--- 5. 堆 vs 栈 ---\n");
    int stack_var = 42;
    int *heap_var = malloc(sizeof(int));
    *heap_var = 84;
    printf("  栈变量: stack_var = %d, 地址 = %p (高地址区)\n",
           stack_var, (void *)&stack_var);
    printf("  堆变量: *heap_var = %d, 地址 = %p (低地址区)\n",
           *heap_var, (void *)heap_var);
    printf("  栈: 自动管理, 函数返回即释放, 大小有限(MB级)\n");
    printf("  堆: 手动管理(malloc/free), 大大超过栈, 速度较慢\n");
    free(heap_var);

    /* 6. 常见错误演示 */
    printf("\n--- 6. 常见错误 (说明, 不执行危险操作) ---\n");
    printf("  错误1: 忘记 free -> 内存泄漏\n");
    printf("  错误2: free 后继续使用 -> use-after-free\n");
    printf("  错误3: 重复 free -> double free\n");
    printf("  错误4: free 非堆指针 -> 未定义行为\n");
    printf("  最佳实践: free 后置 NULL, 使用 valgrind 检查\n");

    printf("\n✅ Q08 通过\n");
    return 0;
}
