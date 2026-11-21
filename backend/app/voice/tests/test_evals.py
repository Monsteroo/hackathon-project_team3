import json

import pytest

from app.voice.evals import __main__ as evals


def test_real_references_update_expectations_without_changing_scenarios():
    cases = json.loads(evals.CASES.read_text(encoding="utf-8"))
    refs = json.loads(evals.REAL_REFS.read_text(encoding="utf-8"))
    original = {case["id"]: case for case in cases}
    updated = {case["id"]: case for case in evals.apply_refs(cases, refs)}
    assert len(updated) == 28
    assert updated["v06"]["spoken"] == original["v06"]["spoken"]
    assert updated["v06"]["actual"] == refs["v06"]["actual"]
    assert updated["v06"]["must_contain"] == refs["v06"]["must_contain"]
    assert updated["v02"]["mode"] == "walk" and updated["v02"]["radius_km"] == 1.0
    assert "мінерал" in updated["v14"]["must_contain"]
    with pytest.raises(ValueError, match="v02"):
        evals.apply_refs(cases, {key: ref for key, ref in refs.items() if key != "v02"})


def test_wer_recognizes_equivalent_numbers_and_counts_changed_quantities():
    assert evals.wer_counts("Кілограм борошна, два десятки яєць.", "1 кг борошна і 20 яєць.") == (1, 5)
    assert evals.wer_counts("Півтора кіло і 2,5%", "1.5 кг і 5%") == (1, 5)


async def test_audio_eval_uses_actual_text_and_selected_model(tmp_path, monkeypatch):
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"mock recording")

    async def transcribe(body, filename, content_type, *, model):
        assert body == b"mock recording" and filename == "a.m4a"
        assert model == "whisper-large-v3-turbo"
        return {"text": "хліб", "duration_s": 3}

    async def clean_text(raw):
        assert raw == "хліб"
        return {"text": raw, "raw_text": raw}

    monkeypatch.setattr(evals, "transcribe", transcribe)
    monkeypatch.setattr(evals, "clean_text", clean_text)
    case = {
        "id": "a",
        "spoken": "хліб і кава",
        "actual": "хліб",
        "mode": None,
        "radius_km": None,
        "must_contain": ["хліб"],
        "must_not_contain": [],
    }
    rows = await evals.run([case], evals.audio_files([case], tmp_path), 0, "whisper-large-v3-turbo")
    result = evals.summarize(rows, "real_audio", "whisper-large-v3-turbo", uses_refs=True)
    assert result["stt_ok"] == result["passed"] == 1
    assert result["wer_reference"] == "actual" and result["wer"] == 0
    assert result["stt_billed_s"] == 10
    assert result["stt_estimated_cost_usd"] == pytest.approx(10 * 0.04 / 3600)
