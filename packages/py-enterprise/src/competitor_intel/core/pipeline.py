"""Pipeline orchestration for running collectors and generating reports."""

import time

import structlog

from competitor_intel.core.collector import BaseCollector
from competitor_intel.core.ingest import IngestionService
from competitor_intel.core.types import CollectorResult, CollectorStatus

logger = structlog.get_logger()


class PipelineRunner:
    """Orchestrates the full competitor intelligence pipeline.

    Pipeline stages:
    1. Collect signals from all configured collectors
    2. Ingest signals into database
    3. Extract intelligence events
    4. Generate embeddings
    5. Generate reports
    """

    def __init__(self):
        self.collectors: list[BaseCollector] = []
        self.ingestion = IngestionService()
        self.results: list[CollectorResult] = []

    def register_collector(self, collector: BaseCollector):
        """Register a collector for the pipeline."""
        self.collectors.append(collector)
        logger.info("collector_registered", name=collector.name)

    async def run_collection(self) -> list[CollectorResult]:
        """Run all registered collectors and ingest results."""
        logger.info("pipeline_started", collectors=len(self.collectors))
        start_time = time.time()

        results = []
        for collector in self.collectors:
            try:
                result = await collector.run()
                results.append(result)

                # Ingest signals if collection was successful
                # Signals collected in collector.run(); returned in result.metadata
                if result.status in (
                    CollectorStatus.SUCCESS,
                    CollectorStatus.PARTIAL,
                ) and result.metadata.get("signals"):
                    signals = result.metadata["signals"]
                    stored = self.ingestion.ingest(
                        signals,
                        source=collector.source_type,
                    )
                    result.signals_stored = stored
                    logger.info(
                        "signals_ingested",
                        collector=collector.name,
                        signals=len(signals),
                        stored=stored,
                    )

            except Exception as e:
                logger.error(
                    "collector_error",
                    collector=collector.name,
                    error=str(e),
                )
                results.append(
                    CollectorResult(
                        collector_name=collector.name,
                        status=CollectorStatus.FAILED,
                        errors=[str(e)],
                    )
                )

        duration = time.time() - start_time
        logger.info(
            "pipeline_completed",
            collectors=len(self.collectors),
            successful=sum(1 for r in results if r.status == CollectorStatus.SUCCESS),
            failed=sum(1 for r in results if r.status == CollectorStatus.FAILED),
            duration=duration,
        )

        self.results = results
        return results

    def get_summary(self) -> dict:
        """Get pipeline run summary."""
        if not self.results:
            return {"status": "not_run", "collectors": 0}

        return {
            "status": "completed",
            "collectors": len(self.results),
            "successful": sum(1 for r in self.results if r.status == CollectorStatus.SUCCESS),
            "partial": sum(1 for r in self.results if r.status == CollectorStatus.PARTIAL),
            "failed": sum(1 for r in self.results if r.status == CollectorStatus.FAILED),
            "skipped": sum(1 for r in self.results if r.status == CollectorStatus.SKIPPED),
            "total_signals": sum(r.signals_collected for r in self.results),
            "total_errors": sum(len(r.errors) for r in self.results),
            "total_duration": sum(r.duration_seconds for r in self.results),
        }
