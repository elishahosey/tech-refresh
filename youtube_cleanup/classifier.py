import re
from collections import Counter
from datetime import datetime, timezone

from .models import Classification, Subscription, Video


TOPICS = {
    "Technical Learning": ("sql", "python", "postgres", "database", "backend", "etl", "aws", "docker", "terraform", "airflow", "snowflake", "linux", "software engineering", "data engineering", "algorithm", "system design"),
    "Security / Labs": ("cybersecurity", "cyber security", "soc lab", "def con", "penetration testing", "ctf", "malware", "network security"),
    "Projects / Building": ("build", "project", "robotics", "maker", "hands-on", "tutorial"),
    "Fitness": ("strength training", "running", "cardio", "mobility", "stretching", "nutrition", "workout", "fitness"),
    "Books / Learning": ("book", "reading", "literature"),
    "Anime": ("anime", "manga", "season impressions"),
    "Gaming": ("gaming", "gameplay", "video game", "playthrough"),
    "Dogs / Pets": ("dog", "puppy", "pet"),
    "Dating / Relationships": ("dating advice", "relationship podcast", "men vs women", "dating app", "breakup", "marriage pressure", "relationship advice"),
    "Drama / Ragebait": ("celebrity drama", "influencer drama", "outrage", "ragebait", "exposed", "meltdown", "destroyed", "reaction clip", "culture war", "doomposting"),
    "Career Anxiety": ("tech layoffs", "layoff panic", "software engineering is dead", "coding is dead", "ai replacing developers", "salary comparison", "faang obsession"),
    "Consumerism": ("shopping haul", "luxury haul", "you need this", "must buy", "amazon finds", "unboxing haul"),
    "Empty Self-Improvement": ("hustle culture", "hustle porn", "wake up at 4", "grindset", "dominate your day", "millionaire mindset"),
    "Shorts / Passive Watching": ("#shorts", "shorts compilation", "recycled tiktok", "clip farm", "reaction farm", "ai generated"),
}
POSITIVE = {"Technical Learning", "Security / Labs", "Projects / Building", "Fitness", "Books / Learning"}
ENTERTAINMENT = {"Anime", "Gaming", "Dogs / Pets"}
NEGATIVE = {"Dating / Relationships", "Drama / Ragebait", "Career Anxiety", "Consumerism", "Empty Self-Improvement", "Shorts / Passive Watching"}


def _matches(text: str) -> Counter:
    normalized = re.sub(r"[^a-z0-9+#]+", " ", text.lower())
    result = Counter()
    for topic, phrases in TOPICS.items():
        for phrase in phrases:
            if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", normalized):
                result[topic] += 1
    return result


def classify_subscription(item: Subscription, overrides: dict | None = None) -> Classification:
    overrides = overrides or {}
    counts, documents = Counter(), Counter()
    for text in (item.channel_name, item.description, *item.recent_titles):
        found = _matches(text)
        counts.update(found)
        documents.update(found.keys())
    for topic, preference in overrides.get("topic_preferences", {}).items():
        if topic in counts and preference == "useful":
            counts[topic] += 2
        elif preference in {"ignore", "never_recommend"}:
            counts.pop(topic, None)
    useful = sum(counts[t] for t in POSITIVE)
    fun = sum(counts[t] for t in ENTERTAINMENT)
    noise = sum(counts[t] for t in NEGATIVE)
    score = max(0, min(100, 50 + useful * 8 + fun * 6 - noise * 9))
    topics = tuple(t for t, _ in counts.most_common())
    category = topics[0] if topics else "Other"
    override = overrides.get("channels", {}).get(item.channel_id)
    if override in {"always_keep", "protect"}:
        recommendation, score, reason = "KEEP_HIGH_VALUE", max(score, 90), "Your local override protects this channel."
    elif override == "entertainment":
        recommendation, score, category, reason = "KEEP_ENTERTAINMENT", max(score, 75), "Useful Entertainment", "Your local override marks this channel as intentional entertainment."
    elif override == "always_review":
        recommendation, reason = "REVIEW", "Your local override requires manual review of this channel."
    elif useful >= 3 and useful >= noise:
        recommendation, reason = "KEEP_HIGH_VALUE", _reason(counts, documents, len(item.recent_titles), "useful content dominates")
    elif fun >= 2 and fun >= noise:
        recommendation, reason = "KEEP_ENTERTAINMENT", _reason(counts, documents, len(item.recent_titles), "intentional entertainment is valuable")
    elif noise >= 5 and noise >= useful + fun + 2 and sum(documents[t] for t in NEGATIVE) >= 3:
        recommendation, reason = "UNSUBSCRIBE_CANDIDATE", _reason(counts, documents, len(item.recent_titles), "negative patterns dominate across multiple items")
    elif noise >= 2 and noise > useful + fun:
        recommendation, reason = "LOW_VALUE", _reason(counts, documents, len(item.recent_titles), "low-value patterns outweigh useful or enjoyable signals")
    else:
        recommendation, reason = "REVIEW", _reason(counts, documents, len(item.recent_titles), "signals are mixed or insufficient")
    return Classification(item.subscription_id, item.channel_name, score, category, recommendation, reason, topics)


