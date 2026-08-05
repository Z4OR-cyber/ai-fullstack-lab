/*
 * Q04: 数组与字符串
 * 知识点: 字符数组vs字符串、string.h函数族、缓冲区溢出初探
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* 手动实现 strlen */
static size_t my_strlen(const char *s)
{
    size_t len = 0;
    while (s[len]) len++;
    return len;
}

/* 手动实现 strcmp */
static int my_strcmp(const char *a, const char *b)
{
    while (*a && *a == *b) { a++; b++; }
    return (unsigned char)*a - (unsigned char)*b;
}

/* 手动实现 strcpy (带长度限制, 防止溢出) */
static char *my_strncpy(char *dest, const char *src, size_t n)
{
    size_t i;
    for (i = 0; i < n && src[i]; i++)
        dest[i] = src[i];
    for (; i < n; i++)
        dest[i] = '\0';
    return dest;
}

int main(void)
{
    printf("========================================\n");
    printf("  Q04: 数组与字符串\n");
    printf("========================================\n\n");

    /* 1. 数组基本操作 */
    printf("--- 1. 数组基本操作 ---\n");
    int arr[] = {10, 20, 30, 40, 50};
    size_t n = sizeof(arr) / sizeof(arr[0]);
    printf("  数组: ");
    for (size_t i = 0; i < n; i++) printf("%d ", arr[i]);
    printf("\n  元素个数 = %zu, 总字节数 = %zu\n", n, sizeof(arr));

    /* 数组求和 */
    int sum = 0;
    for (size_t i = 0; i < n; i++) sum += arr[i];
    printf("  求和 = %d, 平均 = %.1f\n\n", sum, (double)sum / n);

    /* 2. 字符数组 vs 字符串 */
    printf("--- 2. 字符数组 vs 字符串 ---\n");
    char str1[] = "Hello";        /* 字符串字面量初始化, 自动加 '\0' */
    char str2[] = {'H','e','l','l','o','\0'};  /* 手动加 '\0' */
    char str3[5] = {'H','e','l','l','o'};       /* 字符数组, 无 '\0', 不是字符串! */
    printf("  str1 = \"%s\" (size=%zu, len=%zu)\n", str1, sizeof(str1), strlen(str1));
    printf("  str2 = \"%s\" (size=%zu, len=%zu)\n", str2, sizeof(str2), strlen(str2));
    printf("  str3 size=%zu (无'\\0', 不是合法字符串)\n\n", sizeof(str3));

    /* 3. string.h 函数族 */
    printf("--- 3. string.h 函数族 ---\n");
    char buf[32];

    /* strcpy / strncpy */
    strcpy(buf, "World");
    printf("  strcpy -> \"%s\"\n", buf);
    strncpy(buf, "Hi", 32);
    printf("  strncpy -> \"%s\"\n", buf);

    /* strcat */
    strcat(buf, ", C!");
    printf("  strcat -> \"%s\"\n", buf);

    /* strcmp */
    printf("  strcmp(\"abc\",\"abc\") = %d\n", strcmp("abc", "abc"));
    printf("  strcmp(\"abc\",\"abd\") = %d\n", strcmp("abc", "abd"));
    printf("  strcmp(\"abd\",\"abc\") = %d\n", strcmp("abd", "abc"));

    /* strstr */
    const char *found = strstr("Hello, World!", "World");
    printf("  strstr -> %s\n", found ? found : "(null)");

    /* strchr */
    const char *ch = strchr("Hello, World!", 'W');
    printf("  strchr -> %s\n\n", ch ? ch : "(null)");

    /* 4. 手动实现 string.h 函数 */
    printf("--- 4. 手动实现 string.h 函数 ---\n");
    printf("  my_strlen(\"Hello\") = %zu\n", my_strlen("Hello"));
    printf("  my_strcmp(\"abc\",\"abc\") = %d\n", my_strcmp("abc", "abc"));
    printf("  my_strcmp(\"abc\",\"abd\") = %d\n", my_strcmp("abc", "abd"));
    char mybuf[16];
    my_strncpy(mybuf, "Copied!", 16);
    printf("  my_strncpy -> \"%s\"\n\n", mybuf);

    /* 5. 二维数组 */
    printf("--- 5. 二维数组 ---\n");
    int matrix[3][3] = {
        {1, 2, 3},
        {4, 5, 6},
        {7, 8, 9}
    };
    printf("  矩阵:\n");
    for (int i = 0; i < 3; i++) {
        printf("  ");
        for (int j = 0; j < 3; j++)
            printf("%3d ", matrix[i][j]);
        printf("\n");
    }
    /* 对角线求和 */
    int diag_sum = 0;
    for (int i = 0; i < 3; i++) diag_sum += matrix[i][i];
    printf("  主对角线和 = %d\n\n", diag_sum);

    /* 6. 缓冲区溢出初探 (安全演示) */
    printf("--- 6. 缓冲区溢出初探 ---\n");
    char small[8];
    /* 危险: strcpy(small, "This string is too long!");  会溢出! */
    /* 安全: 使用 strncpy 限制长度 */
    strncpy(small, "TooLongString", sizeof(small) - 1);
    small[sizeof(small) - 1] = '\0';
    printf("  安全拷贝(截断): \"%s\" (buf大小=%zu)\n", small, sizeof(small));
    printf("  教训: 永远用 strncpy/snprintf 替代 strcpy/sprintf\n");

    printf("\n✅ Q04 通过\n");
    return 0;
}
