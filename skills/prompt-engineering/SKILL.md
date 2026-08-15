# Prompt Engineering Mastery

> Comprehensive prompt engineering methodology for AI agents — layered architecture, structured frameworks, optimization strategies, and quality assurance.

## When to Use

Apply this skill when:
- Designing or refining system prompts for agents
- Writing task-specific prompts for LLM interactions
- Optimizing prompts for token efficiency
- Debugging poor LLM outputs (diagnosing prompt issues)
- Teaching prompt engineering patterns to other agents
- Building prompt templates for reusable workflows

---

## 1. Layered Prompt Architecture

### 1.1 Three-Layer System

```
┌─────────────────────────────────────────┐
│  L1: System Prompt (Static)             │
│  ─ Identity + rules + constraints       │
│  ─ Global scope, low-frequency changes  │
├─────────────────────────────────────────┤
│  L2: Task Prompt (Semi-dynamic)         │
│  ─ Planning + execution + tool use      │
│  ─ Per-task switching, mid-frequency    │
├─────────────────────────────────────────┤
│  L3: Output Prompt (Dynamic)            │
│  ─ Format + schema + tone               │
│  ─ Per-deliverable, high-frequency      │
└─────────────────────────────────────────┘
```

### 1.2 Static vs Dynamic Layers

**Static Layer** (System Prompt, globally fixed):
1. Identity definition — who you are
2. Capability boundaries — what you can/cannot do
3. Behavioral norms — how to act
4. Output format — what outputs look like

**Dynamic Layer** (Context Assembly, per-request):
5. Task instructions — what to do now
6. Retrieval augmentation — RAG context
7. Conversation history — compressed summary
8. User input — current request

**Key insight**: Component frequency in production prompts (from 86.7% to 19.9%):
- Directive (86.7%) > Context (56.2%) > Output Format (39.7%) > Constraints (35.7%) > Profile/Role (28.4%) > Workflow (27.5%) > Examples (19.9%)

---

## 2. Structured Prompt Frameworks

### 2.1 CREATE Framework

The most reliable structure for task prompts:

```
【Role】You are a senior XX engineer, specializing in XX.
【Context】I need XX, current situation is XX.
【Task】Please complete the following:
1. Specific step 1
2. Specific step 2
3. Specific step 3
【Format】Output in this structure: A → B → C → D
【Tone】Technical documentation style, concise and professional
【Example】Reference these samples: ...
```

**Core principle**: Context + Role + Exact Task + Action Format + Tone + Example

### 2.2 MPO (Modular Prompt Optimization)

Break prompts into independent semantic segments, optimize each separately:

```
[System Role]      → Identity, capability boundaries
[Relevant Context] → Background info, historical decisions
[Task Details]     → Precise task description
[Constraints]      → Limitations, requirements
[Output Format]    → Output specification
```

**Process**: Evaluate each segment independently → generate textual gradient → iterate per segment → reassemble. Keep structure constant, only optimize content.

### 2.3 Six Essential Prompt Types for Agent Projects

An L3/L4 Agent needs at least:

| Type | Purpose | Frequency |
|------|---------|-----------|
| System prompt | Identity + rules + constraints | Every session |
| Task understanding | Parse user intent, decompose tasks | Every task |
| Planning | Generate execution plan, select tools | Every task |
| Step execution | Execute single step, call tools | Each step |
| Final answer | Integrate results, generate output | Every delivery |
| Fallback | Degradation strategy when tools fail | On exceptions |

L4 Agents additionally need: graph planning, plan repair, and review prompts.

---

## 3. Token Optimization Strategies

### 3.1 Prompt Compression Techniques

**Gene Distillation Method**:
1. Start with full prompt (baseline)
2. Identify redundant phrases, examples, explanations
3. Compress while preserving semantic meaning
4. Test compressed version against baseline
5. Iterate until quality degrades

**Example compression**:
```
# Before (120 tokens)
"You are a helpful assistant. You should always be polite and professional. 
When answering questions, you should provide accurate information based on 
your training data. If you don't know something, say so honestly."

# After (45 tokens)
"Helpful assistant. Polite, professional. Provide accurate info. 
Admit uncertainty when unsure."
```

### 3.2 Context Window Management

**Priority ordering** (include in this order if context is limited):
1. System prompt (identity + critical rules)
2. Current task instructions
3. Most relevant examples (2-3 max)
4. Recent conversation history (last 3-5 turns)
5. Background context (compressed)

**Compression techniques**:
- Summarize long conversations into key decisions
- Replace verbose examples with concise templates
- Use abbreviations for repeated terms (define once)
- Remove pleasantries and meta-commentary

