---
name: color-scheme
description: shared utility for color-scheme
---
---
name: color-scheme
description: Shared color scheme and visual styling for agent interfaces.---
# Agent System Color Scheme

## Color Psychology and Assignment Rationale

Based on UX best practices and the 60-30-10 rule, our agent system uses semantic colors that convey function and urgency while maintaining accessibility standards (WCAG 2.1 AA compliance with 4.5:1 contrast ratios).

## Primary Color Categories

### 🔴 Critical/Security (Red Spectrum)
**Hex: #DC2626 | RGB: 220, 38, 38**
- **Security-Architect**: Deep red for threat detection and security gates
- **Secrets-IAM-Guard**: Crimson for credential and access control
- **Incident-Responder**: Alert red for emergency response

### 🟠 Caution/Review (Orange Spectrum)  
**Hex: #EA580C | RGB: 234, 88, 12**
- **AppSec-Reviewer**: Safety orange for vulnerability scanning
- **Compliance-License**: Regulatory orange for legal compliance
- **Issue-Triage-PR-Reviewer**: Review orange for code assessment

### 🟡 Planning/Analysis (Yellow Spectrum)
**Hex: #CA8A04 | RGB: 202, 138, 4**
- **Product-Spec-Writer**: Golden yellow for requirements definition
- **Data-Privacy-Governance**: Amber for data classification
- **API-Contracts**: Contract yellow for interface definitions

