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

__version__ = "1.9.0"
# v1.4.0: 安全加固 — CodeSandboxTool P0 加固（open 写模式拦截、反射函数拦截、
#   dunder 属性访问拦截、危险模块扩展、子进程环境变量最小化）、参数安全验证器.
# v1.5.0: ComputerUseTool — OS 级桌面控制层（截图/鼠标/键盘/窗口/应用启动），
#   可选依赖优雅降级、dry_run 模式、安全护栏（危险组合键/危险程序拦截、
#   坐标越界保护）、审计日志、HITL 签名按动作类型授权.
# v1.6.0: 旁路知识层（Bypass Knowledge Layer）— 代码与数据分离、稳定与进化
#   分离。LearnedKnowledgeStore + TF-IDF 检索（兼容 MemoryBackend 协议，
#   可直接插入 ContextAssembler）+ 语义去重（skip/merge/append）+ 正样本
#   蒸馏器 + 弱信号积累器（达阈值触发外循环蒸馏）+ 三级知识注入（原则/案例/
#   专项）。FeedbackCollector 与 EvolutionOrchestrator 增量对接，向后兼容.
# v1.7.0: Harness 借鉴 — ②请求可重建自检（RequestCheckpoint +
#   RequestReconstructionValidator，发送前序列化→反序列化→checksum 比对，
#   fail-open 不阻断生产）；③执行调度（read_only=True 只读工具并行、
#   read_only=False 写工具在 asyncio.Lock 内串行、结果按 tool_calls 原始
#   顺序有序提交）。纯增量、向后兼容，默认关闭新行为.
# v1.8.0: 多平台漏洞赏金报告统一提交适配器（BountySubmissionAdapter）—
#   suyi.integrations.bounty 子包，支持 HackerOne / Bugcrowd / Intigriti /
#   YesWeHack 四大平台。统一 BountyReport 数据模型 + 平台适配器模式 +
#   BountyRouter 多平台路由 + DraftStore 草稿持久化审查。安全设计：
#   confirmed=False 默认只返回草稿、dry_run 只构建 payload 不发请求、
#   Token 仅通过参数或环境变量传入。纯增量、向后兼容，零新外部依赖.
# v1.9.0: AML 兼容层（Agent Memory Leaderboard）— 新增 suyi.memory 子模块：
#   BM25OkapiRetriever + DenseRetriever + AMLHybridRetriever（RRF 融合 +
#   时间衰减）+ AMLMemoryStore（多用户/多会话三层记忆、去重、TTL、容量、
#   JSON 持久化）+ AMLMemoryServer（标准库 http.server 实现 POST /add
#   与 POST /search，支持 X-API-Key 鉴权、asyncio 集成、优雅关闭）。
#   纯 Python + numpy，不引入新外部依赖，不调用外部 LLM。

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
    # v1.9.0: AML 兼容层
    AMLBM25Retriever,
    AMLDenseRetriever,
    AMLHybridRetriever,
    RetrievalResult as AMLRetrievalResult,
    AMLMemoryStore,
    MemoryRecord as AMLMemoryRecord,
    AMLMemoryServer,
    AMLRequestHandler,
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
    WebRequestTool,
    CodeSandboxTool,
    ComputerUseTool,
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
    # v1.9.0: AML 兼容层
    "AMLBM25Retriever",
    "AMLDenseRetriever",
    "AMLHybridRetriever",
    "AMLRetrievalResult",
    "AMLMemoryStore",
    "AMLMemoryRecord",
    "AMLMemoryServer",
    "AMLRequestHandler",
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
    "WebRequestTool",
    "CodeSandboxTool",
    "ComputerUseTool",
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
    # Phase 10: RAG Pipeline
    "RAGPipeline",
    "RAGRetriever",
    "RAGResult",
    "Chunk",
    "BaseChunker",
    "FixedSizeChunker",
    "SentenceChunker",
    "SemanticChunker",
    "get_chunker",
    # Phase 10: Caching Layer
    "CacheManager",
    "CacheStats",
    "CacheEntry",
    "ExactCache",
    "SemanticCache",
    # Phase 10: Workflow Engine
    "DAG",
    "Node",
    "NodeStatus",
    "Edge",
    "DAGValidationError",
    "WorkflowEngine",
    "WorkflowResult",
    "FailurePolicy",
    # Phase 10: Event System
    "EventBus",
    "Subscription",
    "Event",
    "EventType",
    "get_event_bus",
    "reset_event_bus",
    "before_llm_call",
    "after_llm_call",
    "before_tool_call",
    "after_tool_call",
    "memory_updated",
    "skill_loaded",
    "agent_spawned",
    "error_event",
    # Phase 11: Plugin System
    "PluginManager",
    "PluginBase",
    "PluginContext",
    "PluginState",
    "PluginRegistry",
    "PluginEntry",
    "load_from_file",
    "load_from_package",
    "load_plugin",
    "PluginLoadError",
    # Phase 11: Deployment Templates
    "DeploymentConfig",
    "Environment",
    "EnvVar",
    "HealthCheck",
    "ResourceLimits",
    "DockerConfigGenerator",
    "K8sConfigGenerator",
    "generate_dockerfile",
    "generate_compose",
    "generate_k8s_deployment",
    "generate_k8s_service",
    "generate_k8s_ingress",
    "generate_all_k8s",
    # Phase 11: Vector Store
    "VectorStoreBase",
    "InMemoryVectorStore",
    "VectorRecord",
    "SearchResult",
    "VectorStoreRetrieverAdapter",
    "RAGVectorStoreAdapter",
    # Phase 11: Multimodal Support
    "MultimodalInput",
    "MediaContent",
    "ModalityType",
    "InputProcessor",
    "ProcessResult",
    "FormatConverter",
    # Phase 12: Rate Limiter
    "RateLimitConfig",
    "RateLimitAlgorithm",
    "RLTokenBucket",
    "RLSlidingWindow",
    "DimensionLimiter",
    "MultiRateLimiter",
    "RateLimitMiddleware",
    # Phase 12: State Machine
    "State",
    "Transition",
    "StateHistoryEntry",
    "TransitionResult",
    "StateMachineError",
    "StateNotFoundError",
    "InvalidTransitionError",
    "StateNotStartedError",
    "StateMachine",
    # Phase 12: Cost Tracker
    "CostConfig",
    "CostRecord",
    "CostAlert",
    "CostReport",
    "AlertLevel",
    "DEFAULT_MODEL_PRICING",
    "CostTrackerV2",
    # Phase 12: Feedback Loop
    "FeedbackType",
    "ImplicitSignalType",
    "FeedbackEntry",
    "FeedbackSignalV2",
    "FeedbackLoop",
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

