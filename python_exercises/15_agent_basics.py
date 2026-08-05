"""
第四阶段 4.2 AI Agent 开发基础练习
从零实现 Function Calling、ReAct、规划、记忆系统、多Agent协作
共 10 题，每题独立测试
"""

import numpy as np
import json, re, time, hashlib
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional, Callable

# ============================================================
# Test 01: Function Calling / Tool Use
# 实现工具注册、调度和执行
# ============================================================

class ToolRegistry:
    """工具注册表"""
    def __init__(self):
        self.tools = {}

    def register(self, name, func, description, parameters):
        """注册工具"""
        self.tools[name] = {
            "func": func,
            "description": description,
            "parameters": parameters  # 参数 schema: {param_name: type}
        }

    def call(self, name, **kwargs):
        """调用工具"""
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found. Available: {list(self.tools.keys())}")
        tool = self.tools[name]
        # 参数校验
        for param_name, param_type in tool["parameters"].items():
            if param_name not in kwargs:
                raise ValueError(f"Missing required parameter '{param_name}' for tool '{name}'")
            if not isinstance(kwargs[param_name], param_type):
                raise TypeError(f"Parameter '{param_name}' expected {param_type}, got {type(kwargs[param_name])}")
        return tool["func"](**kwargs)

    def get_schema(self):
        """获取所有工具的 schema 描述"""
        return {
            name: {
                "description": t["description"],
                "parameters": {k: v.__name__ for k, v in t["parameters"].items()}
            }
            for name, t in self.tools.items()
        }

def test_01_function_calling():
    registry = ToolRegistry()
    # 注册计算器工具
    registry.register("add", lambda a, b: a + b, "两数相加", {"a": int, "b": int})
    registry.register("multiply", lambda a, b: a * b, "两数相乘", {"a": int, "b": int})
    registry.register("search", lambda query: f"搜索结果: {query}", "搜索信息", {"query": str})

    # 正常调用
    assert registry.call("add", a=3, b=5) == 8
    assert registry.call("multiply", a=4, b=6) == 24
    assert "测试" in registry.call("search", query="测试")

    # Schema 验证
    schema = registry.get_schema()
    assert "add" in schema
    assert schema["add"]["parameters"]["a"] == "int"
    assert "search" in schema

    # 调用不存在的工具
    try:
        registry.call("divide", a=10, b=2)
        assert False, "Should raise ValueError for unknown tool"
    except ValueError:
        pass

    # 参数类型错误
    try:
        registry.call("add", a="3", b=5)
        assert False, "Should raise TypeError for wrong type"
    except TypeError:
        pass

    # 模拟 LLM 决策: 根据 schema 选择工具
    def mock_llm_decision(query, available_tools):
        """模拟 LLM 根据查询选择工具"""
        if "加" in query or "add" in query.lower():
            return ("add", {"a": 3, "b": 5})
        elif "乘" in query or "multiply" in query.lower():
            return ("multiply", {"a": 4, "b": 6})
        elif "搜索" in query or "search" in query.lower():
            return ("search", {"query": "Python"})
        return (None, {})

    tool_name, params = mock_llm_decision("帮我计算 3 加 5", registry.get_schema())
    result = registry.call(tool_name, **params)
    assert result == 8, f"Expected 8, got {result}"
    print("✅ Test 01 passed: Function Calling / Tool Use")

# ============================================================
# Test 02: ReAct (Reasoning + Acting) 模式
# ============================================================

class ReActAgent:
    """ReAct Agent: Thought -> Action -> Observation 循环"""
    def __init__(self, tools, max_iterations=5):
        self.tools = tools  # ToolRegistry
        self.max_iterations = max_iterations
        self.history = []   # 记录所有步骤

    def run(self, query, decision_fn):
        """
        decision_fn: (query, history, tool_schema) -> (thought, action_name, action_input)
                     返回 (None, None, None) 表示最终答案
        返回最终答案和过程记录
        """
        self.history = []
        for i in range(self.max_iterations):
            thought, action_name, action_input = decision_fn(query, self.history, self.tools.get_schema())
            self.history.append({"step": i, "thought": thought})
            if action_name is None:
                self.history[-1]["answer"] = action_input  # action_input 作为最终答案
                return action_input, self.history
            # 执行工具
            observation = self.tools.call(action_name, **action_input)
            self.history[-1]["action"] = action_name
            self.history[-1]["action_input"] = action_input
            self.history[-1]["observation"] = observation
        return "达到最大迭代次数", self.history