def _reason(counts, documents, recent_count, conclusion):
    if not counts:
        return f"Not enough recognizable topic signals; {conclusion}."
    leaders = [f"{topic} ({documents[topic]} items)" for topic, _ in counts.most_common(3)]
    sample = f" among {recent_count} recent titles" if recent_count else ""
    return f"Detected {', '.join(leaders)}{sample}; {conclusion}."


def classify_watch_later(video: Video, playlist_names=None, overrides=None, now=None) -> Classification:
    overrides, playlist_names = overrides or {}, playlist_names or []
    counts = _matches(" ".join((video.title, video.description, video.channel_name)))
    topics = tuple(t for t, _ in counts.most_common())
    category = topics[0] if topics else "Other"
    destination = suggest_playlist(category, playlist_names, overrides)
    age_days = 0
    if video.saved_at:
        try:
            saved = datetime.fromisoformat(video.saved_at.replace("Z", "+00:00"))
            age_days = ((now or datetime.now(timezone.utc)) - saved).days
        except ValueError:
            pass
    noise, useful, fun = (sum(counts[t] for t in group) for group in (NEGATIVE, POSITIVE, ENTERTAINMENT))
    override = overrides.get("channels", {}).get(video.channel_name) or overrides.get("channels", {}).get(video.video_id)
    if override in {"always_keep", "protect", "entertainment"}:
        rec, score, reason = "KEEP_IN_WATCH_LATER", 90, "A local override protects this channel or video."
    elif noise >= 2 or (noise and age_days > 180):
        rec, score = "REMOVE_FROM_WATCH_LATER", max(0, 45 - noise * 10)
        reason = f"Detected {category} signals" + (f" and the save is {age_days} days old." if age_days else ".")
    elif useful and destination:
        rec, score, reason = "MOVE_TO_PLAYLIST", min(100, 65 + useful * 7), "Useful evergreen content fits a protected permanent playlist better than a temporary queue."
    elif fun:
        rec, score, reason = "WATCH_SOON", 75, "Intentional entertainment is valid; keep it queued only if you realistically plan to watch it."
    elif age_days > 365:
        rec, score, reason = "REVIEW", 40, f"This save is {age_days} days old and has no strong recognized topic signal."
    else:
        rec, score, reason = "REVIEW", 50, "No strong deterministic signal; review manually."
    return Classification(video.video_id, video.title, score, category, rec, reason, topics, destination)


def suggest_playlist(category: str, playlist_names: list[str], overrides=None) -> str | None:
    overrides = overrides or {}
    if category in overrides.get("playlist_destinations", {}):
        return overrides["playlist_destinations"][category]
    words = {
        "Technical Learning": ("database", "sql", "python", "data", "software", "tech", "learning"),
        "Security / Labs": ("security", "cyber", "soc", "lab"), "Projects / Building": ("project", "build", "maker", "robot"),
        "Fitness": ("fitness", "strength", "running", "mobility", "health"), "Books / Learning": ("book", "reading"),
        "Anime": ("anime",), "Gaming": ("gaming", "games"), "Dogs / Pets": ("dog", "pets"),
    }.get(category, ())
    ranked = sorted(((sum(word in name.lower() for word in words), name) for name in playlist_names), reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] else None
