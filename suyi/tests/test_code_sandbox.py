"""CodeSandboxTool 测试.

覆盖范围：
- 正常执行（print、算术、多行代码）
- 返回字段（stdout、stderr、exit_code、elapsed_ms）
- stdout / stderr 分离
- 危险 import 拦截（os / subprocess / socket / ctypes / shutil / pickle 等）
- from...import 拦截、嵌套模块拦截
- 危险函数拦截（eval / exec / compile / __import__）
- 语法错误处理
- 运行时错误捕获
- 超时防护（无限循环）
- 签名键 / schema 生成
"""

import pytest

from suyi.tools import CodeSandboxTool, ToolContext
from suyi.tools.code_sandbox import check_code_safety, BLOCKED_MODULES, DANGEROUS_NAMES


@pytest.fixture
def ctx():
    """工具执行上下文."""
    return ToolContext()


@pytest.fixture
def tool():
    """CodeSandboxTool 实例."""
    return CodeSandboxTool()


# ═══════════════════════════════════════════════════════════════
#  基础属性测试
# ═══════════════════════════════════════════════════════════════


class TestCodeSandboxBasic:
    """基础属性测试."""

    def test_name(self, tool):
        """工具名称为 code_sandbox."""
        assert tool.name == "code_sandbox"

    def test_description(self, tool):
        """工具描述非空且包含关键信息."""
        desc = tool.description
        assert "Python" in desc or "python" in desc.lower()
        assert "code" in desc.lower()

    def test_default_permission(self, tool):
        """默认权限为 confirm."""
        assert tool.default_permission == "confirm"

    def test_parameters(self, tool):
        """参数列表包含 code 和 timeout."""
        param_names = [p.name for p in tool.parameters]
        assert "code" in param_names
        assert "timeout" in param_names

    def test_code_required(self, tool):
        """code 参数为必填."""
        code_param = [p for p in tool.parameters if p.name == "code"][0]
        assert code_param.required is True

    def test_timeout_default_30(self, tool):
        """timeout 默认值为 30."""
        timeout_param = [p for p in tool.parameters if p.name == "timeout"][0]
        assert timeout_param.default == 30

    def test_to_schema(self, tool):
        """schema 生成正确."""
        schema = tool.to_schema()
        assert schema["name"] == "code_sandbox"
        assert "parameters" in schema
        assert "code" in schema["parameters"]["properties"]


# ═══════════════════════════════════════════════════════════════
#  正常执行测试
# ═══════════════════════════════════════════════════════════════


class TestCodeExecution:
    """代码执行测试."""

    def test_simple_print(self, tool, ctx):
        """print 输出被正确捕获."""
        result = tool.execute({"code": "print('hello')"}, ctx)
        assert result.success is True
        assert result.output["stdout"].strip() == "hello"

    def test_multiple_prints(self, tool, ctx):
        """多行 print 输出顺序正确."""
        result = tool.execute({"code": "print('line1')\nprint('line2')\nprint('line3')"}, ctx)
        assert result.success is True
        lines = result.output["stdout"].strip().split("\n")
        assert lines == ["line1", "line2", "line3"]

    def test_arithmetic(self, tool, ctx):
        """算术运算结果正确输出."""
        result = tool.execute({"code": "x = 1 + 2\nprint(x)"}, ctx)
        assert result.success is True
        assert result.output["stdout"].strip() == "3"

    def test_return_fields(self, tool, ctx):
        """返回结构包含所有必需字段."""
        result = tool.execute({"code": "print('test')"}, ctx)
        assert result.success is True
        output = result.output
        assert "stdout" in output
        assert "stderr" in output
        assert "exit_code" in output
        assert "elapsed_ms" in output

    def test_exit_code_zero(self, tool, ctx):
        """成功执行 exit_code 为 0."""
        result = tool.execute({"code": "x = 1"}, ctx)
        assert result.success is True
        assert result.output["exit_code"] == 0

    def test_elapsed_ms_positive(self, tool, ctx):
        """elapsed_ms 为非负整数."""
        result = tool.execute({"code": "print('hi')"}, ctx)
        assert result.success is True
        assert isinstance(result.output["elapsed_ms"], int)
        assert result.output["elapsed_ms"] >= 0

    def test_no_output(self, tool, ctx):
        """无输出的代码正常执行."""
        result = tool.execute({"code": "x = 42"}, ctx)
        assert result.success is True
        assert result.output["stdout"] == ""
        assert result.output["exit_code"] == 0

    def test_loop_execution(self, tool, ctx):
        """循环计算正确."""
        code = "total = sum(range(10))\nprint(total)"
        result = tool.execute({"code": code}, ctx)
        assert result.success is True
        assert result.output["stdout"].strip() == "45"

    def test_string_manipulation(self, tool, ctx):
        """字符串操作正确."""
        code = "s = 'hello'.upper()\nprint(s)"
        result = tool.execute({"code": code}, ctx)
        assert result.success is True
        assert result.output["stdout"].strip() == "HELLO"


