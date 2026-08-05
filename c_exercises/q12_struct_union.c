/*
 * Q12: 结构体与联合
 * 知识点: struct、嵌套、位域、union内存共享、枚举
 */
#include <stdio.h>
#include <string.h>

/* 1. 基本结构体 */
typedef struct {
    int    id;
    char   name[32];
    double score;
} Student;

/* 2. 嵌套结构体 */
typedef struct {
    int year;
    int month;
    int day;
} Date;

typedef struct {
    char     title[64];
    char     author[32];
    Date     publish_date;  /* 嵌套结构体 */
    float    price;
} Book;

/* 3. 位域: 紧凑存储标志位 */
typedef struct {
    unsigned int read    : 1;   /* 1 bit */
    unsigned int write   : 1;
    unsigned int execute : 1;
    unsigned int reserved: 5;   /* 5 bits padding */
} FilePermission;

/* 4. union: 内存共享 */
typedef union {
    int    i;
    float  f;
    char   bytes[4];
} DataUnion;

/* 5. 枚举 */
typedef enum {
    RED = 0,
    GREEN = 1,
    BLUE = 2,
    COLOR_COUNT
} Color;

/* 打印颜色名称 */
static const char *color_name(Color c)
{
    static const char *names[] = {"Red", "Green", "Blue"};
    if (c >= 0 && c < COLOR_COUNT) return names[c];
    return "Unknown";
}

int main(void)
{
    printf("========================================\n");
    printf("  Q12: 结构体与联合\n");
    printf("========================================\n\n");

    /* 1. 基本结构体 */
    printf("--- 1. 基本结构体 ---\n");
    Student s1 = {1, "Alice", 95.5};
    Student s2 = {2, "Bob", 87.3};
    printf("  sizeof(Student) = %zu\n", sizeof(Student));
    printf("  s1: id=%d, name=\"%s\", score=%.1f\n", s1.id, s1.name, s1.score);
    printf("  s2: id=%d, name=\"%s\", score=%.1f\n\n", s2.id, s2.name, s2.score);

    /* 结构体指针与 -> 运算符 */
    Student *sp = &s1;
    printf("  通过指针: sp->id=%d, sp->name=\"%s\"\n\n", sp->id, sp->name);

    /* 2. 嵌套结构体 */
    printf("--- 2. 嵌套结构体 ---\n");
    Book b = {"The C Programming Language", "K&R", {1978, 3, 22}, 45.99f};
    printf("  Book: \"%s\"\n", b.title);
    printf("  Author: %s\n", b.author);
    printf("  Date: %d-%02d-%02d\n", b.publish_date.year, b.publish_date.month, b.publish_date.day);
    printf("  Price: $%.2f\n", b.price);
    printf("  sizeof(Book) = %zu\n\n", sizeof(Book));

    /* 3. 位域 */
    printf("--- 3. 位域 ---\n");
    FilePermission perm = {0};
    perm.read = 1;
    perm.write = 1;
    printf("  sizeof(FilePermission) = %zu (8 bits = 1 byte)\n", sizeof(FilePermission));
    printf("  read=%d, write=%d, execute=%d\n", perm.read, perm.write, perm.execute);
    printf("  rwx: %c%c%c\n\n",
           perm.read ? 'r' : '-',
           perm.write ? 'w' : '-',
           perm.execute ? 'x' : '-');

    /* 4. union 内存共享 */
    printf("--- 4. union 内存共享 ---\n");
    DataUnion u;
    printf("  sizeof(DataUnion) = %zu (取最大成员大小)\n", sizeof(DataUnion));

    u.i = 0x41424344;  /* 'ABCD' in big-endian */
    printf("  u.i = 0x%X (%d)\n", u.i, u.i);
    printf("  u.f = %e (同一内存, 不同解释)\n", (double)u.f);
    printf("  u.bytes: ");
    for (int i = 0; i < 4; i++)
        printf("0x%02X ('%c') ", (unsigned char)u.bytes[i],
               (u.bytes[i] >= 32 && u.bytes[i] < 127) ? u.bytes[i] : '.');
    printf("\n\n");

    /* 5. 枚举 */
    printf("--- 5. 枚举 ---\n");
    printf("  RED=%d, GREEN=%d, BLUE=%d, COLOR_COUNT=%d\n",
           RED, GREEN, BLUE, COLOR_COUNT);
    for (Color c = RED; c < COLOR_COUNT; c++) {
        printf("  Color %d = %s\n", c, color_name(c));
    }

    /* 6. 结构体数组 */
    printf("\n--- 6. 结构体数组 ---\n");
    Student class[] = {
        {1, "Alice", 95.5},
        {2, "Bob", 87.3},
        {3, "Charlie", 92.1},
        {4, "Diana", 88.9}
    };
    int count = sizeof(class) / sizeof(class[0]);
    printf("  班级成绩单 (%d人):\n", count);
    printf("  %-4s %-10s %6s\n", "ID", "Name", "Score");
    printf("  ---- ---------- ------\n");
    double total = 0;
    for (int i = 0; i < count; i++) {
        printf("  %-4d %-10s %6.1f\n", class[i].id, class[i].name, class[i].score);
        total += class[i].score;
    }
    printf("  ---- ---------- ------\n");
    printf("  平均分: %.2f\n", total / count);

    printf("\n✅ Q12 通过\n");
    return 0;
}
