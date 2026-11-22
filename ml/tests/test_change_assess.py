from fastapi.testclient import TestClient

from investwatch_ml import api, change_assess, llm

CHANGE = {"id": "chg_1", "entity_id": "xtb", "url": "https://www.xtb.com/pl", "added_lines": ["77% rachunków"],
          "removed_lines": ["76% rachunków"],
          "style_changes": [{"text": "Kontrakty CFD", "viewport": "1366x768", "field": "font_size_px", "before": 14, "after": 9},
                            {"text": "Kontrakty CFD", "viewport": "390x844", "field": "font_size_px", "before": 14, "after": 9}]}


def test_parse_and_normalize():
    raw = '```json\n[{"id": "chg_1", "relevant": "true", "category": "Risk_Info", "rules": ["4", "R5", "R04", "R12A", "R99"], ' \
          '"reason": "Czcionka „Kontrakty CFD” 14→9 px."}]\n```'
    [res] = llm.parse(raw, "relevant")
    out = change_assess.normalize(res)
    assert out == {"relevant": True, "category": "risk_info", "reason": "Czcionka „Kontrakty CFD” 14→9 px.",
                   "rules": ["R04", "R05", "R12a"], "model": llm.MODEL}
    assert change_assess.normalize({"relevant": False, "category": "nav", "rules": ["R03"], "reason": "Ray ID"})["rules"] == []
    assert change_assess.normalize({"relevant": False, "category": "other", "reason": ""}) is None
    assert change_assess.normalize({"category": "other", "reason": "x"}) is None


def test_parse_objects_without_array():
    text = 'Wynik: {"id": "a", "relevant": false, "reason": "x"} {"id": "b", "relevant": true, "reason": "y"}'
    assert [x["id"] for x in llm.parse(text, "relevant")] == ["a", "b"]


def test_build_input_dedupes_viewports():
    inp = change_assess.build_input(CHANGE)
    assert len(inp["style_changes"]) == 1 and inp["added_lines"] == ["77% rachunków"]


def test_none_backend_returns_null(monkeypatch):
    monkeypatch.setattr(llm, "BACKEND", "none")
    r = TestClient(api.app).post("/assess/change", json={"changes": [CHANGE, {**CHANGE, "id": "chg_2"}]})
    assert r.status_code == 200
    assert r.json() == {"results": [{"id": "chg_1", "assessment": None}, {"id": "chg_2", "assessment": None}]}


def test_llm_failure_returns_null(monkeypatch):
    monkeypatch.setattr(llm, "BACKEND", "groq")

    def boom(*a, **k):
        raise RuntimeError("Groq: limit zapytań")

    monkeypatch.setattr(llm, "_call", boom)
    assert change_assess.assess([CHANGE, {**CHANGE, "id": "chg_2"}]) == {"chg_1": None, "chg_2": None}
