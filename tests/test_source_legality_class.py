from __future__ import annotations


def test_source_legality_class_exposes_v18_allowed_and_disallowed_classes() -> None:
    from predator_mesh.v18.source_truth import SourceLegalityClass

    assert {item.value for item in SourceLegalityClass} == {
        "PUBLIC_ALLOWED",
        "PUBLIC_STATIC_FIXTURE",
        "LICENSE_REQUIRED",
        "UNVERIFIED_SOURCE",
        "DISALLOWED_PRIVATE",
        "DISALLOWED_SCRAPING_RISK",
    }
