"""
安全审计规则库
基于15类攻击共性 + 10层防御联动体系
每条规则包含：检测逻辑、风险等级、攻击描述、修复建议
"""

# ============================================================
# Python 漏洞检测规则（AST + 模式匹配）
# ============================================================

PYTHON_RULES = [
    # --- 输入信任崩塌 ---
    {
        "id": "PY001",
        "category": "注入",
        "name": "SQL注入",
        "severity": "CRITICAL",
        "attack_type": "字符串拼接SQL查询",
        "description": "SQL查询使用字符串拼接或f-string，攻击者可通过注入恶意SQL语句读取/修改/删除数据。",
        "defense": "使用参数化查询（占位符），永不拼接用户输入到SQL语句中。",
        "patterns": [
            r'execute\s*\(\s*f["\']',
            r'execute\s*\(\s*["\'].*%[sd].*["\'].*%',
            r'execute\s*\(\s*["\'].*\+.*["\']',
            r'execute\s*\(\s*["\'].*\.format\s*\(',
        ],
        "ast_check": "sql_injection",
    },
    {
        "id": "PY002",
        "category": "注入",
        "name": "命令注入",
        "severity": "CRITICAL",
        "attack_type": "os.system/subprocess shell=True 拼接用户输入",
        "description": "通过os.system或subprocess(shell=True)执行包含用户输入的命令，攻击者可注入任意系统命令。",
        "defense": "使用subprocess.run(shell=False)并传入参数列表；对输入做白名单校验。",
        "patterns": [
            r'os\.system\s*\(',
            r'os\.popen\s*\(',
            r'subprocess\..*shell\s*=\s*True',
            r'eval\s*\(',
            r'exec\s*\(',
        ],
        "ast_check": "command_injection",
    },
    {
        "id": "PY003",
        "category": "注入",
        "name": "SSTI模板注入",
        "severity": "HIGH",
        "attack_type": "用户输入直接渲染为模板",
        "description": "用户输入被直接作为模板渲染，攻击者可执行任意代码（如{{7*7}}）。",
        "defense": "使用安全模板渲染函数（如render_template而非render_template_string）；对模板输入做白名单。",
        "patterns": [
            r'render_template_string\s*\(',
            r'Template\s*\(.*\)\.render',
            r'Environment.*from_string',
        ],
    },
    {
        "id": "PY004",
        "category": "跨站攻击",
        "name": "XSS跨站脚本",
        "severity": "HIGH",
        "attack_type": "未转义的用户输入输出到HTML",
        "description": "用户输入未经HTML转义直接输出到页面，可注入恶意JavaScript。",
        "defense": "对所有用户输入做HTML转义；设置Content-Security-Policy头；使用框架自动转义功能。",
        "patterns": [
            r'Markup\s*\(',
            r'\|safe\b',
            r'innerHTML\s*=',
        ],
    },
    {
        "id": "PY005",
        "category": "文件攻击",
        "name": "路径遍历",
        "severity": "HIGH",
        "attack_type": "用户输入拼接文件路径",
        "description": "用户输入直接拼接到文件路径中，可通过../访问任意文件。",
        "defense": "使用os.path.realpath规范化路径后校验是否在允许目录内；使用白名单限定文件名。",
        "patterns": [
            r'open\s*\(\s*f["\']',
            r'open\s*\(\s*.*\+.*\)',
            r'open\s*\(\s*.*\.format',
            r'os\.path\.join\s*\(.*request',
        ],
        "ast_check": "path_traversal",
    },
    # --- 身份权限失守 ---
    {
        "id": "PY006",
        "category": "认证安全",
        "name": "硬编码密钥",
        "severity": "HIGH",
        "attack_type": "源码中硬编码密码/Token/API Key",
        "description": "密钥硬编码在源码中，一旦代码泄露（如推送到公开仓库）密钥即暴露。",
        "defense": "使用环境变量或密钥管理服务（如Vault）；.gitignore排除配置文件。",
        "patterns": [
            r'password\s*=\s*["\'][^"\']{4,}["\']',
            r'api_key\s*=\s*["\'][^"\']{8,}["\']',
            r'secret\s*=\s*["\'][^"\']{8,}["\']',
            r'token\s*=\s*["\'][^"\']{10,}["\']',
            r'AWS_SECRET_ACCESS_KEY\s*=\s*["\']',
        ],
    },
    {
        "id": "PY007",
        "category": "认证安全",
        "name": "弱密码哈希",
        "severity": "HIGH",
        "attack_type": "使用MD5/SHA1哈希密码",
        "description": "MD5和SHA1已被破解，不适合用于密码存储。彩虹表可在秒级还原常见密码。",
        "defense": "使用bcrypt/scrypt/argon2等专门密码哈希算法，配合随机salt和足够高的迭代次数。",
        "patterns": [
            r'hashlib\.md5\s*\(',
            r'hashlib\.sha1\s*\(',
        ],
    },
    {
        "id": "PY008",
        "category": "认证安全",
        "name": "JWT弱配置",
        "severity": "HIGH",
        "attack_type": "JWT使用none算法或弱密钥",
        "description": "JWT使用none算法或弱密钥，攻击者可伪造任意token。",
        "defense": "强制使用RS256/ES256等非对称算法；密钥长度不少于256位；验证时拒绝none算法。",
        "patterns": [
            r'algorithm\s*=\s*["\']none["\']',
            r'algorithm\s*=\s*["\']HS256["\'].*secret\s*=\s*["\'][^"\']{0,15}["\']',
            r'jwt\.decode\s*\([^)]*verify\s*=\s*False',
        ],
    },
    {
        "id": "PY009",
        "category": "授权安全",
        "name": "不安全反序列化",
        "severity": "CRITICAL",
        "attack_type": "pickle/yaml不安全加载",
        "description": "反序列化不可信数据可导致远程代码执行。pickle和yaml.load是高危函数。",
        "defense": "使用json替代pickle；yaml.load必须指定Loader=yaml.SafeLoader。",
        "patterns": [
            r'pickle\.loads?\s*\(',
            r'yaml\.load\s*\(\s*[^)]*\)(?<!SafeLoader\))',
            r'marshal\.loads?\s*\(',
            r'cPickle\.loads?\s*\(',
        ],
    },
    # --- 逻辑配置缺陷 ---
    {
        "id": "PY010",
        "category": "配置安全",
        "name": "调试模式开启",
        "severity": "MEDIUM",
        "attack_type": "生产环境开启debug模式",
        "description": "Debug模式暴露详细错误信息和堆栈跟踪，攻击者可获取敏感路径、变量名等内部信息。",
        "defense": "生产环境关闭debug模式；使用自定义错误页面。",
        "patterns": [
            r'debug\s*=\s*True',
            r'app\.debug\s*=\s*True',
            r'FLASK_ENV\s*=\s*["\']development["\']',
        ],
    },
    {
        "id": "PY011",
        "category": "配置安全",
        "name": "CORS配置过宽",
        "severity": "MEDIUM",
        "attack_type": "Allow-Origin设为*",
        "description": "CORS设为允许所有源，任意网站可跨域读取API响应。",
        "defense": "明确指定允许的源列表；避免使用通配符*，尤其当Allow-Credentials=True时。",
        "patterns": [
            r'allow_origins\s*=\s*["\']\*["\']',
            r'Access-Control-Allow-Origin.*\*',
        ],
    },
    {
        "id": "PY012",
        "category": "加密安全",
        "name": "弱随机数",
        "severity": "MEDIUM",
        "attack_type": "安全场景使用random模块",
        "description": "random模块是伪随机，可预测。用于生成Token、密码重置链接等安全场景时存在风险。",
        "defense": "安全场景使用secrets模块或os.urandom()。",
        "patterns": [
            r'random\.choice\s*\(',
            r'random\.randint\s*\(',
            r'random\.random\s*\(\s*\)',
        ],
        "context_filter": ["secrets", "password", "token", "session", "csrf"],
    },
    {
        "id": "PY013",
        "category": "信息泄露",
        "name": "SSL验证关闭",
        "severity": "MEDIUM",
        "attack_type": "verify=False关闭SSL证书验证",
        "description": "关闭SSL验证使连接易受中间人攻击。",
        "defense": "始终启用SSL验证；使用certifi提供的CA证书包。",
        "patterns": [
            r'verify\s*=\s*False',
            r'ssl\._create_unverified_context',
            r'InsecureRequestWarning',
        ],
    },
    {
        "id": "PY014",
        "category": "AI安全",
        "name": "Prompt注入风险",
        "severity": "HIGH",
        "attack_type": "用户输入直接拼入LLM Prompt",
        "description": "用户输入未经过滤直接拼入LLM提示词，可导致prompt注入——覆盖系统指令、泄露上下文、执行非预期操作。",
        "defense": "分离系统指令与用户输入；使用结构化prompt模板；对用户输入做关键词过滤；限制工具调用权限。",
        "patterns": [
            r'prompt\s*\+',
            r'prompt\s*=.*f["\']',
            r'messages\.append.*\{.*"role".*"user".*input',
            r'chat\.completions.*\+.*user_input',
        ],
    },
    {
        "id": "PY015",
        "category": "安全加固",
        "name": "异常吞没",
        "severity": "LOW",
        "attack_type": "except: pass 隐藏错误",
        "description": "裸except + pass隐藏所有异常，可能掩盖安全漏洞和安全事件。",
        "defense": "捕获具体异常类型；记录日志；避免裸except。",
        "patterns": [
            r'except\s*:\s*\n\s*pass',
            r'except\s*Exception\s*:\s*\n\s*pass',
        ],
    },
]

