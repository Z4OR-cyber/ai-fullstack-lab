/*
 * string_utils.c — 字符串工具函数实现
 */
#include "string_utils.h"
#include <string.h>
#include <ctype.h>

size_t str_count_char(const char *s, char c)
{
    size_t count = 0;
    while (*s) {
        if (*s == c) count++;
        s++;
    }
    return count;
}

void str_reverse(char *s)
{
    size_t len = strlen(s);
    for (size_t i = 0; i < len / 2; i++) {
        char tmp = s[i];
        s[i] = s[len - 1 - i];
        s[len - 1 - i] = tmp;
    }
}

int str_is_palindrome(const char *s)
{
    size_t len = strlen(s);
    for (size_t i = 0; i < len / 2; i++) {
        if (s[i] != s[len - 1 - i])
            return 0;
    }
    return 1;
}

void str_to_upper(char *s)
{
    while (*s) {
        *s = toupper((unsigned char)*s);
        s++;
    }
}

void str_to_lower(char *s)
{
    while (*s) {
        *s = tolower((unsigned char)*s);
        s++;
    }
}

void str_trim(char *s)
{
    /* 去前导空格 */
    char *start = s;
    while (*start == ' ' || *start == '\t') start++;
    if (start != s) memmove(s, start, strlen(start) + 1);

    /* 去尾部空格 */
    size_t len = strlen(s);
    while (len > 0 && (s[len - 1] == ' ' || s[len - 1] == '\t')) {
        s[--len] = '\0';
    }
}
