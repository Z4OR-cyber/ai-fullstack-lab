/*
 * Q18: 文件描述符与I/O重定向
 * 知识点: open/read/write、dup/dup2、管道
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/wait.h>

#define TMP_FILE "fd_test.txt"

int main(void)
{
    printf("========================================\n");
    printf("  Q18: 文件描述符与I/O重定向\n");
    printf("========================================\n\n");

    /* 1. 文件描述符基础 */
    printf("--- 1. 文件描述符基础 ---\n");
    printf("  STDIN_FILENO  = %d\n", STDIN_FILENO);
    printf("  STDOUT_FILENO = %d\n", STDOUT_FILENO);
    printf("  STDERR_FILENO = %d\n", STDERR_FILENO);
    printf("  新打开的文件描述符从 3 开始\n\n");

    /* 2. open/write/close (低级I/O) */
    printf("--- 2. open/write/close ---\n");
    int fd = open(TMP_FILE, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) {
        perror("  open");
        return 1;
    }
    printf("  打开 %s, fd=%d\n", TMP_FILE, fd);

    const char *msg = "Hello from low-level I/O!\nLine 2 here.\n";
    ssize_t written = write(fd, msg, strlen(msg));
    printf("  写入 %zd 字节\n", written);
    close(fd);
    printf("  已关闭 fd=%d\n\n", fd);

    /* 3. read 读取文件 */
    printf("--- 3. read 读取文件 ---\n");
    fd = open(TMP_FILE, O_RDONLY);
    if (fd < 0) {
        perror("  open");
        return 1;
    }
    char buf[256];
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    if (n > 0) {
        buf[n] = '\0';
        printf("  读取 %zd 字节:\n%s", n, buf);
    }
    close(fd);
    printf("\n");

    /* 4. dup/dup2: 文件描述符复制 */
    printf("--- 4. dup/dup2 重定向 ---\n");
    /* 保存原始 stdout */
    int saved_stdout = dup(STDOUT_FILENO);
    printf("  原始 stdout fd=%d, saved=%d\n", STDOUT_FILENO, saved_stdout);

    /* 重定向 stdout 到文件 */
    fd = open("redirect_test.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    dup2(fd, STDOUT_FILENO);  /* stdout 现在指向文件 */
    close(fd);

    /* 这条 printf 会写入文件而不是屏幕 */
    printf("这条文字被重定向到文件!\n");
    printf("另一行重定向的内容\n");

    /* 恢复 stdout */
    dup2(saved_stdout, STDOUT_FILENO);
    close(saved_stdout);
    printf("  stdout 已恢复, 重定向内容在 redirect_test.txt 中\n");

    /* 验证: 读取重定向的文件 */
    fd = open("redirect_test.txt", O_RDONLY);
    n = read(fd, buf, sizeof(buf) - 1);
    if (n > 0) {
        buf[n] = '\0';
        printf("  验证文件内容: %s", buf);
    }
    close(fd);
    printf("\n");

    /* 5. 管道 (pipe) */
    printf("--- 5. 管道 (pipe) ---\n");
    int pipefd[2];
    if (pipe(pipefd) < 0) {
        perror("  pipe");
        return 1;
    }
    printf("  创建管道: 读端 fd=%d, 写端 fd=%d\n", pipefd[0], pipefd[1]);

    pid_t pid = fork();
    if (pid == 0) {
        /* 子进程: 写管道 */
        close(pipefd[0]);  /* 关闭读端 */
        const char *pipe_msg = "Data through pipe from child!";
        write(pipefd[1], pipe_msg, strlen(pipe_msg) + 1);
        close(pipefd[1]);
        _exit(0);
    } else {
        /* 父进程: 读管道 */
        close(pipefd[1]);  /* 关闭写端 */
        char pipe_buf[128];
        ssize_t bytes = read(pipefd[0], pipe_buf, sizeof(pipe_buf));
        if (bytes > 0)
            printf("  父进程收到(%zd字节): \"%s\"\n", bytes, pipe_buf);
        close(pipefd[0]);
        wait(NULL);
    }
    printf("\n");

    /* 6. 标准I/O vs 系统调用I/O */
    printf("--- 6. 标准 I/O vs 系统调用 I/O ---\n");
    printf("  标准I/O (stdio.h):\n");
    printf("    fopen/fread/fwrite/fclose\n");
    printf("    带缓冲, 跨平台, 使用 FILE*\n");
    printf("  系统调用I/O (unistd.h/fcntl.h):\n");
    printf("    open/read/write/close\n");
    printf("    无缓冲, Linux专用, 使用 int fd\n");
    printf("  fd -> FILE*: fdopen(fd, mode)\n");
    printf("  FILE* -> fd: fileno(fp)\n");

    /* 清理 */
    remove(TMP_FILE);
    remove("redirect_test.txt");

    printf("\n✅ Q18 通过\n");
    return 0;
}
