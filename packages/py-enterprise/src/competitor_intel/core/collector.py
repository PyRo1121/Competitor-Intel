"""Base collector framework with async HTTP, rate limiting, and retries."""

import asyncio
import hashlib
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from competitor_intel.core.types import CollectorMetrics, CollectorResult, CollectorStatus
from competitor_intel.settings import get_settings

logger = structlog.get_logger()


class BaseCollector(ABC):
    """Base class for all signal collectors.
    
    Provides:
    - Async HTTP client with timeouts
    - Rate limiting via pyrate-limiter
    - Retry logic with exponential backoff
    - Structured logging
    - Metrics collection
    """
    
    def __init__(self, name: str):
        self.name = name
        self.settings = get_settings()
        self.metrics = CollectorMetrics()
        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
    
    @property
    def source_type(self) -> str:
        """Return the source type string. Override in subclasses."""
        return "unknown"
    
    @property
    def timeout(self) -> int:
        """Request timeout in seconds."""
        return self.settings.rate_limit.default_timeout
    
    @property
    def max_concurrent(self) -> int:
        """Maximum concurrent requests."""
        return self.settings.collector.max_concurrent
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(max_connections=self.max_concurrent),
            headers={"User-Agent": self.settings.rate_limit.sec_user_agent},
        )
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
    )
    async def fetch(self, url: str, **kwargs) -> httpx.Response:
        """Fetch URL with retries and rate limiting."""
        if not self._client:
            raise RuntimeError("Collector not initialized. Use 'async with' context.")
        if not self._semaphore:
            raise RuntimeError("Collector not initialized. Use 'async with' context.")
        
        self.metrics.total_requests += 1
        start = time.time()
        
        try:
            async with self._semaphore:
                response = await self._client.get(url, **kwargs)
                response.raise_for_status()
                
                self.metrics.successful_requests += 1
                self.metrics.total_bytes_downloaded += len(response.content)
                
                duration_ms = (time.time() - start) * 1000
                self._update_avg_response_time(duration_ms)
                
                logger.debug(
                    "fetch_success",
                    url=url,
                    status=response.status_code,
                    duration_ms=duration_ms,
                )
                return response
                
        except httpx.HTTPStatusError as e:
            self.metrics.failed_requests += 1
            if e.response.status_code == 429:
                self.metrics.rate_limit_hits += 1
            logger.warning(
                "fetch_failed",
                url=url,
                status=e.response.status_code,
                error=str(e),
            )
            raise
        except Exception as e:
            self.metrics.failed_requests += 1
            logger.error("fetch_error", url=url, error=str(e))
            raise
    
    async def run(self) -> CollectorResult:
        """Main entry point. Collect signals and return result."""
        start_time = time.time()
        errors = []
        signals = []
        
        try:
            async with self:
                logger.info("collector_started", collector=self.name)
                signals = await self.collect()
                
        except NotImplementedError:
            logger.warning("collector_not_implemented", collector=self.name)
            return CollectorResult(
                collector_name=self.name,
                status=CollectorStatus.NOT_IMPLEMENTED,
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            logger.error("collector_failed", collector=self.name, error=str(e))
            errors.append(str(e))
        
        duration = time.time() - start_time
        
        result = CollectorResult(
            collector_name=self.name,
            status=CollectorStatus.SUCCESS if not errors else CollectorStatus.PARTIAL,
            signals_collected=len(signals),
            signals_stored=0,
            errors=errors,
            duration_seconds=duration,
            metadata={
                "signals": signals,
                "total_requests": self.metrics.total_requests,
                "successful_requests": self.metrics.successful_requests,
                "failed_requests": self.metrics.failed_requests,
                "rate_limit_hits": self.metrics.rate_limit_hits,
            },
        )
        
        logger.info(
            "collector_completed",
            collector=self.name,
            signals=len(signals),
            duration=duration,
            status=result.status.value,
        )
        
        return result
    
    @abstractmethod
    async def collect(self) -> list[dict[str, Any]]:
        """Collect signals. Must be implemented by subclasses.
        
        Returns:
            List of signal dictionaries with keys:
            - title: str
            - summary: str  
            - url: str
            - source: str
            - signal_type: str
            - detected_at: datetime (optional)
            - company_id: int (optional)
            - metadata: dict (optional)
        """
        raise NotImplementedError
    
    @staticmethod
    def generate_hash(data: dict[str, Any]) -> str:
        """Generate semantic hash for deduplication."""
        content = str(sorted(data.items()))
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def _update_avg_response_time(self, new_time_ms: float):
        """Update rolling average response time."""
        n = self.metrics.total_requests
        old_avg = self.metrics.avg_response_time_ms
        self.metrics.avg_response_time_ms = (
            (old_avg * (n - 1) + new_time_ms) / n
        )
