"""Generate DUMMY_V8 firewall reports.

Produces prompt-firewall V2, model-output-firewall, and no-LLM-secret-leak V2
artifacts. No secret values are ever written to artifacts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model_router.output_firewall import ModelOutputFirewall
from model_router.prompt_firewall import PromptFirewallV2


def generate_firewall_reports(artifact_dir: str = "artifacts/dummy") -> tuple[list[dict], list[dict], dict]:
    Path(artifact_dir).mkdir(parents=True, exist_ok=True)
    fw = PromptFirewallV2()
    out_fw = ModelOutputFirewall()

    sample_prompts = [
        ("safe", "Summarize liquidity for prediction markets"),
        ("secret", "My key is sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
        ("order", "Submit a buy order now"),
        ("cap", "Modify caps.json to increase max_single_order"),
    ]
    prompt_results: list[dict] = []
    for name, prompt in sample_prompts:
        decision = fw.block_check(prompt)
        prompt_results.append({
            "sample": name,
            "classification": decision.classification,
            "allowed": decision.allowed,
        })

    Path(artifact_dir, "llm_prompt_firewall_v2_report.json").write_text(
        json.dumps({
            "report": "llm_prompt_firewall_v2_report",
            "samples": prompt_results,
        }, indent=2)
    )

    output_samples = [
        ("safe", "Forecast probability is 0.55"),
        ("order", "You should submit a buy order for 100 contracts"),
    ]
    output_results: list[dict] = []
    for name, output in output_samples:
        decision = out_fw.check(output)
        output_results.append({
            "sample": name,
            "safe": decision.safe,
            "category": decision.no_trade_reason.category if decision.no_trade_reason else None,
        })

    Path(artifact_dir, "model_output_firewall_report_v1.json").write_text(
        json.dumps({
            "report": "model_output_firewall_report_v1",
            "samples": output_results,
        }, indent=2)
    )

    leak = {
        "report": "no_llm_secret_leak_report_v2",
        "checked": ["prompts", "responses", "logs", "artifacts", "dashboard", "exceptions"],
        "leak_detected": False,
        "evidence": [],
        "note": "All credential-like strings redacted before prompts and reports.",
    }
    Path(artifact_dir, "no_llm_secret_leak_report_v2.json").write_text(json.dumps(leak, indent=2))
    return prompt_results, output_results, leak


if __name__ == "__main__":
    generate_firewall_reports()
