import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime
import re
import difflib

# Load environment variables
load_dotenv()

# Spotify Authentication Setup
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = "http://localhost:8888/callback"
SCOPE = "playlist-modify-private playlist-modify-public playlist-read-private user-library-modify"

# Initialize Spotify client
@st.cache_resource
def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID,client_secret=CLIENT_SECRET,redirect_uri=REDIRECT_URI,scope=SCOPE,cache_path=".spotifycache"))

# Helper functions
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
        user_id = sp.current_user()["id"]
        playlist = sp.user_playlist_create(user_id, playlist_name, public=False)
        playlist_id = playlist["id"]
        
        track_pool = [(track['id'], track['count']) for track in tracks_with_counts]
        
        interleaved_tracks = []
        while any(count > 0 for _, count in track_pool):
            for i, (track_id, count) in enumerate(track_pool):
                if count > 0:
                    interleaved_tracks.append(track_id)
                    track_pool[i] = (track_id, count - 1)
        
        if interleaved_tracks:
            for i in range(0, len(interleaved_tracks), 100):
                sp.playlist_add_items(playlist_id, interleaved_tracks[i:i + 100])
            
            return True, f"Created playlist '{playlist_name}' with {len(interleaved_tracks)} tracks!"
        else:
            return False, "No tracks could be added to the playlist."
            
    except Exception as e:
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

def main():
    st.set_page_config(page_title="Spotify Playlist Manager",
                      page_icon="🎵",
                      layout="wide",
                      initial_sidebar_state="expanded")

    # Custom CSS
    st.markdown("""
        <style>
        .main {
            background-color: #1DB954;
            color: white;
        }
        .stButton>button {
            background-color: #1DB954;
            color: white;
            border-radius: 20px;
            padding: 10px 24px;
            border: none;
        }
        .stTextInput>div>div>input {
            border-radius: 20px;
        }
        .search-result {
            padding: 10px;
            border-radius: 10px;
            background-color: #f0f0f0;
            margin: 5px 0;
        }
        </style>
    """, unsafe_allow_html=True)

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Playlist Generator", "Playlist Manager"])

    try:
        sp = get_spotify_client()
        
        if page == "Playlist Generator":
            show_playlist_generator(sp)
        else:
            show_playlist_manager(sp)
            
    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.info("Please make sure you're properly authenticated with Spotify.")

def show_playlist_generator(sp):
    st.title("🎵 Spotify Playlist Generator")
    
    # Search type selector
    search_type = st.radio("Search by:", ["Artist", "Album", "Track"], horizontal=True)
    
    if search_type == "Artist":
        show_artist_search(sp)
    elif search_type == "Album":
        show_album_search(sp)
    else:
        show_track_search(sp)
    
    # Track selection and playlist creation
    if 'selected_tracks' in st.session_state:
        show_playlist_creation(sp)

def show_playlist_manager(sp):
    st.title("🎵 Spotify Playlist Manager")
    
    # Get user's playlists
    playlists = get_user_playlists(sp)
    user_id = sp.current_user()["id"]
    
    # Separate owned and followed playlists
    owned_playlists = [p for p in playlists if p['owner']['id'] == user_id]
    followed_playlists = [p for p in playlists if p['owner']['id'] != user_id]
    
    # Display owned playlists
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
            if st.button("Delete Selected Playlists"):
                if st.warning("Are you sure you want to delete these playlists?"):
                    playlists_to_delete = [p['id'] for p, selected in zip(owned_playlists, selected_owned) if selected]
                    results = delete_playlists(sp, playlists_to_delete)
                    for status, message in results:
                        if status == "success":
                            st.success(message)
                        else:
                            st.error(message)
                    st.rerun()
    else:
        st.info("You don't own any playlists.")
    
    # Display followed playlists
    st.header("Followed Playlists")
    if followed_playlists:
        selected_followed = []
        for playlist in followed_playlists:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{playlist['name']}** by *{playlist['owner']['display_name']}*")
            with col2:
                selected_followed.append(st.checkbox("Select", key=f"followed_{playlist['id']}"))
        
        if any(selected_followed):
            if st.button("Unfollow Selected Playlists"):
                if st.warning("Are you sure you want to unfollow these playlists?"):
                    playlists_to_unfollow = [p['id'] for p, selected in zip(followed_playlists, selected_followed) if selected]
                    results = delete_playlists(sp, playlists_to_unfollow)
                    for status, message in results:
                        if status == "success":
                            st.success(message)
                        else:
                            st.error(message)
                    st.rerun()
    else:
        st.info("You're not following any playlists.")

