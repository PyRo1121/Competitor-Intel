"""Test ingestion service."""

from competitor_intel.core.ingest import IngestionService
from competitor_intel.core.types import SignalType
from competitor_intel.db.models import RawSignal


class TestIngestionService:
    """Test IngestionService functionality."""
    
    def test_ingest_signals(self, session):
        """Test ingesting signals."""
        service = IngestionService(dedup_window_days=1)
        
        signals = [
            {"title": "Test 1", "url": "https://test.com/1", "summary": "Summary 1"},
            {"title": "Test 2", "url": "https://test.com/2", "summary": "Summary 2"},
        ]
        
        stored = service.ingest(signals, "test", SignalType.RSS_ITEM)
        
        assert stored == 2
        
        # Verify in database
        result = session.query(RawSignal).all()
        assert len(result) == 2
        assert result[0].source == "test"
        assert result[0].signal_type == "rss_item"
    
    def test_deduplication(self, session):
        """Test signal deduplication."""
        service = IngestionService(dedup_window_days=1)
        
        signals = [
            {"title": "Duplicate", "url": "https://test.com/dup"},
            {"title": "Duplicate", "url": "https://test.com/dup"},  # Same URL
        ]
        
        stored = service.ingest(signals, "test", SignalType.RSS_ITEM)
        
        assert stored == 1  # Second should be deduplicated
    
    def test_get_unprocessed(self, session):
        """Test getting unprocessed signals."""
        service = IngestionService()
        
        signals = [
            {"title": "Test 1", "url": "https://test.com/1"},
            {"title": "Test 2", "url": "https://test.com/2"},
        ]
        
        service.ingest(signals, "test", SignalType.RSS_ITEM)
        
        unprocessed = service.get_unprocessed_signals(limit=10)
        
        assert len(unprocessed) == 2
        assert all(not s.processed for s in unprocessed)
    
    def test_mark_processed(self, session):
        """Test marking signals as processed."""
        service = IngestionService()
        
        signals = [{"title": "Test", "url": "https://test.com"}]
        service.ingest(signals, "test", SignalType.RSS_ITEM)
        
        # Get the signal ID
        result = session.query(RawSignal).first()
        
        service.mark_processed([result.id])
        
        # Refresh and check
        session.refresh(result)
        assert result.processed is True
