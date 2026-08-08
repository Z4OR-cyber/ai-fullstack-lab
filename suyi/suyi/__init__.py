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

__version__ = "0.5.0"

# Memory
from .memory import (
    MemoryManager,
    MemoryLifecycle,
    MemoryPriority,
    WorkingMemory,
    EpisodicMemory,
    SemanticMemory,
    StructuredFact,
    StructuredFactsStore,
    FactSource,
    GroundTruthEntry,
    GroundTruthStore,
    WikiPage,
    AutoWiki,
    MemoryItem,
    BaseRetriever,
    HybridRetriever,
    DenseRetriever,
    LexicalRetriever,
    SQLiteRetriever,
    RetrievalChain,
    SemanticDeduplicator,
    MessageClassifier,
)

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
    "MemoryPriority",
    "WorkingMemory",
    "EpisodicMemory",
    "SemanticMemory",
    # Phase 9: Memory layers
    "StructuredFact",
    "StructuredFactsStore",
    "FactSource",
    "GroundTruthEntry",
    "GroundTruthStore",
    "WikiPage",
    "AutoWiki",
    "MemoryItem",
    "BaseRetriever",
    "HybridRetriever",
    "DenseRetriever",
    "LexicalRetriever",
    "SQLiteRetriever",
    "RetrievalChain",
    "SemanticDeduplicator",
    "MessageClassifier",
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
    "PreLLMInjectMiddleware",
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
    # Phase 9: Agent Relay Pipeline
    "DataSchema",
    "PipelineStep",
    "PipelineExecutionResult",
    "AgentPipeline",
    # Phase 9: Swarm
    "TaskStatus",
    "SharedTask",
    "SwarmGoal",
    "SwarmAgentInfo",
    "SharedTaskBoard",
    "SwarmCoordinator",
    # Phase 5: LLM Adapters
    "OpenAIAdapter",
    "AnthropicAdapter",
    "create_llm",
    "create_llm_from_config",
    "register_provider",
    "list_providers",
    # Phase 5: Configuration
    "SuyiConfig",
    "LLMConfig",
    "MemoryConfig",
    "ToolConfig",
    "MiddlewareConfig",
    "ConfigAgentConfig",
    "ConfigEvolutionConfig",
    "load_config",
    "load_config_from_dict",
    "get_default_config",
    "save_config",
    # Phase 6: Web API, Persistence, Streaming
    "SessionManager",
    "SessionData",
    "StreamHandler",
    "StreamChunk",
    "StreamCallbacks",
    "SuyiServer",
    # Phase 7: MCP Protocol
    "PROTOCOL_VERSION",
    "MCPError",
    "MCPMessage",
    "MCPPrompt",
    "MCPResource",
    "MCPTool",
    "Transport",
    "StdioTransport",
    "TCPTransport",
    "MemoryTransport",
    "MCPServer",
    "serve_on_transport",
    "MCPClient",
    "RemoteMCPTool",
    # Phase 7: AI Gateway
    "GatewayRouter",
    "ProviderEntry",
    "RoutingRule",
    "RateLimiter",
    "TokenBucket",
    "SlidingWindow",
    "CostTracker",
    "CostEntry",
    "BudgetAlert",
    "DEFAULT_PRICING",
    "FallbackChain",
    "FallbackConfig",
    "FallbackResult",
    # Phase 7: Observability
    "StructuredLogger",
    "MetricsCollector",
    "Tracer",
    "Span",
    "ObservabilityMiddleware",
    # Phase 7: Guardrails
    "ContentFilter",
    "OutputValidator",
    "GuardrailsMiddleware",
    # Phase 7: Human-in-the-Loop
    "HITLManager",
    "HITLPolicy",
    "HITLMiddleware",
    # Phase 8: Evaluation Framework
    "MetricBase",
    "MetricResult",
    "MetricSuite",
    "SuiteReport",
    "TraceRecord",
    "TaskCompletionMetric",
    "ToolUsageMetric",
    "LatencyMetric",
    "TokenEfficiencyMetric",
    "ReasoningQualityMetric",
    "HallucinationMetric",
    "get_default_metrics",
    "BenchmarkCase",
    "CaseResult",
    "BenchmarkSuite",
    "BenchmarkRunner",
    "BenchmarkReport",
    "ABTest",
    "ABTestResult",
    "StatisticalSignificance",
    # Phase 8: Prompt Management
    "PromptTemplate",
    "SystemPrompt",
    "ReActPrompt",
    "ToolPrompt",
    "MultiAgentPrompt",
    "PromptManager",
    "TemplateVersion",
    "PromptLibrary",
    "get_library",
    "get_template",
    "render_template",
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
    PreLLMInjectMiddleware,
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
    # Phase 9: Agent Relay Pipeline
    DataSchema,
    PipelineStep,
    PipelineExecutionResult,
    AgentPipeline,
    # Phase 9: Swarm
    TaskStatus,
    SharedTask,
    SwarmGoal,
    SwarmAgentInfo,
    SharedTaskBoard,
    SwarmCoordinator,
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

