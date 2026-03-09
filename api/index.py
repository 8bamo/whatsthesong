from html import escape
from urllib.parse import quote_plus, urlparse
from difflib import SequenceMatcher
import re
import subprocess
import tempfile
from pathlib import Path

import requests
import yt_dlp
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

app = FastAPI()

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (whatsthesong vercel app)"}
SUPPORTED_VIDEO_HOST_HINTS = ("tiktok.com", "instagram.com", "instagr.am")
GENERIC_TRACK_HINTS = {
    "original",
    "original sound",
    "som original",
    "son original",
    "suono originale",
    "video by",
}

LANG_OPTIONS = {
    "de": "\U0001F1E9\U0001F1EA Deutsch",
    "en": "\U0001F1EC\U0001F1E7 English",
    "fr": "\U0001F1EB\U0001F1F7 Francais",
    "es": "\U0001F1EA\U0001F1F8 Espanol",
    "it": "\U0001F1EE\U0001F1F9 Italiano",
}

I18N = {
    "de": {
        "hero_sub": "TikTok/Instagram-Link rein, Song erkennen, Streaming-Links raus.",
        "url_label": "TikTok/Instagram URL",
        "url_placeholder": "https://www.tiktok.com/@user/video/... oder https://www.instagram.com/reel/...",
        "submit": "Suche starten",
        "err_read": "Fehler beim Auslesen des Links: {err}",
        "err_invalid_url": "Bitte einen TikTok- oder Instagram-Link einfuegen.",
        "detected_source": "Erkennungsquelle: {source}",
        "source_metadata": "Metadaten",
        "source_audio": "Audio-Match",
        "badge_queries": "Suchbegriffe: {count}",
        "badge_region": "Region: DE",
        "expand_queries": "Verwendete Suchbegriffe",
        "err_no_links": "Keine Streaming-Links gefunden.",
        "tip_no_links": "Instagram liefert oft keine Song-Metadaten. Dann kann kein sicherer Match entstehen.",
        "caption_match_query": "Treffer ueber Suchbegriff: {query}",
        "unknown": "Unbekannt",
    },
    "en": {
        "hero_sub": "Paste TikTok/Instagram link, detect song, get streaming links.",
        "url_label": "TikTok/Instagram URL",
        "url_placeholder": "https://www.tiktok.com/@user/video/... or https://www.instagram.com/reel/...",
        "submit": "Start search",
        "err_read": "Error reading link: {err}",
        "err_invalid_url": "Please enter a TikTok or Instagram URL.",
        "detected_source": "Detection source: {source}",
        "source_metadata": "Metadata",
        "source_audio": "Audio match",
        "badge_queries": "Queries: {count}",
        "badge_region": "Region: DE",
        "expand_queries": "Used search terms",
        "err_no_links": "No streaming links found.",
        "tip_no_links": "Instagram often has no song metadata. Then no reliable match is possible.",
        "caption_match_query": "Matched via query: {query}",
        "unknown": "Unknown",
    },
    "fr": {
        "hero_sub": "Colle un lien TikTok/Instagram, detecte la musique, recupere les liens.",
        "url_label": "URL TikTok/Instagram",
        "url_placeholder": "https://www.tiktok.com/@user/video/... ou https://www.instagram.com/reel/...",
        "submit": "Lancer la recherche",
        "err_read": "Erreur de lecture du lien : {err}",
        "err_invalid_url": "Saisis un lien TikTok ou Instagram.",
        "detected_source": "Source de detection : {source}",
        "source_metadata": "Metadonnees",
        "source_audio": "Correspondance audio",
        "badge_queries": "Requetes : {count}",
        "badge_region": "Region : DE",
        "expand_queries": "Termes utilises",
        "err_no_links": "Aucun lien trouve.",
        "tip_no_links": "Instagram n'a souvent pas de metadonnees musicales fiables.",
        "caption_match_query": "Trouve via : {query}",
        "unknown": "Inconnu",
    },
    "es": {
        "hero_sub": "Pega un enlace de TikTok/Instagram, detecta la cancion y obten enlaces.",
        "url_label": "URL TikTok/Instagram",
        "url_placeholder": "https://www.tiktok.com/@user/video/... o https://www.instagram.com/reel/...",
        "submit": "Iniciar busqueda",
        "err_read": "Error al leer el enlace: {err}",
        "err_invalid_url": "Ingresa un enlace de TikTok o Instagram.",
        "detected_source": "Fuente de deteccion: {source}",
        "source_metadata": "Metadatos",
        "source_audio": "Coincidencia de audio",
        "badge_queries": "Busquedas: {count}",
        "badge_region": "Region: DE",
        "expand_queries": "Terminos usados",
        "err_no_links": "No se encontraron enlaces.",
        "tip_no_links": "Instagram muchas veces no tiene metadatos de cancion.",
        "caption_match_query": "Coincidencia por: {query}",
        "unknown": "Desconocido",
    },
    "it": {
        "hero_sub": "Incolla il link TikTok/Instagram, rileva la canzone, ottieni i link.",
        "url_label": "URL TikTok/Instagram",
        "url_placeholder": "https://www.tiktok.com/@user/video/... oppure https://www.instagram.com/reel/...",
        "submit": "Avvia ricerca",
        "err_read": "Errore nella lettura del link: {err}",
        "err_invalid_url": "Inserisci un link TikTok o Instagram.",
        "detected_source": "Fonte rilevamento: {source}",
        "source_metadata": "Metadati",
        "source_audio": "Corrispondenza audio",
        "badge_queries": "Query: {count}",
        "badge_region": "Regione: DE",
        "expand_queries": "Termini usati",
        "err_no_links": "Nessun link trovato.",
        "tip_no_links": "Instagram spesso non fornisce metadati audio affidabili.",
        "caption_match_query": "Trovato con: {query}",
        "unknown": "Sconosciuto",
    },
}


