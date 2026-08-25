import json
from types import SimpleNamespace

from app.services import chat
from app.services.verification import VerificationPlan, deterministic_plan, execute, parse_plan


def test_planner_accepts_only_bounded_read_only_tools(app):
    with app.app_context():
        app.config["TESTING"] = False
        try:
            safe = parse_plan('{"tool":"termux","operation":"battery","query":"battery","reason":"live"}', "Pil kaç?")
            attempted_shell = parse_plan('{"tool":"terminal","operation":"shell","query":"rm -rf /"}', "Bunu çalıştır")
        finally:
            app.config["TESTING"] = True
        assert safe == VerificationPlan("termux", "battery", reason="live")
        assert attempted_shell.tool == "web"


def test_factual_questions_cannot_be_downgraded_to_reasoning(app):
    with app.app_context():
        app.config["TESTING"] = False
        try:
            plan = parse_plan('{"tool":"reasoning","reason":"skip verification"}', "Bugünkü güncel altın fiyatı nedir?")
            redirected = parse_plan('{"tool":"web","query":"unrelated weather","reason":"current"}', "Bugünkü güncel altın fiyatı nedir?")
        finally:
            app.config["TESTING"] = True
    assert plan.tool == "web"
    assert redirected.query == "Bugünkü güncel altın fiyatı nedir?"


def test_greeting_does_not_hide_factual_intent_and_termux_operations_are_exact(app):
    with app.app_context():
        app.config["TESTING"] = False
        try:
            greeting_fact = parse_plan('{"tool":"reasoning","reason":"greeting"}', "Merhaba, bugünkü güncel altın fiyatı nedir?")
            wrong_phone_tool = parse_plan('{"tool":"termux","operation":"network","query":"wifi"}', "Pil yüzde kaç?")
            denied_location = parse_plan('{"tool":"termux","operation":"location"}', "Konumumu öğrenme, sadece cihaz durumunu söyle")
        finally:
            app.config["TESTING"] = True
    assert greeting_fact.tool == "web"
    assert wrong_phone_tool == VerificationPlan("termux", "battery", reason="Live battery evidence")
    assert denied_location == VerificationPlan("termux", "api_status", reason="Live Termux capability evidence")


def test_safe_calculation_and_location_explicitness(app):
    with app.app_context():
        calculated = execute(VerificationPlan("calculate", query="(12 + 8) / 4"), "hesapla")
        assert calculated.verified is True
        assert "= 5.0" in calculated.evidence

        blocked = execute(VerificationPlan("termux", operation="location"), "Merhaba")
        denied = execute(VerificationPlan("termux", operation="location"), "Sakın konumuma bakma")
        assert blocked.verified is False
        assert denied.verified is False
        assert "explicitly permitted" in blocked.summary

        oversized = execute(VerificationPlan("calculate", query="9 ** 999999"), "hesapla")
        assert oversized.verified is False
        nested_power = execute(VerificationPlan("calculate", query="9 ** 9 ** 9"), "hesapla")
        assert nested_power.verified is False


def test_live_clock_questions_use_runtime_evidence(app):
    with app.app_context():
        app.config["TESTING"] = False
        try:
            plan = parse_plan('{"tool":"web","query":"time"}', "Şu an saat kaç?")
            result = execute(plan, "Şu an saat kaç?")
        finally:
            app.config["TESTING"] = True
    assert plan == VerificationPlan("runtime", "clock", reason="Live local date and time evidence")
    assert result.verified is True
    assert result.tool == "runtime:clock"
    assert '"date"' in result.evidence
    assert '"time"' in result.evidence
    assert '"timezone"' in result.evidence


def test_minor_typos_still_select_the_expected_safe_intent(app):
    with app.app_context():
        app.config["TESTING"] = False
        try:
            clock = deterministic_plan("Saaat kac?")
            battery = deterministic_plan("Sarzim kac?")
            network = deterministic_plan("Wifim durm ne?")
            terminal = deterministic_plan("Termuks API iznin varmi?")
            project = deterministic_plan("Xultrn backend kodu nerede?")
            greeting = deterministic_plan("Selamm nasilsn?")
            greeting_with_fact = deterministic_plan("Merhabaa bugunku altin fiyati ne?")
        finally:
            app.config["TESTING"] = True

    assert clock == VerificationPlan("runtime", "clock", reason="Live local date and time evidence")
    assert battery == VerificationPlan("termux", "battery", reason="Live battery evidence")
    assert network == VerificationPlan("termux", "network", reason="Live network evidence")
    assert terminal == VerificationPlan("termux", "api_status", reason="Live Termux capability evidence")
    assert project.tool == "project"
    assert greeting.tool == "reasoning"
    assert greeting_with_fact.tool == "web"


def test_location_typos_remain_fail_closed(app):
    with app.app_context():
        app.config["TESTING"] = False
        try:
            denied = deterministic_plan("Sakn konmumu alma")
            ambiguous = deterministic_plan("Konmumu soyle")
        finally:
            app.config["TESTING"] = True

    assert denied.tool == "reasoning"
    assert ambiguous.tool != "termux"


