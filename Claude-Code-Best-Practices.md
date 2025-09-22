# Claude Code - Büyük Proje Yönetimi Best Practices

## 🎯 Core Principles

### 1. Context Management Strategy
- **CLAUDE.md**: Interface definitions, system architecture (sabit spec'ler)
- **Agent files**: Work history, incremental changes (değişen implementation'lar)
- **Context Budget**: 30% architecture + 20% current work + 20% agents + 20% quality + 10% buffer

### 2. Compact Strategy - Golden Rules
```bash
# ✅ Doğru zamanlar
- Özellik tamamlandıktan sonra
- Bug fix bittikten sonra
- Commit yapıldıktan sonra
- Context %85 dolduğunda

# ❌ Yanlış zamanlar
- Context %95+ dolduğunda (çok geç!)
- Task ortasında
- Debug session sırasında

# 🎯 Hedefli compact
/compact preserve: system architecture, active tasks, key decisions
```

### 3. /clear vs /compact Decision Matrix
```
/compact kullan:
- Mevcut session'ı korumak istiyorsan
- Özel bilgileri hedefli korumak istiyorsan
- Proje bağlamını kaybetmek istemiyorsan

/clear kullan:
- Yeni özelliğe başlarken
- Context çok dağılmışsa
- Token maliyetini minimize etmek istiyorsan
```

## 🤖 Agent Management

### Subagent Context Reality Check
```
✅ Agents inherit:
├── MCP tools (all available)
├── System tools (Read, Write, etc.)
├── Environment access
└── File system permissions

❌ Agents DON'T inherit:
├── CLAUDE.md memory files
├── Conversation history
├── Previous context
└── Main agent's "memory"
```

### Agent State Management
```markdown
File Structure:
project/
├── CLAUDE.md (Interface definitions only)
├── agents/
│   ├── UIDesigner.md (Session history)
│   ├── SwarmOptimizer.md (Agent tuning history)
│   └── DatabaseExpert.md (DB optimization sessions)
```

### Perfect Agent Calling Pattern
```javascript
Task("UI improvements", {
  "interface_spec": "Check CLAUDE.md for UI data exchange interfaces",
  "work_history": "Read agents/UIDesigner.md for previous sessions",
  "work_mode": "incremental",
  "preserve_interfaces": "Maintain API contracts from CLAUDE.md",
  "focus": "performance optimization"
})
```

### Agent File Template (UIDesigner.md example)
```markdown
# UI Designer Agent Session History

## Current State (Latest)
- **Design System**: Modern card-based layout
- **Color Palette**: #2563eb primary, #f8fafc background
- **Typography**: Inter font family
- **Layout**: CSS Grid responsive
- **Status**: Production ready ✅

## Session Log
### 2025-01-14 - Initial Design
- Implemented modern card layout
- Added responsive breakpoints
- **Preserve**: Core grid structure

### 2025-01-15 - Accessibility Pass
- Added ARIA labels
- Improved contrast ratios
- **Preserve**: Layout + colors + responsive

## Next Session Guidelines
- **Never Change**: Grid layout, color scheme, responsive breakpoints
- **Focus Areas**: Performance, micro-interactions, loading states
- **Build Upon**: Current accessibility features
```

## 🚀 Power Commands for Large Projects

### 1. Project Planning & Architecture
```bash
/design system-architecture --scope project --focus scalability
/estimate complexity --breakdown modules --time realistic
/analyze dependencies --depth 3 --risk-assessment
/document architecture --format technical --audience developers
```

### 2. Multi-Agent Orchestration
```bash
# Parallel development
Task("Backend API development") & Task("Frontend components") & Task("Database optimization")

# Specialized agents
/agents create --name architecture-reviewer --expertise "system design, scalability"
/agents create --name security-auditor --expertise "vulnerability assessment"
/agents create --name performance-optimizer --expertise "bottlenecks, optimization"
```

### 3. Quality Gates & Validation
```bash
/test --comprehensive --coverage 90%
/analyze --focus security,performance,maintainability
/validate --standards production-ready
/improve --quality --focus "technical debt, code smells"
```

### 4. Progressive Development
```bash
/plan feature --breakdown tasks --dependencies --timeline
/build incremental --test-each-step
/integrate --conflict-detection --rollback-ready
/milestone create "MVP ready" --criteria "core features, basic tests"
```

### 5. Error Prevention & Recovery
```bash
/analyze --focus "potential failures, edge cases"
/troubleshoot --preventive --scope system-wide
/monitor --setup alerts,metrics,logs
/branch feature-experiment --isolate-changes
```

### 6. Production Readiness
```bash
/build production --optimize --security-hardening
/deploy --strategy blue-green --rollback-plan
/monitor production --alerts critical-only
/document --api-auto-generate
```

## 📊 Context Window Insights

### Current Limits (Jan 2025)
- **Claude Code**: 200K tokens (mevcut)
- **Anthropic API**: 1M tokens (Beta, Tier 4 customers)
- **Pricing**: 200K'dan sonra 2x input, 1.5x output

### Context Allocation Strategy
```
Optimal Distribution:
├── 25-30%: System + Memory (değişmez)
├── 25-30%: CLAUDE.md (interface specs)
├── 30-40%: Active work (messages)
└── 10-15%: Safety buffer
```

## 🎯 Agent Orchestration Patterns

### Meta-Agent Example: Swarm Optimizer
```markdown
---
name: swarm-orchestrator
description: OpenAI Swarm system optimizer for WhatsApp B2B
tools: Read, Edit, MultiEdit, Bash
---

You are a specialized Swarm Agent Systems expert. Your role:
- Analyze incoming WhatsApp messages for intent patterns
- Optimize agent routing and tool organization
- Fine-tune agent prompts and transfer functions
- Monitor agent performance and suggest improvements
```

### Compound Intelligence Strategy
```
Intelligence Layers:
├── Main Agent: Strategy & coordination
├── Meta Agent: System optimization
├── Specialist Agents: Domain expertise
└── Emergent system intelligence
```

## 🔄 Workflow Patterns

### Large Project Workflow
```bash
# Phase 1: Foundation
/design + /plan + /document + /clear

# Phase 2: Development (iterative)
/build incremental + /test + /compact + /milestone check

# Phase 3: Integration
/integrate + /validate + /troubleshoot + /clear

# Phase 4: Production
/build production + /deploy + /monitor + /document
```

### Context Efficiency Checkpoints
```
Context Health Checks:
├── 30%: Green - Normal operation
├── 50%: Yellow - Plan compact soon
├── 70%: Orange - Compact preparation
├── 85%: Red - Compact NOW
├── 95%: Critical - /clear or emergency compact
```

## 💡 Advanced Strategies

### Agent Discovery Process
```python
# Subagent otomatik keşif süreci:
1. pwd → Hangi dizindeyim?
2. ls -la → Ne var burada?
3. Read CLAUDE.md → Proje nedir?
4. Find package.json → Tech stack?
5. Grep patterns → Relevant files?
6. Context building → Task execution
```

### Performance Benefits
```
Agent Advantages:
├── Context Efficiency: Fresh context per agent
├── Parallel Processing: 4x speed improvement possible
├── Specialized Expertise: Domain-focused intelligence
└── Context Window Multiplication: Effective 800k tokens with 4 agents
```

### State Persistence Solutions
```
Consistency Patterns:
├── Work History Documentation (agents/*.md)
├── Interface Specifications (CLAUDE.md)
├── Session Instructions (preserve vs improve)
└── Incremental-only approach
```

## 🏗️ Implementation Recommendations

### File Organization
```
project/
├── CLAUDE.md (System interfaces)
├── agents/ (Work history)
│   ├── UIDesigner.md
│   ├── SwarmOptimizer.md
│   └── DatabaseExpert.md
├── docs/ (Generated documentation)
└── .claude/ (Claude-specific configs)
```

### Memory Strategy
```
Memory Hierarchy:
├── User CLAUDE.md: Global preferences, flags
├── Project CLAUDE.md: System architecture, interfaces
├── Agent files: Work history, incremental changes
└── Session memory: Active conversation context
```

### Quality Gates
```
Mandatory Checks:
├── Pre-deployment: /test + /analyze + /validate
├── Architecture: /design review + dependency analysis
├── Security: /analyze --focus security + audit
├── Performance: /monitor + bottleneck analysis
```

## 📈 Success Metrics

### Project Health Indicators
- Context usage consistently under 85%
- Agent session history well-documented
- Interface specifications stable
- Incremental progress documented
- Quality gates consistently passed

### Efficiency Measures
- Reduced context pollution
- Faster development cycles
- Better code quality
- Improved maintainability
- Enhanced team collaboration

---

## 🎯 Key Takeaways

1. **Bebek Adımları**: Her adımdan sonra compact veya clear
2. **Interface vs Implementation**: CLAUDE.md specs, agent files history
3. **Context Budget**: 85% üzerine çıkmamak
4. **Agent State Management**: Incremental work, preserve guidelines
5. **Compound Intelligence**: Meta-agents + specialists = emergent capability

**Remember**: Claude Code agents = Context efficiency + Parallel power + Specialized expertise = 4-10x performance boost! 🚀