def tr(lang: str, key: str, **kwargs) -> str:
    template = I18N.get(lang, I18N["en"]).get(key, key)
    return template.format(**kwargs) if kwargs else template


def is_supported_video_url(url: str) -> bool:
    try:
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        return False
    return any(h in host for h in SUPPORTED_VIDEO_HOST_HINTS)


def is_generic_track(text: str | None) -> bool:
    if not text:
        return True
    t = text.strip().lower()
    return any(h in t for h in GENERIC_TRACK_HINTS)


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


def recognize_song_from_audio(url: str):
    try:
        import asyncio
        import imageio_ffmpeg
        from shazamio import Shazam
    except Exception:
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        in_template = str(tmp / "fp_input.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": in_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                in_file = Path(ydl.prepare_filename(info))
        except Exception:
            return None

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        duration = float(info.get("duration") or 30)
        starts = [s for s in [0, 4, 8, 12, 16, 20] if s < max(duration - 3, 0)]

        async def recognize(path: str):
            shazam = Shazam()
            return await shazam.recognize(path)

        for start in starts:
            seg_file = tmp / f"seg_{start}.wav"
            cmd = [ffmpeg, "-y", "-ss", str(start), "-t", "12", "-i", str(in_file), "-ac", "1", "-ar", "44100", str(seg_file)]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0 or not seg_file.exists() or seg_file.stat().st_size < 50000:
                continue
            try:
                result = asyncio.run(recognize(str(seg_file)))
            except Exception:
                continue
            track = result.get("track", {}) if isinstance(result, dict) else {}
            title = track.get("title")
            artist = track.get("subtitle")
            if title and artist:
                return {"title": title, "artist": artist}
    return None


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

    queries: list[str] = []
    if track and artist and not is_generic_track(track):
        queries += [f"{track} {artist}", track, artist]

    title_q = clean_query(title)
    if title_q and not title_q.lower().startswith("video by"):
        queries.append(title_q)

    desc_q = clean_query(description)
    if desc_q and len(desc_q.split()) <= 6:
        queries.append(desc_q)

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
        response = requests.get(
            f"https://itunes.apple.com/search?term={quote_plus(query)}&entity=song&limit=6",
            headers=REQUEST_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        out = []
        for item in data.get("results", []):
            url = item.get("trackViewUrl")
            if not url:
                continue
            out.append({"url": url, "title": item.get("trackName") or "", "artist": item.get("artistName") or ""})
        return out
    except requests.RequestException:
        return []


def find_deezer_candidates(query: str) -> list[dict]:
    try:
        response = requests.get(
            f"https://api.deezer.com/search?q={quote_plus(query)}&limit=6",
            headers=REQUEST_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        out = []
        for item in data.get("data", []):
            url = item.get("link")
            if not url:
                continue
            artist_obj = item.get("artist") or {}
            out.append({"url": url, "title": item.get("title") or "", "artist": artist_obj.get("name") or ""})
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
            timeout=15,
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
    min_score = 1.45 if (expected_track and expected_artist) else 1.10
    top = [c for c in candidates if c[0] >= min_score][:10]
    if not top:
        return None, None

    for _score, q, url in top:
        links = get_odesli_links_from_url(url)
        if links:
            return links, q
    return None, None


def render_platform_buttons(links: dict) -> str:
    platform_map = [
        ("spotify", "Spotify", False, "&#9835;"),
        ("appleMusic", "Apple Music", False, "&#127822;"),
        ("youtube", "YouTube", False, "&#9654;"),
        ("deezer", "Deezer", True, "&#9679;"),
        ("soundcloud", "SoundCloud", True, "&#9729;"),
    ]
    buttons = []
    for key, label, alt, icon in platform_map:
        purl = links.get(key, {}).get("url")
        if purl:
            buttons.append(
                f'<a class="platform-btn{" alt" if alt else ""}" href="{escape(purl)}" target="_blank" rel="noopener noreferrer">'
                f'<span class="platform-icon">{icon}</span><span>{label}</span></a>'
            )
    return f'<div class="platform-grid">{"".join(buttons)}</div>' if buttons else ""


def page(lang: str, url: str = "", error: str = "", detected_text: str = "", detection_label: str = "", query_count: int = 0, queries: list[str] | None = None, links: dict | None = None, matched_query: str = "", thumbnail_url: str = "", tip: str = ""):
    queries = queries or []
    links = links or {}
    language_options = "".join(f'<option value="{code}"{" selected" if code == lang else ""}>{label}</option>' for code, label in LANG_OPTIONS.items())

    result_block = ""
    if detected_text:
        query_items = "".join(f"<li>{escape(q)}</li>" for q in queries)
        query_section = f'<details class="query-box"><summary>{escape(tr(lang, "expand_queries"))}</summary><ul>{query_items}</ul></details>' if queries else ""
        matched = f'<p class="caption">{escape(tr(lang, "caption_match_query", query=matched_query))}</p>' if matched_query else ""
        thumbs = f'<img class="cover" src="{escape(thumbnail_url)}" alt="cover" />' if thumbnail_url else ""

        result_block = f"""
        <div class="result-card">
            <p class="result-title">{escape(detected_text)}</p>
            <p class="result-sub">{escape(tr(lang, "detected_source", source=detection_label))}</p>
            <div class="badge-row">
                <span class="badge">{escape(tr(lang, "badge_queries", count=query_count))}</span>
                <span class="badge">{escape(tr(lang, "badge_region"))}</span>
            </div>
        </div>
        {query_section}
        {matched}
        {render_platform_buttons(links)}
        {thumbs}
        """

    err_html = f'<p class="err">{escape(error)}</p>' if error else ""
    tip_html = f'<p class="tip">{escape(tip)}</p>' if tip else ""

    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>whatsthesong</title>
      <style>
      body {{ margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; background: radial-gradient(700px 300px at 10% -10%, rgba(34,197,94,0.16), transparent 70%), radial-gradient(850px 400px at 100% 0%, rgba(6,182,212,0.18), transparent 65%), #060b16; color: #e6edf7; }}
      .wrap {{ max-width: 980px; margin: 0 auto; padding: 10px 16px 40px; }}
      .hero {{ border: 1px solid #25324d; border-radius: 18px; padding: 1.2rem; background: linear-gradient(130deg,#101828,#12325c); margin-bottom: .9rem; }}
      .brand-logo-wrap {{ display:flex; justify-content:flex-start; }}
      .brand-logo {{ width:min(420px,100%); height:auto; display:block; }}
      .hero p {{ margin:.55rem 0 0 0; color:#c5d8f7; }}
      .panel {{ margin-top:1rem; border: 1px solid #2b3a57; border-radius: 12px; padding: 14px; background:#0f172a; }}
      .select-wrap {{ margin-bottom: .7rem; }}
      select, input {{ width: 100%; box-sizing: border-box; border:1px solid #334260; border-radius:10px; background:#0e162a; color:#e6edf7; padding: 11px; }}
      label {{ display:block; margin: 0 0 6px 0; color:#c2d3ee; font-weight:700; }}
      button {{ margin-top: 10px; width: 100%; border: 0; border-radius: 10px; padding: 11px; font-weight: 800; color: #06101f; background: linear-gradient(135deg,#34d399,#22c55e); cursor: pointer; }}
      .result-card {{ margin-top:1.25rem; border:1px solid #25324d; border-radius:14px; background:#0f172a; padding:1rem; }}
      .result-title {{ margin:0; color:#f5f9ff; font-size:clamp(1.1rem,2vw,1.4rem); font-weight:700; }}
      .result-sub {{ margin:.35rem 0 0 0; color:#9db0cf; font-size:.92rem; }}
      .badge-row {{ display:flex; gap:.45rem; flex-wrap:wrap; margin-top:.7rem; }}
      .badge {{ border-radius:999px; padding:.26rem .62rem; color:#d7fbe7; background:rgba(34,197,94,.14); border:1px solid rgba(34,197,94,.45); font-size:.78rem; font-weight:700; }}
      .query-box {{ margin-top: .8rem; border:1px solid #25324d; border-radius: 10px; padding: .55rem .7rem; background:#0f172a; }}
      .query-box summary {{ cursor:pointer; color:#c2d3ee; font-weight:700; }}
      .query-box ul {{ margin: .5rem 0 0 1rem; padding: 0; color:#9db0cf; }}
      .platform-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.65rem; margin-top:1.25rem; margin-bottom:.85rem; }}
      .platform-btn {{ text-decoration:none; min-height:44px; display:inline-flex; align-items:center; justify-content:center; gap:.45rem; border-radius:10px; color:#06101f !important; font-weight:700; background:linear-gradient(135deg,#34d399,#22c55e); border:1px solid rgba(0,0,0,.16); }}
      .platform-btn.alt {{ color:#dbe7fb !important; background:linear-gradient(135deg,#1e293b,#27344d); border:1px solid #3c4d6f; }}
      .platform-icon {{ width:18px; height:18px; display:inline-block; text-align:center; line-height:18px; }}
      .caption {{ color:#9db0cf; margin: .55rem 0 0 0; }}
      .cover {{ width: 320px; max-width: 100%; border-radius: 8px; border:1px solid #2b3a57; }}
      .err {{ margin-top:10px; color:#ffb3b3; }}
      .tip {{ margin-top:8px; color:#9db0cf; }}
      .footer {{ margin-top: 18px; color:#7f94b6; font-size:.86rem; text-align:center; }}
      @media (max-width:860px){{ .platform-grid{{grid-template-columns:repeat(2,minmax(0,1fr));}} }}
      @media (max-width:640px){{ .wrap{{padding-left:.85rem;padding-right:.85rem;}} .platform-grid{{grid-template-columns:1fr;}} }}
      </style>
    </head>
    <body>
      <main class="wrap">
        <form method="post" action="/">
          <div class="select-wrap">
            <select name="lang" aria-label="language" onchange="window.location='/?lang='+this.value">{language_options}</select>
          </div>
          <div class="hero">
            <div class="brand-logo-wrap">
              <svg class="brand-logo" viewBox="0 0 980 280" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="whatsthesong logo">
                <defs>
                  <linearGradient id="logoGradA" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#19b7ff"/><stop offset="100%" stop-color="#2af598"/></linearGradient>
                  <linearGradient id="logoGradB" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#27d0ff"/><stop offset="100%" stop-color="#8df570"/></linearGradient>
                </defs>
                <g transform="translate(20,10)">
                  <circle cx="130" cy="110" r="92" fill="none" stroke="url(#logoGradA)" stroke-width="14"/>
                  <path d="M30 106 C 85 120, 100 50, 145 96 C 178 130, 198 68, 240 104" fill="none" stroke="url(#logoGradB)" stroke-width="16" stroke-linecap="round"/>
                  <path d="M58 136 C 102 152, 125 92, 168 128 C 194 150, 216 110, 248 132" fill="none" stroke="#1dc7ff" stroke-opacity="0.55" stroke-width="10" stroke-linecap="round"/>
                  <path d="M190 72 Q 228 52 242 78" fill="none" stroke="#2af598" stroke-width="10" stroke-linecap="round"/>
                  <line x1="236" y1="48" x2="236" y2="90" stroke="url(#logoGradA)" stroke-width="10" stroke-linecap="round"/>
                  <circle cx="236" cy="96" r="14" fill="url(#logoGradA)"/>
                  <line x1="178" y1="170" x2="220" y2="214" stroke="url(#logoGradA)" stroke-width="16" stroke-linecap="round"/>
                </g>
                <text x="300" y="205" fill="#f6fbff" font-size="106" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-weight="700" letter-spacing="0.2">whatsthesong</text>
              </svg>
            </div>
            <p>{escape(tr(lang, "hero_sub"))}</p>
          </div>
          <div class="panel">
            <label>{escape(tr(lang, "url_label"))}</label>
            <input name="url" value="{escape(url)}" placeholder="{escape(tr(lang, "url_placeholder"))}" />
            <button type="submit">{escape(tr(lang, "submit"))}</button>
            {err_html}
            {tip_html}
          </div>
        </form>

        {result_block}

        <div class="footer">copyright bamo.ai 2026</div>
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

    if not url:
        return HTMLResponse(page(lang=lang, url=url))

    if not is_supported_video_url(url):
        return HTMLResponse(page(lang=lang, url=url, error=tr(lang, "err_invalid_url")))

    try:
        audio_info = get_video_audio_info(url)
    except Exception as exc:
        return HTMLResponse(page(lang=lang, url=url, error=tr(lang, "err_read", err=exc)))

    detection_label = tr(lang, "source_metadata")
    track = audio_info.get("track")
    artist = audio_info.get("artist")
    title = audio_info.get("title")

    if not track or not artist or is_generic_track(track):
        audio_match = recognize_song_from_audio(url)
        if audio_match:
            track = audio_match["title"]
            artist = audio_match["artist"]
            detection_label = tr(lang, "source_audio")

    queries = build_search_queries({**audio_info, "track": track, "artist": artist})

    if track and artist and not is_generic_track(track):
        strong = [f"{track} {artist}", track, artist]
        dedup, seen = [], set()
        for q in strong + queries:
            n = q.lower().strip()
            if n and n not in seen:
                dedup.append(q)
                seen.add(n)
        queries = dedup
        detected_text = f"{track} - {artist}"
    else:
        detected_text = title or tr(lang, "unknown")

    links_data, matched_query = get_streaming_links(queries, expected_track=track or "", expected_artist=artist or "")
    if not links_data:
        return HTMLResponse(
            page(
                lang=lang,
                url=url,
                detected_text=detected_text,
                detection_label=detection_label,
                query_count=len(queries),
                queries=queries,
                error=tr(lang, "err_no_links"),
                tip=tr(lang, "tip_no_links"),
            )
        )

    links = links_data.get("linksByPlatform", {})
    entities = links_data.get("entitiesByUniqueId", {})
    thumbnail_url = ""
    if entities:
        first_key = next(iter(entities))
        thumbnail_url = entities[first_key].get("thumbnailUrl") or ""

    return HTMLResponse(
        page(
            lang=lang,
            url=url,
            detected_text=detected_text,
            detection_label=detection_label,
            query_count=len(queries),
            queries=queries,
            links=links,
            matched_query=matched_query or "",
            thumbnail_url=thumbnail_url,
        )
    )