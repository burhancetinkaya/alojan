"""Separate scoped Telegram worker. Requires pinned owner grants; never reads transcripts."""

import argparse
import asyncio
import os
import signal

from alojan_contracts.secrets import SecretBox
from .action_delivery import ActionDelivery
from .telegram_delivery import Telegram


async def run(*, once=False):
    store = ActionDelivery(
        os.environ["ALOJAN_ACTIONS_DATABASE_URL"],
        SecretBox.from_file(os.environ["ALOJAN_CREDENTIAL_KEY_FILE"]),
    )
    transport = Telegram()
    while True:
        try:
            worked = await store.process_one(transport)
        except Exception:
            if once:
                raise
            # Recovery distinguishes unsent leases from uncertain sends; never log payloads.
            print("event=scoped_delivery_worker_unavailable", flush=True)
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
        print(f"event=scoped_delivery_worker_failed kind={type(error).__name__}", flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
