"""Temporal worker for document processing workflows.

This module provides the worker that executes workflows and activities.
Run this as a separate process to handle workflow executions.
"""

import asyncio
import signal
from contextlib import suppress

import structlog
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

logger = structlog.get_logger(__name__)

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
    """Run the Temporal worker with graceful shutdown handling.

    This connects to Temporal and starts processing workflows.
    Handles SIGTERM/SIGINT for graceful shutdown.
    """
    from src.db import init_db

    worker: Worker | None = None
    shutdown_event = asyncio.Event()

    def handle_shutdown(signum: int, frame: object) -> None:
        """Handle shutdown signals gracefully."""
        sig_name = signal.Signals(signum).name
        logger.info("shutdown_signal_received", signal=sig_name)
        shutdown_event.set()

    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    try:
        # Initialize database connection for activities
        logger.info("initializing_database")
        await init_db()

        # Connect to Temporal with timeout
        logger.info("connecting_to_temporal", host=settings.temporal_host)
        try:
            client = await asyncio.wait_for(
                Client.connect(settings.temporal_host),
                timeout=30.0,
            )
        except TimeoutError:
            logger.error("temporal_connection_timeout", host=settings.temporal_host)
            raise RuntimeError(f"Failed to connect to Temporal at {settings.temporal_host}")

        # Create worker
        worker = await create_worker(client)

        logger.info(
            "worker_starting",
            task_queue=TASK_QUEUE,
            temporal_host=settings.temporal_host,
        )

        # Run worker until shutdown signal
        worker_task = asyncio.create_task(worker.run())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [worker_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        # Check if worker crashed
        if worker_task in done:
            exc = worker_task.exception()
            if exc:
                logger.error("worker_crashed", error=str(exc), exc_info=exc)
                raise exc

        logger.info("worker_shutdown_complete")

    except Exception as e:
        logger.error(
            "worker_fatal_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise
    finally:
        # Cleanup
        logger.info("worker_cleanup")


def main() -> None:
    """Entry point for running the worker."""
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