def test_02_react():
    registry = ToolRegistry()
    registry.register("search", lambda query: f"关于'{query}'的信息: Python是一种编程语言", "搜索", {"query": str})
    registry.register("calculate", lambda expression: str(eval(expression)), "计算", {"expression": str})

    agent = ReActAgent(registry, max_iterations=5)

    # 预定义决策逻辑（模拟 LLM 的推理过程）
    def decision_fn(query, history, schema):
        if len(history) == 0:
            # 第一步：搜索
            return ("需要先搜索Python的信息", "search", {"query": "Python"})
        elif len(history) == 1:
            # 第二步：搜索结果已经有了，回答
            obs = history[-1]["observation"]
            return (f"根据搜索结果回答问题", None, f"答案: {obs}")
        return ("直接回答", None, "答案: 未知")

    answer, trace = agent.run("Python是什么?", decision_fn)
    assert "Python" in answer, f"Answer should contain Python, got: {answer}"
    assert len(trace) == 2, f"Should take 2 steps, got {len(trace)}"
    assert trace[0]["thought"] == "需要先搜索Python的信息"
    assert trace[0]["action"] == "search"
    assert "observation" in trace[0]
    assert "answer" in trace[1]
    print(f"   Trace steps: {len(trace)}")
    for t in trace:
        if "action" in t:
            print(f"   Step {t['step']}: Thought={t['thought']}, Action={t['action']}, Obs={t['observation'][:30]}")
        else:
            print(f"   Step {t['step']}: Thought={t['thought']}, Answer={t['answer'][:30]}")
    print("✅ Test 02 passed: ReAct (Reasoning + Acting)")

# ============================================================
# Test 03: 任务规划与分解 (Plan-and-Execute)
# ============================================================

class Planner:
    """任务规划器：将复杂任务分解为子任务"""
    def __init__(self):
        self.plans = {}

    def create_plan(self, goal, subtasks):
        """创建执行计划"""
        plan_id = hashlib.md5(goal.encode()).hexdigest()[:8]
        self.plans[plan_id] = {
            "goal": goal,
            "subtasks": [{"id": i, "desc": st, "status": "pending"} for i, st in enumerate(subtasks)],
            "completed": [],
            "results": {}
        }
        return plan_id

    def execute_plan(self, plan_id, executor_fn):
        """按顺序执行计划"""
        plan = self.plans[plan_id]
        for task in plan["subtasks"]:
            task["status"] = "running"
            try:
                result = executor_fn(task["desc"])
                task["status"] = "completed"
                task["result"] = result
                plan["results"][task["id"]] = result
                plan["completed"].append(task["id"])
            except Exception as e:
                task["status"] = "failed"
                task["error"] = str(e)
                break
        all_done = all(t["status"] == "completed" for t in plan["subtasks"])
        return all_done, plan

    def get_status(self, plan_id):
        plan = self.plans[plan_id]
        return {
            "goal": plan["goal"],
            "total": len(plan["subtasks"]),
            "completed": len(plan["completed"]),
            "pending": len([t for t in plan["subtasks"] if t["status"] == "pending"]),
            "failed": len([t for t in plan["subtasks"] if t["status"] == "failed"]),
        }

def test_03_planning():
    planner = Planner()
    subtasks = [
        "收集数据",
        "清洗数据",
        "训练模型",
        "评估模型",
        "部署模型",
    ]
    plan_id = planner.create_plan("完成ML项目", subtasks)
    assert plan_id is not None
    # 执行前状态
    status = planner.get_status(plan_id)
    assert status["total"] == 5
    assert status["completed"] == 0
    # 执行
    def executor(desc):
        return f"完成: {desc}"
    all_done, plan = planner.execute_plan(plan_id, executor)
    assert all_done, "All tasks should complete"
    status = planner.get_status(plan_id)
    assert status["completed"] == 5
    assert status["pending"] == 0
    # 测试失败场景
    plan_id2 = planner.create_plan("失败测试", ["步骤1", "步骤2", "步骤3"])
    def failing_executor(desc):
        if "步骤2" in desc:
            raise Exception("模拟失败")
        return f"完成: {desc}"
    all_done2, plan2 = planner.execute_plan(plan_id2, failing_executor)
    assert not all_done2, "Should not complete all tasks"
    status2 = planner.get_status(plan_id2)
    assert status2["completed"] == 1
    assert status2["failed"] == 1
    print("✅ Test 03 passed: Task Planning & Decomposition")

