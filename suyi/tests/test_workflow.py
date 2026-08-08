"""Tests for Workflow Engine — DAG 定义、工作流执行。"""

import asyncio
import pytest

from suyi.workflow.dag import Node, NodeStatus, Edge, DAG, DAGValidationError
from suyi.workflow.engine import WorkflowEngine, WorkflowResult, FailurePolicy


# ═════════════════════════════════════════════════════════════
#  Node & NodeStatus
# ═════════════════════════════════════════════════════════════

class TestNode:
    """节点测试。"""

    def test_creation(self):
        node = Node(name="step1")
        assert node.name == "step1"
        assert node.status == NodeStatus.PENDING
        assert node.handler is None

    def test_with_handler(self):
        async def handler(ctx):
            return "done"
        node = Node(name="step1", handler=handler)
        assert node.handler is not None

    def test_config_defaults(self):
        node = Node(name="step1")
        assert node.max_retries == 3
        assert node.timeout == 30.0

    def test_config_override(self):
        node = Node(name="step1", config={"max_retries": 5, "timeout": 10.0})
        assert node.max_retries == 5
        assert node.timeout == 10.0

    def test_to_dict(self):
        node = Node(name="step1")
        d = node.to_dict()
        assert d["name"] == "step1"
        assert d["status"] == "pending"

    def test_auto_id(self):
        n1 = Node(name="a")
        n2 = Node(name="b")
        assert n1.id != n2.id


# ═════════════════════════════════════════════════════════════
#  Edge
# ═════════════════════════════════════════════════════════════

class TestEdge:
    """边测试。"""

    def test_creation(self):
        edge = Edge(source="a", target="b")
        assert edge.source == "a"
        assert edge.target == "b"
        assert edge.condition is None

    def test_with_condition(self):
        def cond(ctx):
            return ctx.get("flag", False)
        edge = Edge(source="a", target="b", condition=cond)
        assert edge.should_traverse({"flag": True})
        assert not edge.should_traverse({"flag": False})

    def test_no_condition_always_traverses(self):
        edge = Edge(source="a", target="b")
        assert edge.should_traverse({})
        assert edge.should_traverse({"any": "thing"})

    def test_condition_exception(self):
        def bad_cond(ctx):
            raise ValueError("boom")
        edge = Edge(source="a", target="b", condition=bad_cond)
        assert not edge.should_traverse({})

    def test_to_dict(self):
        edge = Edge(source="a", target="b", name="edge1")
        d = edge.to_dict()
        assert d["source"] == "a"
        assert d["target"] == "b"
        assert d["name"] == "edge1"
        assert d["has_condition"] is False


# ═════════════════════════════════════════════════════════════
#  DAG
# ═════════════════════════════════════════════════════════════

