from __future__ import annotations

import json

import pytest

from archive.report_scripts.generate_v8_1_reports import (
    generate_model_provider_operator_repair_recommendations_v1,
)


def test_repair_recommendations_do_not_include_secret_values():
    resolution_report = {
        "deepseek_v4_flash": {
            "status": "OPERATOR_MODEL_CONFIG_REQUIRED",
            "api_key_present": True,
            "api_base_present": True,
            "configured_model": "unknown-model",
            "resolved_model": None,
            "error_category": "MODEL_NOT_FOUND",
        },
        "minimax_m3": {
            "status": "OPERATOR_MODEL_CONFIG_REQUIRED",
            "api_key_present": True,
            "api_base_present": True,
            "configured_model": "unknown-model",
            "resolved_model": None,
            "error_category": "MODEL_NOT_FOUND",
        },
    }
    report = generate_model_provider_operator_repair_recommendations_v1(resolution_report)
    text = json.dumps(report, default=str)

    assert report["verdict"] == "OPERATOR_ACTION_REQUIRED"
    assert len(report["recommendations"]) == 2
    for rec in report["recommendations"]:
        assert rec["api_key_present"] is True
        assert rec["base_url_present"] is True
        assert "fields_to_review" in rec
        assert "example_values" in rec
        # Example values must be placeholders only.
        assert rec["example_values"][rec["api_key_env"]] in ("sk-...", None) or "..." in rec["example_values"][rec["api_key_env"]]
    assert "sk-" not in text or "sk-..." in text


def test_repair_recommendations_skip_live_proven_providers():
    resolution_report = {
        "deepseek_v4_flash": {
            "status": "LIVE_PROVEN",
            "api_key_present": True,
            "api_base_present": True,
            "configured_model": "deepseek-chat",
            "resolved_model": "deepseek-chat",
            "error_category": None,
        },
        "minimax_m3": {
            "status": "OPERATOR_MODEL_CONFIG_REQUIRED",
            "api_key_present": True,
            "api_base_present": True,
            "configured_model": "unknown-model",
            "resolved_model": None,
            "error_category": "MODEL_NOT_FOUND",
        },
    }
    report = generate_model_provider_operator_repair_recommendations_v1(resolution_report)
    providers = {r["provider"] for r in report["recommendations"]}
    assert "deepseek_v4_flash" not in providers
    assert "minimax_m3" in providers


def test_repair_recommendations_use_placeholders_only():
    resolution_report = {
        "deepseek_v4_flash": {
            "status": "OPERATOR_MODEL_CONFIG_REQUIRED",
            "api_key_present": True,
            "api_base_present": True,
            "configured_model": "",
            "resolved_model": None,
            "error_category": "ENDPOINT_NOT_FOUND",
        },
    }
    report = generate_model_provider_operator_repair_recommendations_v1(resolution_report)
    rec = report["recommendations"][0]
    assert "DEEPSEEK_API_KEY" in rec["fields_to_review"]
    assert "DEEPSEEK_BASE_URL" in rec["fields_to_review"]
    assert "DEEPSEEK_MODEL" in rec["fields_to_review"]
    assert "configs/model_routing.json" in " ".join(rec["fields_to_review"])
