# comment_multi_channels.py
# pip install google-api-python-client google-auth-oauthlib isodate

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import google.oauth2.credentials as oauth2
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os, json, isodate, time

# ---------- AUTH CONFIG (en clair, comme demande) ----------
CLIENT_ID     = os.getenv("YT_CLIENT_ID", CLIENT_ID)
CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", CLIENT_SECRET)

PORT          = 8080
SCOPES        = ["https://www.googleapis.com/auth/youtube.force-ssl"]
TOKEN_FILE    = "token_comment.json"

# ---------- COMMENTAIRES ----------
# (Les emojis dans les commentaires YouTube sont OK, on les garde)
COMMENT_TEXT_VIDEO = "super la video 🚀"
COMMENT_TEXT_SHORT = "super le short 🎯"

# ---------- 50 cibles FR (Business/Finance/Mindset/eco/Crypto) ----------
# Test court pour valider le flux
CHANNEL_TARGETS = [
    "Squeezie",
    "MisterV",
]

"""
# Exemple de liste longue :
CHANNEL_TARGETS = [
    # Business / Entrepreneuriat (12)
    "Yomi Denzel",
    "Theophile Eliet",
    "@oussamaammaroff",
    "Enzo Honore",
    "Olivier Roland",
    "Marketing Mania",
    "Business Dynamite",
    "Le Marketeur Français",
    "Tugan Bara",
    "Antoine BM",
    "Jean Riviere",
    "Alexandre Roth",

    # Finance / Argent / Investissement (12 -> total 24)
    "Money Radar",
    "Yann Darwin",
    "Christopher Wangen",
    "Pierre Ollier",
    "Greenbull Campus",
    "Finary",
    "S'investir - Matthieu Louvet",
    "Epargnant 3.0",
    "Riche à 30 ans",
    "Investir Simple",
    "Le Revenu",
    "Capital",

    # Mindset / Motivation (10 -> total 34)
    "David Laroche",
    "Franck Nicolas",
    "Alexandre Cormont",
    "Idriss Aberkane",
    "Jean Laval",
    "Laurent Chenot",
    "Emmanuel Fredenrich",
    "Anthony Nevo",
    "Pauline Laigneau",
    "Mind Parachutes",

    # economie / Debats (9 -> total 43)
    "Thinkerview",
    "Heu?reka",
    "Draw My Economy",
    "Institut des Libertes",
    "Les Echos",
    "BFM Business",
    "Zone Bourse",
    "IG France",
    "TV Finance",

    # Crypto / Trading (6 -> total 49)
    "Hasheur",
    "Cryptoast",
    "Journal du Coin",
    "Thami Kabbaj",
    "Young Trader Wealth",     # (Elliot Hewitt)
    "CoinTips",

    # Specifiques (1 -> total 50)
    "@singeexplique",

    # (Remplacer une entree si tu veux rester à 50 strict)
    "Sebastien Koubar",
]
"""

# ---------- Utils auth ----------
def _load_token(path, scopes):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "refresh_token" not in data:
            return None
        return oauth2.Credentials.from_authorized_user_info(data, scopes)
    except Exception:
        return None

def auth_youtube():
    creds = _load_token(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = {
                "installed": {
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [f"http://localhost:{PORT}/"]
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(
                port=PORT,
                access_type="offline",
                prompt="consent",
                include_granted_scopes=False
            )
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

# ---------- Helpers ----------
def iso_to_seconds(iso):
    return int(isodate.parse_duration(iso).total_seconds())

def comment(yt, video_id, text):
    body = {
        "snippet": {
            "videoId": video_id,
            "topLevelComment": {"snippet": {"textOriginal": text}}
        }
    }
    return yt.commentThreads().insert(part="snippet", body=body).execute()

def resolve_uploads_playlist(yt, target: str):
    """
    Accepte:
      - @handle (avec @) -> forHandle
      - nom de chaîne -> search puis channels
    Retourne (uploads_playlist_id, channel_title, channel_id)
    """
    t = target.strip()
    if t.startswith("@"):
        h = t[1:]
        ch = yt.channels().list(part="id,snippet,contentDetails", forHandle=h).execute()
        items = ch.get("items", [])
        if not items:
            raise ValueError(f"Handle introuvable: {t}")
        c = items[0]
        upl = c["contentDetails"]["relatedPlaylists"]["uploads"]
        return upl, c["snippet"]["title"], c["id"]

    sr = yt.search().list(part="snippet", q=t, type="channel", maxResults=1).execute()
    sitems = sr.get("items", [])
    if not sitems:
        raise ValueError(f"Chaîne introuvable via recherche: {t}")
    channel_id = sitems[0]["snippet"]["channelId"]

    ch = yt.channels().list(part="id,snippet,contentDetails", id=channel_id).execute()
    items = ch.get("items", [])
    if not items:
        raise ValueError(f"Impossible de charger la chaîne: {t} ({channel_id})")
    c = items[0]
    upl = c["contentDetails"]["relatedPlaylists"]["uploads"]
    return upl, c["snippet"]["title"], c["id"]

def process_channel(yt, target):
    print(f"\nCible: {target}")
    try:
        uploads_id, channel_title, _ = resolve_uploads_playlist(yt, target)
    except Exception as e:
        print(f"[WARN] Resolution echouee '{target}': {e}")
        return 0

    items = yt.playlistItems().list(
        part="contentDetails", playlistId=uploads_id, maxResults=50
    ).execute().get("items", [])
    if not items:
        print(f"[SKIP] Pas d'uploads pour {channel_title}")
        return 0

    video_ids = [it["contentDetails"]["videoId"] for it in items]

    details = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        resp = yt.videos().list(part="contentDetails,snippet", id=",".join(chunk)).execute()
        for it in resp.get("items", []):
            details[it["id"]] = {
                "duration_s": iso_to_seconds(it["contentDetails"]["duration"]),
                "title": it["snippet"]["title"]
            }

    last_video = last_short = None
    for vid in video_ids:
        d = details.get(vid)
        if not d:
            continue
        if d["duration_s"] >= 60 and last_video is None:
            last_video = (vid, d["title"])
        if d["duration_s"] < 60 and last_short is None:
            last_short = (vid, d["title"])
        if last_video and last_short:
            break

    print("Derniere video :", last_video[1] if last_video else "N/A",
          f"https://www.youtube.com/watch?v={last_video[0]}" if last_video else "")
    print("Dernier short  :", last_short[1] if last_short else "N/A",
          f"https://www.youtube.com/watch?v={last_short[0]}" if last_short else "")

    targets = []
    if last_video: targets.append(("video", last_video[0], COMMENT_TEXT_VIDEO, last_video[1]))
    if last_short and (not last_video or last_short[0] != last_video[0]):
        targets.append(("short", last_short[0], COMMENT_TEXT_SHORT, last_short[1]))

    posted = 0
    for kind, vid, text, title in targets:
        try:
            resp = comment(yt, vid, text)
            print(f"[OK] Commentaire poste sur le {kind} '{title}' -> {resp['id']}")
            posted += 1
            time.sleep(1.5)
        except HttpError as e:
            print(f"[WARN] Impossible de commenter sur {kind} '{title}' ({vid}) : {e}")
    return posted

# === Execution ===
yt = auth_youtube()
total_comments = 0
for target in CHANNEL_TARGETS:
    total_comments += process_channel(yt, target)
    time.sleep(1.5)
print(f"\nTotal de commentaires postes : {total_comments}")