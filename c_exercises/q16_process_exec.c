/*
 * Q16: 进程与exec
 * 知识点: fork/exec/wait、僵尸进程、孤儿进程
 */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <string.h>
#include <errno.h>

int main(void)
{
    printf("========================================\n");
    printf("  Q16: 进程与exec\n");
    printf("========================================\n\n");

    /* 1. fork 基础: 创建子进程 */
    printf("--- 1. fork 基础 ---\n");
    pid_t pid = fork();
    if (pid < 0) {
        fprintf(stderr, "  fork 失败: %s\n", strerror(errno));
        return 1;
    }

    if (pid == 0) {
        /* 子进程 */
        printf("  [子进程] PID=%d, 父PID=%d\n", getpid(), getppid());
        printf("  [子进程] 我是 fork 出来的副本\n");
        _exit(0);  /* 子进程直接退出, 不刷缓冲 */
    } else {
        /* 父进程 */
        printf("  [父进程] PID=%d, 子PID=%d\n", getpid(), pid);
        int status;
        waitpid(pid, &status, 0);
        if (WIFEXITED(status))
            printf("  [父进程] 子进程退出码: %d\n", WEXITSTATUS(status));
    }
    printf("\n");

    /* 2. exec 系列: 替换进程映像 */
    printf("--- 2. exec 替换进程 ---\n");
    pid = fork();
    if (pid == 0) {
        /* 子进程: 用 execlp 执行 echo 命令 */
        printf("  [子进程] exec 前 PID=%d\n", getpid());
        /* execlp 会替换当前进程映像 */
        execlp("echo", "echo", "Hello from exec!", NULL);
        /* 只有 exec 失败才会执行到这里 */
        perror("  execlp 失败");
        _exit(1);
    } else if (pid > 0) {
        int status;
        waitpid(pid, &status, 0);
        printf("  [父进程] 子进程(exec) 完成\n");
    }
    printf("\n");

    /* 3. 多个子进程并行 */
    printf("--- 3. 多个子进程 ---\n");
    int num_children = 3;
    for (int i = 0; i < num_children; i++) {
        pid = fork();
        if (pid == 0) {
            printf("  [子进程%d] PID=%d, 计算结果=%d\n",
                   i + 1, getpid(), i * i);
            _exit(i + 1);
        }
    }
    /* 父进程等待所有子进程 */
    for (int i = 0; i < num_children; i++) {
        int status;
        pid_t child = wait(&status);
        if (WIFEXITED(status))
            printf("  [父进程] 收割 PID=%d, 退出码=%d\n",
                   child, WEXITSTATUS(status));
    }
    printf("\n");

    /* 4. 僵尸进程与孤儿进程说明 */
    printf("--- 4. 僵尸进程与孤儿进程 ---\n");
    printf("  僵尸进程 (Zombie):\n");
    printf("    - 子进程已退出, 但父进程未调用 wait()\n");
    printf("    - 子进程的 PCB 仍占用资源\n");
    printf("    - 解决: 父进程调用 wait()/waitpid()\n");
    printf("    - 或用 signal(SIGCHLD, SIG_IGN) 自动回收\n\n");

    printf("  孤儿进程 (Orphan):\n");
    printf("    - 父进程先于子进程退出\n");
    printf("    - 子进程被 init/systemd (PID=1) 收养\n");
    printf("    - 不会造成危害, init 会自动回收\n\n");

    /* 5. 演示 SIGCHLD 自动回收 */
    printf("--- 5. SIGCHLD 自动回收 ---\n");
    /* 设置忽略 SIGCHLD, 子进程退出后自动回收, 不产生僵尸 */
    signal(SIGCHLD, SIG_IGN);
    pid = fork();
    if (pid == 0) {
        printf("  [子进程] PID=%d, 父进程会自动回收我\n", getpid());
        _exit(0);
    } else if (pid > 0) {
        /* 不需要 wait, 内核会自动回收 */
        sleep(1);  /* 等待子进程退出 */
        printf("  [父进程] 无需 wait, 子进程已被自动回收\n");
    }

    printf("\n✅ Q16 通过\n");
    return 0;
}
