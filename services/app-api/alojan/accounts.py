"""Private operator recovery; passwords never pass through CLI arguments."""

import argparse
import getpass
import os

import psycopg

from alojan.auth import Accounts, AuthError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["reset-password"])
    parser.add_argument("login")
    args = parser.parse_args()
    first = getpass.getpass("New password (8–128 characters): ")
    if first != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords do not match")
    try:
        Accounts(os.environ["ALOJAN_DATABASE_URL"]).reset_password(args.login, first)
    except (AuthError, psycopg.Error):
        raise SystemExit("Recovery failed; check the account and database availability") from None
    print("Password replaced; all existing sessions revoked")


if __name__ == "__main__":
    main()
