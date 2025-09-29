---
name: model-fallback
description: shared utility for model-fallback
---
---
name: model-fallback
description: Shared model fallback and selection logic for agents.---
# Model Fallback Configuration

## Intelligent Model Selection and Fallback

This configuration enables automatic fallback from Opus to Sonnet 4 when usage limits are reached, ensuring continuous agent operation while optimizing for the best available model.

### Fallback Strategy

```yaml
model_fallback:
  enabled: true
  strategy: "graceful_degradation"
  retry_after_cooldown: true
  cooldown_duration: "30m"  # Wait before retrying Opus
  
  models:
    primary: "claude-3-5-sonnet-20241022"  # Sonnet 4
    fallback: "claude-3-haiku-20240307"    # Haiku as last resort
    # Note: Opus will be primary when available, fallback to Sonnet 4
  
  usage_monitoring:
    check_limits: true
    preemptive_fallback: 0.9  # Switch at 90% usage
    track_quota_reset: true
    
  per_agent_config:
    critical_agents:
      - lead-orchestrator
      - security-threat-modeler  
      - architecture-design-opus
      - incident-responder
    
    standard_agents:
      - observability-monitoring
      - python-uv-specialist
      - podman-container-builder
```

### Agent Model Configuration Format

```yaml
# Template for agent configuration with fallback
Model: "Opus|Sonnet"  # Try Opus first, fallback to Sonnet 4

ModelConfig:
  primary: "opus"
  fallback: "sonnet-4"
  fallback_triggers:
    - rate_limit_exceeded
    - quota_exhausted
    - response_timeout > 30s
  
  context_preservation:
    enabled: true
    transfer_conversation_history: true
    maintain_agent_state: true
    
  performance_monitoring:
    track_model_switches: true
    measure_quality_delta: true
    alert_on_degradation: true
```

## Implementation Strategy

### 1. Rate Limit Detection
```python
# Pseudo-code for model fallback logic
class ModelFallbackHandler:
    def __init__(self):
        self.current_model = "opus"
        self.fallback_model = "sonnet-4"
        self.quota_monitor = QuotaMonitor()
        
    def get_available_model(self, agent_name: str) -> str:
        """Determine best available model for agent"""
        
        # Check if Opus is available
        if self.quota_monitor.can_use_opus():
            return "opus"
        
        # Check rate limit status
        if self.quota_monitor.is_rate_limited("opus"):
            self.log_fallback("opus", "sonnet-4", "rate_limit_exceeded")
            return "sonnet-4"
        
        # Check quota exhaustion
        if self.quota_monitor.quota_usage("opus") > 0.9:
            self.log_fallback("opus", "sonnet-4", "quota_threshold_reached")
            return "sonnet-4"
            
        return "opus"  # Default to best model
        
    def execute_with_fallback(self, agent_name: str, prompt: str):
        """Execute agent task with automatic fallback"""
        
        models_to_try = [
            self.get_available_model(agent_name),
            "sonnet-4",  # Always try Sonnet 4 as fallback
            "haiku"      # Final fallback for non-critical tasks
        ]
        
        for model in models_to_try:
            try:
                response = self.call_model(model, prompt, agent_name)
                self.log_success(model, agent_name)
                return response
                
            except RateLimitException:
                self.log_rate_limit(model, agent_name)
                continue
                
            except QuotaExhaustedException:
                self.log_quota_exhausted(model, agent_name)
                continue
                
            except Exception as e:
                self.log_error(model, agent_name, str(e))
                continue
        
        raise AllModelsUnavailableException("All models exhausted")
```

### 2. Context Preservation During Fallback
```python
class ContextManager:
    """Preserve agent context during model transitions"""
    
    def transfer_context(self, from_model: str, to_model: str, agent_state: dict):
        """Transfer conversation and state between models"""
        
        transfer_package = {
            "agent_name": agent_state["name"],
            "conversation_history": agent_state["messages"][-10:],  # Last 10 messages
            "current_task": agent_state["current_task"],
            "task_progress": agent_state["progress"],
            "context_summary": self.summarize_context(agent_state),
            "fallback_reason": f"Switched from {from_model} to {to_model}"
        }
        
        # Inject context preservation prompt
        context_prompt = f"""
        CONTEXT TRANSFER NOTICE: 
        You are continuing a conversation that was started with {from_model}.
        
        Previous Context Summary: {transfer_package["context_summary"]}
        Current Task: {transfer_package["current_task"]}
        Progress: {transfer_package["task_progress"]}
        
        Continue seamlessly from where the previous model left off.
        Maintain the same expertise level and decision-making quality.
        """
        
        return context_prompt
```

