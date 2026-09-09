from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class Subscription:
    subscription_id: str
    channel_id: str
    channel_name: str
    description: str = ""
    recent_titles: tuple[str, ...] = ()


@dataclass
class Video:
    video_id: str
    title: str
    description: str = ""
    channel_name: str = ""
    duration_seconds: Optional[int] = None
    published_at: Optional[str] = None
    saved_at: Optional[str] = None


@dataclass
class Classification:
    item_id: str
    name: str
    score: int
    category: str
    recommendation: str
    reason: str
    detected_topics: tuple[str, ...] = ()
    destination: Optional[str] = None

    def to_dict(self):
        value = asdict(self)
        value["detected_topics"] = list(self.detected_topics)
        return value
