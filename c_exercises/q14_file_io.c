/*
 * Q14: 文件I/O
 * 知识点: fopen/fread/fwrite/fseek、文本vs二进制
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#define TEST_FILE_TXT  "test_text.txt"
#define TEST_FILE_BIN  "test_binary.dat"

typedef struct {
    int    id;
    char   name[32];
    double score;
} Record;

int main(void)
{
    printf("========================================\n");
    printf("  Q14: 文件I/O\n");
    printf("========================================\n\n");

    /* 1. 文本文件写入 */
    printf("--- 1. 文本文件写入 (fprintf) ---\n");
    FILE *fp = fopen(TEST_FILE_TXT, "w");
    if (!fp) {
        fprintf(stderr, "  打开失败: %s\n", strerror(errno));
        return 1;
    }
    fprintf(fp, "Line 1: Hello, File I/O!\n");
    fprintf(fp, "Line 2: C Programming\n");
    fprintf(fp, "Line 3: %d + %d = %d\n", 10, 20, 30);
    fprintf(fp, "Line 4: PI = %.5f\n", 3.14159);
    fclose(fp);
    printf("  已写入 %s\n\n", TEST_FILE_TXT);

    /* 2. 文本文件读取 */
    printf("--- 2. 文本文件读取 (fgets) ---\n");
    fp = fopen(TEST_FILE_TXT, "r");
    if (!fp) {
        fprintf(stderr, "  打开失败: %s\n", strerror(errno));
        return 1;
    }
    char line[256];
    int line_no = 0;
    while (fgets(line, sizeof(line), fp)) {
        line_no++;
        /* 去掉换行符 */
        line[strcspn(line, "\n")] = '\0';
        printf("  [%d] %s\n", line_no, line);
    }
    fclose(fp);
    printf("\n");

    /* 3. 二进制文件写入 (fwrite) */
    printf("--- 3. 二进制文件写入 (fwrite) ---\n");
    Record records[] = {
        {1, "Alice",   95.5},
        {2, "Bob",     87.3},
        {3, "Charlie", 92.1},
        {4, "Diana",   88.9}
    };
    int rec_count = sizeof(records) / sizeof(records[0]);

    fp = fopen(TEST_FILE_BIN, "wb");
    if (!fp) {
        fprintf(stderr, "  打开失败: %s\n", strerror(errno));
        return 1;
    }
    /* 先写入记录数 */
    fwrite(&rec_count, sizeof(int), 1, fp);
    /* 写入记录数组 */
    fwrite(records, sizeof(Record), rec_count, fp);
    fclose(fp);
    printf("  已写入 %d 条记录到 %s\n", rec_count, TEST_FILE_BIN);
    printf("  每条记录大小: %zu 字节, 总计: %zu 字节\n\n",
           sizeof(Record), sizeof(int) + sizeof(Record) * rec_count);

    /* 4. 二进制文件读取 (fread) */
    printf("--- 4. 二进制文件读取 (fread) ---\n");
    fp = fopen(TEST_FILE_BIN, "rb");
    if (!fp) {
        fprintf(stderr, "  打开失败: %s\n", strerror(errno));
        return 1;
    }
    int count;
    fread(&count, sizeof(int), 1, fp);
    printf("  读取记录数: %d\n", count);
    printf("  %-4s %-10s %8s\n", "ID", "Name", "Score");
    printf("  ---- ---------- --------\n");
    for (int i = 0; i < count; i++) {
        Record r;
        fread(&r, sizeof(Record), 1, fp);
        printf("  %-4d %-10s %8.1f\n", r.id, r.name, r.score);
    }
    fclose(fp);
    printf("\n");

    /* 5. fseek / ftell 文件定位 */
    printf("--- 5. fseek/ftell 文件定位 ---\n");
    fp = fopen(TEST_FILE_BIN, "rb");
    if (!fp) {
        fprintf(stderr, "  打开失败: %s\n", strerror(errno));
        return 1;
    }
    /* 获取文件大小 */
    fseek(fp, 0, SEEK_END);
    long file_size = ftell(fp);
    printf("  文件大小: %ld 字节\n", file_size);

    /* 跳过第1条, 读取第2条 */
    fseek(fp, sizeof(int) + sizeof(Record), SEEK_SET);
    Record r2;
    fread(&r2, sizeof(Record), 1, fp);
    printf("  第2条记录: id=%d, name=\"%s\", score=%.1f\n", r2.id, r2.name, r2.score);

    /* 读取最后一条 */
    fseek(fp, -(long)sizeof(Record), SEEK_END);
    Record r_last;
    fread(&r_last, sizeof(Record), 1, fp);
    printf("  最后一条: id=%d, name=\"%s\", score=%.1f\n",
           r_last.id, r_last.name, r_last.score);
    fclose(fp);
    printf("\n");

    /* 6. 文本 vs 二进制对比 */
    printf("--- 6. 文本 vs 二进制 ---\n");
    printf("  文本模式:\n");
    printf("    - 可读, 可用编辑器查看\n");
    printf("    - 有格式转换 (换行符等)\n");
    printf("    - 适合配置文件、日志\n");
    printf("  二进制模式:\n");
    printf("    - 紧凑, 读写快\n");
    printf("    - 无格式转换\n");
    printf("    - 适合结构化数据、图片\n");

    /* 清理 */
    remove(TEST_FILE_TXT);
    remove(TEST_FILE_BIN);

    printf("\n✅ Q14 通过\n");
    return 0;
}
