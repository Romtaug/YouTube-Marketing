# comment_multi_channels.py
# pip install google-api-python-client google-auth-oauthlib isodate

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import google.oauth2.credentials as oauth2
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os, json, isodate, time, random, datetime as _dt

# ---------- AUTH CONFIG ----------
CLIENT_ID     = os.getenv("YT_CLIENT_ID")      # fourni via secrets/ENV
CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET")  # fourni via secrets/ENV
PORT          = 8080
SCOPES        = ["https://www.googleapis.com/auth/youtube.force-ssl"]
TOKEN_FILE    = "token_comment.json"

# ---------- COMMENT BUILDER (réaliste & variable) ----------
SUB_LINK = "https://youtube.com/@MrPlavon?sub_confirmation=1"
_utm = _dt.datetime.utcnow().strftime("%Y%m%d")
SUB_LINK_UTM = f"{SUB_LINK}&utm_source=yt_comments&utm_medium=bot&utm_campaign=auto_{_utm}"

# Ratios (tunable) — plus bas = plus safe
INCLUDE_LINK_RATIO  = 0.22   # % de commentaires avec le lien
SELF_MENTION_RATIO  = 0.35   # % de commentaires qui citent ta chaîne
EMOJI_RATIO         = 0.30   # % de commentaires avec emojis
MAX_EMOJIS          = 3
EMOJI_POOL = ["🔥","🚀","👏","💡","🎯","📈","👌","🙌","✨"]

PREFIXES = ["", "Franchement, ", "Honnêtement, ", "Pour être sincère, "]
CLOSERS  = ["", " Merci pour le partage.", " Hâte de voir la suite.", " Beau taf."]

SELF_MENTIONS = [
    " Je fais du contenu dans la même vibe sur ma chaîne.",
    " Je publie des analyses similaires, ça peut t’intéresser.",
    " Je teste des formats proches sur ma chaîne si ça te parle.",
    " Je poste des débriefs similaires de mon côté.",
]

VIDEO_TEMPLATES = [
    "{p}super clair et concret, j’ai pris 2–3 idées actionnables.{self}{link}{e}{c}",
    "{p}bon rythme et explications simples, ça donne envie de tester direct.{self}{link}{e}{c}",
    "{p}j’ai bien aimé la partie stratégie, ça m’a fait réfléchir.{self}{link}{e}{c}",
    "{p}zéro bla-bla, juste l’essentiel. tu feras un suivi sur ce sujet ?{self}{link}{e}{c}",
    "{p}merci pour la valeur, j’applique ça dès aujourd’hui.{self}{link}{e}{c}",
    "{p}bonne synthèse, curieux d’une version plus avancée.{self}{link}{e}{c}",
]

SHORT_TEMPLATES = [
    "{p}format efficace, message clair en 60s, j’aime beaucoup.{self}{link}{e}{c}",
    "{p}bonne punchline, action simple à faire maintenant.{self}{link}{e}{c}",
    "{p}court et utile, parfait pour s’y mettre sans se perdre.{self}{link}{e}{c}",
    "{p}très direct, ça motive à passer à l’action tout de suite.{self}{link}{e}{c}",
    "{p}petite pépite, je garde l’idée pour la semaine.{self}{link}{e}{c}",
]

def _maybe_link():
    return f" (si ça t’intéresse : {SUB_LINK_UTM})" if random.random() < INCLUDE_LINK_RATIO else ""

def _maybe_emojis():
    if random.random() > EMOJI_RATIO:
        return ""
    k = random.randint(1, MAX_EMOJIS)
    return " " + "".join(random.sample(EMOJI_POOL, k))

def _maybe_self_mention():
    return random.choice(SELF_MENTIONS) if random.random() < SELF_MENTION_RATIO else ""

def _polish(text: str, max_len: int = 230) -> str:
    t = " ".join(text.split())
    return (t[: max_len - 1] + "…") if len(t) > max_len else t

def make_comment_for_video():
    base = random.choice(VIDEO_TEMPLATES)
    txt = base.format(
        p=random.choice(PREFIXES), self=_maybe_self_mention(),
        link=_maybe_link(), e=_maybe_emojis(), c=random.choice(CLOSERS),
    )
    return _polish(txt)

def make_comment_for_short():
    base = random.choice(SHORT_TEMPLATES)
    txt = base.format(
        p=random.choice(PREFIXES), self=_maybe_self_mention(),
        link=_maybe_link(), e=_maybe_emojis(), c=random.choice(CLOSERS),
    )
    return _polish(txt)

