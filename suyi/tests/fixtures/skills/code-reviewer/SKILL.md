---
name: code-reviewer
description: 审查 Python 代码质量，检测安全漏洞和代码异味
---
# 代码审查技能

## 使用步骤

1. 接收用户提供的代码文件路径
2. 使用 `read_file` 工具读取代码内容
3. 逐模块分析代码质量：
   - 安全漏洞（SQL 注入、命令注入等）
   - 代码异味（重复代码、过长函数等）
   - 类型标注完整性
   - 文档字符串覆盖
4. 输出结构化审查报告

## 注意事项

- 仅审查 Python 文件（.py）
- 不修改用户代码，只输出审查报告
- 对于疑似安全问题，标注为 `[SECURITY]` 前缀
- 使用 `grep` 搜索已知危险模式

## 附件

- `scripts/scan_patterns.py` — 危险模式定义
- `references/security_checklist.md` — 安全检查清单