### 3.3 Output Token Control

**Explicit length guidance**:
- "Respond in 2-3 sentences" (soft limit)
- "Maximum 500 words" (hard limit)
- "Use bullet points, max 5 items" (structural limit)

**Structured output** (reduces verbosity):
```json
{
  "answer": "concise answer here",
  "confidence": 0.95,
  "sources": ["source1", "source2"]
}
```

---

## 4. Quality Assurance Checklist

Before deploying a prompt, verify:

### 4.1 Clarity
- [ ] Role/identity is unambiguous
- [ ] Task is specific and measurable
- [ ] Constraints are explicit
- [ ] Output format is defined

### 4.2 Completeness
- [ ] All necessary context is included
- [ ] Edge cases are addressed
- [ ] Error handling is specified
- [ ] Examples cover typical use cases

### 4.3 Efficiency
- [ ] No redundant instructions
- [ ] Examples are minimal but sufficient
- [ ] Token count is reasonable for the task
- [ ] Context window is not overloaded

### 4.4 Robustness
- [ ] Handles ambiguous inputs gracefully
- [ ] Fallback behavior is defined
- [ ] Does not rely on implicit assumptions
- [ ] Tested with varied inputs

---

## 5. Common Anti-Patterns

### 5.1 Vague Instructions
❌ "Write something good"
✅ "Write a 500-word blog post about X for audience Y, using professional tone"

### 5.2 Contradictory Constraints
❌ "Be concise but thorough" (conflicting)
✅ "Prioritize conciseness; include details only when critical"

### 5.3 Over-Specification
❌ 2000-word prompt for a simple classification task
✅ Match prompt complexity to task complexity

### 5.4 Missing Examples
❌ Expecting specific output format without showing one
✅ Include 2-3 examples covering typical cases

### 5.5 Ignoring Context Limits
❌ Stuffing entire codebase into context
✅ Include only relevant files/functions

### 5.6 No Error Handling
❌ Assuming perfect inputs
✅ Specify behavior for invalid/ambiguous inputs

---

## 6. Advanced Techniques

### 6.1 Chain-of-Thought (CoT) Prompting

For complex reasoning tasks:

```
Solve this step by step:
1. First, identify the key components
2. Then, analyze their relationships
3. Next, apply the relevant principles
4. Finally, synthesize the conclusion

Show your reasoning at each step.
```

### 6.2 Few-Shot Learning

Provide 2-3 examples before the actual task:

```
Example 1:
Input: "The food was amazing!"
Output: {"sentiment": "positive", "confidence": 0.95}

Example 2:
Input: "Terrible service, never coming back."
Output: {"sentiment": "negative", "confidence": 0.92}

Now classify:
Input: "It was okay, nothing special."
Output:
```

### 6.3 Role-Playing for Domain Expertise

```
You are a senior backend engineer with 15 years of experience in:
- Distributed systems design
- Database optimization
- API architecture

Review this code and identify:
1. Performance bottlenecks
2. Security vulnerabilities
3. Scalability concerns

Provide specific, actionable recommendations.
```

### 6.4 Iterative Refinement

For complex outputs, use multi-turn refinement:

```
Turn 1: "Generate initial draft"
Turn 2: "Review for clarity and completeness"
Turn 3: "Optimize for conciseness"
Turn 4: "Final polish and formatting"
```

---

## 7. Prompt Templates by Use Case

### 7.1 Code Review Template

```
【Role】Senior software engineer, expert in [language/framework]
【Task】Review this code for:
- Bugs and logic errors
- Performance issues
- Security vulnerabilities
- Code style and best practices

【Code】
```[language]
[code here]
```

【Output Format】
1. Critical issues (must fix)
2. Important suggestions (should fix)
3. Minor improvements (nice to have)
4. Overall assessment (1-10 score)

【Constraints】
- Be specific with line numbers
- Provide fix suggestions
- Explain the "why" behind each issue
```

### 7.2 Content Generation Template

```
【Role】Professional content writer specializing in [domain]
【Context】Target audience: [demographics], Platform: [medium]
【Task】Write [content type] about [topic]

【Requirements】
- Tone: [professional/casual/technical/etc.]
- Length: [word count]
- Include: [key points to cover]
- Avoid: [topics/phrases to exclude]

【Format】
- Headline: compelling, SEO-friendly
- Structure: intro → body → conclusion
- Include: subheadings, bullet points where appropriate

【Examples】
Reference style of: [example content]
```

### 7.3 Data Analysis Template

