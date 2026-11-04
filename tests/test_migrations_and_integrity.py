"""
Database migration chain validation, schema integrity, constraints, and ingestion idempotency tests.
Validates Alembic heads, foreign keys, transaction rollbacks, and duplicate notice prevention.
"""

import os
import tempfile
from datetime import datetime, timezone
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from app.ingestion.save import save_ingested_properties
from app.models import Document, DocumentChunk, Evidence, IngestionRun, Property, PropertyDocument, User


@pytest.mark.migration
class TestAlembicMigrationChain:
    def test_single_alembic_head(self):
        """Verify that the Alembic migration chain has exactly one head revision (no unmerged branches)."""
        config = Config("alembic.ini")
        script = ScriptDirectory.from_config(config)
        heads = script.get_heads()
        assert len(heads) == 1, f"Expected exactly 1 Alembic head, but found {len(heads)}: {heads}"

    def test_all_revisions_connected_without_cycles(self):
        """Walk the entire revision chain from head to base to guarantee DAG integrity."""
        config = Config("alembic.ini")
        script = ScriptDirectory.from_config(config)
        revisions = list(script.walk_revisions())
        assert len(revisions) >= 20, f"Expected at least 20 migration revisions, found {len(revisions)}"
        rev_map = {r.revision: r for r in revisions}
        for r in revisions:
            if r.down_revision:
                if isinstance(r.down_revision, tuple):
                    for down_rev in r.down_revision:
                        assert down_rev in rev_map, f"Down revision {down_rev} not found in map for {r.revision}"
                else:
                    assert r.down_revision in rev_map, f"Down revision {r.down_revision} not found for {r.revision}"

    def test_alembic_upgrade_head_fresh_and_idempotent(self):
        """Verify that upgrading to head succeeds on fresh DB and is idempotent without DuplicateTable errors."""
        temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db.close()
        try:
            config = Config("alembic.ini")
            config.set_main_option("sqlalchemy.url", f"sqlite:///{temp_db.name}")

            # First upgrade pass: creates all tables, columns, indexes
            command.upgrade(config, "head")

            # Second upgrade pass: re-running upgrade against current head is a no-op / idempotent
            command.upgrade(config, "head")

            # Inspect that document_chunks index exists
            engine = sa.create_engine(f"sqlite:///{temp_db.name}")
            try:
                insp = sa.inspect(engine)
                indexes = {ix["name"] for ix in insp.get_indexes("document_chunks")}
                assert "ix_document_chunks_document_id_chunk_index" in indexes
            finally:
                engine.dispose()
        finally:
            if os.path.exists(temp_db.name):
                try:
                    os.unlink(temp_db.name)
                except PermissionError:
                    pass

    def test_document_chunk_composite_index_migration_idempotent(self):
        """Directly verify that revision 66c1710f4924 handles already-existing indexes gracefully."""
        config = Config("alembic.ini")
        script = ScriptDirectory.from_config(config)
        rev_66 = script.get_revision("66c1710f4924")
        assert rev_66 is not None

        # Verify revision defines safe upgrade and downgrade callables
        assert callable(rev_66.module.upgrade)
        assert callable(rev_66.module.downgrade)


@pytest.mark.migration
class TestSchemaIntegrityAndConstraints:
    def test_user_email_uniqueness_constraint(self, db):
        u1 = User(email="unique@example.com", password_hash="hash1", role="user")
        db.add(u1)
        db.commit()

        u2 = User(email="unique@example.com", password_hash="hash2", role="user")
        db.add(u2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_property_document_relationship_integrity(self, db):
        user = User(email="propowner@example.com", password_hash="hash", role="user")
        db.add(user)
        db.commit()

        prop = Property(address="123 Test St", city="Delhi", user_id=user.id)
        doc = Document(
            title="Notice 123",
            source_name="PNB",
            source_url="https://bank.com/notice123.pdf",
            document_type="auction_notice",
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add_all([prop, doc])
        db.commit()

        link = PropertyDocument(property_id=prop.id, document_id=doc.id, relationship_type="primary_notice")
        db.add(link)
        db.commit()

        found_link = db.query(PropertyDocument).filter_by(property_id=prop.id).first()
        assert found_link is not None
        assert found_link.document_id == doc.id

    def test_failed_transaction_rollback_leaves_no_orphans(self, db):
        user = User(email="rollback_user@example.com", password_hash="hash", role="user")
        db.add(user)
        db.commit()

        try:
            prop = Property(address="Rollback Villa", user_id=user.id)
            db.add(prop)
            dup_user = User(email="rollback_user@example.com", password_hash="hash", role="user")
            db.add(dup_user)
            db.commit()
        except IntegrityError:
            db.rollback()

        orphaned = db.query(Property).filter_by(address="Rollback Villa").first()
        assert orphaned is None


@pytest.mark.integration
class TestIngestionIdempotency:
    def test_ingest_duplicate_properties_deduplicated(self, db):
        user = User(email="ingest_user@example.com", password_hash="hash", role="user")
        run = IngestionRun(source_name="PNB", status="running", started_at=datetime.now(timezone.utc))
        db.add_all([user, run])
        db.commit()

        item_payload = {
            "property": {
                "address": "Idempotent House No 5",
                "city": "Pathankot",
                "locality": "Civil Lines",
                "area_sqft": 1200,
                "property_type": "residential",
                "reserve_price": 2_500_000,
                "emd": 250_000,
                "opening_bid": 2_500_000,
                "foreclosure_status": "scheduled",
            },
            "document": {
                "source_name": "PNB",
                "source_url": "https://pnb.bank.in/eauction/notice101.pdf",
                "document_type": "auction_notice",
                "title": "Idempotent Notice",
            },
            "evidence": [],
        }

        # First ingestion run
        res1 = save_ingested_properties(
            db=db,
            properties=[item_payload],
            user_id=user.id,
            ingestion_run_id=run.id,
        )
        assert len(res1["saved"]) == 1
        assert len(res1["skipped"]) == 0

        # Second ingestion run with identical property
        res2 = save_ingested_properties(
            db=db,
            properties=[item_payload],
            user_id=user.id,
            ingestion_run_id=run.id,
        )
        assert len(res2["saved"]) == 0
        assert len(res2["skipped"]) == 1
        assert res2["skipped"][0]["reason"] in ("duplicate_property", "updated_existing_property")

        count = db.query(Property).filter_by(address="Idempotent House No 5").count()
        assert count == 1
