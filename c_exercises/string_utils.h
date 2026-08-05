/*
 * string_utils.h — 字符串工具函数声明
 */
#ifndef STRING_UTILS_H
#define STRING_UTILS_H

#include <stddef.h>

/* 统计字符出现次数 */
size_t str_count_char(const char *s, char c);

/* 反转字符串 (原地) */
void str_reverse(char *s);

/* 判断回文 */
int str_is_palindrome(const char *s);

/* 转大写 */
void str_to_upper(char *s);

/* 转小写 */
void str_to_lower(char *s);

/* 去除首尾空格 */
void str_trim(char *s);

#endif /* STRING_UTILS_H */
