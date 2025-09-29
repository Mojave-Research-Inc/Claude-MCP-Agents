#!/usr/bin/env python3
"""
Test script demonstrating the full integration of Checklist Sentinel
with Brain and Knowledge Management systems.
"""

import time
import json
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent))

from unified_checklist_brain import UnifiedChecklistBrain, KnowledgeStewardAgent
from checklist_agent_wrapper import ChecklistAgentWrapper
from checklist_sentinel import TaskState

def test_full_workflow():
    """Test a complete workflow with all systems integrated."""
    print("=" * 60)
    print("Testing Unified Checklist-Brain-Knowledge Integration")
    print("=" * 60)

    # Initialize unified system
    unified = UnifiedChecklistBrain()

    # Create a unified session
    print("\n1. Creating unified session...")
    context = unified.create_unified_session(
        intent="Build a REST API with authentication and testing",
        project_path="/tmp/test_project"
    )
    print(f"✓ Created session {context.session_id}")

    # Start knowledge steward
    print("\n2. Starting knowledge steward...")
    steward = KnowledgeStewardAgent(unified)
    steward.start()
    print("✓ Knowledge steward running")

    # Create checklist items with knowledge
    print("\n3. Creating checklist items with knowledge integration...")

    items = []

    # Design phase
    item1 = unified.create_checklist_item_with_knowledge(
        title="Design API architecture",
        description="Plan the API structure, endpoints, and data models",
        acceptance_criteria=[
            "API endpoints documented",
            "Data models defined",
            "Authentication flow designed"
        ],
        related_knowledge="RESTful API best practices: Use HTTP verbs properly, implement proper status codes, version your API"
    )
    items.append(item1)
    print(f"✓ Created item {item1}: Design API architecture")

    # Implementation phase
    item2 = unified.create_checklist_item_with_knowledge(
        title="Implement authentication system",
        description="Create JWT-based authentication",
        acceptance_criteria=[
            "User registration endpoint working",
            "Login endpoint returns JWT",
            "Token validation middleware implemented"
        ],
        related_knowledge="JWT authentication pattern: Store user ID in token, use refresh tokens, implement proper expiry"
    )
    items.append(item2)
    print(f"✓ Created item {item2}: Implement authentication")

    item3 = unified.create_checklist_item_with_knowledge(
        title="Create API endpoints",
        description="Implement CRUD operations for main resources",
        acceptance_criteria=[
            "All CRUD endpoints functional",
            "Input validation implemented",
            "Error handling in place"
        ],
        related_knowledge="CRUD operations should be idempotent where applicable, use proper HTTP methods"
    )
    items.append(item3)
    print(f"✓ Created item {item3}: Create API endpoints")

    # Testing phase
    item4 = unified.create_checklist_item_with_knowledge(
        title="Write comprehensive tests",
        description="Create unit and integration tests",
        acceptance_criteria=[
            "Unit test coverage > 80%",
            "Integration tests for all endpoints",
            "Authentication tests passing"
        ],
        related_knowledge="Test pyramid: More unit tests, fewer integration tests, even fewer E2E tests"
    )
    items.append(item4)
    print(f"✓ Created item {item4}: Write tests")

    # Verification phase
    item5 = unified.create_checklist_item_with_knowledge(
        title="Verify complete solution",
        description="Final verification of all components",
        acceptance_criteria=[
            "All tests passing",
            "API documentation complete",
            "Security review completed"
        ],
        related_knowledge="Final verification should include performance testing and security audit"
    )
    items.append(item5)
    print(f"✓ Created item {item5}: Verify solution")

    # Create checkpoint
    print("\n4. Creating initial checkpoint...")
    checkpoint1 = unified.create_checkpoint("initial_setup")
    print(f"✓ Created checkpoint {checkpoint1}")

    # Simulate agent work on items
    print("\n5. Simulating agent work...")

    # Agent 1: Architecture designer
    agent1 = ChecklistAgentWrapper("architecture-design")
    agent1.session_id = context.session_id

    if agent1.claim_task(item1, "Designing API architecture"):
        print(f"✓ architecture-design claimed item {item1}")
        agent1.add_note("Analyzing requirements")
        agent1.add_note("Creating endpoint specifications")
        agent1.attach_artifact("specification", "/tmp/api_spec.yaml")
        agent1.attach_artifact("diagram", "/tmp/architecture.png")
        unified.log_agent_work_unified(
            item1, "architecture-design",
            "Completed API architecture design",
            ["/tmp/api_spec.yaml", "/tmp/architecture.png"]
        )
        agent1.submit_for_review("Architecture design complete")
        print(f"✓ architecture-design completed item {item1}")

    # Agent 2: Backend implementer
    agent2 = ChecklistAgentWrapper("backend-implementer")
    agent2.session_id = context.session_id

    if agent2.claim_task(item2, "Implementing authentication"):
        print(f"✓ backend-implementer claimed item {item2}")
        agent2.add_note("Setting up JWT library")
        agent2.add_note("Creating user model")
        agent2.add_note("Implementing auth endpoints")
        agent2.attach_artifact("code", "/tmp/auth.py")
        unified.log_agent_work_unified(
            item2, "backend-implementer",
            "Implemented JWT authentication",
            ["/tmp/auth.py", "/tmp/user_model.py"]
        )
        agent2.submit_for_review("Authentication implementation complete")
        print(f"✓ backend-implementer completed item {item2}")

    # Simulate some blocked items
    agent3 = ChecklistAgentWrapper("test-automator")
    agent3.session_id = context.session_id

    if agent3.claim_task(item4, "Writing tests"):
        print(f"✓ test-automator claimed item {item4}")
        agent3.add_note("Writing unit tests")
        # Simulate blocking
        agent3.mark_blocked(
            "Missing test database configuration",
            ["Provide TEST_DATABASE_URL environment variable", "Set up test fixtures"]
        )
        print(f"⚠ test-automator blocked on item {item4}")

    # Create checkpoint after work
    print("\n6. Creating work-in-progress checkpoint...")
    checkpoint2 = unified.create_checkpoint("work_in_progress")
    print(f"✓ Created checkpoint {checkpoint2}")

    # Search across systems
    print("\n7. Testing unified search...")
    search_results = unified.search_unified("auth")
    print(f"✓ Search for 'auth' found:")
    print(f"  - {len(search_results['checklist_items'])} checklist items")
    print(f"  - {len(search_results['knowledge_chunks'])} knowledge chunks")
    print(f"  - {len(search_results['artifacts'])} artifacts")

    # Sync checklist events to brain
    print("\n8. Syncing checklist events to brain...")
    unified.sync_checklist_events_to_brain()
    print("✓ Events synced to knowledge base")

    # Generate haikus for items
    print("\n9. Generating haikus for items...")
    for item_id in items[:3]:
        haiku = unified.generate_haiku_for_item(item_id)
        print(f"✓ Haiku for item {item_id}:")
        print(f"  {haiku.replace(chr(10), chr(10) + '  ')}")

    # Get unified status
    print("\n10. Getting unified system status...")
    status = unified.get_unified_status()

    print("\n📊 System Status:")
    print(f"  Checklist:")
    checklist_status = status['checklist']
    print(f"    - Items: {checklist_status.get('total_items', 0)}")
    print(f"    - Completion: {checklist_status.get('completion_rate', 0):.1f}%")
    print(f"    - Active leases: {checklist_status.get('active_leases', 0)}")

    if 'brain' in status and status['brain']:
        print(f"  Brain:")
        print(f"    - Session ID: {status['brain'].get('session_id', 'N/A')}")

    if 'knowledge' in status:
        print(f"  Knowledge:")
        print(f"    - Chunks created: {status['knowledge'].get('chunks_created', 0)}")
        print(f"    - Artifacts tracked: {status['knowledge'].get('artifacts_tracked', 0)}")

    if 'unified' in status:
        print(f"  Unified:")
        print(f"    - Brain mappings: {status['unified'].get('brain_mappings', 0)}")
        print(f"    - Knowledge mappings: {status['unified'].get('knowledge_mappings', 0)}")
        print(f"    - Total artifacts: {status['unified'].get('total_artifacts', 0)}")
        print(f"    - Checkpoints: {status['unified'].get('total_checkpoints', 0)}")

    # Test revival mechanism
    print("\n11. Testing orchestrator revival...")
    briefing = unified.sentinel.revive_orchestrator("test-orchestrator")
    print(f"✓ Revival briefing generated:")
    print(f"  - Context: {briefing['context']}")
    print(f"  - Next items: {len(briefing.get('next_items', []))}")
    print(f"  - Blockers: {len(briefing.get('blockers', []))}")

    # Stop knowledge steward
    print("\n12. Stopping knowledge steward...")
    steward.stop()
    print("✓ Knowledge steward stopped")

    # Final cleanup
    print("\n13. Creating final checkpoint and cleaning up...")
    checkpoint3 = unified.create_checkpoint("final")
    print(f"✓ Created final checkpoint {checkpoint3}")

    unified.cleanup()
    print("✓ Cleanup complete")

    print("\n" + "=" * 60)
    print("✅ Integration test completed successfully!")
    print("=" * 60)

    return True

