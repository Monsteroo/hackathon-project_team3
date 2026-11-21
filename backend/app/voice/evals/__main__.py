"""Evals модуля «Голос»: чистка тексту + витяг mode/radius, і (опційно) розпізнавання аудіо.

  uv run python -m app.voice.evals --text --delay 7      # лише LLM-чистка на текстах кейсів
  uv run python -m app.voice.evals --synthetic            # озвучка голосом macOS «Lesya» → Whisper → чистка
  uv run python -m app.voice.evals --audio-dir <папка> --refs --stt-model whisper-large-v3 --delay 3

Кейс пройдено, якщо: усі must_contain є в очищеному тексті, жодного must_not_contain, mode і radius_km збігаються.
Результати: app/voice/evals/results/voice_<suite>.json і .md (з прикладами помилок — для слайда Evals).
"""

import argparse
import asyncio
import json
import mimetypes
import re
import statistics
import subprocess
import time
from pathlib import Path

from app.config import get_settings
from app.voice.cleanup import clean_text
from app.voice.errors import VoiceError
from app.voice.numbers import normalize_numbers
from app.voice.stt import transcribe

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.json"
REAL_REFS = HERE / "real_refs.json"
RESULTS = HERE / "results"
SYNTH_DIR = HERE / "audio" / "synthetic"
AUDIO_EXT = (".m4a", ".webm", ".mp3", ".wav", ".ogg", ".mp4", ".aac")
STT_PRICE_PER_HOUR = {"whisper-large-v3": 0.111, "whisper-large-v3-turbo": 0.04}
MIN_BILLED_SECONDS = 10
REFERENCE_OVERRIDES = {"mode", "radius_km", "must_contain", "must_not_contain"}
WER_TOKEN_RE = re.compile(r"\d+(?:,\d+)?|[^\W\d_]+(?:'[^\W\d_]+)*|%")


def norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("ʼ", "'")
    return re.sub(r"(\d)\.(\d)", r"\1,\2", s)


def words_for_wer(s: str) -> list[str]:
    return WER_TOKEN_RE.findall(norm(normalize_numbers(s)))


def wer_counts(ref: str, hyp: str) -> tuple[int, int]:
    r, h = words_for_wer(ref), words_for_wer(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)], len(r)


def has_word(text: str, phrase: str) -> bool:
    return re.search(r"(?<![\w'])" + re.escape(norm(phrase)) + r"(?![\w'])", norm(text)) is not None


def check(case: dict, res: dict) -> dict:
    text = norm(res.get("text", ""))
    missing = [m for m in case["must_contain"] if norm(m) not in text]
    leaked = [m for m in case["must_not_contain"] if has_word(text, m)]
    mode_ok = res.get("mode") == case["mode"]
    r_exp, r_got = case["radius_km"], res.get("radius_km")
    radius_ok = (r_exp is None and r_got is None) or (
        r_exp is not None and r_got is not None and abs(r_exp - r_got) < 0.01
    )
    return {
        "missing": missing,
        "leaked": leaked,
        "mode_ok": mode_ok,
        "radius_ok": radius_ok,
        "passed": not missing and not leaked and mode_ok and radius_ok,
    }


def synthesize(cases: list[dict]) -> Path:
    SYNTH_DIR.mkdir(parents=True, exist_ok=True)
    for c in cases:
        out = SYNTH_DIR / f"{c['id']}.m4a"
        if out.exists():
            continue
        aiff = SYNTH_DIR / f"{c['id']}.aiff"
        subprocess.run(["say", "-v", "Lesya", "-o", str(aiff), c["spoken"]], check=True)
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(aiff), str(out)], check=True)
        aiff.unlink()
    return SYNTH_DIR


AUDIO_DELAY_S = 3.2  # безкоштовний Groq Whisper: 20 запитів/хв


def apply_refs(cases: list[dict], refs: dict) -> list[dict]:
    expected = {c["id"] for c in cases}
    if set(refs) != expected:
        raise ValueError(f"Refs: missing {sorted(expected - refs.keys())}, unknown {sorted(refs.keys() - expected)}")
    updated = []
    for case in cases:
        ref = refs[case["id"]]
        if (
            not isinstance(ref, dict)
            or not isinstance(ref.get("actual"), str)
            or not ref["actual"].strip()
            or ref.keys() - (REFERENCE_OVERRIDES | {"actual"})
        ):
            raise ValueError(f"Invalid reference for {case['id']}")
        updated.append({**case, **ref})
    return updated


