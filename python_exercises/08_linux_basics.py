"""
Linux 基础练习 + 扩展题
======================
涵盖：命令行操作、文本处理、Shell脚本、进程管理
在云沙箱环境中实际执行
"""

import subprocess
import os
import tempfile

def run(cmd, check=True):
    """执行 shell 命令并返回输出"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, executable='/bin/bash')
    if check and result.returncode != 0:
        raise AssertionError(f"命令失败: {cmd}\nstderr: {result.stderr}")
    return result.stdout.strip()

# ============================================================
# 基础练习
# ============================================================

def exercise_1_file_operations():
    """练习1：文件与目录操作"""
    # 1. 创建目录结构
    run("mkdir -p /tmp/linux_exercise/{dir1,dir2,dir3/subdir}")
    assert os.path.isdir("/tmp/linux_exercise/dir1")
    assert os.path.isdir("/tmp/linux_exercise/dir3/subdir")
    
    # 2. 创建文件并写入内容
    run("echo 'Hello Linux' > /tmp/linux_exercise/dir1/file1.txt")
    run("echo 'World' > /tmp/linux_exercise/dir1/file2.txt")
    run("echo 'Test Data' > /tmp/linux_exercise/dir2/data.txt")
    
    # 3. ls 列出文件
    output = run("ls /tmp/linux_exercise/dir1/")
    assert "file1.txt" in output
    assert "file2.txt" in output
    
    # 4. cat 查看文件内容
    content = run("cat /tmp/linux_exercise/dir1/file1.txt")
    assert content == "Hello Linux"
    
    # 5. cp 复制文件
    run("cp /tmp/linux_exercise/dir1/file1.txt /tmp/linux_exercise/dir2/")
    assert os.path.exists("/tmp/linux_exercise/dir2/file1.txt")
    
    # 6. mv 移动/重命名
    run("mv /tmp/linux_exercise/dir1/file2.txt /tmp/linux_exercise/dir1/renamed.txt")
    assert not os.path.exists("/tmp/linux_exercise/dir1/file2.txt")
    assert os.path.exists("/tmp/linux_exercise/dir1/renamed.txt")
    
    # 7. touch 创建空文件
    run("touch /tmp/linux_exercise/dir1/empty.txt")
    assert os.path.getsize("/tmp/linux_exercise/dir1/empty.txt") == 0
    
    # 8. find 查找文件
    output = run("find /tmp/linux_exercise -name '*.txt'")
    assert "file1.txt" in output
    assert "data.txt" in output
    
    # 9. wc 统计
    run("echo -e 'line1\\nline2\\nline3' > /tmp/linux_exercise/multiline.txt")
    line_count = run("wc -l < /tmp/linux_exercise/multiline.txt")
    assert int(line_count) == 3
    
    # 10. rm 删除
    run("rm /tmp/linux_exercise/dir1/empty.txt")
    assert not os.path.exists("/tmp/linux_exercise/dir1/empty.txt")
    
    print("✅ 练习1 通过：文件与目录操作")


def exercise_2_text_processing():
    """练习2：文本处理工具"""
    # 准备数据
    data = """Alice,25,Beijing,8000
