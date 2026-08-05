/*
 * Q06: 指针基础
 * 知识点: 取地址/解引用、NULL指针、void指针
 */
#include <stdio.h>
#include <stddef.h>

/* 通过指针修改变量值 */
static void set_value(int *p, int val)
{
    if (p != NULL)
        *p = val;
}

/* void* 指针: 通用指针, 可以指向任何类型 */
static void print_as_int(void *p)
{
    int *ip = (int *)p;
    printf("  void* -> int: %d\n", *ip);
}

static void print_as_double(void *p)
{
    double *dp = (double *)p;
    printf("  void* -> double: %.2f\n", *dp);
}

int main(void)
{
    printf("========================================\n");
    printf("  Q06: 指针基础\n");
    printf("========================================\n\n");

    /* 1. 取地址与解引用 */
    printf("--- 1. 取地址与解引用 ---\n");
    int x = 42;
    int *ptr = &x;   /* 取地址 */
    printf("  x = %d\n", x);
    printf("  &x = %p\n", (void *)&x);
    printf("  ptr = %p (指向x)\n", (void *)ptr);
    printf("  *ptr = %d (解引用)\n", *ptr);

    /* 通过指针修改变量 */
    *ptr = 100;
    printf("  *ptr = 100 后, x = %d\n\n", x);

    /* 2. 指针大小与对齐 */
    printf("--- 2. 指针大小 ---\n");
    printf("  sizeof(int*)    = %zu\n", sizeof(int *));
    printf("  sizeof(double*) = %zu\n", sizeof(double *));
    printf("  sizeof(char*)   = %zu\n", sizeof(char *));
    printf("  sizeof(void*)   = %zu (64位系统通常为8)\n\n", sizeof(void *));

    /* 3. NULL 指针 */
    printf("--- 3. NULL 指针 ---\n");
    int *null_ptr = NULL;
    printf("  null_ptr = %p\n", (void *)null_ptr);
    printf("  null_ptr == NULL? %s\n", null_ptr == NULL ? "是" : "否");

    /* 安全使用: 先检查再解引用 */
    set_value(null_ptr, 5);   /* 不会崩溃, 因为函数内检查了 NULL */
    printf("  set_value(NULL, 5) 安全跳过\n");
    set_value(&x, 7);
    printf("  set_value(&x, 7) 后, x = %d\n\n", x);

    /* 4. void* 通用指针 */
    printf("--- 4. void* 通用指针 ---\n");
    int    iv = 123;
    double dv = 9.99;
    void *vp;
    vp = &iv;
    print_as_int(vp);
    vp = &dv;
    print_as_double(vp);
    printf("\n");

    /* 5. 指针的指针 (二级指针) */
    printf("--- 5. 二级指针 ---\n");
    int value = 55;
    int *p1 = &value;
    int **p2 = &p1;
    printf("  value = %d\n", value);
    printf("  *p1 = %d (一级解引用)\n", *p1);
    printf("  **p2 = %d (二级解引用)\n", **p2);
    printf("  p1 = %p, p2 = %p (p2指向p1)\n", (void *)p1, (void *)p2);

    /* 6. const 指针 */
    printf("\n--- 6. const 指针 ---\n");
    int a = 10, b = 20;
    const int *pc1 = &a;    /* 指向const的指针: 不能通过指针修改值 */
    int *const pc2 = &a;    /* const指针: 指针本身不可变 */
    const int *const pc3 = &a; /* 都不可变 */
    printf("  const int *p  -> 可改指向, 不可改值\n");
    printf("  int *const p  -> 不可改指向, 可改值\n");
    printf("  const int *const p -> 都不可变\n");
    pc1 = &b;  /* OK: 可以改指向 */
    /* *pc1 = 5; */ /* 错误: 不能修改值 */
    *pc2 = 15; /* OK: 可以改值 */
    /* pc2 = &b; */ /* 错误: 不能改指向 */
    printf("  *pc1 = %d, *pc2 = %d\n", *pc1, *pc2);

    printf("\n✅ Q06 通过\n");
    return 0;
}
