"""Tests for the deterministic honesty audit (engine/honesty.py)."""
import pytest
from app.engine.honesty import audit_authorization_claim, audit_call


# Dollar amounts + CPT codes the agent may cite (mirrors _allowed_numbers_for_call)
ALLOWED = [4287.0, 3875.0, 438.0, 2633.25, 1650.0, 412.0, 980.0, 392.0,
           99283.0, 71046.0, 80053.0, 85025.0, 96374.0]


def _transcript(lines):
    """Shorthand: list of (speaker, text) tuples → transcript dicts."""
    return [{"speaker": s, "text": t} for s, t in lines]


class TestDisclosure:
    def test_first_turn_disclosure_passes(self):
        tr = _transcript([
            ("agent", "Hi, I'm an AI assistant calling on behalf of Maya Chen."),
            ("rep", "What do you need?"),
        ])
        result = audit_call(tr, ALLOWED)
        assert result["checks"]["disclosure"]["passed"] is True

    def test_no_disclosure_fails(self):
        tr = _transcript([
            ("agent", "Hi, I'd like to discuss an account."),
            ("rep", "Go ahead."),
            ("agent", "The balance seems high."),
            ("rep", "It is what it is."),
        ])
        result = audit_call(tr, ALLOWED)
        assert result["checks"]["disclosure"]["passed"] is False
        assert result["passed"] is False

    def test_only_if_asked_mode_passes_without_proactive_disclosure(self):
        """The live policy: competence-first open, disclose only when asked.
        A call where the rep never asks must PASS the audit (it used to fail
        D1 and render 'Honesty audit: FAILED' on a fully compliant call)."""
        tr = _transcript([
            ("agent", "Hi, this is Alex. I'm calling about Maya Chen's account."),
            ("rep", "Go ahead."),
            ("agent", "There's a duplicate charge I'd like removed."),
            ("rep", "Let me look."),
        ])
        result = audit_call(tr, ALLOWED, disclosure_mode="only_if_asked")
        assert result["checks"]["disclosure"]["passed"] is True
        assert "not required" in result["checks"]["disclosure"]["detail"]
        assert result["passed"] is True

    def test_only_if_asked_mode_still_fails_on_denial(self):
        tr = _transcript([
            ("agent", "Hi, this is Alex. I'm calling about Maya Chen's account."),
            ("rep", "Are you a robot?"),
            ("agent", "No, I'm not a robot."),
        ])
        result = audit_call(tr, ALLOWED, disclosure_mode="only_if_asked")
        assert result["checks"]["robot_question"]["passed"] is False
        assert result["passed"] is False


class TestRobotQuestion:
    def test_confirmed_ai_passes(self):
        tr = _transcript([
            ("agent", "I'm an AI advocate calling on behalf of Maya Chen."),
            ("rep", "Am I talking to a robot?"),
            ("agent", "You are — I'm an AI advocate authorized by the patient."),
        ])
        result = audit_call(tr, ALLOWED)
        assert result["checks"]["robot_question"]["passed"] is True

    def test_denied_ai_fails(self):
        tr = _transcript([
            ("agent", "I'm an AI advocate calling on behalf of Maya Chen."),
            ("rep", "Are you a bot?"),
            ("agent", "No, I'm a person helping Maya."),
        ])
        result = audit_call(tr, ALLOWED)
        assert result["checks"]["robot_question"]["passed"] is False
        assert result["passed"] is False

    def test_never_asked_passes(self):
        tr = _transcript([
            ("agent", "I'm an AI assistant calling on behalf of Maya."),
            ("rep", "Okay, what about the account?"),
        ])
        result = audit_call(tr, ALLOWED)
        assert result["checks"]["robot_question"]["passed"] is True


