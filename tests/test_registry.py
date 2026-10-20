from app.ingestion.registry import adapters_to_run
from app.models import ConnectedSource


def test_custom_source_does_not_disable_builtin_sources(client, db):
    db.add(
        ConnectedSource(
            name="Custom auction portal",
            base_url="https://auctions.example/notice",
            adapter_key="custom_html",
            config_json={"rules": {"item_selector": ".listing"}},
            enabled=True,
        )
    )
    db.commit()

    labels = [label for label, _adapter in adapters_to_run(db)]
    assert "PNBSourceAdapter" in labels
    assert "BankNetSourceAdapter" in labels
    assert any(label.startswith("connected:") for label in labels)


def test_connected_builtin_key_replaces_duplicate_builtin(client, db):
    db.add(
        ConnectedSource(
            name="BankNet configured source",
            base_url="https://banknet.example/auctions",
            adapter_key="banknet",
            config_json={"limit": 20},
            enabled=True,
        )
    )
    db.commit()

    labels = [label for label, _adapter in adapters_to_run(db)]
    assert "PNBSourceAdapter" in labels
    assert "BankNetSourceAdapter" not in labels
    assert any(label.startswith("connected:") for label in labels)
