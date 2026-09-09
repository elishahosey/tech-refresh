# YouTube Cleanup CLI

A small, deterministic CLI for reviewing YouTube subscriptions before deciding which channels to keep or remove. It provides explainable recommendations, local overrides, exports, dry runs, and confirmation-gated account changes.

The repository includes an opinionated **sample classification profile** covering educational content, fitness, hobbies, entertainment, consumerism, ragebait, and passive viewing patterns. These defaults are examples rather than universal judgments. Users can correct channel decisions and topic handling in their local `overrides.json` file without committing account-specific preferences.

The tool analyzes first. It never changes the account during review, never unsubscribes without explicit selection and a default-No confirmation, and supports `--dry-run`. Regular playlists are protected.

## API boundaries

Implemented: list subscriptions, fetch recent upload titles for classification, export results, persist overrides, and delete explicitly selected subscriptions after confirmation. The API also supports liked-video retrieval and removing a rating with `videos.rate(rating=none)`; those are not yet implemented.

The public YouTube Data API does **not** expose usable Watch Later or watch-history contents. Since September 2016, `WL` and `HL` return empty results. It also has no “Not interested” endpoint. The CLI therefore reports this limitation instead of claiming to clean those surfaces. Watch Later classification and playlist-suggestion logic are tested for a future user-provided export or supported API.

## Setup and OAuth

1. In Google Cloud, enable YouTube Data API v3, configure OAuth consent, and create a Desktop app credential.
2. Save it as `client_secrets_desktop.json`.
3. Install Python 3.10+ dependencies: `python -m pip install -r requirements.txt`.
4. Run `python main.py subscriptions review --limit 25`. First use opens browser consent and saves ignored `token.json`.

Review requests `https://www.googleapis.com/auth/youtube.readonly`. Real unsubscribe requests `https://www.googleapis.com/auth/youtube.force-ssl`. The original broad `youtube` scope also permits deletion, but the new CLI requests narrower documented scopes. No API key is needed. Treat the token and client-secret file as secrets.

## Commands

```powershell
python main.py subscriptions review
python main.py subscriptions review --only unsubscribe --limit 25
python main.py subscriptions review --category "Technical Learning"
python main.py subscriptions review --export review.json
python main.py subscriptions review --export review.csv

python main.py subscriptions unsubscribe --all-candidates --dry-run
python main.py subscriptions unsubscribe --from-config --dry-run
python main.py subscriptions unsubscribe --select 2 5 8 --dry-run
python main.py subscriptions unsubscribe --ids SUBSCRIPTION_ID --dry-run
python main.py subscriptions unsubscribe --select 2 5 8
python main.py subscriptions unsubscribe --from-config
python main.py subscriptions unsubscribe --ids SUBSCRIPTION_ID

python main.py overrides set-channel CHANNEL_ID always_keep
python main.py overrides set-channel CHANNEL_ID entertainment
python main.py overrides set-channel CHANNEL_ID always_review
python main.py overrides set-channel CHANNEL_ID protect

python main.py capabilities
python main.py watch-later review
```

Global file options precede the command, e.g. `python main.py --overrides cleanup-config.json subscriptions review`.

Review output includes both a numbered `ROW` and the permanent YouTube `SUBSCRIPTION ID`. Use `--select` with the displayed row numbers, or `--ids` with permanent IDs. Because an unsubscribe command performs a fresh review, repeat the same `--only`, `--category`, `--limit`, and `--recent-videos` options when selecting by row. The command prints the resolved channel names and IDs before confirmation.

To maintain your deletion selection in config instead of the command line, copy `overrides.example.json` to `overrides.json` and fill its array:

```json
{
  "unsubscribe_subscription_ids": [
    "SUBSCRIPTION_ID_1",
    "SUBSCRIPTION_ID_2"
  ]
}
```

Then run `python main.py subscriptions unsubscribe --from-config --dry-run`. Remove `--dry-run` only after checking the preview. Missing or stale configured IDs abort the whole operation rather than silently producing a partial deletion.

## Rules and overrides

Classification counts signals across channel name, description, and up to 25 recent titles. A single keyword is insufficient for unsubscribe: negative patterns must dominate across several items. The included sample profile treats educational content and practical projects positively and does not automatically penalize entertainment. Every result includes its leading topics, number of matching items, score, recommendation, and explanation.

Overrides use local JSON; see `overrides.example.json`. Channel actions are `always_keep`, `always_review`, `entertainment`, and `protect`. The schema also supports topic preferences (`useful`, `ignore`, `never_recommend`) and category-to-playlist mappings.

## Safety and protected playlists

- Review is read-only.
- Unsubscribe requires explicit selection, an exact preview, and `y`; Enter cancels.
- `--dry-run` changes nothing.
- No normal playlist is renamed, reordered, deleted, cleaned, or bulk-modified.
- Playlist names may only inform suggestions.
- No Watch Later operation is attempted because the API cannot return its contents.
- The legacy `python youTubeReset.py ...` entry point now uses these safeguards.

## Architecture

- `youtube_cleanup/client.py`: OAuth and API access.
- `youtube_cleanup/classifier.py`: deterministic scoring and playlist suggestions.
- `youtube_cleanup/overrides.py`: JSON preferences.
- `youtube_cleanup/cli.py`: display, export, selection, confirmation.
- `tests/`: regression tests.

Run tests with `python -m unittest discover -s tests -v`.

## Roadmap

Liked-video review; optional Watch Later analysis from a user-provided export; smarter learned preferences; topic prevalence and weekly reports; watch trends only if a legitimate source exists; optional local ML/LLM evaluation for borderline cases; stale-save and passive-viewing detection; and an optional GUI/web app only after the CLI proves useful.
