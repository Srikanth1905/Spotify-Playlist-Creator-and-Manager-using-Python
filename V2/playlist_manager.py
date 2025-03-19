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
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
from streamlit_autorefresh import st_autorefresh
import json
load_dotenv()
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = (
    "playlist-modify-private "
    "playlist-modify-public "
    "playlist-read-private "
    "user-library-modify "
    "user-read-private "
    "user-read-email "
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing "
    "streaming"
)

# Utility functions for common operations
def show_notification(message, type="info"):
    """Show a custom notification box with the given message and type."""
    styles = {
        "info": {
            "icon": "ℹ️",
            "style": {
                "backgroundColor": "#EEF6FF",
                "borderLeft": "5px solid #3B82F6"
            }
        },
        "success": {
            "icon": "✅",
            "style": {
                "backgroundColor": "#F0FDF4",
                "borderLeft": "5px solid #22C55E"
            }
        },
        "warning": {
            "icon": "⚠️",
            "style": {
                "backgroundColor": "#FFFBEB",
                "borderLeft": "5px solid #F59E0B"
            }
        },
        "error": {
            "icon": "❌",
            "style": {
                "backgroundColor": "#FEF2F2",
                "borderLeft": "5px solid #EF4444"
            }
        }
    }
    
    style = styles.get(type, styles["info"])
    st.markdown(
        f"""
        <div style="
            padding: 1rem;
            border-radius: 0.5rem;
            margin: 1rem 0;
            background-color: {style['style']['backgroundColor']};
            border-left: {style['style']['borderLeft']};
        ">
            {style['icon']} {message}
        </div>
        """,
        unsafe_allow_html=True
    )

def handle_spotify_operation_result(results):
    """Handle operation results with consistent UI feedback."""
    for status, message in results:
        if status == "success":
            show_notification(message, "success")
        else:
            show_notification(message, "error")
    time.sleep(0.5)
    st.rerun()

def display_playlist_section(playlists, section_type, sp, user_id):
    """Display and handle playlist section with consistent UI."""
    selected = []
    for playlist in playlists:
        col1, col2 = st.columns([3, 1])
        with col1:
            owner_text = "(Owned)" if section_type == "owned" else f"(by {playlist['owner']['display_name']})"
            st.write(f"**{playlist['name']}** {owner_text}")
        with col2:
            selected.append(st.checkbox("Select", key=f"{section_type}_{playlist['id']}"))
    
    if any(selected):
        button_text = "Delete Selected" if section_type == "owned" else "Unfollow Selected"
        if st.button(button_text):
            playlists_to_modify = [p['id'] for p, selected in zip(playlists, selected) if selected]
            results = delete_playlists(sp, playlists_to_modify)
            handle_spotify_operation_result(results)

def clean_song_name(song_name):
    """Clean song name with a single regex operation."""
    # Combined regex to remove both "By/by <artist>" and "Album-<name>" in one pass
    cleaned = re.sub(r'\s*(?:(?:By|by)\s*.*|Album-.*)', '', song_name)
    return ' '.join(cleaned.split()).lower()

@st.cache_resource
def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE, cache_path=".spotifycache"))

# Cache for 1 hour
def get_user_playlists(sp):
    """Cached function to get user playlists."""
    playlists = []
    results = sp.current_user_playlists()
    while results:
        playlists.extend(results['items'])
        if results['next']:
            results = sp.next(results)
        else:
            break
    return playlists

# Cache for 5 minutes
def search_artists(sp, artist_name):
    """Cached function to search artists."""
    results = sp.search(q=artist_name, type='artist', limit=5)  # Reduced to match UI columns
    return results['artists']['items']

  # Cache for 5 minutes
def get_artist_albums(sp, artist_id):
    """Cached function to get artist albums with deduplication."""
    albums = []
    results = sp.artist_albums(artist_id, album_type='album,single')
    seen_names = set()
    for album in results['items']:
        name_lower = album['name'].lower()
        if name_lower not in seen_names:
            seen_names.add(name_lower)
            albums.append(album)
    return albums

  # Cache for 5 minutes