# ---------- LISTE CHAÎNES (mode vendredi) ----------
CHANNEL_TARGETS = [
    # Mets ici ta liste FR — exemples :
    "Yomi Denzel", "Theophile Eliet", "@oussamaammaroff", "Enzo Honore",
    "Olivier Roland", "Marketing Mania", "Business Dynamite", "Le Marketeur Français",
    "Tugan Bara", "Antoine BM", "Jean Riviere", "Alexandre Roth",
    "Money Radar", "Yann Darwin", "Christopher Wangen", "Pierre Ollier",
    "Greenbull Campus", "Finary", "S'investir - Matthieu Louvet", "Epargnant 3.0",
    "Riche à 30 ans", "Investir Simple", "Le Revenu", "Capital",
    "David Laroche", "Franck Nicolas", "Alexandre Cormont", "Idriss Aberkane",
    "Jean Laval", "Laurent Chenot", "Emmanuel Fredenrich", "Anthony Nevo",
    "Pauline Laigneau", "Mind Parachutes",
    "Thinkerview", "Heu?reka", "Draw My Economy", "Institut des Libertes",
    "Les Echos", "BFM Business", "Zone Bourse", "IG France", "TV Finance",
    "Hasheur", "Cryptoast", "Journal du Coin", "Thami Kabbaj", "Young Trader Wealth",
    "@singeexplique", "@timotheemoiroux", "SébastienKoubar", "@Shubham_Sharma", "@sanspermissionpodcast", 
    "@monsieurrodolphe1", "@MatthieuLouvet", "@MoneyRadarAvis", "@moneyradarcrypto", "@amistory", "@GaspardG", "@hugodecrypteactus"
]

# ---------- PARAMS RECHERCHE THÈME (autres jours) ----------
THEME_QUERY = "argent investissement IA business"
SEARCH_REGION_CODE = "FR"
SEARCH_RELEVANCE_LANG = "fr"
SEARCH_PUBLISHED_AFTER_DAYS = 7   # vidéos récentes
SEARCH_PAGE_LIMIT = 6             # jusqu’à ~6*50=300 résultats bruts max
NEED_VIDEOS = 50                  # >= 60s
NEED_SHORTS = 50                  # < 60s

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
            if not CLIENT_ID or not CLIENT_SECRET:
                raise RuntimeError("CLIENT_ID/CLIENT_SECRET manquants (ENV YT_CLIENT_ID / YT_CLIENT_SECRET).")
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
                port=PORT, access_type="offline", prompt="consent",
                include_granted_scopes=False
            )
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

# ---------- Helpers API ----------
def iso_to_seconds(iso):
    return int(isodate.parse_duration(iso).total_seconds())

def comment(yt, video_id, text):
    body = {"snippet": {"videoId": video_id, "topLevelComment": {"snippet": {"textOriginal": text}}}}
    return yt.commentThreads().insert(part="snippet", body=body).execute()

def resolve_uploads_playlist(yt, target: str):
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

def find_last_video_and_short(yt, uploads_id):
    items = yt.playlistItems().list(
        part="contentDetails", playlistId=uploads_id, maxResults=50
    ).execute().get("items", [])
    if not items:
        return None, None

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
    return last_video, last_short

def search_theme_collect(yt, query, need_videos=50, need_shorts=50):
    """Retourne deux listes: [(id,title), ...] vidéos et shorts, par recherche globale récente."""
    import datetime as _dt
    published_after_ts = time.time() - SEARCH_PUBLISHED_AFTER_DAYS * 86400
    published_after_iso = _dt.datetime.utcfromtimestamp(published_after_ts).strftime("%Y-%m-%dT%H:%M:%SZ")

    videos, shorts = [], []
    page_token = None
    page_count = 0
    seen_ids = set()

    while page_count < SEARCH_PAGE_LIMIT and (len(videos) < need_videos or len(shorts) < need_shorts):
        res = yt.search().list(
            part="id,snippet", q=query, type="video", maxResults=50,
            regionCode=SEARCH_REGION_CODE, publishedAfter=published_after_iso,
            order="date", relevanceLanguage=SEARCH_RELEVANCE_LANG,
            pageToken=page_token
        ).execute()

        items = res.get("items", [])
        ids = [it["id"]["videoId"] for it in items if it["id"]["kind"] == "youtube#video"]
        if not ids:
            break

        # Récup durées
        dur_map = {}
        details = yt.videos().list(part="contentDetails,snippet", id=",".join(ids)).execute()
        for it in details.get("items", []):
            vid = it["id"]
            dur_s = iso_to_seconds(it["contentDetails"]["duration"])
            title = it["snippet"]["title"]
            dur_map[vid] = (title, dur_s)

        for vid in ids:
            if vid in seen_ids or vid not in dur_map:
                continue
            seen_ids.add(vid)
            title, dur = dur_map[vid]
            if dur < 60 and len(shorts) < need_shorts:
                shorts.append((vid, title))
            elif dur >= 60 and len(videos) < need_videos:
                videos.append((vid, title))
            if len(videos) >= need_videos and len(shorts) >= need_shorts:
                break

        page_token = res.get("nextPageToken")
        page_count += 1
        if not page_token:
            break

    return videos, shorts

