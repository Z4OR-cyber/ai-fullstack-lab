/*
 * Q07: 指针与数组
 * 知识点: 指针算术、数组名退化、多维数组与指针
 */
#include <stdio.h>

/* 数组名退化为指针: sizeof 在函数内失去数组大小信息 */
static void show_array_info(int arr[], int n)
{
    printf("  函数内 sizeof(arr) = %zu (退化为指针!)\n", sizeof(arr));
    printf("  函数内 sizeof(arr[0]) = %zu\n", sizeof(arr[0]));
    /* 用指针遍历 */
    int *p = arr;
    printf("  指针遍历: ");
    for (int i = 0; i < n; i++) {
        printf("%d ", *p);
        p++;  /* 指针算术: p+1 实际移动 sizeof(int) 字节 */
    }
    printf("\n");
}

/* 用指针算术求和 */
static int ptr_sum(const int *begin, const int *end)
{
    int sum = 0;
    for (const int *p = begin; p != end; p++)
        sum += *p;
    return sum;
}

int main(void)
{
    printf("========================================\n");
    printf("  Q07: 指针与数组\n");
    printf("========================================\n\n");

    /* 1. 数组名退化为指针 */
    printf("--- 1. 数组名退化 ---\n");
    int arr[] = {10, 20, 30, 40, 50};
    size_t n = sizeof(arr) / sizeof(arr[0]);
    printf("  main中 sizeof(arr) = %zu (真实大小)\n", sizeof(arr));
    show_array_info(arr, (int)n);
    printf("\n");

    /* 2. 指针算术 */
    printf("--- 2. 指针算术 ---\n");
    int *p = arr;
    printf("  arr[0] 地址 = %p, 值 = %d\n", (void *)p, *p);
    printf("  arr[1] 地址 = %p, 值 = %d (p+1)\n", (void *)(p + 1), *(p + 1));
    printf("  arr[4] 地址 = %p, 值 = %d (p+4)\n", (void *)(p + 4), *(p + 4));
    printf("  指针差: (p+4) - p = %ld (元素个数, 非字节数)\n", (long)((p + 4) - p));
    printf("  p[2] = %d (指针下标访问)\n", p[2]);

    /* 指针比较 */
    int *begin = arr;
    int *end = arr + n;
    printf("  ptr_sum = %d (begin 到 end)\n\n", ptr_sum(begin, end));

    /* 3. 数组名 vs &数组名 */
    printf("--- 3. 数组名 vs &数组名 ---\n");
    printf("  arr    = %p (首元素地址)\n", (void *)arr);
    printf("  &arr   = %p (整个数组地址, 值相同)\n", (void *)&arr);
    printf("  arr+1  = %p (跳过1个元素)\n", (void *)(arr + 1));
    printf("  &arr+1 = %p (跳过整个数组!)\n", (void *)(&arr + 1));
    printf("  差值 = %zu 字节 = 整个数组大小\n\n",
           (size_t)((char *)(&arr + 1) - (char *)arr));

    /* 4. 二维数组与指针 */
    printf("--- 4. 二维数组与指针 ---\n");
    int matrix[3][4] = {
        {1, 2, 3, 4},
        {5, 6, 7, 8},
        {9, 10, 11, 12}
    };
    printf("  matrix[1][2] = %d\n", matrix[1][2]);
    printf("  *(*(matrix+1)+2) = %d (指针写法)\n", *(*(matrix + 1) + 2));
    printf("  matrix[1] = %p, *(matrix+1) = %p (等价)\n",
           (void *)matrix[1], (void *)(*(matrix + 1)));

    /* 用行指针遍历 */
    int (*row_ptr)[4] = matrix;  /* 指向含4个int的数组的指针 */
    printf("  行指针遍历:\n");
    for (int i = 0; i < 3; i++) {
        printf("    行%d: ", i);
        for (int j = 0; j < 4; j++) {
            printf("%3d ", row_ptr[i][j]);
        }
        printf("\n");
    }
    printf("\n");

    /* 5. 指针数组 vs 数组指针 */
    printf("--- 5. 指针数组 vs 数组指针 ---\n");
    int a = 1, b = 2, c = 3;
    int *ptr_arr[3] = {&a, &b, &c};  /* 指针数组: 存放指针的数组 */
    printf("  指针数组: ");
    for (int i = 0; i < 3; i++)
        printf("%d ", *ptr_arr[i]);
    printf("\n");

    int single[5] = {100, 200, 300, 400, 500};
    int (*arr_ptr)[5] = &single;  /* 数组指针: 指向数组的指针 */
    printf("  数组指针: (*arr_ptr)[2] = %d\n", (*arr_ptr)[2]);

    printf("\n✅ Q07 通过\n");
    return 0;
}