def get_album_tracks(sp, album_id):
    """Cached function to get album tracks."""
    tracks = []
    results = sp.album_tracks(album_id)
    for track in results['items']:
        tracks.append({
            'name': track['name'],
            'id': track['id'],
            'artists': ', '.join([artist['name'] for artist in track['artists']])
        })
    return tracks

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
                show_notification(f"Created playlist '{playlist_name}' with {len(interleaved_tracks)} tracks!", "success")
                return True, f"Created playlist '{playlist_name}' with {len(interleaved_tracks)} tracks!"
            else:
                status.update(label="No tracks to add", state="error")
                show_notification("No tracks could be added to the playlist.", "error")
                return False, "No tracks could be added to the playlist."
    except Exception as e:
        if 'status' in locals():
            status.update(label=f"Error: {str(e)}", state="error")
        show_notification(f"Error creating playlist: {str(e)}", "error")
        return False, f"Error creating playlist: {str(e)}"

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
    if 'keyboard_shortcuts' not in st.session_state:
        st.session_state.keyboard_shortcuts = True

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
                show_notification("Found best matching track!", "info")
            elif not tracks:
                show_notification("No tracks found matching your search.", "warning")
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
                                show_notification(f"Added {track['name']} to selection", "success")

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
                            show_notification(f"Added {track['name']} to selection", "success")

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

