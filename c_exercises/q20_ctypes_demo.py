#!/usr/bin/env python3
"""
Q20: C与Python互操作 — ctypes 演示
通过 ctypes 调用 C 编译的共享库函数
"""
import ctypes
import os
import time
import sys

# 加载C共享库
lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libq20.so")
if not os.path.exists(lib_path):
    print(f"  错误: {lib_path} 不存在, 请先编译")
    print("  编译命令: gcc -shared -fPIC -o libq20.so q20_c_python_interop.c")
    sys.exit(1)

lib = ctypes.CDLL(lib_path)

# 设置函数签名 (类型检查)
lib.c_add.argtypes = [ctypes.c_int, ctypes.c_int]
lib.c_add.restype = ctypes.c_int

lib.c_fibonacci.argtypes = [ctypes.c_int]
lib.c_fibonacci.restype = ctypes.c_long

lib.c_count_primes.argtypes = [ctypes.c_int]
lib.c_count_primes.restype = ctypes.c_int

lib.c_array_sum.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int]
lib.c_array_sum.restype = ctypes.c_double

lib.c_reverse_string.argtypes = [ctypes.c_char_p, ctypes.c_int]
lib.c_reverse_string.restype = None

print("=" * 40)
print("  Q20: ctypes 调用C函数演示")
print("=" * 40)
print()

# 1. 基本调用
print("--- 1. 基本函数调用 ---")
result = lib.c_add(17, 25)
print(f"  c_add(17, 25) = {result}")

fib20 = lib.c_fibonacci(20)
print(f"  c_fibonacci(20) = {fib20}")

primes100 = lib.c_count_primes(100)
print(f"  c_count_primes(100) = {primes100}")
primes10k = lib.c_count_primes(10000)
print(f"  c_count_primes(10000) = {primes10k}")
print()

# 2. 数组传递
print("--- 2. 数组传递 ---")
data = [1.1, 2.2, 3.3, 4.4, 5.5]
arr_type = ctypes.c_double * len(data)
arr = arr_type(*data)
total = lib.c_array_sum(arr, len(data))
print(f"  c_array_sum({data}) = {total:.1f}")
print()

# 3. 字符串处理
print("--- 3. 字符串处理 ---")
s = ctypes.create_string_buffer(b"Hello, ctypes!")
lib.c_reverse_string(s, len(s.value))
print(f'  c_reverse_string("Hello, ctypes!") = "{s.value.decode()}"')
print()

# 4. 性能对比
print("--- 4. 性能对比: C vs Python ---")

def py_fib(n):
    if n <= 1:
        return n
    return py_fib(n - 1) + py_fib(n - 2)

n = 35

# C版本
t0 = time.time()
c_result = lib.c_fibonacci(n)
t_c = time.time() - t0
print(f"  C fib({n}) = {c_result}, 耗时 {t_c:.3f}s")

# Python版本
t0 = time.time()
py_result = py_fib(n)
t_py = time.time() - t0
print(f"  Python fib({n}) = {py_result}, 耗时 {t_py:.3f}s")

if t_c > 0:
    print(f"  C比Python快约 {t_py / t_c:.1f} 倍")
print()

# 5. 素数计数性能对比
print("--- 5. 素数计数性能对比 ---")

def py_count_primes(n):
    if n < 2:
        return 0
    sieve = [True] * n
    sieve[0] = sieve[1] = False
    for i in range(2, int(n**0.5) + 1):
        if sieve[i]:
            for j in range(i * i, n, i):
                sieve[j] = False
    return sum(1 for x in sieve if x)

n = 100000
t0 = time.time()
c_primes = lib.c_count_primes(n)
t_c = time.time() - t0
print(f"  C      count_primes({n}) = {c_primes}, 耗时 {t_c:.4f}s")

t0 = time.time()
py_primes = py_count_primes(n)
t_py = time.time() - t0
print(f"  Python count_primes({n}) = {py_primes}, 耗时 {t_py:.4f}s")

if t_c > 0:
    print(f"  C比Python快约 {t_py / t_c:.1f} 倍")

print()
print("✅ Q20 ctypes 演示通过")
