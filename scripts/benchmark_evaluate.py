#!/usr/bin/env python3
"""Benchmark script for the /v1/evaluate endpoint.

Measures actual response latency to validate the "milliseconds" claim.

Usage:
    # Start the API server first, then:
    python scripts/benchmark_evaluate.py

    # With custom settings:
    python scripts/benchmark_evaluate.py --requests 500 --templates 50
"""

import argparse
import asyncio
import hashlib
import json
import statistics
import time
from dataclasses import dataclass

import httpx

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "cp_test_key_for_benchmarking"  # Will be created if doesn't exist


@dataclass
class BenchmarkResult:
    """Results from a benchmark run."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time_seconds: float
    latencies_ms: list[float]

    @property
    def requests_per_second(self) -> float:
        return self.total_requests / self.total_time_seconds if self.total_time_seconds > 0 else 0

    @property
    def p50_ms(self) -> float:
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0

    @property
    def p90_ms(self) -> float:
        return statistics.quantiles(self.latencies_ms, n=10)[8] if len(self.latencies_ms) >= 10 else max(self.latencies_ms, default=0)

    @property
    def p95_ms(self) -> float:
        return statistics.quantiles(self.latencies_ms, n=20)[18] if len(self.latencies_ms) >= 20 else max(self.latencies_ms, default=0)

    @property
    def p99_ms(self) -> float:
        return statistics.quantiles(self.latencies_ms, n=100)[98] if len(self.latencies_ms) >= 100 else max(self.latencies_ms, default=0)

    @property
    def min_ms(self) -> float:
        return min(self.latencies_ms) if self.latencies_ms else 0

    @property
    def max_ms(self) -> float:
        return max(self.latencies_ms) if self.latencies_ms else 0

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0

    @property
    def stdev_ms(self) -> float:
        return statistics.stdev(self.latencies_ms) if len(self.latencies_ms) > 1 else 0


def generate_structural_features(seed: int) -> dict:
    """Generate varied structural features for testing."""
    import random
    random.seed(seed)

    return {
        "page_count": random.randint(1, 10),
        "element_count": random.randint(50, 500),
        "table_count": random.randint(0, 5),
        "text_block_count": random.randint(10, 100),
        "image_count": random.randint(0, 10),
        "text_density": round(random.uniform(0.3, 0.9), 2),
        "layout_complexity": round(random.uniform(0.2, 0.8), 2),
        "column_count": random.randint(1, 4),
        "has_header": random.choice([True, False]),
        "has_footer": random.choice([True, False]),
        "bounding_boxes": [],
    }


def generate_fingerprint(features: dict) -> str:
    """Generate fingerprint from features."""
    features_json = json.dumps(features, sort_keys=True)
    return hashlib.sha256(features_json.encode()).hexdigest()


async def setup_test_data(client: httpx.AsyncClient, num_templates: int) -> list[dict]:
    """Create test templates for benchmarking."""
    templates = []

    print(f"Creating {num_templates} test templates...")

    for i in range(num_templates):
        features = generate_structural_features(seed=i)
        fingerprint = generate_fingerprint(features)

        template_data = {
            "template_id": f"BENCHMARK-TEMPLATE-{i:04d}",
            "version": "1.0",
            "structural_features": features,
            "baseline_reliability": round(0.75 + (i % 25) * 0.01, 2),
            "correction_rules": [
                {"field": "total", "rule": "sum_line_items", "parameters": {"tolerance": 0.01}}
            ] if i % 3 == 0 else [],
        }

        response = await client.post("/v1/templates", json=template_data)

        if response.status_code == 201:
            templates.append({
                "features": features,
                "fingerprint": fingerprint,
            })
        elif response.status_code == 409:
            # Template already exists, that's fine
            templates.append({
                "features": features,
                "fingerprint": fingerprint,
            })
        else:
            print(f"  Warning: Failed to create template {i}: {response.status_code}")

    print(f"  Created/found {len(templates)} templates")
    return templates


async def run_single_request(
    client: httpx.AsyncClient,
    templates: list[dict],
    request_id: int,
) -> tuple[float, bool, str]:
    """Run a single evaluation request and return (latency_ms, success, decision)."""
    import random

    # Randomly choose a scenario:
    # 40% - exact match (same fingerprint as existing template)
    # 30% - similar features (should trigger similarity matching)
    # 30% - new/unknown template

    scenario = random.random()

    if scenario < 0.4 and templates:
        # Exact match scenario
        template = random.choice(templates)
        features = template["features"]
        fingerprint = template["fingerprint"]
    elif scenario < 0.7 and templates:
        # Similar features scenario
        template = random.choice(templates)
        features = template["features"].copy()
        # Slightly modify features
        features["element_count"] = features["element_count"] + random.randint(-5, 5)
        fingerprint = hashlib.sha256(str(random.random()).encode()).hexdigest()
    else:
        # New template scenario
        features = generate_structural_features(seed=10000 + request_id)
        fingerprint = hashlib.sha256(str(random.random()).encode()).hexdigest()

    request_data = {
        "layout_fingerprint": fingerprint,
        "structural_features": features,
        "extractor_metadata": {
            "vendor": "nvidia",
            "model": "nemotron",
            "version": "1.0",
            "confidence": round(random.uniform(0.7, 0.99), 2),
            "latency_ms": random.randint(100, 500),
        },
        "client_doc_hash": hashlib.sha256(f"doc-{request_id}".encode()).hexdigest(),
        "client_correlation_id": f"benchmark-{request_id}",
        "pipeline_id": "benchmark",
    }

    start = time.perf_counter()

    try:
        response = await client.post("/v1/evaluate", json=request_data)
        latency_ms = (time.perf_counter() - start) * 1000

        if response.status_code == 200:
            data = response.json()
            return latency_ms, True, data.get("decision", "UNKNOWN")
        else:
            return latency_ms, False, f"HTTP {response.status_code}"
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return latency_ms, False, str(e)


async def run_benchmark(
    num_requests: int,
    num_templates: int,
    concurrency: int,
    api_key: str,
    base_url: str,
) -> BenchmarkResult:
    """Run the full benchmark."""

    headers = {"X-API-Key": api_key}

    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=30.0) as client:
        # Check API health
        try:
            response = await client.get("/health")
            if response.status_code != 200:
                raise Exception(f"API health check failed: {response.status_code}")
            print(f"API is healthy at {base_url}")
        except httpx.ConnectError:
            raise Exception(f"Cannot connect to API at {base_url}. Is the server running?")

        # Setup test templates
        templates = await setup_test_data(client, num_templates)

        # Warm-up phase
        print("\nWarm-up phase (10 requests)...")
        for i in range(10):
            await run_single_request(client, templates, i)

        # Benchmark phase
        print(f"\nRunning benchmark: {num_requests} requests with concurrency {concurrency}...")

        latencies: list[float] = []
        successes = 0
        failures = 0
        decisions: dict[str, int] = {}

        start_time = time.perf_counter()

        # Run in batches based on concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def limited_request(request_id: int) -> tuple[float, bool, str]:
            async with semaphore:
                return await run_single_request(client, templates, request_id)

        # Create all tasks
        tasks = [limited_request(i) for i in range(num_requests)]

        # Process with progress updates
        completed = 0
        for coro in asyncio.as_completed(tasks):
            latency_ms, success, decision = await coro
            latencies.append(latency_ms)

            if success:
                successes += 1
                decisions[decision] = decisions.get(decision, 0) + 1
            else:
                failures += 1

            completed += 1
            if completed % 100 == 0:
                print(f"  Progress: {completed}/{num_requests} ({completed/num_requests*100:.0f}%)")

        total_time = time.perf_counter() - start_time

        print(f"\nDecision distribution: {decisions}")

        return BenchmarkResult(
            total_requests=num_requests,
            successful_requests=successes,
            failed_requests=failures,
            total_time_seconds=total_time,
            latencies_ms=latencies,
        )


def print_results(result: BenchmarkResult):
    """Print benchmark results in a nice format."""

    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)

    print(f"\nRequests:")
    print(f"  Total:      {result.total_requests}")
    print(f"  Successful: {result.successful_requests}")
    print(f"  Failed:     {result.failed_requests}")
    print(f"  Success %:  {result.successful_requests/result.total_requests*100:.1f}%")

    print(f"\nThroughput:")
    print(f"  Total time: {result.total_time_seconds:.2f}s")
    print(f"  Requests/s: {result.requests_per_second:.1f}")

    print(f"\nLatency (milliseconds):")
    print(f"  Min:    {result.min_ms:>8.2f} ms")
    print(f"  Mean:   {result.mean_ms:>8.2f} ms")
    print(f"  P50:    {result.p50_ms:>8.2f} ms")
    print(f"  P90:    {result.p90_ms:>8.2f} ms")
    print(f"  P95:    {result.p95_ms:>8.2f} ms")
    print(f"  P99:    {result.p99_ms:>8.2f} ms")
    print(f"  Max:    {result.max_ms:>8.2f} ms")
    print(f"  StdDev: {result.stdev_ms:>8.2f} ms")

    print("\n" + "=" * 60)

    # Verdict on "milliseconds" claim
    print("\nVERDICT ON 'MILLISECONDS' CLAIM:")
    print("-" * 40)

    if result.p95_ms < 100:
        print(f"  VALIDATED - P95 latency is {result.p95_ms:.1f}ms (< 100ms)")
        print("  The 'milliseconds' claim is accurate.")
    elif result.p95_ms < 500:
        print(f"  PARTIALLY VALIDATED - P95 latency is {result.p95_ms:.1f}ms")
        print("  Technically milliseconds, but on the slower end.")
    else:
        print(f"  NOT VALIDATED - P95 latency is {result.p95_ms:.1f}ms")
        print("  Response times exceed what users expect from 'milliseconds'.")

    if result.p50_ms < 50:
        print(f"  Median response time ({result.p50_ms:.1f}ms) is excellent.")

    print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description="Benchmark the /v1/evaluate endpoint")
    parser.add_argument("--requests", type=int, default=200, help="Number of requests to run")
    parser.add_argument("--templates", type=int, default=20, help="Number of templates to create")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent requests")
    parser.add_argument("--api-key", type=str, default=API_KEY, help="API key to use")
    parser.add_argument("--base-url", type=str, default=BASE_URL, help="API base URL")

    args = parser.parse_args()

    print("PreFlight Evaluation Endpoint Benchmark")
    print("-" * 40)
    print(f"Target:      {args.base_url}")
    print(f"Requests:    {args.requests}")
    print(f"Templates:   {args.templates}")
    print(f"Concurrency: {args.concurrency}")
    print("-" * 40)

    try:
        result = await run_benchmark(
            num_requests=args.requests,
            num_templates=args.templates,
            concurrency=args.concurrency,
            api_key=args.api_key,
            base_url=args.base_url,
        )

        print_results(result)

    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
