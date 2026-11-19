from __future__ import annotations


def test_verify_returns_is_exported_from_verify_package() -> None:
    import monte_neo.verify as v
    from monte_neo.verify.returns_dd import verify_returns

    assert "verify_returns" in v.__all__
    assert v.verify_returns is verify_returns
