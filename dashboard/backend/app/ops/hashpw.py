"""Makes welldash²'s settings lines: a hash of the password you type (never shown or stored) and a random secret key.

    docker compose exec backend python -m ops.hashpw     (on the VM, from ~/WELLWebsite; any container of the
                                                          backend image works, e.g. run --rm --no-deps ops)

Prints two lines to add to the env file docker compose reads (see README.md in this folder, "Setting it up"):
    OPS_PASSWORD_HASH='scrypt:...'     single quotes keep compose from reading its $ signs as variables
    OPS_SECRET_KEY='...'               signs the session cookie; a new one signs everyone out
--hash-only prints just the first line, to change the password and keep the secret key. (A new password signs
everyone out either way.)
"""
import argparse
import getpass
import secrets
import sys

from werkzeug.security import generate_password_hash

MIN_LENGTH = 12


def main(argv=None, ask=getpass.getpass, out=print):
    parser = argparse.ArgumentParser(description="Print welldash²'s OPS_PASSWORD_HASH and OPS_SECRET_KEY lines.")
    parser.add_argument("--hash-only", action="store_true", help="print only the OPS_PASSWORD_HASH line")
    args = parser.parse_args(argv)
    password = ask("New welldash² password: ")
    if len(password) < MIN_LENGTH:
        print(f"Use at least {MIN_LENGTH} characters.", file=sys.stderr)
        return 1
    if ask("Same password again: ") != password:
        print("The two entries differ; nothing printed.", file=sys.stderr)
        return 1
    out(f"OPS_PASSWORD_HASH='{generate_password_hash(password, method='scrypt')}'")
    if not args.hash_only:
        out(f"OPS_SECRET_KEY='{secrets.token_urlsafe(48)}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