def get_playlist_analytics(sp, playlist_id):
    """Get simplified analytics for a playlist with visual feedback."""
    try:
        with st.status("Analyzing playlist...", expanded=True) as status:
            status.write("Fetching playlist tracks...")
            results = sp.playlist_tracks(playlist_id)
            tracks = results['items']
            
            # Initialize counters and data structures
            track_data = {
                'artists': Counter(),
                'artist_durations': Counter(),  # Track duration per artist
                'albums': Counter(),
                'release_years': Counter(),
                'duration_ms': 0,
                'explicit_count': 0,
                'popularity_data': []
            }
            
            # Process tracks with progress bar
            status.write("Processing track information...")
            progress_bar = st.progress(0)
            for i, item in enumerate(tracks):
                if item['track']:
                    track = item['track']
                    
                    # Update progress
                    progress = (i + 1) / len(tracks)
                    progress_bar.progress(progress, text=f"Analyzing tracks... {int(progress * 100)}%")
                    
                    # Basic track info
                    track_duration = track['duration_ms']
                    track_data['duration_ms'] += track_duration
                    if track['explicit']:
                        track_data['explicit_count'] += 1
                    
                    # Artist info and duration
                    for artist in track['artists']:
                        track_data['artists'][artist['name']] += 1
                        track_data['artist_durations'][artist['name']] += track_duration
                    
                    # Album info
                    album_name = track['album']['name']
                    track_data['albums'][album_name] += 1
                    
                    # Release year
                    release_year = track['album']['release_date'][:4]
                    track_data['release_years'][int(release_year)] += 1
                    
                    # Popularity
                    if track['popularity'] is not None:
                        track_data['popularity_data'].append(track['popularity'])
            
            status.write("Generating insights...")
            
            # Calculate additional metrics
            total_tracks = len(tracks)
            total_duration_minutes = track_data['duration_ms'] / (1000 * 60)
            hours = int(total_duration_minutes // 60)
            minutes = int(total_duration_minutes % 60)
            
            avg_popularity = sum(track_data['popularity_data']) / len(track_data['popularity_data']) if track_data['popularity_data'] else 0
            
            # Process artist durations
            artist_durations_formatted = {}
            for artist, duration in track_data['artist_durations'].items():
                artist_minutes = duration / (1000 * 60)
                artist_hours = int(artist_minutes // 60)
                artist_mins = int(artist_minutes % 60)
                artist_durations_formatted[artist] = f"{artist_hours}h {artist_mins}m"
            
            # Create analytics dict
            analytics = {
                'total_tracks': total_tracks,
                'total_duration': f"{hours}h {minutes}m",
                'total_artists': len(track_data['artists']),
                'explicit_percentage': (track_data['explicit_count'] / total_tracks) * 100 if total_tracks > 0 else 0,
                'avg_popularity': avg_popularity,
                'top_artists': dict(track_data['artists'].most_common(10)),
                'artist_durations': artist_durations_formatted,
                'top_albums': dict(track_data['albums'].most_common(10)),
                'release_years': dict(sorted(track_data['release_years'].items())),
                'decade_distribution': get_decade_distribution(track_data['release_years'])
            }
            
            status.update(label="Analysis complete!", state="complete")
            return analytics
            
    except Exception as e:
        st.error(f"Error analyzing playlist: {str(e)}")
        return {
            'total_tracks': 0,
            'total_duration': "0h 0m",
            'total_artists': 0,
            'explicit_percentage': 0,
            'avg_popularity': 0,
            'top_artists': {},
            'artist_durations': {},
            'top_albums': {},
            'release_years': {},
            'decade_distribution': {}
        }

def get_decade_distribution(release_years):
    """Calculate distribution of tracks by decade."""
    decades = Counter()
    for year, count in release_years.items():
        decade = (year // 10) * 10
        decades[f"{decade}s"] += count
    return dict(sorted(decades.items()))

def display_playlist_analytics(sp, playlist_id):
    """Display enhanced analytics visualizations for a playlist."""
    with st.spinner("Loading analytics..."):
        analytics = get_playlist_analytics(sp, playlist_id)
    
    # Create a container for analytics
    analytics_container = st.container()
    
    with analytics_container:
        # Basic stats in a table
        st.subheader("📊 Playlist Overview")
        overview_data = {
            "Metric": ["Total Tracks", "Total Duration", "Total Artists", "Explicit Content"],
            "Value": [
                analytics['total_tracks'],
                analytics['total_duration'],
                analytics['total_artists'],
                f"{analytics['explicit_percentage']:.1f}%"
            ]
        }
        st.table(pd.DataFrame(overview_data))
        
        # Create tabs for different analytics sections
        tab1, tab2, tab3 = st.tabs(["👥 Artist Statistics", "💿 Album Statistics", "📈 Timeline Statistics"])
        
        with tab1:
            st.subheader("Artist Statistics")
            
            # Artist track counts and durations
            artist_data = []
            for artist in analytics['top_artists'].keys():
                artist_data.append({
                    "Artist": artist,
                    "Track Count": analytics['top_artists'][artist],
                    "Total Duration": analytics['artist_durations'].get(artist, "0h 0m")
                })
            
            st.markdown("**Artist Contribution Details**")
            st.table(pd.DataFrame(artist_data))
        
        with tab2:
            st.subheader("Album Statistics")
            
            # Album track counts
            album_data = []
            for album, count in analytics['top_albums'].items():
                album_data.append({
                    "Album": album,
                    "Track Count": count
                })
            
            st.markdown("**Album Track Distribution**")
            st.table(pd.DataFrame(album_data))
        
        with tab3:
            st.subheader("Timeline Statistics")
            
            # Decade distribution
            st.markdown("**Tracks by Decade**")
            decade_data = []
            for decade, count in analytics['decade_distribution'].items():
                decade_data.append({
                    "Decade": decade,
                    "Track Count": count
                })
            st.table(pd.DataFrame(decade_data))
            
            # Year distribution
            st.markdown("**Tracks by Year**")
            year_data = []
            for year, count in analytics['release_years'].items():
                year_data.append({
                    "Year": year,
                    "Track Count": count
                })
            st.table(pd.DataFrame(year_data))

def enhanced_track_search(sp, track_name, filters=None):
    """Enhanced track search with filters."""
    if filters is None:
        filters = {}
    
    # Build search query
    query = track_name
    if 'year' in filters:
        query += f" year:{filters['year']}"
    
    # Initial search
    results = sp.search(q=query, limit=50, type="track")
    tracks = results["tracks"]["items"]
    
    # Apply additional filters
    if 'min_popularity' in filters:
        tracks = [t for t in tracks if t['popularity'] >= filters['min_popularity']]
    
    if 'genre' in filters:
        filtered_tracks = []
        for track in tracks:
            artist_id = track['artists'][0]['id']
            artist = sp.artist(artist_id)
            if filters['genre'].lower() in [g.lower() for g in artist['genres']]:
                filtered_tracks.append(track)
        tracks = filtered_tracks
    
    return tracks

def show_enhanced_track_search(sp):
    st.subheader("🔍 Enhanced Track Search")
    
    # Search filters
    with st.expander("Search Filters"):
        col1, col2, col3 = st.columns(3)
        with col1:
            year = st.number_input("Release Year", min_value=1900, max_value=datetime.now().year, value=2020)
        with col2:
            min_popularity = st.slider("Minimum Popularity", 0, 100, 0)
        with col3:
            genre = st.text_input("Genre")
    
    track_name = st.text_input("Enter track name", key="enhanced_track_search")
    
    if track_name:
        filters = {
            'year': year if year != 2020 else None,
            'min_popularity': min_popularity if min_popularity > 0 else None,
            'genre': genre if genre else None
        }
        filters = {k: v for k, v in filters.items() if v is not None}
        
        with st.spinner("Searching for tracks..."):
            tracks = enhanced_track_search(sp, track_name, filters)
        
        if tracks:
            show_notification(f"Found {len(tracks)} tracks matching your criteria!", "info")
            for track in tracks:
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.markdown(f"**{track['name']}** - *{', '.join([artist['name'] for artist in track['artists']])}*")
                    with col2:
                        st.markdown(f"Popularity: {track['popularity']}")
                    with col3:
                        if st.button("Add", key=f"track_{track['id']}"):
                            track_info = {
                                'name': track['name'],
                                'id': track['id'],
                                'artists': ', '.join([artist['name'] for artist in track['artists']])
                            }
                            if track_info not in st.session_state.selected_tracks:
                                st.session_state.selected_tracks.append(track_info)
                                show_notification(f"Added {track['name']} to selection", "success")
        else:
            show_notification("No tracks found matching your criteria.", "warning")

def export_playlist_to_file(sp, playlist_id, format="csv"):
    """Export playlist tracks to a file."""
    results = sp.playlist_tracks(playlist_id)
    tracks = []
    
    for item in results['items']:
        if item['track']:
            track = item['track']
            track_info = {
                'name': track['name'],
                'artists': ', '.join([artist['name'] for artist in track['artists']]),
                'album': track['album']['name'],
                'id': track['id'],
                'duration_ms': track['duration_ms'],
                'popularity': track.get('popularity', 0)
            }
            tracks.append(track_info)
    
    df = pd.DataFrame(tracks)
    
    if format == "csv":
        return df.to_csv(index=False).encode('utf-8')
    else:
        return df.to_json(orient='records')

def import_playlist_from_file(sp, file, playlist_name=None):
    """Import tracks from a file into a new playlist."""
    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_json(file)
        
        track_ids = df['id'].tolist()
        if not playlist_name:
            playlist_name = f"Imported Playlist - {datetime.now().strftime('%B %d, %Y')}"
        
        # Create new playlist
        user_id = sp.current_user()["id"]
        playlist = sp.user_playlist_create(user_id, playlist_name, public=False)
        
        # Add tracks in batches
        for i in range(0, len(track_ids), 100):
            batch = track_ids[i:i+100]
            sp.playlist_add_items(playlist["id"], batch)
        
        return True, f"Successfully imported {len(track_ids)} tracks to playlist '{playlist_name}'"
    except Exception as e:
        return False, f"Error importing playlist: {str(e)}"

def sort_playlists(playlists, sort_by="name", reverse=False):
    """Sort playlists by different criteria."""
    if sort_by == "name":
        return sorted(playlists, key=lambda x: x['name'].lower(), reverse=reverse)
    elif sort_by == "tracks":
        return sorted(playlists, key=lambda x: x['tracks']['total'], reverse=reverse)
    elif sort_by == "owner":
        return sorted(playlists, key=lambda x: x['owner']['display_name'].lower(), reverse=reverse)
    return playlists

def filter_playlists(playlists, filter_text):
    """Filter playlists by name or owner."""
    if not filter_text:
        return playlists
    filter_text = filter_text.lower()
    return [p for p in playlists if 
            filter_text in p['name'].lower() or 
            filter_text in p['owner']['display_name'].lower()]

def show_playlist_manager(sp):
    st.title("Playlist Manager")
    
    # Enable dark mode toggle
    st.sidebar.markdown("### Theme Settings")
    if st.sidebar.checkbox("Dark Mode"):
        st.markdown("""
            <style>
                .stApp {
                    background-color: #1E1E1E;
                    color: #FFFFFF;
                }
            </style>
        """, unsafe_allow_html=True)
    
    # Add Import Playlist section
    st.sidebar.markdown("### Import Playlist")
    uploaded_file = st.sidebar.file_uploader("Upload playlist file", type=['csv', 'json'])
    if uploaded_file:
        import_name = st.sidebar.text_input("Playlist Name (optional)")
        if st.sidebar.button("Import Playlist"):
            success, message = import_playlist_from_file(sp, uploaded_file, import_name)
            if success:
                show_notification(message, "success")
            else:
                show_notification(message, "error")
    
    # Add sorting and filtering controls
    st.sidebar.markdown("### Playlist Controls")
    sort_by = st.sidebar.selectbox("Sort by", ["Name", "Tracks", "Owner"], key="sort_by")
    sort_order = st.sidebar.radio("Sort order", ["Ascending", "Descending"], key="sort_order")
    filter_text = st.sidebar.text_input("Filter playlists", key="filter_text")
    
    with st.spinner("Loading playlists..."):
        playlists = get_user_playlists(sp)
        user_id = sp.current_user()["id"]
    
    owned_playlists = [p for p in playlists if p['owner']['id'] == user_id]
    followed_playlists = [p for p in playlists if p['owner']['id'] != user_id]
    
    # Apply sorting and filtering
    owned_playlists = sort_playlists(
        filter_playlists(owned_playlists, filter_text),
        sort_by.lower(),
        sort_order == "Descending"
    )
    followed_playlists = sort_playlists(
        filter_playlists(followed_playlists, filter_text),
        sort_by.lower(),
        sort_order == "Descending"
    )
    
    # Display playlist counts
    st.markdown(f"### Your Playlists ({len(owned_playlists)})")
    if owned_playlists:
        for playlist in owned_playlists:
            playlist_container = st.container()
            with playlist_container:
                st.markdown(f"📝 **{playlist['name']}** ({playlist['tracks']['total']} tracks)")
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    if st.button("View Analytics", key=f"analytics_{playlist['id']}"):
                        display_playlist_analytics(sp, playlist['id'])
                with col2:
                    export_format = st.selectbox("Format", ["CSV", "JSON"], key=f"format_{playlist['id']}")
                    if st.button("Export", key=f"export_{playlist['id']}"):
                        file_data = export_playlist_to_file(sp, playlist['id'], export_format.lower())
                        st.download_button(
                            label="Download",
                            data=file_data,
                            file_name=f"{playlist['name']}.{export_format.lower()}",
                            mime="text/csv" if export_format == "CSV" else "application/json"
                        )
                with col3:
                    if st.button("Delete", key=f"delete_{playlist['id']}"):
                        results = delete_playlists(sp, [playlist['id']])
                        handle_spotify_operation_result(results)
                st.markdown("---")  # Add a separator between playlists
    
    st.markdown(f"### Followed Playlists ({len(followed_playlists)})")
    if followed_playlists:
        for playlist in followed_playlists:
            playlist_container = st.container()
            with playlist_container:
                st.markdown(f"👥 **{playlist['name']}** ({playlist['tracks']['total']} tracks)")
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    if st.button("View Analytics", key=f"analytics_followed_{playlist['id']}"):
                        display_playlist_analytics(sp, playlist['id'])
                with col2:
                    export_format = st.selectbox("Format", ["CSV", "JSON"], key=f"format_followed_{playlist['id']}")
                    if st.button("Export", key=f"export_followed_{playlist['id']}"):
                        file_data = export_playlist_to_file(sp, playlist['id'], export_format.lower())
                        st.download_button(
                            label="Download",
                            data=file_data,
                            file_name=f"{playlist['name']}.{export_format.lower()}",
                            mime="text/csv" if export_format == "CSV" else "application/json"
                        )
                with col3:
                    if st.button("Unfollow", key=f"unfollow_{playlist['id']}"):
                        results = delete_playlists(sp, [playlist['id']])
                        handle_spotify_operation_result(results)
                st.markdown("---")  # Add a separator between playlists

def main():
    st.set_page_config(
        page_title="Spotify Playlist Manager",
        page_icon="🎵",
        layout="wide",
        menu_items={
            'Get Help': 'https://github.com/yourusername/spotify-playlist-manager',
            'Report a bug': "https://github.com/yourusername/spotify-playlist-manager/issues",
            'About': "# Spotify Playlist Manager\nA powerful tool to manage your Spotify playlists."
        }
    )
    
    initialize_session_state()
    
    # Add keyboard shortcuts
    st.sidebar.markdown("### Settings")
    st.session_state.keyboard_shortcuts = st.sidebar.checkbox(
        "Enable Keyboard Shortcuts",
        value=st.session_state.keyboard_shortcuts
    )
    
    if st.session_state.keyboard_shortcuts:
        st.sidebar.markdown("""
        ### Keyboard Shortcuts
        - `Ctrl/⌘ + S`: Save playlist
        - `Ctrl/⌘ + F`: Search
        - `Ctrl/⌘ + D`: Delete selected
        - `Ctrl/⌘ + E`: Export playlist
        """)
    
    # Auto-refresh for real-time updates
    st_autorefresh(interval=5 * 60 * 1000)  # Refresh every 5 minutes
    
    try:
        sp = get_spotify_client()
    except Exception as e:
        st.error(f"Error connecting to Spotify: {str(e)}")
        return
    
    # Sidebar navigation with icons
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("", [
        "🎵 Playlist Generator",
        "📝 Playlist Manager",
        "🔍 Enhanced Search"
    ])
    
    if "Playlist Generator" in page:
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
    
    elif "Enhanced Search" in page:
        st.title("Enhanced Search")
        show_enhanced_track_search(sp)
    
    else:
        show_playlist_manager(sp)

if __name__ == "__main__":
    main()