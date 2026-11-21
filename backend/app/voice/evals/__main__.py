"""Evals модуля «Голос»: чистка тексту + витяг mode/radius, і (опційно) розпізнавання аудіо.

  uv run python -m app.voice.evals --text --delay 7      # лише LLM-чистка на текстах кейсів
  uv run python -m app.voice.evals --synthetic            # озвучка голосом macOS «Lesya» → Whisper → чистка
  uv run python -m app.voice.evals --audio-dir <папка>   # справжні записи: файли <id>.m4a/.webm/...

Кейс пройдено, якщо: усі must_contain є в очищеному тексті, жодного must_not_contain, mode і radius_km збігаються.
Результати: app/voice/evals/results/voice_<suite>.json і .md (з прикладами помилок — для слайда Evals).
"""

import argparse
import asyncio
import json
import re
import statistics
import subprocess
import time
from pathlib import Path

from app.voice.cleanup import clean_text
from app.voice.errors import VoiceError
from app.voice.stt import transcribe

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.json"
RESULTS = HERE / "results"
SYNTH_DIR = HERE / "audio" / "synthetic"
AUDIO_EXT = (".m4a", ".webm", ".mp3", ".wav", ".ogg", ".mp4", ".aac")

NUM_WORD_RE = re.compile(
    r"^(\d+([.,]\d+)?|пів\w*|один\w*|одна|одну|два|дві|двох|три|трьох|трьохсот|чотир\w*|п'ят\w*|шіст\w*|шість|сім\w*|"
    r"вісім\w*|дев'ят\w*|десят\w*|десяток|десятки|сто|двісті|триста|сімсот|кілограм\w*|кіло|грам\w*|літр\w*|"
    r"гривень|грн|кг|г|л|мл|шт|штук\w*|кілометр\w*|метр\w*|км|м)$"
)


def norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("ʼ", "'")
    return re.sub(r"(\d)\.(\d)", r"\1,\2", s)


def words_for_wer(s: str) -> list[str]:
    toks = re.findall(r"[\w']+", norm(s))
    return [t for t in toks if not NUM_WORD_RE.match(t)]  # числа Whisper пише то словами, то цифрами


def wer(ref: str, hyp: str) -> float:
    r, h = words_for_wer(ref), words_for_wer(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / max(1, len(r))


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


async def run(cases: list[dict], audio_dir: Path | None, delay_s: float = 0.0) -> list[dict]:
    rows = []
    for c in cases:
        if rows and (delay_s or audio_dir):
            await asyncio.sleep(max(delay_s, AUDIO_DELAY_S if audio_dir else 0))
        row = {"id": c["id"], "spoken": c["spoken"], "expected": {"mode": c["mode"], "radius_km": c["radius_km"]}}
        t0 = time.perf_counter()
        try:
            if audio_dir:
                f = next(
                    (audio_dir / f"{c['id']}{e}" for e in AUDIO_EXT if (audio_dir / f"{c['id']}{e}").exists()), None
                )
                if f is None:
                    continue
                stt = await transcribe(f.read_bytes(), f.name, None)
                t_stt = time.perf_counter() - t0
                res = await clean_text(stt["text"])
                row.update(stt_s=round(t_stt, 2), wer=round(wer(c["spoken"], stt["text"]), 3))
            else:
                res = await clean_text(c["spoken"])
        except VoiceError as e:
            res = {"text": "", "error": e.code}
        row["latency_s"] = round(time.perf_counter() - t0, 2)
        row["result"] = {k: res.get(k) for k in ("raw_text", "text", "mode", "radius_km", "cleanup", "error")}
        row.update(check(c, res))
        rows.append(row)
        flag = "✅" if row["passed"] else "❌"
        print(f"{flag} {c['id']} {row['latency_s']:>5}s  {res.get('text', '')[:70]}")
    return rows


def summarize(rows: list[dict], suite: str) -> dict:
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
    }
    if any("wer" in r for r in rows):
        s["wer_avg"] = statistics.mean(r["wer"] for r in rows if "wer" in r)
    return s


def write_report(rows: list[dict], s: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"voice_{s['suite']}.json").write_text(
        json.dumps({"summary": s, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8"
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
    ]
    if "wer_avg" in s:
        lines.append(f"| WER розпізнавання (без чисел) | {pct(s['wer_avg'])} |")
    fails = [r for r in rows if not r["passed"]]
    if fails:
        lines += ["", "## Помилки", ""]
        for r in fails:
            why = []
            if r["missing"]:
                why.append(f"бракує: {', '.join(r['missing'])}")
            if r["leaked"]:
                why.append(f"лишилось: {', '.join(r['leaked'])}")
            if not r["mode_ok"]:
                why.append(f"mode {r['result']['mode']} ≠ {r['expected']['mode']}")
            if not r["radius_ok"]:
                why.append(f"radius {r['result']['radius_km']} ≠ {r['expected']['radius_km']}")
            lines.append(f"- **{r['id']}** «{r['spoken']}» → «{r['result']['text']}» — {'; '.join(why)}")
    (RESULTS / f"voice_{s['suite']}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", action="store_true")
    g.add_argument("--synthetic", action="store_true")
    g.add_argument("--audio-dir", type=Path)
    ap.add_argument(
        "--delay", type=float, default=0.0, help="пауза між кейсами, с (безкоштовний Groq має ліміт токенів/хв для LLM)"
    )
    args = ap.parse_args()

    cases = json.loads(CASES.read_text(encoding="utf-8"))
    if args.text:
        suite, audio_dir = "text", None
    elif args.synthetic:
        suite, audio_dir = "synthetic_audio", synthesize(cases)
    else:
        suite, audio_dir = "real_audio", args.audio_dir

    rows = asyncio.run(run(cases, audio_dir, args.delay))
    if not rows:
        raise SystemExit("Немає жодного кейсу з аудіо")
    s = summarize(rows, suite)
    write_report(rows, s)
    print(json.dumps(s, ensure_ascii=False, indent=1))
    print(f"→ app/voice/evals/results/voice_{suite}.md")


if __name__ == "__main__":
    main()
