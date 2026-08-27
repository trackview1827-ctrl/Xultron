import json
from types import SimpleNamespace

from app.services import chat
from app.services.verification import VerificationPlan, deterministic_plan, direct_answer, execute, parse_plan
from tests.conftest import patch_json, post_json


def test_planner_rejects_removed_device_automation_tools(app):
    with app.app_context():
        app.config["TESTING"] = False
        try:
            safe = parse_plan('{"tool":"termux","operation":"battery","query":"battery","reason":"live"}', "Pil kaç?")
            attempted_shell = parse_plan('{"tool":"terminal","operation":"shell","query":"rm -rf /"}', "Bunu çalıştır")
        finally:
            app.config["TESTING"] = True
    assert safe == VerificationPlan("runtime", "unsupported_device_fact", reason="Device API automations are disabled")
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


def test_greeting_does_not_hide_factual_intent_and_removed_device_operations_fail_closed(app):
    with app.app_context():
        app.config["TESTING"] = False
        try:
            greeting_fact = parse_plan('{"tool":"reasoning","reason":"greeting"}', "Merhaba, bugünkü güncel altın fiyatı nedir?")
            wrong_phone_tool = parse_plan('{"tool":"termux","operation":"network","query":"wifi"}', "Pil yüzde kaç?")
            denied_location = parse_plan('{"tool":"termux","operation":"location"}', "Konumumu öğrenme, sadece cihaz durumunu söyle")
        finally:
            app.config["TESTING"] = True
    assert greeting_fact.tool == "web"
    assert wrong_phone_tool == VerificationPlan("runtime", "unsupported_device_fact", reason="Device API automations are disabled")
    assert denied_location == VerificationPlan("runtime", "unsupported_device_fact", reason="Device API automations are disabled")


def test_safe_calculation_and_location_explicitness(app):
    with app.app_context():
        calculated = execute(VerificationPlan("calculate", query="(12 + 8) / 4"), "hesapla")
        assert calculated.verified is True
        assert "= 5.0" in calculated.evidence

        blocked = execute(VerificationPlan("runtime", operation="unsupported_device_fact"), "Merhaba")
        denied = execute(VerificationPlan("runtime", operation="unsupported_device_fact"), "Sakın konumuma bakma")
        assert blocked.verified is False
        assert denied.verified is False
        assert "disabled" in blocked.summary

        oversized = execute(VerificationPlan("calculate", query="9 ** 999999"), "hesapla")
        assert oversized.verified is False
        nested_power = execute(VerificationPlan("calculate", query="9 ** 9 ** 9"), "hesapla")
        assert nested_power.verified is False


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

    assert clock.tool == "web"
    assert clock.operation == "saatkac_country"
    assert clock.query == "Türkiye"
    assert battery == VerificationPlan("runtime", "unsupported_device_fact", reason="Device API automations are disabled")
    assert network == VerificationPlan("runtime", "unsupported_device_fact", reason="Device API automations are disabled")
    assert terminal == VerificationPlan("runtime", "unsupported_device_fact", reason="Device API automations are disabled")
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

    assert denied.tool == "runtime"
    assert ambiguous.tool == "runtime"


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
    assert answer == "Bu istek için doğrulanmış bir sonuç bulunamadı."
    assert "Doğrulama" not in answer


def test_typo_greeting_is_answered_locally_without_provider(app, monkeypatch):
    calls = []
    monkeypatch.setattr(chat, "adapter_call", lambda *args, **kwargs: calls.append((args, kwargs)))
    with app.app_context():
        app.config["TESTING"] = False
        try:
            answer = chat._verified_complete(SimpleNamespace(id="provider"), [{"role": "user", "content": "Selamm nasilsn?"}], "Selamm nasilsn?", "tr")
        finally:
            app.config["TESTING"] = True
    assert answer == "Selam! İyiyim, nasıl yardımcı olabilirim?"
    assert calls == []


def test_private_values_are_not_sent_to_web_verification(app, monkeypatch):
    requested = []
    monkeypatch.setattr("app.services.verification.requests.get", lambda *args, **kwargs: requested.append((args, kwargs)))
    with app.app_context():
        result = execute(VerificationPlan("web", query="API key secret-token"), "anahtarımı kontrol et")
    assert result.verified is False
    assert "private data" in result.summary
    assert requested == []


def test_removed_device_automation_never_calls_termux_api(app):
    with app.app_context():
        result = execute(VerificationPlan("runtime", operation="unsupported_device_fact"), "WiFi durumum nasıl?")
    assert result.verified is False


