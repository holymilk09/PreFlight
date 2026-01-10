"""Temporal worker for document processing workflows.

This module provides the worker that executes workflows and activities.
Run this as a separate process to handle workflow executions.
"""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from src.config import settings
from src.workflows.activities import (
    compute_drift_activity,
    compute_reliability_activity,
    match_template_activity,
    select_rules_activity,
)
from src.workflows.document_processing import DocumentProcessingWorkflow

# Task queue name for PreFlight workflows
TASK_QUEUE = "preflight-tasks"


async def create_worker(client: Client | None = None) -> Worker:
    """Create a Temporal worker for document processing.

    Args:
        client: Optional Temporal client. If not provided, creates one.

    Returns:
        Configured Worker instance.
    """
    if client is None:
        client = await Client.connect(settings.temporal_host)

    return Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DocumentProcessingWorkflow],
        activities=[
            match_template_activity,
            compute_drift_activity,
            compute_reliability_activity,
            select_rules_activity,
        ],
    )


async def run_worker() -> None:
    """Run the Temporal worker.

    This connects to Temporal and starts processing workflows.
    """
    from src.db import init_db

    # Initialize database connection for activities
    await init_db()

    # Connect to Temporal
    client = await Client.connect(settings.temporal_host)

    # Create and run worker
    worker = await create_worker(client)

    print(f"Starting worker on task queue: {TASK_QUEUE}")
    print(f"Connected to Temporal at: {settings.temporal_host}")

    await worker.run()


def main() -> None:
    """Entry point for running the worker."""
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
