from victus.core.confidence import ConfidenceEngine
from victus.core.schemas import PlanStep


def test_missing_required_fields_force_clarify_and_skip_retrieval():
    retrieval_called = False

    def _retrieval(_intent):
        nonlocal retrieval_called
        retrieval_called = True
        return 1.0

    engine = ConfidenceEngine({"communication.send_email": _retrieval})
    step = PlanStep(id="step-1", tool="gmail", action="send", args={"to": "a@b.com"})

    evaluation = engine.evaluate_step(step)

    assert evaluation.decision == "clarify"
    assert evaluation.parse <= 0.34
    assert retrieval_called is False
    assert "missing required fields; clarification required" in evaluation.reasons


def test_play_missing_query_forces_clarify_without_retrieval():
    retrieval_called = False

    def _retrieval(_intent):
        nonlocal retrieval_called
        retrieval_called = True
        return 0.9

    engine = ConfidenceEngine({"media.play": _retrieval})
    step = PlanStep(id="step-1", tool="local", action="media_play", args={"artist": "daft"})

    evaluation = engine.evaluate_step(step)

    assert evaluation.decision == "clarify"
    assert retrieval_called is False


def test_required_fields_present_allow_execute():
    retrieval_called = False

    def _retrieval(_intent):
        nonlocal retrieval_called
        retrieval_called = True
        return 0.9

    engine = ConfidenceEngine({"media.play": _retrieval})
    step = PlanStep(id="step-1", tool="local", action="media_play", args={"query": "perfect"})

    evaluation = engine.evaluate_step(step)

    assert evaluation.decision == "execute"
    assert evaluation.missing_fields == []
    assert retrieval_called is True


def test_empty_required_fields_block_and_skip_retrieval():
    retrieval_called = False

    def _retrieval(_intent):
        nonlocal retrieval_called
        retrieval_called = True
        return 1.0

    engine = ConfidenceEngine({"communication.send_email": _retrieval})
    step = PlanStep(id="step-1", tool="gmail", action="send", args={})

    evaluation = engine.evaluate_step(step)

    assert evaluation.decision == "block"
    assert evaluation.parse <= 0.34
    assert retrieval_called is False