class TestDAG:
    """DAG 测试。"""

    def test_add_node(self):
        dag = DAG()
        node = dag.add_node(Node(name="step1"))
        assert dag.node_count == 1
        assert dag.nodes[node.id] is node

    def test_duplicate_node(self):
        dag = DAG()
        node = Node(name="step1")
        dag.add_node(node)
        with pytest.raises(DAGValidationError):
            dag.add_node(node)

    def test_add_edge(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="a"))
        n2 = dag.add_node(Node(name="b"))
        edge = dag.add_edge(n1.id, n2.id)
        assert dag.edge_count == 1
        assert edge.source == n1.id
        assert edge.target == n2.id

    def test_edge_nonexistent_node(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="a"))
        with pytest.raises(DAGValidationError):
            dag.add_edge(n1.id, "nonexistent")
        with pytest.raises(DAGValidationError):
            dag.add_edge("nonexistent", n1.id)

    def test_cycle_detection(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="a"))
        n2 = dag.add_node(Node(name="b"))
        n3 = dag.add_node(Node(name="c"))
        dag.add_edge(n1.id, n2.id)
        dag.add_edge(n2.id, n3.id)
        with pytest.raises(DAGValidationError):
            dag.add_edge(n3.id, n1.id)

    def test_topological_sort(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="a"))
        n2 = dag.add_node(Node(name="b"))
        n3 = dag.add_node(Node(name="c"))
        dag.add_edge(n1.id, n2.id)
        dag.add_edge(n2.id, n3.id)
        order = dag.topological_sort()
        assert order.index(n1.id) < order.index(n2.id)
        assert order.index(n2.id) < order.index(n3.id)

    def test_get_roots(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="a"))
        n2 = dag.add_node(Node(name="b"))
        dag.add_edge(n1.id, n2.id)
        roots = dag.get_roots()
        assert len(roots) == 1
        assert roots[0].id == n1.id

    def test_get_leaves(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="a"))
        n2 = dag.add_node(Node(name="b"))
        dag.add_edge(n1.id, n2.id)
        leaves = dag.get_leaves()
        assert len(leaves) == 1
        assert leaves[0].id == n2.id

    def test_get_successors(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="a"))
        n2 = dag.add_node(Node(name="b"))
        n3 = dag.add_node(Node(name="c"))
        dag.add_edge(n1.id, n2.id)
        dag.add_edge(n1.id, n3.id)
        successors = dag.get_successors(n1.id)
        assert len(successors) == 2

    def test_conditional_successors(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="a"))
        n2 = dag.add_node(Node(name="b"))
        n3 = dag.add_node(Node(name="c"))
        dag.add_edge(n1.id, n2.id, condition=lambda ctx: ctx.get("go_b", True))
        dag.add_edge(n1.id, n3.id, condition=lambda ctx: ctx.get("go_c", False))
        # 默认走 b
        successors = dag.get_successors(n1.id, {"go_b": True, "go_c": False})
        assert len(successors) == 1
        assert successors[0].id == n2.id
        # 切换到 c
        successors = dag.get_successors(n1.id, {"go_b": False, "go_c": True})
        assert len(successors) == 1
        assert successors[0].id == n3.id

    def test_get_predecessors(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="a"))
        n2 = dag.add_node(Node(name="b"))
        dag.add_edge(n1.id, n2.id)
        preds = dag.get_predecessors(n2.id)
        assert len(preds) == 1
        assert preds[0].id == n1.id

    def test_remove_node(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="a"))
        n2 = dag.add_node(Node(name="b"))
        dag.add_edge(n1.id, n2.id)
        dag.remove_node(n2.id)
        assert dag.node_count == 1
        assert dag.edge_count == 0

    def test_parallel_groups(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="a"))
        n2 = dag.add_node(Node(name="b"))
        n3 = dag.add_node(Node(name="c"))
        n4 = dag.add_node(Node(name="d"))
        dag.add_edge(n1.id, n3.id)
        dag.add_edge(n2.id, n3.id)
        dag.add_edge(n3.id, n4.id)
        groups = dag.get_parallel_groups()
        # 第一层: a, b 并行
        assert n1.id in groups[0]
        assert n2.id in groups[0]
        # 第二层: c
        assert n3.id in groups[1]
        # 第三层: d
        assert n4.id in groups[2]

    def test_to_dict(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="a"))
        n2 = dag.add_node(Node(name="b"))
        dag.add_edge(n1.id, n2.id)
        d = dag.to_dict()
        assert len(d["nodes"]) == 2
        assert len(d["edges"]) == 1


# ═════════════════════════════════════════════════════════════
#  WorkflowEngine
# ═════════════════════════════════════════════════════════════

