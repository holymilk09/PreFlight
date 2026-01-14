#!/usr/bin/env python3
"""Bootstrap script to create tenant and API key for benchmarking.

Run this before running the benchmark to set up required test data.

Usage:
    python scripts/setup_benchmark_data.py
"""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from uuid_extensions import uuid7

# Load environment from .env file
from dotenv import load_dotenv
load_dotenv()

from src.config import settings
from src.models import APIKey, Tenant
from src.security import generate_api_key


async def setup_benchmark_data():
    """Create tenant and API key for benchmarking."""

    print("Setting up benchmark data...")
    print(f"Database: {settings.database_url.split('@')[1]}")  # Hide credentials

    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )

    async_session = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    # Check if tables exist
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'tenants')"
        ))
        tables_exist = result.scalar()

        if not tables_exist:
            print("Tables don't exist. Run 'make migrate' first.")
            await engine.dispose()
            return None

    # Create benchmark tenant
    async with async_session() as session:
        # Check if benchmark tenant already exists
        result = await session.execute(
            text("SELECT id FROM tenants WHERE name = 'Benchmark Tenant' LIMIT 1")
        )
        existing = result.first()

        if existing:
            tenant_id = existing[0]
            print(f"Benchmark tenant already exists: {tenant_id}")
        else:
            tenant = Tenant(
                name="Benchmark Tenant",
                settings={"plan": "enterprise", "purpose": "benchmarking"},
            )
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
            tenant_id = tenant.id
            print(f"Created benchmark tenant: {tenant_id}")

        # Check if benchmark API key exists
        result = await session.execute(
            text("SELECT key_prefix FROM api_keys WHERE name = 'benchmark-key' LIMIT 1")
        )
        existing_key = result.first()

        if existing_key:
            print(f"Benchmark API key already exists with prefix: {existing_key[0]}")
            print("\nTo get the full key, you need to create a new one.")
            print("Delete existing key first if needed.")

            # Generate new key anyway for convenience
            key_components = generate_api_key()

            api_key = APIKey(
                tenant_id=tenant_id,
                key_hash=key_components.key_hash,
                key_prefix=key_components.key_prefix,
                name=f"benchmark-key-{uuid7().hex[:8]}",
                scopes=["*"],
                rate_limit=10000,  # High limit for benchmarking
            )
            session.add(api_key)
            await session.commit()

            print(f"\nCreated NEW benchmark API key:")
            print(f"  Full key: {key_components.full_key}")
            print(f"  Prefix:   {key_components.key_prefix}")
        else:
            # Create new API key
            key_components = generate_api_key()

            api_key = APIKey(
                tenant_id=tenant_id,
                key_hash=key_components.key_hash,
                key_prefix=key_components.key_prefix,
                name="benchmark-key",
                scopes=["*"],
                rate_limit=10000,  # High limit for benchmarking
            )
            session.add(api_key)
            await session.commit()

            print(f"\nCreated benchmark API key:")
            print(f"  Full key: {key_components.full_key}")
            print(f"  Prefix:   {key_components.key_prefix}")

    await engine.dispose()

    print("\n" + "=" * 60)
    print("BENCHMARK SETUP COMPLETE")
    print("=" * 60)
    print("\nTo run benchmark:")
    print(f"  python scripts/benchmark_evaluate.py --api-key {key_components.full_key}")
    print("\nOr export the key:")
    print(f"  export BENCHMARK_API_KEY={key_components.full_key}")
    print("  python scripts/benchmark_evaluate.py --api-key $BENCHMARK_API_KEY")
    print("=" * 60)

    return key_components.full_key


if __name__ == "__main__":
    asyncio.run(setup_benchmark_data())
