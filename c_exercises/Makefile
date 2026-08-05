# Makefile for Q15: 多文件项目
# 用法: make        编译
#       make run    编译并运行
#       make clean  清理

CC = gcc
CFLAGS = -Wall -Wextra -g -std=c11

# 目标文件
TARGET = q15_multifile

# 源文件
SRCS = q15_multifile.c math_utils.c string_utils.c

# 头文件
HDRS = math_utils.h string_utils.h

# 对象文件
OBJS = $(SRCS:.c=.o)

# 默认目标
$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^

# 编译规则
%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

# q15_multifile.o 依赖头文件
q15_multifile.o: math_utils.h string_utils.h
math_utils.o: math_utils.h
string_utils.o: string_utils.h

# 运行
run: $(TARGET)
	./$(TARGET)

# 静态库演示
static_lib: math_utils.o string_utils.o
	ar rcs libutils.a math_utils.o string_utils.o
	$(CC) $(CFLAGS) -o q15_static q15_multifile.c -L. -lutils
	@echo "静态库构建完成: ./q15_static"

# 动态库演示
dynamic_lib:
	$(CC) $(CFLAGS) -shared -fPIC -o libutils.so math_utils.c string_utils.c
	$(CC) $(CFLAGS) -o q15_dynamic q15_multifile.c -L. -lutils
	@echo "动态库构建完成: LD_LIBRARY_PATH=. ./q15_dynamic"

# 清理
clean:
	rm -f $(OBJS) $(TARGET) q15_static q15_dynamic libutils.a libutils.so

.PHONY: run clean static_lib dynamic_lib