# ============================================================
# C 语言漏洞检测规则（模式匹配）
# ============================================================

C_RULES = [
    {
        "id": "C001",
        "category": "内存安全",
        "name": "缓冲区溢出-危险函数",
        "severity": "CRITICAL",
        "attack_type": "使用strcpy/strcat/sprintf/gets等无边界检查函数",
        "description": "这些函数不检查目标缓冲区大小，是缓冲区溢出漏洞的最常见根因。攻击者可覆盖返回地址执行任意代码。",
        "defense": "使用strncpy/strncat/snprintf/fgets替代，并严格检查长度。",
        "patterns": [
            r'\bstrcpy\s*\(',
            r'\bstrcat\s*\(',
            r'\bsprintf\s*\(',
            r'\bgets\s*\(',
            r'\bvsprintf\s*\(',
        ],
    },
    {
        "id": "C002",
        "category": "内存安全",
        "name": "格式化字符串漏洞",
        "severity": "CRITICAL",
        "attack_type": "printf系列函数格式串含用户输入",
        "description": "用户输入直接作为printf格式串，可读栈内存、写任意地址（%n）。",
        "defense": "始终使用固定格式串：printf(\"%s\", user_input)。",
        "patterns": [
            r'\bprintf\s*\(\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\)',
            r'\bfprintf\s*\([^,]+,\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\)',
            r'\bsyslog\s*\(\s*[A-Z_]+\s*,\s*[a-zA-Z_]',
        ],
    },
    {
        "id": "C003",
        "category": "内存安全",
        "name": "释放后使用",
        "severity": "CRITICAL",
        "attack_type": "free后继续使用指针",
        "description": "释放后使用（UAF）可导致任意代码执行或信息泄露。",
        "defense": "free后立即置NULL：free(p); p=NULL; 使用前检查非NULL。",
        "patterns": [
            r'free\s*\(\s*(\w+)\s*\)[\s\S]{0,100}?\1\b(?!.*=\s*NULL)',
        ],
    },
    {
        "id": "C004",
        "category": "内存安全",
        "name": "整数溢出",
        "severity": "HIGH",
        "attack_type": "malloc参数未校验溢出",
        "description": "size计算可能整数溢出，导致分配小缓冲区后写入大量数据。",
        "defense": "使用size_t；乘法前检查是否溢出：if(a > SIZE_MAX/b) error();",
        "patterns": [
            r'malloc\s*\(\s*\w+\s*\*\s*\w+\s*\)',
            r'malloc\s*\(\s*sizeof\s*\([^)]+\)\s*\*\s*\w+\s*\)',
        ],
    },
    {
        "id": "C005",
        "category": "命令注入",
        "name": "C命令注入",
        "severity": "CRITICAL",
        "attack_type": "system/popen拼接用户输入",
        "description": "system()和popen()通过shell执行命令，用户输入可注入任意命令。",
        "defense": "使用execve/execvp直接执行（不经shell）；或严格白名单校验输入。",
        "patterns": [
            r'\bsystem\s*\(\s*[^"]',
            r'\bpopen\s*\(\s*[^"]',
        ],
    },
    {
        "id": "C006",
        "category": "内存安全",
        "name": "内存泄漏",
        "severity": "MEDIUM",
        "attack_type": "malloc无对应free",
        "description": "动态分配的内存未释放，长期运行导致内存耗尽。",
        "defense": "确保每个malloc有对应free；使用RAII模式或valgrind检测。",
        "patterns": [
            r'malloc\s*\(\s*[^)]+\s*\)(?![\s\S]{0,200}?\bfree\b)',
        ],
    },
    {
        "id": "C007",
        "category": "竞态条件",
        "name": "TOCTOU竞态",
        "severity": "HIGH",
        "attack_type": "access/open检查-使用竞态",
        "description": "检查文件权限和使用文件之间存在时间窗口，攻击者可在此期间替换文件（符号链接攻击）。",
        "defense": "使用fstat检查已打开的fd而非access；设置O_NOFOLLOW标志。",
        "patterns": [
            r'access\s*\([^)]+\)[\s\S]{0,200}?(open|fopen)\s*\(',
        ],
    },
    {
        "id": "C008",
        "category": "认证安全",
        "name": "C硬编码密钥",
        "severity": "HIGH",
        "attack_type": "C源码中硬编码密码/密钥",
        "description": "密钥硬编码在源码中，编译后的二进制也可被逆向提取。",
        "defense": "运行时从环境变量或配置文件读取；使用密钥管理服务。",
        "patterns": [
            r'#define\s+\w*(PASSWORD|SECRET|KEY|TOKEN)\w*\s+["\']',
            r'char\s+\w*(password|secret|key|token)\w*\[\]\s*=\s*["\']',
        ],
    },
    {
        "id": "C009",
        "category": "内存安全",
        "name": "双重释放",
        "severity": "CRITICAL",
        "attack_type": "同一指针被free两次",
        "description": "双重释放破坏堆管理器元数据，可导致任意代码执行。",
        "defense": "free后立即置NULL；使用引用计数或智能指针模式。",
        "patterns": [
            r'free\s*\(\s*(\w+)\s*\)[\s\S]{0,500}?free\s*\(\s*\1\s*\)',
        ],
    },
    {
        "id": "C010",
        "category": "安全加固",
        "name": "不安全随机数",
        "severity": "MEDIUM",
        "attack_type": "安全场景使用rand()",
        "description": "rand()是伪随机且可预测，不适合安全场景（如生成Token或密钥）。",
        "defense": "使用/dev/urandom或getrandom()系统调用生成安全随机数。",
        "patterns": [
            r'\brand\s*\(\s*\)(?![\s\S]{0,50}seed)',
            r'\bsrand\s*\(\s*time',
        ],
    },
]

