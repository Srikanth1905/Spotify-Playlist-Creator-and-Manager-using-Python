import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime
import re
import difflib
import time
load_dotenv()
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = "http://localhost:8888/callback"
SCOPE = "playlist-modify-private playlist-modify-public playlist-read-private user-library-modify"
@st.cache_resource
def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE, cache_path=".spotifycache"))
def clean_song_name(song_name):
    song_name = re.sub(r'\s*(?:By|by)\s*.*', '', song_name)
    song_name = re.sub(r'\s*Album-.*', '', song_name)
    return ' '.join(song_name.split()).lower()
def find_best_match(original_song_name, search_results, similarity_threshold=0.6):
    cleaned_song_name = clean_song_name(original_song_name)
    best_match = None
    best_similarity = 0
    for track in search_results:
        track_name = track['name'].lower()
        similarity = difflib.SequenceMatcher(None, cleaned_song_name, track_name).ratio()
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = track
    if best_match and best_similarity >= similarity_threshold:
        return best_match
    return None
def search_artists(sp, artist_name):
    results = sp.search(q=artist_name, type='artist', limit=10)
    return results['artists']['items']
def get_artist_albums(sp, artist_id):
    albums = []
    results = sp.artist_albums(artist_id, album_type='album,single', limit=50)
    seen_names = set()
    for album in results['items']:
        name_lower = album['name'].lower()
        if name_lower not in seen_names:
            seen_names.add(name_lower)
            albums.append(album)
    return albums
def get_album_tracks(sp, album_id):
    tracks = []
    results = sp.album_tracks(album_id)
    for track in results['items']:
        tracks.append({
            'name': track['name'],
            'id': track['id'],
            'artists': ', '.join([artist['name'] for artist in track['artists']])
        })
    return tracks
def create_playlist_from_tracks(sp, tracks_with_counts, playlist_name):
    try:
        with st.status("Creating playlist...", expanded=True) as status:
            user_id = sp.current_user()["id"]
            status.write("Creating new playlist...")
            playlist = sp.user_playlist_create(user_id, playlist_name, public=False)
            playlist_id = playlist["id"]
            track_pool = [(track['id'], track['count']) for track in tracks_with_counts]
            total_tracks = sum(count for _, count in track_pool)
            status.write("Preparing tracks...")
            interleaved_tracks = []
            while any(count > 0 for _, count in track_pool):
                for i, (track_id, count) in enumerate(track_pool):
                    if count > 0:
                        interleaved_tracks.append(track_id)
                        track_pool[i] = (track_id, count - 1)
            if interleaved_tracks:
                progress_bar = st.progress(0)
                for i in range(0, len(interleaved_tracks), 100):
                    batch = interleaved_tracks[i:i + 100]
                    status.write(f"Adding tracks {i+1} to {min(i+100, len(interleaved_tracks))}...")
                    sp.playlist_add_items(playlist_id, batch)
                    progress = min((i + 100) / len(interleaved_tracks), 1.0)
                    progress_bar.progress(progress)
                    time.sleep(0.1)
                status.update(label="Playlist created successfully!", state="complete")
                return True, f"Created playlist '{playlist_name}' with {len(interleaved_tracks)} tracks!"
            else:
                status.update(label="No tracks to add", state="error")
                return False, "No tracks could be added to the playlist."
    except Exception as e:
        if 'status' in locals():
            status.update(label=f"Error: {str(e)}", state="error")
        return False, f"Error creating playlist: {str(e)}"
def get_user_playlists(sp):
    playlists = []
    results = sp.current_user_playlists()
    while results:
        playlists.extend(results['items'])
        if results['next']:
            results = sp.next(results)
        else:
            break
    return playlists
def delete_playlists(sp, playlist_ids):
    user_id = sp.current_user()["id"]
    results = []
    for playlist_id in playlist_ids:
        try:
            sp.current_user_unfollow_playlist(playlist_id)
            results.append(("success", f"Successfully deleted/unfollowed playlist"))
        except Exception as e:
            results.append(("error", f"Error: {str(e)}"))
    return results
def initialize_session_state():
    if 'selected_tracks' not in st.session_state:
        st.session_state.selected_tracks = []
    if 'artist_albums' not in st.session_state:
        st.session_state.artist_albums = []
    if 'album_tracks' not in st.session_state:
        st.session_state.album_tracks = []
def show_artist_search(sp):
    st.subheader("🔍 Search Artist")
    artist_name = st.text_input("Enter artist name", key="artist_search")
    if artist_name:
        with st.spinner("Searching for artists..."):
            artists = search_artists(sp, artist_name)
        if artists:
            st.write("Select an artist:")
            cols = st.columns(5)
            for idx, artist in enumerate(artists):
                with cols[idx % 5]:
                    with st.container():
                        if artist['images']:
                            st.image(artist['images'][0]['url'], width=150, use_container_width=True)
                        st.markdown(f"**{artist['name']}**")
                        if st.button(f"Select", key=f"artist_{idx}"):
                            with st.spinner(f"Loading albums by {artist['name']}..."):
                                st.session_state.artist_albums = get_artist_albums(sp, artist['id'])
                                st.rerun()
    if st.session_state.artist_albums:
        st.subheader("Albums")
        cols = st.columns(4)
        for idx, album in enumerate(st.session_state.artist_albums):
            with cols[idx % 4]:
                with st.container():
                    if album['images']:
                        st.image(album['images'][0]['url'], width=200, use_container_width=True)
                    st.markdown(f"**{album['name']}**")
                    if st.button(f"View Tracks", key=f"album_{idx}"):
                        with st.spinner(f"Loading tracks from {album['name']}..."):
                            st.session_state.album_tracks = get_album_tracks(sp, album['id'])
                            st.rerun()
