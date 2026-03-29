"""
manage_clients.py — Interactive CLI for managing the client and owner list.

Usage (interactive menu):
  python manage_clients.py

Usage (non-interactive / scriptable):
  python manage_clients.py list
  python manage_clients.py add  "Acme Corp" "Jane Doe"
  python manage_clients.py remove <id>
  python manage_clients.py export          # re-export clients.csv from the DB

The client list is stored in signals.db and seeded from clients.csv on startup.
Edits made here are immediately persisted in the database.

Tip: After adding/removing clients via this tool you can also sync clients.csv
by running:  python manage_clients.py export
"""

import argparse
import csv
import os
import sys

import database

CSV_PATH = os.path.join(os.path.dirname(__file__), "clients.csv")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _print_table(clients: list[dict]) -> None:
    if not clients:
        print("  (no clients found)")
        return
    id_w = max(len("ID"), max(len(str(c["id"])) for c in clients))
    name_w = max(len("Client Name"), max(len(c["name"]) for c in clients))
    owner_w = max(len("Owner Name"), max(len(c["owner_name"]) for c in clients))
    sep = f"+{'-' * (id_w + 2)}+{'-' * (name_w + 2)}+{'-' * (owner_w + 2)}+"
    header = f"| {'ID':<{id_w}} | {'Client Name':<{name_w}} | {'Owner Name':<{owner_w}} |"
    print(sep)
    print(header)
    print(sep)
    for c in clients:
        print(f"| {c['id']:<{id_w}} | {c['name']:<{name_w}} | {c['owner_name']:<{owner_w}} |")
    print(sep)


# ---------------------------------------------------------------------------
# CLI actions
# ---------------------------------------------------------------------------

def cmd_list() -> None:
    """Print all clients in a formatted table."""
    clients = database.list_clients()
    print(f"\nClients ({len(clients)} total):\n")
    _print_table(clients)
    print()


def cmd_add(name: str, owner_name: str) -> None:
    """Add a new client."""
    name = name.strip()
    owner_name = owner_name.strip()
    if not name or not owner_name:
        print("Error: both name and owner_name are required.")
        sys.exit(1)
    new_id = database.add_client(name, owner_name)
    print(f"✓ Added: [{new_id}] {name!r} → {owner_name!r}")


def cmd_remove(client_id: int) -> None:
    """Remove a client by ID."""
    clients = database.list_clients()
    target = next((c for c in clients if c["id"] == client_id), None)
    if target is None:
        print(f"Error: no client with id={client_id}.")
        sys.exit(1)
    confirm = input(
        f"Remove [{client_id}] {target['name']!r} (owner: {target['owner_name']!r})? [y/N] "
    ).strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return
    database.remove_client(client_id)
    print(f"✓ Removed client [{client_id}] {target['name']!r}.")


def cmd_export() -> None:
    """Write the current database state back to clients.csv."""
    clients = database.list_clients()
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        f.write(
            "# clients.csv — Client and Owner seed list\n"
            "# Edit this file to manage clients, then restart the app or run database.py\n"
            "# Format: name,owner_name\n"
            "#\n"
        )
        writer = csv.writer(f)
        writer.writerow(["name", "owner_name"])
        for c in clients:
            writer.writerow([c["name"], c["owner_name"]])
    print(f"✓ Exported {len(clients)} clients to '{CSV_PATH}'.")


# ---------------------------------------------------------------------------
# Interactive menu
# ---------------------------------------------------------------------------

def interactive_menu() -> None:
    database.init_db()
    while True:
        print("\n=== Client Manager ===")
        print("  1. List clients")
        print("  2. Add a client")
        print("  3. Remove a client")
        print("  4. Export to clients.csv")
        print("  5. Quit")
        choice = input("Choice [1-5]: ").strip()

        if choice == "1":
            cmd_list()

        elif choice == "2":
            name = input("  Client name : ").strip()
            owner = input("  Owner name  : ").strip()
            if name and owner:
                cmd_add(name, owner)
            else:
                print("  Both fields are required.")

        elif choice == "3":
            cmd_list()
            try:
                cid = int(input("  Enter client ID to remove: ").strip())
            except ValueError:
                print("  Invalid ID.")
                continue
            cmd_remove(cid)

        elif choice == "4":
            cmd_export()

        elif choice == "5":
            print("Goodbye.")
            break

        else:
            print("  Please enter a number from 1 to 5.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage the client and owner list for Client Signal Notifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python manage_clients.py                       # interactive menu
  python manage_clients.py list                  # print all clients
  python manage_clients.py add "Acme Corp" "Jane Doe"
  python manage_clients.py remove 3
  python manage_clients.py export                # write DB → clients.csv
""",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List all clients")

    add_p = sub.add_parser("add", help="Add a new client")
    add_p.add_argument("name", help="Client company name")
    add_p.add_argument("owner_name", help="Owner / account manager name")

    rem_p = sub.add_parser("remove", help="Remove a client by ID")
    rem_p.add_argument("id", type=int, help="Client ID (see 'list')")

    sub.add_parser("export", help="Export current DB state to clients.csv")

    args = parser.parse_args()

    if args.command is None:
        # No sub-command → launch interactive menu
        interactive_menu()
        return

    database.init_db()

    if args.command == "list":
        cmd_list()
    elif args.command == "add":
        cmd_add(args.name, args.owner_name)
    elif args.command == "remove":
        cmd_remove(args.id)
    elif args.command == "export":
        cmd_export()


if __name__ == "__main__":
    main()
