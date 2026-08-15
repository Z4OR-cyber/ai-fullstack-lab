"""
Suyi Core — Agent loop, context assembly, and budget management.

Core exports:
    AgentLoop:         The core ReAct agent loop
    ContextAssembler:  Four-layer context assembly with stable prefix caching
    BudgetTracker:     Three-dimensional budget management with progressive thresholds

Supporting types:
    Budget:     BudgetConfig, BudgetStatus, BudgetLevel
    Context:    AssembledContext, ToolDefinition, IdentityConfig, ProjectRules,
                MemoryBackend, InMemoryBackend
    Goal:       StructuredGoal, Priority
    Loop:       LLMInterface, LLMResponse, ToolCall, MockLLM,
                Tool, FunctionTool, Middleware,
                LoopState, LoopResult, ToolResult
"""

from .budget import (
    BudgetTracker,
    BudgetConfig,
    BudgetStatus,
    BudgetLevel,
)
from .context import (
    ContextAssembler,
    AssembledContext,
    ToolDefinition,
    IdentityConfig,
    ProjectRules,
    MemoryBackend,
    InMemoryBackend,
)
from .goal import StructuredGoal, Priority
from .loop import (
    AgentLoop,
    LLMInterface,
    LLMResponse,
    ToolCall,
    MockLLM,
    Tool,
    FunctionTool,
    Middleware,
    LoopState,
    LoopResult,
    ToolResult,
)
# v1.7.0: 请求可重建自检
from .request_checkpoint import (
    RequestCheckpoint,
    RequestReconstructionValidator,
    RequestNotReconstructableError,
)

__all__ = [
    # Core classes
    "AgentLoop",
    "ContextAssembler",
    "BudgetTracker",
    # Budget types
    "BudgetConfig",
    "BudgetStatus",
    "BudgetLevel",
    # Context types
    "AssembledContext",
    "ToolDefinition",
    "IdentityConfig",
    "ProjectRules",
    "MemoryBackend",
    "InMemoryBackend",
    # Goal types
    "StructuredGoal",
    "Priority",
    # Loop types
    "LLMInterface",
    "LLMResponse",
    "ToolCall",
    "MockLLM",
    "Tool",
    "FunctionTool",
    "Middleware",
    "LoopState",
    "LoopResult",
    "ToolResult",
    # v1.7.0: request checkpoint
    "RequestCheckpoint",
    "RequestReconstructionValidator",
    "RequestNotReconstructableError",
]