# ═══════════════════════════════════════════════════════════════
#  stdout / stderr 分离测试
# ═══════════════════════════════════════════════════════════════


class TestStdoutStderr:
    """stdout / stderr 分离测试."""

    def test_stderr_capture(self, tool, ctx):
        """stderr 输出被捕获."""
        code = "import sys\nsys.stderr.write('error msg\\n')"
        result = tool.execute({"code": code}, ctx)
        assert result.success is True
        assert "error msg" in result.output["stderr"]

    def test_stdout_stderr_separated(self, tool, ctx):
        """stdout 和 stderr 分离."""
        code = "import sys\nprint('to stdout')\nsys.stderr.write('to stderr\\n')"
        result = tool.execute({"code": code}, ctx)
        assert result.success is True
        assert "to stdout" in result.output["stdout"]
        assert "to stdout" not in result.output["stderr"]
        assert "to stderr" in result.output["stderr"]
        assert "to stderr" not in result.output["stdout"]

    def test_stdout_empty_on_stderr_only(self, tool, ctx):
        """只有 stderr 输出时 stdout 为空."""
        code = "import sys\nsys.stderr.write('only stderr\\n')"
        result = tool.execute({"code": code}, ctx)
        assert result.success is True
        assert result.output["stdout"] == ""


# ═══════════════════════════════════════════════════════════════
#  允许的 import 测试
# ═══════════════════════════════════════════════════════════════


class TestAllowedImports:
    """允许的 import 测试."""

    def test_import_math(self, tool, ctx):
        """允许导入 math."""
        code = "import math\nprint(math.sqrt(16))"
        result = tool.execute({"code": code}, ctx)
        assert result.success is True
        assert "4.0" in result.output["stdout"]

    def test_import_json(self, tool, ctx):
        """允许导入 json."""
        code = "import json\nprint(json.dumps({'a': 1}))"
        result = tool.execute({"code": code}, ctx)
        assert result.success is True
        assert '{"a": 1}' in result.output["stdout"]

    def test_import_from_math(self, tool, ctx):
        """允许 from math import."""
        code = "from math import pi\nprint(round(pi, 2))"
        result = tool.execute({"code": code}, ctx)
        assert result.success is True
        assert "3.14" in result.output["stdout"]

    def test_import_re(self, tool, ctx):
        """允许导入 re."""
        code = "import re\nprint(re.findall(r'\\d+', 'a1b2c3'))"
        result = tool.execute({"code": code}, ctx)
        assert result.success is True
        assert "['1', '2', '3']" in result.output["stdout"]


# ═══════════════════════════════════════════════════════════════
#  危险 import 拦截测试
# ═══════════════════════════════════════════════════════════════


