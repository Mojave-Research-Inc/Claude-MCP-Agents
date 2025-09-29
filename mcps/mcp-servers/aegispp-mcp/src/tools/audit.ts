import { brainAdapter } from '../adapters/brain.js';
import { now } from '../ids.js';
import { logger } from '../logger.js';

export const audit_trail = {
  name: 'audit_trail',
  description: 'Generate comprehensive audit trail for plan execution',
  inputSchema: {
    type: 'object',
    properties: {
      plan_id: { type: 'string', description: 'Plan ID to audit (optional - audits all if not provided)' },
      timeframe: { type: 'string', enum: ['hour', 'day', 'week', 'month'], default: 'day' },
      include_attestations: { type: 'boolean', default: true, description: 'Include SLSA attestations' },
      format: { type: 'string', enum: ['json', 'summary', 'detailed'], default: 'detailed' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      const timeframMs = {
        hour: 60 * 60 * 1000,
        day: 24 * 60 * 60 * 1000,
        week: 7 * 24 * 60 * 60 * 1000,
        month: 30 * 24 * 60 * 60 * 1000
      };

      const cutoff = now() - timeframMs[input.timeframe || 'day'];

      // Get comprehensive audit data
      let planFilter = '';
      let params = [cutoff];

      if (input.plan_id) {
        planFilter = ' AND p.id = ?';
        params.push(input.plan_id);
      }

      const auditData = db.all(`
        SELECT
          p.id as plan_id, p.goal, p.owner, p.status as plan_status,
          p.created_at as plan_created, p.updated_at as plan_updated,
          s.id as step_id, s.capability, s.status as step_status, s.critical,
          s.created_at as step_created, s.updated_at as step_updated,
          t.id as ticket_id, t.route_id, t.latency_ms, t.cost,
          t.created_at as execution_started, t.completed_at as execution_completed,
          r.mcp_id, r.tool,
          e.source as event_source, e.kind as event_kind, e.payload as event_payload, e.ts as event_time
        FROM plans p
        LEFT JOIN steps s ON p.id = s.plan_id
        LEFT JOIN tickets t ON s.id = t.step_id
        LEFT JOIN routes r ON t.route_id = r.id
        LEFT JOIN events e ON e.ts > ? AND (
          (e.source = 'planning' AND JSON_EXTRACT(e.payload, '$.plan_id') = p.id) OR
          (e.source = 'execution' AND JSON_EXTRACT(e.payload, '$.step_id') = s.id)
        )
        WHERE p.created_at > ?${planFilter}
        ORDER BY p.created_at DESC, s.order_index, t.created_at
      `, cutoff, ...params) as any[];

      // Get attestations if requested
      let attestations = [];
      if (input.include_attestations) {
        attestations = db.all(`
          SELECT a.*, t.step_id, p.id as plan_id
          FROM attestations a
          JOIN tickets t ON a.ticket_id = t.id
          JOIN steps s ON t.step_id = s.id
          JOIN plans p ON s.plan_id = p.id
          WHERE a.created_at > ?${planFilter}
          ORDER BY a.created_at DESC
        `, cutoff, ...(input.plan_id ? [input.plan_id] : [])) as any[];
      }

      // Process audit data by format
      let result;
      switch (input.format) {
        case 'json':
          result = this.formatAsJSON(auditData, attestations);
          break;
        case 'summary':
          result = this.formatAsSummary(auditData, attestations);
          break;
        case 'detailed':
        default:
          result = this.formatAsDetailed(auditData, attestations, input);
          break;
      }

      // Log audit access
      db.event('audit', 'trail_accessed', {
        plan_id: input.plan_id,
        timeframe: input.timeframe,
        format: input.format,
        records_found: auditData.length
      });

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      logger.error('Audit trail generation failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  },

  formatAsJSON(auditData: any[], attestations: any[]): any {
    return {
      audit_type: 'raw_data',
      execution_records: auditData,
      attestation_records: attestations,
      generated_at: now()
    };
  },

  formatAsSummary(auditData: any[], attestations: any[]): any {
    const plans = new Set(auditData.map(r => r.plan_id));
    const steps = auditData.filter(r => r.step_id);
    const tickets = auditData.filter(r => r.ticket_id);
    const events = auditData.filter(r => r.event_kind);

    return {
      audit_type: 'summary',
      summary: {
        plans_executed: plans.size,
        steps_executed: new Set(steps.map(s => s.step_id)).size,
        executions_completed: new Set(tickets.map(t => t.ticket_id)).size,
        attestations_created: attestations.length,
        audit_events: new Set(events.map(e => e.event_kind)).size,
        total_cost: tickets.reduce((sum, t) => sum + (t.cost || 0), 0),
        avg_latency_ms: tickets.length > 0 ?
          tickets.reduce((sum, t) => sum + (t.latency_ms || 0), 0) / tickets.length : 0
      },
      compliance_status: this.assessCompliance(auditData, attestations),
      generated_at: now()
    };
  },

  formatAsDetailed(auditData: any[], attestations: any[], input: any): any {
    const planMap = new Map();

    // Group data by plan
    auditData.forEach(record => {
      if (!planMap.has(record.plan_id)) {
        planMap.set(record.plan_id, {
          plan: {
            id: record.plan_id,
            goal: record.goal,
            owner: record.owner,
            status: record.plan_status,
            created_at: record.plan_created,
            updated_at: record.plan_updated
          },
          steps: new Map(),
          events: []
        });
      }

      const planData = planMap.get(record.plan_id);

      if (record.step_id && !planData.steps.has(record.step_id)) {
        planData.steps.set(record.step_id, {
          step: {
            id: record.step_id,
            capability: record.capability,
            status: record.step_status,
            critical: Boolean(record.critical),
            created_at: record.step_created,
            updated_at: record.step_updated
          },
          executions: []
        });
      }

      if (record.ticket_id) {
        const stepData = planData.steps.get(record.step_id);
        if (stepData) {
          stepData.executions.push({
            ticket_id: record.ticket_id,
            route_id: record.route_id,
            mcp_id: record.mcp_id,
            tool: record.tool,
            latency_ms: record.latency_ms,
            cost: record.cost,
            started_at: record.execution_started,
            completed_at: record.execution_completed
          });
        }
      }

      if (record.event_kind) {
        planData.events.push({
          source: record.event_source,
          kind: record.event_kind,
          payload: record.event_payload ? JSON.parse(record.event_payload) : {},
          timestamp: record.event_time
        });
      }
    });

    // Convert maps to arrays for JSON serialization
    const plans = Array.from(planMap.values()).map(planData => ({
      ...planData.plan,
      steps: Array.from(planData.steps.values()),
      events: planData.events
    }));

    return {
      audit_type: 'detailed',
      timeframe: input.timeframe,
      plans,
      attestations: this.groupAttestationsByPlan(attestations),
      compliance_assessment: this.assessCompliance(auditData, attestations),
      security_analysis: this.analyzeSecurityEvents(auditData),
      performance_metrics: this.calculateAuditMetrics(auditData),
      generated_at: now()
    };
  },

  groupAttestationsByPlan(attestations: any[]): any {
    const grouped = {};
    attestations.forEach(att => {
      if (!grouped[att.plan_id]) {
        grouped[att.plan_id] = [];
      }
      grouped[att.plan_id].push(att);
    });
    return grouped;
  },

  assessCompliance(auditData: any[], attestations: any[]): any {
    const criticalSteps = auditData.filter(r => r.critical && r.step_id);
    const criticalWithAttestations = criticalSteps.filter(step =>
      attestations.some(att => att.step_id === step.step_id)
    );

    const completedSteps = auditData.filter(r => r.step_status === 'done');
    const failedSteps = auditData.filter(r => r.step_status === 'failed');

    return {
      critical_steps_attested: criticalSteps.length > 0 ?
        criticalWithAttestations.length / criticalSteps.length : 1.0,
      execution_success_rate: completedSteps.length + failedSteps.length > 0 ?
        completedSteps.length / (completedSteps.length + failedSteps.length) : 0,
      attestation_coverage: criticalSteps.length > 0 ?
        criticalWithAttestations.length / criticalSteps.length : 1.0,
      compliance_level: this.calculateComplianceLevel(criticalSteps, criticalWithAttestations, completedSteps, failedSteps)
    };
  },

  calculateComplianceLevel(criticalSteps: any[], attested: any[], completed: any[], failed: any[]): string {
    const attestationRate = criticalSteps.length > 0 ? attested.length / criticalSteps.length : 1.0;
    const successRate = completed.length + failed.length > 0 ?
      completed.length / (completed.length + failed.length) : 0;

    if (attestationRate >= 0.95 && successRate >= 0.95) return 'excellent';
    if (attestationRate >= 0.8 && successRate >= 0.8) return 'good';
    if (attestationRate >= 0.6 && successRate >= 0.6) return 'acceptable';
    return 'needs_improvement';
  },

  analyzeSecurityEvents(auditData: any[]): any {
    const securityEvents = auditData.filter(r =>
      r.event_source === 'security' ||
      (r.event_payload && JSON.parse(r.event_payload).security_relevant)
    );

    return {
      security_events_detected: securityEvents.length,
      event_types: [...new Set(securityEvents.map(e => e.event_kind))],
      risk_level: securityEvents.length > 10 ? 'high' :
                  securityEvents.length > 3 ? 'medium' : 'low'
    };
  },

  calculateAuditMetrics(auditData: any[]): any {
    const executions = auditData.filter(r => r.ticket_id);

    return {
      total_executions: executions.length,
      avg_execution_time_ms: executions.length > 0 ?
        executions.reduce((sum, e) => sum + (e.latency_ms || 0), 0) / executions.length : 0,
      total_cost: executions.reduce((sum, e) => sum + (e.cost || 0), 0),
      unique_capabilities: new Set(auditData.map(r => r.capability).filter(Boolean)).size,
      unique_mcps: new Set(auditData.map(r => r.mcp_id).filter(Boolean)).size
    };
  }
};

export const compliance_check = {
  name: 'compliance_check',
  description: 'Check compliance with security and operational policies',
  inputSchema: {
    type: 'object',
    properties: {
      plan_id: { type: 'string', description: 'Plan ID to check (optional)' },
      policy_set: { type: 'string', enum: ['security', 'operational', 'all'], default: 'all' },
      severity_filter: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'all'], default: 'all' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      logger.info(`Running compliance check for policy set: ${input.policy_set}`);

      const checks = [];

      // Security policy checks
      if (input.policy_set === 'security' || input.policy_set === 'all') {
        checks.push(...this.runSecurityChecks(input, db));
      }

      // Operational policy checks
      if (input.policy_set === 'operational' || input.policy_set === 'all') {
        checks.push(...this.runOperationalChecks(input, db));
      }

      // Filter by severity
      const filteredChecks = input.severity_filter === 'all' ? checks :
        checks.filter(check => check.severity === input.severity_filter);

      // Calculate compliance score
      const passed = filteredChecks.filter(c => c.status === 'pass').length;
      const total = filteredChecks.length;
      const complianceScore = total > 0 ? passed / total : 1.0;

      // Group violations by category
      const violations = filteredChecks
        .filter(c => c.status === 'fail')
        .reduce((groups, check) => {
          if (!groups[check.category]) groups[check.category] = [];
          groups[check.category].push(check);
          return groups;
        }, {});

      // Log compliance check
      db.event('audit', 'compliance_checked', {
        plan_id: input.plan_id,
        policy_set: input.policy_set,
        total_checks: total,
        passed_checks: passed,
        compliance_score: complianceScore
      });

      const result = {
        plan_id: input.plan_id,
        policy_set: input.policy_set,
        compliance_score: complianceScore,
        compliance_level: this.getComplianceLevel(complianceScore),
        total_checks: total,
        passed_checks: passed,
        failed_checks: total - passed,
        checks: filteredChecks,
        violations_by_category: violations,
        recommendations: this.generateComplianceRecommendations(violations),
        checked_at: now()
      };

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      logger.error('Compliance check failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  },

  runSecurityChecks(input: any, db: any): any[] {
    const checks = [];

    // Check critical step attestations
    let query = 'SELECT COUNT(*) as total FROM steps WHERE critical = 1';
    let params = [];

    if (input.plan_id) {
      query += ' AND plan_id = ?';
      params.push(input.plan_id);
    }

    const criticalSteps = db.get(query, ...params);

    query = `
      SELECT COUNT(*) as attested FROM steps s
      JOIN tickets t ON s.id = t.step_id
      JOIN attestations a ON t.id = a.ticket_id
      WHERE s.critical = 1
    `;

    if (input.plan_id) {
      query += ' AND s.plan_id = ?';
    }

    const attestedSteps = db.get(query, ...params);

    const attestationRate = criticalSteps.total > 0 ?
      attestedSteps.attested / criticalSteps.total : 1.0;

    checks.push({
      id: 'SEC-001',
      category: 'security',
      name: 'Critical Step Attestations',
      description: 'All critical steps must have SLSA attestations',
      status: attestationRate >= 0.95 ? 'pass' : 'fail',
      severity: 'critical',
      details: {
        critical_steps: criticalSteps.total,
        attested_steps: attestedSteps.attested,
        attestation_rate: attestationRate
      }
    });

    // Check for failed executions in critical steps
    query = `
      SELECT COUNT(*) as failed FROM steps s
      JOIN tickets t ON s.id = t.step_id
      WHERE s.critical = 1 AND t.status = 'failed'
    `;

    if (input.plan_id) {
      query += ' AND s.plan_id = ?';
    }

    const failedCritical = db.get(query, ...params);

    checks.push({
      id: 'SEC-002',
      category: 'security',
      name: 'Critical Step Failures',
      description: 'Critical steps should not fail',
      status: failedCritical.failed === 0 ? 'pass' : 'fail',
      severity: 'high',
      details: {
        failed_critical_steps: failedCritical.failed
      }
    });

    // Check for unauthorized route usage
    query = `
      SELECT COUNT(*) as unauthorized FROM tickets t
      JOIN routes r ON t.route_id = r.id
      WHERE r.healthy = 0
    `;

    if (input.plan_id) {
      query += ` AND t.step_id IN (
        SELECT id FROM steps WHERE plan_id = ?
      )`;
    }

    const unauthorizedRoutes = db.get(query, ...params);

    checks.push({
      id: 'SEC-003',
      category: 'security',
      name: 'Route Health Verification',
      description: 'Only healthy routes should be used for execution',
      status: unauthorizedRoutes.unauthorized === 0 ? 'pass' : 'fail',
      severity: 'medium',
      details: {
        unhealthy_route_usages: unauthorizedRoutes.unauthorized
      }
    });

    return checks;
  },

  runOperationalChecks(input: any, db: any): any[] {
    const checks = [];

    // Check execution performance
    let query = `
      SELECT AVG(latency_ms) as avg_latency, COUNT(*) as total
      FROM tickets
      WHERE status = 'completed'
    `;
    let params = [];

    if (input.plan_id) {
      query += ` AND step_id IN (
        SELECT id FROM steps WHERE plan_id = ?
      )`;
      params.push(input.plan_id);
    }

    const performance = db.get(query, ...params);
    const avgLatency = performance.avg_latency || 0;

    checks.push({
      id: 'OPS-001',
      category: 'operational',
      name: 'Execution Performance',
      description: 'Average execution time should be under 30 seconds',
      status: avgLatency < 30000 ? 'pass' : 'fail',
      severity: avgLatency > 60000 ? 'high' : 'medium',
      details: {
        avg_latency_ms: avgLatency,
        total_executions: performance.total
      }
    });

    // Check cost efficiency
    query = `
      SELECT AVG(cost) as avg_cost, SUM(cost) as total_cost
      FROM tickets
      WHERE status = 'completed'
    `;

    if (input.plan_id) {
      query += ` AND step_id IN (
        SELECT id FROM steps WHERE plan_id = ?
      )`;
    }

    const costData = db.get(query, ...params);
    const avgCost = costData.avg_cost || 0;

    checks.push({
      id: 'OPS-002',
      category: 'operational',
      name: 'Cost Efficiency',
      description: 'Average execution cost should be reasonable',
      status: avgCost < 5.0 ? 'pass' : 'fail',
      severity: avgCost > 10.0 ? 'high' : 'low',
      details: {
        avg_cost: avgCost,
        total_cost: costData.total_cost
      }
    });

    // Check route diversity
    query = `
      SELECT COUNT(DISTINCT route_id) as unique_routes,
             COUNT(DISTINCT capability) as capabilities
      FROM tickets t
      JOIN steps s ON t.step_id = s.id
      WHERE t.status = 'completed'
    `;

    if (input.plan_id) {
      query += ' AND s.plan_id = ?';
    }

    const diversity = db.get(query, ...params);
    const diversityRatio = diversity.capabilities > 0 ?
      diversity.unique_routes / diversity.capabilities : 0;

    checks.push({
      id: 'OPS-003',
      category: 'operational',
      name: 'Route Diversity',
      description: 'Should have multiple routes available per capability',
      status: diversityRatio >= 1.2 ? 'pass' : 'fail',
      severity: 'low',
      details: {
        unique_routes: diversity.unique_routes,
        capabilities: diversity.capabilities,
        diversity_ratio: diversityRatio
      }
    });

    return checks;
  },

  getComplianceLevel(score: number): string {
    if (score >= 0.95) return 'excellent';
    if (score >= 0.85) return 'good';
    if (score >= 0.7) return 'acceptable';
    if (score >= 0.5) return 'needs_improvement';
    return 'critical';
  },

  generateComplianceRecommendations(violations: any): string[] {
    const recommendations = [];

    Object.keys(violations).forEach(category => {
      const categoryViolations = violations[category];
      const criticalCount = categoryViolations.filter(v => v.severity === 'critical').length;
      const highCount = categoryViolations.filter(v => v.severity === 'high').length;

      if (criticalCount > 0) {
        recommendations.push(`Address ${criticalCount} critical ${category} violations immediately`);
      }

      if (highCount > 0) {
        recommendations.push(`Review ${highCount} high-severity ${category} issues`);
      }
    });

    if (violations.security) {
      recommendations.push('Implement additional security controls for critical step execution');
    }

    if (violations.operational) {
      recommendations.push('Optimize operational procedures to improve compliance scores');
    }

    if (recommendations.length === 0) {
      recommendations.push('All compliance checks passed - maintain current security posture');
    }

    return recommendations;
  }
};

export const risk_assessment = {
  name: 'risk_assessment',
  description: 'Assess operational and security risks in plan execution',
  inputSchema: {
    type: 'object',
    properties: {
      plan_id: { type: 'string', description: 'Plan ID to assess (optional)' },
      risk_categories: { type: 'array', items: { type: 'string' }, default: ['security', 'operational', 'financial'], description: 'Risk categories to analyze' },
      include_mitigation: { type: 'boolean', default: true, description: 'Include mitigation recommendations' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      logger.info(`Conducting risk assessment for plan: ${input.plan_id || 'all'}`);

      const risks = [];

      // Analyze different risk categories
      for (const category of input.risk_categories || ['security', 'operational', 'financial']) {
        switch (category) {
          case 'security':
            risks.push(...this.assessSecurityRisks(input, db));
            break;
          case 'operational':
            risks.push(...this.assessOperationalRisks(input, db));
            break;
          case 'financial':
            risks.push(...this.assessFinancialRisks(input, db));
            break;
        }
      }

      // Calculate overall risk score
      const riskScore = this.calculateRiskScore(risks);

      // Generate mitigation recommendations
      let mitigations = [];
      if (input.include_mitigation) {
        mitigations = this.generateMitigationRecommendations(risks);
      }

      // Log risk assessment
      db.event('audit', 'risk_assessed', {
        plan_id: input.plan_id,
        categories: input.risk_categories,
        risk_score: riskScore,
        high_risks: risks.filter(r => r.severity === 'high').length
      });

      const result = {
        plan_id: input.plan_id,
        assessment_scope: input.risk_categories,
        overall_risk_score: riskScore,
        risk_level: this.getRiskLevel(riskScore),
        identified_risks: risks,
        risk_summary: this.summarizeRisks(risks),
        mitigation_recommendations: mitigations,
        assessed_at: now()
      };

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      logger.error('Risk assessment failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  },

  assessSecurityRisks(input: any, db: any): any[] {
    const risks = [];

    // Critical steps without attestations
    let query = `
      SELECT COUNT(*) as unattested FROM steps s
      LEFT JOIN tickets t ON s.id = t.step_id
      LEFT JOIN attestations a ON t.id = a.ticket_id
      WHERE s.critical = 1 AND a.id IS NULL
    `;
    let params = [];

    if (input.plan_id) {
      query += ' AND s.plan_id = ?';
      params.push(input.plan_id);
    }

    const unattested = db.get(query, ...params);

    if (unattested.unattested > 0) {
      risks.push({
        id: 'RISK-SEC-001',
        category: 'security',
        title: 'Unattested Critical Steps',
        description: 'Critical steps executed without proper attestation',
        severity: 'high',
        probability: 0.8,
        impact: 0.9,
        details: {
          unattested_critical_steps: unattested.unattested
        }
      });
    }

    // Routes with poor reliability
    query = `
      SELECT COUNT(*) as unreliable FROM routes r
      JOIN learning l ON r.id = l.route_id
      WHERE l.total_count > 10 AND (l.success_count * 1.0 / l.total_count) < 0.8
    `;

    const unreliableRoutes = db.get(query);

    if (unreliableRoutes.unreliable > 0) {
      risks.push({
        id: 'RISK-SEC-002',
        category: 'security',
        title: 'Unreliable Route Usage',
        description: 'Routes with poor success rates pose execution risks',
        severity: 'medium',
        probability: 0.6,
        impact: 0.7,
        details: {
          unreliable_routes: unreliableRoutes.unreliable
        }
      });
    }

    return risks;
  },

  assessOperationalRisks(input: any, db: any): any[] {
    const risks = [];

    // Single points of failure
    let query = `
      SELECT capability, COUNT(*) as route_count
      FROM routes
      WHERE healthy = 1
      GROUP BY capability
      HAVING COUNT(*) = 1
    `;

    const spofCapabilities = db.all(query) as any[];

    if (spofCapabilities.length > 0) {
      risks.push({
        id: 'RISK-OPS-001',
        category: 'operational',
        title: 'Single Points of Failure',
        description: 'Capabilities with only one healthy route',
        severity: 'high',
        probability: 0.3,
        impact: 0.8,
        details: {
          vulnerable_capabilities: spofCapabilities.map(c => c.capability),
          count: spofCapabilities.length
        }
      });
    }

    // High latency executions
    query = `
      SELECT AVG(latency_ms) as avg_latency
      FROM tickets
      WHERE status = 'completed'
    `;
    let params = [];

    if (input.plan_id) {
      query += ` AND step_id IN (
        SELECT id FROM steps WHERE plan_id = ?
      )`;
      params.push(input.plan_id);
    }

    const latencyData = db.get(query, ...params);

    if (latencyData.avg_latency > 20000) {
      risks.push({
        id: 'RISK-OPS-002',
        category: 'operational',
        title: 'Performance Degradation',
        description: 'Average execution time exceeds acceptable thresholds',
        severity: latencyData.avg_latency > 45000 ? 'high' : 'medium',
        probability: 0.7,
        impact: 0.5,
        details: {
          avg_latency_ms: latencyData.avg_latency,
          threshold_ms: 20000
        }
      });
    }

    return risks;
  },

  assessFinancialRisks(input: any, db: any): any[] {
    const risks = [];

    // High cost executions
    let query = `
      SELECT SUM(cost) as total_cost, AVG(cost) as avg_cost, COUNT(*) as executions
      FROM tickets
      WHERE status = 'completed'
    `;
    let params = [];

    if (input.plan_id) {
      query += ` AND step_id IN (
        SELECT id FROM steps WHERE plan_id = ?
      )`;
      params.push(input.plan_id);
    }

    const costData = db.get(query, ...params);

    if (costData.avg_cost > 8.0) {
      risks.push({
        id: 'RISK-FIN-001',
        category: 'financial',
        title: 'High Execution Costs',
        description: 'Average execution cost exceeds budget thresholds',
        severity: costData.avg_cost > 15.0 ? 'high' : 'medium',
        probability: 0.9,
        impact: 0.6,
        details: {
          avg_cost: costData.avg_cost,
          total_cost: costData.total_cost,
          executions: costData.executions
        }
      });
    }

    // Cost trend analysis
    if (costData.total_cost > 100) {
      risks.push({
        id: 'RISK-FIN-002',
        category: 'financial',
        title: 'Budget Overrun Risk',
        description: 'Total execution costs approaching budget limits',
        severity: 'medium',
        probability: 0.5,
        impact: 0.7,
        details: {
          total_cost: costData.total_cost,
          estimated_budget_limit: 100
        }
      });
    }

    return risks;
  },

  calculateRiskScore(risks: any[]): number {
    if (risks.length === 0) return 0;

    const totalRisk = risks.reduce((sum, risk) => {
      return sum + (risk.probability * risk.impact);
    }, 0);

    return Math.min(1.0, totalRisk / risks.length);
  },

  getRiskLevel(score: number): string {
    if (score >= 0.8) return 'critical';
    if (score >= 0.6) return 'high';
    if (score >= 0.4) return 'medium';
    if (score >= 0.2) return 'low';
    return 'minimal';
  },

  summarizeRisks(risks: any[]): any {
    const summary = {
      total_risks: risks.length,
      by_severity: {},
      by_category: {},
      top_risks: risks.sort((a, b) => (b.probability * b.impact) - (a.probability * a.impact)).slice(0, 3)
    };

    risks.forEach(risk => {
      // Count by severity
      summary.by_severity[risk.severity] = (summary.by_severity[risk.severity] || 0) + 1;

      // Count by category
      summary.by_category[risk.category] = (summary.by_category[risk.category] || 0) + 1;
    });

    return summary;
  },

  generateMitigationRecommendations(risks: any[]): string[] {
    const recommendations = new Set();

    risks.forEach(risk => {
      switch (risk.category) {
        case 'security':
          if (risk.id === 'RISK-SEC-001') {
            recommendations.add('Implement mandatory attestation for all critical steps');
          }
          if (risk.id === 'RISK-SEC-002') {
            recommendations.add('Establish route health monitoring and automatic failover');
          }
          break;

        case 'operational':
          if (risk.id === 'RISK-OPS-001') {
            recommendations.add('Register additional MCPs to eliminate single points of failure');
          }
          if (risk.id === 'RISK-OPS-002') {
            recommendations.add('Optimize route selection and implement caching strategies');
          }
          break;

        case 'financial':
          if (risk.id === 'RISK-FIN-001') {
            recommendations.add('Review and optimize expensive execution paths');
          }
          if (risk.id === 'RISK-FIN-002') {
            recommendations.add('Implement budget monitoring and cost controls');
          }
          break;
      }
    });

    return Array.from(recommendations);
  }
};