## Updated Agent Configurations

Let me update the existing agents to include the fallback mechanism:

### Lead Orchestrator (Opus → Sonnet 4)
```yaml
Model: "Opus|Sonnet"
ModelConfig:
  primary: "opus"
  fallback: "sonnet-4" 
  reason: "Complex orchestration requires highest reasoning, but Sonnet 4 acceptable"
```

### Security Threat Modeler (Opus → Sonnet 4) 
```yaml
Model: "Opus|Sonnet"
ModelConfig:
  primary: "opus"
  fallback: "sonnet-4"
  reason: "Security analysis benefits from Opus reasoning, Sonnet 4 provides good coverage"
```

### Architecture Design (Opus → Sonnet 4)
```yaml
Model: "Opus|Sonnet" 
ModelConfig:
  primary: "opus"
  fallback: "sonnet-4"
  reason: "Architecture decisions need deep reasoning, Sonnet 4 suitable for most cases"
```

## Monitoring and Alerting

### Usage Tracking
```yaml
monitoring_metrics:
  model_usage:
    - opus_requests_total
    - sonnet_requests_total  
    - haiku_requests_total
    
  fallback_events:
    - fallback_triggered_total
    - fallback_reason{reason="rate_limit|quota|timeout|error"}
    - context_transfer_success_rate
    
  quality_metrics:
    - task_completion_rate_by_model
    - user_satisfaction_by_model
    - error_rate_by_model
    
  quota_monitoring:
    - opus_quota_usage_percent
    - opus_rate_limit_approaching
    - estimated_time_to_quota_reset
```

### Alert Configuration
```yaml
alerts:
  - name: OpusQuotaHigh
    condition: opus_quota_usage_percent > 85
    severity: warning
    message: "Opus quota at {{ $value }}% - fallback imminent"
    
  - name: OpusUnavailable  
    condition: fallback_triggered_total{reason="quota"} > 0
    severity: critical
    message: "Opus unavailable - agents running on Sonnet 4"
    
  - name: ContextTransferFailing
    condition: context_transfer_success_rate < 0.95
    severity: warning
    message: "Context transfer success rate: {{ $value }}"
```

## Best Practices for Fallback Implementation

### 1. Graceful Degradation
- Maintain agent personality and expertise level
- Preserve conversation context and state
- Continue tasks without interruption
- Inform user only if quality significantly impacts results

### 2. Intelligent Model Selection
```python
def select_model_for_task(task_complexity: str, agent_type: str) -> str:
    """Intelligent model selection based on task requirements"""
    
    # Critical decision-making tasks prefer Opus
    if task_complexity in ["critical", "complex_reasoning", "security_analysis"]:
        return get_available_model_with_preference("opus")
    
    # Standard tasks work well with Sonnet 4
    elif task_complexity in ["standard", "implementation", "analysis"]:
        return get_available_model_with_preference("sonnet-4")
    
    # Simple tasks can use Haiku
    elif task_complexity in ["simple", "formatting", "basic_queries"]:
        return "haiku"
        
    return "sonnet-4"  # Safe default
```

### 3. Quality Assurance
- Monitor output quality across model transitions
- Maintain performance benchmarks per model
- Alert on significant quality degradation
- Automatically retry with higher model if results unsatisfactory

### 4. Cost Optimization
```yaml
cost_optimization:
  strategy: "smart_routing"
  
  routing_rules:
    - condition: "task_type == 'code_review'"
      preferred_model: "sonnet-4"
      reason: "Sonnet 4 excellent for code analysis"
      
    - condition: "task_type == 'threat_modeling'" 
      preferred_model: "opus"
      reason: "Security analysis requires deep reasoning"
      
    - condition: "task_type == 'documentation'"
      preferred_model: "haiku"
      reason: "Documentation generation works well with Haiku"
  
  fallback_budget:
    daily_opus_limit: 1000  # requests
    reserve_for_critical: 100  # keep for emergencies
    auto_upgrade_threshold: 0.95  # upgrade to Opus if task failing
```

This fallback mechanism ensures continuous operation while optimizing for the best available model, maintaining context during transitions, and providing comprehensive monitoring of model usage and performance.