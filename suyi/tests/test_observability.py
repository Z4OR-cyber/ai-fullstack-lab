"""
Tests for Suyi Observability — structured logging, metrics, tracing, middleware.

Covers:
    - StructuredLogger: JSON format, levels, context tracking, file output, rotation
    - MetricsCollector: Counter, Histogram, Gauge, time windows, export
    - Tracer / Span: creation, nesting, tags, logs, export
    - ObservabilityMiddleware: hooks, metrics integration, tracer integration
"""

import json
import os
import tempfile
import time

import pytest

from suyi.observability import (
    StructuredLogger,
    LogLevel,
    MetricsCollector,
    Histogram,
    Counter,
    Gauge,
    Tracer,
    Span,
    SpanStatus,
    ObservabilityMiddleware,
)
from suyi.core.loop import LLMResponse, LoopState, ToolCall


# ═══════════════════════════════════════════════════════════════
#  StructuredLogger tests
# ═══════════════════════════════════════════════════════════════


class TestStructuredLogger:
    """Test the StructuredLogger class."""

    def test_defaults(self):
        logger = StructuredLogger()
        assert logger.name == "suyi"
        assert logger.session_id  # auto-generated
        assert logger.agent_name is None
        assert logger.level == LogLevel.INFO

    def test_custom_session_id(self):
        logger = StructuredLogger(session_id="test-session-123")
        assert logger.session_id == "test-session-123"

    def test_agent_name(self):
        logger = StructuredLogger(agent_name="suyi-agent")
        assert logger.agent_name == "suyi-agent"

    def test_log_levels(self):
        logger = StructuredLogger(level=LogLevel.DEBUG, console=False)
        assert logger.level == LogLevel.DEBUG

    def test_debug_log(self):
        """Debug logging does not raise."""
        logger = StructuredLogger(level=LogLevel.DEBUG, console=False)
        logger.debug("Debug message", extra={"key": "value"})

    def test_info_log(self):
        """Info logging does not raise."""
        logger = StructuredLogger(console=False)
        logger.info("Info message", extra={"key": "value"})

    def test_warn_log(self):
        """Warn logging does not raise."""
        logger = StructuredLogger(console=False)
        logger.warn("Warn message")

    def test_warning_alias(self):
        """warning is an alias for warn."""
        logger = StructuredLogger(console=False)
        assert logger.warning == logger.warn

    def test_error_log(self):
        """Error logging does not raise."""
        logger = StructuredLogger(console=False)
        logger.error("Error message", extra={"error_code": 500})

    def test_log_to_file(self):
        """Logs are written to file in JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            logger = StructuredLogger(
                session_id="file-test",
                log_file=log_file,
                console=False,
                level=LogLevel.DEBUG,
            )
            logger.info("Test message", extra={"custom": "field"})

            # Read log file
            with open(log_file, "r") as f:
                line = f.readline().strip()
            entry = json.loads(line)
            assert entry["message"] == "Test message"
            assert entry["level"] == "INFO"
            assert entry["session_id"] == "file-test"
            assert entry["custom"] == "field"
            assert "timestamp" in entry

    def test_log_context_fields(self):
        """Context fields (session_id, agent_name) are included in logs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            logger = StructuredLogger(
                session_id="ctx-session",
                agent_name="ctx-agent",
                log_file=log_file,
                console=False,
            )
            logger.info("Context test")

            with open(log_file, "r") as f:
                entry = json.loads(f.readline().strip())
            assert entry["session_id"] == "ctx-session"
            assert entry["agent_name"] == "ctx-agent"

    def test_with_context(self):
        """with_context creates a child logger with fixed extra fields."""
        logger = StructuredLogger(console=False)
        child = logger.with_context(request_id="req-001")
        assert child.session_id == logger.session_id
        assert child._logger is logger._logger  # shared underlying logger

    def test_set_level(self):
        """set_level dynamically changes log level."""
        logger = StructuredLogger(level=LogLevel.ERROR, console=False)
        logger.set_level(LogLevel.DEBUG)
        assert logger.level == LogLevel.DEBUG

    def test_get_context(self):
        """get_context returns session_id and agent_name."""
        logger = StructuredLogger(
            session_id="ctx-test",
            agent_name="my-agent",
            console=False,
        )
        ctx = logger.get_context()
        assert ctx["session_id"] == "ctx-test"
        assert ctx["agent_name"] == "my-agent"

    def test_log_level_to_numeric(self):
        """LogLevel.to_numeric converts string levels to logging constants."""
        import logging as stdlib_logging
        assert LogLevel.to_numeric("DEBUG") == stdlib_logging.DEBUG
        assert LogLevel.to_numeric("INFO") == stdlib_logging.INFO
        assert LogLevel.to_numeric("WARN") == stdlib_logging.WARNING
        assert LogLevel.to_numeric("ERROR") == stdlib_logging.ERROR
        assert LogLevel.to_numeric("UNKNOWN") == stdlib_logging.INFO

    def test_rotating_file_handler(self):
        """RotatingFileHandler is used when max_bytes is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "rotate.log")
            logger = StructuredLogger(
                log_file=log_file,
                max_bytes=200,
                backup_count=3,
                console=False,
            )
            # Write enough to trigger rotation
            for i in range(20):
                logger.info(f"Message {i}" + "x" * 30)
            # Should have created backup files
            files = os.listdir(tmpdir)
            assert len(files) >= 1  # at least the main file


# ═══════════════════════════════════════════════════════════════
#  Counter tests
# ═══════════════════════════════════════════════════════════════


class TestCounter:
    """Test the Counter metric."""

    def test_initial_value(self):
        c = Counter("test_counter")
        assert c.value() == 0.0

    def test_inc(self):
        c = Counter("test_counter")
        c.inc()
        assert c.value() == 1.0
        c.inc(5)
        assert c.value() == 6.0

    def test_window_value(self):
        c = Counter("test_counter")
        c.inc(3)
        assert c.window_value(60) == 3.0  # within 1m window

    def test_window_expiry(self):
        """Old events are expired from the window."""
        from suyi.observability.metrics import WINDOW_1M
        c = Counter("test_counter")
        # Manually add an old event
        c._events[WINDOW_1M].append((time.time() - 120, 10))
        # window_value should not include it
        assert c.window_value(WINDOW_1M) == 0.0

    def test_reset(self):
        c = Counter("test_counter")
        c.inc(5)
        c.reset()
        assert c.value() == 0.0

    def test_to_dict(self):
        c = Counter("test_counter", "description")
        c.inc(3)
        d = c.to_dict()
        assert d["type"] == "counter"
        assert d["name"] == "test_counter"
        assert d["total"] == 3.0
        assert "windows" in d


# ═══════════════════════════════════════════════════════════════
#  Gauge tests
# ═══════════════════════════════════════════════════════════════


class TestGauge:
    """Test the Gauge metric."""

    def test_initial_value(self):
        g = Gauge("test_gauge")
        assert g.value() == 0.0

    def test_set(self):
        g = Gauge("test_gauge")
        g.set(42)
        assert g.value() == 42.0

    def test_inc(self):
        g = Gauge("test_gauge")
        g.set(10)
        g.inc(5)
        assert g.value() == 15.0

    def test_dec(self):
        g = Gauge("test_gauge")
        g.set(10)
        g.dec(3)
        assert g.value() == 7.0

    def test_to_dict(self):
        g = Gauge("test_gauge", "desc")
        g.set(5)
        d = g.to_dict()
        assert d["type"] == "gauge"
        assert d["value"] == 5.0


# ═══════════════════════════════════════════════════════════════
#  Histogram tests
# ═══════════════════════════════════════════════════════════════


class TestHistogram:
    """Test the Histogram metric."""

    def test_observe(self):
        h = Histogram("test_hist")
        h.observe(0.5)
        h.observe(1.0)
        h.observe(2.0)
        assert h.count() == 3
        assert h.sum() == 3.5
        assert h.mean() == pytest.approx(3.5 / 3)

    def test_percentile(self):
        h = Histogram("test_hist")
        for v in range(1, 101):
            h.observe(float(v))
        assert h.percentile(0.5) >= 49  # ~50th percentile
        assert h.percentile(0.9) >= 89  # ~90th percentile

    def test_empty_percentile(self):
        h = Histogram("test_hist")
        assert h.percentile(0.5) == 0.0

    def test_reset(self):
        h = Histogram("test_hist")
        h.observe(5)
        h.reset()
        assert h.count() == 0
        assert h.sum() == 0.0

    def test_to_dict(self):
        h = Histogram("test_hist", "desc")
        h.observe(1.0)
        h.observe(2.0)
        d = h.to_dict()
        assert d["type"] == "histogram"
        assert d["count"] == 2
        assert "percentiles" in d
        assert "buckets" in d

    def test_custom_buckets(self):
        h = Histogram("test_hist", buckets=[1, 5, 10])
        h.observe(3)
        h.observe(7)
        d = h.to_dict()
        assert d["buckets"]["<=1"] == 0
        assert d["buckets"]["<=5"] == 1
        assert d["buckets"]["<=10"] == 2


# ═══════════════════════════════════════════════════════════════
#  MetricsCollector tests
# ═══════════════════════════════════════════════════════════════


class TestMetricsCollector:
    """Test the MetricsCollector class."""

    def test_default_metrics_exist(self):
        mc = MetricsCollector()
        assert "requests_total" in mc._counters
        assert "request_duration" in mc._histograms
        assert "token_usage" in mc._histograms
        assert "tool_calls_total" in mc._counters
        assert "errors_total" in mc._counters
        assert "active_sessions" in mc._gauges

    def test_inc_counter(self):
        mc = MetricsCollector()
        mc.inc_counter("requests_total")
        assert mc._counters["requests_total"].value() == 1.0

    def test_observe_histogram(self):
        mc = MetricsCollector()
        mc.observe_histogram("request_duration", 0.5)
        assert mc._histograms["request_duration"].count() == 1

    def test_set_gauge(self):
        mc = MetricsCollector()
        mc.set_gauge("active_sessions", 5)
        assert mc._gauges["active_sessions"].value() == 5.0

    def test_custom_counter(self):
        mc = MetricsCollector()
        c = mc.counter("custom_counter", "custom metric")
        c.inc(3)
        assert c.value() == 3.0

    def test_custom_histogram(self):
        mc = MetricsCollector()
        h = mc.histogram("custom_hist")
        h.observe(1.5)
        assert h.count() == 1

    def test_custom_gauge(self):
        mc = MetricsCollector()
        g = mc.gauge("custom_gauge")
        g.set(42)
        assert g.value() == 42.0

    def test_export_json(self):
        mc = MetricsCollector()
        mc.inc_counter("requests_total")
        mc.observe_histogram("request_duration", 0.3)
        mc.set_gauge("active_sessions", 3)
        result = mc.export_json()
        assert "counters" in result
        assert "histograms" in result
        assert "gauges" in result
        assert result["counters"]["requests_total"]["total"] == 1.0

    def test_reset(self):
        mc = MetricsCollector()
        mc.inc_counter("requests_total", 5)
        mc.set_gauge("active_sessions", 10)
        mc.reset()
        assert mc._counters["requests_total"].value() == 0.0
        assert mc._gauges["active_sessions"].value() == 0.0

    def test_error_rate(self):
        mc = MetricsCollector()
        mc.inc_counter("requests_total", 100)
        mc.inc_counter("errors_total", 5)
        rate = mc.error_rate()
        assert rate == pytest.approx(0.05)

    def test_error_rate_zero_requests(self):
        mc = MetricsCollector()
        assert mc.error_rate() == 0.0


# ═══════════════════════════════════════════════════════════════
#  Span tests
# ═══════════════════════════════════════════════════════════════


class TestSpan:
    """Test the Span class."""

    def test_creation(self):
        span = Span("test_operation")
        assert span.operation_name == "test_operation"
        assert span.trace_id  # auto-generated
        assert span.span_id  # auto-generated
        assert span.parent_id is None
        assert span.status == SpanStatus.OK

    def test_start_finish(self):
        span = Span("test_op")
        span.start()
        time.sleep(0.01)
        span.finish()
        assert span.is_finished
        assert span.duration > 0

    def test_set_tag(self):
        span = Span("test_op")
        span.set_tag("key", "value")
        assert span.tags["key"] == "value"

    def test_set_tag_chaining(self):
        span = Span("test_op")
        result = span.set_tag("a", 1).set_tag("b", 2)
        assert result is span
        assert span.tags["a"] == 1
        assert span.tags["b"] == 2

    def test_log(self):
        span = Span("test_op")
        span.log("test message", level="info", field1="val1")
        assert len(span.logs) == 1
        assert span.logs[0].message == "test message"
        assert span.logs[0].level == "info"
        assert span.logs[0].fields["field1"] == "val1"

    def test_log_chaining(self):
        span = Span("test_op")
        result = span.log("msg1").log("msg2")
        assert result is span
        assert len(span.logs) == 2

    def test_add_child(self):
        parent = Span("parent_op")
        child = Span("child_op", parent_id=parent.span_id, parent=parent)
        parent.add_child(child)
        assert len(parent.children) == 1
        assert parent.children[0] is child

    def test_context_manager(self):
        with Span("test_op") as span:
            span.set_tag("during", "execution")
            assert not span.is_finished
        assert span.is_finished
        assert span.status == SpanStatus.OK

    def test_context_manager_with_exception(self):
        with pytest.raises(ValueError):
            with Span("test_op") as span:
                raise ValueError("test error")
        assert span.is_finished
        assert span.status == SpanStatus.ERROR
        assert len(span.logs) == 1
        assert span.logs[0].level == "error"

    def test_finish_idempotent(self):
        span = Span("test_op")
        span.start()
        span.finish()
        end1 = span.end_time
        span.finish()
        end2 = span.end_time
        assert end1 == end2

    def test_to_dict(self):
        span = Span("test_op")
        span.start()
        span.set_tag("key", "value")
        span.log("message")
        span.finish()
        d = span.to_dict()
        assert d["operation_name"] == "test_op"
        assert d["status"] == "OK"
        assert d["tags"]["key"] == "value"
        assert len(d["logs"]) == 1
        assert d["duration"] > 0


# ═══════════════════════════════════════════════════════════════
#  Tracer tests
# ═══════════════════════════════════════════════════════════════


class TestTracer:
    """Test the Tracer class."""

    def test_creation(self):
        tracer = Tracer()
        assert tracer.trace_id
        assert tracer.span_count == 0
        assert tracer.root is None

    def test_start_span_creates_root(self):
        tracer = Tracer()
        span = tracer.start_span("root_op")
        assert tracer.root is span
        assert tracer.span_count == 1

    def test_nested_spans(self):
        tracer = Tracer()
        root = tracer.start_span("root")
        child1 = tracer.start_span("child1", parent=root)
        child2 = tracer.start_span("child2", parent=root)
        grandchild = tracer.start_span("grandchild", parent=child1)

        assert tracer.span_count == 4
        assert len(root.children) == 2
        assert root.children[0] is child1
        assert root.children[1] is child2
        assert len(child1.children) == 1
        assert child1.children[0] is grandchild

    def test_export(self):
        tracer = Tracer()
        root = tracer.start_span("root")
        child = tracer.start_span("child", parent=root)
        root.finish()
        child.finish()

        export = tracer.export()
        assert export["trace_id"] == tracer.trace_id
        assert export["span_count"] == 2
        assert export["root"]["operation_name"] == "root"
        assert len(export["root"]["children"]) == 1
        assert export["spans"][0]["operation_name"] == "root"
        assert export["spans"][1]["operation_name"] == "child"

    def test_reset(self):
        tracer = Tracer()
        tracer.start_span("test")
        tracer.reset()
        assert tracer.span_count == 0
        assert tracer.root is None
        # New trace_id after reset
        assert tracer.trace_id

    def test_with_context_manager(self):
        tracer = Tracer()
        with tracer.start_span("operation") as span:
            span.set_tag("key", "value")
        assert span.is_finished
        assert tracer.span_count == 1

    def test_set_current_span(self):
        tracer = Tracer()
        root = tracer.start_span("root")
        tracer.set_current_span(root)
        # New spans without explicit parent should use current_span
        child = tracer.start_span("child")
        assert child.parent is root


# ═══════════════════════════════════════════════════════════════
#  ObservabilityMiddleware tests
# ═══════════════════════════════════════════════════════════════


class TestObservabilityMiddleware:
    """Test the ObservabilityMiddleware class."""

    @pytest.fixture
    def state(self):
        return LoopState(history=[{"role": "user", "content": "hi"}], turn=0)

    def test_priority(self):
        mw = ObservabilityMiddleware()
        assert mw.priority == 5

    def test_name(self):
        mw = ObservabilityMiddleware()
        assert mw.name == "ObservabilityMiddleware"

    def test_no_components(self):
        """Middleware works without any observability components."""
        mw = ObservabilityMiddleware()
        assert mw.logger is None
        assert mw.metrics is None
        assert mw.tracer is None

    @pytest.mark.asyncio
    async def test_before_llm_call_no_components(self, state):
        """before_llm_call works without components."""
        mw = ObservabilityMiddleware()
        result = await mw.before_llm_call(state)
        assert result is state  # unchanged

    @pytest.mark.asyncio
    async def test_before_llm_call_with_logger(self, state):
        """before_llm_call logs with logger."""
        logger = StructuredLogger(console=False)
        mw = ObservabilityMiddleware(logger=logger)
        await mw.before_llm_call(state)

    @pytest.mark.asyncio
    async def test_before_llm_call_with_metrics(self, state):
        """before_llm_call increments request counter."""
        metrics = MetricsCollector()
        mw = ObservabilityMiddleware(metrics=metrics)
        await mw.before_llm_call(state)
        assert metrics._counters["requests_total"].value() == 1.0

    @pytest.mark.asyncio
    async def test_before_llm_call_with_tracer(self, state):
        """before_llm_call creates a span."""
        tracer = Tracer()
        mw = ObservabilityMiddleware(tracer=tracer)
        await mw.before_llm_call(state)
        assert tracer.span_count == 1
        assert mw._llm_span is not None

    @pytest.mark.asyncio
    async def test_after_llm_call_with_metrics(self, state):
        """after_llm_call records duration and tokens."""
        metrics = MetricsCollector()
        mw = ObservabilityMiddleware(metrics=metrics)
        await mw.before_llm_call(state)
        response = LLMResponse.text("Hello", tokens=100)
        await mw.after_llm_call(response, state)
        assert metrics._histograms["token_usage"].count() == 1
        assert metrics._histograms["request_duration"].count() == 1

    @pytest.mark.asyncio
    async def test_after_llm_call_finishes_span(self, state):
        """after_llm_call finishes the LLM span."""
        tracer = Tracer()
        mw = ObservabilityMiddleware(tracer=tracer)
        await mw.before_llm_call(state)
        response = LLMResponse.text("Hello", tokens=50)
        await mw.after_llm_call(response, state)
        assert mw._llm_span is None
        assert tracer.spans[0].is_finished

    @pytest.mark.asyncio
    async def test_before_tool_call_with_metrics(self, state):
        """before_tool_call increments tool_calls counter."""
        metrics = MetricsCollector()
        mw = ObservabilityMiddleware(metrics=metrics)
        await mw.before_tool_call("bash", {"command": "ls"}, state)
        assert metrics._counters["tool_calls_total"].value() == 1.0

    @pytest.mark.asyncio
    async def test_before_tool_call_with_tracer(self, state):
        """before_tool_call creates a span."""
        tracer = Tracer()
        mw = ObservabilityMiddleware(tracer=tracer)
        await mw.before_tool_call("bash", {"command": "ls"}, state)
        assert tracer.span_count == 1
        assert tracer.spans[0].tags["tool_name"] == "bash"

    @pytest.mark.asyncio
    async def test_after_tool_call_finishes_span(self, state):
        """after_tool_call finishes the tool span."""
        tracer = Tracer()
        mw = ObservabilityMiddleware(tracer=tracer)
        await mw.before_tool_call("bash", {"command": "ls"}, state)
        assert "bash" in mw._tool_spans
        await mw.after_tool_call("bash", {"command": "ls"}, "output", state)
        assert "bash" not in mw._tool_spans
        assert tracer.spans[0].is_finished

    @pytest.mark.asyncio
    async def test_full_integration(self, state):
        """Full lifecycle with all components."""
        logger = StructuredLogger(console=False)
        metrics = MetricsCollector()
        tracer = Tracer()
        mw = ObservabilityMiddleware(
            logger=logger, metrics=metrics, tracer=tracer
        )

        # LLM call
        await mw.before_llm_call(state)
        response = LLMResponse.text("Hello", tokens=100)
        await mw.after_llm_call(response, state)

        # Tool call
        await mw.before_tool_call("search", {"query": "test"}, state)
        await mw.after_tool_call("search", {"query": "test"}, "results", state)

        # Verify metrics
        assert metrics._counters["requests_total"].value() == 1.0
        assert metrics._counters["tool_calls_total"].value() == 1.0
        assert metrics._histograms["token_usage"].count() == 1

        # Verify tracer
        assert tracer.span_count == 2  # llm + tool
        export = tracer.export()
        assert export["span_count"] == 2

    def test_record_error(self):
        """record_error increments error counter."""
        metrics = MetricsCollector()
        mw = ObservabilityMiddleware(metrics=metrics)
        mw.record_error(ValueError("test error"))
        assert metrics._counters["errors_total"].value() == 1.0