# ============================================================
# Test 04: 记忆系统 (短期 + 长期记忆)
# ============================================================

class MemorySystem:
    """Agent 记忆系统"""
    def __init__(self, short_term_capacity=5, long_term_threshold=3):
        self.short_term = deque(maxlen=short_term_capacity)  # 短期记忆（滑动窗口）
        self.long_term = defaultdict(list)  # 长期记忆（按主题分类）
        self.access_count = defaultdict(int)  # 访问次数
        self.long_term_threshold = long_term_threshold  # 被访问超过此次数后转长期

    def add(self, content, topic="general"):
        """添加记忆"""
        item = {"content": content, "topic": topic, "timestamp": time.time()}
        self.short_term.append(item)

    def retrieve_short_term(self, query=""):
        """检索短期记忆"""
        results = list(self.short_term)
        if query:
            # 简单关键词匹配
            results = [r for r in results if query.lower() in r["content"].lower()]
        return results

    def retrieve_long_term(self, topic=None):
        """检索长期记忆"""
        if topic:
            return self.long_term.get(topic, [])
        return {t: items for t, items in self.long_term.items()}

    def consolidate(self):
        """将频繁访问的短期记忆转为长期记忆"""
        for item in list(self.short_term):
            key = item["content"][:50]  # 简化去重键
            self.access_count[key] += 1
            if self.access_count[key] >= self.long_term_threshold:
                # 检查是否已在长期记忆中
                existing = [m for m in self.long_term[item["topic"]] if m["content"] == item["content"]]
                if not existing:
                    self.long_term[item["topic"]].append(item.copy())

    def forget(self, topic=None):
        """遗忘：清除指定主题的长期记忆"""
        if topic:
            self.long_term.pop(topic, None)
        else:
            self.long_term.clear()

def test_04_memory():
    memory = MemorySystem(short_term_capacity=3, long_term_threshold=2)
    # 添加短期记忆
    memory.add("用户喜欢Python", topic="preference")
    memory.add("用户在学AI", topic="status")
    memory.add("用户用Mac", topic="preference")
    # 短期记忆容量限制
    memory.add("新记忆4", topic="general")
    assert len(memory.retrieve_short_term()) == 3, "Short-term should be capped at 3"
    # 最旧的应该被挤出
    short = memory.retrieve_short_term()
    contents = [s["content"] for s in short]
    assert "用户喜欢Python" not in contents, "Oldest should be evicted"
    # 检索
    results = memory.retrieve_short_term("Mac")
    assert len(results) == 1
    assert "Mac" in results[0]["content"]
    # 巩固记忆
    memory.add("用户喜欢Python", topic="preference")
    memory.add("用户喜欢Python", topic="preference")
    memory.consolidate()
    long_prefs = memory.retrieve_long_term("preference")
    assert len(long_prefs) > 0, "Should have consolidated to long-term"
    assert any("Python" in p["content"] for p in long_prefs)
    # 遗忘
    memory.forget("preference")
    assert len(memory.retrieve_long_term("preference")) == 0
    print("✅ Test 04 passed: Memory System (Short-term + Long-term)")

# ============================================================
# Test 05: 多 Agent 协作 (Multi-Agent Collaboration)
# ============================================================

class Agent:
    """单个 Agent"""
    def __init__(self, name, role, tools=None):
        self.name = name
        self.role = role
        self.tools = tools or {}
        self.messages = []

    def receive(self, message):
        """接收消息"""
        self.messages.append(message)

    def act(self, task):
        """执行任务"""
        # 根据角色模拟不同的行为
        if self.role == "researcher":
            result = f"[研究] 调研了'{task}'，发现3个关键点"
        elif self.role == "writer":
            result = f"[写作] 基于调研结果写了一篇关于'{task}'的文档"
        elif self.role == "reviewer":
            result = f"[审查] 审查文档，提出2条修改建议"
        elif self.role == "coder":
            result = f"[编码] 实现了'{task}'的代码"
        else:
            result = f"[{self.role}] 处理了'{task}'"
        self.messages.append({"role": "self", "content": result})
        return result

