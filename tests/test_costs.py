"""Test del modello dei costi con prezzi finti (non sono prezzi reali)."""
import json
from pathlib import Path

import pytest

from nihongo_agent.costs import PRICE_KEYS, check_inputs, monthly_costs

INPUTS_PATH = Path(__file__).resolve().parents[1] / "docs" / "cost_inputs.json"


def fake_inputs(**price_overrides):
    inputs = json.loads(INPUTS_PATH.read_text(encoding="utf-8"))
    inputs["prices"] = {k: 1.0 for k in PRICE_KEYS} | price_overrides
    inputs["free_grants"]["log_analytics_free_gb"] = 5
    return inputs


def test_missing_prices_are_listed():
    inputs = fake_inputs()
    inputs["prices"]["registry_month"] = None
    with pytest.raises(ValueError, match="registry_month"):
        check_inputs(inputs)


def test_free_grant_covers_one_learner():
    zero = {k: 0.0 for k in PRICE_KEYS}
    inputs = fake_inputs(**zero | {"container_apps_vcpu_second": 1.0, "container_apps_gib_second": 1.0})
    r = monthly_costs(inputs, learners=1)
    # 12 sessioni x 20 minuti x 0,5 vCPU = 7.200 vCPU-s, sotto i 180.000 gratuiti
    assert r["vcpu_seconds"] == 7200 and r["parts"]["Container Apps"] == 0


def test_llm_cost_formula():
    zero = {k: 0.0 for k in PRICE_KEYS}
    inputs = fake_inputs(**zero | {"gemini_input_per_million": 1.0})
    r = monthly_costs(inputs, learners=1)
    assert r["questions"] == 180
    assert r["parts"]["Gemini API"] == pytest.approx(180 * 1242 / 1e6)


def test_ru_sensitivity_scales_only_cosmos_requests():
    zero = {k: 0.0 for k in PRICE_KEYS}
    inputs = fake_inputs(**zero | {"cosmos_serverless_per_million_ru": 1.0})
    base, worst = monthly_costs(inputs, 30), monthly_costs(inputs, 30, ru_factor=10)
    assert worst["parts"]["Cosmos DB"] == pytest.approx(10 * base["parts"]["Cosmos DB"])