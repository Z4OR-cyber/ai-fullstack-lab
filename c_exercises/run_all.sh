#!/bin/bash
# run_all.sh — 一键编译运行所有C语言练习题
# 用法: bash run_all.sh

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

CC=gcc
CFLAGS="-Wall -Wextra -g -std=c11"
PASS=0
FAIL=0
FAILED_LIST=()

echo "############################################################"
echo "#  AI全栈学习第二期 — 轨道A·阶段八：C语言底层基石"
echo "#  20道练习题一键编译运行"
echo "############################################################"
echo ""

# ========== Q01-Q14: 单文件编译 ==========
SIMPLE_EXES=(
    "q01_types_io.c"
    "q02_control_flow.c"
    "q03_functions_scope.c"
    "q04_arrays_strings.c"
    "q05_preprocessor.c"
    "q06_pointer_basics.c"
    "q07_pointer_array.c"
    "q08_dynamic_memory.c"
    "q09_function_pointers.c"
    "q10_strings_pointers.c"
    "q11_memory_layout.c"
    "q12_struct_union.c"
    "q13_linked_list.c"
    "q14_file_io.c"
)

for src in "${SIMPLE_EXES[@]}"; do
    exe="${src%.c}"
    echo ">>> 编译运行: $src"
    if $CC $CFLAGS -o "$exe" "$src" 2>&1; then
        if ./"$exe"; then
            PASS=$((PASS + 1))
            echo ""
        else
            echo "  ❌ 运行失败: $src"
            FAIL=$((FAIL + 1))
            FAILED_LIST+=("$src")
            echo ""
        fi
    else
        echo "  ❌ 编译失败: $src"
        FAIL=$((FAIL + 1))
        FAILED_LIST+=("$src")
        echo ""
    fi
    rm -f "$exe"
done

# ========== Q15: 多文件项目 (make) ==========
echo ">>> 编译运行: Q15 多文件项目 (make)"
cd "$DIR"
make clean >/dev/null 2>&1 || true
if make 2>&1; then
    if ./q15_multifile; then
        PASS=$((PASS + 1))
        echo ""
    else
        echo "  ❌ 运行失败: Q15"
        FAIL=$((FAIL + 1))
        FAILED_LIST+=("q15_multifile")
        echo ""
    fi
else
    echo "  ❌ make 失败: Q15"
    FAIL=$((FAIL + 1))
    FAILED_LIST+=("q15_multifile")
    echo ""
fi
make clean >/dev/null 2>&1 || true

# ========== Q16-Q19: 系统编程 ==========
SYS_EXES=(
    "q16_process_exec.c"
    "q17_signal_handling.c"
    "q18_file_descriptors.c"
    "q19_web_server.c"
)

for src in "${SYS_EXES[@]}"; do
    exe="${src%.c}"
    echo ">>> 编译运行: $src"
    if $CC $CFLAGS -o "$exe" "$src" 2>&1; then
        if ./"$exe"; then
            PASS=$((PASS + 1))
            echo ""
        else
            echo "  ❌ 运行失败: $src"
            FAIL=$((FAIL + 1))
            FAILED_LIST+=("$src")
            echo ""
        fi
    else
        echo "  ❌ 编译失败: $src"
        FAIL=$((FAIL + 1))
        FAILED_LIST+=("$src")
        echo ""
    fi
    rm -f "$exe"
done

# ========== Q20: C与Python互操作 ==========
echo ">>> 编译运行: Q20 C与Python互操作"
cd "$DIR"

# 编译独立程序
if $CC $CFLAGS -DSTANDALONE -o q20_c_python_interop q20_c_python_interop.c 2>&1; then
    if ./q20_c_python_interop; then
        echo "  [C程序部分] ✅"
    else
        echo "  ❌ 运行失败: Q20 C程序"
        FAIL=$((FAIL + 1))
        FAILED_LIST+=("q20_c_python_interop (C)")
    fi
else
    echo "  ❌ 编译失败: Q20 C程序"
    FAIL=$((FAIL + 1))
    FAILED_LIST+=("q20_c_python_interop (C)")
fi
rm -f q20_c_python_interop

# 编译共享库 + Python ctypes
if $CC -shared -fPIC -O2 -o libq20.so q20_c_python_interop.c 2>&1; then
    if python3 q20_ctypes_demo.py; then
        PASS=$((PASS + 1))
        echo ""
    else
        echo "  ❌ Python ctypes 演示运行失败"
        FAIL=$((FAIL + 1))
        FAILED_LIST+=("q20_ctypes_demo.py")
    fi
else
    echo "  ❌ 共享库编译失败"
    FAIL=$((FAIL + 1))
    FAILED_LIST+=("libq20.so")
fi
rm -f libq20.so

# ========== 统计 ==========
echo "############################################################"
echo "#  统计结果"
echo "############################################################"
echo ""
echo "  通过: $PASS / 20"
echo "  失败: $FAIL / 20"
if [ $FAIL -gt 0 ]; then
    echo "  失败列表:"
    for f in "${FAILED_LIST[@]}"; do
        echo "    - $f"
    done
fi
echo ""

# 文件统计
echo "  文件列表:"
find "$DIR" -maxdepth 1 \( -name "*.c" -o -name "*.h" -o -name "Makefile" -o -name "*.sh" -o -name "*.py" \) | sort | while read f; do
    lines=$(wc -l < "$f")
    echo "    $(basename "$f"): ${lines} 行"
done

echo ""
TOTAL_LINES=$(cat "$DIR"/*.c "$DIR"/*.h "$DIR"/Makefile "$DIR"/run_all.sh "$DIR"/*.py 2>/dev/null | wc -l)
FILE_COUNT=$(find "$DIR" -maxdepth 1 \( -name "*.c" -o -name "*.h" -o -name "Makefile" -o -name "*.sh" -o -name "*.py" \) | wc -l)
echo "  总文件数: $FILE_COUNT"
echo "  总代码行数: $TOTAL_LINES"
echo ""
echo "############################################################"
if [ $FAIL -eq 0 ]; then
    echo "#  🎉 全部 20/20 通过!"
else
    echo "#  ⚠️  有 $FAIL 题未通过"
fi
echo "############################################################"