class MultiAgentSystem:
    """多 Agent 协作系统"""
    def __init__(self):
        self.agents = {}
        self.workflow = []

    def add_agent(self, agent):
        self.agents[agent.name] = agent

    def send(self, from_name, to_name, content):
        """Agent 间通信"""
        if from_name not in self.agents or to_name not in self.agents:
            raise ValueError("Agent not found")
        msg = {"from": from_name, "to": to_name, "content": content}
        self.agents[to_name].receive(msg)
        self.workflow.append(msg)
        return msg

    def run_pipeline(self, task, pipeline):
        """
        按管道执行多 Agent 协作
        pipeline: [(agent_name, task), ...]
        """
        results = []
        for agent_name, sub_task in pipeline:
            agent = self.agents[agent_name]
            result = agent.act(sub_task)
            results.append({"agent": agent_name, "result": result})
            # 将结果发送给下一个 agent
            idx = next(i for i, (n, _) in enumerate(pipeline) if n == agent_name)
            if idx < len(pipeline) - 1:
                next_agent = pipeline[idx + 1][0]
                self.send(agent_name, next_agent, result)
        return results

def test_05_multi_agent():
    system = MultiAgentSystem()
    # 创建 Agents
    system.add_agent(Agent("Alice", "researcher"))
    system.add_agent(Agent("Bob", "writer"))
    system.add_agent(Agent("Carol", "reviewer"))
    system.add_agent(Agent("Dave", "coder"))

    # 定义协作管道
    pipeline = [
        ("Alice", "AI Agent 架构"),
        ("Bob", "撰写 AI Agent 技术文档"),
        ("Carol", "审查技术文档"),
        ("Dave", "实现 AI Agent 原型"),
    ]
    results = system.run_pipeline("AI Agent", pipeline)
    assert len(results) == 4, f"Should have 4 results, got {len(results)}"
    # 验证每个 agent 都执行了
    assert results[0]["agent"] == "Alice"
    assert "研究" in results[0]["result"]
    assert "写作" in results[1]["result"]
    assert "审查" in results[2]["result"]
    assert "编码" in results[3]["result"]
    # 验证消息传递
    assert len(system.workflow) == 3, "Should have 3 messages between agents"
    # Bob 应该收到 Alice 的消息
    bob = system.agents["Bob"]
    received = [m for m in bob.messages if m.get("from") == "Alice"]
    assert len(received) >= 1, "Bob should have received Alice's message"
    # 直接通信测试
    system.send("Dave", "Alice", "代码遇到问题需要重新调研")
    alice = system.agents["Alice"]
    msgs_from_dave = [m for m in alice.messages if m.get("from") == "Dave"]
    assert len(msgs_from_dave) >= 1
    print(f"   Pipeline results: {[r['result'][:20] for r in results]}")
    print(f"   Total messages: {len(system.workflow)}")
    print("✅ Test 05 passed: Multi-Agent Collaboration")

# ============================================================
# Test 06: Agent 循环 + 观察反思 (Observation-Reflection)
# ============================================================

class ReflectiveAgent:
    """带反思能力的 Agent"""
    def __init__(self, name, max_steps=5):
        self.name = name
        self.max_steps = max_steps
        self.episodes = []  # 历史经验
        self.reflections = []

    def think(self, observation):
        """根据观察生成行动"""
        # 检查是否有相关历史经验
        relevant = [e for e in self.episodes if e["observation"] == observation]
        if relevant:
            # 利用历史经验
            best = max(relevant, key=lambda e: e["reward"])
            return best["action"]
        # 默认策略：尝试不同动作
        actions = ["explore", "exploit", "ask_help", "retry"]
        idx = len(self.episodes) % len(actions)
        return actions[idx]

    def reflect(self, observation, action, reward):
        """反思并记录经验"""
        episode = {"observation": observation, "action": action, "reward": reward}
        self.episodes.append(episode)
        # 如果奖励低，生成反思
        if reward < 0:
            reflection = f"观察到'{observation}'时执行'{action}'效果不好(奖励={reward})，下次尝试不同策略"
            self.reflections.append(reflection)

    def run_episode(self, env, task):
        """运行一个完整 episode"""
        total_reward = 0
        for step in range(self.max_steps):
            obs = env.observe()
            action = self.think(obs)
            obs_next, reward = env.step(action)
            total_reward += reward
            self.reflect(obs, action, reward)
        return total_reward

