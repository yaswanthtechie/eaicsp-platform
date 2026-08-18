from app.core.database import SessionLocal
from app.models.audit import ComplianceAudit
from app.services import rescreen_service


def create_audit(
    db,
    entity_name: str,
    matched: bool,
    matched_name: str | None = None,
    match_score: int = 0,
):
    record = ComplianceAudit(
        entity_name=entity_name,
        matched=matched,
        matched_name=matched_name,
        matched_lists="OFAC" if matched else None,
        match_score=match_score,
        risk_score=0,
        risk_factors=None,
        screening_type="INITIAL",
        newly_flagged=False,
        screening_run_id=None,
        service_name="test",
        duration_ms=0,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


def test_get_latest_audits():

    db = SessionLocal()

    try:
        create_audit(
            db,
            "TEST SUPPLIER",
            matched=False,
        )

        new_record = create_audit(
            db,
            "TEST SUPPLIER",
            matched=True,
            matched_name="TEST SUPPLIER",
            match_score=100,
        )

        latest = rescreen_service.get_latest_audits(db)

        assert "TEST SUPPLIER" in latest

        assert (
            latest["TEST SUPPLIER"].id
            == new_record.id
        )

    finally:
        db.close()


def test_get_previously_cleared_entities():

    db = SessionLocal()

    try:
        create_audit(
            db,
            "CLEARED SUPPLIER",
            matched=False,
        )

        cleared = (
            rescreen_service
            .get_previously_cleared_entities(db)
        )

        names = [
            record.entity_name
            for record in cleared
        ]

        assert "CLEARED SUPPLIER" in names

    finally:
        db.close()



def test_latest_matched_entity_is_not_cleared():

    db = SessionLocal()

    try:
        create_audit(
            db,
            "ALREADY MATCHED",
            matched=False,
        )

        create_audit(
            db,
            "ALREADY MATCHED",
            matched=True,
            matched_name="ALREADY MATCHED",
            match_score=100,
        )

        cleared = (
            rescreen_service
            .get_previously_cleared_entities(db)
        )

        names = [
            record.entity_name
            for record in cleared
        ]

        assert "ALREADY MATCHED" not in names

    finally:
        db.close()




def test_rescreen_entity_still_clean(monkeypatch):

    db = SessionLocal()

    try:
        record = create_audit(
            db,
            "CLEAN SUPPLIER",
            matched=False,
        )

        monkeypatch.setattr(
            rescreen_service,
            "screen_entity",
            lambda name: {
                "entity_name": name,
                "is_flagged": False,
                "matched_name": None,
                "matched_lists": [],
                "matched_count": 0,
                "match_score": 0,
                "confidence": 0,
                "risk_score": 0,
                "risk_factors": {
                    "match_confidence": 0,
                    "source_coverage": 0,
                    "recency": 0,
                },
            },
        )

        result = rescreen_service.rescreen_entity(
            db,
            record,
        )

        assert result["previously_cleared"] is True
        assert result["newly_flagged"] is False

       
        audits = (
            db.query(ComplianceAudit)
            .filter(
                ComplianceAudit.entity_name
                == "CLEAN SUPPLIER"
            )
            .all()
        )

        assert len(audits) == 1

    finally:
        db.close()


def test_rescreen_entity_becomes_flagged(monkeypatch):

    db = SessionLocal()

    try:
        record = create_audit(
            db,
            "NEWLY SANCTIONED SUPPLIER",
            matched=False,
        )

        monkeypatch.setattr(
            rescreen_service,
            "screen_entity",
            lambda name: {
                "entity_name": name,
                "is_flagged": True,
                "matched_name": name,
                "matched_lists": ["OFAC"],
                "matched_count": 1,
                "match_score": 100,
                "confidence": 1.0,
                "risk_score": 85,
                "risk_factors": {
                    "match_confidence": 100,
                    "source_coverage": 33.33,
                    "recency": 100,
                },
            },
        )

        result = rescreen_service.rescreen_entity(
            db,
            record,
        )

        assert result["previously_cleared"] is True
        assert result["newly_flagged"] is True
        assert result["result"]["is_flagged"] is True

    finally:
        db.close()



def test_newly_flagged_record_is_saved(monkeypatch):

    db = SessionLocal()

    try:
        record = create_audit(
            db,
            "SANCTIONED COMPANY",
            matched=False,
        )

        monkeypatch.setattr(
            rescreen_service,
            "screen_entity",
            lambda name: {
                "entity_name": name,
                "is_flagged": True,
                "matched_name": name,
                "matched_lists": ["OFAC"],
                "matched_count": 1,
                "match_score": 100,
                "confidence": 1.0,
                "risk_score": 90,
                "risk_factors": {
                    "match_confidence": 100,
                    "source_coverage": 33.33,
                    "recency": 100,
                },
            },
        )

        result = rescreen_service.rescreen_entity(
            db,
            record,
        )

        assert result["newly_flagged"] is True

        db.commit()

        new_audit = (
            db.query(ComplianceAudit)
            .filter(
                ComplianceAudit.entity_name
                == "SANCTIONED COMPANY",
                ComplianceAudit.screening_type
                == "RESCREEN",
            )
            .order_by(
                ComplianceAudit.id.desc()
            )
            .first()
        )

        assert new_audit is not None
        assert new_audit.matched is True
        assert new_audit.newly_flagged is True
        assert new_audit.matched_name == (
            "SANCTIONED COMPANY"
        )
        assert new_audit.match_score == 100

    finally:
        db.close()



def test_rescreen_all_cleared_entities(monkeypatch):

    db = SessionLocal()

    try:
        create_audit(
            db,
            "SUPPLIER ONE",
            matched=False,
        )

        create_audit(
            db,
            "SUPPLIER TWO",
            matched=False,
        )

        create_audit(
            db,
            "SUPPLIER THREE",
            matched=False,
        )

        screened = []

        def fake_screen(name):

            screened.append(name)

            return {
                "entity_name": name,
                "is_flagged": False,
                "matched_name": None,
                "matched_lists": [],
                "matched_count": 0,
                "match_score": 0,
                "confidence": 0,
                "risk_score": 0,
                "risk_factors": {
                    "match_confidence": 0,
                    "source_coverage": 0,
                    "recency": 0,
                },
            }

        monkeypatch.setattr(
            rescreen_service,
            "screen_entity",
            fake_screen,
        )

  
        monkeypatch.setattr(
            rescreen_service,
            "refresh_sanctions_data",
            lambda: None,
        )

        result = (
            rescreen_service
            .rescreen_cleared_entities()
        )

        assert result["total_checked"] == 3
        assert result["newly_flagged"] == 0
        assert result["still_clean"] == 3

        assert len(screened) == 3

    finally:
        db.close()




def test_rescreen_mixed_results(monkeypatch):

    db = SessionLocal()

    try:
        create_audit(
            db,
            "CLEAN SUPPLIER",
            matched=False,
        )

        create_audit(
            db,
            "SANCTIONED SUPPLIER",
            matched=False,
        )

        def fake_screen(name):

            if name == "SANCTIONED SUPPLIER":

                return {
                    "entity_name": name,
                    "is_flagged": True,
                    "matched_name": name,
                    "matched_lists": ["OFAC"],
                    "matched_count": 1,
                    "match_score": 100,
                    "confidence": 1.0,
                    "risk_score": 90,
                    "risk_factors": {
                        "match_confidence": 100,
                        "source_coverage": 33.33,
                        "recency": 100,
                    },
                }

            return {
                "entity_name": name,
                "is_flagged": False,
                "matched_name": None,
                "matched_lists": [],
                "matched_count": 0,
                "match_score": 0,
                "confidence": 0,
                "risk_score": 0,
                "risk_factors": {
                    "match_confidence": 0,
                    "source_coverage": 0,
                    "recency": 0,
                },
            }

        monkeypatch.setattr(
            rescreen_service,
            "screen_entity",
            fake_screen,
        )

     
        monkeypatch.setattr(
            rescreen_service,
            "refresh_sanctions_data",
            lambda: None,
        )

        result = (
            rescreen_service
            .rescreen_cleared_entities()
        )

        assert result["total_checked"] == 2
        assert result["newly_flagged"] == 1
        assert result["still_clean"] == 1

    finally:
        db.close()




def test_rescreen_when_no_cleared_entities(monkeypatch):

    db = SessionLocal()

    try:

        monkeypatch.setattr(
            rescreen_service,
            "refresh_sanctions_data",
            lambda: None,
        )

        result = (
            rescreen_service
            .rescreen_cleared_entities()
        )

        assert result["total_checked"] == 0
        assert result["newly_flagged"] == 0
        assert result["still_clean"] == 0
        assert result["results"] == []

    finally:
        db.close()



def test_sanctions_refreshed_before_rescreen(monkeypatch):

    execution_order = []

    db = SessionLocal()

    try:
        create_audit(
            db,
            "TEST SUPPLIER",
            matched=False,
        )

        def fake_refresh():

            execution_order.append(
                "refresh"
            )

        def fake_screen(name):

            execution_order.append(
                "screen"
            )

            return {
                "entity_name": name,
                "is_flagged": False,
                "matched_name": None,
                "matched_lists": [],
                "matched_count": 0,
                "match_score": 0,
                "confidence": 0,
                "risk_score": 0,
                "risk_factors": {
                    "match_confidence": 0,
                    "source_coverage": 0,
                    "recency": 0,
                },
            }

        monkeypatch.setattr(
            rescreen_service,
            "refresh_sanctions_data",
            fake_refresh,
        )

        monkeypatch.setattr(
            rescreen_service,
            "screen_entity",
            fake_screen,
        )

        rescreen_service.rescreen_cleared_entities()

        assert execution_order[0] == "refresh"
        assert "screen" in execution_order

    finally:
        db.close()



def test_nightly_rescreen_job(monkeypatch):

    expected = {
        "total_checked": 10,
        "newly_flagged": 2,
        "still_clean": 8,
        "total_duration_ms": 25.5,
        "results": [],
    }

    monkeypatch.setattr(
        rescreen_service,
        "rescreen_cleared_entities",
        lambda: expected,
    )

    result = (
        rescreen_service
        .nightly_rescreen_job()
    )

    assert result["total_checked"] == 10
    assert result["newly_flagged"] == 2
    assert result["still_clean"] == 8
    assert result["total_duration_ms"] == 25.5
    assert result["results"] == []

def test_rescreen_respects_override(monkeypatch):
    db = SessionLocal()

    try:
        record = create_audit(
            db,
            "ABC TEST COMPANY",
            matched=False,
        )

        # Create false-positive override
        from app.services.override_service import create_override

        create_override(
            db=db,
            entity_name="ABC TEST COMPANY",
            matched_name="ABC TEST COMPANY",
            source="OFAC",
            reason="Reviewed and confirmed false positive",
            reviewed_by="compliance-team",
        )

        monkeypatch.setattr(
            rescreen_service,
            "screen_entity",
            lambda name: {
                "entity_name": name,
                "is_flagged": True,
                "matched_name": "ABC TEST COMPANY",
                "matched_lists": ["OFAC"],
                "matched_count": 1,
                "match_score": 100,
                "confidence": 1.0,
                "risk_score": 90,
                "risk_factors": {
                    "match_confidence": 100,
                    "source_coverage": 33.33,
                    "recency": 100,
                },
            },
        )

        result = rescreen_service.rescreen_entity(
            db=db,
            entity=record,
        )

        assert result["newly_flagged"] is False

        assert (
            result["result"]["override_applied"]
            is True
        )

        assert (
            result["result"]["is_flagged"]
            is False
        )

    finally:
        db.close()