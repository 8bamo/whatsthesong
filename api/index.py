from html import escape
from urllib.parse import quote_plus, urlparse
from difflib import SequenceMatcher
import re

import requests
import yt_dlp
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

app = FastAPI()

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (whatsthesong vercel app)"}
GENERIC_TIKTOK_TRACK_HINTS = {
    "original",
    "original sound",
    "som original",
    "son original",
    "suono originale",
}
SUPPORTED_VIDEO_HOST_HINTS = ("tiktok.com", "instagram.com", "instagr.am")

LANG_OPTIONS = {
    "de": "\U0001F1E9\U0001F1EA Deutsch",
    "en": "\U0001F1EC\U0001F1E7 English",
    "fr": "\U0001F1EB\U0001F1F7 Francais",
    "es": "\U0001F1EA\U0001F1F8 Espanol",
    "it": "\U0001F1EE\U0001F1F9 Italiano",
}

I18N = {
    "de": {
        "title": "whatsthesong",
        "subtitle": "TikTok/Instagram-Link rein, Song erkennen, Streaming-Links raus.",
        "url": "TikTok/Instagram URL",
        "submit": "Song finden",
        "invalid_url": "Bitte einen TikTok- oder Instagram-Link eingeben.",
        "detected": "Erkannt",
        "source": "Quelle",
        "source_meta": "Metadaten",
        "no_links": "Keine Streaming-Links gefunden.",
    },
    "en": {
        "title": "whatsthesong",
        "subtitle": "Paste TikTok/Instagram link, detect song, get streaming links.",
        "url": "TikTok/Instagram URL",
        "submit": "Find song",
        "invalid_url": "Please enter a TikTok or Instagram URL.",
        "detected": "Detected",
        "source": "Source",
        "source_meta": "Metadata",
        "no_links": "No streaming links found.",
    },
    "fr": {
        "title": "whatsthesong",
        "subtitle": "Colle un lien TikTok/Instagram, detecte la musique, recupere les liens streaming.",
        "url": "URL TikTok/Instagram",
        "submit": "Trouver la chanson",
        "invalid_url": "Saisis un lien TikTok ou Instagram.",
        "detected": "Detecte",
        "source": "Source",
        "source_meta": "Metadonnees",
        "no_links": "Aucun lien streaming trouve.",
    },
    "es": {
        "title": "whatsthesong",
        "subtitle": "Pega un enlace de TikTok/Instagram, detecta la cancion y obten enlaces.",
        "url": "URL TikTok/Instagram",
        "submit": "Buscar cancion",
        "invalid_url": "Ingresa un enlace de TikTok o Instagram.",
        "detected": "Detectado",
        "source": "Fuente",
        "source_meta": "Metadatos",
        "no_links": "No se encontraron enlaces.",
    },
    "it": {
        "title": "whatsthesong",
        "subtitle": "Incolla il link TikTok/Instagram, rileva la canzone, ottieni i link.",
        "url": "URL TikTok/Instagram",
        "submit": "Trova canzone",
        "invalid_url": "Inserisci un link TikTok o Instagram.",
        "detected": "Rilevato",
        "source": "Fonte",
        "source_meta": "Metadati",
        "no_links": "Nessun link trovato.",
    },
}


def tr(lang: str, key: str) -> str:
    return I18N.get(lang, I18N["en"]).get(key, key)


def is_supported_video_url(url: str) -> bool:
    try:
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        return False
    return any(h in host for h in SUPPORTED_VIDEO_HOST_HINTS)


def is_generic_tiktok_track(track_name: str | None) -> bool:
    if not track_name:
        return True
    lower_track = track_name.strip().lower()
    return any(hint in lower_track for hint in GENERIC_TIKTOK_TRACK_HINTS)


def get_video_audio_info(url: str):
    ydl_opts = {"format": "bestaudio/best", "noplaylist": True, "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "track": info.get("track"),
            "artist": info.get("artist"),
            "title": info.get("title"),
            "description": info.get("description") or "",
            "artists": info.get("artists") or [],
        }


