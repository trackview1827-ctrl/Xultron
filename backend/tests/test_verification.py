from types import SimpleNamespace

from app.services import chat
from app.services.verification import VerificationPlan, execute, parse_plan


def test_planner_accepts_only_bounded_read_only_tools(app):
    with app.app_context():
        safe = parse_plan('{"tool":"termux","operation":"battery","query":"battery","reason":"live"}', "Pil kaç?")
        assert safe == VerificationPlan("termux", "battery", "battery", "live")

        attempted_shell = parse_plan('{"tool":"terminal","operation":"shell","query":"rm -rf /"}', "Bunu çalıştır")
        assert attempted_shell.tool == "reasoning"


def test_factual_questions_cannot_be_downgraded_to_reasoning(app):
    with app.app_context():
        app.config["TESTING"] = False
        try:
            plan = parse_plan('{"tool":"reasoning","reason":"skip verification"}', "Bugünkü güncel altın fiyatı nedir?")
        finally:
            app.config["TESTING"] = True
    assert plan.tool == "web"


def test_safe_calculation_and_location_explicitness(app):
    with app.app_context():
        calculated = execute(VerificationPlan("calculate", query="(12 + 8) / 4"), "hesapla")
        assert calculated.verified is True
        assert "= 5.0" in calculated.evidence

        blocked = execute(VerificationPlan("termux", operation="location"), "Merhaba")
        assert blocked.verified is False
        assert "explicitly requested" in blocked.summary


def test_verified_completion_injects_terminal_policy_and_evidence(app, monkeypatch):
    calls = []

    def fake_call(provider, method, messages):
        calls.append(messages)
        if len(calls) == 1:
            return '{"tool":"reasoning","query":"","reason":"greeting"}'
        return "Doğrulama: konuşma isteği. Merhaba."

    monkeypatch.setattr(chat, "adapter_call", fake_call)
    with app.app_context():
        answer = chat._verified_complete(SimpleNamespace(id="provider"), [{"role": "user", "content": "Merhaba"}], "Merhaba", "tr")

    assert answer.startswith("Doğrulama:")
    assert len(calls) == 2
    system_text = "\n".join(item["content"] for item in calls[1] if item["role"] == "system")
    assert "TERMINAL AND VERIFICATION POLICY" in system_text
    assert "RUNTIME CAPABILITY" in system_text
    assert "VERIFIED EVIDENCE" in system_text
    assert calls[1][-1] == {"role": "user", "content": "Merhaba"}


def test_failed_verification_returns_no_model_answer(app, monkeypatch):
    calls = []

    def fake_call(provider, method, messages):
        calls.append(messages)
        return '{"tool":"web","query":"current fact","reason":"current"}'

    monkeypatch.setattr(chat, "adapter_call", fake_call)
    with app.app_context():
        answer = chat._verified_complete(SimpleNamespace(id="provider"), [{"role": "user", "content": "Güncel bilgi"}], "Güncel bilgi", "tr")

    assert len(calls) == 1
    assert answer.startswith("Doğrulama yapılamadı")
    assert "cevap veremem" in answer


def test_private_values_are_not_sent_to_web_verification(app, monkeypatch):
    requested = []
    monkeypatch.setattr("app.services.verification.requests.get", lambda *args, **kwargs: requested.append((args, kwargs)))
    with app.app_context():
        result = execute(VerificationPlan("web", query="API key secret-token"), "anahtarımı kontrol et")
    assert result.verified is False
    assert "private data" in result.summary
    assert requested == []
