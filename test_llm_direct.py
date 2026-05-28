"""Direct LLM orchestrator test.

Run from backend/ directory with server stopped:
    cd backend
    python test_llm_direct.py
"""

import asyncio
import sys
import time
import uuid

# Ensure backend/ modules are importable
sys.path.insert(0, ".")


async def test():
    print("\n=== Step 1: Emotional Intelligence Cycle ===")
    try:
        from emotion.emotional_intelligence_core import (
            EmotionalIntelligenceCore,
        )
        from emotion.emotional_fusion_engine import EmotionalSignal
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("   Run this from inside the backend/ directory")
        return

    ei = EmotionalIntelligenceCore()

    signal = EmotionalSignal(
        source="voice",
        confidence=0.8,
        timestamp=time.monotonic(),
        values={
            "stress": 0.6,
            "cognitive_load": 0.5,
            "engagement": 0.4,
            "emotional_openness": 0.3,
        },
    )

    # Try both locations for RhythmSignal
    RhythmSignal = None
    for module_path in [
        "voice.conversational_runtime",
        "emotion.conversational_rhythm_engine",
    ]:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            RhythmSignal = getattr(mod, "RhythmSignal", None)
            if RhythmSignal:
                print(f"   RhythmSignal found in {module_path}")
                break
        except ImportError:
            continue

    if RhythmSignal is None:
        print("❌ RhythmSignal not found in expected modules")
        print("   Check voice/conversational_runtime.py or")
        print("   emotion/conversational_rhythm_engine.py")
        return

    rhythm = RhythmSignal(
        pause_duration=1.2,
        interruption_frequency=0.3,
        speech_pacing=0.6,
        silence_comfort=0.5,
        response_latency=0.4,
        conversational_volatility=0.3,
        timestamp=time.monotonic(),
    )

    try:
        cycle = await ei.run_cycle([signal], rhythm)
        print(f"✅ Cycle complete:")
        print(f"   stress          = {cycle.emotional_state.stress:.2f}")
        print(f"   cognitive_load  = {cycle.emotional_state.cognitive_load:.2f}")
        print(f"   engagement      = {cycle.emotional_state.engagement:.2f}")
        print(f"   recovery_state  = {cycle.emotional_state.recovery_state:.2f}")
    except Exception as e:
        print(f"❌ Cycle failed: {e}")
        import traceback; traceback.print_exc()
        return

    print("\n=== Step 2: Response Policy ===")
    try:
        from cognition.response_policy_engine import ResponsePolicyEngine
        engine = ResponsePolicyEngine()
        policy = engine.evaluate(cycle)
        print(f"✅ Policy evaluated:")
        print(f"   mode            = {policy.response_mode}")
        print(f"   should_respond  = {policy.should_respond}")
        print(f"   max_sentences   = {policy.max_sentences}")
        print(f"   max_questions   = {policy.max_questions}")
        print(f"   pacing_density  = {policy.pacing_density}")
        print(f"   silence_reason  = {policy.silence_reason}")
    except Exception as e:
        print(f"❌ Policy failed: {e}")
        import traceback; traceback.print_exc()
        return

    if not policy.should_respond:
        print("\n⚠️  Silence decision — system correctly chose not to respond")
        print("   This is valid behavior. To force a response for testing,")
        print("   increase engagement value in signal above.")
        return

    print("\n=== Step 3: Prompt Conditioner ===")
    try:
        from cognition.prompt_conditioner import PromptConditioner
        conditioner = PromptConditioner()
        prompt = conditioner.build(policy, cycle)
        print(f"✅ Prompt built:")
        print(f"   response_mode   = {prompt.response_mode}")
        print(f"   prompt_version  = {prompt.prompt_version}")
        print(f"   max_sentences   = {prompt.max_sentences}")
        print(f"   system_prompt preview:")
        # Show first 200 chars only
        preview = prompt.system_prompt[:200].replace("\n", " ")
        print(f"   '{preview}...'")
    except Exception as e:
        print(f"❌ Prompt conditioner failed: {e}")
        import traceback; traceback.print_exc()
        return

    print("\n=== Step 4: Phi-3 via Ollama ===")
    try:
        from cognition.backends.phi3_ollama_backend import Phi3OllamaBackend
        from cognition.llm_orchestrator import LLMOrchestrator

        backend = Phi3OllamaBackend()
        orchestrator = LLMOrchestrator(llm_backend=backend)

        start = time.monotonic()
        result = await orchestrator.orchestrate(
            cycle,
            uuid.uuid4(),
            "debug_session_001",
            time.monotonic(),
        )
        elapsed = (time.monotonic() - start) * 1000

        if result is None:
            print("⚠️  Orchestrator silence decision")
            print("   Policy chose silence — valid behavior")
            return

        print(f"✅ LLM response in {elapsed:.0f}ms:")
        print(f"   raw response:   '{result.raw_response[:100]}'")
        print(f"   enforced:       '{result.enforced_response.enforced_text}'")
        print(f"   mode:           {result.policy_applied.response_mode}")
        print(f"   fallback_used:  {result.used_fallback}")
        print(f"   fallback_reason:{result.fallback_reason}")
        print(f"   sentences_removed: {result.enforced_response.sentences_removed}")
        print(f"   questions_removed: {result.enforced_response.questions_removed}")
        print(f"   was_truncated:  {result.enforced_response.was_truncated}")

        if elapsed > 3000:
            print(f"\n⚠️  {elapsed:.0f}ms exceeds 3s timeout budget")
            print("    Consider: ollama pull phi3:mini")
        else:
            print(f"\n✅ Within 3s timeout — good for real-time use")

    except Exception as e:
        print(f"❌ LLM orchestration failed: {e}")
        import traceback; traceback.print_exc()
        return

    print("\n=== Step 5: Constraint Enforcer Verification ===")
    try:
        from cognition.response_constraint_enforcer import (
            ResponseConstraintEnforcer,
        )
        enforcer = ResponseConstraintEnforcer()

        # Simulate Phi-3's actual verbose response pattern
        raw_overreach = (
            "I understand that you're seeking acknowledgment. "
            "I hear you and I'm here for you. "
            "You should try to take things one step at a time. "
            "Everything will be okay."
        )

        enforced = enforcer.enforce(raw_overreach, policy)
        print(f"✅ Enforcer working:")
        print(f"   input:    '{raw_overreach[:80]}...'")
        print(f"   output:   '{enforced.enforced_text}'")
        print(f"   removed:  {enforced.sentences_removed} sentences")
        print(f"   truncated:{enforced.was_truncated}")
    except Exception as e:
        print(f"❌ Enforcer test failed: {e}")
        import traceback; traceback.print_exc()

    print("\n=== All Steps Complete ===")
    print("Ready for Debug Step 4: WebSocket end-to-end test")


asyncio.run(test())
