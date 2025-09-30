# Guide complet : Configurer Google Cloud (OAuth) pour YouTube Auto Commenter

Ce guide explique **toutes les étapes** côté **Google Cloud Platform (GCP)** pour que votre script `comment_multi_channels.py` et votre **GitHub Actions** fonctionnent sans publier vos secrets en clair.

---

## 0) Pré-requis rapides
- Un compte Google.
- Un dépôt GitHub contenant :
  - `comment_multi_channels.py`
  - `requirements.txt`
  - `.github/workflows/yt_autocomment.yml` (votre workflow)
- Python 3.11+ en local (pour générer le token la première fois).

---

## 1) Créer un projet GCP
1. Allez sur **console.cloud.google.com**.
2. Barre du haut → Sélecteur de projet → **Nouveau projet**.
3. Donnez un nom (ex. _ytb-auto-comment_), créez.

> Le **nom du projet** n’apparaît pas à l’utilisateur. Il sert à organiser votre config GCP.

---

## 2) Activer l’API YouTube
1. Dans GCP, menu hamburger (☰) → **API et services** → **Bibliothèque**.
2. Recherchez **YouTube Data API v3**.
3. Cliquez dessus → **Activer**.

> Sans cette étape, toute requête YouTube échouera avec un 403 ou 404 API non activée.

---

## 3) Écran de consentement OAuth (Branding)
1. **API et services** → **Écran de consentement OAuth**.
2. **Type d’utilisateur** : _Externe_.
3. **Nom de l’application** : ex. _Test Ytb_ (ou votre nom).
4. **Adresse e‑mail d’assistance** : votre e‑mail.
5. **Domaines autorisés** : laissez vide si vous n’avez pas de site. (Inutile pour Desktop App et en mode Test.)
6. (Facultatif) **Logo** : possible, non obligatoire en mode Test.
7. **Ajouter des utilisateurs test** : ajoutez l’adresse Google qui lancera le script (la vôtre).

**États possibles :**
- **Test** (recommandé au début) : pas de validation Google requise, pas besoin de politique de confidentialité.
- **En production** : nécessite une **validation** si vous demandez des scopes sensibles/restrictifs. **Inutile** pour `youtube.force-ssl` si vous restez en _Test_ et n’excédez pas la limite de testeurs.

> Tant que vous êtes en **Mode Test** et que vous **ajoutez votre compte** comme _Utilisateur test_, vous n’avez pas besoin d’envoyer à la validation.

---

## 4) Créer un identifiant OAuth (Client OAuth)
1. **API et services** → **Identifiants**.
2. **Créer des identifiants** → **ID client OAuth**.
3. **Type d’application** : **Application de bureau** (Desktop App).  
   (Ne pas choisir Web tant que vous n’avez pas de domaine.)
4. Donnez un nom (ex. `Desktop - YouTube Bot`) → **Créer**.
5. Copiez **Client ID** et **Client Secret**.

> C’est **ce couple** qui sera injecté dans GitHub via **Secrets** (`YT_CLIENT_ID`/`YT_CLIENT_SECRET`).

---

## 5) Scopes requis (automatique lors du consentement)
Le script utilise :
- `https://www.googleapis.com/auth/youtube.force-ssl`

Vous **n’avez pas besoin** d’ajouter manuellement le scope dans la page “Accès aux données” : la **fenêtre de consentement** l’affichera au premier login OAuth et enregistrera le consentement.

---

## 6) Générer le token localement (une seule fois)
Vous devez créer **`token_comment.json`** UNE FOIS en local (sur votre machine).

Deux méthodes :

### Méthode A — Utiliser votre script tel quel
- Assurez-vous que `YT_CLIENT_ID` et `YT_CLIENT_SECRET` sont définis dans votre environnement **local** ou remplacez temporairement le code pour mettre vos ID/Secret en clair (localement **uniquement**).
- Exécutez :
  ```bash
  python comment_multi_channels.py
  ```
- Un navigateur s’ouvre → **Connexion** avec votre compte Google → **Valider** les scopes → vous revenez au script.
- Un fichier **`token_comment.json`** est créé dans le dossier.

### Méthode B — Mini script dédié
```python
from google_auth_oauthlib.flow import InstalledAppFlow
import json

CLIENT_ID = "xxx.apps.googleusercontent.com"
CLIENT_SECRET = "yyy"
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

flow = InstalledAppFlow.from_client_config(
    {"installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost:8080/"]
    }},
    SCOPES
)
creds = flow.run_local_server(port=8080, access_type="offline", prompt="consent")
open("token_comment.json", "w", encoding="utf-8").write(creds.to_json())
print("OK -> token_comment.json écrit")
```

