"""危险模式定义 — 代码审查技能的脚本附件.

定义常见的代码安全危险模式，供 code-reviewer 技能使用.
"""

# 危险函数调用模式
DANGEROUS_FUNCTIONS = [
    "eval(",
    "exec(",
    "os.system(",
    "subprocess.call(",
    "pickle.loads(",
    "yaml.load(",  # 应使用 yaml.safe_load
]

# SQL 注入风险模式
SQL_INJECTION_PATTERNS = [
    "f\"SELECT",
    "f'SELECT",
    "format(query",
    "% (",
    "+ user_input",
]