class TestWorkflowEngine:
    """工作流引擎测试。"""

    @pytest.mark.asyncio
    async def test_simple_linear(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="step1", handler=lambda ctx: "result1"))
        n2 = dag.add_node(Node(name="step2", handler=lambda ctx: "result2"))
        dag.add_edge(n1.id, n2.id)
        engine = WorkflowEngine(dag)
        result = await engine.run({"input": "data"})
        assert result.success
        assert result.nodes_executed == 2

    @pytest.mark.asyncio
    async def test_async_handlers(self):
        async def handler1(ctx):
            await asyncio.sleep(0.01)
            return "async_result"

        async def handler2(ctx):
            await asyncio.sleep(0.01)
            return "async_result2"

        dag = DAG()
        n1 = dag.add_node(Node(name="a", handler=handler1))
        n2 = dag.add_node(Node(name="b", handler=handler2))
        dag.add_edge(n1.id, n2.id)
        engine = WorkflowEngine(dag)
        result = await engine.run()
        assert result.success
        assert result.node_results[n1.id] == "async_result"

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        execution_order = []

        async def slow_handler(ctx):
            await asyncio.sleep(0.05)
            execution_order.append(ctx.get("name", "unknown"))
            return "done"

        dag = DAG()
        n1 = dag.add_node(Node(name="parallel1", handler=slow_handler))
        n2 = dag.add_node(Node(name="parallel2", handler=slow_handler))
        n3 = dag.add_node(Node(name="join", handler=slow_handler))
        dag.add_edge(n1.id, n3.id)
        dag.add_edge(n2.id, n3.id)
        engine = WorkflowEngine(dag)
        result = await engine.run({"name": "test"})
        assert result.success
        # 三个节点都应执行成功
        assert result.nodes_executed == 3
        # 上下文中应该有结果
        assert result.context.get("parallel1") == "done"
        assert result.context.get("parallel2") == "done"
        assert result.context.get("join") == "done"

    @pytest.mark.asyncio
    async def test_failure_stop(self):
        def failing_handler(ctx):
            raise RuntimeError("Intentional failure")

        dag = DAG()
        n1 = dag.add_node(Node(name="fail", handler=failing_handler, config={"max_retries": 1}))
        n2 = dag.add_node(Node(name="after", handler=lambda ctx: "ok"))
        dag.add_edge(n1.id, n2.id)
        engine = WorkflowEngine(dag, failure_policy=FailurePolicy.STOP)
        result = await engine.run()
        assert not result.success
        assert result.nodes_failed >= 1
        assert "after" not in result.node_results

    @pytest.mark.asyncio
    async def test_failure_continue(self):
        call_count = {"n": 0}

        def failing_handler(ctx):
            call_count["n"] += 1
            raise RuntimeError("Intentional failure")

        def ok_handler(ctx):
            return "ok"

        dag = DAG()
        n1 = dag.add_node(Node(name="fail_node", handler=failing_handler, config={"max_retries": 1}))
        n2 = dag.add_node(Node(name="ok_node", handler=ok_handler))
        engine = WorkflowEngine(dag, failure_policy=FailurePolicy.CONTINUE)
        result = await engine.run()
        # n2 应该被执行
        assert n2.id in result.node_results

    @pytest.mark.asyncio
    async def test_retry(self):
        attempt_count = {"n": 0}

        def flaky_handler(ctx):
            attempt_count["n"] += 1
            if attempt_count["n"] < 2:
                raise RuntimeError("Not yet")
            return "success"

        dag = DAG()
        n1 = dag.add_node(Node(name="flaky", handler=flaky_handler, config={"max_retries": 3}))
        engine = WorkflowEngine(dag)
        result = await engine.run()
        assert result.success
        assert attempt_count["n"] == 2

    @pytest.mark.asyncio
    async def test_conditional_branch(self):
        async def handler_a(ctx):
            return "A"
        async def handler_b(ctx):
            return "B"
        async def handler_c(ctx):
            return "C"

        dag = DAG()
        start = dag.add_node(Node(name="start", handler=handler_a))
        branch_b = dag.add_node(Node(name="branch_b", handler=handler_b))
        branch_c = dag.add_node(Node(name="branch_c", handler=handler_c))
        dag.add_edge(start.id, branch_b.id, condition=lambda ctx: ctx.get("path") == "b")
        dag.add_edge(start.id, branch_c.id, condition=lambda ctx: ctx.get("path") == "c")
        engine = WorkflowEngine(dag)
        result = await engine.run({"path": "b"})
        assert result.success
        assert branch_b.id in result.node_results
        assert branch_c.id not in result.node_results

    @pytest.mark.asyncio
    async def test_get_node_status(self):
        async def handler(ctx):
            return "done"
        dag = DAG()
        n1 = dag.add_node(Node(name="step", handler=handler))
        engine = WorkflowEngine(dag)
        assert engine.get_node_status(n1.id) == NodeStatus.PENDING
        await engine.run()
        assert engine.get_node_status(n1.id) == NodeStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_reset(self):
        async def handler(ctx):
            return "done"
        dag = DAG()
        n1 = dag.add_node(Node(name="step", handler=handler))
        engine = WorkflowEngine(dag)
        await engine.run()
        engine.reset()
        assert engine.get_node_status(n1.id) == NodeStatus.PENDING

    @pytest.mark.asyncio
    async def test_workflow_result_to_dict(self):
        dag = DAG()
        n1 = dag.add_node(Node(name="step1", handler=lambda ctx: "ok"))
        engine = WorkflowEngine(dag)
        result = await engine.run()
        d = result.to_dict()
        assert "success" in d
        assert "execution_time" in d
        assert "nodes_executed" in d

    @pytest.mark.asyncio
    async def test_empty_dag(self):
        dag = DAG()
        engine = WorkflowEngine(dag)
        result = await engine.run()
        assert result.success
        assert result.nodes_executed == 0

    @pytest.mark.asyncio
    async def test_context_propagation(self):
        async def step1(ctx):
            ctx["step1_done"] = True
            return "step1_result"
        async def step2(ctx):
            assert ctx.get("step1_done") is True
            return "step2_result"

        dag = DAG()
        n1 = dag.add_node(Node(name="step1", handler=step1))
        n2 = dag.add_node(Node(name="step2", handler=step2))
        dag.add_edge(n1.id, n2.id)
        engine = WorkflowEngine(dag)
        result = await engine.run()
        assert result.success
        assert result.context.get("step1_done") is True
