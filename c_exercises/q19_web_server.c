/*
 * Q19: 简易Web服务器
 * 知识点: socket/bind/listen/accept、HTTP解析、并发
 *
 * 服务器启动后监听端口 18080, 接受一个请求后回复并退出
 * (避免阻塞测试脚本)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <signal.h>
#include <sys/wait.h>

#define PORT 18080
#define BUF_SIZE 4096

/* 构建HTTP响应 */
static void send_response(int client_fd, const char *status,
                          const char *content_type, const char *body)
{
    char header[BUF_SIZE];
    int body_len = (int)strlen(body);
    int header_len = snprintf(header, sizeof(header),
        "HTTP/1.1 %s\r\n"
        "Content-Type: %s\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n"
        "\r\n"
        "%s",
        status, content_type, body_len, body);
    write(client_fd, header, header_len);
}

/* 处理HTTP请求 */
static void handle_request(int client_fd)
{
    char buf[BUF_SIZE];
    ssize_t n = read(client_fd, buf, sizeof(buf) - 1);
    if (n <= 0) {
        close(client_fd);
        return;
    }
    buf[n] = '\0';

    /* 解析请求行: METHOD PATH HTTP/VERSION */
    char method[16], path[256], version[16];
    sscanf(buf, "%15s %255s %15s", method, path, version);

    printf("  [请求] %s %s %s\n", method, path, version);

    /* 路由 */
    if (strcmp(path, "/") == 0 || strcmp(path, "/index.html") == 0) {
        const char *body =
            "<html><body>"
            "<h1>Hello from C Web Server!</h1>"
            "<p>Built with socket() API</p>"
            "<ul>"
            "<li><a href=\"/time\">/time</a> - 当前时间</li>"
            "<li><a href=\"/info\">/info</a> - 服务器信息</li>"
            "</ul>"
            "</body></html>";
        send_response(client_fd, "200 OK", "text/html", body);
    } else if (strcmp(path, "/time") == 0) {
        char body[128];
        snprintf(body, sizeof(body),
            "{\"path\":\"/time\",\"pid\":%d}", getpid());
        send_response(client_fd, "200 OK", "application/json", body);
    } else if (strcmp(path, "/info") == 0) {
        const char *body =
            "{\"server\":\"C-Mini-HTTP\",\"port\":18080,"
            "\"version\":\"1.0\",\"author\":\"CLearn\"}";
        send_response(client_fd, "200 OK", "application/json", body);
    } else {
        const char *body =
            "<html><body><h1>404 Not Found</h1>"
            "<p>The requested URL was not found.</p>"
            "</body></html>";
        send_response(client_fd, "404 Not Found", "text/html", body);
    }

    close(client_fd);
}

int main(void)
{
    printf("========================================\n");
    printf("  Q19: 简易Web服务器\n");
    printf("========================================\n\n");

    /* 忽略 SIGCHLD, 自动回收子进程 */
    signal(SIGCHLD, SIG_IGN);

    /* 1. 创建 socket */
    printf("--- 1. 创建 socket ---\n");
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        perror("  socket");
        return 1;
    }
    printf("  socket 创建成功, fd=%d\n", server_fd);

    /* 设置 SO_REUSEADDR */
    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    /* 2. bind 绑定地址 */
    printf("\n--- 2. bind 绑定地址 ---\n");
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(PORT);
    if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("  bind");
        close(server_fd);
        return 1;
    }
    printf("  bind 成功: 0.0.0.0:%d\n", PORT);

    /* 3. listen 监听 */
    printf("\n--- 3. listen 监听 ---\n");
    if (listen(server_fd, 5) < 0) {
        perror("  listen");
        close(server_fd);
        return 1;
    }
    printf("  listen 成功, 等待连接...\n");

    /* 4. 等待并处理请求 */
    printf("\n--- 4. 接受连接 ---\n");
    printf("  服务器运行中 (PID=%d)\n", getpid());
    printf("  测试: curl http://localhost:%d/\n", PORT);

    /* fork 子进程来自测 */
    pid_t test_pid = fork();
    if (test_pid == 0) {
        /* 子进程: 等待1秒后用 curl 测试 */
        sleep(1);
        /* 测试首页 */
        printf("\n  [自测] curl http://localhost:%d/\n", PORT);
        execlp("curl", "curl", "-s", "http://localhost:18080/", NULL);
        _exit(0);
    }

    /* 父进程: accept 连接 */
    int handled = 0;
    while (handled < 1) {
        struct sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);
        int client_fd = accept(server_fd,
                               (struct sockaddr *)&client_addr, &client_len);
        if (client_fd < 0) {
            perror("  accept");
            continue;
        }

        char client_ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, sizeof(client_ip));
        printf("  [连接] 来自 %s:%d\n", client_ip, ntohs(client_addr.sin_port));

        /* fork 子进程处理请求 (并发) */
        pid_t pid = fork();
        if (pid == 0) {
            close(server_fd);
            handle_request(client_fd);
            _exit(0);
        }
        close(client_fd);
        handled++;
    }

    /* 等待测试子进程 */
    waitpid(test_pid, NULL, 0);

    close(server_fd);

    /* 5. socket API 流程总结 */
    printf("\n--- 5. Socket API 流程 ---\n");
    printf("  服务器端:\n");
    printf("    socket()  -> 创建套接字\n");
    printf("    bind()    -> 绑定 IP:Port\n");
    printf("    listen()  -> 开始监听\n");
    printf("    accept()  -> 接受连接 (阻塞)\n");
    printf("    read/write -> 数据交互\n");
    printf("    close()   -> 关闭连接\n");
    printf("  客户端:\n");
    printf("    socket()  -> 创建套接字\n");
    printf("    connect() -> 连接服务器\n");
    printf("    write/read -> 数据交互\n");
    printf("    close()   -> 关闭连接\n");
    printf("\n  并发模型: fork 子进程处理每个连接\n");

    printf("\n✅ Q19 通过\n");
    return 0;
}