def test_terminal_capability_is_bounded_read_only(app, monkeypatch):
    with app.app_context():
        app.config["TESTING"] = False
        plan = deterministic_plan("Terminalden projeyi listele")
        result = execute(plan, "Terminalden projeyi listele")
        denied = execute(VerificationPlan("terminal", operation="shell"), "rm -rf /")
        app.config["TESTING"] = True
    assert plan.tool == "terminal"
    assert result.verified is True
    assert result.tool == "terminal:list_project"
    assert denied.verified is False
    assert "bounded" in denied.summary.lower() or "unsupported" in denied.summary.lower()


def test_country_clock_questions_use_saatkac_and_legacy_runtime_clock_stays_disabled(app, monkeypatch):
    page = b'''<title>Almanya'da saat ka\xc3\xa7 - SaatKac.info.tr</title>
    <time id="clock">19:03:03</time><script>uT="Almanya: "; zone_id='Europe/Berlin';</script>'''
    requested = []

    class Response:
        encoding = "utf-8"

        def __init__(self, status_code, body=b"", location=None):
            self.status_code = status_code
            self.body = body
            self.headers = {"Content-Length": str(len(body))}
            if location:
                self.headers["Location"] = location

        def iter_content(self, chunk_size=32768):
            yield self.body

        def close(self):
            return None

    def get(url, *args, **kwargs):
        requested.append(url)
        if len(requested) == 1:
            return Response(302, location="/Germany")
        return Response(200, page)

    monkeypatch.setattr("app.services.verification.requests.get", get)
    with app.app_context():
        app.config["TESTING"] = False
        app.config["VERIFICATION_WEB_ENABLED"] = True
        try:
            plan = deterministic_plan("Almanya'da saat kaç?")
            result = execute(plan, "Almanya'da saat kaç?")
            legacy = execute(VerificationPlan("runtime", operation="clock"), "Şu an saat kaç?")
        finally:
            app.config["TESTING"] = True
    assert plan == VerificationPlan("web", "saatkac_country", query="almanya", reason="Country time from SaatKac.info.tr")
    assert result.verified is True
    assert result.tool == "web:saatkac"
    evidence = json.loads(result.evidence)
    assert evidence["source"] == "saatkac.info.tr"
    assert evidence["sourceUrl"] == "https://saatkac.info.tr/Germany"
    assert evidence["location"] == "Almanya"
    assert evidence["currentTime"] == "19:03:03"
    assert evidence["timeZone"] == "Europe/Berlin"
    assert direct_answer(result, "tr") == "Almanya için saat 19:03:03."
    assert requested == ["https://saatkac.info.tr/?q=almanya", "https://saatkac.info.tr/Germany"]
    assert legacy.verified is False


def test_country_clock_plans_extract_aliases_typos_and_default_country(app):
    with app.app_context():
        app.config["TESTING"] = False
        try:
            default = deterministic_plan("Şu an saat kaç?")
            typo = deterministic_plan("Saaat kac Almnya?")
            us = deterministic_plan("ABD'de saat kaç?")
            uk = deterministic_plan("İngiltere'de saat kaç?")
            korea = deterministic_plan("Güney Kore'de şu an saat kaç?")
            date = deterministic_plan("Bugünün tarihi ne?")
        finally:
            app.config["TESTING"] = True
    assert default == VerificationPlan("web", "saatkac_country", query="Türkiye", reason="Country time from SaatKac.info.tr")
    assert typo.operation == "saatkac_country" and typo.query == "almnya"
    assert us.query == "Amerika Birleşik Devletleri"
    assert uk.query == "Birleşik Krallık"
    assert korea.query == "Güney Kore"
    assert date.tool == "web" and date.operation is None


def test_saatkac_country_source_fails_closed_on_unsafe_or_wrong_resolution(app, monkeypatch):
    class Response:
        encoding = "utf-8"

        def __init__(self, status_code, body=b"", location=None):
            self.status_code = status_code
            self.body = body
            self.headers = {"Content-Length": str(len(body))}
            if location:
                self.headers["Location"] = location

        def iter_content(self, chunk_size=32768):
            yield self.body

        def close(self):
            return None

    with app.app_context():
        app.config["VERIFICATION_WEB_ENABLED"] = True
        monkeypatch.setattr("app.services.verification.requests.get", lambda *args, **kwargs: Response(302, location="https://evil.example/time"))
        unsafe = execute(VerificationPlan("web", "saatkac_country", query="Almanya"), "Almanya'da saat kaç?")

        page = b'''<title>Marshall Adalari'nda saat kac - SaatKac.info.tr</title>
        <time id="clock">05:08:27</time><script>uT="Marshall Adalari: "; zone_id='Pacific/Kwajalein';</script>'''
        responses = iter((Response(302, location="/Marshall_Islands"), Response(200, page)))
        monkeypatch.setattr("app.services.verification.requests.get", lambda *args, **kwargs: next(responses))
        wrong = execute(VerificationPlan("web", "saatkac_country", query="mars"), "Mars'ta saat kaç?")

    assert unsafe.verified is False
    assert "unsafe redirect" in unsafe.summary.lower()
    assert wrong.verified is False
    assert "different location" in wrong.summary.lower()