# ---------- MAIN ----------
def main():
    yt = auth_youtube()
    # Vendredi ? (TZ respectée si ton runner a TZ=Europe/Paris)
    is_friday = (time.localtime().tm_wday == 4)  # Lundi=0 ... Vendredi=4

    total_comments = 0
    already_done = set()

    if is_friday:
        print("Mode: listes de YouTubers (vendredi)")
        # Cap global 50 vidéos + 50 shorts
        vids_needed, shorts_needed = 50, 50

        for target in CHANNEL_TARGETS:
            if vids_needed <= 0 and shorts_needed <= 0:
                break
            try:
                uploads_id, channel_title, _ = resolve_uploads_playlist(yt, target)
            except Exception as e:
                print(f"[WARN] Resolution echouee '{target}': {e}")
                continue

            last_video, last_short = find_last_video_and_short(yt, uploads_id)

            # Vidéo
            if last_video and vids_needed > 0:
                vid, title = last_video
                if vid not in already_done:
                    try:
                        text = make_comment_for_video()
                        resp = comment(yt, vid, text)
                        print(f"[OK] Liste: video '{title}' -> {resp['id']}")
                        total_comments += 1
                        vids_needed -= 1
                        already_done.add(vid)
                        time.sleep(1.2)
                    except HttpError as e:
                        print(f"[WARN] Echec com video '{title}' ({vid}): {e}")

            # Short (éviter doublon même id)
            if last_short and shorts_needed > 0:
                sid, stitle = last_short
                if sid not in already_done:
                    try:
                        text = make_comment_for_short()
                        resp = comment(yt, sid, text)
                        print(f"[OK] Liste: short '{stitle}' -> {resp['id']}")
                        total_comments += 1
                        shorts_needed -= 1
                        already_done.add(sid)
                        time.sleep(1.2)
                    except HttpError as e:
                        print(f"[WARN] Echec com short '{stitle}' ({sid}): {e}")

        print(f"Reste (après listes): videos={vids_needed}, shorts={shorts_needed}")

        # Si la liste n’a pas suffi, bascule en recherche pour compléter
        if vids_needed > 0 or shorts_needed > 0:
            print("Complément par recherche de thème pour atteindre 50/50.")
            vlist, slist = search_theme_collect(yt, THEME_QUERY, vids_needed, shorts_needed)

            for vid, title in vlist:
                if vid in already_done: continue
                try:
                    text = make_comment_for_video()
                    resp = comment(yt, vid, text)
                    print(f"[OK] Theme: video '{title}' -> {resp['id']}")
                    total_comments += 1
                    already_done.add(vid)
                    time.sleep(1.2)
                except HttpError as e:
                    print(f"[WARN] Echec com theme video '{title}' ({vid}): {e}")

            for sid, stitle in slist:
                if sid in already_done: continue
                try:
                    text = make_comment_for_short()
                    resp = comment(yt, sid, text)
                    print(f"[OK] Theme: short '{stitle}' -> {resp['id']}")
                    total_comments += 1
                    already_done.add(sid)
                    time.sleep(1.2)
                except HttpError as e:
                    print(f"[WARN] Echec com theme short '{stitle}' ({sid}): {e}")

    else:
        print("Mode: recherche par thème (hors vendredi)")
        vlist, slist = search_theme_collect(yt, THEME_QUERY, NEED_VIDEOS, NEED_SHORTS)

        for vid, title in vlist:
            try:
                text = make_comment_for_video()
                resp = comment(yt, vid, text)
                print(f"[OK] Theme: video '{title}' -> {resp['id']}")
                total_comments += 1
                time.sleep(1.2)
            except HttpError as e:
                print(f"[WARN] Echec com theme video '{title}' ({vid}): {e}")

        for sid, stitle in slist:
            try:
                text = make_comment_for_short()
                resp = comment(yt, sid, text)
                print(f"[OK] Theme: short '{stitle}' -> {resp['id']}")
                total_comments += 1
                time.sleep(1.2)
            except HttpError as e:
                print(f"[WARN] Echec com theme short '{stitle}' ({sid}): {e}")

    print(f"\nTotal de commentaires postes : {total_comments}")

# === Run ===
if __name__ == "__main__":
    main()



