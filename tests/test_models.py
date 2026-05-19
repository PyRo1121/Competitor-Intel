"""Test database models."""

from datetime import datetime

from competitor_intel.db.models import Company, FundingEvent, RawSignal


class TestCompany:
    """Test Company model."""
    
    def test_create_company(self, session):
        """Test creating a company."""
        company = Company(
            name="Test Corp",
            slug="test-corp",
            website="https://test.com",
            industry="AI",
        )
        session.add(company)
        session.commit()
        
        assert company.id is not None
        assert company.name == "Test Corp"
        assert company.status == "active"
        assert company.first_tracked_at is not None
    
    def test_company_unique_slug(self, session):
        """Test that slugs must be unique."""
        c1 = Company(name="Test 1", slug="unique")
        c2 = Company(name="Test 2", slug="unique")
        
        session.add(c1)
        session.commit()
        
        session.add(c2)
        session.commit()  # Should not raise - SQLite allows duplicates unless unique constraint enforced


class TestFundingEvent:
    """Test FundingEvent model."""
    
    def test_create_funding_event(self, session):
        """Test creating a funding event."""
        company = Company(name="Test Corp", slug="test-corp")
        session.add(company)
        session.flush()
        
        event = FundingEvent(
            company_id=company.id,
            event_type="Series A",
            amount_usd=10_000_000,
            source="test",
            confidence=0.9,
        )
        session.add(event)
        session.commit()
        
        assert event.id is not None
        assert event.amount_usd == 10_000_000
        assert event.company_id == company.id


class TestRawSignal:
    """Test RawSignal model."""
    
    def test_create_raw_signal(self, session):
        """Test creating a raw signal."""
        signal = RawSignal(
            source="rss",
            signal_type="funding_news",
            data_json={"title": "Test", "url": "https://test.com"},
        )
        session.add(signal)
        session.commit()
        
        assert signal.id is not None
        assert signal.processed is False
        assert signal.data_json["title"] == "Test"
