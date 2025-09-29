#!/usr/bin/env python3
"""
Codex CLI MCP Server: Test Engineer
Provides comprehensive testing strategies, frameworks, and quality assurance processes.
"""

import asyncio
import json
import sys
import logging
import os
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

# Configure logging to stderr to avoid interfering with JSON-RPC
logging.basicConfig(level=logging.DEBUG, stream=sys.stderr,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestingStrategy(Enum):
    TDD = "test_driven_development"
    BDD = "behavior_driven_development"
    ATDD = "acceptance_test_driven_development"
    EXPLORATORY = "exploratory_testing"
    RISK_BASED = "risk_based_testing"
    MODEL_BASED = "model_based_testing"

class QualityGate(Enum):
    CODE_COVERAGE = "code_coverage"
    MUTATION_SCORE = "mutation_score"
    COMPLEXITY_THRESHOLD = "complexity_threshold"
    PERFORMANCE_BENCHMARK = "performance_benchmark"
    SECURITY_SCAN = "security_scan"
    ACCESSIBILITY = "accessibility"

@dataclass
class TestingFramework:
    """Testing framework configuration"""
    name: str
    language: str
    test_types: List[str]
    features: List[str]
    setup_complexity: str
    learning_curve: str
    ecosystem: str

@dataclass
class TestStrategy:
    """Test strategy definition"""
    name: str
    strategy_type: TestingStrategy
    scope: str
    objectives: List[str]
    phases: List[str]
    tools: List[str]
    metrics: List[str]
    timeline: str

@dataclass
class QualityAssurance:
    """Quality assurance process"""
    gates: List[QualityGate]
    thresholds: Dict[str, float]
    automation_level: str
    review_process: Dict[str, Any]
    reporting: Dict[str, Any]

class TestEngineer:
    """Testing strategies and frameworks specialist"""

    def __init__(self):
        self.testing_frameworks = {
            'python': {
                'pytest': TestingFramework(
                    name='pytest',
                    language='python',
                    test_types=['unit', 'integration', 'functional'],
                    features=['fixtures', 'parametrization', 'plugins', 'mocking'],
                    setup_complexity='low',
                    learning_curve='gentle',
                    ecosystem='extensive'
                ),
                'unittest': TestingFramework(
                    name='unittest',
                    language='python',
                    test_types=['unit', 'integration'],
                    features=['test_discovery', 'mocking', 'assertions'],
                    setup_complexity='minimal',
                    learning_curve='easy',
                    ecosystem='standard_library'
                ),
                'nose2': TestingFramework(
                    name='nose2',
                    language='python',
                    test_types=['unit', 'integration'],
                    features=['test_discovery', 'plugins'],
                    setup_complexity='low',
                    learning_curve='moderate',
                    ecosystem='limited'
                )
            },
            'javascript': {
                'jest': TestingFramework(
                    name='jest',
                    language='javascript',
                    test_types=['unit', 'integration', 'snapshot'],
                    features=['mocking', 'coverage', 'snapshot_testing', 'parallel'],
                    setup_complexity='low',
                    learning_curve='gentle',
                    ecosystem='extensive'
                ),
                'mocha': TestingFramework(
                    name='mocha',
                    language='javascript',
                    test_types=['unit', 'integration', 'e2e'],
                    features=['flexible', 'async_support', 'custom_reporters'],
                    setup_complexity='moderate',
                    learning_curve='moderate',
                    ecosystem='extensive'
                ),
                'jasmine': TestingFramework(
                    name='jasmine',
                    language='javascript',
                    test_types=['unit', 'integration'],
                    features=['bdd_style', 'spies', 'async_support'],
                    setup_complexity='low',
                    learning_curve='easy',
                    ecosystem='good'
                )
            },
            'java': {
                'junit5': TestingFramework(
                    name='junit5',
                    language='java',
                    test_types=['unit', 'integration', 'parametrized'],
                    features=['annotations', 'extensions', 'dynamic_tests'],
                    setup_complexity='moderate',
                    learning_curve='moderate',
                    ecosystem='extensive'
                ),
                'testng': TestingFramework(
                    name='testng',
                    language='java',
                    test_types=['unit', 'integration', 'functional'],
                    features=['data_providers', 'parallel', 'dependencies'],
                    setup_complexity='moderate',
                    learning_curve='steep',
                    ecosystem='good'
                )
            }
        }

        self.test_pyramid_levels = {
            'unit': {
                'percentage': 70,
                'characteristics': ['fast', 'isolated', 'deterministic'],
                'tools': ['pytest', 'jest', 'junit'],
                'focus': 'individual_components'
            },
            'integration': {
                'percentage': 20,
                'characteristics': ['moderate_speed', 'component_interaction'],
                'tools': ['pytest', 'postman', 'rest_assured'],
                'focus': 'component_interfaces'
            },
            'e2e': {
                'percentage': 10,
                'characteristics': ['slow', 'realistic', 'brittle'],
                'tools': ['cypress', 'selenium', 'playwright'],
                'focus': 'user_workflows'
            }
        }

        self.quality_metrics = {
            'coverage': {
                'line_coverage': {'threshold': 80, 'excellent': 95},
                'branch_coverage': {'threshold': 75, 'excellent': 90},
                'function_coverage': {'threshold': 85, 'excellent': 98}
            },
            'complexity': {
                'cyclomatic_complexity': {'threshold': 10, 'excellent': 5},
                'cognitive_complexity': {'threshold': 15, 'excellent': 8}
            },
            'maintainability': {
                'maintainability_index': {'threshold': 70, 'excellent': 85},
                'technical_debt_ratio': {'threshold': 5, 'excellent': 2}
            }
        }

    async def recommend_testing_strategy(self, project_info: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend testing strategy based on project characteristics"""
        try:
            project_type = project_info.get('type', 'web_application')
            team_size = project_info.get('team_size', 5)
            timeline = project_info.get('timeline', 'moderate')
            risk_level = project_info.get('risk_level', 'medium')
            existing_tests = project_info.get('existing_tests', False)

            recommendation = {
                'primary_strategy': None,
                'secondary_strategies': [],
                'test_pyramid': self.test_pyramid_levels,
                'frameworks': {},
                'quality_gates': [],
                'implementation_plan': {},
                'estimated_effort': '',
                'success_metrics': []
            }

            # Recommend primary strategy based on project characteristics
            if risk_level == 'high' or project_type in ['financial', 'healthcare', 'safety_critical']:
                recommendation['primary_strategy'] = TestingStrategy.RISK_BASED.value
                recommendation['secondary_strategies'] = [TestingStrategy.TDD.value]
            elif team_size <= 3 and timeline == 'tight':
                recommendation['primary_strategy'] = TestingStrategy.TDD.value
                recommendation['secondary_strategies'] = [TestingStrategy.EXPLORATORY.value]
            elif project_type in ['api', 'microservices']:
                recommendation['primary_strategy'] = TestingStrategy.BDD.value
                recommendation['secondary_strategies'] = [TestingStrategy.TDD.value]
            else:
                recommendation['primary_strategy'] = TestingStrategy.BDD.value
                recommendation['secondary_strategies'] = [TestingStrategy.EXPLORATORY.value]

            # Recommend frameworks based on technology stack
            tech_stack = project_info.get('tech_stack', [])
            recommendation['frameworks'] = await self._recommend_frameworks(tech_stack)

            # Set up quality gates
            recommendation['quality_gates'] = await self._setup_quality_gates(project_info)

            # Create implementation plan
            recommendation['implementation_plan'] = await self._create_implementation_plan(
                recommendation['primary_strategy'], existing_tests, team_size
            )

            # Calculate effort estimation
            recommendation['estimated_effort'] = self._estimate_implementation_effort(
                team_size, existing_tests, len(tech_stack)
            )

            # Define success metrics
            recommendation['success_metrics'] = self._define_success_metrics(project_type, risk_level)

            return recommendation

        except Exception as e:
            logger.error(f"Error recommending testing strategy: {e}")
            return {'error': str(e)}

    async def design_test_architecture(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Design comprehensive test architecture"""
        try:
            architecture = {
                'layers': {},
                'test_data_strategy': {},
                'environment_strategy': {},
                'ci_cd_integration': {},
                'reporting_strategy': {},
                'maintenance_strategy': {}
            }

            # Design test layers
            architecture['layers'] = {
                'unit_tests': {
                    'purpose': 'Test individual components in isolation',
                    'tools': requirements.get('unit_framework', 'pytest'),
                    'coverage_target': 85,
                    'execution_time': '< 5 minutes',
                    'structure': 'tests/unit/'
                },
                'integration_tests': {
                    'purpose': 'Test component interactions',
                    'tools': requirements.get('integration_framework', 'pytest'),
                    'coverage_target': 70,
                    'execution_time': '< 15 minutes',
                    'structure': 'tests/integration/'
                },
                'e2e_tests': {
                    'purpose': 'Test complete user workflows',
                    'tools': requirements.get('e2e_framework', 'cypress'),
                    'coverage_target': 'critical_paths',
                    'execution_time': '< 30 minutes',
                    'structure': 'tests/e2e/'
                },
                'performance_tests': {
                    'purpose': 'Validate performance requirements',
                    'tools': requirements.get('perf_framework', 'locust'),
                    'coverage_target': 'key_scenarios',
                    'execution_time': '< 60 minutes',
                    'structure': 'tests/performance/'
                }
            }

            # Design test data strategy
            architecture['test_data_strategy'] = {
                'generation': 'factory_pattern',
                'management': 'fixtures_and_builders',
                'isolation': 'database_transactions',
                'cleanup': 'automatic_rollback',
                'sensitive_data': 'anonymization'
            }

            # Design environment strategy
            architecture['environment_strategy'] = {
                'local': 'docker_compose',
                'ci': 'containerized_services',
                'staging': 'production_like',
                'production': 'synthetic_monitoring'
            }

            # CI/CD integration
            architecture['ci_cd_integration'] = {
                'trigger_points': ['pull_request', 'merge_to_main', 'nightly'],
                'parallel_execution': True,
                'test_selection': 'impact_analysis',
                'failure_handling': 'fast_feedback',
                'deployment_gates': ['unit_tests', 'integration_tests', 'security_scan']
            }

            # Reporting strategy
            architecture['reporting_strategy'] = {
                'coverage_reports': 'html_and_json',
                'test_results': 'junit_xml',
                'trend_analysis': 'historical_tracking',
                'notifications': 'slack_and_email',
                'dashboards': 'real_time_metrics'
            }

            # Maintenance strategy
            architecture['maintenance_strategy'] = {
                'test_review': 'weekly_review_sessions',
                'obsolete_cleanup': 'automated_detection',
                'performance_monitoring': 'execution_time_tracking',
                'framework_updates': 'quarterly_assessment'
            }

            return architecture

        except Exception as e:
            logger.error(f"Error designing test architecture: {e}")
            return {'error': str(e)}

    async def create_quality_gates(self, project_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Create comprehensive quality gates"""
        try:
            quality_gates = {
                'gates': [],
                'thresholds': {},
                'automation': {},
                'escalation': {},
                'reporting': {}
            }

            project_type = project_requirements.get('type', 'web_application')
            compliance_requirements = project_requirements.get('compliance', [])

            # Define quality gates based on project type
            if project_type in ['financial', 'healthcare']:
                gates = [
                    QualityGate.CODE_COVERAGE,
                    QualityGate.MUTATION_SCORE,
                    QualityGate.SECURITY_SCAN,
                    QualityGate.PERFORMANCE_BENCHMARK,
                    QualityGate.COMPLEXITY_THRESHOLD
                ]
            elif project_type == 'web_application':
                gates = [
                    QualityGate.CODE_COVERAGE,
                    QualityGate.SECURITY_SCAN,
                    QualityGate.ACCESSIBILITY,
                    QualityGate.PERFORMANCE_BENCHMARK
                ]
            else:
                gates = [
                    QualityGate.CODE_COVERAGE,
                    QualityGate.COMPLEXITY_THRESHOLD,
                    QualityGate.SECURITY_SCAN
                ]

            quality_gates['gates'] = [gate.value for gate in gates]

            # Set thresholds
            quality_gates['thresholds'] = {
                'code_coverage': {
                    'minimum': 80,
                    'target': 90,
                    'measurement': 'line_coverage'
                },
                'mutation_score': {
                    'minimum': 70,
                    'target': 85,
                    'measurement': 'mutation_testing'
                },
                'complexity_threshold': {
                    'maximum': 10,
                    'target': 5,
                    'measurement': 'cyclomatic_complexity'
                },
                'performance_benchmark': {
                    'response_time': '< 200ms',
                    'throughput': '> 1000 rps',
                    'error_rate': '< 0.1%'
                },
                'security_scan': {
                    'critical_vulnerabilities': 0,
                    'high_vulnerabilities': 0,
                    'medium_vulnerabilities': '< 5'
                },
                'accessibility': {
                    'wcag_level': 'AA',
                    'automated_score': '> 95%',
                    'manual_review': 'required'
                }
            }

            # Automation configuration
            quality_gates['automation'] = {
                'ci_integration': True,
                'automated_blocking': True,
                'manual_override': 'team_lead_approval',
                'notification_channels': ['slack', 'email'],
                'escalation_timeout': '2_hours'
            }

            return quality_gates

        except Exception as e:
            logger.error(f"Error creating quality gates: {e}")
            return {'error': str(e)}

    async def generate_test_plan(self, project_scope: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive test plan"""
        try:
            test_plan = {
                'project_overview': {},
                'test_objectives': [],
                'test_strategy': {},
                'test_scope': {},
                'test_schedule': {},
                'test_deliverables': [],
                'risk_assessment': {},
                'resource_planning': {},
                'success_criteria': {}
            }

            # Project overview
            test_plan['project_overview'] = {
                'name': project_scope.get('name', 'Project'),
                'description': project_scope.get('description', ''),
                'stakeholders': project_scope.get('stakeholders', []),
                'timeline': project_scope.get('timeline', 'TBD')
            }

            # Test objectives
            test_plan['test_objectives'] = [
                'Verify functional requirements are met',
                'Ensure system performance meets requirements',
                'Validate security controls are effective',
                'Confirm user experience is acceptable',
                'Ensure system reliability and stability'
            ]

            # Test strategy
            features = project_scope.get('features', [])
            test_plan['test_strategy'] = {
                'approach': 'risk_based_testing',
                'test_levels': ['unit', 'integration', 'system', 'acceptance'],
                'test_types': ['functional', 'performance', 'security', 'usability'],
                'automation_strategy': f"{self._calculate_automation_percentage(features)}% automated",
                'tools': await self._select_testing_tools(project_scope)
            }

            # Test scope
            test_plan['test_scope'] = {
                'in_scope': features,
                'out_of_scope': project_scope.get('exclusions', []),
                'assumptions': project_scope.get('assumptions', []),
                'constraints': project_scope.get('constraints', [])
            }

            # Test schedule
            test_plan['test_schedule'] = await self._create_test_schedule(project_scope)

            # Test deliverables
            test_plan['test_deliverables'] = [
                'Test strategy document',
                'Test cases and scripts',
                'Test data sets',
                'Automated test suites',
                'Test execution reports',
                'Defect reports',
                'Test completion report'
            ]

            # Risk assessment
            test_plan['risk_assessment'] = await self._assess_testing_risks(project_scope)

            # Resource planning
            test_plan['resource_planning'] = await self._plan_testing_resources(project_scope)

            # Success criteria
            test_plan['success_criteria'] = {
                'functional': 'All critical and high priority test cases pass',
                'performance': 'System meets performance requirements',
                'security': 'No critical or high security vulnerabilities',
                'coverage': 'Minimum 85% code coverage achieved',
                'defects': 'No open critical or high priority defects'
            }

            return test_plan

        except Exception as e:
            logger.error(f"Error generating test plan: {e}")
            return {'error': str(e)}

    async def analyze_test_metrics(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze test execution metrics and provide insights"""
        try:
            analysis = {
                'coverage_analysis': {},
                'performance_trends': {},
                'quality_trends': {},
                'risk_indicators': [],
                'recommendations': [],
                'action_items': []
            }

            # Coverage analysis
            coverage_data = test_data.get('coverage', {})
            analysis['coverage_analysis'] = {
                'current_coverage': coverage_data.get('line_coverage', 0),
                'trend': self._calculate_coverage_trend(test_data.get('historical_coverage', [])),
                'gaps': await self._identify_coverage_gaps(coverage_data),
                'target_met': coverage_data.get('line_coverage', 0) >= 85
            }

            # Performance trends
            execution_data = test_data.get('execution_times', [])
            analysis['performance_trends'] = {
                'average_execution_time': self._calculate_average(execution_data),
                'trend': self._calculate_performance_trend(execution_data),
                'slow_tests': await self._identify_slow_tests(test_data.get('test_results', [])),
                'optimization_opportunities': await self._find_optimization_opportunities(execution_data)
            }

            # Quality trends
            defect_data = test_data.get('defects', [])
            analysis['quality_trends'] = {
                'defect_density': len(defect_data) / max(test_data.get('total_tests', 1), 1),
                'defect_trend': self._calculate_defect_trend(defect_data),
                'severity_distribution': self._analyze_severity_distribution(defect_data),
                'escape_rate': self._calculate_defect_escape_rate(defect_data)
            }

            # Risk indicators
            analysis['risk_indicators'] = await self._identify_risk_indicators(test_data)

            # Recommendations
            analysis['recommendations'] = await self._generate_test_recommendations(analysis)

            # Action items
            analysis['action_items'] = await self._create_action_items(analysis)

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing test metrics: {e}")
            return {'error': str(e)}

    async def _recommend_frameworks(self, tech_stack: List[str]) -> Dict[str, Any]:
        """Recommend testing frameworks based on technology stack"""
        recommendations = {}

        for tech in tech_stack:
            if tech.lower() in ['python', 'django', 'flask', 'fastapi']:
                recommendations['python'] = {
                    'primary': 'pytest',
                    'alternatives': ['unittest', 'nose2'],
                    'reasoning': 'Pytest offers the best balance of features and ease of use'
                }
            elif tech.lower() in ['javascript', 'node.js', 'react', 'vue', 'angular']:
                recommendations['javascript'] = {
                    'primary': 'jest',
                    'alternatives': ['mocha', 'jasmine'],
                    'reasoning': 'Jest provides excellent built-in features and zero configuration'
                }
            elif tech.lower() in ['java', 'spring', 'springboot']:
                recommendations['java'] = {
                    'primary': 'junit5',
                    'alternatives': ['testng'],
                    'reasoning': 'JUnit 5 is the modern standard with excellent ecosystem support'
                }

        return recommendations

    async def _setup_quality_gates(self, project_info: Dict[str, Any]) -> List[str]:
        """Setup appropriate quality gates for the project"""
        gates = []

        # Always include basic gates
        gates.extend(['code_coverage', 'complexity_threshold'])

        # Add security gate for sensitive projects
        if project_info.get('risk_level') in ['high', 'critical']:
            gates.append('security_scan')

        # Add performance gate for user-facing applications
        if project_info.get('type') in ['web_application', 'mobile_app']:
            gates.append('performance_benchmark')

        # Add accessibility gate for public-facing applications
        if project_info.get('public_facing', False):
            gates.append('accessibility')

        return gates

    async def _create_implementation_plan(self, strategy: str, existing_tests: bool, team_size: int) -> Dict[str, Any]:
        """Create implementation plan based on strategy and constraints"""
        plan = {
            'phases': [],
            'timeline': '',
            'resources': [],
            'dependencies': []
        }

        if strategy == TestingStrategy.TDD.value:
            plan['phases'] = [
                'Setup testing framework and CI integration',
                'Train team on TDD practices',
                'Implement test-first development workflow',
                'Establish quality gates and metrics',
                'Continuous improvement and refinement'
            ]
            plan['timeline'] = '4-6 weeks'
        elif strategy == TestingStrategy.BDD.value:
            plan['phases'] = [
                'Define user stories and acceptance criteria',
                'Setup BDD framework (Cucumber/Gherkin)',
                'Create feature files and step definitions',
                'Implement automation layer',
                'Integrate with CI/CD pipeline'
            ]
            plan['timeline'] = '6-8 weeks'

        # Adjust timeline based on team size
        if team_size <= 2:
            plan['timeline'] = self._extend_timeline(plan['timeline'], 1.5)
        elif team_size >= 10:
            plan['timeline'] = self._reduce_timeline(plan['timeline'], 0.8)

        return plan

    def _estimate_implementation_effort(self, team_size: int, existing_tests: bool, tech_complexity: int) -> str:
        """Estimate implementation effort in person-weeks"""
        base_effort = 4  # weeks

        # Adjust for team size
        if team_size <= 2:
            base_effort *= 1.5
        elif team_size >= 8:
            base_effort *= 0.7

        # Adjust for existing tests
        if existing_tests:
            base_effort *= 0.6

        # Adjust for technology complexity
        base_effort += tech_complexity * 0.5

        return f"{base_effort:.1f} person-weeks"

    def _define_success_metrics(self, project_type: str, risk_level: str) -> List[str]:
        """Define success metrics based on project characteristics"""
        metrics = [
            'Test coverage > 85%',
            'All critical tests passing',
            'Test execution time < 15 minutes'
        ]

        if risk_level in ['high', 'critical']:
            metrics.extend([
                'Mutation score > 80%',
                'Zero critical security vulnerabilities',
                'Performance benchmarks met'
            ])

        if project_type == 'web_application':
            metrics.append('Accessibility compliance (WCAG AA)')

        return metrics

    async def _select_testing_tools(self, project_scope: Dict[str, Any]) -> Dict[str, str]:
        """Select appropriate testing tools"""
        tools = {}

        tech_stack = project_scope.get('tech_stack', [])

        if 'python' in tech_stack:
            tools['unit'] = 'pytest'
            tools['integration'] = 'pytest'

        if any(js_tech in tech_stack for js_tech in ['javascript', 'react', 'vue']):
            tools['frontend'] = 'jest'
            tools['e2e'] = 'cypress'

        tools['api'] = 'postman'
        tools['performance'] = 'locust'
        tools['security'] = 'bandit'

        return tools

    async def _create_test_schedule(self, project_scope: Dict[str, Any]) -> Dict[str, str]:
        """Create test execution schedule"""
        timeline = project_scope.get('timeline', 'moderate')

        if timeline == 'aggressive':
            return {
                'test_planning': '1 week',
                'test_implementation': '2 weeks',
                'test_execution': '1 week',
                'bug_fixing': '1 week'
            }
        else:
            return {
                'test_planning': '2 weeks',
                'test_implementation': '4 weeks',
                'test_execution': '2 weeks',
                'bug_fixing': '2 weeks'
            }

    async def _assess_testing_risks(self, project_scope: Dict[str, Any]) -> Dict[str, Any]:
        """Assess testing-related risks"""
        return {
            'high_risks': [
                'Incomplete requirements leading to test gaps',
                'Limited test environment availability',
                'Team inexperience with testing tools'
            ],
            'medium_risks': [
                'Test data management complexity',
                'Integration testing dependencies',
                'Performance testing environment setup'
            ],
            'mitigation_strategies': [
                'Early stakeholder engagement for requirements clarity',
                'Containerized test environments',
                'Team training and knowledge sharing sessions'
            ]
        }

    async def _plan_testing_resources(self, project_scope: Dict[str, Any]) -> Dict[str, Any]:
        """Plan testing resource requirements"""
        team_size = project_scope.get('team_size', 5)

        return {
            'human_resources': {
                'test_engineer': 1,
                'automation_engineer': 1 if team_size > 3 else 0,
                'performance_tester': 1 if 'performance' in project_scope.get('requirements', []) else 0
            },
            'infrastructure': {
                'test_environments': 3,
                'ci_cd_pipeline': 'required',
                'test_data_management': 'required'
            },
            'tools_and_licenses': {
                'testing_framework': 'open_source',
                'test_management': 'required',
                'performance_testing': 'conditional'
            }
        }

    def _calculate_automation_percentage(self, features: List[str]) -> int:
        """Calculate recommended automation percentage"""
        base_percentage = 70

        # Increase automation for API-heavy projects
        if any('api' in feature.lower() for feature in features):
            base_percentage += 10

        # Increase automation for complex business logic
        if len(features) > 10:
            base_percentage += 5

        return min(base_percentage, 90)

    def _calculate_coverage_trend(self, historical_data: List[float]) -> str:
        """Calculate coverage trend from historical data"""
        if len(historical_data) < 2:
            return 'insufficient_data'

        recent_avg = sum(historical_data[-3:]) / min(len(historical_data), 3)
        older_avg = sum(historical_data[:-3]) / max(len(historical_data) - 3, 1)

        if recent_avg > older_avg + 2:
            return 'improving'
        elif recent_avg < older_avg - 2:
            return 'declining'
        else:
            return 'stable'

    async def _identify_coverage_gaps(self, coverage_data: Dict[str, Any]) -> List[str]:
        """Identify areas with insufficient test coverage"""
        gaps = []

        file_coverage = coverage_data.get('files', {})
        for file_path, coverage in file_coverage.items():
            if coverage < 70:
                gaps.append(f"{file_path}: {coverage}% coverage")

        return gaps

    def _calculate_average(self, data: List[float]) -> float:
        """Calculate average from list of numbers"""
        if not data:
            return 0.0
        return sum(data) / len(data)

    def _calculate_performance_trend(self, execution_times: List[float]) -> str:
        """Calculate performance trend"""
        if len(execution_times) < 5:
            return 'insufficient_data'

        recent_avg = sum(execution_times[-5:]) / 5
        older_avg = sum(execution_times[:-5]) / max(len(execution_times) - 5, 1)

        if recent_avg > older_avg * 1.1:
            return 'degrading'
        elif recent_avg < older_avg * 0.9:
            return 'improving'
        else:
            return 'stable'

    async def _identify_slow_tests(self, test_results: List[Dict[str, Any]]) -> List[str]:
        """Identify tests that run slower than expected"""
        slow_tests = []

        for test in test_results:
            execution_time = test.get('duration', 0)
            if execution_time > 30:  # seconds
                slow_tests.append(f"{test.get('name', 'unknown')}: {execution_time}s")

        return slow_tests

    async def _find_optimization_opportunities(self, execution_data: List[float]) -> List[str]:
        """Find opportunities to optimize test execution"""
        opportunities = []

        avg_time = self._calculate_average(execution_data)

        if avg_time > 300:  # 5 minutes
            opportunities.append('Consider parallel test execution')

        if avg_time > 600:  # 10 minutes
            opportunities.append('Review test suite for redundant tests')
            opportunities.append('Implement test categorization and selective execution')

        return opportunities

    def _analyze_severity_distribution(self, defects: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze distribution of defect severities"""
        distribution = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}

        for defect in defects:
            severity = defect.get('severity', 'low').lower()
            if severity in distribution:
                distribution[severity] += 1

        return distribution

    def _calculate_defect_trend(self, defects: List[Dict[str, Any]]) -> str:
        """Calculate defect discovery trend"""
        if len(defects) < 5:
            return 'insufficient_data'

        # Group defects by week (simplified)
        recent_defects = len([d for d in defects[-10:]])
        older_defects = len([d for d in defects[:-10]])

        if recent_defects > older_defects * 1.2:
            return 'increasing'
        elif recent_defects < older_defects * 0.8:
            return 'decreasing'
        else:
            return 'stable'

    def _calculate_defect_escape_rate(self, defects: List[Dict[str, Any]]) -> float:
        """Calculate rate of defects escaping to production"""
        total_defects = len(defects)
        production_defects = len([d for d in defects if d.get('found_in') == 'production'])

        if total_defects == 0:
            return 0.0

        return (production_defects / total_defects) * 100

    async def _identify_risk_indicators(self, test_data: Dict[str, Any]) -> List[str]:
        """Identify risk indicators from test data"""
        risks = []

        coverage = test_data.get('coverage', {}).get('line_coverage', 0)
        if coverage < 70:
            risks.append('Low test coverage increases defect risk')

        execution_times = test_data.get('execution_times', [])
        if execution_times and self._calculate_average(execution_times) > 900:
            risks.append('Long test execution time may reduce testing frequency')

        defects = test_data.get('defects', [])
        critical_defects = len([d for d in defects if d.get('severity') == 'critical'])
        if critical_defects > 0:
            risks.append(f'{critical_defects} critical defects indicate quality issues')

        return risks

    async def _generate_test_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []

        coverage = analysis.get('coverage_analysis', {})
        if not coverage.get('target_met', False):
            recommendations.append('Increase test coverage to meet 85% target')

        performance = analysis.get('performance_trends', {})
        if performance.get('trend') == 'degrading':
            recommendations.append('Optimize test execution performance')

        quality = analysis.get('quality_trends', {})
        if quality.get('escape_rate', 0) > 5:
            recommendations.append('Improve test coverage for critical paths')

        return recommendations

    async def _create_action_items(self, analysis: Dict[str, Any]) -> List[Dict[str, str]]:
        """Create actionable items based on analysis"""
        action_items = []

        risks = analysis.get('risk_indicators', [])
        for risk in risks:
            if 'coverage' in risk.lower():
                action_items.append({
                    'priority': 'high',
                    'action': 'Identify and test uncovered code paths',
                    'owner': 'development_team',
                    'timeline': '2_weeks'
                })

        return action_items

    def _extend_timeline(self, timeline: str, factor: float) -> str:
        """Extend timeline by given factor"""
        # Simple implementation - would need more sophisticated parsing
        return timeline.replace('4-6 weeks', f'{int(4*factor)}-{int(6*factor)} weeks')

    def _reduce_timeline(self, timeline: str, factor: float) -> str:
        """Reduce timeline by given factor"""
        # Simple implementation - would need more sophisticated parsing
        return timeline.replace('4-6 weeks', f'{int(4*factor)}-{int(6*factor)} weeks')

class MCPServer:
    """MCP Server for Test Engineer"""

    def __init__(self):
        self.test_engineer = TestEngineer()

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP requests"""
        try:
            method = request.get('method')
            params = request.get('params', {})

            if method == 'initialize':
                return {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "test-engineer", "version": "1.0.0"}
                }
            elif method == 'tools/list':
                return {
                    "tools": [
                        {
                            "name": "recommend_testing_strategy",
                            "description": "Recommend testing strategy based on project characteristics",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "project_type": {"type": "string", "enum": ["web_application", "api", "mobile_app", "desktop", "microservices"]},
                                    "team_size": {"type": "integer", "minimum": 1, "maximum": 100},
                                    "timeline": {"type": "string", "enum": ["tight", "moderate", "relaxed"]},
                                    "risk_level": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                                    "tech_stack": {"type": "array", "items": {"type": "string"}},
                                    "existing_tests": {"type": "boolean"}
                                },
                                "required": ["project_type"]
                            }
                        },
                        {
                            "name": "design_test_architecture",
                            "description": "Design comprehensive test architecture",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "unit_framework": {"type": "string"},
                                    "integration_framework": {"type": "string"},
                                    "e2e_framework": {"type": "string"},
                                    "performance_requirements": {"type": "object"},
                                    "scalability_needs": {"type": "string"}
                                },
                                "required": []
                            }
                        },
                        {
                            "name": "create_quality_gates",
                            "description": "Create comprehensive quality gates",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "project_type": {"type": "string"},
                                    "compliance_requirements": {"type": "array", "items": {"type": "string"}},
                                    "performance_requirements": {"type": "object"},
                                    "security_requirements": {"type": "object"}
                                },
                                "required": ["project_type"]
                            }
                        },
                        {
                            "name": "generate_test_plan",
                            "description": "Generate comprehensive test plan",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "project_name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "features": {"type": "array", "items": {"type": "string"}},
                                    "stakeholders": {"type": "array", "items": {"type": "string"}},
                                    "timeline": {"type": "string"},
                                    "constraints": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["project_name", "features"]
                            }
                        },
                        {
                            "name": "analyze_test_metrics",
                            "description": "Analyze test execution metrics and provide insights",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "coverage": {"type": "object"},
                                    "execution_times": {"type": "array", "items": {"type": "number"}},
                                    "test_results": {"type": "array"},
                                    "defects": {"type": "array"},
                                    "historical_data": {"type": "object"}
                                },
                                "required": []
                            }
                        },
                        {
                            "name": "framework_comparison",
                            "description": "Compare testing frameworks for given requirements",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "language": {"type": "string", "enum": ["python", "javascript", "java", "csharp"]},
                                    "requirements": {"type": "array", "items": {"type": "string"}},
                                    "team_experience": {"type": "string", "enum": ["beginner", "intermediate", "advanced"]}
                                },
                                "required": ["language"]
                            }
                        },
                        {
                            "name": "test_pyramid_analysis",
                            "description": "Analyze current test distribution against test pyramid principles",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "unit_tests": {"type": "integer"},
                                    "integration_tests": {"type": "integer"},
                                    "e2e_tests": {"type": "integer"},
                                    "execution_times": {"type": "object"}
                                },
                                "required": ["unit_tests", "integration_tests", "e2e_tests"]
                            }
                        }
                    ]
                }

            elif method == 'tools/call':
                tool_name = params.get('name')
                arguments = params.get('arguments', {})

                if tool_name == 'recommend_testing_strategy':
                    result = await self.test_engineer.recommend_testing_strategy(arguments)
                    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

                elif tool_name == 'design_test_architecture':
                    result = await self.test_engineer.design_test_architecture(arguments)
                    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

                elif tool_name == 'create_quality_gates':
                    result = await self.test_engineer.create_quality_gates(arguments)
                    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

                elif tool_name == 'generate_test_plan':
                    result = await self.test_engineer.generate_test_plan(arguments)
                    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

                elif tool_name == 'analyze_test_metrics':
                    result = await self.test_engineer.analyze_test_metrics(arguments)
                    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

                elif tool_name == 'framework_comparison':
                    # Compare frameworks
                    language = arguments['language']
                    frameworks = self.test_engineer.testing_frameworks.get(language, {})

                    comparison = {
                        'language': language,
                        'frameworks': []
                    }

                    for name, framework in frameworks.items():
                        comparison['frameworks'].append({
                            'name': framework.name,
                            'features': framework.features,
                            'setup_complexity': framework.setup_complexity,
                            'learning_curve': framework.learning_curve,
                            'ecosystem': framework.ecosystem,
                            'recommended_for': arguments.get('requirements', [])
                        })

                    return {"content": [{"type": "text", "text": json.dumps(comparison, indent=2)}]}

                elif tool_name == 'test_pyramid_analysis':
                    # Analyze test pyramid distribution
                    unit_count = arguments['unit_tests']
                    integration_count = arguments['integration_tests']
                    e2e_count = arguments['e2e_tests']
                    total = unit_count + integration_count + e2e_count

                    if total == 0:
                        return {"content": [{"type": "text", "text": json.dumps({'error': 'No tests found'}, indent=2)}]}

                    current_distribution = {
                        'unit': (unit_count / total) * 100,
                        'integration': (integration_count / total) * 100,
                        'e2e': (e2e_count / total) * 100
                    }

                    ideal_distribution = {
                        'unit': 70,
                        'integration': 20,
                        'e2e': 10
                    }

                    analysis = {
                        'current_distribution': current_distribution,
                        'ideal_distribution': ideal_distribution,
                        'recommendations': [],
                        'health_score': 0
                    }

                    # Calculate health score and recommendations
                    if current_distribution['unit'] < 60:
                        analysis['recommendations'].append('Increase unit test coverage')
                    if current_distribution['e2e'] > 20:
                        analysis['recommendations'].append('Reduce e2e test dependency')
                    if current_distribution['integration'] > 30:
                        analysis['recommendations'].append('Review integration test necessity')

                    # Simple health score calculation
                    unit_score = min(current_distribution['unit'] / 70, 1.0) * 70
                    integration_score = min(current_distribution['integration'] / 20, 1.0) * 20
                    e2e_score = min(10 / max(current_distribution['e2e'], 1), 1.0) * 10
                    analysis['health_score'] = unit_score + integration_score + e2e_score

                    return {"content": [{"type": "text", "text": json.dumps(analysis, indent=2)}]}

                else:
                    return {"error": {"code": -32601, "message": f"Method {tool_name} not found"}}

            else:
                return {"error": {"code": -32601, "message": f"Method {method} not found"}}

        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return {"error": {"code": -32603, "message": f"Internal error: {str(e)}"}}

async def main():
    """Main server loop"""
    server = MCPServer()

    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break

            request = json.loads(line.strip())
            response = await server.handle_request(request)

            if 'id' in request:
                response['id'] = request['id']
            response['jsonrpc'] = '2.0'

            print(json.dumps(response), flush=True)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error"},
                "id": None
            }
            print(json.dumps(error_response), flush=True)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                "id": request.get('id') if 'request' in locals() else None
            }
            print(json.dumps(error_response), flush=True)

if __name__ == "__main__":
    asyncio.run(main())