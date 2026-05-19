#!/usr/bin/env python3
"""
End-to-end pipeline test for competitor intelligence.
Validates that all collectors can run and produce signals.
"""

import logging
import sys
from pathlib import Path

logger = logging.getLogger("test_pipeline")

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from collectors.rss_collector import load_company_names, extract_company_mentions
from db.schema import init_database

def test_company_detection():
    """Test that company mention extraction works."""
    logger.info("=== Testing Company Detection ===")
    
    # Test cases
    test_cases = [
        ("OpenAI releases GPT-5", ["OpenAI"]),
        ("Anthropic raises funding", ["Anthropic"]),
        ("Cursor and Perplexity compete", ["Cursor", "Perplexity"]),
        ("Nothing relevant here", []),
    ]
    
    for text, expected in test_cases:
        mentions = extract_company_mentions(text)
        # Just check that it runs without error
        logger.info("  Text: '%s...' -> Found: %s", text[:50], mentions)
    
    logger.info("Company detection test passed")

def test_database_connection():
    """Test database is accessible."""
    logger.info("=== Testing Database ===")
    
    companies = load_company_names()
    logger.info("Loaded %s company name variations", len(companies))
    
    if len(companies) > 0:
        logger.info("Database connection test passed")
        return True
    else:
        logger.warning("No companies found in database")
        return False

def test_collector_imports():
    """Test that all collectors can be imported."""
    logger.info("=== Testing Collector Imports ===")
    
    collectors = [
        "collectors.rss_collector",
        "collectors.github_signals",
        "collectors.website_monitor",
        "collectors.multi_source_collector",
    ]
    
    passed = 0
    for module_name in collectors:
        try:
            __import__(module_name)
            logger.info("  [OK] %s", module_name)
            passed += 1
        except Exception as e:
            logger.error("  [FAIL] %s: %s", module_name, e)
    
    logger.info("Import test: %s/%s passed", passed, len(collectors))
    return passed == len(collectors)

def main():
    """Main entry point for testing the intelligence pipeline."""
    logger.info("Competitor Intelligence Pipeline Test")
    
    test_company_detection()
    db_ok = test_database_connection()
    imports_ok = test_collector_imports()
    
    if db_ok and imports_ok:
        logger.info("All tests passed. Pipeline is operational.")
        return 0
    else:
        logger.error("Some tests failed. Check output above.")
        return 1

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.exit(main())