def clean_query(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"#[^\s]+", " ", text)
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_search_queries(audio_info: dict) -> list[str]:
    track = audio_info.get("track")
    artist = audio_info.get("artist")
    title = audio_info.get("title")
    description = audio_info.get("description")
    artists = audio_info.get("artists") or []

    queries: list[str] = []
    if track and artist and not is_generic_tiktok_track(track):
        queries += [f"{track} {artist}", track, artist]
    elif track and not is_generic_tiktok_track(track):
        queries.append(track)
    elif artist:
        queries.append(artist)

    queries += [str(a) for a in artists[:2] if a]

    clean_title = clean_query(title)
    clean_desc = clean_query(description)
    if clean_title and not clean_title.lower().startswith("video by"):
        queries.append(clean_title)
    if clean_desc and len(clean_desc.split()) <= 5:
        queries.append(clean_desc)

    out, seen = [], set()
    for q in queries:
        n = q.lower().strip()
        if n and n not in seen and len(n) >= 3:
            out.append(q)
            seen.add(n)
    return out[:8]


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str | None, b: str | None) -> float:
    na = normalize_text(a)
    nb = normalize_text(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def score_candidate(candidate: dict, query: str, expected_track: str = "", expected_artist: str = "") -> float:
    title = candidate.get("title") or ""
    artist = candidate.get("artist") or ""

    score = 0.0
    score += similarity(f"{title} {artist}", query) * 1.2

    if expected_track:
        score += similarity(title, expected_track) * 2.2
    if expected_artist:
        score += similarity(artist, expected_artist) * 1.8

    qn = normalize_text(query)
    tn = normalize_text(title)
    an = normalize_text(artist)
    if qn and (qn in tn or qn in an or qn in f"{tn} {an}"):
        score += 0.25

    return score


def find_itunes_candidates(query: str) -> list[dict]:
    try:
        res = requests.get(
            f"https://itunes.apple.com/search?term={quote_plus(query)}&entity=song&limit=6",
            headers=REQUEST_HEADERS,
            timeout=12,
        )
        res.raise_for_status()
        data = res.json()

        out = []
        for r in data.get("results", []):
            url = r.get("trackViewUrl")
            if not url:
                continue
            out.append(
                {
                    "url": url,
                    "title": r.get("trackName") or "",
                    "artist": r.get("artistName") or "",
                }
            )
        return out
    except requests.RequestException:
        return []


def find_deezer_candidates(query: str) -> list[dict]:
    try:
        res = requests.get(
            f"https://api.deezer.com/search?q={quote_plus(query)}&limit=6",
            headers=REQUEST_HEADERS,
            timeout=12,
        )
        res.raise_for_status()
        data = res.json()

        out = []
        for r in data.get("data", []):
            url = r.get("link")
            if not url:
                continue
            artist_obj = r.get("artist") or {}
            out.append(
                {
                    "url": url,
                    "title": r.get("title") or "",
                    "artist": artist_obj.get("name") or "",
                }
            )
        return out
    except requests.RequestException:
        return []


def get_odesli_links_from_url(track_url: str):
    if not track_url:
        return None
    try:
        res = requests.get(
            "https://api.song.link/v1-alpha.1/links",
            params={"url": track_url, "userCountry": "DE"},
            headers=REQUEST_HEADERS,
            timeout=12,
        )
        res.raise_for_status()
        data = res.json()
        return data if data.get("linksByPlatform") else None
    except requests.RequestException:
        return None


def get_streaming_links(queries: list[str], expected_track: str = "", expected_artist: str = ""):
    candidates = []
    for q in queries:
        for cand in find_itunes_candidates(q):
            candidates.append((score_candidate(cand, q, expected_track, expected_artist), q, cand["url"]))
        for cand in find_deezer_candidates(q):
            candidates.append((score_candidate(cand, q, expected_track, expected_artist), q, cand["url"]))

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: x[0], reverse=True)

    if expected_track and expected_artist:
        min_score = 1.45
    elif expected_track or expected_artist:
        min_score = 1.10
    else:
        min_score = 1.80

    top = [c for c in candidates if c[0] >= min_score][:10]
    if not top:
        return None, None

    for _score, query, url in top:
        links = get_odesli_links_from_url(url)
        if links:
            return links, query
    return None, None