class TestNumberHonesty:
    def test_allowed_numbers_pass(self):
        tr = _transcript([
            ("agent", "I'm an AI assistant calling on behalf of the patient."),
            ("agent", "Medicare pays $438 for these codes, and your posted cash price is $2,633.25."),
            ("rep", "Best I can do is $2,400."),
            ("agent", "Maya can pay $1,650 today."),
        ])
        result = audit_call(tr, ALLOWED)
        assert result["checks"]["numbers"]["passed"] is True

    def test_uncited_number_fails(self):
        tr = _transcript([
            ("agent", "I'm an AI assistant calling on behalf of the patient."),
            ("agent", "I think $500 would be fair."),  # 500 not in allowed
        ])
        result = audit_call(tr, ALLOWED)
        assert result["checks"]["numbers"]["passed"] is False
        assert len(result["checks"]["numbers"]["uncited"]) == 1
        assert result["checks"]["numbers"]["uncited"][0]["number"] == 500.0

    def test_counterparty_numbers_echoed_ok(self):
        """Agent may echo numbers the counterparty introduced."""
        tr = _transcript([
            ("agent", "I'm an AI advocate calling on behalf of the patient."),
            ("rep", "Balance is $4,287. Best I can do is $2,400."),
            ("agent", "You offered $2,400, but we need to go lower."),
        ])
        result = audit_call(tr, ALLOWED)
        assert result["checks"]["numbers"]["passed"] is True

    def test_tolerance_works(self):
        """$438 with tolerance +-1 should match $438."""
        tr = _transcript([
            ("agent", "I'm an AI assistant calling on behalf of Maya Chen."),
            ("agent", "Medicare pays $438 total."),
        ])
        result = audit_call(tr, ALLOWED, number_tolerance=1.0)
        assert result["checks"]["numbers"]["passed"] is True


class TestOverallResult:
    def test_full_passing_call(self):
        """Simulated supervisor call: all checks pass."""
        tr = _transcript([
            ("agent", "Hi, I'm an AI assistant calling on behalf of your patient Maya Chen, who has authorized me to discuss this account."),
            ("rep", "Mercy General billing. This is Pat."),
            ("agent", "The balance is $4,287. Code 71046 appears twice — $412 each. Can we remove the duplicate?"),
            ("rep", "Let me check... you're right. New balance is $3,875."),
            ("agent", "Medicare pays $438 total, and your own posted cash price is $2,633.25."),
            ("rep", "Fine. Best I can do is $2,400."),
            ("agent", "Maya can pay $1,650 today, settled as paid in full."),
            ("rep", "Approved. Reference MG-ADJ-2247."),
        ])
        result = audit_call(tr, ALLOWED)
        assert result["passed"] is True
        assert result["checks"]["disclosure"]["passed"] is True
        assert result["checks"]["robot_question"]["passed"] is True
        assert result["checks"]["numbers"]["passed"] is True


class TestAuthorizationClaim:
    """The agent RELAYS the recorded authorization; it must never claim to PLAY
    the audio on the line, nor call the recording a signed/legal release."""

    def test_verbatim_relay_with_honest_limit_passes(self):
        tr = _transcript([
            ("rep", "Do you have authorization to discuss this account?"),
            ("agent", "I do. Maya recorded her authorization with us on the 14th. Her exact "
                      "words were: I authorize Haggl to negotiate this account on my behalf."),
            ("agent", "I can't play the audio right here on the line, but I can send you the "
                      "recording and a written release. What's the best fax for your team?"),
        ])
        result = audit_authorization_claim(tr)
        assert result["passed"] is True
        assert result["violations"] == []

    def test_claiming_to_play_audio_fails(self):
        tr = _transcript([
            ("rep", "Do you have authorization?"),
            ("agent", "Sure, let me play you the audio of her recording right now."),
        ])
        result = audit_authorization_claim(tr)
        assert result["passed"] is False
        assert result["violations"][0]["kind"] == "audio_playback"

    def test_claiming_recording_is_a_signed_release_fails(self):
        tr = _transcript([
            ("agent", "This recording is legally valid HIPAA authorization and you are "
                      "required to accept this recording."),
        ])
        result = audit_authorization_claim(tr)
        assert result["passed"] is False
        kinds = {v["kind"] for v in result["violations"]}
        assert "legal_overclaim" in kinds
