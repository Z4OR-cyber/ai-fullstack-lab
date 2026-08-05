/*
 * Q10: 字符串与指针
 * 知识点: 字符串常量vs字符数组、str系列函数实现
 */
#include <stdio.h>
#include <string.h>

/* 手动实现 strlen */
static size_t my_strlen(const char *s)
{
    const char *p = s;
    while (*p) p++;
    return (size_t)(p - s);
}

/* 手动实现 strcpy */
static char *my_strcpy(char *dest, const char *src)
{
    char *ret = dest;
    while ((*dest++ = *src++))
        ;
    return ret;
}

/* 手动实现 strcat */
static char *my_strcat(char *dest, const char *src)
{
    char *ret = dest;
    while (*dest) dest++;       /* 找到末尾 */
    while ((*dest++ = *src++))  /* 追加 */
        ;
    return ret;
}

/* 手动实现 strchr */
static char *my_strchr(const char *s, int c)
{
    while (*s) {
        if (*s == (char)c)
            return (char *)s;
        s++;
    }
    return (c == '\0') ? (char *)s : NULL;
}

/* 手动实现 strstr */
static char *my_strstr(const char *haystack, const char *needle)
{
    if (!*needle) return (char *)haystack;
    for (const char *h = haystack; *h; h++) {
        const char *p1 = h, *p2 = needle;
        while (*p1 && *p2 && *p1 == *p2) {
            p1++; p2++;
        }
        if (!*p2) return (char *)h;
    }
    return NULL;
}

/* 字符串反转 (原地) */
static void str_reverse(char *s)
{
    char *end = s + strlen(s) - 1;
    while (s < end) {
        char tmp = *s;
        *s = *end;
        *end = tmp;
        s++; end--;
    }
}

/* 判断回文 */
static int is_palindrome(const char *s)
{
    size_t len = strlen(s);
    for (size_t i = 0; i < len / 2; i++) {
        if (s[i] != s[len - 1 - i])
            return 0;
    }
    return 1;
}

int main(void)
{
    printf("========================================\n");
    printf("  Q10: 字符串与指针\n");
    printf("========================================\n\n");

    /* 1. 字符串常量 vs 字符数组 */
    printf("--- 1. 字符串常量 vs 字符数组 ---\n");
    char *str_const = "Hello";      /* 字符串常量, 存在只读区, 不可修改 */
    char  str_arr[] = "Hello";      /* 字符数组, 存在栈上, 可修改 */

    printf("  str_const = \"%s\" (地址=%p, 只读区)\n", str_const, (void *)str_const);
    printf("  str_arr   = \"%s\" (地址=%p, 栈区)\n", str_arr, (void *)str_arr);

    str_arr[0] = 'h';   /* OK: 字符数组可修改 */
    printf("  修改后 str_arr = \"%s\"\n", str_arr);
    /* str_const[0] = 'h'; */ /* 错误: 段错误! 字符串常量不可修改 */
    printf("  字符串常量不可修改 (修改会段错误)\n\n");

    /* 2. 手动实现 str 系列函数 */
    printf("--- 2. 手动实现 str 系列函数 ---\n");

    /* my_strlen */
    printf("  my_strlen(\"Hello World\") = %zu\n", my_strlen("Hello World"));

    /* my_strcpy */
    char dest1[32];
    my_strcpy(dest1, "Copied!");
    printf("  my_strcpy -> \"%s\"\n", dest1);

    /* my_strcat */
    char dest2[64] = "Hello, ";
    my_strcat(dest2, "World!");
    printf("  my_strcat -> \"%s\"\n", dest2);

    /* my_strchr */
    char *found = my_strchr("Hello, World!", 'W');
    printf("  my_strchr('W') -> \"%s\"\n", found ? found : "(null)");

    /* my_strstr */
    char *sub = my_strstr("abcdefgabc", "def");
    printf("  my_strstr(\"def\") -> \"%s\"\n", sub ? sub : "(null)");
    printf("\n");

    /* 3. 字符串操作 */
    printf("--- 3. 字符串操作 ---\n");

    /* 反转 */
    char rev[] = "Hello, C!";
    printf("  原始: \"%s\"\n", rev);
    str_reverse(rev);
    printf("  反转: \"%s\"\n", rev);
    str_reverse(rev);
    printf("  再反转: \"%s\"\n", rev);

    /* 回文判断 */
    printf("\n  回文判断:\n");
    const char *words[] = {"level", "hello", "racecar", "world", "noon"};
    for (int i = 0; i < 5; i++) {
        printf("    \"%s\" -> %s\n", words[i],
               is_palindrome(words[i]) ? "是回文" : "不是回文");
    }
    printf("\n");

    /* 4. 字符串与指针遍历 */
    printf("--- 4. 指针遍历字符串 ---\n");
    const char *text = "Pointers are powerful";
    printf("  逐字符遍历 \"%s\":\n    ", text);
    const char *p = text;
    int char_count = 0;
    while (*p) {
        printf("[%c] ", *p);
        p++;
        char_count++;
    }
    printf("\n  字符数 = %d\n", char_count);

    /* 5. sprintf 构建字符串 */
    printf("\n--- 5. sprintf 构建字符串 ---\n");
    char buf[128];
    int age = 25;
    const char *name = "Alice";
    sprintf(buf, "Name: %s, Age: %d", name, age);
    printf("  sprintf -> \"%s\"\n", buf);
    snprintf(buf, sizeof(buf), "Score: %.1f%%", 95.5);
    printf("  snprintf -> \"%s\" (安全, 限制长度)\n", buf);

    printf("\n✅ Q10 通过\n");
    return 0;
}
