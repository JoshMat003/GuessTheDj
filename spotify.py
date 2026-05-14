import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

load_dotenv()
load_dotenv(dotenv_path='secrets.env')

client_id = (os.getenv('SPOTIFY_CLIENT_ID') or '').strip()
client_secret = (os.getenv('SPOTIFY_CLIENT_SECRET') or '').strip()
redirect_uri = (os.getenv('SPOTIFY_REDIRECT_URI') or 'http://localhost:8888/callback').strip()
playlist_id = (os.getenv('SPOTIFY_PLAYLIST_ID') or '0hZMtCh7Plo8MbVX0r1PhE').strip()


def _build_search_client():
    if not client_id or not client_secret:
        return None
    try:
        return spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret,
            )
        )
    except Exception:
        return None


def _build_playlist_client():
    if not client_id or not client_secret:
        return None
    try:
        return spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope='playlist-modify-public playlist-modify-private',
            )
        )
    except Exception:
        return None


search_sp = _build_search_client()
playlist_sp = _build_playlist_client()


def search_song(query):
    query = (query or '').strip()
    if not query or search_sp is None:
        return []

    try:
        results = search_sp.search(q=query, type='track', limit=5)
    except Exception:
        return []

    songs = []
    for track in (results.get('tracks') or {}).get('items', []):
        album = track.get('album') or {}
        images = album.get('images') or []
        artists = track.get('artists') or []
        songs.append({
            'name': track.get('name'),
            'artist': (artists[0].get('name') if artists else None),
            'album': album.get('name'),
            'image': (images[0].get('url') if images else None),
            'url': (track.get('external_urls') or {}).get('spotify'),
            'uri': track.get('uri'),
        })

    return songs


def clear_playlist():
    if playlist_sp is None or not playlist_id:
        return False

    try:
        # Fast path: replace playlist contents with an empty list.
        playlist_sp.playlist_replace_items(playlist_id, [])
        return True
    except Exception:
        pass

    # Fallback path: paginate and remove tracks in batches.
    try:
        offset = 0
        limit = 100
        while True:
            results = playlist_sp.playlist_items(
                playlist_id,
                offset=offset,
                limit=limit,
                fields='items(track(uri)),total,next',
            )
            track_uris = [
                item['track']['uri']
                for item in results.get('items', [])
                if item.get('track') and item['track'].get('uri')
            ]
            if track_uris:
                playlist_sp.playlist_remove_all_occurrences_of_items(playlist_id, track_uris)

            if not results.get('next'):
                break
            offset += limit

        return True
    except Exception:
        return False


def add_song_to_playlist(track_uri):
    if playlist_sp is None or not playlist_id:
        return False

    if not track_uri:
        return False

    try:
        playlist_sp.playlist_add_items(playlist_id, [track_uri])
        return True
    except Exception:
        return False
