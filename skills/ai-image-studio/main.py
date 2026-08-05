#!/usr/bin/env python3
"""AI作图工坊 — 多引擎图片生成器"""

import os
import sys
import time
import argparse
import base64

from coze_workload_identity import requests

# === 凭证读取 ===
SKILL_ID = "7662704699870658614"

def get_credential(name: str) -> str | None:
    """读取凭据环境变量（值可能是COZE_CRED_DUMMY占位符，由auth proxy自动替换真实值）"""
    env_key = f"COZE_{name.upper()}_{SKILL_ID}"
    return os.getenv(env_key)


# === 引擎实现 ===

def generate_gpt(prompt: str, size: str, count: int, negative: str, output_dir: str) -> list[str]:
    """GPT Image 2 引擎 (via Apiframe v2)"""
    api_key = get_credential("MJ_PROXY")
    if not api_key:
        raise ValueError("未配置 Apiframe API Key (mj_proxy)")

    full_prompt = prompt
    if negative:
        full_prompt += f" Avoid: {negative}"

    url = "https://api.apiframe.ai/v2/images/generate"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    payload = {"prompt": full_prompt, "model": "gpt-image-2"}

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code >= 400:
        raise Exception(f"GPT Image API error: {resp.status_code} {resp.text}")

    data = resp.json()
    job_id = data.get("jobId")
    if not job_id:
        raise Exception(f"GPT Image: no jobId: {data}")

    print(f"  ⏳ GPT Image job submitted ({job_id}), polling...")

    status_url = f"https://api.apiframe.ai/v2/jobs/{job_id}"
    for _ in range(120):
        time.sleep(3)
        result_resp = requests.get(status_url, headers={"X-API-Key": api_key}, timeout=30)
        result_data = result_resp.json()
        status = result_data.get("status", "").upper()

        if status == "COMPLETED":
            result = result_data.get("result", {})
            images = result.get("images", [])
            if images:
                paths = []
                for i, img_url in enumerate(images):
                    img_resp = requests.get(img_url, timeout=60)
                    fpath = os.path.join(output_dir, f"gpt_{int(time.time())}_{i}.png")
                    with open(fpath, "wb") as f:
                        f.write(img_resp.content)
                    paths.append(fpath)
                return paths
            raise Exception("GPT Image: completed but no images")
        elif status in ("FAILED", "ERROR"):
            raise Exception(f"GPT Image job failed: {result_data}")

    raise Exception("GPT Image: timeout waiting for result")


def generate_flux(prompt: str, size: str, count: int, negative: str, output_dir: str) -> list[str]:
    """FLUX 2 Pro 引擎 (via BFL API - api.bfl.ai)"""
    api_key = get_credential("BFL_KEY")
    if not api_key:
        raise ValueError("未配置 BFL API Key (bfl_key)")

    full_prompt = prompt
    if negative:
        full_prompt += f" Avoid: {negative}"

    # BFL new endpoint: api.bfl.ai, model: flux-2-pro-preview
    url = "https://api.bfl.ai/v1/flux-2-pro-preview"
    headers = {
        "x-key": api_key,
        "Content-Type": "application/json",
        "accept": "application/json"
    }

    w, h = size.split("x")
    payload = {
        "prompt": full_prompt,
        "width": int(w),
        "height": int(h)
    }

    # Submit job
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code >= 400:
        raise Exception(f"FLUX API error: {resp.status_code} {resp.text}")

    data = resp.json()
    polling_url = data.get("polling_url")
    if not polling_url:
        # Fallback: construct from id
        job_id = data.get("id")
        if not job_id:
            raise Exception(f"FLUX: no polling_url or id in response: {data}")
        polling_url = f"https://api.bfl.ai/v1/get_result?id={job_id}"

    print(f"  ⏳ FLUX job submitted, polling...")

    # Poll for result
    for _ in range(120):  # max 10 min
        time.sleep(3)
        result_resp = requests.get(polling_url, headers={"x-key": api_key, "accept": "application/json"}, timeout=30)
        result_data = result_resp.json()
        status = result_data.get("status")

        if status == "Ready":
            image_url = result_data.get("result", {}).get("sample")
            if image_url:
                paths = []
                img_resp = requests.get(image_url, timeout=60)
                fpath = os.path.join(output_dir, f"flux_{int(time.time())}_0.png")
                with open(fpath, "wb") as f:
                    f.write(img_resp.content)
                paths.append(fpath)
                return paths
            raise Exception("FLUX: Ready but no image URL")
        elif status in ("Failed", "Error"):
            raise Exception(f"FLUX job failed: {result_data}")

    raise Exception("FLUX: timeout waiting for result")


