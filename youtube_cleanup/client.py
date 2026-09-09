from pathlib import Path

from .models import Subscription

READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
WRITE_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"


class YouTubeClient:
    def __init__(self, service):
        self.service = service

    @classmethod
    def authenticate(cls, secrets="client_secrets_desktop.json", token="token.json", write=False):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError("Install dependencies with: pip install -r requirements.txt") from exc
        scopes = [WRITE_SCOPE if write else READONLY_SCOPE]
        credentials = None
        token_path = Path(token)
        if token_path.exists():
            credentials = Credentials.from_authorized_user_file(token_path, scopes)
            if not credentials.has_scopes(scopes):
                credentials = None
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        if not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(secrets, scopes)
            credentials = flow.run_local_server(port=0)
            token_path.write_text(credentials.to_json(), encoding="utf-8")
        return cls(build("youtube", "v3", credentials=credentials))

    def _pages(self, request_factory):
        token = None
        while True:
            response = request_factory(token).execute()
            yield from response.get("items", [])
            token = response.get("nextPageToken")
            if not token:
                break

    def subscriptions(self, recent_limit=25, limit=None):
        request = lambda token: self.service.subscriptions().list(
            part="id,snippet", mine=True, maxResults=50, pageToken=token
        )
        raw = list(self._pages(request))
        if limit is not None:
            raw = raw[:limit]
        channel_ids = [x["snippet"]["resourceId"]["channelId"] for x in raw]
        uploads = {}
        for start in range(0, len(channel_ids), 50):
            batch = self.service.channels().list(part="contentDetails", id=",".join(channel_ids[start:start + 50])).execute()
            for channel in batch.get("items", []):
                uploads[channel["id"]] = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        results = []
        for sub in raw:
            snippet = sub["snippet"]
            channel_id = snippet["resourceId"]["channelId"]
            titles = ()
            if recent_limit and uploads.get(channel_id):
                response = self.service.playlistItems().list(
                    part="snippet", playlistId=uploads[channel_id], maxResults=min(50, recent_limit)
                ).execute()
                titles = tuple(x["snippet"].get("title", "") for x in response.get("items", []))
            results.append(Subscription(sub["id"], channel_id, snippet.get("title", snippet.get("channelTitle", channel_id)), snippet.get("description", ""), titles))
        return results

    def playlist_names(self):
        request = lambda token: self.service.playlists().list(part="snippet", mine=True, maxResults=50, pageToken=token)
        return [item["snippet"]["title"] for item in self._pages(request)]

    def unsubscribe(self, subscription_id):
        self.service.subscriptions().delete(id=subscription_id).execute()

    @staticmethod
    def watch_later_supported():
        return False
