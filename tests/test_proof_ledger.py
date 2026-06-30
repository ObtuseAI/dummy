from proof.ledger import write_proof, list_proofs
from pathlib import Path


def test_write_proof():
    before = set(list_proofs())
    ref = write_proof("test", "pass", {"x": 1})
    after = set(list_proofs())
    assert ref in after - before
    assert (Path("C:/src/engine/dumby/proof") / f"{ref}.json").exists()