def generate_google(prompt: str, size: str, count: int, negative: str, output_dir: str) -> list[str]:
    """Google Nano Banana 引擎 (via Apiframe v2 - nano-banana model)"""
    api_key = get_credential("MJ_PROXY")
    if not api_key:
        raise ValueError("未配置 Apiframe API Key (mj_proxy) - Google引擎通过Apiframe代理调用")

    full_prompt = prompt
    if negative:
        full_prompt += f" Avoid: {negative}"

    # Convert size to aspect ratio
    w, h = size.split("x")
    from math import gcd
    g = gcd(int(w), int(h))
    aspect_ratio = f"{int(w)//g}:{int(h)//g}"

    url = "https://api.apiframe.ai/v2/images/generate"
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": full_prompt,
        "model": "nano-banana"
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code >= 400:
        raise Exception(f"Nano Banana API error: {resp.status_code} {resp.text}")

    data = resp.json()
    job_id = data.get("jobId")
    if not job_id:
        raise Exception(f"Nano Banana: no jobId: {data}")

    print(f"  ⏳ Nano Banana job submitted ({job_id}), polling...")

    status_url = f"https://api.apiframe.ai/v2/jobs/{job_id}"
    for _ in range(120):
        time.sleep(3)
        result_resp = requests.get(status_url, headers={"X-API-Key": api_key}, timeout=30)
        result_data = result_resp.json()
        status = result_data.get("status", "").upper()

        if status == "COMPLETED":
            result = result_data.get("result", {})
            images = result.get("images", [])
            if images:
                paths = []
                for i, img_url in enumerate(images):
                    img_resp = requests.get(img_url, timeout=60)
                    fpath = os.path.join(output_dir, f"google_{int(time.time())}_{i}.png")
                    with open(fpath, "wb") as f:
                        f.write(img_resp.content)
                    paths.append(fpath)
                return paths
            raise Exception("Nano Banana: completed but no images")
        elif status in ("FAILED", "ERROR"):
            raise Exception(f"Nano Banana job failed: {result_data}")

    raise Exception("Nano Banana: timeout waiting for result")


def generate_qwen(prompt: str, size: str, count: int, negative: str, output_dir: str) -> list[str]:
    """Qwen Image 2 Pro 引擎 (via Apiframe v2 - 支持中文prompt)"""
    api_key = get_credential("MJ_PROXY")
    if not api_key:
        raise ValueError("未配置 Apiframe API Key (mj_proxy)")

    full_prompt = prompt  # Qwen原生支持中文
    if negative:
        full_prompt += f" 避免: {negative}"

    url = "https://api.apiframe.ai/v2/images/generate"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    payload = {"prompt": full_prompt, "model": "qwen-image-2-pro"}

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code >= 400:
        raise Exception(f"Qwen API error: {resp.status_code} {resp.text}")

    data = resp.json()
    job_id = data.get("jobId")
    if not job_id:
        raise Exception(f"Qwen: no jobId: {data}")

    print(f"  ⏳ Qwen Image job submitted ({job_id}), polling...")

    status_url = f"https://api.apiframe.ai/v2/jobs/{job_id}"
    for _ in range(120):
        time.sleep(3)
        result_resp = requests.get(status_url, headers={"X-API-Key": api_key}, timeout=30)
        result_data = result_resp.json()
        status = result_data.get("status", "").upper()

        if status == "COMPLETED":
            result = result_data.get("result", {})
            images = result.get("images", [])
            if images:
                paths = []
                for i, img_url in enumerate(images):
                    img_resp = requests.get(img_url, timeout=60)
                    fpath = os.path.join(output_dir, f"qwen_{int(time.time())}_{i}.png")
                    with open(fpath, "wb") as f:
                        f.write(img_resp.content)
                    paths.append(fpath)
                return paths
            raise Exception("Qwen: completed but no images")
        elif status in ("FAILED", "ERROR"):
            raise Exception(f"Qwen job failed: {result_data}")

    raise Exception("Qwen: timeout waiting for result")


