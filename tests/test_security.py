from eci.security import pseudonymize, redact_pii, sanitize_query


def test_pii_redaction_masks_common_identifiers() -> None:
    text = "Email me at person@example.com, call 843-555-0199, SSN 123-45-6789, card 4111 1111 1111 1111."
    redacted = redact_pii(text)
    assert "person@example.com" not in redacted
    assert "843-555-0199" not in redacted
    assert "123-45-6789" not in redacted
    assert "4111 1111 1111 1111" not in redacted


def test_pseudonym_is_stable_and_secret_dependent() -> None:
    first = pseudonymize("customer-1", "secret-a")
    second = pseudonymize("customer-1", "secret-a")
    third = pseudonymize("customer-1", "secret-b")
    assert first == second
    assert first != third
    assert "customer-1" not in first


def test_query_is_normalized() -> None:
    assert sanitize_query("  delayed\n refund  ", 100) == "delayed refund"


def test_query_rejects_excessive_length() -> None:
    import pytest

    with pytest.raises(Exception):
        sanitize_query("x" * 101, 100)


def test_csv_formula_is_escaped() -> None:
    from eci.security import sanitize_for_csv

    assert sanitize_for_csv("=HYPERLINK(\"bad\")").startswith("'")
    assert sanitize_for_csv("ordinary") == "ordinary"