class SimpleEnv:
    """简单的网格世界环境"""
    def __init__(self, target_action="exploit"):
        self.target_action = target_action
        self.step_count = 0
    def observe(self):
        return f"state_{self.step_count}"
    def step(self, action):
        self.step_count += 1
        if action == self.target_action:
            return f"state_{self.step_count}", 1  # 正奖励
        return f"state_{self.step_count}", -1  # 负奖励

def test_06_reflection():
    agent = ReflectiveAgent("ReflectiveBot", max_steps=4)
    # 第一轮：没有经验，可能走错
    env1 = SimpleEnv(target_action="exploit")
    reward1 = agent.run_episode(env1, "learn")
    assert len(agent.episodes) == 4, "Should have 4 episodes after first run"
    # 第二轮：应该利用学到的经验
    env2 = SimpleEnv(target_action="exploit")
    reward2 = agent.run_episode(env2, "learn")
    # 第二轮应该表现更好（因为有经验了）
    assert reward2 >= reward1, f"Second run ({reward2}) should be >= first ({reward1})"
    # 应该有反思记录
    if reward1 < 0:
        assert len(agent.reflections) > 0, "Should have reflections from failed attempts"
    print(f"   Episode 1 reward: {reward1}, Episode 2 reward: {reward2}")
    print(f"   Total episodes: {len(agent.episodes)}, Reflections: {len(agent.reflections)}")
    print("✅ Test 06 passed: Observation-Reflection Loop")

# ============================================================
# Test 07: Prompt Engineering 模板系统
# ============================================================

class PromptTemplate:
    """提示工程模板系统"""
    def __init__(self):
        self.templates = {}

    def register(self, name, template, variables):
        """注册提示模板
        template: 含 {var} 占位符的字符串
        variables: 必需变量列表
        """
        self.templates[name] = {"template": template, "variables": variables}

    def render(self, name, **kwargs):
        """渲染模板"""
        if name not in self.templates:
            raise ValueError(f"Template '{name}' not found")
        tmpl = self.templates[name]
        # 检查必需变量
        for var in tmpl["variables"]:
            if var not in kwargs:
                raise ValueError(f"Missing variable '{var}' for template '{name}'")
        return tmpl["template"].format(**kwargs)

    def few_shot(self, system_prompt, examples, query):
        """Few-shot 提示构造"""
        example_text = "\n".join([f"输入: {e['input']}\n输出: {e['output']}" for e in examples])
        return f"{system_prompt}\n\n示例:\n{example_text}\n\n输入: {query}\n输出:"

    def chain_of_thought(self, question, steps):
        """CoT 链式思考提示"""
        steps_text = "\n".join([f"步骤{i+1}: {s}" for i, s in enumerate(steps)])
        return f"问题: {question}\n\n让我们一步步思考:\n{steps_text}\n\n最终答案:"

def test_07_prompt_engineering():
    pt = PromptTemplate()
    # 基础模板
    pt.register("translate", "将以下{src_lang}翻译为{dst_lang}: {text}", ["src_lang", "dst_lang", "text"])
    result = pt.render("translate", src_lang="中文", dst_lang="英文", text="你好世界")
    assert "中文" in result and "英文" in result and "你好世界" in result
    # 缺少变量
    try:
        pt.render("translate", src_lang="中文", dst_lang="英文")
        assert False, "Should raise ValueError"
    except ValueError:
        pass
    # Few-shot
    examples = [
        {"input": "苹果", "output": "apple"},
        {"input": "香蕉", "output": "banana"},
    ]
    few_shot = pt.few_shot("请翻译水果名称", examples, "橙子")
    assert "苹果" in few_shot and "apple" in few_shot
    assert "橙子" in few_shot
    # Chain of Thought
    cot = pt.chain_of_thought("计算 15 * 17", ["15 * 17 = 15 * 10 + 15 * 7 = 150 + 105 = 255"])
    assert "一步步思考" in cot
    assert "255" in cot
    print("✅ Test 07 passed: Prompt Engineering Templates")

# ============================================================
# Test 08: Agent 路由 (Router) 与动态工具选择
# ============================================================

class AgentRouter:
    """Agent 路由器：根据输入动态选择处理路径"""
    def __init__(self):
        self.routes = {}  # pattern -> handler
        self.default_handler = None
        self.route_log = []

    def add_route(self, pattern, handler):
        """添加路由规则"""
        self.routes[pattern] = handler

    def set_default(self, handler):
        self.default_handler = handler

    def route(self, query):
        """根据输入匹配路由"""
        for pattern, handler in self.routes.items():
            if re.search(pattern, query, re.IGNORECASE):
                self.route_log.append({"query": query, "route": pattern, "handler": handler.__name__})
                return handler(query)
        if self.default_handler:
            self.route_log.append({"query": query, "route": "default", "handler": self.default_handler.__name__})
            return self.default_handler(query)
        return "无法处理"

    def get_log(self):
        return self.route_log