Bob,30,Shanghai,12000
Charlie,35,Guangzhou,15000
David,28,Beijing,10000
Eve,22,Shenzhen,7000
Frank,40,Shanghai,20000
Grace,33,Beijing,13000
Henry,26,Shenzhen,9000
"""
    with open("/tmp/linux_exercise/employees.csv", "w") as f:
        f.write(data)
    
    # 1. grep 文本搜索
    result = run("grep 'Beijing' /tmp/linux_exercise/employees.csv")
    assert "Alice" in result
    assert "David" in result
    assert "Grace" in result
    
    # 2. grep -v 反向匹配
    result = run("grep -v 'Beijing' /tmp/linux_exercise/employees.csv")
    assert "Bob" in result
    assert "Alice" not in result
    
    # 3. grep -c 计数
    count = run("grep -c 'Shanghai' /tmp/linux_exercise/employees.csv")
    assert int(count) == 2
    
    # 4. sort 排序
    result = run("sort -t',' -k4 -n /tmp/linux_exercise/employees.csv")
    lines = result.split('\n')
    # 按薪资排序，第一行应该是 Eve(7000)
    assert "Eve" in lines[0]
    assert "Frank" in lines[-1]
    
    # 5. cut 提取列
    result = run("cut -d',' -f1 /tmp/linux_exercise/employees.csv")
    assert "Alice" in result
    assert "Bob" in result
    
    # 6. head/tail
    result = run("head -3 /tmp/linux_exercise/employees.csv")
    assert len(result.split('\n')) == 3
    
    result = run("tail -2 /tmp/linux_exercise/employees.csv")
    assert "Grace" in result
    
    # 7. uniq 去重（需先排序）
    result = run("cut -d',' -f3 /tmp/linux_exercise/employees.csv | sort | uniq -c | sort -rn")
    assert "Beijing" in result
    
    # 8. awk 数据处理
    result = run("awk -F',' '{sum+=$4} END {print sum}' /tmp/linux_exercise/employees.csv")
    total_salary = int(result)
    assert total_salary == 8000 + 12000 + 15000 + 10000 + 7000 + 20000 + 13000 + 9000
    
    # 9. sed 替换
    run("sed -i 's/Beijing/BJ/g' /tmp/linux_exercise/employees.csv")
    result = run("grep 'BJ' /tmp/linux_exercise/employees.csv")
    assert "Alice" in result
    
    print("✅ 练习2 通过：文本处理工具")


def exercise_3_permissions_ownership():
    """练习3：权限管理"""
    test_file = "/tmp/linux_exercise/perm_test.txt"
    run(f"echo 'permission test' > {test_file}")
    
    # 1. chmod 数字模式
    run(f"chmod 755 {test_file}")
    result = run(f"stat -c '%a' {test_file}")
    assert result == "755"
    
    # 2. chmod 符号模式
    run(f"chmod u+x,g-w,o-r {test_file}")
    # 755 = rwx r-x r-x; u+x(no-op), g-w(no-op, already no w), o-r: r-x -> -x = 1
    result = run(f"stat -c '%a' {test_file}")
    assert result == "751"
    
    # 3. 目录权限
    test_dir = "/tmp/linux_exercise/perm_dir"
    run(f"mkdir -p {test_dir}")
    run(f"chmod 700 {test_dir}")
    result = run(f"stat -c '%a' {test_dir}")
    assert result == "700"
    
    # 4. umask
    result = run("umask")
    assert len(result) >= 3
    
    print("✅ 练习3 通过：权限管理")


def exercise_4_pipes_redirection():
    """练习4：管道与重定向"""
    # 1. 管道链
    result = run("echo 'hello world foo bar' | tr ' ' '\\n' | sort | uniq -c | sort -rn")
    assert "1" in result  # 每个单词出现1次
    
    # 2. 输出重定向
    run("echo 'redirected' > /tmp/linux_exercise/redirect.txt")
    assert open("/tmp/linux_exercise/redirect.txt").read().strip() == "redirected"
    
    # 3. 追加重定向
    run("echo 'appended' >> /tmp/linux_exercise/redirect.txt")
    content = open("/tmp/linux_exercise/redirect.txt").read()
    assert "redirected" in content
    assert "appended" in content
    
    # 4. stderr 重定向
    result = run("ls /nonexistent 2>/tmp/linux_exercise/stderr.txt", check=False)
    err_content = open("/tmp/linux_exercise/stderr.txt").read()
    assert "No such file" in err_content or "cannot access" in err_content
    
    # 5. /dev/null 丢弃输出
    run("echo 'discarded' > /dev/null")
    
    # 6. tee 命令
    run("echo 'tee test' | tee /tmp/linux_exercise/tee.txt")
    assert open("/tmp/linux_exercise/tee.txt").read().strip() == "tee test"
    
    # 7. xargs
    result = run("echo '1 2 3 4 5' | tr ' ' '\\n' | xargs -n1 echo")
    assert "1" in result
    
    # 8. 进程替换
    result = run("diff <(echo 'a') <(echo 'b')", check=False)
    assert "a" in result or "b" in result
    
    print("✅ 练习4 通过：管道与重定向")


def exercise_5_environment_variables():
    """练习5：环境变量与Shell配置"""
    # 1. 设置变量
    result = run("export MY_VAR='test123' && echo $MY_VAR")
    assert result == "test123"
    
    # 2. 环境变量
    result = run("echo $HOME")
    assert len(result) > 0
    
    result = run("echo $PATH")
    assert ":" in result  # PATH 有多个路径
    
    # 3. 命令替换
    result = run("echo $(whoami)")
    assert len(result) > 0
    
    # 4. 算术运算
    result = run("echo $((5 + 3))")
    assert result == "8"
    
    result = run("echo $((10 / 3))")
    assert result == "3"  # 整数除法
    
    # 5. 字符串操作
    result = run("VAR='HelloWorld' && echo ${VAR:0:5}")
    assert result == "Hello"
    
    result = run("VAR='HelloWorld' && echo ${#VAR}")
    assert result == "10"
    
    # 6. 默认值
    result = run("echo ${UNDEFINED_VAR:-default_value}")
    assert result == "default_value"
    
    print("✅ 练习5 通过：环境变量与Shell配置")


# ============================================================
# 扩展题
# ============================================================

def ext_1_shell_script():
    """扩展1：编写 Shell 脚本 - 批量文件处理"""
    script = """#!/bin/bash