def show_album_search(sp):
    st.subheader("🔍 Search Album")
    album_name = st.text_input("Enter album name", key="album_search")
    if album_name:
        with st.spinner("Searching for albums..."):
            results = sp.search(q=album_name, type='album', limit=8)
            albums = results['albums']['items']
        if albums:
            cols = st.columns(4)
            for idx, album in enumerate(albums):
                with cols[idx % 4]:
                    with st.container():
                        if album['images']:
                            st.image(album['images'][0]['url'], width=200, use_container_width=True)
                        st.markdown(f"**{album['name']}**")
                        st.markdown(f"*{album['artists'][0]['name']}*")
                        if st.button(f"View Tracks", key=f"album_search_{idx}"):
                            with st.spinner(f"Loading tracks from {album['name']}..."):
                                st.session_state.album_tracks = get_album_tracks(sp, album['id'])
                                st.rerun()
def show_track_search(sp):
    st.subheader("🔍 Search Track")
    track_name = st.text_input("Enter track name", key="track_search")
    if track_name:
        with st.spinner("Searching for tracks..."):
            artist_match = re.search(r'(?:by|By)\s*([^-]+)', track_name)
            artist_query = artist_match.group(1).strip() if artist_match else ''
            query = f"{clean_song_name(track_name)} {artist_query}".strip()
            results = sp.search(q=query, limit=50, type="track")
            tracks = results["tracks"]["items"]
            best_match = find_best_match(track_name, tracks)
            if best_match:
                tracks = [best_match] + [t for t in tracks if t['id'] != best_match['id']][:9]
        if tracks:
            st.write("Select tracks to add to playlist:")
            for track in tracks:
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{track['name']}** - *{', '.join([artist['name'] for artist in track['artists']])}*")
                    with col2:
                        if st.button("Add", key=f"track_{track['id']}"):
                            track_info = {
                                'name': track['name'],
                                'id': track['id'],
                                'artists': ', '.join([artist['name'] for artist in track['artists']])
                            }
                            if track_info not in st.session_state.selected_tracks:
                                st.session_state.selected_tracks.append(track_info)
                                st.success(f"Added {track['name']} to selection")
def show_album_tracks(sp):
    if st.session_state.album_tracks:
        st.subheader("Album Tracks")
        for track in st.session_state.album_tracks:
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{track['name']}** - *{track['artists']}*")
                with col2:
                    if st.button("Add", key=f"track_{track['id']}"):
                        if track not in st.session_state.selected_tracks:
                            st.session_state.selected_tracks.append(track)
                            st.success(f"Added {track['name']} to selection")
def show_playlist_creation(sp):
    if st.session_state.selected_tracks:
        st.header("Create Playlist")
        st.write("Selected Tracks:")
        tracks_with_counts = []
        for track in st.session_state.selected_tracks:
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"**{track['name']}** - *{track['artists']}*")
                with col2:
                    count = st.number_input("Count", min_value=1, max_value=50, value=1, key=f"count_{track['id']}")
                with col3:
                    if st.button("Remove", key=f"remove_{track['id']}"):
                        st.session_state.selected_tracks.remove(track)
                        st.rerun()
                tracks_with_counts.append({'id': track['id'], 'count': count})
        playlist_name = st.text_input("Playlist Name", value=f"My Mix - {datetime.now().strftime('%B %d, %Y')}")
        if st.button("Create Playlist"):
            success, message = create_playlist_from_tracks(sp, tracks_with_counts, playlist_name)
            if success:
                st.success(message)
                st.session_state.selected_tracks = []
            else:
                st.error(message)
def show_playlist_manager(sp):
    st.title("Playlist Manager")
    with st.spinner("Loading playlists..."):
        playlists = get_user_playlists(sp)
        user_id = sp.current_user()["id"]
    owned_playlists = [p for p in playlists if p['owner']['id'] == user_id]
    followed_playlists = [p for p in playlists if p['owner']['id'] != user_id]
    st.header("Your Playlists")
    if owned_playlists:
        selected_owned = []
        for playlist in owned_playlists:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{playlist['name']}** (Owned)")
            with col2:
                selected_owned.append(st.checkbox("Select", key=f"owned_{playlist['id']}"))
        if any(selected_owned):
            if st.button("Delete Selected"):
                playlists_to_delete = [p['id'] for p, selected in zip(owned_playlists, selected_owned) if selected]
                results = delete_playlists(sp, playlists_to_delete)
                for status, message in results:
                    if status == "success":
                        st.success(message)
                    else:
                        st.error(message)
                time.sleep(1)
                st.rerun()
def main():
    st.set_page_config(page_title="Spotify Playlist Manager", page_icon="🎵", layout="wide")
    initialize_session_state()
    try:
        sp = get_spotify_client()
    except Exception as e:
        st.error(f"Error connecting to Spotify: {str(e)}")
        return
    page = st.sidebar.radio("Navigation", ["Playlist Generator", "Playlist Manager"])
    if page == "Playlist Generator":
        st.title("Spotify Playlist Generator")
        search_type = st.radio("Search by:", ["Artist", "Album", "Track"], horizontal=True)
        if search_type == "Artist":
            show_artist_search(sp)
        elif search_type == "Album":
            show_album_search(sp)
        else:
            show_track_search(sp)
        show_album_tracks(sp)
        show_playlist_creation(sp)
    else:
        show_playlist_manager(sp)
if __name__ == "__main__":
    main()