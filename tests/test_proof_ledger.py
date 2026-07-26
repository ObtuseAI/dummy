from proof import ledger


def test_write_proof(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "PROOF_DIR", tmp_path)

    before = set(ledger.list_proofs())
    ref = ledger.write_proof("test", "pass", {"x": 1})
    after = set(ledger.list_proofs())

    assert ref in after - before
    assert (tmp_path / f"{ref}.json").exists()
