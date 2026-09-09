import argparse
import csv
import json
import sys
from pathlib import Path

from .classifier import classify_subscription
from .client import YouTubeClient
from .overrides import load_overrides, save_channel_override


RECOMMENDATION_ALIASES = {
    "unsubscribe": "UNSUBSCRIBE_CANDIDATE", "review": "REVIEW", "low-value": "LOW_VALUE",
    "keep": "KEEP_HIGH_VALUE", "entertainment": "KEEP_ENTERTAINMENT",
}


def parser():
    root = argparse.ArgumentParser(description="Explainable, approval-first YouTube cleanup")
    root.add_argument("--secrets", default="client_secrets_desktop.json")
    root.add_argument("--token", default="token.json")
    root.add_argument("--overrides", default="overrides.json")
    groups = root.add_subparsers(dest="group", required=True)
    subscriptions = groups.add_parser("subscriptions")
    subcommands = subscriptions.add_subparsers(dest="command", required=True)
    review = subcommands.add_parser("review")
    _review_options(review)
    unsubscribe = subcommands.add_parser("unsubscribe")
    _review_options(unsubscribe)
    unsubscribe.add_argument("--ids", nargs="*", default=[], help="Exact subscription IDs to select")
    unsubscribe.add_argument("--select", nargs="*", type=int, default=[], help="Displayed row numbers to select (for example: --select 2 5 8)")
    unsubscribe.add_argument("--from-config", action="store_true", help="Select IDs from unsubscribe_subscription_ids in the overrides file")
    unsubscribe.add_argument("--all-candidates", action="store_true", help="Select every displayed UNSUBSCRIBE_CANDIDATE")
    unsubscribe.add_argument("--dry-run", action="store_true")
    overrides = groups.add_parser("overrides")
    override_commands = overrides.add_subparsers(dest="command", required=True)
    set_channel = override_commands.add_parser("set-channel")
    set_channel.add_argument("channel_id")
    set_channel.add_argument("action", choices=("always_keep", "always_review", "entertainment", "protect"))
    watch_later = groups.add_parser("watch-later")
    watch_later.add_subparsers(dest="command", required=True).add_parser("review")
    groups.add_parser("capabilities")
    return root


def _review_options(command):
    command.add_argument("--only", choices=tuple(RECOMMENDATION_ALIASES))
    command.add_argument("--category")
    command.add_argument("--limit", type=int)
    command.add_argument("--recent-videos", type=int, default=25)
    command.add_argument("--export", help="Output .json or .csv file")


def main(argv=None):
    args = parser().parse_args(argv)
    if args.group == "overrides":
        save_channel_override(args.overrides, args.channel_id, args.action)
        print(f"Saved {args.action} override for {args.channel_id} in {args.overrides}")
        return 0
    if args.group == "capabilities":
        _capabilities()
        return 0
    if args.group == "watch-later":
        print("Watch Later cannot be retrieved or modified through the public YouTube Data API.")
        print("Since September 2016, playlistItems.list for WL returns an empty list. No account action was attempted.")
        return 2
    write = args.command == "unsubscribe" and not args.dry_run
    try:
        client = YouTubeClient.authenticate(args.secrets, args.token, write=write)
        results = [classify_subscription(item, load_overrides(args.overrides)) for item in client.subscriptions(args.recent_videos, args.limit)]
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    results = _filter(results, args)
    _display(results)
    if args.export:
        _export(results, args.export)
    if args.command == "unsubscribe":
        return _unsubscribe(client, results, args, load_overrides(args.overrides))
    return 0


def _filter(results, args):
    if args.only:
        results = [r for r in results if r.recommendation == RECOMMENDATION_ALIASES[args.only]]
    if args.category:
        results = [r for r in results if r.category.casefold() == args.category.casefold()]
    return results


def _display(results):
    if not results:
        print("No matching subscriptions.")
        return
    print("ROW | SUBSCRIPTION ID | CHANNEL | SCORE | CATEGORY | RECOMMENDATION")
    for row, result in enumerate(results, 1):
        print(f"\n{row} | {result.item_id} | {result.name} | {result.score} | {result.category} | {result.recommendation}")
        print(f"  {result.reason}")


def _export(results, filename):
    path, rows = Path(filename), [r.to_dict() for r in results]
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    elif path.suffix.lower() == ".csv":
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else ["item_id", "name"])
            writer.writeheader()
            for row in rows:
                row["detected_topics"] = "; ".join(row["detected_topics"])
                writer.writerow(row)
    else:
        raise ValueError("Export filename must end in .json or .csv")
    print(f"Exported {len(rows)} results to {path}")


def _unsubscribe(client, results, args, overrides=None):
    overrides = overrides or {}
    candidates = {r.item_id: r for r in results}
    selected_rows = getattr(args, "select", [])
    invalid_rows = [row for row in selected_rows if row < 1 or row > len(results)]
    if invalid_rows:
        print(f"Invalid row number(s): {', '.join(map(str, invalid_rows))}; no account changes made.")
        return 2
    explicitly_selected = {results[row - 1].item_id for row in selected_rows}
    explicitly_selected.update(item_id for item_id in args.ids if item_id in candidates)
    configured_ids = overrides.get("unsubscribe_subscription_ids", []) if getattr(args, "from_config", False) else []
    if not isinstance(configured_ids, list) or not all(isinstance(item_id, str) for item_id in configured_ids):
        print("unsubscribe_subscription_ids must be an array of strings; no account changes made.")
        return 2
    explicitly_selected.update(item_id for item_id in configured_ids if item_id in candidates)
    missing_ids = [item_id for item_id in configured_ids if item_id not in candidates]
    if missing_ids:
        print("Configured subscription ID(s) were not found in the current results:")
        for item_id in missing_ids:
            print(f"- {item_id}")
        print("No account changes made. Remove stale IDs or adjust the current filters/limit.")
        return 2
    if args.all_candidates:
        selected = [r for r in results if r.recommendation == "UNSUBSCRIBE_CANDIDATE"]
    else:
        selected = [r for r in results if r.item_id in explicitly_selected]
    if not selected:
        print("No subscriptions selected; no account changes made.")
        return 0
    print(f"\nYou are about to unsubscribe from {len(selected)} channel(s):")
    for item in selected:
        print(f"- {item.name} ({item.item_id})")
    if args.dry_run:
        print("Dry run: no account changes made.")
        return 0
    if input("Continue? [y/N] ").strip().lower() != "y":
        print("Cancelled; no account changes made.")
        return 0
    for item in selected:
        client.unsubscribe(item.item_id)
        print(f"Unsubscribed: {item.name}")
    return 0


def _capabilities():
    print("Supported: subscription review/delete; user playlist-name inspection; liked-video listing and rating removal are API-capable but not yet implemented.")
    print("Unsupported by public API: Watch Later contents, watch history contents/deletion, and 'Not interested' feedback.")
    print("All normal playlists are protected by this tool.")
