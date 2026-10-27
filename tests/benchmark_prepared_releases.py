"""Explicit synthetic preload measurement, not an inference/media acceptance gate."""

import asyncio
import statistics
import time

from alojan_agent.prepared import PreparedReleases
from test_prepared_releases import preload, release


def report(label, samples):
    ordered = sorted(samples)
    print(
        f"\n{label}: n={len(samples)}, P50={statistics.median(samples):.4f} ms, "
        f"P95={ordered[int(len(samples) * 0.95) - 1]:.4f} ms, max={max(samples):.4f} ms"
    )


def test_measure_prepared_release(tmp_path):
    fixture = release(tmp_path)

    async def run():
        cold = []
        for index in range(35):
            cache = PreparedReleases(tmp_path / "store")
            start = time.perf_counter()
            item = await preload(cache, fixture)
            if index >= 5:
                cold.append((time.perf_counter() - start) * 1000)
            await cache.close()
        cache = PreparedReleases(tmp_path / "store")
        await preload(cache, fixture)
        warm = []
        for _ in range(10000):
            start = time.perf_counter()
            item = cache.pin(fixture[0])
            cache.unpin(item)
            warm.append((time.perf_counter() - start) * 1000)
        assert not cache.pins and len(cache.entries) == 1
        size = item.payload_bytes
        await cache.close()
        return cold, warm, size

    cold, warm, size = asyncio.run(run())
    report(
        "Cold application cache, warm OS file cache; synthetic 1s speech + 400ms greeting pad", cold
    )
    report("Warm in-memory pin/unpin, no files/DB/inference", warm)
    print(
        f"Accounted payload={size} bytes. No native/RTP, maximum-duration assets or matched live baseline."
    )