# 批量重命名 .txt 文件为 .md
DIR="/tmp/linux_exercise/script_test"
mkdir -p "$DIR"

# 创建测试文件
for i in 1 2 3 4 5; do
    echo "File $i content" > "$DIR/file_$i.txt"
done

# 统计文件数
count=$(ls "$DIR"/*.txt 2>/dev/null | wc -l)
echo "Found $count txt files"

# 批量重命名
for f in "$DIR"/*.txt; do
    mv "$f" "${f%.txt}.md"
done

# 验证
md_count=$(ls "$DIR"/*.md 2>/dev/null | wc -l)
txt_count=$(ls "$DIR"/*.txt 2>/dev/null | wc -l)
echo "After: $md_count md files, $txt_count txt files"
"""
    script_path = "/tmp/linux_exercise/batch_rename.sh"
    with open(script_path, "w") as f:
        f.write(script)
    run(f"chmod +x {script_path}")
    result = run(f"bash {script_path}")
    
    assert "Found 5 txt files" in result
    assert "After: 5 md files, 0 txt files" in result
    
    print("✅ 扩展1 通过：Shell 脚本批量处理")


def ext_2_log_analysis():
    """扩展2：日志分析实战"""
    # 模拟 nginx 访问日志
    logs = """192.168.1.1 - - [01/Jan/2025:10:00:01] "GET /api/users HTTP/1.1" 200 1024
192.168.1.2 - - [01/Jan/2025:10:00:02] "POST /api/login HTTP/1.1" 401 512
192.168.1.1 - - [01/Jan/2025:10:00:03] "GET /api/products HTTP/1.1" 200 2048
192.168.1.3 - - [01/Jan/2025:10:00:04] "GET /api/users HTTP/1.1" 200 1024
192.168.1.2 - - [01/Jan/2025:10:00:05] "POST /api/login HTTP/1.1" 200 512
192.168.1.1 - - [01/Jan/2025:10:00:06] "GET /api/orders HTTP/1.1" 500 0
192.168.1.4 - - [01/Jan/2025:10:00:07] "DELETE /api/users/5 HTTP/1.1" 403 256
192.168.1.3 - - [01/Jan/2025:10:00:08] "GET /api/products HTTP/1.1" 200 2048
192.168.1.1 - - [01/Jan/2025:10:00:09] "GET /api/users HTTP/1.1" 200 1024
192.168.1.2 - - [01/Jan/2025:10:00:10] "GET /api/orders HTTP/1.1" 200 4096
"""
    log_file = "/tmp/linux_exercise/access.log"
    with open(log_file, "w") as f:
        f.write(logs)
    
    # 1. 统计 HTTP 状态码分布
    result = run(f"awk '{{print $8}}' {log_file} | sort | uniq -c | sort -rn")
    assert "200" in result
    assert "401" in result
    
    # 2. 找出最活跃的 IP
    result = run(f"awk '{{print $1}}' {log_file} | sort | uniq -c | sort -rn | head -1")
    assert "192.168.1.1" in result  # 出现4次
    
    # 3. 统计错误请求（4xx, 5xx）
    result = run(f"grep -E ' (4[0-9][0-9]|5[0-9][0-9]) ' {log_file} | wc -l")
    assert int(result) == 3  # 401, 500, 403
    
    # 4. 统计每个 API 路径的访问次数
    result = run(f"awk '{{print $6}}' {log_file} | sort | uniq -c | sort -rn")
    assert "/api/users" in result
    
    # 5. 计算总流量
    result = run(f"awk '{{sum+=$9}} END {{print sum}}' {log_file}")
    total_bytes = int(result)
    assert total_bytes == 1024 + 512 + 2048 + 1024 + 512 + 0 + 256 + 2048 + 1024 + 4096
    
    print(f"   总流量: {total_bytes} bytes | 错误请求: 3个")
    print("✅ 扩展2 通过：日志分析实战")


def ext_3_crontab_automation():
    """扩展3：定时任务概念与监控脚本"""
    # 1. crontab 语法验证（不实际设置，只验证概念）
    # 每天凌晨3点: 0 3 * * *
    # 每5分钟: */5 * * * *
    # 每周一9点: 0 9 * * 1
    
    # 2. 编写监控脚本
    monitor_script = """#!/bin/bash
# 系统监控脚本
LOG="/tmp/linux_exercise/monitor.log"

echo "=== $(date) ===" >> $LOG
echo "CPU Load: $(cat /proc/loadavg | awk '{print $1}')" >> $LOG
echo "Memory: $(free -m | awk '/Mem/{print $3"MB/"$2"MB"}')" >> $LOG
echo "Disk: $(df -h / | awk 'NR==2{print $5" used"}')" >> $LOG
echo "Processes: $(ps aux | wc -l)" >> $LOG
echo "---" >> $LOG
"""
    script_path = "/tmp/linux_exercise/monitor.sh"
    with open(script_path, "w") as f:
        f.write(monitor_script)
    run(f"chmod +x {script_path}")
    run(f"bash {script_path}")
    
    # 验证日志生成
    log_content = open("/tmp/linux_exercise/monitor.log").read()
    assert "CPU Load:" in log_content
    assert "Memory:" in log_content
    assert "Disk:" in log_content
    
    # 3. 磁盘使用率检查
    result = run("df -h / | awk 'NR==2{print $5}'")
    assert "%" in result
    
    # 4. 进程检查
    result = run("ps aux | wc -l")
    assert int(result) > 5  # 至少有5个进程
    
    print("✅ 扩展3 通过：监控脚本与自动化")


def ext_4_network_tools():
    """扩展4：网络工具与诊断"""
    # 1. 检查网络连接
    result = run("hostname")
    assert len(result) > 0
    
    # 2. /etc/hosts 文件
    result = run("cat /etc/hosts | head -5")
    assert len(result) > 0  # 文件存在且有内容
    
    # 3. curl HTTP 请求
    result = run("curl -s -o /dev/null -w '%{http_code}' https://httpbin.org/get", check=False)
    # 在沙箱中可能无法访问外网，不强制断言
    if result and result.isdigit():
        assert int(result) in [200, 301, 302]
    
    # 4. 检查端口监听
    result = run("ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null", check=False)
    # 可能有输出也可能没有，不强制断言
    
    # 5. wget/curl 下载文件
    result = run("curl -s --head https://httpbin.org/ 2>/dev/null | head -1", check=False)
    if "HTTP" in result:
        assert "200" in result or "301" in result or "302" in result
    
    print("✅ 扩展4 通过：网络工具与诊断")


def ext_5_git_cli():
    """扩展5：Git 命令行操作"""
    # 1. 初始化仓库
    repo_dir = "/tmp/linux_exercise/git_repo"
    run(f"rm -rf {repo_dir} && mkdir -p {repo_dir} && cd {repo_dir} && git init && git branch -m main")
    assert os.path.isdir(f"{repo_dir}/.git")
    
    # 2. 配置（不使用个人信息，用测试值）
    run(f"cd {repo_dir} && git config user.name 'TestBot'")
    run(f"cd {repo_dir} && git config user.email 'test@local'")
    
    # 3. 创建文件并提交
    run(f"cd {repo_dir} && echo 'v1' > README.md && git add . && git commit -m 'Initial commit'")
    
    # 4. 查看日志
    result = run(f"cd {repo_dir} && git log --oneline")
    assert "Initial commit" in result
    
    # 5. 创建分支
    run(f"cd {repo_dir} && git checkout -b feature-branch")
    result = run(f"cd {repo_dir} && git branch")
    assert "feature-branch" in result
    
    # 6. 修改并提交
    run(f"cd {repo_dir} && echo 'v2' >> README.md && git add . && git commit -m 'Update README'")
    
    # 7. 合并分支
    run(f"cd {repo_dir} && git checkout main && git merge feature-branch")
    result = run(f"cd {repo_dir} && git log --oneline")
    assert "Update README" in result
    
    # 8. 查看差异
    run(f"cd {repo_dir} && echo 'v3' >> README.md")
    result = run(f"cd {repo_dir} && git diff")
    assert "v3" in result
    
    # 9. 回退
    run(f"cd {repo_dir} && git checkout -- README.md")
    result = run(f"cd {repo_dir} && git status --short")
    assert result == ""  # 工作区干净
    
    print("✅ 扩展5 通过：Git 命令行操作")


# ============================================================
# 主函数
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Linux 基础练习")
    print("=" * 60)
    exercise_1_file_operations()
    exercise_2_text_processing()
    exercise_3_permissions_ownership()
    exercise_4_pipes_redirection()
    exercise_5_environment_variables()
    
    print("\n" + "=" * 60)
    print("Linux 基础扩展题")
    print("=" * 60)
    ext_1_shell_script()
    ext_2_log_analysis()
    ext_3_crontab_automation()
    ext_4_network_tools()
    ext_5_git_cli()
    
    # 清理
    run("rm -rf /tmp/linux_exercise", check=False)
    
    print("\n" + "=" * 60)
    print("全部通过！Linux 基础 + 扩展 10/10 ✅")
    print("=" * 60)