# Phase 10: RAG Pipeline
from .rag import (
    RAGPipeline,
    RAGRetriever,
    RAGResult,
    Chunk,
    BaseChunker,
    FixedSizeChunker,
    SentenceChunker,
    SemanticChunker,
    get_chunker,
)

# Phase 10: Caching Layer
from .cache import (
    CacheManager,
    CacheStats,
    CacheEntry,
    ExactCache,
    SemanticCache,
)

# Phase 10: Workflow Engine
from .workflow import (
    DAG,
    Node,
    NodeStatus,
    Edge,
    DAGValidationError,
    WorkflowEngine,
    WorkflowResult,
    FailurePolicy,
)

# Phase 10: Event System
from .events import (
    EventBus,
    Subscription,
    Event,
    EventType,
    get_event_bus,
    reset_event_bus,
    before_llm_call,
    after_llm_call,
    before_tool_call,
    after_tool_call,
    memory_updated,
    skill_loaded,
    agent_spawned,
    error_event,
)

# Phase 11: Plugin System
from .plugins import (
    PluginManager,
    PluginBase,
    PluginContext,
    PluginState,
    PluginRegistry,
    PluginEntry,
    load_from_file,
    load_from_package,
    load_plugin,
    PluginLoadError,
)

# Phase 11: Deployment Templates
from .deploy import (
    DeploymentConfig,
    Environment,
    EnvVar,
    HealthCheck,
    ResourceLimits,
    DockerConfigGenerator,
    K8sConfigGenerator,
    generate_dockerfile,
    generate_compose,
    generate_k8s_deployment,
    generate_k8s_service,
    generate_k8s_ingress,
    generate_all_k8s,
)

# Phase 11: Vector Store
from .vectorstore import (
    VectorStoreBase,
    InMemoryVectorStore,
    VectorRecord,
    SearchResult,
    VectorStoreRetrieverAdapter,
    RAGVectorStoreAdapter,
)

# Phase 11: Multimodal Support
from .multimodal import (
    MultimodalInput,
    MediaContent,
    ModalityType,
    InputProcessor,
    ProcessResult,
    FormatConverter,
)

# Phase 12: Rate Limiter
from .ratelimit import (
    RateLimitConfig,
    RateLimitAlgorithm,
    TokenBucket as RLTokenBucket,
    SlidingWindow as RLSlidingWindow,
    DimensionLimiter,
    MultiRateLimiter,
    RateLimitMiddleware,
)

# Phase 12: State Machine
from .statemachine import (
    State,
    Transition,
    StateHistoryEntry,
    TransitionResult,
    StateMachineError,
    StateNotFoundError,
    InvalidTransitionError,
    StateNotStartedError,
    StateMachine,
)

# Phase 12: Cost Tracker
from .cost import (
    CostConfig,
    CostRecord,
    CostAlert,
    CostReport,
    AlertLevel,
    DEFAULT_MODEL_PRICING,
    CostTrackerV2,
)

# Phase 12: Feedback Loop
from .feedback import (
    FeedbackType,
    ImplicitSignalType,
    FeedbackEntry,
    FeedbackSignalV2,
    FeedbackLoop,
)