# ============================================================
# 通用规则（跨语言）
# ============================================================

GENERIC_RULES = [
    {
        "id": "GEN001",
        "category": "信息泄露",
        "name": "敏感信息注释",
        "severity": "LOW",
        "attack_type": "注释中包含敏感信息",
        "description": "注释中包含密码、Token、IP等敏感信息。",
        "defense": "清理注释中的敏感信息；使用配置管理而非注释记录凭据。",
        "patterns": [
            r'#.*(?:password|passwd|pwd|secret|token|api_key)\s*[=:]\s*\S+',
            r'//.*(?:password|passwd|pwd|secret|token|api_key)\s*[=:]\s*\S+',
            r'/\*.*(?:password|passwd|pwd|secret|token|api_key).*\*/',
        ],
    },
    {
        "id": "GEN002",
        "category": "供应链安全",
        "name": "不安全依赖版本",
        "severity": "MEDIUM",
        "attack_type": "使用已知有漏洞的依赖版本",
        "description": "requirements.txt或package.json中可能包含已知漏洞的依赖版本。",
        "defense": "定期使用safety/pip-audit/npm audit检查依赖；锁定版本范围。",
        "patterns": [
            r'==(0\.|1\.[0-9]\.)',  # 疑似旧版本
        ],
        "file_patterns": ["requirements.txt", "package.json"],
    },
]

# 风险等级权重
SEVERITY_WEIGHT = {
    "CRITICAL": 10,
    "HIGH": 7,
    "MEDIUM": 4,
    "LOW": 1,
}

# 风险等级颜色（终端）
SEVERITY_COLOR = {
    "CRITICAL": "\033[91m",  # 红色
    "HIGH": "\033[93m",      # 黄色
    "MEDIUM": "\033[96m",    # 青色
    "LOW": "\033[37m",       # 白色
}