```
【Role】Data analyst with expertise in [domain]
【Data Description】
- Source: [where data comes from]
- Size: [rows/columns]
- Key fields: [list important columns]

【Task】
1. Summarize key statistics
2. Identify trends and patterns
3. Highlight anomalies or outliers
4. Provide actionable insights

【Output Format】
- Executive summary (2-3 sentences)
- Key findings (bullet points)
- Visualizations (describe what charts would show)
- Recommendations (numbered list)

【Constraints】
- Base conclusions only on provided data
- Quantify confidence levels
- Note limitations of analysis
```

---

## 8. Iterative Optimization Workflow

### 8.1 Baseline → Measure → Improve Cycle

1. **Baseline**: Write initial prompt
2. **Test**: Run with 5-10 representative inputs
3. **Evaluate**: Score outputs (accuracy, relevance, format compliance)
4. **Diagnose**: Identify failure patterns
5. **Refine**: Adjust prompt to address failures
6. **Retest**: Verify improvements didn't break other cases
7. **Document**: Record what worked and why

### 8.2 A/B Testing Prompts

When unsure between two approaches:

```
Prompt A: [first version]
Prompt B: [second version]

Test both with same 10 inputs.
Compare:
- Output quality (1-5 scale)
- Token usage
- Response time
- Failure rate

Choose winner based on weighted criteria.
```

### 8.3 Version Control for Prompts

Track prompt evolution:

```markdown
## Prompt v2.1 (2026-08-15)
- Added explicit output format
- Reduced token count by 15%
- Improved edge case handling

## Prompt v2.0 (2026-08-10)
- Restructured using CREATE framework
- Added 3 examples
- Fixed ambiguity in role definition

## Prompt v1.0 (2026-08-01)
- Initial version
```

---

## 9. Domain-Specific Patterns

### 9.1 Code Generation

- Specify language and version
- Include import statements
- Show expected input/output
- Request error handling
- Ask for type annotations

### 9.2 Creative Writing

- Define voice and style
- Provide mood/tone references
- Specify length constraints
- Include target audience
- Request multiple variants

### 9.3 Data Extraction

- Show sample input
- Define output schema (JSON preferred)
- Specify handling of missing data
- Request confidence scores
- Include edge case examples

### 9.4 Summarization

- Specify target length
- Define key points to preserve
- Request structured format (bullets/headings)
- Ask for source attribution
- Specify audience (expert vs. general)

---

## 10. Meta-Prompting: Prompts About Prompts

Use these to improve existing prompts:

### 10.1 Prompt Critique

```
Analyze this prompt for weaknesses:
"""
[prompt here]
"""

Identify:
1. Ambiguities or unclear instructions
2. Missing context or examples
3. Inefficient token usage
4. Potential failure modes
5. Suggested improvements

Rate overall quality (1-10) with justification.
```

### 10.2 Prompt Compression

```
Compress this prompt while preserving semantic meaning:
"""
[prompt here]
"""

Rules:
- Reduce token count by 30-50%
- Keep all critical instructions
- Maintain output format specification
- Preserve examples (can shorten)
- Test: compressed version should produce equivalent outputs
```

### 10.3 Prompt Expansion

```
This prompt is too terse and produces inconsistent outputs:
"""
[prompt here]
"""

Expand it to include:
- Clear role definition
- Explicit constraints
- 2-3 examples
- Output format specification
- Error handling instructions

Target: 2-3x current length, maximum clarity.
```

---

## References & Further Reading

- CREATE Framework: Based on 2026 Prompt Engineering Best Practices
- MPO: Modular Prompt Optimization (arxiv 2601.04055)
- Production Prompt Templates: Analysis of 1000+ production prompts
- Gene Distillation: Token compression methodology
- Six-Dimensional Analysis Model: Content evaluation framework

---

## Quick Decision Tree

**What are you trying to do?**

1. **Write a new prompt from scratch**
   → Start with CREATE framework (§2.1)
   → Add examples (§6.2)
   → Run quality checklist (§4)

2. **Improve an existing prompt**
   → Run prompt critique (§10.1)
   → Identify anti-patterns (§5)
   → Apply iterative workflow (§8.1)

3. **Reduce token usage**
   → Apply compression techniques (§3.1)
   → Use prompt compression meta-prompt (§10.2)
   → Test quality after compression

4. **Debug poor outputs**
   → Check for anti-patterns (§5)
   → Verify completeness (§4.2)
   → Add examples for failure cases
   → Test with varied inputs

5. **Teach prompt engineering**
   → Start with layered architecture (§1)
   → Show CREATE framework (§2.1)
   → Demonstrate with templates (§7)
   → Practice with meta-prompts (§10)
