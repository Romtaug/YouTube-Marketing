# comment_multi_channels.py
# Dépendances: google-api-python-client google-auth-oauthlib isodate
# pip install google-api-python-client google-auth-oauthlib isodate

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import google.oauth2.credentials as oauth2
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import os, json, isodate, time, random, datetime as _dt

# ===============================
# CONFIG AUTH
# ===============================
CLIENT_ID     = os.getenv("YT_CLIENT_ID")      # via secrets/ENV
CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET")  # via secrets/ENV
PORT          = 8080
SCOPES        = ["https://www.googleapis.com/auth/youtube.force-ssl"]
TOKEN_FILE    = "token_comment.json"

# ===============================
# COMMENT BUILDER (réaliste & variable)
# ===============================
SUB_LINK = "https://youtube.com/@MrPlavon?sub_confirmation=1"
_utm = _dt.datetime.utcnow().strftime("%Y%m%d")
SUB_LINK_UTM = f"{SUB_LINK}&utm_source=yt_comments&utm_medium=bot&utm_campaign=auto_{_utm}"

# Ratios (ajuste si tu veux être plus/moins agressif)
INCLUDE_LINK_RATIO  = 0.25   # % de commentaires avec le lien d’abo
SELF_MENTION_RATIO  = 0.45   # % avec mention “je fais du contenu similaire”
EMOJI_RATIO         = 0.5   # % avec 1–3 emojis
MAX_EMOJIS          = 3
EMOJI_POOL = ["🔥","🚀","👏","💡","🎯","📈","👌","🙌","✨"]

PREFIXES = ["", "Franchement, ", "Honnêtement, ", "Pour être sincère, "]
CLOSERS  = ["", " Merci pour le partage.", " Hâte de voir la suite.", " Beau taf."]