def show_artist_search(sp):
    st.subheader("Search Artist")
    artist_name = st.text_input("Enter artist name", key="artist_search")
    
    if artist_name:
        artists = search_artists(sp, artist_name)
        
        if artists:
            st.write("Select an artist:")
            cols = st.columns(5)
            
            for idx, artist in enumerate(artists):
                with cols[idx % 5]:
                    if artist['images']:
                        st.image(artist['images'][0]['url'], width=150)
                    st.write(f"**{artist['name']}**")
                    if st.button(f"Select {artist['name']}", key=f"artist_{idx}"):
                        st.session_state.selected_artist = artist
                        st.session_state.artist_albums = get_artist_albums(sp, artist['id'])
                        if 'selected_tracks' in st.session_state:
                            del st.session_state.selected_tracks
                        st.rerun()
        
        if 'selected_artist' in st.session_state:
            show_artist_albums(sp)

def show_artist_albums(sp):
    st.subheader(f"Albums by {st.session_state.selected_artist['name']}")
    
    albums = st.session_state.artist_albums
    if albums:
        cols = st.columns(4)
        for idx, album in enumerate(albums):
            with cols[idx % 4]:
                if album['images']:
                    st.image(album['images'][0]['url'], width=200)
                st.write(f"**{album['name']}**")
                if st.button(f"View Tracks", key=f"album_{idx}"):
                    st.session_state.selected_album = album
                    st.session_state.album_tracks = get_album_tracks(sp, album['id'])
                    st.rerun()
    
    if 'selected_album' in st.session_state:
        show_album_tracks(sp)

def show_album_search(sp):
    st.subheader("Search Album")
    album_name = st.text_input("Enter album name", key="album_search")
    
    if album_name:
        results = sp.search(q=album_name, type='album', limit=8)
        albums = results['albums']['items']
        
        if albums:
            cols = st.columns(4)
            for idx, album in enumerate(albums):
                with cols[idx % 4]:
                    if album['images']:
                        st.image(album['images'][0]['url'], width=200)
                    st.write(f"**{album['name']}**")
                    st.write(f"*{album['artists'][0]['name']}*")
                    if st.button(f"View Tracks", key=f"album_search_{idx}"):
                        st.session_state.selected_album = album
                        st.session_state.album_tracks = get_album_tracks(sp, album['id'])
                        if 'selected_tracks' in st.session_state:
                            del st.session_state.selected_tracks
                        st.rerun()
        
        if 'selected_album' in st.session_state:
            show_album_tracks(sp)

def show_track_search(sp):
    st.subheader("Search Track")
    track_name = st.text_input("Enter track name", key="track_search")
    
    if track_name:
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
            
            if 'selected_tracks' not in st.session_state:
                st.session_state.selected_tracks = []
            
            for track in tracks:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{track['name']}** - *{', '.join([artist['name'] for artist in track['artists']])}*")
                with col2:
                    if st.button("Add", key=f"track_{track['id']}"):
                        track_info = { 'name': track['name'],'id': track['id'],'artists': ', '.join([artist['name'] for artist in track['artists']])}
                        if track_info not in st.session_state.selected_tracks:
                            st.session_state.selected_tracks.append(track_info)
                            st.success(f"Added {track['name']} to selection")

def show_album_tracks(sp):
    st.subheader(f"Tracks from {st.session_state.selected_album['name']}")
    
    if 'selected_tracks' not in st.session_state:
        st.session_state.selected_tracks = []
    
    for track in st.session_state.album_tracks:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**{track['name']}** - *{track['artists']}*")
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
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{track['name']}** - *{track['artists']}*")
            with col2:
                count = st.number_input(f"Count", min_value=1, max_value=50, value=1, key=f"count_{track['id']}")
            with col3:
                if st.button("Remove", key=f"remove_{track['id']}"):
                    st.session_state.selected_tracks.remove(track)
                    st.rerun()
            
            tracks_with_counts.append({'id': track['id'], 'count': count})
        
        playlist_name = st.text_input("Playlist Name", value="My Custom Mix")
        
        if st.button("Create Playlist", type="primary"):
            success, message = create_playlist_from_tracks(sp, tracks_with_counts, playlist_name)
            if success:
                st.success(message)
                st.session_state.selected_tracks = []  
            else:
                st.error(message)

if __name__ == "__main__":
    main()