def audio_files(cases: list[dict], audio_dir: Path) -> dict[str, Path]:
    files = {}
    for case in cases:
        case_id = case["id"]
        matches = [audio_dir / f"{case_id}{ext}" for ext in AUDIO_EXT if (audio_dir / f"{case_id}{ext}").is_file()]
        if len(matches) != 1:
            raise ValueError(f"Expected one recording for {case_id} in {audio_dir}, found {len(matches)}")
        files[case_id] = matches[0]
    return files


async def run(cases: list[dict], files: dict[str, Path] | None, delay_s: float, stt_model: str | None) -> list[dict]:
    rows = []
    for c in cases:
        if rows and (delay_s or files):
            await asyncio.sleep(max(delay_s, AUDIO_DELAY_S if files else 0))
        row = {
            "id": c["id"],
            "spoken": c["spoken"],
            "expected": {k: c[k] for k in sorted(REFERENCE_OVERRIDES)},
        }
        if "actual" in c:
            row["actual"] = c["actual"]
        t0 = time.perf_counter()
        try:
            if files is not None:
                f = files[c["id"]]
                stt = await transcribe(f.read_bytes(), f.name, mimetypes.guess_type(f.name)[0], model=stt_model)
                t_stt = time.perf_counter() - t0
                edits, reference_words = wer_counts(c.get("actual", c["spoken"]), stt["text"])
                res = await clean_text(stt["text"])
                row.update(
                    stt_s=round(t_stt, 3), duration_s=stt["duration_s"], wer_edits=edits, wer_words=reference_words
                )
            else:
                res = await clean_text(c["spoken"])
        except VoiceError as e:
            res = {"text": "", "error": e.code}
        row["latency_s"] = round(time.perf_counter() - t0, 3)
        row["result"] = {k: res.get(k) for k in ("raw_text", "text", "mode", "radius_km", "cleanup", "error")}
        row.update(check(c, res))
        if res.get("error"):
            row["passed"] = False
        rows.append(row)
        flag = "✅" if row["passed"] else "❌"
        print(f"{flag} {c['id']} {row['latency_s']:>5}s  {res.get('text', '')[:70]}")
    return rows


def summarize(rows: list[dict], suite: str, stt_model: str | None, uses_refs: bool) -> dict:
    n = len(rows)
    s = {
        "suite": suite,
        "cases": n,
        "passed": sum(r["passed"] for r in rows),
        "mode_acc": sum(r["mode_ok"] for r in rows) / n,
        "radius_acc": sum(r["radius_ok"] for r in rows) / n,
        "items_kept": sum(not r["missing"] for r in rows) / n,
        "fillers_removed": sum(not r["leaked"] for r in rows) / n,
        "guard_rejected": sum((r["result"].get("cleanup") or {}).get("guard") == "rejected" for r in rows),
        "latency_p50_s": statistics.median(r["latency_s"] for r in rows),
        "latency_max_s": max(r["latency_s"] for r in rows),
        "llm_tokens_avg": statistics.mean((r["result"].get("cleanup") or {}).get("tokens", 0) for r in rows),
        "fallback_model_used": sum(
            (r["result"].get("cleanup") or {}).get("model") == "openai/gpt-oss-120b" for r in rows
        ),
        "llm_unavailable": sum((r["result"].get("cleanup") or {}).get("guard") == "llm_unavailable" for r in rows),
    }
    if stt_model:
        recognized = [r for r in rows if "stt_s" in r]
        s.update(stt_model=stt_model, stt_ok=len(recognized), wer_reference="actual" if uses_refs else "spoken")
        if recognized:
            words = sum(r["wer_words"] for r in recognized)
            s["wer"] = sum(r["wer_edits"] for r in recognized) / words if words else None
            s["stt_p50_s"] = statistics.median(r["stt_s"] for r in recognized)
            s["stt_max_s"] = max(r["stt_s"] for r in recognized)
        if stt_model in STT_PRICE_PER_HOUR and len(recognized) == n and all(r["duration_s"] for r in recognized):
            billed_s = sum(max(MIN_BILLED_SECONDS, r["duration_s"]) for r in recognized)
            s["stt_billed_s"] = billed_s
            s["stt_price_per_hour_usd"] = STT_PRICE_PER_HOUR[stt_model]
            s["stt_estimated_cost_usd"] = billed_s * STT_PRICE_PER_HOUR[stt_model] / 3600
    return s


