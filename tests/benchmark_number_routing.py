"""Explicit isolated admission measurement; not a native/media non-regression gate."""

import asyncio
import statistics
import time

import test_number_routing as routing_tests
from alojan_agent.routing import CallRouter

accounts = routing_tests.accounts
database = routing_tests.database
author = routing_tests.author
published = routing_tests.published
dedicated = routing_tests.dedicated


def test_measure_private_admission(accounts, published, dedicated):
    routing_tests.bound(accounts, published)
    router = CallRouter(dedicated("routing"), routing_tests.NODE)

    async def measure():
        times = []
        for index in range(55):
            start = time.perf_counter()
            snapshot = await router.initialize(
                f"benchmark-{index}", routing_tests.DID, "request_uri"
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert snapshot.scope_id == published[1] and snapshot.release_id == published[3]
            if index >= 5:
                times.append(elapsed_ms)
        return times

    timings = asyncio.run(measure())
    print(
        "\nIsolated PostgreSQL admission, restricted role, 50 sequential samples after 5 warmups: "
        f"P50={statistics.median(timings):.2f} ms, P95={sorted(timings)[47]:.2f} ms, "
        f"max={max(timings):.2f} ms. Includes a fresh DB connection per call; "
        "excludes SIP, preload, inference and RTP. No matched baseline or media gate."
    )
