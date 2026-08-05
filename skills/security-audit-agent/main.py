#!/usr/bin/env python3
"""
安全审计Agent - 入口文件
扫描代码文件/目录中的安全漏洞，生成审计报告

用法:
  python main.py <文件或目录路径> [--format markdown|json|terminal] [--output <输出目录>]

示例:
  python main.py ./my_project
  python main.py ./app.py --format json
  python main.py ./src --format markdown --output ./reports
"""

import sys
import os
import argparse

# 将脚本所在目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanner import CodeScanner
from report import ReportGenerator


def scan_target(target_path: str, output_format: str = "terminal", output_dir: str = None):
    """扫描目标路径并生成报告"""

    scanner = CodeScanner()

    if os.path.isfile(target_path):
        scanner.scan_file(target_path)
    elif os.path.isdir(target_path):
        scanner.scan_directory(target_path)
    else:
        print(f"错误: 路径不存在 - {target_path}")
        sys.exit(1)

    report = ReportGenerator(scanner.findings, scanner.get_stats())

    # 输出报告
    if output_format == "terminal":
        print(report.terminal_output())
    elif output_format == "markdown":
        md = report.markdown_report()
        if output_dir:
            path = report.save_report(output_dir, "markdown")
            print(f"报告已保存: {path}")
            print(f"\n摘要: {scanner.get_stats()}")
        else:
            print(md)
    elif output_format == "json":
        if output_dir:
            path = report.save_report(output_dir, "json")
            print(f"报告已保存: {path}")
        else:
            print(report.json_report())
    else:
        print(report.terminal_output())

    # 返回退出码：有CRITICAL/HIGH则返回1
    stats = scanner.get_stats()
    if stats["critical"] > 0 or stats["high"] > 0:
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="安全审计Agent - 代码安全漏洞扫描器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
支持的漏洞类型:
  Python: SQL注入、命令注入、SSTI、XSS、路径遍历、硬编码密钥、
          弱哈希、JWT弱配置、不安全反序列化、调试模式、CORS过宽、
          弱随机数、SSL关闭、Prompt注入、异常吞没
  C:      缓冲区溢出、格式化字符串、UAF、整数溢出、命令注入、
          内存泄漏、TOCTOU、硬编码密钥、双重释放、不安全随机数
  通用:   敏感信息注释、不安全依赖版本

风险等级: CRITICAL > HIGH > MEDIUM > LOW
        """
    )
    parser.add_argument("path", help="要扫描的文件或目录路径")
    parser.add_argument("--format", "-f", default="terminal",
                        choices=["terminal", "markdown", "json"],
                        help="报告格式 (默认: terminal)")
    parser.add_argument("--output", "-o", default=None,
                        help="报告输出目录 (仅markdown/json格式)")

    args = parser.parse_args()

    exit_code = scan_target(args.path, args.format, args.output)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
