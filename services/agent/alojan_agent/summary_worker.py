"""Separate scoped summary worker. Finalizes durable events; never sends notifications."""

import argparse
import asyncio
import os
import signal

from alojan_contracts.secrets import SecretBox
from .backend import Backend
from .credentials import ProviderClients
from .records import CallSummaries


async def process_one(store, credential_dsn, secrets):
    # Sequential jobs get independent clients; historical connections cannot exhaust a node cache.
    backend = Backend(credentials=ProviderClients(credential_dsn, secrets))
    try:
        return await store.process_one(backend)
    finally:
        await backend.close()


async def run(*, once=False):
    store = CallSummaries(os.environ["ALOJAN_SUMMARIES_DATABASE_URL"])
    credential_dsn = os.environ["ALOJAN_CREDENTIALS_DATABASE_URL"]
    secrets = SecretBox.from_file(os.environ["ALOJAN_CREDENTIAL_KEY_FILE"])
    while True:
        try:
            worked = await process_one(store, credential_dsn, secrets)
        except Exception:
            if once:
                raise
            # Preserve leased work for retry; never log provider/DB payloads.
            print("event=scoped_summary_worker_unavailable", flush=True)
            worked = False
        if once:
            return worked
        if not worked:
            await asyncio.sleep(1)


async def supervise(once):
    task = asyncio.create_task(run(once=once))
    loop = asyncio.get_running_loop()
    stopping = False

    def stop():
        nonlocal stopping
        if not stopping:
            stopping = True
            task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop)
    try:
        return await task
    except asyncio.CancelledError:
        if not stopping:
            raise
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Process at most one scoped job")
    args = parser.parse_args()
    try:
        asyncio.run(supervise(args.once))
    except Exception as error:
        print(f"event=scoped_summary_worker_failed kind={type(error).__name__}", flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
