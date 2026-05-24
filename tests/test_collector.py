"""Tests for enterprise collector framework."""

import pytest

pytestmark = pytest.mark.enterprise

from competitor_intel.core.collector import BaseCollector
from competitor_intel.core.types import CollectorStatus


class MockCollector(BaseCollector):
    """Mock collector for testing."""

    def __init__(self, signals=None, should_fail=False):
        super().__init__("mock")
        self._signals = signals or []
        self._should_fail = should_fail

    @property
    def source_type(self):
        return "mock"

    async def collect(self):
        if self._should_fail:
            raise RuntimeError("Test failure")
        return self._signals


class TestBaseCollector:
    """Test BaseCollector functionality."""

    @pytest.mark.asyncio
    async def test_successful_collection(self):
        """Test successful signal collection."""
        signals = [
            {"title": "Test 1", "url": "https://test.com/1"},
            {"title": "Test 2", "url": "https://test.com/2"},
        ]
        collector = MockCollector(signals=signals)

        result = await collector.run()

        assert result.status == CollectorStatus.SUCCESS
        assert result.signals_collected == 2
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_failed_collection(self):
        """Test failed signal collection."""
        collector = MockCollector(should_fail=True)

        result = await collector.run()

        assert result.status == CollectorStatus.PARTIAL
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_not_implemented(self):
        """Test not implemented collector."""
        collector = BaseCollector("test")

        result = await collector.run()

        assert result.status == CollectorStatus.NOT_IMPLEMENTED

    def test_generate_hash(self):
        """Test semantic hash generation."""
        data = {"title": "Test", "url": "https://test.com"}
        hash1 = BaseCollector.generate_hash(data)
        hash2 = BaseCollector.generate_hash(data)

        assert hash1 == hash2
        assert len(hash1) == 32
