"""Tests for Message Classifier — 平凡消息分类。"""

import pytest

from suyi.memory.message_classifier import MessageClassifier


class TestMessageClassifier:
    """MessageClassifier 平凡消息分类器测试。"""

    def setup_method(self):
        self.classifier = MessageClassifier()

    # ── 中文 trivial 消息 ──────────────────────────────────────

    @pytest.mark.parametrize("msg", [
        "好的", "嗯", "嗯嗯", "哦", "谢谢", "收到", "明白", "了解",
        "知道了", "可以", "行", "好吧", "对", "是的",
        "没问题", "没事", "哈哈", "继续",
    ])
    def test_trivial_chinese(self, msg):
        """中文 trivial 消息。"""
        assert self.classifier.is_trivial(msg) is True

    # ── 英文 trivial 消息 ──────────────────────────────────────

    @pytest.mark.parametrize("msg", [
        "ok", "okay", "sure", "yes", "yeah", "yep", "yup",
        "thanks", "thank you", "thx", "got it", "understood",
        "cool", "nice", "great", "lol", "fine", "alright",
        "no", "nope", "k", "kk", "done",
    ])
    def test_trivial_english(self, msg):
        """英文 trivial 消息。"""
        assert self.classifier.is_trivial(msg.lower()) is True

    # ── 重复字符 ───────────────────────────────────────────────

    @pytest.mark.parametrize("msg", [
        "嗯嗯嗯嗯嗯", "哈哈哈哈", "啊啊啊", "......",
    ])
    def test_trivial_repeated_chars(self, msg):
        """重复字符 trivial 消息。"""
        assert self.classifier.is_trivial(msg) is True

    # ── 非 trivial 消息 ────────────────────────────────────────

    @pytest.mark.parametrize("msg", [
        "请帮我写一个 Python 脚本来处理 CSV 文件",
        "What are the best practices for async programming in Python?",
        "我需要你帮我分析一下这段代码的性能问题",
        "Can you explain how the GIL works in Python?",
    ])
    def test_not_trivial(self, msg):
        """非 trivial 消息。"""
        assert self.classifier.is_trivial(msg) is False

    # ── 边界情况 ───────────────────────────────────────────────

    def test_empty_message(self):
        """空消息是 trivial。"""
        assert self.classifier.is_trivial("") is True
        assert self.classifier.is_trivial("   ") is True

    def test_too_long_is_not_trivial(self):
        """超过长度阈值不是 trivial。"""
        long_msg = "好的" * 20  # 超过 30 字符
        assert self.classifier.is_trivial(long_msg) is False

    # ── 分类详情 ───────────────────────────────────────────────

    def test_classify_trivial(self):
        """分类 trivial 消息。"""
        result = self.classifier.classify("好的")
        assert result["is_trivial"] is True
        assert result["reason"] == "exact_match"
        assert result["length"] == 2

    def test_classify_not_trivial(self):
        """分类非 trivial 消息。"""
        result = self.classifier.classify("请帮我写代码")
        assert result["is_trivial"] is False
        assert result["reason"] == "not_trivial"

    def test_classify_empty(self):
        """分类空消息。"""
        result = self.classifier.classify("")
        assert result["is_trivial"] is True
        assert result["reason"] == "empty_message"

    def test_classify_too_long(self):
        """分类过长消息。"""
        result = self.classifier.classify("好的" * 20)
        assert result["is_trivial"] is False
        assert result["reason"] == "too_long"

    # ── 自定义扩展 ─────────────────────────────────────────────

    def test_add_custom_word(self):
        """添加自定义 trivial 词汇。"""
        self.classifier.add_trivial_word("收到收到")
        assert self.classifier.is_trivial("收到收到") is True

    def test_add_custom_pattern(self):
        """添加自定义 trivial 模式。"""
        self.classifier.add_trivial_pattern(r"^收到\d+次$")
        assert self.classifier.is_trivial("收到3次") is True

    # ── 自定义初始化 ───────────────────────────────────────────

    def test_custom_init(self):
        """自定义初始化参数。"""
        classifier = MessageClassifier(
            custom_trivial={"自定义词"},
            max_trivial_length=50,
        )
        assert classifier.is_trivial("自定义词") is True
        assert classifier.max_trivial_length == 50

    def test_repr(self):
        """repr 方法。"""
        assert "MessageClassifier" in repr(self.classifier)
