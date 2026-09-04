"""Operational job discovery: multi-source intake, dedup and ranking."""

from career_os.discovery.scraper import JobPageScraper, ScrapedPage
from career_os.discovery.service import (
    DiscoveredJob,
    DiscoveryItem,
    DiscoveryResult,
    JobDiscoveryService,
)

__all__ = [
    "DiscoveredJob",
    "DiscoveryItem",
    "DiscoveryResult",
    "JobDiscoveryService",
    "JobPageScraper",
    "ScrapedPage",
]