class TestBlockedImports:
    """危险 import 拦截测试."""

    def test_block_import_os(self, tool, ctx):
        """拦截 import os."""
        result = tool.execute({"code": "import os\nprint(os.getcwd())"}, ctx)
        assert result.success is False
        assert "os" in result.error or "禁止" in result.error

    def test_block_import_subprocess(self, tool, ctx):
        """拦截 import subprocess."""
        result = tool.execute({"code": "import subprocess"}, ctx)
        assert result.success is False
        assert "subprocess" in result.error

    def test_block_import_socket(self, tool, ctx):
        """拦截 import socket."""
        result = tool.execute({"code": "import socket"}, ctx)
        assert result.success is False
        assert "socket" in result.error

    def test_block_import_ctypes(self, tool, ctx):
        """拦截 import ctypes."""
        result = tool.execute({"code": "import ctypes"}, ctx)
        assert result.success is False
        assert "ctypes" in result.error

    def test_block_import_shutil(self, tool, ctx):
        """拦截 import shutil."""
        result = tool.execute({"code": "import shutil"}, ctx)
        assert result.success is False
        assert "shutil" in result.error

    def test_block_import_pickle(self, tool, ctx):
        """拦截 import pickle."""
        result = tool.execute({"code": "import pickle"}, ctx)
        assert result.success is False
        assert "pickle" in result.error

    def test_block_from_import_os(self, tool, ctx):
        """拦截 from os import path."""
        result = tool.execute({"code": "from os import path\nprint(path)"}, ctx)
        assert result.success is False
        assert "os" in result.error

    def test_block_nested_module_import(self, tool, ctx):
        """拦截 import os.path."""
        result = tool.execute({"code": "import os.path"}, ctx)
        assert result.success is False
        assert "os" in result.error

    def test_block_from_subprocess_import(self, tool, ctx):
        """拦截 from subprocess import run."""
        result = tool.execute({"code": "from subprocess import run"}, ctx)
        assert result.success is False
        assert "subprocess" in result.error

    def test_blocked_exit_code(self, tool, ctx):
        """被拦截时代码不执行，exit_code 为 -1."""
        result = tool.execute({"code": "import os"}, ctx)
        assert result.success is False
        assert result.output["exit_code"] == -1


# ═══════════════════════════════════════════════════════════════
#  危险函数拦截测试
# ═══════════════════════════════════════════════════════════════


class TestBlockedFunctions:
    """危险函数调用拦截测试."""

    def test_block_eval(self, tool, ctx):
        """拦截 eval 调用."""
        result = tool.execute({"code": "eval('1+1')"}, ctx)
        assert result.success is False
        assert "eval" in result.error

    def test_block_exec(self, tool, ctx):
        """拦截 exec 调用."""
        result = tool.execute({"code": "exec('x = 1')"}, ctx)
        assert result.success is False
        assert "exec" in result.error

    def test_block_compile(self, tool, ctx):
        """拦截 compile 调用."""
        result = tool.execute({"code": "compile('1+1', '<test>', 'eval')"}, ctx)
        assert result.success is False
        assert "compile" in result.error

    def test_block_dunder_import(self, tool, ctx):
        """拦截 __import__ 调用."""
        result = tool.execute({"code": "__import__('os')"}, ctx)
        assert result.success is False
        assert "__import__" in result.error or "import" in result.error.lower()


# ═══════════════════════════════════════════════════════════════
#  错误处理测试
# ═══════════════════════════════════════════════════════════════


class TestErrorHandling:
    """错误处理测试."""

    def test_syntax_error(self, tool, ctx):
        """语法错误被捕获."""
        result = tool.execute({"code": "def broken("}, ctx)
        assert result.success is False
        assert "语法错误" in result.error or "SyntaxError" in result.error

    def test_runtime_error(self, tool, ctx):
        """运行时错误被捕获到 stderr."""
        result = tool.execute({"code": "print(undefined_var)"}, ctx)
        assert result.success is False
        assert result.output["exit_code"] != 0
        assert "NameError" in result.output["stderr"] or "undefined" in result.output["stderr"].lower()

    def test_zero_division_error(self, tool, ctx):
        """除零错误被捕获."""
        result = tool.execute({"code": "print(1 / 0)"}, ctx)
        assert result.success is False
        assert result.output["exit_code"] != 0

    def test_no_code_error(self, tool, ctx):
        """无代码返回错误."""
        result = tool.execute({}, ctx)
        assert result.success is False
        assert "代码" in result.error or "code" in result.error.lower()

    def test_empty_code_error(self, tool, ctx):
        """空代码返回错误."""
        result = tool.execute({"code": ""}, ctx)
        assert result.success is False

    def test_non_string_code_error(self, tool, ctx):
        """非字符串代码返回错误."""
        result = tool.execute({"code": 123}, ctx)
        assert result.success is False

    def test_invalid_timeout_error(self, tool, ctx):
        """无效超时时间返回错误."""
        result = tool.execute({"code": "print('hi')", "timeout": -1}, ctx)
        assert result.success is False