> **Important** : Vérifiez que le JSON contient **`refresh_token`**. S’il manque, relancez en ajoutant `prompt="consent"` ET en supprimant d’éventuels anciens consentements pour l’app.

---

## 7) Injecter les secrets côté GitHub
Dans votre dépôt GitHub : **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Créez **3 secrets** :

- `YT_CLIENT_ID` → valeur = votre Client ID (ex. `2207...apps.googleusercontent.com`)
- `YT_CLIENT_SECRET` → valeur = votre Client Secret
- `YT_TOKEN_JSON` → **contenu complet** du fichier **`token_comment.json`** (copier/coller le JSON)

> ⚠️ **Ne commitez JAMAIS** ces valeurs dans le repo.

---

## 8) Vérifier votre workflow GitHub Actions
Exemple minimal (adapté à votre projet) :

```yaml
name: YouTube Auto Commenter

on:
  schedule:
    # Tous les jours à 17:00 Europe/Paris (16:00 UTC en hiver / 15:00 UTC en été)
    - cron: "0 15 * * *"
  workflow_dispatch: {}

jobs:
  run:
    runs-on: ubuntu-latest
    env:
      TZ: Europe/Paris
      YT_CLIENT_ID: ${{ secrets.YT_CLIENT_ID }}
      YT_CLIENT_SECRET: ${{ secrets.YT_CLIENT_SECRET }}
      YT_TOKEN_JSON: ${{ secrets.YT_TOKEN_JSON }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Restore token_comment.json from secret
        run: |
          echo "$YT_TOKEN_JSON" > token_comment.json
          python - << 'PY'
import json, sys
try:
    d = json.load(open("token_comment.json", encoding="utf-8"))
    assert "refresh_token" in d, "refresh_token manquant"
    print("token_comment.json OK")
except Exception as e:
    print("token_comment.json invalide:", e); sys.exit(1)
PY

      - name: Run script
        run: python comment_multi_channels.py
```

**Remarques :**
- Le `cron` est **en UTC**. Ajustez selon l’heure souhaitée pour **Europe/Paris**.
- `TZ` définit les logs/time.localtime() pour la logique vendredi vs thème.

---

## 9) Tester et dépanner
- **Manuel** : Onglet **Actions** → Workflows → **Run workflow** (bouton vert).
- **Logs** : lisez les sorties du job (OK/WARN + IDs de commentaires).

**Erreurs fréquentes :**
- `invalid_grant` : token expiré/corrompu → régénérez `token_comment.json` localement.
- `insufficientPermissions` : mauvais scope ou app/test user non autorisé → vérifiez l’écran de consentement (ajouter votre e-mail comme **Test user**), reconsentez.
- `commentsDisabled` : la vidéo n’accepte pas les commentaires → normal, skip.
- `quotaExceeded` / `rateLimitExceeded` : ralentissez (baissez `NEED_VIDEOS/NEED_SHORTS`), ajoutez des `sleep` plus longs.
- `forbidden` (403) : chaîne bloquée, vidéo privée, etc. → skip automatique.

---

## 10) Conseils de bonnes pratiques
- **Sécurité** : uniquement via **Secrets** GitHub. Jamais en clair dans le code public.
- **Mode Test** recommandé : pas de validation Google, moins de friction.
- **Ratios “naturels”** : limitez le nombre de commentaires / jour, variez les messages (déjà fait dans le script).
- **Rotation** : si vous changez d’ID/Secret, régénérez `token_comment.json`.
- **Limites** : la logique commente **50 vidéos + 50 shorts** hors vendredi par thème, et **vendredi** via liste **puis** thème (complément). Ajustez si nécessaire.

---

## 11) Mise à jour / Publication (facultatif)
- Pour publier l’app (hors mode Test) : il faudra renseigner **site web**, **politique de confidentialité**, et **envoyer en validation** (long, inutile dans votre cas).
- Tant que vous restez **en Test** avec **Utilisateurs test**, c’est suffisant pour un usage perso/équipe.

---

## 12) Structure du repo conseillée
```
.
├─ comment_multi_channels.py
├─ requirements.txt
└─ .github/
   └─ workflows/
      └─ yt_autocomment.yml
```

---

**Ça y est.** Côté Google Cloud, vous avez tout ce qu’il faut pour que l’auth OAuth fonctionne et que votre workflow GitHub commente automatiquement selon votre logique (thème/vendredi + ratios anti-spam). Bonne automatisation !
