
# Spotify Playlist Manager

This Streamlit application allows users to generate and manage Spotify playlists.  It provides functionality to search for artists, albums, and tracks, select songs, and create custom playlists.  Additionally, it offers playlist management features, enabling users to view, delete, and unfollow playlists.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [Configuration](#configuration)
- [Code Overview](#code-overview)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Search:** Search for artists, albums, and tracks using the Spotify API.
- **Playlist Generation:** Create new playlists with selected tracks, specifying the number of times each track should appear.  The app uses an interleaving algorithm to distribute track repetitions evenly.
- **Playlist Management:** View, delete owned playlists, and unfollow followed playlists.
- **User Interface:**  Built using Streamlit for an interactive and user-friendly experience.
- **Authentication:** Securely authenticates with Spotify using OAuth2.
- **Track Matching:** Uses fuzzy matching (difflib) to improve track search accuracy, especially when track names are slightly misspelled or contain extra information.

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Srikanth1905/Spotify-Playlist-Creator-and-Manager-using-Python.git  
cd spotify-playlist-manager
````

2.  Create a virtual environment (recommended):

<!-- end list -->

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3.  Install the required packages:

<!-- end list -->

```bash
pip install -r requirements.txt
```

4.  Create a `.env` file in the project directory and add your Spotify API credentials (see Configuration).

## Usage

1.  Run the Streamlit app:

<!-- end list -->

```bash
streamlit run app.py
```

2.  Open the app in your web browser (usually at `http://localhost:8501`).

3.  Authorize the app to access your Spotify account.

4.  Use the sidebar to navigate between "Playlist Generator" and "Playlist Manager."

### Playlist Generator

  - Search for artists, albums, or tracks.
  - Select tracks to add to your playlist.
  - Specify the number of times each track should be included.
  - Create a new playlist with a custom name.

### Playlist Manager

  - View your owned and followed playlists.
  - Select playlists to delete or unfollow.

## Project Structure

```
spotify-playlist-manager/
├── app.py          # Main Streamlit application
├── requirements.txt # Project dependencies
├── .env            # Environment variables (Spotify API credentials)
└── .spotifycache   # Cache file for Spotify OAuth (automatically created)
```

## Dependencies

  - `streamlit`: For creating the interactive web app.
  - `spotipy`: For interacting with the Spotify API.
  - `pandas`: For data manipulation (although not heavily used in this version, it's good practice to include it for potential future enhancements).
  - `python-dotenv`: For loading environment variables from the `.env` file.
  - `difflib`: For fuzzy string matching to find the best matching tracks.

## Configuration

1.  Create a Spotify Developer app:  Go to [https://developer.spotify.com/dashboard/applications](https://www.google.com/url?sa=E&source=gmail&q=https://developer.spotify.com/dashboard/applications) and create a new app.

2.  Obtain your `CLIENT_ID` and `CLIENT_SECRET`.

3.  Set the `REDIRECT_URI` to `http://localhost:8888/callback`.  This must match the redirect URI you set in your Spotify Developer app settings.

4.  Create a `.env` file in the project directory and add the following:

<!-- end list -->

```
CLIENT_ID=<your_client_id>
CLIENT_SECRET=<your_client_secret>
```

## Code Overview

The `app.py` file contains the core logic of the application.  Key functions include:

  - `get_spotify_client()`: Creates and caches a Spotipy client instance.
  - `search_artists()`, `get_artist_albums()`, `get_album_tracks()`: Functions to search for and retrieve data from the Spotify API.
  - `clean_song_name()`: Cleans track names for improved matching.
  - `find_best_match()`: Uses `difflib.SequenceMatcher` to find the best matching track from search results.
  - `create_playlist_from_tracks()`: Creates a new playlist and adds tracks, handling track repetitions and using an interleaving algorithm.
  - `get_user_playlists()`, `delete_playlists()`: Functions for playlist management.
  - `show_artist_search()`, `show_album_search()`, `show_track_search()`: Streamlit functions to display search interfaces.
  - `show_album_tracks()`: Streamlit function to display tracks from a selected album.
  - `show_playlist_creation()`: Streamlit function to display selected tracks and create a playlist.
  - `show_playlist_manager()`: Streamlit function to display and manage user playlists.
  - `main()`: Main function to initialize the app and handle navigation.

## Contributing

Contributions are welcome\! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

