/*
 * Q17: 信号处理
 * 知识点: signal注册、SIGINT/SIGTERM、信号屏蔽
 *
 * 注意: 使用 sigaction 代替 signal (更可靠, 不会重置处理函数)
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>

static volatile sig_atomic_t got_sigint = 0;
static volatile sig_atomic_t got_sigusr1 = 0;

/* SIGINT 信号处理函数 */
static void sigint_handler(int sig)
{
    (void)sig;
    /* 在信号处理函数中只能使用 async-signal-safe 函数 */
    const char msg[] = "\n  [信号] 捕获 SIGINT (Ctrl+C)! 已忽略, 请等待...\n";
    write(STDOUT_FILENO, msg, sizeof(msg) - 1);
    got_sigint = 1;
}

/* SIGUSR1 信号处理函数 */
static void sigusr1_handler(int sig)
{
    (void)sig;
    const char msg[] = "  [信号] 捕获 SIGUSR1!\n";
    write(STDOUT_FILENO, msg, sizeof(msg) - 1);
    got_sigusr1 = 1;
}

/* SIGTERM 信号处理函数 */
static void sigterm_handler(int sig)
{
    (void)sig;
    const char msg[] = "  [信号] 捕获 SIGTERM, 准备退出...\n";
    write(STDOUT_FILENO, msg, sizeof(msg) - 1);
}

/* 使用 sigaction 注册信号处理函数 (比 signal 更可靠) */
static void register_handler(int signum, void (*handler)(int))
{
    struct sigaction sa;
    sa.sa_handler = handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    /* SA_RESTART: 被信号打断的系统调用自动重启 */
    /* 不设 SA_RESETHAND: 处理后不重置 (与 signal 的 System V 行为不同) */
    sigaction(signum, &sa, NULL);
}

int main(void)
{
    printf("========================================\n");
    printf("  Q17: 信号处理\n");
    printf("========================================\n\n");

    /* 1. sigaction 注册信号处理函数 */
    printf("--- 1. sigaction 注册 ---\n");
    register_handler(SIGINT, sigint_handler);
    register_handler(SIGUSR1, sigusr1_handler);
    register_handler(SIGTERM, sigterm_handler);
    /* 忽略 SIGPIPE (写已关闭的管道) */
    register_handler(SIGPIPE, SIG_IGN);
    printf("  已注册: SIGINT, SIGUSR1, SIGTERM, SIGPIPE(忽略)\n");
    printf("  使用 sigaction (比 signal 更可靠, 不重置处理函数)\n\n");

    /* 2. 常用信号说明 */
    printf("--- 2. 常用信号 ---\n");
    printf("  %-10s %-6s %s\n", "信号", "编号", "说明");
    printf("  %-10s %-6d %s\n", "SIGINT",  SIGINT,  "Ctrl+C 中断");
    printf("  %-10s %-6d %s\n", "SIGTERM", SIGTERM, "终止信号 (可捕获)");
    printf("  %-10s %-6d %s\n", "SIGKILL", SIGKILL, "强制终止 (不可捕获)");
    printf("  %-10s %-6d %s\n", "SIGSTOP", SIGSTOP, "暂停 (不可捕获)");
    printf("  %-10s %-6d %s\n", "SIGCONT", SIGCONT, "继续执行");
    printf("  %-10s %-6d %s\n", "SIGCHLD", SIGCHLD, "子进程状态变化");
    printf("  %-10s %-6d %s\n", "SIGPIPE", SIGPIPE, "管道破裂");
    printf("  %-10s %-6d %s\n", "SIGUSR1", SIGUSR1, "用户自定义信号1");
    printf("  %-10s %-6d %s\n", "SIGUSR2", SIGUSR2, "用户自定义信号2");
    printf("\n");

    /* 3. 给自己发送信号 */
    printf("--- 3. 给自己发送信号 ---\n");
    printf("  发送 SIGUSR1 给自己...\n");
    raise(SIGUSR1);  /* raise: 给当前进程发信号 */
    printf("  got_sigusr1 = %d\n", got_sigusr1);

    printf("  发送 SIGUSR2 给自己...\n");
    /* 临时忽略 SIGUSR2 */
    register_handler(SIGUSR2, SIG_IGN);
    raise(SIGUSR2);
    printf("  SIGUSR2 被忽略 (SIG_IGN)\n\n");

    /* 4. 信号屏蔽 (sigprocmask) */
    printf("--- 4. 信号屏蔽 (sigprocmask) ---\n");
    sigset_t block_set, old_set;

    /* 屏蔽 SIGUSR1 */
    sigemptyset(&block_set);
    sigaddset(&block_set, SIGUSR1);
    sigprocmask(SIG_BLOCK, &block_set, &old_set);
    printf("  已屏蔽 SIGUSR1\n");

    /* 发送 SIGUSR1, 此时被屏蔽, 挂起等待 */
    raise(SIGUSR1);
    printf("  SIGUSR1 已发送但被屏蔽 (pending)\n");

    /* 解除屏蔽, 信号被立即递送 */
    printf("  解除屏蔽...\n");
    got_sigusr1 = 0;
    sigprocmask(SIG_UNBLOCK, &block_set, NULL);
    printf("  got_sigusr1 = %d (解除屏蔽后信号被递送)\n\n", got_sigusr1);

    /* 5. 信号处理注意事项 */
    printf("--- 5. 信号处理注意事项 ---\n");
    printf("  1. 信号处理函数中只能调用 async-signal-safe 函数\n");
    printf("     安全: write(), _exit(), read()\n");
    printf("     不安全: printf(), malloc(), free()\n");
    printf("  2. 使用 volatile sig_atomic_t 标志变量\n");
    printf("  3. 信号可能在任意时刻打断程序执行\n");
    printf("  4. SIGKILL 和 SIGSTOP 不可被捕获/屏蔽\n");
    printf("  5. 信号不排队: 同一信号多次发送可能只递送一次\n");
    printf("  6. 推荐用 sigaction 替代 signal\n");
    printf("     - signal 在某些系统上处理后重置为 SIG_DFL\n");
    printf("     - sigaction 提供更精细的控制\n");

    printf("\n✅ Q17 通过\n");
    return 0;
}
