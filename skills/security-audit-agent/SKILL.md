---
name: security-audit-agent
description: 代码安全审计工具。扫描Python/C代码中的安全漏洞，检测SQL注入、命令注入、XSS、路径遍历、硬编码密钥、不安全反序列化、弱加密、缓冲区溢出、格式化字符串等15类安全问题，并生成包含风险评级和修复建议的结构化审计报告。当用户需要代码安全扫描、漏洞检测、安全审计、代码审查、安全检查、code review安全方面、查找代码中的安全漏洞、代码安全分析、渗透测试代码审查、安全合规检查时使用。
---

# 安全审计Agent

扫描代码中的安全漏洞，基于15类攻击共性检测 + 10层防御联动体系，生成包含风险评级和修复建议的审计报告。

## 工作流程

1. **接收目标**：用户提供文件路径、目录路径或代码片段
2. **自动识别语言**：根据文件扩展名选择对应规则集（.py → Python规则，.c/.h → C规则）
3. **执行扫描**：
   - Python代码：AST语法树分析 + 正则模式匹配双重检测
   - C代码：正则模式匹配检测
   - 通用规则：注释中的敏感信息、依赖版本检查
4. **生成报告**：按风险等级排序，输出漏洞详情 + 修复建议 + 防御体系建议

## 执行方式

### 扫描文件或目录

```bash
cd skills/security-audit-agent
python main.py <目标路径> --format markdown
```

参数说明：
- `path`：要扫描的文件或目录路径（必填）
- `--format`：报告格式，可选 terminal / markdown / json（默认 terminal）
- `--output`：报告输出目录（仅 markdown/json 时有效，不指定则直接输出到终端）

### 扫描代码片段

如果用户提供的是代码片段而非文件，先将代码保存为临时文件再扫描：
```bash
python main.py /tmp/code_snippet.py --format terminal
```

## 检测能力

### Python漏洞（15类）

| 类别 | 检测项 | 风险等级 |
|------|--------|---------|
| 注入 | SQL注入（f-string/%/拼接）、命令注入（os.system/eval/exec）、SSTI模板注入 | CRITICAL |
| 跨站 | XSS跨站脚本（Markup/safe/innerHTML） | HIGH |
| 文件 | 路径遍历（open拼接用户输入） | HIGH |
| 认证 | 硬编码密钥、弱密码哈希（MD5/SHA1）、JWT弱配置 | HIGH |
| 授权 | 不安全反序列化（pickle/yaml.load） | CRITICAL |
| 配置 | 调试模式、CORS过宽 | MEDIUM |
| 加密 | 弱随机数（安全场景用random） | MEDIUM |
| 信息 | SSL验证关闭 | MEDIUM |
| AI安全 | Prompt注入（用户输入拼入LLM提示词） | HIGH |
| 加固 | 异常吞没（except: pass） | LOW |

### C漏洞（10类）

| 类别 | 检测项 | 风险等级 |
|------|--------|---------|
| 内存安全 | 缓冲区溢出（strcpy/gets/sprintf）、格式化字符串、UAF、双重释放 | CRITICAL |
| 内存安全 | 整数溢出（malloc乘法）、内存泄漏 | HIGH/MEDIUM |
| 命令注入 | system/popen拼接用户输入 | CRITICAL |
| 竞态 | TOCTOU（access+open） | HIGH |
| 认证 | 硬编码密钥 | HIGH |
| 加固 | 不安全随机数（rand/srand(time)） | MEDIUM |

### 通用规则

- 注释中的敏感信息（密码/Token/密钥）
- 不安全依赖版本

## 报告格式

### Markdown报告包含：
1. 扫描统计（文件数/行数/问题数/风险评分）
2. 风险等级说明
3. 每个漏洞的详细信息（文件位置、攻击类型、描述、代码片段、修复建议）
4. 防御体系建议（按类别汇总）

### 风险评分规则
- CRITICAL = 10分, HIGH = 7分, MEDIUM = 4分, LOW = 1分
- 总分越高，整体安全风险越大

## 输出要求

- 扫描完成后，向用户展示终端摘要（问题数量和风险分布）
- 如果发现 CRITICAL 或 HIGH 级别问题，明确提醒用户优先处理
- Markdown报告保存为文件时，告知用户文件路径
- 对于代码片段扫描，直接在终端输出结果

## 边界情况

- 语法错误的Python文件：跳过AST分析，仅做模式匹配
- 不支持的文件类型：仅应用通用规则
- 空文件或无代码的文件：正常扫描，报告0问题
- 大型项目：递归扫描，自动排除 .git/node_modules/__pycache__ 等目录