def test_saatkac_accepts_equivalent_country_alias_returned_by_source(app, monkeypatch):
    page = '''<title>İngiltere'de saat kaç - SaatKac.info.tr</title>
    <time id="clock">18:42:10</time><script>uT="İngiltere: "; zone_id='Europe/London';</script>'''.encode()

    class Response:
        encoding = "utf-8"

        def __init__(self, status_code, body=b"", location=None):
            self.status_code = status_code
            self.body = body
            self.headers = {"Content-Length": str(len(body))}
            if location:
                self.headers["Location"] = location

        def iter_content(self, chunk_size=32768):
            yield self.body

        def close(self):
            return None

    responses = iter((Response(302, location="/United_Kingdom"), Response(200, page)))
    monkeypatch.setattr("app.services.verification.requests.get", lambda *args, **kwargs: next(responses))
    with app.app_context():
        app.config["VERIFICATION_WEB_ENABLED"] = True
        result = execute(VerificationPlan("web", "saatkac_country", query="Birleşik Krallık"), "İngiltere'de saat kaç?")

    assert result.verified is True
    evidence = json.loads(result.evidence)
    assert evidence["location"] == "İngiltere"
    assert evidence["sourceUrl"] == "https://saatkac.info.tr/United_Kingdom"


def test_verified_chat_answers_country_clock_directly_without_provider(app, monkeypatch):
    page = b'''<title>Fransa'da saat ka\xc3\xa7 - SaatKac.info.tr</title>
    <time id="clock">18:42:10</time><script>uT="Fransa: "; zone_id='Europe/Paris';</script>'''

    class Response:
        status_code = 200
        headers = {"Content-Length": str(len(page))}
        encoding = "utf-8"

        def iter_content(self, chunk_size=32768):
            yield page

        def close(self):
            return None

    calls = []
    monkeypatch.setattr("app.services.verification.requests.get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(chat, "adapter_call", lambda *args, **kwargs: calls.append((args, kwargs)))
    with app.app_context():
        app.config["TESTING"] = False
        app.config["VERIFICATION_WEB_ENABLED"] = True
        try:
            answer = chat._verified_complete(SimpleNamespace(id="provider"), [{"role": "user", "content": "Fransa'da saat kaç?"}], "Fransa'da saat kaç?", "tr")
        finally:
            app.config["TESTING"] = True
    assert answer == "Fransa için saat 18:42:10."
    assert calls == []


def test_public_chat_api_answers_named_country_from_saatkac(user_client, app, monkeypatch):
    page = b'''<title>Japonya'da saat ka\xc3\xa7 - SaatKac.info.tr</title>
    <time id="clock">02:42:10</time><script>uT="Japonya: "; zone_id='Asia/Tokyo';</script>'''

    class Response:
        status_code = 200
        headers = {"Content-Length": str(len(page))}
        encoding = "utf-8"

        def iter_content(self, chunk_size=32768):
            yield page

        def close(self):
            return None

    requested = []

    def get(url, *args, **kwargs):
        requested.append(url)
        return Response()

    post_json(user_client, "/api/v1/providers", {
        "name": "Mock AI",
        "kind": "ai",
        "adapter": "mock",
        "apiKey": "sk-secret1234567890abcd",
        "model": "mock-1",
        "enabled": True,
        "isDefault": True,
        "config": {"reply": "provider output must not replace sourced time"},
    })
    patch_json(user_client, "/api/v1/settings", {"locale": "tr"})
    monkeypatch.setattr("app.services.verification.requests.get", get)
    monkeypatch.setattr(chat, "adapter_call", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider must not be called")))
    app.config["TESTING"] = False
    app.config["VERIFICATION_WEB_ENABLED"] = True
    try:
        response = post_json(user_client, "/api/v1/chat/messages", {"message": "Japonya'da saat kaç?", "requestId": "saatkac-japan"})
    finally:
        app.config["TESTING"] = True

    assert response.status_code == 201
    assert response.get_json()["messages"][-1]["content"] == "Japonya için saat 02:42:10."
    assert requested == ["https://saatkac.info.tr/?q=japonya"]