### 🟢 Implementation/Building (Green Spectrum)
**Hex: #16A34A | RGB: 22, 163, 74**
- **Backend-Implementer**: Forest green for server-side development
- **Frontend-Implementer**: Lime green for client-side development
- **Database-Migration**: Data green for schema operations
- **Python-UV-Specialist**: Python green (#3776AB variant)

### 🔵 Architecture/Design (Blue Spectrum)
**Hex: #2563EB | RGB: 37, 99, 235**
- **Architecture-Design-Opus**: Royal blue for system design
- **Lead-Orchestrator**: Navy blue for coordination and leadership
- **Kubernetes-Orchestrator**: Container blue for orchestration

### 🟣 Quality/Testing (Purple Spectrum)
**Hex: #9333EA | RGB: 147, 51, 234**
- **Test-Engineer**: Testing purple for quality assurance
- **Performance-Profiler**: Performance violet for optimization
- **Observability-Telemetry**: Monitoring purple for insights

### ⚫ Infrastructure/Platform (Gray Spectrum)
**Hex: #6B7280 | RGB: 107, 114, 128**
- **IaC-Platform**: Infrastructure gray for platform engineering
- **CI-CD-Engineer**: Pipeline gray for automation
- **Podman-Container-Builder**: Container gray for packaging
- **DevEx-Build**: Developer gray for tooling

### 🟤 Documentation/Knowledge (Brown Spectrum)
**Hex: #92400E | RGB: 146, 64, 14**
- **Docs-Changelog**: Documentation brown for knowledge management
- **RAG-Knowledge-Indexer**: Knowledge brown for information retrieval
- **API-Documentation**: Reference brown for API docs

### 🩵 Innovation/AI (Cyan Spectrum)
**Hex: #06B6D4 | RGB: 6, 182, 212**
- **LLM-Safety-Prompt-Eval**: AI cyan for model evaluation
- **Open-Source-Scout-Integrator**: Innovation cyan for discovery

### 🩷 Release/Deployment (Magenta Spectrum)
**Hex: #EC4899 | RGB: 236, 72, 153**
- **Release-Manager**: Release magenta for deployment coordination
- **Performance-Reliability**: Reliability pink for SRE concerns

## Terminal Color Codes

### ANSI 256-Color Codes
```bash
# Security/Critical (Reds)
security-architect: 196
secrets-iam-guard: 160
incident-responder: 9

# Review/Caution (Oranges)
appsec-reviewer: 208
compliance-license: 214
issue-triage: 202

# Planning (Yellows)
product-spec-writer: 220
data-privacy: 178
api-contracts: 226

# Implementation (Greens)
backend-impl: 34
frontend-impl: 118
database-migration: 28
python-uv: 70

# Architecture (Blues)
architecture-design: 21
lead-orchestrator: 19
kubernetes: 33

# Testing (Purples)
test-engineer: 129
performance-profiler: 135
observability: 99

# Infrastructure (Grays)
iac-platform: 244
cicd-engineer: 240
podman-builder: 242
devex-build: 245

# Documentation (Browns)
docs-changelog: 94
rag-knowledge: 130
api-documentation: 137

# Innovation (Cyans)
llm-safety: 51
open-source-scout: 87

# Release (Magentas)
release-manager: 201
perf-reliability: 213
```

## Usage Guidelines

### 1. Status Indicators
```
🟢 Success/Ready: Use implementation green
🟡 Warning/Pending: Use planning yellow
🔴 Error/Blocked: Use security red
🔵 Info/Processing: Use architecture blue
⚫ Neutral/System: Use infrastructure gray
```

### 2. Progress Bars
```
Low Risk: Green gradient (34 → 118)
Medium Risk: Yellow gradient (220 → 178)
High Risk: Orange gradient (208 → 214)
Critical Risk: Red gradient (196 → 160)
```

### 3. Agent Communication
When agents communicate, use color to indicate message priority:
```
CRITICAL: Red background, white text
HIGH: Orange background, black text
MEDIUM: Yellow background, black text
LOW: Green background, black text
INFO: Blue background, white text
```

### 4. Dark Mode Adjustments
For dark mode terminals, adjust luminosity while maintaining hue:
- Increase brightness by 20% for backgrounds
- Decrease brightness by 10% for text
- Maintain minimum 7:1 contrast ratio

### 5. Accessibility Considerations

#### Color Blind Friendly Alternatives
```
Protanopia (Red-Green Blind):
- Replace red-green with blue-orange
- Use patterns/icons as secondary indicators

Deuteranopia (Green-Red Blind):
- Replace green-red with blue-yellow
- Add text labels for critical distinctions

Tritanopia (Blue-Yellow Blind):
- Replace blue-yellow with red-green
- Use brightness variations
```

#### High Contrast Mode
```
Background: #000000 (pure black)
Primary Text: #FFFFFF (pure white)
Success: #00FF00 (bright green)
Warning: #FFFF00 (bright yellow)
Error: #FF0000 (bright red)
Info: #00FFFF (bright cyan)
```

## Implementation Examples

### Agent Header Format
```
╔════════════════════════════════════════╗
║ [COLOR] AGENT-NAME [COLOR]            ║
║ Role: [Agent Role Description]         ║
║ Status: [Active|Idle|Processing]       ║
╚════════════════════════════════════════╝
```

### Task Status Display
```
[🔵] Architecture Design: Planning system components
[🟢] Backend Implementation: Building API endpoints
[🟡] Security Review: Analyzing dependencies
[🔴] Critical Issue: Blocking deployment
```

### Inter-Agent Communication
```
[LEAD-ORCHESTRATOR] → [SECURITY-ARCHITECT]: Requesting security review
[SECURITY-ARCHITECT] → [APPSEC-REVIEWER]: Initiate vulnerability scan
[APPSEC-REVIEWER] → [LEAD-ORCHESTRATOR]: 3 high-severity findings
```

## Color Configuration API

```yaml
color_scheme:
  mode: "auto"  # auto|light|dark|high-contrast
  accessibility: "none"  # none|protanopia|deuteranopia|tritanopia
  
  agents:
    lead-orchestrator:
      primary: "#2563EB"
      secondary: "#1E40AF"
      accent: "#DBEAFE"
      terminal: 19
      
    security-architect:
      primary: "#DC2626"
      secondary: "#991B1B"
      accent: "#FEE2E2"
      terminal: 196
    
    # ... (other agents)
  
  semantic:
    success: "#16A34A"
    warning: "#CA8A04"
    error: "#DC2626"
    info: "#2563EB"
    debug: "#6B7280"
  
  gradients:
    risk_low: ["#16A34A", "#10B981"]
    risk_medium: ["#CA8A04", "#EAB308"]
    risk_high: ["#EA580C", "#F97316"]
    risk_critical: ["#DC2626", "#EF4444"]
```

## Dynamic Color Assignment

For new agents, the system automatically assigns colors based on:
1. Primary function category (security, implementation, testing, etc.)
2. Existing color distribution (avoid overuse of any spectrum)
3. Contrast requirements with frequently interacting agents
4. User preferences and accessibility settings

## Best Practices

1. **Consistency**: Always use the assigned color for an agent across all interfaces
2. **Contrast**: Ensure text is readable against backgrounds (4.5:1 minimum)
3. **Meaning**: Use color to convey information, not just decoration
4. **Redundancy**: Never rely solely on color; include icons, text, or patterns
5. **Testing**: Validate color choices with actual users and different display types
6. **Documentation**: Update this scheme when adding new agents or changing assignments
7. **Flexibility**: Allow users to customize colors while maintaining semantic meaning