from __future__ import annotations

import pytest


def _forbidden(*_args, **_kwargs):
    raise AssertionError("default archive report path attempted provider/network construction")


@pytest.mark.asyncio
async def test_v8_provider_report_default_never_constructs_live_providers(
    monkeypatch, tmp_path
):
    import archive.report_scripts.generate_v8_model_provider_reports as reports
    import model_router.providers as providers

    monkeypatch.setattr(reports, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(providers, "DeepSeekV4FlashProvider", _forbidden)
    monkeypatch.setattr(providers, "MinimaxM3Provider", _forbidden)
    monkeypatch.setattr(providers.httpx, "AsyncClient", _forbidden)

    report = await reports.generate_live_model_provider_adapter_report_v1()
    paths = await reports.generate_provider_reports()

    assert report["contact_mode"] == "PREFLIGHT_ONLY"
    assert report["live_contact_authorized"] is False
    assert report["network_contact_authorized"] is False
    assert {row["status"] for row in report["provider_results"][:2]} == {"skipped"}
    assert set(paths) == {
        "live_model_provider_adapter_report_v1.json",
        "model_provider_error_handling_report_v1.json",
    }


@pytest.mark.asyncio
async def test_v8_1_resolution_reports_default_never_construct_live_resolver(
    monkeypatch,
):
    import archive.report_scripts.generate_v8_1_reports as reports
    import model_router.resolver as resolver

    monkeypatch.setattr(resolver, "ModelProviderResolver", _forbidden)
    monkeypatch.setattr(resolver.httpx, "AsyncClient", _forbidden)

    resolution = await reports.generate_model_provider_resolution_report_v1()
    aliases = await reports.generate_model_alias_resolution_report_v1()
    errors = await reports.generate_model_provider_error_resolution_report_v1()

    assert resolution["deepseek_v4_flash"]["status"] == "PREFLIGHT_ONLY"
    assert resolution["minimax_m3"]["status"] == "PREFLIGHT_ONLY"
    assert aliases["deepseek_v4_flash"]["resolved_model"] is None
    assert aliases["minimax_m3"]["resolved_model"] is None
    assert errors["deepseek_v4_flash"]["status"] == "PREFLIGHT_ONLY"
    assert errors["minimax_m3"]["status"] == "PREFLIGHT_ONLY"
    assert resolution["deepseek_v4_flash"]["network_contacted"] is False
    assert resolution["minimax_m3"]["network_contacted"] is False


@pytest.mark.asyncio
async def test_v8_2_model_id_default_never_constructs_live_resolver(monkeypatch):
    import archive.report_scripts.generate_v8_2_reports as reports
    import model_router.resolver as resolver

    monkeypatch.setattr(resolver, "ModelProviderResolver", _forbidden)
    monkeypatch.setattr(resolver.httpx, "AsyncClient", _forbidden)

    report = await reports.generate_model_id_validation_report_v1()

    assert report["live_contact_authorized"] is False
    assert report["deepseek_v4_flash"]["status"] == "PREFLIGHT_ONLY"
    assert report["minimax_m3"]["status"] == "PREFLIGHT_ONLY"
    assert report["deepseek_v4_flash"]["network_contacted"] is False
    assert report["minimax_m3"]["network_contacted"] is False


@pytest.mark.asyncio
async def test_truthy_non_boolean_never_arms_archive_live_paths(monkeypatch):
    import archive.report_scripts.generate_v8_1_reports as v81
    import archive.report_scripts.generate_v8_2_reports as v82
    import archive.report_scripts.generate_v8_model_provider_reports as v8
    import model_router.providers as providers
    import model_router.resolver as resolver

    monkeypatch.setattr(providers, "DeepSeekV4FlashProvider", _forbidden)
    monkeypatch.setattr(providers, "MinimaxM3Provider", _forbidden)
    monkeypatch.setattr(providers.httpx, "AsyncClient", _forbidden)
    monkeypatch.setattr(resolver, "ModelProviderResolver", _forbidden)
    monkeypatch.setattr(resolver.httpx, "AsyncClient", _forbidden)

    adapter = await v8.generate_live_model_provider_adapter_report_v1(
        allow_live="true"  # type: ignore[arg-type]
    )
    resolution = await v81.generate_model_provider_resolution_report_v1(
        allow_live=1  # type: ignore[arg-type]
    )
    model_id = await v82.generate_model_id_validation_report_v1(
        allow_live="1"  # type: ignore[arg-type]
    )

    assert adapter["contact_mode"] == "PREFLIGHT_ONLY"
    assert adapter["live_contact_authorized"] is False
    assert resolution["deepseek_v4_flash"]["status"] == "PREFLIGHT_ONLY"
    assert model_id["deepseek_v4_flash"]["status"] == "PREFLIGHT_ONLY"


@pytest.mark.asyncio
async def test_archive_report_entrypoints_are_zero_network_by_default(
    monkeypatch, tmp_path
):
    import archive.report_scripts.generate_v8_1_reports as v81
    import archive.report_scripts.generate_v8_2_reports as v82
    import archive.report_scripts.generate_v8_model_provider_reports as v8
    import model_router.openrouter_panel_smoke as panel_smoke
    import model_router.providers as providers
    import model_router.resolver as resolver

    monkeypatch.setattr(v8, "ARTIFACTS", tmp_path / "v8")
    monkeypatch.setattr(v81, "ARTIFACTS", tmp_path / "v81")
    monkeypatch.setattr(v82, "ARTIFACTS", tmp_path / "v82")
    for module in (v8, v81, v82):
        module.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(providers.httpx, "AsyncClient", _forbidden)
    monkeypatch.setattr(resolver.httpx, "AsyncClient", _forbidden)
    monkeypatch.setattr(panel_smoke.httpx, "AsyncClient", _forbidden)

    await v8.main()
    v81_result = await v81.main()
    v82_result = await v82.main()

    assert v81_result["verdict"] in {"PASS", "PARTIAL"}
    assert v82_result["verdict"] in {"PASS", "PARTIAL"}