# Phase 5: LLM Adapters & Configuration
from .llm import (
    OpenAIAdapter,
    AnthropicAdapter,
    create_llm,
    create_llm_from_config,
    register_provider,
    list_providers,
)
from .config import (
    SuyiConfig,
    LLMConfig,
    MemoryConfig,
    ToolConfig,
    MiddlewareConfig,
    # AgentConfig from config module — aliased to avoid conflict
    # with agents.AgentConfig which is the sub-agent configuration
    AgentConfig as ConfigAgentConfig,
    EvolutionConfig as ConfigEvolutionConfig,
    load_config,
    load_config_from_dict,
    get_default_config,
    save_config,
)

# Phase 6: Web API, Persistence, Streaming
from .persistence import (
    SessionManager,
    SessionData,
)
from .streaming import (
    StreamHandler,
    StreamChunk,
    StreamCallbacks,
)
from .web import SuyiServer

# Phase 7: MCP Protocol
from .mcp import (
    PROTOCOL_VERSION,
    MCPError,
    MCPMessage,
    MCPPrompt,
    MCPResource,
    MCPTool,
    Transport,
    StdioTransport,
    TCPTransport,
    MemoryTransport,
    MCPServer,
    serve_on_transport,
    MCPClient,
    RemoteMCPTool,
)

# Phase 7: AI Gateway
from .gateway import (
    GatewayRouter,
    ProviderEntry,
    RoutingRule,
    RateLimiter,
    TokenBucket,
    SlidingWindow,
    CostTracker,
    CostEntry,
    BudgetAlert,
    DEFAULT_PRICING,
    FallbackChain,
    FallbackConfig,
    FallbackResult,
)

# Phase 7: Observability
from .observability import (
    StructuredLogger,
    MetricsCollector,
    Tracer,
    Span,
    ObservabilityMiddleware,
)

# Phase 7: Guardrails
from .guardrails import (
    ContentFilter,
    OutputValidator,
    GuardrailsMiddleware,
)

# Phase 7: Human-in-the-Loop
from .hitl import (
    HITLManager,
    HITLPolicy,
    HITLMiddleware,
)
# Phase 8: Evaluation Framework & Prompt Management
from .evaluation import (
    MetricBase,
    MetricResult,
    MetricSuite,
    SuiteReport,
    TraceRecord,
    TaskCompletionMetric,
    ToolUsageMetric,
    LatencyMetric,
    TokenEfficiencyMetric,
    ReasoningQualityMetric,
    HallucinationMetric,
    get_default_metrics,
    BenchmarkCase,
    CaseResult,
    BenchmarkSuite,
    BenchmarkRunner,
    BenchmarkReport,
    ABTest,
    ABTestResult,
    StatisticalSignificance,
)
from .prompts import (
    PromptTemplate,
    SystemPrompt,
    ReActPrompt,
    ToolPrompt,
    MultiAgentPrompt,
    PromptManager,
    TemplateVersion,
    PromptLibrary,
    get_library,
    get_template,
    render_template,
)
