"""
异步编程扩展练习 —— 的作答
=====================================
完成 02_async_basics.py 末尾的 5 道扩展练习
"""

import asyncio
import time
import random
import json
import os


# =============================================================================
# 扩展 2：异步重试机制（失败自动重试 3 次）
# =============================================================================
async def fetch_with_retry(url, max_retries=3, delay=0.5):
    """带指数退避的异步重试"""
    for attempt in range(1, max_retries + 1):
        try:
            # 模拟请求，20% 概率失败
            await asyncio.sleep(random.uniform(0.2, 0.8))
            if random.random() < 0.2:
                raise ConnectionError(f"{url} 连接失败")
            return {"url": url, "status": 200, "attempt": attempt}

        except (ConnectionError, asyncio.TimeoutError) as e:
            if attempt == max_retries:
                return {"url": url, "status": 503, "error": str(e), "attempt": attempt}
            backoff = delay * (2 ** (attempt - 1))  # 指数退避: 0.5, 1.0, 2.0
            print(f"  ⚠️ [{url}] 第{attempt}次失败, {backoff}s后重试")
            await asyncio.sleep(backoff)


async def test_retry():
    print("=== 扩展2: 异步重试 ===")
    urls = [f"retry_page_{i}" for i in range(1, 7)]
    results = await asyncio.gather(*[fetch_with_retry(url) for url in urls])
    for r in results:
        status = "✅" if r["status"] == 200 else "❌"
        print(f"  {status} {r['url']} -> {r['status']} (尝试{r['attempt']}次)")


