"""包含多种安全漏洞的Python测试代码

此文件包含10种安全漏洞，用于验证扫描器的检测能力。
每段代码标注了对应的漏洞规则ID (SCxxx)。
"""

import os
import pickle
import hashlib
import random
import requests


# SC004 - 硬编码密钥
API_KEY = "sk-1234567890abcdef"
SECRET_TOKEN = "bearer_token_abc123"
DATABASE_PASSWORD = "admin_password_2024"


# SC001 - SQL注入：字符串拼接构造SQL语句
def get_user(username):
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    cursor.execute(query)


# SC002 - 命令注入：os.system + 用户输入拼接
def ping_host(host):
    os.system("ping -c 3 " + host)


# SC003 - XSS：Flask render_template_string + 用户输入
def render_page(user_input):
    return render_template_string(user_input)


# SC005 - 路径遍历：open() + 路径拼接
def read_file(filename):
    f = open("/data/" + filename, "r")
    return f.read()


# SC006 - 不安全的反序列化：pickle.loads
def load_data(data):
    return pickle.loads(data)


# SC007 - 弱加密：MD5用于密码哈希
def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()


# SC008 - SSRF：requests.get + 用户可控URL
def fetch_url(url):
    response = requests.get(url)
    return response.text


# SC009 - 信息泄露：print输出敏感信息
def log_credentials(user_password):
    print(f"Password: {user_password}")


# SC010 - 不安全的随机数：random.random()用于令牌生成
def generate_token():
    return str(random.random())
