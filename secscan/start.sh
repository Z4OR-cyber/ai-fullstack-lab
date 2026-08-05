#!/bin/bash
# ============================================================
# SecScan 一键启动脚本 (Linux / macOS)
# 功能：检查 Python → 安装依赖 → 启动服务 → 提示访问地址
# ============================================================

set -e

# ---- 颜色定义 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ---- 配置 ----
APP_NAME="SecScan"
APP_PORT="${APP_PORT:-8000}"
APP_URL="http://localhost:${APP_PORT}"
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=10

# 获取脚本所在目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---- 辅助函数 ----
print_info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
print_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
print_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_step()  { echo -e "\n${BOLD}${BLUE}━━━ $1 ━━━${NC}\n"; }

# ---- 横幅 ----
echo ""
echo -e "${BOLD}${CYAN}"
cat << 'BANNER'
  ╔══════════════════════════════════════════════╗
  ║          🛡️  SecScan  v2.0.0                 ║
  ║     AI 驱动的代码安全审计平台  一键启动       ║
  ╚══════════════════════════════════════════════╝
BANNER
echo -e "${NC}"
echo ""

# ============================================================
# 步骤 1：检查 Python 环境
# ============================================================
print_step "步骤 1/4：检查 Python 环境"

PYTHON_CMD=""

# 尝试查找可用的 Python 命令
for cmd in python3 python; do
    if command -v "$cmd" &> /dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    print_error "未检测到 Python 环境！"
    echo ""
    echo -e "  ${YELLOW}请安装 Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR} 或更高版本：${NC}"
    echo -e "  ${CYAN}官网下载：${NC} https://www.python.org/downloads/"
    echo -e "  ${CYAN}macOS (Homebrew)：${NC} brew install python@3.12"
    echo -e "  ${CYAN}Ubuntu/Debian：${NC} sudo apt install python3 python3-pip"
    echo ""
    exit 1
fi

# 获取 Python 版本
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.minor)')

print_info "检测到 Python：${PYTHON_CMD} (v${PYTHON_VERSION})"

# 检查版本是否满足要求
if [ "$PYTHON_MAJOR" -lt "$PYTHON_MIN_MAJOR" ] || \
   [ "$PYTHON_MAJOR" -eq "$PYTHON_MIN_MAJOR" -a "$PYTHON_MINOR" -lt "$PYTHON_MIN_MINOR" ]; then
    print_error "Python 版本过低！当前 v${PYTHON_VERSION}，需要 v${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+"
    echo ""
    echo -e "  ${YELLOW}请升级 Python 版本后重试。${NC}"
    exit 1
fi

print_ok "Python 版本满足要求 (≥ ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR})"

# ============================================================
# 步骤 2：创建虚拟环境并安装依赖
# ============================================================
print_step "步骤 2/4：安装依赖"

VENV_DIR=".venv"

# 创建虚拟环境（如果不存在）
if [ ! -d "$VENV_DIR" ]; then
    print_info "创建虚拟环境 ($VENV_DIR) ..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    print_ok "虚拟环境已创建"
else
    print_info "虚拟环境已存在，跳过创建"
fi

# 激活虚拟环境
if [ -f "$VENV_DIR/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    print_ok "已激活虚拟环境"
else
    print_warn "虚拟环境激活文件不存在，使用系统 Python 继续"
fi

# 检查是否需要安装依赖
PIP_CMD="pip"
if [ -f "$VENV_DIR/bin/pip" ]; then
    PIP_CMD="$VENV_DIR/bin/pip"
fi

# 检查 fastapi 是否已安装
if $PIP_CMD show fastapi &> /dev/null 2>&1; then
    print_info "依赖已安装，跳过安装步骤"
else
    print_info "安装依赖 (requirements.txt) ..."
    echo ""
    $PIP_CMD install --upgrade pip -q
    $PIP_CMD install -r requirements.txt -q
    print_ok "依赖安装完成"
fi

# ============================================================
# 步骤 3：检查端口占用
# ============================================================
print_step "步骤 3/4：检查端口 ${APP_PORT}"

if command -v lsof &> /dev/null; then
    if lsof -i :"${APP_PORT}" &> /dev/null 2>&1; then
        print_warn "端口 ${APP_PORT} 已被占用！"
        echo ""
        echo -e "  ${YELLOW}解决方法：${NC}"
        echo -e "  1. 终止占用进程：${CYAN}lsof -i :${APP_PORT}${NC} 查看后 ${CYAN}kill -9 <PID>${NC}"
        echo -e "  2. 换端口启动：${CYAN}APP_PORT=8080 ./start.sh${NC}"
        echo ""
        print_info "尝试自动切换到端口 $((APP_PORT + 1)) ..."
        NEW_PORT=$((APP_PORT + 1))
        if ! lsof -i :"${NEW_PORT}" &> /dev/null 2>&1; then
            APP_PORT="$NEW_PORT"
            APP_URL="http://localhost:${APP_PORT}"
            print_ok "已切换到端口 ${APP_PORT}"
        else
            print_error "端口 ${NEW_PORT} 也被占用，请手动指定端口"
            echo -e "  ${CYAN}APP_PORT=9000 ./start.sh${NC}"
            exit 1
        fi
    else
        print_ok "端口 ${APP_PORT} 可用"
    fi
elif command -v netstat &> /dev/null; then
    if netstat -tlnp 2>/dev/null | grep ":${APP_PORT}" &> /dev/null; then
        print_warn "端口 ${APP_PORT} 可能被占用，继续尝试启动..."
    else
        print_ok "端口 ${APP_PORT} 可用"
    fi
else
    print_info "未检测到端口检查工具 (lsof/netstat)，跳过端口检查"
fi

# ============================================================
# 步骤 4：启动服务
# ============================================================
print_step "步骤 4/4：启动 SecScan 服务"

echo ""
echo -e "  ${BOLD}${GREEN}SecScan 正在启动...${NC}"
echo ""
echo -e "  ${CYAN}Web 界面：${NC}  ${APP_URL}"
echo -e "  ${CYAN}API 文档：${NC}  ${APP_URL}/docs"
echo -e "  ${CYAN}健康检查：${NC}  ${APP_URL}/"
echo ""
echo -e "  ${YELLOW}按 Ctrl+C 停止服务${NC}"
echo ""
echo -e "  ${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 尝试打开浏览器（后台执行，不阻塞）
(
    sleep 2.5
    if command -v xdg-open &> /dev/null; then
        xdg-open "${APP_URL}" 2>/dev/null &
    elif command -v open &> /dev/null; then
        open "${APP_URL}" 2>/dev/null &
    fi
) &

# 启动 uvicorn
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT}"
