import html
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import requests
import streamlit as st
import yt_dlp

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (whatsthesong local app)"}
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
    "🇩🇪 Deutsch": "de",
    "🇬🇧 English": "en",
    "🇫🇷 Francais": "fr",
    "🇪🇸 Espanol": "es",
    "🇮🇹 Italiano": "it",
}

I18N = {
    "de": {
        "hero_sub": "TikTok/Instagram-Link rein, Song erkennen, Streaming-Links raus.",
        "intro": "Füge einen TikTok- oder Instagram-Link ein.",
        "url_label": "TikTok/Instagram URL",
        "url_placeholder": "https://www.tiktok.com/@user/video/... oder https://www.instagram.com/reel/...",
        "spin_analyze": "Analysiere Video...",
        "spin_links": "Suche Streaming-Links...",
        "err_read": "Fehler beim Auslesen des Links: {err}",
        "err_invalid_url": "Bitte einen TikTok- oder Instagram-Link einfügen.",
        "detected_source": "Erkennungsquelle: {source}",
        "source_metadata": "Metadaten",
        "source_audio": "Audio-Match",
        "badge_queries": "Suchbegriffe: {count}",
        "badge_region": "Region: DE",
        "expand_queries": "Verwendete Suchbegriffe",
        "err_no_links": "Keine Streaming-Links gefunden.",
        "tip_no_links": "Instagram liefert oft keine Song-Metadaten. Dann kann kein sicherer Match entstehen.",
        "caption_match_query": "Treffer über Suchbegriff: {query}",
        "unknown": "Unbekannt",
        "preview_title": "Audio-Preview",
        "preview_caption": "Spiele 10 Sekunden aus dem Video-Audio ab.",
        "preview_start": "Startsekunde",
        "preview_error": "Audio-Preview konnte nicht geladen werden: {err}",
    },
    "en": {
        "hero_sub": "Paste TikTok/Instagram link, detect song, get streaming links.",
        "intro": "Paste a TikTok or Instagram link.",
        "url_label": "TikTok/Instagram URL",
        "url_placeholder": "https://www.tiktok.com/@user/video/... or https://www.instagram.com/reel/...",
        "spin_analyze": "Analyzing video...",
        "spin_links": "Searching streaming links...",
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
        "preview_title": "Audio preview",
        "preview_caption": "Play 10 seconds from the video audio.",
        "preview_start": "Start second",
        "preview_error": "Could not load audio preview: {err}",
    },
    "fr": {
        "hero_sub": "Colle un lien TikTok/Instagram, détecte la musique, récupère les liens.",
        "intro": "Colle un lien TikTok ou Instagram.",
        "url_label": "URL TikTok/Instagram",
        "url_placeholder": "https://www.tiktok.com/@user/video/... ou https://www.instagram.com/reel/...",
        "spin_analyze": "Analyse de la vidéo...",
        "spin_links": "Recherche des liens streaming...",
        "err_read": "Erreur de lecture du lien : {err}",
        "err_invalid_url": "Saisis un lien TikTok ou Instagram.",
        "detected_source": "Source de détection : {source}",
        "source_metadata": "Métadonnées",
        "source_audio": "Correspondance audio",
        "badge_queries": "Requêtes : {count}",
        "badge_region": "Région : DE",
        "expand_queries": "Termes utilisés",
        "err_no_links": "Aucun lien trouvé.",
        "tip_no_links": "Instagram n'a souvent pas de métadonnées musicales fiables.",
        "caption_match_query": "Trouvé via : {query}",
        "unknown": "Inconnu",
        "preview_title": "Aperçu audio",
        "preview_caption": "Lire 10 secondes de l'audio.",
        "preview_start": "Seconde de départ",
        "preview_error": "Impossible de charger l'aperçu : {err}",
    },
    "es": {
        "hero_sub": "Pega un enlace de TikTok/Instagram, detecta la canción y obtén enlaces.",
        "intro": "Pega un enlace de TikTok o Instagram.",
        "url_label": "URL TikTok/Instagram",
        "url_placeholder": "https://www.tiktok.com/@user/video/... o https://www.instagram.com/reel/...",
        "spin_analyze": "Analizando video...",
        "spin_links": "Buscando enlaces...",
        "err_read": "Error al leer el enlace: {err}",
        "err_invalid_url": "Ingresa un enlace de TikTok o Instagram.",
        "detected_source": "Fuente de detección: {source}",
        "source_metadata": "Metadatos",
        "source_audio": "Coincidencia de audio",
        "badge_queries": "Búsquedas: {count}",
        "badge_region": "Región: DE",
        "expand_queries": "Términos usados",
        "err_no_links": "No se encontraron enlaces.",
        "tip_no_links": "Instagram muchas veces no tiene metadatos de canción.",
        "caption_match_query": "Coincidencia por: {query}",
        "unknown": "Desconocido",
        "preview_title": "Vista previa",
        "preview_caption": "Reproduce 10 segundos de audio.",
        "preview_start": "Segundo inicial",
        "preview_error": "No se pudo cargar el audio: {err}",
    },
    "it": {
        "hero_sub": "Incolla il link TikTok/Instagram, rileva la canzone, ottieni i link.",
        "intro": "Incolla un link TikTok o Instagram.",
        "url_label": "URL TikTok/Instagram",
        "url_placeholder": "https://www.tiktok.com/@user/video/... oppure https://www.instagram.com/reel/...",
        "spin_analyze": "Analisi video...",
        "spin_links": "Ricerca link...",
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
        "preview_title": "Anteprima audio",
        "preview_caption": "Riproduci 10 secondi di audio.",
        "preview_start": "Secondo iniziale",
        "preview_error": "Impossibile caricare l'audio: {err}",
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
            "duration": info.get("duration") or 0,
        }


@st.cache_data(show_spinner=False)
def get_audio_preview_bytes(url: str, start_sec: int, duration_sec: int = 10):
    try:
        import imageio_ffmpeg
    except Exception as exc:
        return None, str(exc)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        in_template = str(tmp / "preview_input.%(ext)s")
        out_mp3 = tmp / "preview.mp3"

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
        except Exception as exc:
            return None, str(exc)

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            str(start_sec),
            "-t",
            str(duration_sec),
            "-i",
            str(in_file),
            "-vn",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-b:a",
            "192k",
            str(out_mp3),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not out_mp3.exists():
            return None, "ffmpeg conversion failed"
        return out_mp3.read_bytes(), None


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


def find_itunes_track_urls(query: str) -> list[str]:
    try:
        response = requests.get(
            f"https://itunes.apple.com/search?term={quote_plus(query)}&entity=song&limit=5",
            headers=REQUEST_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        return [r.get("trackViewUrl") for r in data.get("results", []) if r.get("trackViewUrl")]
    except requests.RequestException:
        return []


def find_deezer_track_urls(query: str) -> list[str]:
    try:
        response = requests.get(
            f"https://api.deezer.com/search?q={quote_plus(query)}&limit=5",
            headers=REQUEST_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        return [r.get("link") for r in data.get("data", []) if r.get("link")]
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


def get_streaming_links(queries: list[str]):
    for q in queries:
        for url in find_itunes_track_urls(q):
            links = get_odesli_links_from_url(url)
            if links:
                return links, q
        for url in find_deezer_track_urls(q):
            links = get_odesli_links_from_url(url)
            if links:
                return links, q
    return None, None


def inject_styles():
    st.markdown(
        """
        <style>
        header[data-testid="stHeader"], div[data-testid="stToolbar"], div[data-testid="stDecoration"], #MainMenu, footer { display:none !important; }
        .stApp {
            background: radial-gradient(700px 300px at 10% -10%, rgba(34,197,94,0.16), transparent 70%),
                        radial-gradient(850px 400px at 100% 0%, rgba(6,182,212,0.18), transparent 65%),
                        #060b16;
            color: #e6edf7;
        }
        section.main > div { max-width: 980px; padding-top: 0.6rem; }
        .hero { border: 1px solid #25324d; border-radius: 18px; padding: 1.2rem; background: linear-gradient(130deg,#101828,#12325c); margin-bottom: .9rem; }
        .hero h1 { margin:0; font-size: clamp(1.7rem,3vw,2.4rem); }
        .hero p { margin:.55rem 0 0 0; color:#c5d8f7; }
        .panel { margin-top:.6rem; }
        .result-card { margin-top:.75rem; border:1px solid #25324d; border-radius:14px; background:#0f172a; padding:1rem; }
        .result-title { margin:0; color:#f5f9ff; font-size:clamp(1.1rem,2vw,1.4rem); font-weight:700; }
        .result-sub { margin:.35rem 0 0 0; color:#9db0cf; font-size:.92rem; }
        .badge-row { display:flex; gap:.45rem; flex-wrap:wrap; margin-top:.7rem; }
        .badge { border-radius:999px; padding:.26rem .62rem; color:#d7fbe7; background:rgba(34,197,94,.14); border:1px solid rgba(34,197,94,.45); font-size:.78rem; font-weight:700; }
        .platform-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.65rem; margin-top:.85rem; }
        .platform-btn { text-decoration:none; min-height:44px; display:inline-flex; align-items:center; justify-content:center; border-radius:10px; color:#06101f !important; font-weight:700; background:linear-gradient(135deg,#34d399,#22c55e); border:1px solid rgba(0,0,0,.16); }
        .platform-btn.alt { color:#dbe7fb !important; background:linear-gradient(135deg,#1e293b,#27344d); border:1px solid #3c4d6f; }
        div[data-baseweb="select"] > div, div[data-baseweb="input"] > div { background:#0e162a !important; border:1px solid #334260 !important; color:#e6edf7 !important; }
        div[data-baseweb="input"] input, div[data-baseweb="select"] input { color:#e6edf7 !important; }
        label p, .stSlider label, .stCaption { color:#c2d3ee !important; }
        @media (max-width:860px){ .platform-grid{grid-template-columns:repeat(2,minmax(0,1fr));} }
        @media (max-width:640px){ section.main > div { padding-left:.85rem; padding-right:.85rem; } .platform-grid{grid-template-columns:1fr;} }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_platform_buttons(links: dict):
    platform_map = [
        ("spotify", "Spotify", False),
        ("appleMusic", "Apple Music", False),
        ("youtube", "YouTube", False),
        ("deezer", "Deezer", True),
        ("soundcloud", "SoundCloud", True),
    ]
    buttons = []
    for key, label, alt in platform_map:
        url = links.get(key, {}).get("url")
        if url:
            buttons.append(f'<a class="platform-btn{" alt" if alt else ""}" href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>')
    if buttons:
        st.markdown(f'<div class="platform-grid">{"".join(buttons)}</div>', unsafe_allow_html=True)


def main():
    st.set_page_config(page_title="whatsthesong", page_icon="🎵", layout="centered")
    inject_styles()

    language_label = st.selectbox("Language", list(LANG_OPTIONS.keys()), index=0)
    lang = LANG_OPTIONS[language_label]

    st.markdown(
        f"""
        <div class="hero">
            <h1>whatsthesong</h1>
            <p>{html.escape(tr(lang, "hero_sub"))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.write(tr(lang, "intro"))
    url = st.text_input(tr(lang, "url_label"), placeholder=tr(lang, "url_placeholder"))
    st.markdown("</div>", unsafe_allow_html=True)

    if not url:
        return

    if not is_supported_video_url(url):
        st.error(tr(lang, "err_invalid_url"))
        return

    with st.spinner(tr(lang, "spin_analyze")):
        try:
            audio_info = get_video_audio_info(url)
        except Exception as exc:
            st.error(tr(lang, "err_read", err=exc))
            return

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown(f"### {tr(lang, 'preview_title')}")
    st.caption(tr(lang, "preview_caption"))

    total_duration = int(audio_info.get("duration") or 0)
    max_start = max(total_duration - 10, 0)
    start_sec = st.slider(tr(lang, "preview_start"), min_value=0, max_value=max_start, value=0, step=1) if max_start > 0 else 0

    with st.spinner(tr(lang, "spin_analyze")):
        preview_bytes, preview_err = get_audio_preview_bytes(url, start_sec, 10)

    if preview_bytes:
        st.audio(preview_bytes, format="audio/mp3")
    elif preview_err:
        st.caption(tr(lang, "preview_error", err=preview_err))
    st.markdown("</div>", unsafe_allow_html=True)

    detection_label = tr(lang, "source_metadata")
    track = audio_info.get("track")
    artist = audio_info.get("artist")
    title = audio_info.get("title")

    if (not track or not artist or is_generic_track(track)):
        with st.spinner(tr(lang, "spin_analyze")):
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

    st.markdown(
        f"""
        <div class="result-card">
            <p class="result-title">{html.escape(detected_text)}</p>
            <p class="result-sub">{html.escape(tr(lang, "detected_source", source=detection_label))}</p>
            <div class="badge-row">
                <span class="badge">{html.escape(tr(lang, "badge_queries", count=len(queries)))}</span>
                <span class="badge">{html.escape(tr(lang, "badge_region"))}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(tr(lang, "expand_queries")):
        for item in queries:
            st.write(f"- {item}")

    with st.spinner(tr(lang, "spin_links")):
        links_data, matched_query = get_streaming_links(queries)

    if not links_data:
        st.error(tr(lang, "err_no_links"))
        st.caption(tr(lang, "tip_no_links"))
        return

    links = links_data.get("linksByPlatform", {})
    entities = links_data.get("entitiesByUniqueId", {})

    if matched_query:
        st.caption(tr(lang, "caption_match_query", query=matched_query))

    render_platform_buttons(links)

    if entities:
        first_key = next(iter(entities))
        thumbnail = entities[first_key].get("thumbnailUrl")
        if thumbnail:
            st.image(thumbnail, width=320)


if __name__ == "__main__":
    main()