def write_report(rows: list[dict], s: dict, output_dir: Path, filename: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{filename}.json").write_text(
        json.dumps({"summary": s, "rows": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    pct = lambda v: f"{v * 100:.0f}%"  # noqa: E731
    lines = [
        f"# Evals голосу — {s['suite']}",
        "",
        f"**{s['passed']}/{s['cases']} кейсів пройдено** "
        "(усі продукти збережені, паразити прибрані, mode і радіус вірні)",
        "",
        "| Метрика | Значення |",
        "|---|---|",
        f"| Режим (пішки/авто) | {pct(s['mode_acc'])} |",
        f"| Радіус | {pct(s['radius_acc'])} |",
        f"| Усі продукти й числа збережені | {pct(s['items_kept'])} |",
        f"| Слова-паразити прибрані | {pct(s['fillers_removed'])} |",
        f"| Захист від галюцинацій спрацював | {s['guard_rejected']} раз(и) |",
        f"| Затримка p50 / max | {s['latency_p50_s']:.2f} с / {s['latency_max_s']:.2f} с |",
        f"| Токенів LLM на запит (сер.) | {s['llm_tokens_avg']:.0f} |",
        f"| Запасна модель (429 / збій основної) | {s['fallback_model_used']} раз(и) |",
        f"| Чистка без LLM через збій обох моделей | {s['llm_unavailable']} раз(и) |",
    ]
    if "stt_model" in s:
        lines.append(f"| Розпізнано моделлю `{s['stt_model']}` | {s['stt_ok']}/{s['cases']} |")
    if s.get("wer") is not None:
        lines.append(f"| WER розпізнавання (еталон `{s['wer_reference']}`) | {s['wer']:.1%} |")
        lines.append(f"| Затримка STT p50 / max | {s['stt_p50_s']:.3f} с / {s['stt_max_s']:.3f} с |")
    if "stt_estimated_cost_usd" in s:
        lines.append(f"| Оцінка вартості STT, мін. 10 с за запис | ${s['stt_estimated_cost_usd']:.5f} |")
    fails = [r for r in rows if not r["passed"]]
    if fails:
        lines += ["", "## Помилки", ""]
        for r in fails:
            why = []
            if error := r["result"].get("error"):
                lines.append(f"- **{r['id']}** — `{error}`")
                continue
            if r["missing"]:
                why.append(f"бракує: {', '.join(r['missing'])}")
            if r["leaked"]:
                why.append(f"лишилось: {', '.join(r['leaked'])}")
            if not r["mode_ok"]:
                why.append(f"mode {r['result']['mode']} ≠ {r['expected']['mode']}")
            if not r["radius_ok"]:
                why.append(f"radius {r['result']['radius_km']} ≠ {r['expected']['radius_km']}")
            lines.append(
                f"- **{r['id']}** «{r.get('actual', r['spoken'])}» → «{r['result']['text']}» — {', '.join(why)}"
            )
    (output_dir / f"{filename}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", action="store_true")
    g.add_argument("--synthetic", action="store_true")
    g.add_argument("--audio-dir", type=Path)
    ap.add_argument(
        "--refs", nargs="?", const=REAL_REFS, type=Path, help="еталони живого голосу, типово real_refs.json"
    )
    ap.add_argument("--stt-model", choices=STT_PRICE_PER_HOUR, help="модель Whisper для аудіопрогону")
    ap.add_argument("--output-dir", type=Path, default=RESULTS / "current", help="папка звітів")
    ap.add_argument(
        "--delay", type=float, default=0.0, help="пауза між кейсами, с (безкоштовний Groq має ліміт токенів/хв для LLM)"
    )
    args = ap.parse_args()
    if args.refs and not args.audio_dir:
        ap.error("--refs requires --audio-dir")
    if args.text and args.stt_model:
        ap.error("--stt-model requires an audio run")
    if not args.delay >= 0:
        ap.error("--delay must be non-negative")
    settings = get_settings()
    if not settings.groq_api_key:
        ap.error("Groq API key is missing from backend settings")

    cases = json.loads(CASES.read_text(encoding="utf-8"))
    if args.text:
        suite, audio_dir = "text", None
    elif args.synthetic:
        suite, audio_dir = "synthetic_audio", synthesize(cases)
    else:
        suite, audio_dir = "real_audio", args.audio_dir

    try:
        if args.refs:
            cases = apply_refs(cases, json.loads(args.refs.read_text(encoding="utf-8")))
        files = audio_files(cases, audio_dir) if audio_dir is not None else None
    except (ValueError, OSError) as exc:
        ap.error(str(exc))
    stt_model = (args.stt_model or settings.groq_stt_model) if files is not None else None
    rows = asyncio.run(run(cases, files, args.delay, stt_model))
    s = summarize(rows, suite, stt_model, bool(args.refs))
    filename = f"voice_{suite}" + (f"_{stt_model}" if stt_model else "")
    write_report(rows, s, args.output_dir, filename)
    print(json.dumps(s, ensure_ascii=False, indent=1))
    print(f"→ {args.output_dir / (filename + '.md')}")
    if s.get("stt_ok", s["cases"]) == 0 or s["llm_unavailable"] == s["cases"]:
        raise SystemExit("Groq did not complete the suite")


if __name__ == "__main__":
    main()
