from apps.api.app.safety import redact_secrets


def test_log_redaction_masks_common_secret_prefixes() -> None:
    rendered = redact_secrets("token sb_secret_example123 and ghp_example123")
    assert "example123" not in rendered
    assert rendered.count("[REDACTED]") == 2
