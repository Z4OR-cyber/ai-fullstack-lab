#!/usr/bin/env python3
"""Kimi K3 编码助手 - 通过K3 API完成编码任务"""

import os
import sys
import time
import argparse
import json

from coze_workload_identity import requests


KIMI_BASE_URL = "https://api.moonshot.cn/v1"
KIMI_MODEL = "kimi-k3"

DEFAULT_SYSTEM = """你是一个资深前端开发专家，精通HTML/CSS/JavaScript单文件游戏开发。
用户会给你一个编码任务和可选的上下文代码。请：
1. 仔细阅读任务描述和上下文代码
2. 输出完整的、可直接使用的代码
3. 只输出代码和必要的简短注释，不要有多余的解释说明
4. 如果是基于现有代码修改，输出完整的修改后代码，不要只输出diff
5. 代码风格保持与上下文一致"""

MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]  # 秒


def call_kimi(task, context=None, max_tokens=8192, system_prompt=None):
    """调用Kimi K3 API"""
    credential = os.getenv("COZE_KIMI_API_KEY_7665653061028692008")
    if not credential:
        raise ValueError("缺少Kimi API凭证，请检查环境变量 COZE_KIMI_API_KEY_7665653061028692008")

    url = f"{KIMI_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {credential}",
    }

    messages = []
    sys_prompt = system_prompt if system_prompt else DEFAULT_SYSTEM
    messages.append({"role": "system", "content": sys_prompt})

    user_content = f"## 任务\n{task}"
    if context:
        # 如果是文件路径，读取文件内容
        if os.path.isfile(context):
            with open(context, 'r', encoding='utf-8') as f:
                context = f.read()
        user_content += f"\n\n## 上下文代码\n```\n{context}\n```"
    
    messages.append({"role": "user", "content": user_content})

    payload = {
        "model": KIMI_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
    }

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            data = response.json()

            if "error" in data:
                err_msg = data["error"].get("message", str(data["error"]))
                err_type = data["error"].get("type", "")
                if "overloaded" in err_type or "overloaded" in err_msg.lower():
                    wait = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 30
                    print(f"[K3引擎过载] {attempt+1}/{MAX_RETRIES}次重试，等待{wait}秒...", file=sys.stderr)
                    time.sleep(wait)
                    last_error = err_msg
                    continue
                else:
                    raise Exception(f"API错误: {err_msg} (type={err_type})")

            content = data["choices"][0]["message"]["content"]
            reasoning = data["choices"][0]["message"].get("reasoning_content", "")
            usage = data.get("usage", {})

            # 输出使用统计到stderr
            if usage:
                print(f"[Token统计] prompt={usage.get('prompt_tokens',0)}, "
                      f"completion={usage.get('completion_tokens',0)}, "
                      f"cached={usage.get('prompt_tokens_details',{}).get('cached_tokens',0)}, "
                      f"reasoning={usage.get('completion_tokens_details',{}).get('reasoning_tokens',0)}",
                      file=sys.stderr)

            return content

        except requests.exceptions.RequestException as e:
            wait = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 30
            print(f"[请求异常] {attempt+1}/{MAX_RETRIES}次重试，等待{wait}秒... {str(e)}", file=sys.stderr)
            time.sleep(wait)
            last_error = str(e)

    raise Exception(f"K3 API调用失败，重试{MAX_RETRIES}次后仍失败: {last_error}")


def main():
    parser = argparse.ArgumentParser(description="Kimi K3 编码助手")
    parser.add_argument("--task", required=True, help="编码任务描述")
    parser.add_argument("--context", default=None, help="上下文代码或文件路径")
    parser.add_argument("--max-tokens", type=int, default=8192, help="最大输出token数")
    parser.add_argument("--system", default=None, help="自定义system prompt")
    parser.add_argument("--output", default="kimi_k3_output.txt", help="输出文件路径")
    args = parser.parse_args()

    result = call_kimi(args.task, args.context, args.max_tokens, args.system)

    # 保存到文件
    output_path = os.path.join(os.getcwd(), args.output)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result)

    # 同时输出到stdout
    print(result)
    print(f"\n[已保存到 {output_path}]", file=sys.stderr)


if __name__ == "__main__":
    main()