# =============================================================================
# 扩展 3：持续运行的任务队列（不断添加新 URL）
# =============================================================================
class CrawlScheduler:
    """持续运行的异步任务调度器"""

    def __init__(self, max_workers=3):
        self.queue = asyncio.Queue()
        self.max_workers = max_workers
        self.results = []
        self._running = True

    async def add_urls(self, urls):
        """持续添加 URL 到队列"""
        for url in urls:
            await self.queue.put(url)
            print(f"  [调度器] 添加 {url}")
            await asyncio.sleep(0.1)

    async def worker(self, worker_id):
        """工作协程：持续从队列取 URL 处理"""
        while self._running or not self.queue.empty():
            try:
                url = await asyncio.wait_for(self.queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            if url is None:  # 哨兵信号
                self.queue.put_nowait(None)  # 传递给其他 worker
                break

            delay = random.uniform(0.3, 0.8)
            await asyncio.sleep(delay)
            result = {"url": url, "status": 200, "worker": worker_id}
            self.results.append(result)
            print(f"  [Worker-{worker_id}] 完成 {url}")

    async def stop(self):
        """停止调度器"""
        self._running = False
        await self.queue.put(None)

    async def run(self, url_batches):
        """运行调度器：分批添加 URL，同时启动 worker"""
        workers = [asyncio.create_task(self.worker(i)) for i in range(self.max_workers)]

        for batch in url_batches:
            await self.add_urls(batch)
            await asyncio.sleep(0.5)  # 模拟间隔

        await self.stop()

        # 等待所有 worker 完成
        await asyncio.gather(*workers)
        print(f"  [调度器] 全部完成, 共处理 {len(self.results)} 个URL")


async def test_scheduler():
    print("\n=== 扩展3: 持续任务队列 ===")
    scheduler = CrawlScheduler(max_workers=3)
    batches = [
        [f"batch1_{i}" for i in range(3)],
        [f"batch2_{i}" for i in range(4)],
        [f"batch3_{i}" for i in range(3)],
    ]
    await scheduler.run(batches)


# =============================================================================
# 扩展 4：异步写入文件（用 asyncio.to_thread）
# =============================================================================
async def async_write_json(filepath, data):
    """用 asyncio.to_thread 把同步文件写入变成异步"""
    def _write():
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath

    # to_thread 把同步函数放到线程池执行，不阻塞事件循环
    return await asyncio.to_thread(_write)


async def async_write_batch(base_dir, results):
    """并发写入多个文件"""
    tasks = []
    for i, result in enumerate(results):
        filepath = os.path.join(base_dir, f"result_{i:03d}.json")
        tasks.append(async_write_json(filepath, result))

    filepaths = await asyncio.gather(*tasks)
    return filepaths


async def test_async_write():
    print("\n=== 扩展4: 异步写入文件 ===")
    # 模拟爬取结果
    results = [
        {"url": f"http://example.com/{i}", "status": 200, "data": f"content_{i}"}
        for i in range(10)
    ]

    output_dir = "/tmp/async_crawl_results"
    start = time.time()
    filepaths = await async_write_batch(output_dir, results)
    elapsed = time.time() - start

    print(f"  写入 {len(filepaths)} 个文件, 耗时 {elapsed:.3f}s")
    print(f"  示例文件: {filepaths[0]}")

    # 验证写入
    def _verify():
        with open(filepaths[0], "r") as f:
            return json.load(f)
    sample = await asyncio.to_thread(_verify)
    print(f"  验证: {sample}")

    # 清理
    await asyncio.to_thread(lambda: __import__("shutil").rmtree(output_dir))
    print("  临时文件已清理")


# =============================================================================
# 扩展 5：异步上下文管理器（async with 管理爬虫生命周期）
# =============================================================================
class AsyncCrawlerSession:
    """异步上下文管理器：管理爬虫的启动和清理"""

    def __init__(self, name, max_concurrency=5):
        self.name = name
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.stats = {"total": 0, "success": 0, "failed": 0}
        self._start_time = None

    async def __aenter__(self):
        """进入上下文：初始化资源"""
        self._start_time = time.time()
        print(f"  🚀 [{self.name}] 爬虫启动")
        return self  # 返回自身供 as 子句使用

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文：打印统计、清理资源"""
        elapsed = time.time() - self._start_time
        print(f"  📊 [{self.name}] 爬虫结束: "
              f"总计{self.stats['total']}, "
              f"成功{self.stats['success']}, "
              f"失败{self.stats['failed']}, "
              f"耗时{elapsed:.2f}s")
        # 如果有异常，不吞掉
        return False

    async def fetch(self, url):
        """在上下文内发起请求"""
        async with self.semaphore:
            self.stats["total"] += 1
            try:
                delay = random.uniform(0.2, 0.6)
                await asyncio.sleep(delay)
                if random.random() < 0.15:
                    raise ConnectionError(f"{url} 连接失败")
                self.stats["success"] += 1
                return {"url": url, "status": 200}
            except Exception as e:
                self.stats["failed"] += 1
                return {"url": url, "status": 503, "error": str(e)}


async def test_context_manager():
    print("\n=== 扩展5: 异步上下文管理器 ===")
    urls = [f"http://example.com/page/{i}" for i in range(1, 11)]

    # 用 async with 管理生命周期
    async with AsyncCrawlerSession("小悟爬虫", max_concurrency=4) as crawler:
        results = await asyncio.gather(*[crawler.fetch(url) for url in urls])

    # 退出上下文后自动打印统计


# =============================================================================
# 扩展 1：用 aiohttp 发送真实 HTTP 请求（如果已安装）
# =============================================================================
async def test_real_http():
    print("\n=== 扩展1: 真实 HTTP 请求 ===")
    try:
        import aiohttp
    except ImportError:
        print("  aiohttp 未安装，跳过真实请求测试")
        print("  安装命令: pip install aiohttp")
        # 降级方案：用 asyncio.to_thread + urllib
        print("  --- 降级方案: asyncio.to_thread + urllib ---")

        import urllib.request

        async def fetch_real(url):
            def _fetch():
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return {"url": url, "status": resp.status, "length": len(resp.read())}
            return await asyncio.to_thread(_fetch)

        urls = [
            "https://httpbin.org/get",
            "https://httpbin.org/status/200",
            "https://httpbin.org/status/404",
        ]
        try:
            results = await asyncio.gather(*[fetch_real(url) for url in urls])
            for r in results:
                print(f"  ✅ {r['url']} -> {r['status']} ({r['length']} bytes)")
        except Exception as e:
            print(f"  请求失败: {e}")
        return

    async with aiohttp.ClientSession() as session:
        urls = ["https://httpbin.org/get", "https://httpbin.org/status/200"]
        async def fetch(session, url):
            async with session.get(url) as resp:
                return {"url": url, "status": resp.status}
        results = await asyncio.gather(*[fetch(session, url) for url in urls])
        for r in results:
            print(f"  ✅ {r['url']} -> {r['status']}")


# =============================================================================
# 主函数：运行所有扩展测试
# =============================================================================
async def main():
    print("=" * 60)
    print("🔧 异步编程扩展练习")
    print("=" * 60)

    await test_retry()
    await test_scheduler()
    await test_async_write()
    await test_context_manager()
    await test_real_http()

    print("\n" + "=" * 60)
    print("✅ 异步编程全部掌握，核心知识点：")
    print("=" * 60)
    print("""
1. 协程基础：async def + await，asyncio.run() 入口
2. 并发控制：gather（全部并发）、create_task（后台调度）、wait_for（超时）
3. Semaphore：令牌机制限制并发数，防止过载
4. Queue：协程间安全通信，生产者-消费者模式
5. 重试机制：指数退避 + 最大重试次数
6. 异步文件IO：asyncio.to_thread 把同步操作包装为异步
7. async with：异步上下文管理器，管理资源生命周期
8. 降级策略：aiohttp 不可用时用 to_thread + urllib 替代
""")


asyncio.run(main())
