"""Проганяє evals/cases.yaml через крок Parse і рахує точність, час і вартість.

Запуск (з backend/):
  uv run python -m app.agent.evals.run_eval --rules       # безкоштовна базова лінія без LLM
  uv run python -m app.agent.evals.run_eval               # провайдер і модель з backend/.env
  uv run python -m app.agent.evals.run_eval --provider anthropic --model claude-haiku-5-5
  uv run python -m app.agent.evals.run_eval --provider openai_compat --model gemini-flash-lite-latest --delay 5

Кожен виклик LLM платний (крім безкоштовних тарифів). Результати: app/agent/evals/results/*.json.
"""

import argparse
import asyncio
import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml

from app.agent import llm
from app.agent.evals.grader import grade
from app.agent.parser import parse_rules
from app.config import get_settings

HERE = Path(__file__).parent

# $ за 1M токенів (вхід, вихід). Невідомі моделі (напр. безкоштовний Gemini) рахуються як 0.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", action="store_true", help="лише парсер на правилах, без LLM")
    ap.add_argument("--provider", choices=["anthropic", "openai_compat"])
    ap.add_argument("--model")
    ap.add_argument("--delay", type=float, default=0, help="пауза між запитами, с (для безкоштовних лімітів)")
    ap.add_argument("--only", help="лише кейси, id яких починається з цього префікса")
    args = ap.parse_args()
    settings = get_settings()

    if args.provider:
        settings.llm_provider = args.provider
    if args.model:
        if settings.llm_provider == "anthropic":
            settings.anthropic_model = args.model
        else:
            settings.llm_model = args.model
    model = (
        "rules"
        if args.rules
        else (settings.anthropic_model if settings.llm_provider == "anthropic" else settings.llm_model)
    )
    if not args.rules and not llm.llm_enabled():
        raise SystemExit(f"Немає ключа для провайдера {settings.llm_provider} у backend/.env (або запустіть з --rules)")

    cases = yaml.safe_load((HERE / "cases.yaml").read_text())
    if args.only:
        cases = [c for c in cases if c["id"].startswith(args.only)]

    price_in, price_out = PRICES.get(model, (0.0, 0.0))
    results = []
    for n, case in enumerate(cases, 1):
        if n > 1 and args.delay:
            await asyncio.sleep(args.delay)
        llm.LAST_USAGE.clear()
        t = time.time()
        error = None
        try:
            parsed = parse_rules(case["text"]) if args.rules else await llm.parse_with_llm(case["text"])
        except Exception as e:  # помилка моделі = кейс не пройдено
            parsed, error = None, f"{type(e).__name__}: {str(e)[:200]}"
        latency = time.time() - t

        checks = grade(parsed, case["expect"]) if parsed else []
        passed = parsed is not None and all(ch.ok for ch in checks)
        usage = dict(llm.LAST_USAGE)
        cost = usage.get("input_tokens", 0) * price_in / 1e6 + usage.get("output_tokens", 0) * price_out / 1e6
        results.append(
            {
                "id": case["id"],
                "category": case["category"],
                "text": case["text"],
                "passed": passed,
                "error": error,
                "latency_s": round(latency, 2),
                "usage": usage,
                "cost_usd": round(cost, 6),
                "failed_checks": [{"check": ch.name, "detail": ch.detail} for ch in checks if not ch.ok],
                "parsed": parsed.model_dump() if parsed else None,
            }
        )
        mark = "✓" if passed else "✗"
        print(f"{mark} {case['id']:<10} {latency:5.1f}s  {case['text']}")

    # ---------- Підсумок ----------
    total = len(results)
    ok = sum(r["passed"] for r in results)
    by_cat = defaultdict(lambda: [0, 0])
    for r in results:
        by_cat[r["category"]][0] += r["passed"]
        by_cat[r["category"]][1] += 1
    llm_calls = [r for r in results if r["usage"]]
    avg_latency = sum(r["latency_s"] for r in results) / total
    avg_cost = sum(r["cost_usd"] for r in llm_calls) / len(llm_calls) if llm_calls else 0

    print(f"\nМодель: {model}")
    print(
        f"Пройдено: {ok}/{total} ({ok / total:.0%})   Середній час: {avg_latency:.1f} с   "
        f"Середня вартість: ${avg_cost:.5f}/запит   Помилок API: {sum(1 for r in results if r['error'])}"
    )
    print("\nЗа категоріями:")
    for cat, (p, t) in by_cat.items():
        print(f"  {cat:<20} {p}/{t}")
    failed = [r for r in results if not r["passed"]]
    if failed:
        print("\nНе пройдено:")
        for r in failed:
            reasons = r["error"] or "; ".join(f"{f['check']} ({f['detail']})" for f in r["failed_checks"])
            print(f"  {r['id']:<10} «{r['text']}»\n             → {reasons}")

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}_{model}.json"
    out.write_text(
        json.dumps(
            {
                "model": model,
                "passed": ok,
                "total": total,
                "avg_latency_s": round(avg_latency, 2),
                "avg_cost_usd": round(avg_cost, 6),
                "by_category": {k: {"passed": p, "total": t} for k, (p, t) in by_cat.items()},
                "results": results,
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    print(f"\nДеталі: {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    asyncio.run(main())
