from autonomy.crypto_horizon_evidence import build_registered_crypto_sources


def test_matrix_roster_covers_registered_crypto_sources_without_production_ledger() -> None:
    sources = build_registered_crypto_sources(include_cross_venue=True)
    names = {source.name for source in sources}
    assert {
        "market_prior",
        "crypto_spot_vol",
        "crypto_ewma_t",
        "crypto_empirical_regime",
        "crypto_technical_composite",
        "crypto_technical_foundry",
        "crypto_dvol_implied",
        "crypto_structure_swing",
        "crypto_macro_regime",
        "crypto_equities_flow",
        "crypto_blend_sigma",
        "crypto_vrp_regime",
        "crypto_btc_leadlag",
        "crypto_patience_confirm",
        "crypto_kama_momentum",
        "crypto_chartist",
        "cross_venue_polymarket_crypto",
        "market_debias",
        "crypto_spot_vol::cal",
        "crypto_ewma_t::cal",
    } <= names
    cross_venue = next(
        source for source in sources
        if source.name == "cross_venue_polymarket_crypto"
    )
    assert cross_venue.ledger is None
