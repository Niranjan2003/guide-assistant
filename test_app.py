import pytest

from app import create_app, Question, db


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.test_client() as c:
        yield c


def ask(client, q):
    return client.post("/", data={"question": q})


def test_index_loads(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Ask something" in r.data


def test_answer_has_source_section(client):
    r = ask(client, "How often do I have to meet my thesis supervisor?")
    assert b"from the guide" in r.data
    assert b"Thesis supervision" in r.data
    assert b"once a month" in r.data


def test_out_of_scope_is_refused(client):
    r = ask(client, "What is on the cafeteria lunch menu today?")
    assert b"not in the guide" in r.data


def test_empty_question_is_ignored(client):
    r = ask(client, "   ")
    assert r.status_code == 200
    assert b"from the guide" not in r.data


def test_questions_end_up_in_the_log(client):
    ask(client, "How do I appeal a grade?")
    ask(client, "How much is a parking permit on campus?")
    page = client.get("/log").data
    assert b"2 questions asked" in page
    assert b"1 of them not answered" in page


def test_log_saves_answered_flag(client):
    ask(client, "How do I appeal a grade?")
    q = db.session.execute(db.select(Question)).scalars().first()
    assert q.answered is True
    assert q.section == "Grade appeals"


def test_api_needs_q(client):
    assert client.get("/api/ask").status_code == 400
    data = client.get("/api/ask?q=how do I appeal a grade").get_json()
    assert data["found"] is True


def test_pasted_guide_needs_two_sections(client):
    r = client.post("/guide", data={"guide": "## only one\ntext"}, follow_redirects=True)
    assert b"at least two sections" in r.data


def test_pasted_guide_is_used(client):
    text = "## Parking\nParking costs five euros a day.\n## Gym\nThe gym opens at six."
    client.post("/guide", data={"guide": text})
    data = client.get("/api/ask?q=how much does parking cost").get_json()
    assert data["hits"][0]["title"] == "Parking"


def test_model_failure_falls_back(client, monkeypatch):
    monkeypatch.setenv("LLM_URL", "http://127.0.0.1:9/nothing")
    monkeypatch.setenv("LLM_KEY", "x")
    monkeypatch.setenv("LLM_MODEL", "x")
    r = ask(client, "How do I appeal a grade?")
    assert b"from the guide" in r.data