def test_08_router():
    router = AgentRouter()
    def handle_code(query): return f"[代码助手] {query}"
    def handle_search(query): return f"[搜索助手] {query}"
    def handle_chat(query): return f"[聊天助手] {query}"
    def handle_default(query): return f"[通用助手] {query}"

    router.add_route(r"搜索|查找|search|google", handle_search)
    router.add_route(r"写代码|编程|code|python|函数", handle_code)
    router.add_route(r"你好|聊天|hi|hello|天气", handle_chat)
    router.set_default(handle_default)

    # 测试路由匹配
    assert "[代码助手]" in router.route("帮我写代码")
    assert "[搜索助手]" in router.route("搜索一下Python教程")
    assert "[聊天助手]" in router.route("你好啊")
    assert "[通用助手]" in router.route("今天是几号")  # 走默认

    # 验证路由日志
    log = router.get_log()
    assert len(log) == 4
    assert log[0]["route"] != "default"
    assert log[3]["route"] == "default"
    # 多次调用累积日志
    router.route("写一个Python函数")
    assert len(router.get_log()) == 5
    print("✅ Test 08 passed: Agent Router & Dynamic Tool Selection")

# ============================================================
# Test 09: Agent 状态机 (State Machine)
# ============================================================

class AgentStateMachine:
    """Agent 状态机：管理 Agent 的状态流转"""
    def __init__(self, initial_state="idle"):
        self.state = initial_state
        self.transitions = {}  # (state, event) -> new_state
        self.history = [(initial_state, "init")]

    def add_transition(self, from_state, event, to_state):
        """添加状态转换规则"""
        self.transitions[(from_state, event)] = to_state

    def trigger(self, event):
        """触发事件，尝试状态转换"""
        key = (self.state, event)
        if key in self.transitions:
            old_state = self.state
            self.state = self.transitions[key]
            self.history.append((self.state, event))
            return True
        return False

    def get_state(self):
        return self.state

    def get_history(self):
        return self.history

def test_09_state_machine():
    sm = AgentStateMachine("idle")
    # 定义状态转换
    sm.add_transition("idle", "start", "thinking")
    sm.add_transition("thinking", "decide", "acting")
    sm.add_transition("acting", "complete", "idle")
    sm.add_transition("acting", "error", "error")
    sm.add_transition("error", "retry", "thinking")
    sm.add_transition("error", "abort", "idle")

    assert sm.get_state() == "idle"
    # 正常流程: idle -> thinking -> acting -> idle
    assert sm.trigger("start") == True
    assert sm.get_state() == "thinking"
    assert sm.trigger("decide") == True
    assert sm.get_state() == "acting"
    assert sm.trigger("complete") == True
    assert sm.get_state() == "idle"
    # 错误流程: idle -> thinking -> acting -> error -> retry -> thinking -> acting -> idle
    sm.trigger("start")
    sm.trigger("decide")
    sm.trigger("error")
    assert sm.get_state() == "error"
    sm.trigger("retry")
    assert sm.get_state() == "thinking"
    sm.trigger("decide")
    sm.trigger("complete")
    assert sm.get_state() == "idle"
    # 非法转换
    assert sm.trigger("decide") == False  # idle 不能直接 decide
    assert sm.get_state() == "idle"
    # 历史记录
    history = sm.get_history()
    assert len(history) >= 8, f"Should have at least 8 entries, got {len(history)}"
    assert history[0] == ("idle", "init")
    print(f"   State history: {history}")
    print("✅ Test 09 passed: Agent State Machine")

# ============================================================
# Test 10: Agent 评估与自改进 (Self-Evaluation)
# ============================================================