# ═══════════════════════════════════════════════════════════════
#  超时防护测试
# ═══════════════════════════════════════════════════════════════


class TestTimeoutProtection:
    """超时防护测试."""

    def test_infinite_loop_timeout(self, tool, ctx):
        """无限循环被超时终止."""
        result = tool.execute({"code": "while True:\n    pass", "timeout": 2}, ctx)
        assert result.success is False
        assert "超时" in result.error or "timeout" in result.error.lower()

    def test_timeout_elapsed_ms(self, tool, ctx):
        """超时结果包含 elapsed_ms."""
        result = tool.execute({"code": "while True:\n    pass", "timeout": 2}, ctx)
        assert result.success is False
        assert result.output["elapsed_ms"] >= 1000  # 至少 1 秒

    def test_custom_timeout_short(self, tool, ctx):
        """短超时正常工作."""
        result = tool.execute({"code": "import time\ntime.sleep(0.1)\nprint('done')", "timeout": 5}, ctx)
        assert result.success is True
        assert result.output["stdout"].strip() == "done"

    def test_timeout_exit_code(self, tool, ctx):
        """超时时 exit_code 为 -1."""
        result = tool.execute({"code": "while True:\n    pass", "timeout": 2}, ctx)
        assert result.success is False
        assert result.output["exit_code"] == -1


# ═══════════════════════════════════════════════════════════════
#  签名键 / 风险评估测试
# ═══════════════════════════════════════════════════════════════


class TestCodeSandboxSignature:
    """签名键 / 风险评估测试."""

    def test_signature_key_normal(self, tool):
        """正常代码的签名键为前 50 字符."""
        code = "print('hello world')"
        key = tool.get_signature_key({"code": code})
        assert key == code[:50]

    def test_signature_key_long_code(self, tool):
        """长代码的签名键被截断到 50 字符."""
        code = "x = 1\n" * 20  # 超过 50 字符
        key = tool.get_signature_key({"code": code})
        assert len(key) == 50

    def test_signature_key_empty(self, tool):
        """空代码的签名键为空字符串."""
        key = tool.get_signature_key({"code": ""})
        assert key == ""

    def test_assess_risk_returns_none(self, tool):
        """assess_risk 始终返回 None（回退到 confirm）."""
        risk = tool.assess_risk({"code": "print('hi')"}, ToolContext())
        assert risk is None


# ═══════════════════════════════════════════════════════════════
#  安全检查函数测试
# ═══════════════════════════════════════════════════════════════


class TestCheckCodeSafety:
    """check_code_safety 函数测试."""

    def test_safe_code(self):
        """安全代码通过检查."""
        is_safe, reason = check_code_safety("print('hello')")
        assert is_safe is True
        assert reason == ""

    def test_syntax_error_detected(self):
        """语法错误被检测."""
        is_safe, reason = check_code_safety("def broken(")
        assert is_safe is False
        assert "语法错误" in reason

    def test_blocked_module_in_set(self):
        """os 在 BLOCKED_MODULES 集合中."""
        assert "os" in BLOCKED_MODULES
        assert "subprocess" in BLOCKED_MODULES
        assert "socket" in BLOCKED_MODULES

    def test_dangerous_names_in_set(self):
        """eval / exec 在 DANGEROUS_NAMES 集合中."""
        assert "eval" in DANGEROUS_NAMES
        assert "exec" in DANGEROUS_NAMES
        assert "compile" in DANGEROUS_NAMES

    def test_multiple_blocked_imports(self):
        """多个危险 import 都被检测."""
        code = "import os\nimport subprocess"
        is_safe, reason = check_code_safety(code)
        assert is_safe is False
        # 第一个危险模块被报告
        assert "os" in reason
