"""Adapt a copy of generate_v4_reports.py into generate_v5_reports.py."""
from pathlib import Path

path = Path(__file__).parent.parent / "scripts" / "generate_v5_reports.py"
text = path.read_text(encoding="utf-8")

# Docstring and paths
text = text.replace('"""Generate V4 milestone artifact reports."""', '"""Generate V5 milestone artifact reports."""')
text = text.replace('ARTIFACTS = ROOT / "artifacts" / "dumby"', 'ARTIFACTS = ROOT / "artifacts" / "dummy"')

# Workstreams V4 -> V5
text = text.replace('"workstream": "V4:', '"workstream": "V5:')

# Function names that should reflect v2/v3/v5
text = text.replace('async def generate_real_kalshi_read_only_report()', 'async def generate_real_kalshi_read_only_report_v2()')
text = text.replace('async def generate_normalization_report()', 'async def generate_normalization_report_v2()')
text = text.replace('async def generate_strategy_scan_report()', 'async def generate_strategy_scan_report_v2()')
text = text.replace('async def generate_firewall_rehearsal_report()', 'async def generate_firewall_rehearsal_report_v2()')
text = text.replace('def generate_no_order_in_read_only_report()', 'def generate_no_order_in_read_only_report_v2()')
text = text.replace('def generate_no_secret_leak_report()', 'def generate_no_secret_leak_report_v4()')
text = text.replace('def generate_firewall_rehearsal_regression_report()', 'def generate_firewall_rehearsal_regression_report_v2()')
text = text.replace('def generate_blunder_separation_recheck()', 'def generate_blunder_separation_recheck_v3()')
text = text.replace('def generate_dashboard_v4_report()', 'def generate_dashboard_v5_report()')

# Report file names in main()
text = text.replace('"real_kalshi_read_only_report_v1.json"', '"real_kalshi_read_only_report_v2.json"')
text = text.replace('"kalshi_normalization_report_v1.json"', '"kalshi_normalization_report_v2.json"')
text = text.replace('"real_market_strategy_scan_report_v1.json"', '"real_market_strategy_scan_report_v2.json"')
text = text.replace('"live_cap_firewall_rehearsal_report_v1.json"', '"live_cap_firewall_rehearsal_report_v2.json"')
text = text.replace('"dashboard_v4_report_v1.json"', '"dashboard_v5_report_v1.json"')
text = text.replace('"no_order_in_read_only_report_v1.json"', '"no_order_in_read_only_report_v2.json"')
text = text.replace('"no_secret_leak_report_v3.json"', '"no_secret_leak_report_v4.json"')
text = text.replace('"firewall_rehearsal_regression_report_v1.json"', '"firewall_rehearsal_regression_report_v2.json"')
text = text.replace('"blunder_separation_recheck_v2.json"', '"blunder_separation_recheck_v3.json"')

# Milestone
text = text.replace(
    '"milestone": "DUMBY_V4_REAL_KALSHI_READ_ONLY_INGESTION_AND_LIVE_CAP_FIREWALL_REHEARSAL_V1"',
    '"milestone": "DUMMY_V5_CANONICAL_RENAME_REAL_KALSHI_READ_ONLY_AND_LIVE_CAP_REHEARSAL_V1"',
)

# Dashboard endpoint list V4 -> V5
text = text.replace('"/v4/kalshi/status"', '"/v5/kalshi/status"')
text = text.replace('"/v4/kalshi/account"', '"/v5/kalshi/account"')
text = text.replace('"/v4/kalshi/markets"', '"/v5/kalshi/markets"')
text = text.replace('"/v4/kalshi/orderbook/MKT-YES"', '"/v5/kalshi/orderbook/MKT-YES"')
text = text.replace('"/v4/kalshi/positions"', '"/v5/kalshi/positions"')
text = text.replace('"/v4/kalshi/orders"', '"/v5/kalshi/orders"')
text = text.replace('"/v4/kalshi/fills"', '"/v5/kalshi/fills"')
text = text.replace('"/v4/strategies/scan"', '"/v5/strategies/scan"')
text = text.replace('"/v4/firewall/rehearse"', '"/v5/firewall/rehearse"')
text = text.replace('"/v4/firewall/blocked"', '"/v5/firewall/blocked"')
text = text.replace('"/v4/caps"', '"/v5/caps"')
text = text.replace('"/v4/live-submit/status"', '"/v5/live-submit/status"')

# Dashboard report field references
text = text.replace('"V4: Dashboard V4"', '"V5: Dashboard V5"')
text = text.replace('reports["dashboard_v4_report_v1.json"]', 'reports["dashboard_v5_report_v1.json"]')
text = text.replace('"dashboard_built": reports["dashboard_v4_report_v1.json"]["frontend_built"]', '"dashboard_built": reports["dashboard_v5_report_v1.json"]["frontend_built"]')

# Note
text = text.replace('"note": "All V4 reports generated.', '"note": "All V5 reports generated.')

path.write_text(text, encoding="utf-8")
print("adapted generate_v5_reports.py")
