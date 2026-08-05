"""安全的Python代码 - 无漏洞

此文件展示安全编码实践，作为扫描器的阴性测试用例。
扫描结果应为0个漏洞。
"""

import os
import hashlib
import secrets
import sqlite3


def get_user(username):
    """使用参数化查询防止SQL注入"""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE name = ?", (username,))
    return cursor.fetchone()


def hash_password(password):
    """使用SHA-256安全哈希算法"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token():
    """使用secrets模块生成密码学安全的随机令牌"""
    return secrets.token_hex(32)


def read_config(path):
    """安全地读取配置文件（path为受控路径，非用户输入拼接）"""
    with open(path, "r") as f:
        return f.read()


def get_api_key():
    """从环境变量读取密钥，避免硬编码"""
    return os.environ.get("API_KEY", "")


def safe_subprocess(host):
    """使用参数列表形式调用子进程，避免命令注入"""
    import subprocess
    return subprocess.run(["ping", "-c", "3", host], capture_output=True)
