"""Suyi — A self-evolving AI agent framework.

Phase 1 核心模块:
    - Memory: 三层记忆系统 (working / episodic / semantic)
    - Core: ReAct 循环 + 上下文组装 + 预算管理
    - Tools: 工具基类 + 权限分级 + 内置工具

Phase 2 扩展模块:
    - Skills: 渐进式披露技能系统 (loader / menu / scanner)
    - Middleware: 可插拔中间件链 (压缩 / 记忆注入 / 循环检测 / 澄清)

Phase 3 多Agent系统:
    - Agents: AgentInstance + OrchestratorAgent + SubAgentManager
    - Patterns: Pipeline / Blackboard / Voting

Quick start:
    from suyi import MemoryManager, AgentLoop, MockLLM, get_builtin_tools
    from suyi import get_default_middleware, SkillLoader
    from suyi import OrchestratorAgent, SubAgentConfig, AgentInstance

    mgr = MemoryManager()
    mgr.add_memory("Python GIL limits threading", tags=["python"])

    tools = get_builtin_tools()
    middleware = get_default_middleware(mgr)
    llm = MockLLM()
    loop = AgentLoop(llm=llm, tools=tools, middleware_chain=middleware)

    # Multi-agent
    agent = AgentInstance(
        config=AgentConfig(name="worker", description="A worker"),
        llm=MockLLM([LLMResponse.text("Done!")]),
    )
    result = await agent.run("Do something")
"""

__version__ = "0.1.0"

# Memory
from .memory import MemoryManager, MemoryLifecycle
from .memory.working import WorkingMemory
from .memory.episodic import EpisodicMemory
from .memory.semantic import SemanticMemory

# Core
from .core import (
    AgentLoop,
    ContextAssembler,
    BudgetTracker,
    BudgetConfig,
    BudgetStatus,
    BudgetLevel,
    LLMInterface,
    LLMResponse,
    MockLLM,
    ToolCall,
    LoopState,
    LoopResult,
    IdentityConfig,
    ProjectRules,
    AssembledContext,
)

# Tools
from .tools import (
    AgentTool,
    ToolContext,
    ToolParameter,
    ToolResult,
    PermissionManager,
    SecurityClassifier,
    ClassifierInput,
    ClassifierResult,
    PERMISSION_AUTO,
    PERMISSION_CONFIRM,
    PERMISSION_BLOCK,
    BashTool,
    ReadFileTool,
    WriteFileTool,
    SearchTool,
    SkillTool,
    get_builtin_tools,
)

# Utils
from .utils import (
    TokenCounter,
    estimate_tokens,
    estimate_message_tokens,
    estimate_messages_tokens,
    strip_html,
    extract_summary,
    split_messages,
    encode_xml_tag,
)

__all__ = [
    "__version__",
    # Memory
    "MemoryManager",
    "MemoryLifecycle",
    "WorkingMemory",
    "EpisodicMemory",
    "SemanticMemory",
    # Core
    "AgentLoop",
    "ContextAssembler",
    "BudgetTracker",
    "BudgetConfig",
    "BudgetStatus",
    "BudgetLevel",
    "LLMInterface",
    "LLMResponse",
    "MockLLM",
    "ToolCall",
    "LoopState",
    "LoopResult",
    "IdentityConfig",
    "ProjectRules",
    "AssembledContext",
    # Tools
    "AgentTool",
    "ToolContext",
    "ToolParameter",
    "ToolResult",
    "PermissionManager",
    "SecurityClassifier",
    "ClassifierInput",
    "ClassifierResult",
    "PERMISSION_AUTO",
    "PERMISSION_CONFIRM",
    "PERMISSION_BLOCK",
    "BashTool",
    "ReadFileTool",
    "WriteFileTool",
    "SearchTool",
    "SkillTool",
    "get_builtin_tools",
    # Utils
    "TokenCounter",
    "estimate_tokens",
    "estimate_message_tokens",
    "estimate_messages_tokens",
    "strip_html",
    "extract_summary",
    "split_messages",
    "encode_xml_tag",
    # Phase 2: Skills
    "SkillLoader",
    "SkillMeta",
    "SkillContent",
    "SkillMenu",
    "SkillScanner",
    "ScanFinding",
    # Phase 2: Middleware
    "SummarizationMiddleware",
    "MemoryInjectMiddleware",
    "LoopDetectionMiddleware",
    "ClarificationMiddleware",
    "get_default_middleware",
    # Phase 3: Multi-Agent
    "AgentInstance",
    "AgentConfig",
    "AgentState",
    "SubAgentConfig",
    "SubAgentManager",
    "OrchestratorAgent",
    "SubTask",
    "SubTaskResult",
    "OrchestratorResult",
    "Pipeline",
    "PipelineStage",
    "PipelineResult",
    "Blackboard",
    "BlackboardEntry",
    "Voting",
    "Vote",
    "VoteResult",
    "VotingStrategy",
]

# Phase 2: Skills
from .skills import (
    SkillLoader,
    SkillMeta,
    SkillContent,
    SkillMenu,
    SkillScanner,
    ScanFinding,
)

# Phase 2: Middleware
from .middleware import (
    SummarizationMiddleware,
    MemoryInjectMiddleware,
    LoopDetectionMiddleware,
    ClarificationMiddleware,
    get_default_middleware,
)

# Phase 3: Multi-Agent
from .agents import (
    AgentInstance,
    AgentConfig,
    AgentState,
    SubAgentConfig,
    SubAgentManager,
    OrchestratorAgent,
    SubTask,
    SubTaskResult,
    OrchestratorResult,
    Pipeline,
    PipelineStage,
    PipelineResult,
    Blackboard,
    BlackboardEntry,
    Voting,
    Vote,
    VoteResult,
    VotingStrategy,
)

# Phase 4: Evolution Engine
from .evolution import (
    InteractionRecord,
    Pattern,
    BehaviorPolicy,
    LearningEngine,
    ToolSequence,
    GeneratedSkill,
    SkillGenerator,
    EvaluationMetrics,
    EvaluationReport,
    BehaviorEvaluator,
    Feedback,
    FeedbackSignal,
    FeedbackCollector,
    EvolutionOrchestrator,
)
