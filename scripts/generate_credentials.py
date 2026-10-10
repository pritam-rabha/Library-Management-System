"""Create the administrator password hash (and optionally a SECRET_KEY).

Usage:
    python scripts/generate_credentials.py            # prompts for a password, prints its hash
    python scripts/generate_credentials.py --secret   # prints a random SECRET_KEY
"""
import argparse
import getpass
import secrets
import sys

from werkzeug.security import generate_password_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--secret", action="store_true", help="print a random SECRET_KEY instead")
    args = parser.parse_args()

    if args.secret:
        print(secrets.token_hex(32))
        return 0

    password = getpass.getpass("Administrator password (at least 10 characters): ")
    if len(password) < 10:
        print("The password must be at least 10 characters long.", file=sys.stderr)
        return 1
    if password != getpass.getpass("Repeat the password: "):
        print("The passwords do not match.", file=sys.stderr)
        return 1
    print("\nAdd this line to your .env file (or the Render environment settings):\n")
    print("ADMIN_PASSWORD_HASH=" + generate_password_hash(password, method="pbkdf2:sha256"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