class SelfEvaluatingAgent:
    """带自我评估和改进能力的 Agent"""
    def __init__(self, name):
        self.name = name
        self.performance_history = []
        self.strategy_adjustments = []
        self.current_strategy = "default"

    def execute(self, task, strategy=None):
        """执行任务"""
        strategy = strategy or self.current_strategy
        # 模拟不同策略的效果
        if strategy == "careful":
            quality = np.random.uniform(0.85, 0.98)
            speed = np.random.uniform(0.3, 0.5)
        elif strategy == "fast":
            quality = np.random.uniform(0.5, 0.7)
            speed = np.random.uniform(0.85, 0.98)
        else:  # default
            quality = np.random.uniform(0.6, 0.85)
            speed = np.random.uniform(0.6, 0.85)
        # 综合得分
        score = quality * 0.7 + speed * 0.3
        return {"task": task, "strategy": strategy, "quality": quality, "speed": speed, "score": score}

    def evaluate(self, result, target_score=0.8):
        """评估执行结果"""
        passed = result["score"] >= target_score
        self.performance_history.append({
            "task": result["task"],
            "strategy": result["strategy"],
            "score": result["score"],
            "quality": result["quality"],
            "speed": result["speed"],
            "passed": passed,
        })
        return passed

    def improve(self):
        """根据历史表现自改进策略"""
        if len(self.performance_history) < 3:
            return "数据不足，保持当前策略"
        recent = self.performance_history[-10:]
        avg_score = np.mean([r["score"] for r in recent])
        avg_quality = np.mean([r["quality"] for r in recent])
        avg_speed = np.mean([r["speed"] for r in recent])
        old_strategy = self.current_strategy
        # 策略调整逻辑
        if avg_quality < 0.7:
            self.current_strategy = "careful"
            adjustment = f"质量偏低({avg_quality:.2f})，切换到 careful 策略"
        elif avg_speed < 0.5:
            self.current_strategy = "fast"
            adjustment = f"速度偏低({avg_speed:.2f})，切换到 fast 策略"
        elif avg_score >= 0.85:
            self.current_strategy = "default"  # 表现好，回到均衡
            adjustment = f"表现优秀({avg_score:.2f})，保持 default 策略"
        else:
            adjustment = f"表现一般({avg_score:.2f})，保持当前策略"
        if old_strategy != self.current_strategy:
            self.strategy_adjustments.append({
                "from": old_strategy,
                "to": self.current_strategy,
                "reason": adjustment,
            })
        return adjustment

    def get_report(self):
        """生成自评估报告"""
        if not self.performance_history:
            return "暂无数据"
        total = len(self.performance_history)
        passed = sum(1 for r in self.performance_history if r["passed"])
        avg_score = np.mean([r["score"] for r in self.performance_history])
        return {
            "total_tasks": total,
            "passed": passed,
            "success_rate": passed / total,
            "avg_score": avg_score,
            "current_strategy": self.current_strategy,
            "strategy_changes": len(self.strategy_adjustments),
        }

def test_10_self_evaluation():
    np.random.seed(42)
    agent = SelfEvaluatingAgent("SelfImprover")
    # 执行一批任务
    for i in range(10):
        result = agent.execute(f"task_{i}")
        agent.evaluate(result, target_score=0.75)
    # 检查历史记录
    assert len(agent.performance_history) == 10
    report = agent.get_report()
    assert report["total_tasks"] == 10
    assert 0 <= report["success_rate"] <= 1
    assert report["avg_score"] > 0
    # 自改进
    improvement = agent.improve()
    assert isinstance(improvement, str)
    # 再执行一批任务，使用新策略
    for i in range(10, 15):
        result = agent.execute(f"task_{i}")
        agent.evaluate(result, target_score=0.75)
    report2 = agent.get_report()
    assert report2["total_tasks"] == 15
    # 策略调整记录
    if report["avg_score"] < 0.8:
        assert len(agent.strategy_adjustments) >= 0  # 可能调整了策略
    print(f"   Report: {json.dumps(report2, indent=2, ensure_ascii=False)}")
    print(f"   Strategy adjustments: {agent.strategy_adjustments}")
    print("✅ Test 10 passed: Self-Evaluation & Improvement")

# ============================================================
# 运行所有测试
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("第四阶段 4.2 AI Agent 开发基础练习")
    print("=" * 60)
    print()
    tests = [
        test_01_function_calling,
        test_02_react,
        test_03_planning,
        test_04_memory,
        test_05_multi_agent,
        test_06_reflection,
        test_07_prompt_engineering,
        test_08_router,
        test_09_state_machine,
        test_10_self_evaluation,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()
    print("=" * 60)
    print(f"结果: {passed}/{passed + failed} 通过")
    print("=" * 60)
