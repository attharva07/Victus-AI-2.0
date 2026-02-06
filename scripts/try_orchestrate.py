from __future__ import annotations

import argparse
import json
import os

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual /orchestrate helper")
    parser.add_argument("text", help="Text to send to /orchestrate")
    parser.add_argument("--base-url", default=os.getenv("VICTUS_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("VICTUS_TOKEN"))
    args = parser.parse_args()

    if not args.token:
        raise SystemExit("Missing token. Set --token or VICTUS_TOKEN.")

    response = requests.post(
        f"{args.base_url.rstrip('/')}/orchestrate",
        headers={"Authorization": f"Bearer {args.token}"},
        json={"text": args.text},
        timeout=20,
    )
    print(f"status={response.status_code}")
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()