def test_web_evidence_names_public_source_domains(app, monkeypatch):
    page = b'<a class="result__a" href="https://docs.python.org/3/">Python documentation</a><div class="result__snippet">Official Python documentation.</div>'

    class Response:
        status_code = 200
        headers = {"Content-Length": str(len(page))}
        encoding = "utf-8"

        def iter_content(self, chunk_size=32768):
            yield page

        def close(self):
            return None

    monkeypatch.setattr("app.services.verification.requests.get", lambda *args, **kwargs: Response())
    with app.app_context():
        app.config["VERIFICATION_WEB_ENABLED"] = True
        result = execute(VerificationPlan("web", query="Python official documentation"), "Python resmi sitesi nedir?")
    assert result.verified is True
    assert "docs.python.org" in result.evidence
    assert "Python documentation" in result.evidence


def test_verified_completion_injects_terminal_policy_and_evidence(app, monkeypatch):
    calls = []

    def fake_call(provider, method, messages):
        calls.append(messages)
        return "**Doğrulama:** Merhaba."

    monkeypatch.setattr(chat, "adapter_call", fake_call)
    with app.app_context():
        answer = chat._verified_complete(SimpleNamespace(id="provider"), [{"role": "user", "content": "Merhaba"}], "Merhaba", "tr")

    assert answer == "Merhaba."
    assert len(calls) == 1
    system_text = "\n".join(item["content"] for item in calls[0] if item["role"] == "system")
    assert "TERMINAL AND VERIFICATION POLICY" in system_text
    assert "RUNTIME CAPABILITY" in system_text
    assert "VERIFIED EVIDENCE" in system_text
    assert "Do not mention verification" in system_text
    assert "one to three short sentences" in system_text
    assert "minor spelling" in system_text
    assert calls[0][-1] == {"role": "user", "content": "Merhaba"}
    assert calls[0][-2]["role"] == "system"
    assert "VERIFIED EVIDENCE" in calls[0][-2]["content"]


def test_failed_verification_returns_no_model_answer(app, monkeypatch):
    calls = []

    def fake_call(provider, method, messages):
        calls.append(messages)
        return '{"tool":"web","query":"current fact","reason":"current"}'

    monkeypatch.setattr(chat, "adapter_call", fake_call)
    with app.app_context():
        app.config["TESTING"] = False
        try:
            answer = chat._verified_complete(SimpleNamespace(id="provider"), [{"role": "user", "content": "Güncel bilgi"}], "Güncel bilgi", "tr")
        finally:
            app.config["TESTING"] = True

    assert len(calls) == 0
    assert answer == "Şu anda güvenilir bir cevap üretemiyorum. Lütfen biraz sonra tekrar dene."
    assert "Doğrulama" not in answer


def test_clock_answer_does_not_call_rate_limited_provider(app, monkeypatch):
    calls = []
    monkeypatch.setattr(chat, "adapter_call", lambda *args, **kwargs: calls.append((args, kwargs)))
    with app.app_context():
        app.config["TESTING"] = False
        try:
            answer = chat._verified_complete(SimpleNamespace(id="provider"), [{"role": "user", "content": "Şu an saat kaç?"}], "Şu an saat kaç?", "tr")
        finally:
            app.config["TESTING"] = True
    assert answer.startswith("Şu an saat ")
    assert "tarih" in answer
    assert "Doğrulama" not in answer
    assert calls == []


def test_private_values_are_not_sent_to_web_verification(app, monkeypatch):
    requested = []
    monkeypatch.setattr("app.services.verification.requests.get", lambda *args, **kwargs: requested.append((args, kwargs)))
    with app.app_context():
        result = execute(VerificationPlan("web", query="API key secret-token"), "anahtarımı kontrol et")
    assert result.verified is False
    assert "private data" in result.summary
    assert requested == []


def test_network_evidence_redacts_identifiers_unless_explicit(app, monkeypatch):
    payload = json.dumps({"ssid": "Example", "ip": "192.0.2.10", "bssid": "private-bssid", "mac_address": "private-mac", "rssi": -45})
    monkeypatch.setattr("app.services.verification.shutil.which", lambda command: f"/bin/{command}")
    monkeypatch.setattr("app.services.verification.subprocess.run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=payload, stderr=""))
    with app.app_context():
        ordinary = execute(VerificationPlan("termux", operation="network"), "WiFi durumum nasıl?")
        explicit = execute(VerificationPlan("termux", operation="network"), "IP adresim nedir?")
        named = execute(VerificationPlan("termux", operation="network"), "WiFi adı nedir?")
    assert ordinary.verified is True
    assert "private-bssid" not in ordinary.evidence
    assert "private-mac" not in ordinary.evidence
    assert "192.0.2.10" not in ordinary.evidence
    assert "Example" not in ordinary.evidence
    assert "192.0.2.10" in explicit.evidence
    assert "Example" in named.evidence