SELF_MENTIONS = [
    " Je fais du contenu dans la même vibe sur ma chaîne.",
    " Je publie des analyses similaires, ça peut vous intéresser.",
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

# ===============================
# LISTE CHAÎNES (mode vendredi)
# ===============================
CHANNEL_TARGETS = [
    "Yomi Denzel", "Theophile Eliet", "@oussamaammaroff", "Enzo Honore",
    "Olivier Roland", "Marketing Mania", "Business Dynamite", "Le Marketeur Français",
    "Tugan Bara", "Antoine BM", "Jean Riviere", "Alexandre Roth",
    "Money Radar", "Yann Darwin", "Christopher Wangen", "Pierre Ollier",
    "Greenbull Campus", "Finary", "S'investir - Matthieu Louvet", "Epargnant 3.0",
    "Riche à 30 ans", "Investir Simple", "Le Revenu", "Capital",
    "David Laroche", "Franck Nicolas", "Alexandre Cormont", "Idriss Aberkane",
    "Jean Laval", "Laurent Chenot", "Emmanuel Fredenrich", "Anthony Nevo",
    "Pauline Laigneau", "Mind Parachutes", "@ego_one", "@LaMenaceVlogs",
    "Thinkerview", "Heu?reka", "Draw My Economy", "Institut des Libertes",
    "Les Echos", "BFM Business", "Zone Bourse", "IG France", "TV Finance",
    "Hasheur", "Cryptoast", "Journal du Coin", "Thami Kabbaj", "Young Trader Wealth",
    "@singeexplique", "@timotheemoiroux", "SébastienKoubar", "@Shubham_Sharma",
    "@sanspermissionpodcast", "@monsieurrodolphe1", "@MatthieuLouvet",
    "@MoneyRadarAvis", "@moneyradarcrypto", "@amistory", "@GaspardG", "@hugodecrypteactus"
]

# ===============================
# RECHERCHE THÈMES (autres jours)
# ===============================
THEME_QUERIES = [
    "actualité financière", "dette", "IA", "Agent IA", "trading en france", "investissement", "économie", "stoicisme",
    "business en ligne", "crypto en france", "immobilier", "ingénieur data", "bourse", "libéralisme", "pragmatisme",
    "entrepreneuriat", "dev perso", "patrimoine", "gagnant", "fintech", "néobanque", "vidéo de motivation", "aller à Dubaï",
    "revenus passifs", "indépendance financière", "fiscalité france", "assurance vie", "ETF", "obligations françaises",
    "intelligence artificielle", "automatisation no-code", "growth hacking", "side hustle", "start-up française", "podcast business",
    "blockchain en france", "web3 france", "productivité quotidienne", "habitudes millionnaires", "mindset d'entrepreneur",
    "résilience mentale", "travail au luxembourg", "expatriation suisse", "freelance data", "consultant stratégie",
    "intelligence financière", "revenus en ligne", "cryptomonnaies", "gestion du temps", "succès entrepreneurial"
]

SEARCH_RELEVANCE_LANG = "fr"
SEARCH_REGION_CODE    = "FR"   # commente si trop restrictif
SEARCH_PUBLISHED_AFTER_DAYS = 30  # élargit la moisson
SEARCH_PAGE_LIMIT     = 20       # jusqu’à ~1000 résultats bruts/req
NEED_VIDEOS           = 50       # >= 60s
NEED_SHORTS           = 50       # < 60s

# Sécurité & anti-spam
MAX_COMMENTS_PER_RUN  = 120
SLEEP_MIN, SLEEP_MAX  = 1.2, 3.0   # jitter entre commentaires

# Override pour tester le mode “vendredi”
IS_FRIDAY_OVERRIDE = os.getenv("FORCE_FRIDAY") == "1"

# ===============================
# HELPERS RÉSEAU / API ROBUSTES
# ===============================
def _exec(req, retries=3, delay=1.0):
    """Exécute une requête YouTube avec un léger retry/backoff et gère les 4xx/5xx."""
    for i in range(retries):
        try:
            return req.execute()
        except HttpError as e:
            status = getattr(e, "status_code", None) or getattr(e.resp, "status", None)
            # 4xx souvent définitifs (permissions, not found, etc.)
            if status in (400, 401, 403, 404):
                if i == retries - 1:
                    raise
                time.sleep(delay * (i + 1))
            else:
                # 5xx / transient
                if i == retries - 1:
                    raise
                time.sleep(delay * (i + 1))

def _is_live_or_upcoming(snippet, live_streaming_details):
    # Détection fiable live / upcoming
    if live_streaming_details and any(k in live_streaming_details for k in ("actualStartTime", "scheduledStartTime")):
        return True
    lbc = (snippet or {}).get("liveBroadcastContent")
    return lbc in ("live", "upcoming")

def _is_kids(status):
    return bool((status or {}).get("madeForKids"))

# ===============================
# AUTH
# ===============================
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

# ===============================
# HELPERS API
# ===============================
def iso_to_seconds(iso):
    return int(isodate.parse_duration(iso).total_seconds())

def comment(yt, video_id, text):
    body = {"snippet": {"videoId": video_id, "topLevelComment": {"snippet": {"textOriginal": text}}}}
    return _exec(yt.commentThreads().insert(part="snippet", body=body))

def resolve_uploads_playlist(yt, target: str):
    t = target.strip()
    if t.startswith("@"):
        h = t[1:]
        ch = _exec(yt.channels().list(part="id,snippet,contentDetails", forHandle=h))
        items = ch.get("items", [])
        if not items:
            raise ValueError(f"Handle introuvable: {t}")
        c = items[0]
        upl = c["contentDetails"]["relatedPlaylists"].get("uploads")
        if not upl:
            raise ValueError(f"Pas de playlist 'uploads' pour {t}")
        return upl, c["snippet"]["title"], c["id"]

    sr = _exec(yt.search().list(part="snippet", q=t, type="channel", maxResults=1))
    sitems = sr.get("items", [])
    if not sitems:
        raise ValueError(f"Chaîne introuvable via recherche: {t}")
    channel_id = sitems[0]["snippet"]["channelId"]
    ch = _exec(yt.channels().list(part="id,snippet,contentDetails", id=channel_id))
    items = ch.get("items", [])
    if not items:
        raise ValueError(f"Impossible de charger la chaîne: {t} ({channel_id})")
    c = items[0]
    upl = c["contentDetails"]["relatedPlaylists"].get("uploads")
    if not upl:
        raise ValueError(f"Pas de playlist 'uploads' pour {t}")
    return upl, c["snippet"]["title"], c["id"]

def find_last_video_and_short(yt, uploads_id):
    try:
        items = _exec(yt.playlistItems().list(
            part="contentDetails", playlistId=uploads_id, maxResults=50
        )).get("items", [])
    except HttpError as e:
        print(f"[WARN] Playlist introuvable/privée '{uploads_id}': {e}")
        return None, None

    if not items:
        return None, None

    video_ids = [it["contentDetails"]["videoId"] for it in items]
    details = {}
    for i in range(0, len(video_ids), 50):
        chunk = ",".join(video_ids[i:i+50])
        resp = _exec(yt.videos().list(
            part="contentDetails,snippet,status,liveStreamingDetails",
            id=chunk
        ))
        for it in resp.get("items", []):
            details[it["id"]] = {
                "duration_s": iso_to_seconds(it["contentDetails"]["duration"]),
                "title": it["snippet"]["title"],
                "snippet": it["snippet"],
                "status": it.get("status"),
                "lsd": it.get("liveStreamingDetails"),
            }

    last_video = last_short = None
    for vid in video_ids:
        d = details.get(vid)
        if not d:
            continue
        # Filtrage live/upcoming + madeForKids
        if _is_live_or_upcoming(d["snippet"], d["lsd"]) or _is_kids(d["status"]):
            continue
        if d["duration_s"] >= 60 and last_video is None:
            last_video = (vid, d["title"])
        if d["duration_s"] < 60 and last_short is None:
            last_short = (vid, d["title"])
        if last_video and last_short:
            break
    return last_video, last_short

# NEW: helper pour construire l'URL vidéo complète
def video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"

# ===============================
# RECHERCHE THÈMES – multi-requêtes & 2 passes
# ===============================
def search_theme_collect(yt, query_or_queries, need_videos=50, need_shorts=50):
    import datetime as _dt
    queries = query_or_queries if isinstance(query_or_queries, list) else [query_or_queries]

    def _collect(order_mode, use_published_after=True):
        videos, shorts = [], []
        seen_ids = set()
        published_after_iso = None
        if use_published_after:
            ts = time.time() - SEARCH_PUBLISHED_AFTER_DAYS * 86400
            published_after_iso = _dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")

        for q in queries:
            page_token = None
            page_count = 0
            while page_count < SEARCH_PAGE_LIMIT and (len(videos) < need_videos or len(shorts) < need_shorts):
                params = dict(
                    part="id,snippet", q=q, type="video", maxResults=50,
                    order=order_mode, relevanceLanguage=SEARCH_RELEVANCE_LANG,
                )
                # Optionnel: commente la ligne ci-dessous si trop restrictif
                params["regionCode"] = SEARCH_REGION_CODE
                if published_after_iso:
                    params["publishedAfter"] = published_after_iso
                if page_token:
                    params["pageToken"] = page_token

                res = _exec(yt.search().list(**params))
                items = res.get("items", [])
                ids = [it["id"]["videoId"] for it in items if it["id"]["kind"] == "youtube#video"]
                if not ids:
                    break

                det = _exec(yt.videos().list(
                    part="contentDetails,snippet,status,liveStreamingDetails",
                    id=",".join(ids)
                ))
                for it in det.get("items", []):
                    vid = it["id"]
                    if vid in seen_ids:
                        continue
                    dur = iso_to_seconds(it["contentDetails"]["duration"])
                    title = it["snippet"]["title"]
                    snippet = it["snippet"]
                    status = it.get("status")
                    lsd = it.get("liveStreamingDetails")

                    # Filtrer lives / upcoming / kids
                    if _is_live_or_upcoming(snippet, lsd) or _is_kids(status):
                        continue

                    if dur < 60 and len(shorts) < need_shorts:
                        shorts.append((vid, title)); seen_ids.add(vid)
                    elif dur >= 60 and len(videos) < need_videos:
                        videos.append((vid, title)); seen_ids.add(vid)
                    if len(videos) >= need_videos and len(shorts) >= need_shorts:
                        break

                page_token = res.get("nextPageToken")
                page_count += 1
                if not page_token:
                    break
        return videos, shorts

    # Pass 1 : récents + tri par date
    V1, S1 = _collect(order_mode="date", use_published_after=True)
    if len(V1) >= need_videos and len(S1) >= need_shorts:
        return V1[:need_videos], S1[:need_shorts]

    # Pass 2 : élargi (sans publishedAfter) + tri par pertinence
    V2, S2 = _collect(order_mode="relevance", use_published_after=False)

    # Merge & tronque
    def _merge_take(A, B, n):
        out, seen = [], set()
        for x in A + B:
            if x[0] in seen: continue
            out.append(x); seen.add(x[0])
            if len(out) >= n: break
        return out

    videos = _merge_take(V1, V2, need_videos)
    shorts = _merge_take(S1, S2, need_shorts)
    return videos, shorts

# ===============================
# MAIN
# ===============================
def main():
    yt = auth_youtube()

    # Vendredi ? (respecte TZ du runner si tu l’as fixée, ex: Europe/Paris)
    weekday = time.localtime().tm_wday  # 0=lundi, 4=vendredi
    is_friday = (weekday == 4) or IS_FRIDAY_OVERRIDE

    total_comments = 0
    already_done = set()

    def _sleep():
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

    if is_friday:
        print("Mode: listes de YouTubers (vendredi)")
        vids_needed, shorts_needed = 50, 50

        for target in CHANNEL_TARGETS:
            if (vids_needed <= 0 and shorts_needed <= 0) or total_comments >= MAX_COMMENTS_PER_RUN:
                break
            try:
                uploads_id, channel_title, _ = resolve_uploads_playlist(yt, target)
            except Exception as e:
                print(f"[WARN] Résolution échouée '{target}': {e}")
                continue

            last_video, last_short = find_last_video_and_short(yt, uploads_id)

            if last_video and vids_needed > 0:
                vid, title = last_video
                if vid not in already_done:
                    try:
                        resp = comment(yt, vid, make_comment_for_video())
                        print(f"[OK] Liste: video '{title}' -> {video_url(vid)}  (comment: {resp['id']})")
                        total_comments += 1; vids_needed -= 1; already_done.add(vid)
                        _sleep()
                    except HttpError as e:
                        print(f"[WARN] Echec com video '{title}' ({vid}): {e}")

            if last_short and shorts_needed > 0 and total_comments < MAX_COMMENTS_PER_RUN:
                sid, stitle = last_short
                if sid not in already_done:
                    try:
                        resp = comment(yt, sid, make_comment_for_short())
                        print(f"[OK] Liste: short '{stitle}' -> {video_url(sid)}  (comment: {resp['id']})")
                        total_comments += 1; shorts_needed -= 1; already_done.add(sid)
                        _sleep()
                    except HttpError as e:
                        print(f"[WARN] Echec com short '{stitle}' ({sid}): {e}")

        print(f"Reste (après listes): videos={vids_needed}, shorts={shorts_needed}")

        if (vids_needed > 0 or shorts_needed > 0) and total_comments < MAX_COMMENTS_PER_RUN:
            print("Complément par recherche de thème pour atteindre 50/50.")
            vlist, slist = search_theme_collect(yt, THEME_QUERIES, vids_needed, shorts_needed)

            for vid, title in vlist:
                if total_comments >= MAX_COMMENTS_PER_RUN: break
                if vid in already_done: continue
                try:
                    resp = comment(yt, vid, make_comment_for_video())
                    print(f"[OK] Thème: video '{title}' -> {video_url(vid)}  (comment: {resp['id']})")
                    total_comments += 1; already_done.add(vid)
                    _sleep()
                except HttpError as e:
                    print(f"[WARN] Echec com thème video '{title}' ({vid}): {e}")

            for sid, stitle in slist:
                if total_comments >= MAX_COMMENTS_PER_RUN: break
                if sid in already_done: continue
                try:
                    resp = comment(yt, sid, make_comment_for_short())
                    print(f"[OK] Thème: short '{stitle}' -> {video_url(sid)}  (comment: {resp['id']})")
                    total_comments += 1; already_done.add(sid)
                    _sleep()
                except HttpError as e:
                    print(f"[WARN] Echec com thème short '{stitle}' ({sid}): {e}")

    else:
        print("Mode: recherche par thème (hors vendredi)")
        vlist, slist = search_theme_collect(yt, THEME_QUERIES, NEED_VIDEOS, NEED_SHORTS)

        for vid, title in vlist:
            if total_comments >= MAX_COMMENTS_PER_RUN: break
            try:
                resp = comment(yt, vid, make_comment_for_video())
                print(f"[OK] Thème: video '{title}' -> {video_url(vid)}  (comment: {resp['id']})")
                total_comments += 1
                _sleep()
            except HttpError as e:
                print(f"[WARN] Echec com thème video '{title}' ({vid}): {e}")

        for sid, stitle in slist:
            if total_comments >= MAX_COMMENTS_PER_RUN: break
            try:
                resp = comment(yt, sid, make_comment_for_short())
                print(f"[OK] Thème: short '{stitle}' -> {video_url(sid)}  (comment: {resp['id']})")
                total_comments += 1
                _sleep()
            except HttpError as e:
                print(f"[WARN] Echec com thème short '{stitle}' ({sid}): {e}")

    print(f"\nTotal de commentaires postés : {total_comments}")

# ===============================
# RUN
# ===============================
if __name__ == "__main__":
    main()