def generate_mj(prompt: str, size: str, count: int, negative: str, output_dir: str) -> list[str]:
    """Midjourney 引擎 (via Apiframe v2)"""
    api_key = get_credential("MJ_PROXY")
    if not api_key:
        raise ValueError("未配置 Apiframe API Key (mj_proxy)")

    full_prompt = prompt
    if negative:
        full_prompt += f" --no {negative}"

    # Convert size to aspect ratio
    w, h = size.split("x")
    from math import gcd
    g = gcd(int(w), int(h))
    aspect_ratio = f"{int(w)//g}:{int(h)//g}"

    # Apiframe v2 API
    url = "https://api.apiframe.ai/v2/images/generate"
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": full_prompt,
        "model": "midjourney",
        "midjourneyParams": {
            "aspect_ratio": aspect_ratio
        }
    }

    # Submit job
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code >= 400:
        raise Exception(f"MJ API error: {resp.status_code} {resp.text}")

    data = resp.json()
    job_id = data.get("jobId")
    if not job_id:
        raise Exception(f"MJ: no jobId in response: {data}")

    print(f"  ⏳ MJ job submitted ({job_id}), polling...")

    # Poll for result via jobs endpoint
    status_url = f"https://api.apiframe.ai/v2/jobs/{job_id}"
    for _ in range(120):  # MJ can take 1-2 min
        time.sleep(5)
        result_resp = requests.get(status_url, headers={"X-API-Key": api_key}, timeout=30)
        result_data = result_resp.json()
        status = result_data.get("status", "").upper()

        if status == "COMPLETED":
            result = result_data.get("result", {})
            images = result.get("images", [])
            if images:
                paths = []
                for i, img_url in enumerate(images):
                    img_resp = requests.get(img_url, timeout=60)
                    fpath = os.path.join(output_dir, f"mj_{int(time.time())}_{i}.png")
                    with open(fpath, "wb") as f:
                        f.write(img_resp.content)
                    paths.append(fpath)
                return paths
            raise Exception("MJ: completed but no images")
        elif status in ("FAILED", "ERROR"):
            raise Exception(f"MJ job failed: {result_data}")

    raise Exception("MJ: timeout waiting for result")


# === 引擎注册表 ===
ENGINES = {
    "gpt": {"func": generate_gpt, "name": "GPT Image 2"},
    "flux": {"func": generate_flux, "name": "FLUX 2 Pro"},
    "google": {"func": generate_google, "name": "Nano Banana"},
    "qwen": {"func": generate_qwen, "name": "Qwen Image 2 Pro"},
    "mj": {"func": generate_mj, "name": "Midjourney"},
}


def main():
    parser = argparse.ArgumentParser(description="AI作图工坊 — 多引擎图片生成")
    parser.add_argument("--prompt", required=True, help="图片描述")
    parser.add_argument("--engine", default="flux", choices=ENGINES.keys(), help="引擎 (默认 flux)")
    parser.add_argument("--size", default="1024x1024", help="输出尺寸 (默认 1024x1024)")
    parser.add_argument("--count", type=int, default=1, help="生成数量 (默认 1)")
    parser.add_argument("--negative", default="", help="负面提示词")
    parser.add_argument("--output", default="./output", help="输出目录")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    engine_info = ENGINES[args.engine]
    print(f"🎨 引擎: {engine_info['name']}")
    print(f"📝 Prompt: {args.prompt}")
    print(f"📐 Size: {args.size}")
    print(f"🔢 Count: {args.count}")
    if args.negative:
        print(f"🚫 Negative: {args.negative}")
    print("---")

    try:
        paths = engine_info["func"](
            prompt=args.prompt,
            size=args.size,
            count=args.count,
            negative=args.negative,
            output_dir=args.output
        )
        print(f"\n✅ 生成成功！共 {len(paths)} 张图片:")
        for p in paths:
            print(f"  📄 {p}")
    except Exception as e:
        print(f"\n❌ 生成失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