def test_recovery():
    """Test checkpoint recovery functionality."""
    print("\n" + "=" * 60)
    print("Testing Checkpoint Recovery")
    print("=" * 60)

    # Create initial system
    unified = UnifiedChecklistBrain()
    context = unified.create_unified_session("Test recovery", "/tmp/recovery_test")

    # Create some items
    item1 = unified.create_checklist_item_with_knowledge(
        "Test item 1", "First test item",
        ["Criterion 1"], "Test knowledge 1"
    )

    # Create checkpoint
    checkpoint_id = unified.create_checkpoint("test_recovery")
    print(f"Created checkpoint {checkpoint_id}")

    # Simulate system failure - create new instance
    unified2 = UnifiedChecklistBrain()

    # Restore from checkpoint
    success = unified2.restore_from_checkpoint(checkpoint_id)
    print(f"Recovery {'successful' if success else 'failed'}")

    if success:
        print(f"Restored session: {unified2.current_context.session_id}")
        print(f"Restored items: {unified2.current_context.checklist_items}")

    unified.cleanup()
    return success

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Checklist Integration")
    parser.add_argument("--test", choices=["full", "recovery", "all"],
                       default="all", help="Which test to run")

    args = parser.parse_args()

    try:
        if args.test in ["full", "all"]:
            success = test_full_workflow()
            if not success and args.test == "all":
                print("Full workflow test failed, skipping recovery test")
                sys.exit(1)

        if args.test in ["recovery", "all"]:
            success = test_recovery()
            if not success:
                print("Recovery test failed")
                sys.exit(1)

        print("\n✅ All tests passed!")

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)