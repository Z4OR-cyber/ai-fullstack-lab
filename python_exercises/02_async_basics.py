"""
Python 异步编程练习
=====================================
对应学习路线图：第一阶段 - 筑基期 - 异步编程
目标：掌握 async/await、协程、事件循环，最终写一个异步爬虫

运行方式：python 02_async_basics.py
"""

import asyncio
import time
import random

# 知识点：协程、await、事件循环、gather、Semaphore、Queue、async with

async def say_hello():
    print("Hello")
    await asyncio.sleep(1)
    print("World")

def say_hello_sync():
    print("Hello")
    time.sleep(1)
    print("World")

print("=== 同步版本 ===")
start = time.time()
say_hello_sync()
print(f"耗时: {time.time() - start:.2f}s\n")

print("=== 异步版本 ===")
start = time.time()
asyncio.run(say_hello())
print(f"耗时: {time.time() - start:.2f}s\n")


async def fetch_data(name, delay):
    print(f"  [{name}] 开始请求...")
    await asyncio.sleep(delay)
    print(f"  [{name}] 请求完成 (耗时{delay}s)")
    return f"{name}_data"

async def serial_fetch():
    results = []
    results.append(await fetch_data("A", 1))
    results.append(await fetch_data("B", 2))
    results.append(await fetch_data("C", 1))
    return results

async def concurrent_fetch():
    results = await asyncio.gather(
        fetch_data("A", 1),
        fetch_data("B", 2),
        fetch_data("C", 1),
    )
    return results

async def test_concurrency():
    print("=== 串行执行 ===")
    start = time.time()
    results = await serial_fetch()
    print(f"结果: {results}, 总耗时: {time.time() - start:.2f}s\n")

    print("=== 并发执行 (gather) ===")
    start = time.time()
    results = await concurrent_fetch()
    print(f"结果: {results}, 总耗时: {time.time() - start:.2f}s\n")

asyncio.run(test_concurrency())


async def slow_task(name, duration):
    print(f"  [{name}] 任务开始，预计{duration}s完成")
    await asyncio.sleep(duration)
    return f"{name}完成"

async def test_timeout():
    print("--- 正常任务（1s < 2s超时）---")
    try:
        result = await asyncio.wait_for(slow_task("快速", 1), timeout=2)
        print(f"  结果: {result}")
    except asyncio.TimeoutError:
        print("  任务超时！")

    print("\n--- 超时任务（3s > 2s超时）---")
    try:
        result = await asyncio.wait_for(slow_task("慢速", 3), timeout=2)
        print(f"  结果: {result}")
    except asyncio.TimeoutError:
        print("  ❌ 任务超时！")

    print("\n--- create_task 后台任务 ---")
    task = asyncio.create_task(slow_task("后台", 1))
    print("  主任务继续执行其他工作...")
    await asyncio.sleep(0.5)
    print("  主任务工作完成，等待后台任务...")
    result = await task
    print(f"  后台任务结果: {result}")

asyncio.run(test_timeout())


async def crawl_page(url, semaphore):
    async with semaphore:
        delay = random.uniform(0.5, 1.5)
        print(f"  [{url}] 开始爬取 (模拟耗时{delay:.1f}s)")
        await asyncio.sleep(delay)
        print(f"  [{url}] 爬取完成")
        return f"{url}_content"

async def test_semaphore():
    semaphore = asyncio.Semaphore(3)
    urls = [f"page_{i}" for i in range(1, 11)]

    start = time.time()
    results = await asyncio.gather(
        *[crawl_page(url, semaphore) for url in urls]
    )
    elapsed = time.time() - start
    print(f"\n  爬取{len(urls)}页, 并发上限3, 总耗时: {elapsed:.2f}s")
    print(f"  如果串行需约10s, 并发3约需3-4s\n")

asyncio.run(test_semaphore())


async def producer(queue):
    for i in range(1, 6):
        item = f"task_{i}"
        await queue.put(item)
        print(f"  [生产者] 放入 {item}")
        await asyncio.sleep(0.3)
    await queue.put(None)
    await queue.put(None)
    print("  [生产者] 生产完毕")

async def consumer(name, queue):
    while True:
        item = await queue.get()
        if item is None:
            print(f"  [消费者{name}] 收到结束信号，退出")
            break
        print(f"  [消费者{name}] 处理 {item}")
        await asyncio.sleep(random.uniform(0.5, 1.0))
        print(f"  [消费者{name}] 完成 {item}")

async def test_producer_consumer():
    queue = asyncio.Queue(maxsize=3)
    await asyncio.gather(
        producer(queue),
        consumer("A", queue),
        consumer("B", queue),
    )

asyncio.run(test_producer_consumer())


async def fetch_url(url, semaphore, timeout=2):
    async with semaphore:
        try:
            delay = random.uniform(0.3, 1.5)
            await asyncio.wait_for(asyncio.sleep(delay), timeout=timeout)
            if random.random() < 0.1:
                raise ConnectionError(f"{url} 连接失败")
            return {"url": url, "status": 200, "data": f"<html>{url}的内容</html>"}
        except asyncio.TimeoutError:
            return {"url": url, "status": 408, "error": "请求超时"}
        except ConnectionError as e:
            return {"url": url, "status": 503, "error": str(e)}

async def crawl_site(base_url, num_pages, max_concurrency=5):
    semaphore = asyncio.Semaphore(max_concurrency)
    urls = [f"{base_url}/page/{i}" for i in range(1, num_pages + 1)]

    print(f"\n🕷️ 开始爬取 {base_url} ({num_pages}页, 并发{max_concurrency})")
    start = time.time()

    results = await asyncio.gather(
        *[fetch_url(url, semaphore) for url in urls]
    )

    elapsed = time.time() - start
    success = sum(1 for r in results if r["status"] == 200)
    failed = len(results) - success

    print(f"✅ 爬取完成: 成功{success} 失败{failed} 耗时{elapsed:.2f}s")
    for r in results:
        status = "✅" if r["status"] == 200 else "❌"
        print(f"  {status} {r['url']} -> {r['status']}")

    return results

async def main():
    print("=" * 60)
    print("🕷️ 异步爬虫演示")
    print("=" * 60)

    all_results = await asyncio.gather(
        crawl_site("https://example.com", 8, max_concurrency=3),
        crawl_site("https://docs.python.org", 5, max_concurrency=3),
    )

    total = sum(len(r) for r in all_results)
    print(f"\n📊 总计爬取 {total} 个页面")

asyncio.run(main())
