from app.models import MemoryItem, Message
from app.services.auto_memory import extract_durable_memories
from tests.conftest import patch_json, post_json


def test_extracts_only_explicit_durable_information():
    assert extract_durable_memories("Python'da listeyi nasıl sıralarım?") == []
    assert extract_durable_memories("Bugün hava nasıl?") == []

    name = extract_durable_memories("Benim adım Mert.")
    assert name == [{"title": "Kullanıcı adı", "content": "Kullanıcının adı: Mert", "category": "personal"}]

    project = extract_durable_memories("Projemin adı Xultron.")
    assert project[0]["category"] == "personal"
    assert "Xultron" in project[0]["content"]

    solution = extract_durable_memories("Sorunu önbelleği temizleyerek çözdüm.")
    assert solution[0]["category"] == "important"
    assert "önbelleği temizleyerek" in solution[0]["content"]


def test_rejects_secrets_even_when_message_looks_memorable():
    assert extract_durable_memories("Karar verdim: API key sk-supersecret123 kullanacağım") == []
    assert extract_durable_memories("Şifrem hunter2, bunu tercih ederim") == []
    assert extract_durable_memories("TC kimlik numaramı profil bilgim olarak hatırla") == []
    assert extract_durable_memories("Tercihim telefonla aranmak, numaram +90 555 123 45 67") == []
    assert extract_durable_memories("Tercihim sağlık durumumu migren olarak saklamak") == []
    assert extract_durable_memories("I prefer deliveries to my address on Pine Street") == []


def test_rejects_questions_quotes_and_conditional_statements():
    assert extract_durable_memories("Benim adım ne?") == []
    assert extract_durable_memories("Can you call me tomorrow?") == []
    assert extract_durable_memories('“Benim adım Ali” dedi') == []
    assert extract_durable_memories("Karar verdim: belki yarın PostgreSQL kullanırım") == []


def test_extracts_multiple_explicit_facts_without_name_overcapture():
    memories = extract_durable_memories("Benim adım Mert ve projemin adı Xultron")
    assert len(memories) == 2
    assert memories[0]["content"] == "Kullanıcının adı: Mert"
    assert memories[1]["content"] == "Aktif proje: Xultron"


def test_chat_automatically_remembers_name_project_and_solution(user_client, app):
    messages = (
        "Benim adım Mert.",
        "Projemin adı Xultron.",
        "Sorunu önbelleği temizleyerek çözdüm.",
    )
    for index, message in enumerate(messages):
        response = post_json(user_client, "/api/v1/chat/messages", {"message": message, "requestId": f"auto-memory-{index}"})
        assert response.status_code == 201

    memories = user_client.get("/api/v1/memory").get_json()["memories"]
    assert {item["category"] for item in memories} == {"personal", "important"}
    assert len(memories) == 3
    assert len(user_client.get("/api/v1/memory?category=personal").get_json()["memories"]) == 2
    assert len(user_client.get("/api/v1/memory?category=important").get_json()["memories"]) == 1

    with app.app_context():
        assert MemoryItem.query.count() == 3


def test_chat_does_not_remember_questions_and_updates_single_value_slots(user_client):
    for index, message in enumerate(("Bugün hava nasıl?", "Benim adım Mert.", "Benim adım Deniz.")):
        response = post_json(user_client, "/api/v1/chat/messages", {"message": message, "requestId": f"selective-{index}"})
        assert response.status_code == 201

    memories = user_client.get("/api/v1/memory").get_json()["memories"]
    assert len(memories) == 1
    assert memories[0]["content"] == "Kullanıcının adı: Deniz"


def test_chat_keeps_multiple_projects_without_duplicate_copies(user_client):
    for index, message in enumerate(("Projemin adı Xultron.", "Projemin adı Atlas.", "Projemin adı Xultron.")):
        response = post_json(user_client, "/api/v1/chat/messages", {"message": message, "requestId": f"projects-{index}"})
        assert response.status_code == 201

    memories = user_client.get("/api/v1/memory").get_json()["memories"]
    assert len(memories) == 2
    assert {item["content"] for item in memories} == {"Aktif proje: Xultron", "Aktif proje: Atlas"}


def test_memory_setting_disables_automatic_capture(user_client):
    patched = patch_json(user_client, "/api/v1/settings", {"memoryEnabled": False})
    assert patched.status_code == 200

    response = post_json(user_client, "/api/v1/chat/messages", {"message": "Benim adım Mert.", "requestId": "memory-off"})
    assert response.status_code == 201
    assert user_client.get("/api/v1/memory").get_json()["memories"] == []


def test_memory_can_remain_selectively_enabled_when_chat_history_is_off(user_client, app):
    patched = patch_json(user_client, "/api/v1/settings", {"conversationHistory": False, "memoryEnabled": True})
    assert patched.status_code == 200

    question = post_json(user_client, "/api/v1/chat/messages", {"message": "Bugün hava nasıl?", "requestId": "private-question"})
    fact = post_json(user_client, "/api/v1/chat/messages", {"message": "Benim adım Mert.", "requestId": "private-fact"})
    assert question.status_code == fact.status_code == 201
    memories = user_client.get("/api/v1/memory").get_json()["memories"]
    assert [item["content"] for item in memories] == ["Kullanıcının adı: Mert"]
    with app.app_context():
        assert Message.query.count() == 0
