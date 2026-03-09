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
GENERIC_TIKTOK_TRACK_HINTS = {
    "original",
    "original sound",
    "som original",
    "son original",
    "suono originale",
}

SUPPORTED_VIDEO_HOST_HINTS = ("tiktok.com", "instagram.com", "instagr.am")

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
        "intro": "Fuege einen TikTok-Link ein, um Spotify-, Apple-Music- und YouTube-Links zu finden.",
        "url_label": "TikTok/Instagram URL",
        "url_placeholder": "https://www.tiktok.com/@user/video/...  oder https://www.instagram.com/reel/...",
        "fingerprint_toggle": "Audio-Fingerprint nutzen (langsamer, aber genauer)",
        "spin_analyze": "Analysiere Video...",
        "spin_fingerprint": "Hoere Audio und erkenne Song...",
        "spin_links": "Suche Streaming-Links...",
        "err_read": "Fehler beim Auslesen des TikTok-Links: {err}",
        "warn_no_fp": "Kein Audio-Match: {err}. Nutze Fallback ueber Metadaten.",
        "success_fp": "Audio-Match: {title} - {artist}",
        "detected_source": "Erkennungsquelle: {source}",
        "source_metadata": "TikTok-Metadaten",
        "source_fingerprint": "Audio Fingerprint (Shazam)",
        "badge_queries": "Suchbegriffe: {count}",
        "badge_region": "Region: DE",
        "expand_queries": "Verwendete Suchbegriffe",
        "err_no_links": "Leider konnten keine Streaming-Links gefunden werden.",
        "tip_no_links": "Tipp: Manche TikToks nutzen keinen offiziellen Song oder stark veraenderte Remixe.",
        "caption_match_query": "Treffer ueber Suchbegriff: {query}",
        "unknown": "Unbekannt",
        "err_packages": "Audio-Fingerprint-Pakete fehlen. Bitte requirements installieren.",
        "err_download": "Audio-Download fehlgeschlagen: {err}",
        "err_no_fp_match": "Kein Fingerprint-Match gefunden",
        "preview_title": "Audio-Preview",
        "preview_caption": "Spiele 10 Sekunden aus dem Video-Audio ab.",
        "preview_start": "Startsekunde",
        "preview_error": "Audio-Preview konnte nicht geladen werden: {err}",
    },
    "en": {
        "hero_sub": "Paste TikTok/Instagram link, detect song, get streaming links.",
        "intro": "Paste a TikTok link to find Spotify, Apple Music, and YouTube links.",
        "url_label": "TikTok/Instagram URL",
        "url_placeholder": "https://www.tiktok.com/@user/video/...  oder https://www.instagram.com/reel/...",
        "fingerprint_toggle": "Use audio fingerprint (slower, more accurate)",
        "spin_analyze": "Analyzing video...",
        "spin_fingerprint": "Listening to audio and detecting song...",
        "spin_links": "Searching streaming links...",
        "err_read": "Error reading TikTok link: {err}",
        "warn_no_fp": "No audio match: {err}. Falling back to metadata.",
        "success_fp": "Audio match: {title} - {artist}",
        "detected_source": "Detection source: {source}",
        "source_metadata": "TikTok metadata",
        "source_fingerprint": "Audio fingerprint (Shazam)",
        "badge_queries": "Queries: {count}",
        "badge_region": "Region: DE",
        "expand_queries": "Used search terms",
        "err_no_links": "No streaming links could be found.",
        "tip_no_links": "Tip: some TikToks use unofficial songs or heavily edited remixes.",
        "caption_match_query": "Matched via query: {query}",
        "unknown": "Unknown",
        "err_packages": "Audio fingerprint packages are missing. Please install requirements.",
        "err_download": "Audio download failed: {err}",
        "err_no_fp_match": "No fingerprint match found",
        "preview_title": "Audio preview",
        "preview_caption": "Play 10 seconds from the video audio.",
        "preview_start": "Start second",
        "preview_error": "Could not load audio preview: {err}",
    },
    "fr": {
        "hero_sub": "Colle un lien TikTok/Instagram, detecte la musique, recupere les liens streaming.",
        "intro": "Colle un lien TikTok pour trouver les liens Spotify, Apple Music et YouTube.",
        "url_label": "URL TikTok/Instagram",
        "url_placeholder": "https://www.tiktok.com/@user/video/...  oder https://www.instagram.com/reel/...",
        "fingerprint_toggle": "Utiliser l'empreinte audio (plus lent, plus precis)",
        "spin_analyze": "Analyse de la video...",
        "spin_fingerprint": "Analyse audio et detection du titre...",
        "spin_links": "Recherche des liens streaming...",
        "err_read": "Erreur lors de la lecture du lien TikTok : {err}",
        "warn_no_fp": "Aucune correspondance audio : {err}. Repli sur les metadonnees.",
        "success_fp": "Correspondance audio : {title} - {artist}",
        "detected_source": "Source de detection : {source}",
        "source_metadata": "Metadonnees TikTok",
        "source_fingerprint": "Empreinte audio (Shazam)",
        "badge_queries": "Requetes : {count}",
        "badge_region": "Region : DE",
        "expand_queries": "Termes de recherche utilises",
        "err_no_links": "Aucun lien streaming trouve.",
        "tip_no_links": "Astuce : certains TikToks utilisent des sons non officiels ou des remixes tres modifies.",
        "caption_match_query": "Trouve via la requete : {query}",
        "unknown": "Inconnu",
        "err_packages": "Paquets d'empreinte audio manquants. Installe les dependances.",
        "err_download": "Echec du telechargement audio : {err}",
        "err_no_fp_match": "Aucune correspondance d'empreinte trouvee",
        "preview_title": "Apercu audio",
        "preview_caption": "Lire 10 secondes de l'audio de la video.",
        "preview_start": "Seconde de depart",
        "preview_error": "Impossible de charger l'apercu audio : {err}",
    },
    "es": {
        "hero_sub": "Pega un enlace de TikTok/Instagram, detecta la cancion y obten enlaces de streaming.",
        "intro": "Pega un enlace de TikTok para encontrar enlaces de Spotify, Apple Music y YouTube.",
        "url_label": "URL TikTok/Instagram",
        "url_placeholder": "https://www.tiktok.com/@user/video/...  oder https://www.instagram.com/reel/...",
        "fingerprint_toggle": "Usar huella de audio (mas lento, mas preciso)",
        "spin_analyze": "Analizando video...",
        "spin_fingerprint": "Escuchando audio y detectando cancion...",
        "spin_links": "Buscando enlaces de streaming...",
        "err_read": "Error al leer el enlace de TikTok: {err}",
        "warn_no_fp": "Sin coincidencia de audio: {err}. Uso de metadatos como respaldo.",
        "success_fp": "Coincidencia de audio: {title} - {artist}",
        "detected_source": "Fuente de deteccion: {source}",
        "source_metadata": "Metadatos de TikTok",
        "source_fingerprint": "Huella de audio (Shazam)",
        "badge_queries": "Busquedas: {count}",
        "badge_region": "Region: DE",
        "expand_queries": "Terminos de busqueda usados",
        "err_no_links": "No se pudieron encontrar enlaces de streaming.",
        "tip_no_links": "Consejo: algunos TikToks usan canciones no oficiales o remixes muy editados.",
        "caption_match_query": "Coincidencia por busqueda: {query}",
        "unknown": "Desconocido",
        "err_packages": "Faltan paquetes de huella de audio. Instala los requisitos.",
        "err_download": "Error al descargar audio: {err}",
        "err_no_fp_match": "No se encontro coincidencia de huella",
        "preview_title": "Vista previa de audio",
        "preview_caption": "Reproduce 10 segundos del audio del video.",
        "preview_start": "Segundo de inicio",
        "preview_error": "No se pudo cargar la vista previa de audio: {err}",
    },
    "it": {
        "hero_sub": "Incolla il link TikTok/Instagram, rileva la canzone, ottieni i link streaming.",
        "intro": "Incolla un link TikTok per trovare i link Spotify, Apple Music e YouTube.",
        "url_label": "URL TikTok/Instagram",
        "url_placeholder": "https://www.tiktok.com/@user/video/...  oder https://www.instagram.com/reel/...",
        "fingerprint_toggle": "Usa impronta audio (piu lento, piu preciso)",
        "spin_analyze": "Analisi del video...",
        "spin_fingerprint": "Ascolto audio e rilevamento brano...",
        "spin_links": "Ricerca link streaming...",
        "err_read": "Errore nella lettura del link TikTok: {err}",
        "warn_no_fp": "Nessuna corrispondenza audio: {err}. Uso fallback metadati.",
        "success_fp": "Corrispondenza audio: {title} - {artist}",
        "detected_source": "Fonte rilevamento: {source}",
        "source_metadata": "Metadati TikTok",
        "source_fingerprint": "Impronta audio (Shazam)",
        "badge_queries": "Query: {count}",
        "badge_region": "Regione: DE",
        "expand_queries": "Termini di ricerca usati",
        "err_no_links": "Nessun link streaming trovato.",
        "tip_no_links": "Suggerimento: alcuni TikTok usano brani non ufficiali o remix molto modificati.",
        "caption_match_query": "Trovato con query: {query}",
        "unknown": "Sconosciuto",
        "err_packages": "Pacchetti impronta audio mancanti. Installa i requisiti.",
        "err_download": "Download audio fallito: {err}",
        "err_no_fp_match": "Nessuna corrispondenza impronta trovata",
        "preview_title": "Anteprima audio",
        "preview_caption": "Riproduci 10 secondi dell'audio del video.",
        "preview_start": "Secondo iniziale",
        "preview_error": "Impossibile caricare l'anteprima audio: {err}",
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


def get_tiktok_audio_info(url: str):
    ydl_opts = {"format": "bestaudio/best", "noplaylist": True, "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return {
                "track": info.get("track"),
                "artist": info.get("artist"),
                "title": info.get("title"),
                "description": info.get("description") or "",
                "artists": info.get("artists") or [],
                "duration": info.get("duration") or 0,
            }, None
        except Exception as exc:
            return None, str(exc)



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


def is_generic_tiktok_track(track_name: str | None) -> bool:
    if not track_name:
        return True
    return any(h in track_name.strip().lower() for h in GENERIC_TIKTOK_TRACK_HINTS)


def clean_query(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"https?://\S+", " ", text).replace("#", " ")
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_hashtags(text: str | None) -> list[str]:
    return re.findall(r"#([a-zA-Z0-9_\.]+)", text or "")


def build_search_queries(audio_info: dict) -> list[str]:
    track, artist, title = audio_info.get("track"), audio_info.get("artist"), audio_info.get("title")
    description, artists = audio_info.get("description"), audio_info.get("artists") or []
    queries: list[str] = []

    if track and artist and not is_generic_tiktok_track(track):
        queries += [f"{track} {artist}", track]
    elif track and not is_generic_tiktok_track(track):
        queries.append(track)

    if artist:
        queries.append(artist)
    queries += [str(a) for a in artists[:2] if a]

    for q in [clean_query(title), clean_query(description)]:
        if q:
            queries.append(q)

    for tag in (extract_hashtags(title) + extract_hashtags(description))[:5]:
        if len(tag) > 2:
            queries.append(tag.replace(".", " "))

    out, seen = [], set()
    for q in queries:
        n = q.lower().strip()
        if n and n not in seen and len(n) >= 3:
            out.append(q.strip())
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
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap');

        :root {
            --bg: #060b16;
            --panel: #0f172a;
            --panel-2: #111c34;
            --line: #25324d;
            --text: #e6edf7;
            --muted: #9db0cf;
            --accent: #22c55e;
            --accent-2: #06b6d4;
        }

        html, body, [class*="css"]  {
            font-family: 'Space Grotesk', sans-serif;
        }

        
        header[data-testid="stHeader"],
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"],
        #MainMenu,
        footer {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
        }
        .stApp {
            background:
                radial-gradient(700px 300px at 8% -10%, rgba(34,197,94,0.16), transparent 70%),
                radial-gradient(850px 400px at 100% 0%, rgba(6,182,212,0.18), transparent 65%),
                var(--bg);
            color: var(--text);
        }

        section.main > div {
            max-width: 980px;
            padding-top: 0.55rem;
            padding-bottom: 2rem;
        }

        .hero {
            border: 1px solid var(--line);
            border-radius: 18px;
            background: linear-gradient(135deg, #0b1220 0%, #10233f 65%, #0c4a6e 100%);
            padding: 1.2rem 1.2rem;
            box-shadow: 0 20px 40px rgba(0,0,0,0.35);
            margin-bottom: 0.9rem;
        }

        .hero h1 {
            margin: 0;
            color: #f8fbff;
            font-size: clamp(1.7rem, 3vw, 2.4rem);
            line-height: 1.08;
        }

        .hero p {
            margin: 0.55rem 0 0 0;
            color: #c5d8f7;
            font-size: 1rem;
        }

        .panel {
            border: none;
            border-radius: 0;
            background: transparent;
            padding: 0;
            margin-top: 0.45rem;
        }

        .panel-title {
            margin: 0 0 0.35rem 0;
            color: #e6edf7;
            font-weight: 700;
            font-size: 1rem;
        }

        .panel-sub {
            margin: 0;
            color: #9db0cf;
            font-size: 0.92rem;
        }

        .result-card {
            margin-top: 0.75rem;
            border: 1px solid var(--line);
            border-radius: 14px;
            background: linear-gradient(180deg, rgba(17,28,52,0.92), rgba(11,18,32,0.92));
            padding: 1rem;
        }

        .result-title {
            margin: 0;
            color: #f5f9ff;
            font-size: clamp(1.1rem, 2vw, 1.4rem);
            font-weight: 700;
        }

        .result-sub {
            margin: 0.35rem 0 0 0;
            color: #9db0cf;
            font-size: 0.92rem;
        }

        .badge-row {
            display: flex;
            gap: 0.45rem;
            flex-wrap: wrap;
            margin-top: 0.7rem;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.26rem 0.62rem;
            color: #d7fbe7;
            background: rgba(34,197,94,0.14);
            border: 1px solid rgba(34,197,94,0.45);
            font-size: 0.78rem;
            font-weight: 700;
        }

        .platform-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.65rem;
            margin-top: 0.85rem;
        }

        .platform-btn {
            text-decoration: none;
            min-height: 44px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 10px;
            color: #06101f !important;
            font-weight: 700;
            font-size: 0.93rem;
            background: linear-gradient(135deg, #34d399, #22c55e);
            border: 1px solid rgba(0,0,0,0.16);
        }

        .platform-btn.alt {
            color: #dbe7fb !important;
            background: linear-gradient(135deg, #1e293b, #27344d);
            border: 1px solid #3c4d6f;
        }

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div {
            background: #0e162a !important;
            border: 1px solid #334260 !important;
            color: #e6edf7 !important;
        }

        div[data-baseweb="input"] input,
        div[data-baseweb="select"] input {
            color: #e6edf7 !important;
        }

        label p,
        .stCheckbox label,
        .stSlider label {
            color: #c2d3ee !important;
            font-weight: 600 !important;
        }

        .stCaption {
            color: #9db0cf !important;
        }

        @media (max-width: 860px) {
            .platform-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }

        @media (max-width: 640px) {
            section.main > div {
                padding-left: 0.85rem;
                padding-right: 0.85rem;
                padding-top: 0.75rem;
            }
            .hero, .panel, .result-card {
                border-radius: 12px;
            }
            .platform-grid { grid-template-columns: 1fr; }
        }
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
    st.markdown(f'<p class="panel-title">{html.escape(tr(lang, "intro"))}</p>', unsafe_allow_html=True)
    url = st.text_input(tr(lang, "url_label"), placeholder=tr(lang, "url_placeholder"))
    st.markdown("</div>", unsafe_allow_html=True)

    if not url:
        return

    if not is_supported_video_url(url):
        st.error("Please use a TikTok or Instagram URL.")
        return

    with st.spinner(tr(lang, "spin_analyze")):
        audio_info, err = get_tiktok_audio_info(url)

    if err:
        st.error(tr(lang, "err_read", err=err))
        return

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown(f'<p class="panel-title">{html.escape(tr(lang, "preview_title"))}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="panel-sub">{html.escape(tr(lang, "preview_caption"))}</p>', unsafe_allow_html=True)

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

    fallback_queries = build_search_queries(audio_info)
    queries, seen = [], set()
    for q in fallback_queries:
        n = q.lower().strip() if q else ""
        if n and n not in seen:
            queries.append(q)
            seen.add(n)

    track, artist, title = audio_info.get("track"), audio_info.get("artist"), audio_info.get("title")
    if track and artist and not is_generic_tiktok_track(track):
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