def page(lang: str, selected_url: str = "", error: str = "", detected: str = "", source: str = "", links: dict | None = None, matched_query: str = ""):
    links = links or {}
    language_options = "".join(
        f'<option value="{code}"{" selected" if code == lang else ""}>{label}</option>'
        for code, label in LANG_OPTIONS.items()
    )

    buttons = []
    for key, label, alt in [
        ("spotify", "Spotify", False),
        ("appleMusic", "Apple Music", False),
        ("youtube", "YouTube", False),
        ("deezer", "Deezer", True),
        ("soundcloud", "SoundCloud", True),
    ]:
        url = links.get(key, {}).get("url")
        if url:
            cls = "btn alt" if alt else "btn"
            buttons.append(f'<a class="{cls}" target="_blank" rel="noopener" href="{escape(url)}">{label}</a>')

    result_block = ""
    if detected:
        result_block = f"""
        <section class="result">
          <div class="k">{escape(tr(lang, "detected"))}</div>
          <h2>{escape(detected)}</h2>
          <div class="meta">{escape(tr(lang, "source"))}: {escape(source)}</div>
          {f'<div class="meta">query: {escape(matched_query)}</div>' if matched_query else ''}
          <div class="grid">{''.join(buttons) if buttons else f'<p class="meta">{escape(tr(lang, "no_links"))}</p>'}</div>
        </section>
        """

    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>{escape(tr(lang, "title"))}</title>
      <style>
      body {{
        margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
        background: radial-gradient(800px 400px at 10% -10%, #15335f 0%, transparent 60%), #070b14;
        color: #e6edf7;
      }}
      .wrap {{ max-width: 860px; margin: 0 auto; padding: 24px 16px 40px; }}
      .hero {{ border: 1px solid #2b3a57; border-radius: 16px; padding: 18px; background: linear-gradient(140deg, #0d1423, #102846); }}
      h1 {{ margin: 0; font-size: clamp(30px, 5vw, 44px); }}
      .sub {{ color: #adc3e7; margin-top: 8px; }}
      .panel {{ margin-top: 14px; padding: 14px; border: 1px solid #2b3a57; border-radius: 12px; background: #0f172a; }}
      label {{ display:block; font-weight:700; margin-bottom:6px; color:#d4e2f8; }}
      input, select {{ width: 100%; box-sizing: border-box; border: 1px solid #3a4c71; border-radius: 10px; background:#101a2f; color:#e6edf7; padding: 11px; }}
      .row {{ display: grid; grid-template-columns: 1fr 2fr; gap: 10px; }}
      button {{ margin-top: 10px; width: 100%; border: 0; border-radius: 10px; padding: 11px; font-weight: 800; color: #062018; background: linear-gradient(135deg, #34d399, #22c55e); cursor: pointer; }}
      .err {{ margin-top: 10px; color:#ffb3b3; }}
      .result {{ margin-top: 14px; padding: 14px; border:1px solid #2b3a57; border-radius: 12px; background: #0f172a; }}
      .k {{ color:#9cb4da; font-size: 13px; }}
      h2 {{ margin: 4px 0 0; font-size: 24px; }}
      .meta {{ color:#9cb4da; margin-top:6px; font-size:14px; }}
      .grid {{ margin-top:10px; display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }}
      .btn {{ text-decoration:none; text-align:center; border-radius:10px; padding:10px; font-weight:800; color:#08151f; background:linear-gradient(135deg,#22d3ee,#06b6d4); }}
      .btn.alt {{ color:#e6edf7; background:#1f2d45; border:1px solid #3a4c71; }}
      @media (max-width: 760px) {{ .row {{ grid-template-columns: 1fr; }} .grid {{ grid-template-columns: 1fr; }} }}
      </style>
    </head>
    <body>
      <main class="wrap">
        <section class="hero">
          <h1>whatsthesong</h1>
          <p class="sub">{escape(tr(lang, "subtitle"))}</p>
        </section>

        <section class="panel">
          <form method="post" action="/">
            <div class="row">
              <div>
                <label>Language</label>
                <select name="lang">{language_options}</select>
              </div>
              <div>
                <label>{escape(tr(lang, "url"))}</label>
                <input name="url" value="{escape(selected_url)}" placeholder="https://www.tiktok.com/@user/video/..." />
              </div>
            </div>
            <button type="submit">{escape(tr(lang, "submit"))}</button>
          </form>
          {f'<p class="err">{escape(error)}</p>' if error else ''}
        </section>

        {result_block}
      </main>
    </body>
    </html>
    """


@app.get("/", response_class=HTMLResponse)
def index_get(lang: str = "de"):
    lang = lang if lang in I18N else "en"
    return HTMLResponse(page(lang=lang))


@app.post("/", response_class=HTMLResponse)
def index_post(lang: str = Form("de"), url: str = Form("")):
    lang = lang if lang in I18N else "en"
    url = (url or "").strip()

    if not url or not is_supported_video_url(url):
        return HTMLResponse(page(lang=lang, selected_url=url, error=tr(lang, "invalid_url")))

    try:
        audio_info = get_video_audio_info(url)
        track = audio_info.get("track")
        artist = audio_info.get("artist")
        title = audio_info.get("title")

        queries = build_search_queries(audio_info)
        links_data, matched_query = get_streaming_links(queries, expected_track=track or "", expected_artist=artist or "")

        if track and artist and not is_generic_tiktok_track(track):
            detected_text = f"{track} - {artist}"
        else:
            detected_text = title or "Unknown"

        links = (links_data or {}).get("linksByPlatform", {})
        return HTMLResponse(
            page(
                lang=lang,
                selected_url=url,
                detected=detected_text,
                source=tr(lang, "source_meta"),
                links=links,
                matched_query=matched_query or "",
            )
        )
    except Exception as exc:
        return HTMLResponse(page(lang=lang, selected_url=url, error=str(exc)))