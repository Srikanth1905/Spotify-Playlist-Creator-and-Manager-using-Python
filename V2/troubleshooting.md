# Troubleshooting Guide for Spotify Playlist Manager

## Current Issues and Solutions

### 1. Custom Notification Box Error
**Error:**
```
TypeError: custom_notification_box() got an unexpected keyword argument 'iconDisplay'
```

**Cause:**
The `streamlit-custom-notification-box` package is causing compatibility issues with different versions.

**Solution:**
Replaced the custom notification box with a native Streamlit markdown solution:
```python
def show_notification(message, type="info"):
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
```

### 2. Spotify API Authorization Error
**Error:**
```
spotipy.exceptions.SpotifyException: http status: 403, code:-1
```

**Cause:**
This error occurs due to one of these reasons:
1. Invalid or expired access token
2. Insufficient permissions in the Spotify API scope
3. Rate limiting from the Spotify API

**Solution:**
1. Update the SCOPE variable to include all necessary permissions:
```python
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
```

2. Implement rate limiting and error handling:
```python
def get_playlist_analytics(sp, playlist_id):
    try:
        results = sp.playlist_tracks(playlist_id)
        tracks = results['items']
        
        # Process in smaller batches to avoid rate limits
        track_ids = []
        for item in tracks:
            if item['track']:
                track_ids.append(item['track']['id'])
        
        # Process audio features in batches of 50
        audio_features = []
        for i in range(0, len(track_ids), 50):
            batch = track_ids[i:i+50]
            try:
                features = sp.audio_features(batch)
                if features:
                    audio_features.extend(features)
                time.sleep(0.1)  # Add small delay between batches
            except Exception as e:
                st.warning(f"Could not fetch audio features for some tracks: {str(e)}")
                continue
        
        # Rest of the function...
    except Exception as e:
        st.error(f"Error analyzing playlist: {str(e)}")
        return None
```

### 3. Spotify API Rate Limiting Error
**Error:**
```
Could not fetch audio features for some tracks: http status: 403, code:-1
```

**Cause:**
This error occurs due to Spotify API rate limiting when:
1. Too many requests are made in a short time
2. Batch size is too large
3. Not enough delay between requests

**Solution:**
1. Reduced batch size from 50 to 20 tracks
2. Increased delay between requests from 0.1s to 0.25s
3. Added progress indicator
4. Improved error handling:

```python
def get_playlist_analytics(sp, playlist_id):
    # ... existing code ...
    
    # Process in smaller batches with longer delays
    for i in range(0, len(track_ids), 20):
        batch = track_ids[i:i+20]
        try:
            time.sleep(0.25)  # Longer delay
            features = sp.audio_features(batch)
            if features:
                valid_features = [f for f in features if f is not None]
                audio_features.extend(valid_features)
        except Exception as e:
            st.warning(f"Could not fetch audio features: {str(e)}")
            continue
        
        # Show progress
        progress = (i + len(batch)) / len(track_ids)
        st.progress(progress, text=f"Analyzing tracks... {int(progress * 100)}%")
```

## Best Practices for API Usage

### 1. Rate Limiting
- Keep batch sizes small (20 or fewer items)
- Add delays between requests (0.25s minimum)
- Implement exponential backoff for retries
- Show progress to users during long operations

### 2. Error Handling
- Catch and handle specific exceptions
- Provide meaningful error messages
- Gracefully degrade functionality when errors occur
- Return empty/default values instead of None

### 3. Performance Optimization
- Cache frequently accessed data
- Process data in smaller batches
- Show progress indicators for long operations
- Implement request queuing for large datasets

## Setup Instructions

1. **Remove Dependencies:**
```bash
pip uninstall streamlit-custom-notification-box
```

2. **Update Required Packages:**
```bash
pip install spotipy==2.23.0
pip install streamlit==1.31.0
pip install plotly==5.18.0
pip install pandas==2.2.0
```

3. **Environment Setup:**
```bash
# Create a .env file with:
CLIENT_ID=your_spotify_client_id
CLIENT_SECRET=your_spotify_client_secret
REDIRECT_URI=http://127.0.0.1:8888/callback
```

4. **Cache Management:**
- Delete `.spotifycache` file if authentication issues occur
- Clear browser cache if UI issues persist
- Restart the application after making changes

## Common Issues and Solutions

### 1. API Rate Limiting
**Symptoms:**
- 403 errors
- Failed requests
- Missing data

**Solutions:**
- Reduce batch sizes
- Increase delays between requests
- Implement request queuing
- Show progress indicators

### 2. Authentication Issues
**Symptoms:**
- 401 errors
- Failed login
- Token expiration

**Solutions:**
- Delete `.spotifycache`
- Re-authenticate
- Check API credentials
- Verify scope permissions

### 3. UI/Display Issues
**Symptoms:**
- Missing notifications
- Layout problems
- Style inconsistencies

**Solutions:**
- Use native Streamlit components
- Clear browser cache
- Check Streamlit version
- Verify HTML/CSS compatibility

## Debugging Tips

1. **API Issues:**
- Enable debug logging
- Monitor rate limits
- Check response headers
- Verify request parameters

2. **Performance:**
- Profile API calls
- Monitor memory usage
- Check response times
- Optimize batch sizes

3. **User Experience:**
- Add progress indicators
- Provide clear error messages
- Implement graceful degradation
- Cache when possible

## Common Issues and Solutions

### 1. Analytics Performance Issues

#### Symptoms
- Slow loading of playlist analytics
- Timeouts when fetching analytics
- API rate limit errors

#### Solutions
- Analytics have been optimized to use local processing instead of multiple API calls
- Progress indicators and status updates show the analysis progress
- Data is now processed in a single batch with visual feedback
- No more genre or audio feature API calls that could cause rate limiting

### 2. Spotify API Authorization Issues

#### Symptoms
- 403 Forbidden errors
- Authentication failures
- Token expiration issues

#### Solutions
- Ensure all required scopes are included in the `SCOPE` variable
- Clear the `.spotifycache` file if you encounter authentication issues
- Restart the application after clearing the cache
- The application will automatically refresh tokens when needed

### 3. UI/Display Issues

#### Symptoms
- Charts not rendering properly
- Layout issues
- Visualization problems

#### Solutions
- Charts now use consistent styling and Spotify's brand color (#1DB954)
- Improved layout with two-column design for better space utilization
- Added proper margins and padding for better visual hierarchy
- Progress bars and status indicators provide better feedback

### 4. Performance Optimization

#### Best Practices
- Analytics are now processed locally to reduce API calls
- Data is processed in a single pass through the tracks
- Visual feedback shows progress during analysis
- Efficient data structures (Counter) are used for statistics

### 5. Error Recovery

If you encounter any errors:
1. Check your internet connection
2. Verify your Spotify credentials
3. Clear the `.spotifycache` file
4. Restart the application
5. Check the error message in the status indicator

## Setup Instructions

1. Install required packages:
```bash
pip install streamlit pandas plotly spotipy python-dotenv streamlit-autorefresh
```

2. Create a `.env` file with your Spotify credentials:
```
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
```

3. Ensure proper permissions in your Spotify Developer Dashboard

## Common Error Messages and Solutions

### "Error analyzing playlist"
- **Cause**: Usually occurs when there's an issue accessing playlist data
- **Solution**: 
  - Check playlist accessibility
  - Verify your Spotify premium status
  - Ensure stable internet connection

### "No tracks found"
- **Cause**: Empty playlist or access issues
- **Solution**:
  - Verify playlist contains tracks
  - Check playlist privacy settings
  - Refresh the page

## Additional Tips

1. **Performance**
   - Analytics now process faster with local calculations
   - Progress bars show real-time analysis status
   - Status messages indicate current operation

2. **Visualization**
   - Charts are now more responsive
   - Better use of screen space with two-column layout
   - Consistent styling across all visualizations

3. **Error Handling**
   - Clear error messages
   - Graceful fallbacks for missing data
   - Status indicators for all operations

4. **Data Processing**
   - Efficient single-pass analysis
   - Local processing to reduce API calls
   - Better memory management

## Getting Help

If you continue to experience issues:
1. Check this troubleshooting guide
2. Review the error messages
3. Verify your setup
4. Contact support with specific error details

## Recent Fixes

### 1. Empty Label Warning
**Error:**
```
`label` got an empty value. This is discouraged for accessibility reasons.
```

**Cause:**
Metrics and other UI components were missing proper labels or help text, which could cause accessibility issues.

**Solution:**
- Added explicit labels and help text to all metrics:
```python
st.metric(
    label="Total Tracks",
    value=analytics['total_tracks'],
    help="Total number of tracks in the playlist"
)
```
- Updated all UI components to include descriptive labels
- Added help text for better accessibility
- Ensured all visualizations have proper titles and descriptions

### 2. Analytics Display Improvements
**Changes:**
- Duration now displays in hours and minutes format (e.g., "2h 45m")
- Added new metrics:
  - Total unique artists count
  - Duration per artist
  - Track count per artist
- Removed preview availability percentage (no longer needed)
- Reorganized tabs for better data presentation:
  1. Artist Analysis
  2. Album Analysis
  3. Timeline Analysis
- Added help text to all metrics for better accessibility

### 3. UI Organization
**Changes:**
- Separated artist and album analysis into distinct tabs
- Added artist contributions section showing duration per artist
- Improved insights section with more relevant information
- Enhanced visualization titles and descriptions
- Better spacing and layout in analytics display

## Setup Instructions

1. Install required packages:
```bash
pip install streamlit pandas plotly spotipy python-dotenv streamlit-autorefresh
```

2. Create a `.env` file with your Spotify credentials:
```
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
```

3. Ensure proper permissions in your Spotify Developer Dashboard

## Common Error Messages and Solutions

### "Error analyzing playlist"
- **Cause**: Usually occurs when there's an issue accessing playlist data
- **Solution**: 
  - Check playlist accessibility
  - Verify your Spotify premium status
  - Ensure stable internet connection

### "No tracks found"
- **Cause**: Empty playlist or access issues
- **Solution**:
  - Verify playlist contains tracks
  - Check playlist privacy settings
  - Refresh the page

## Additional Tips

1. **Performance**
   - Analytics now process faster with local calculations
   - Progress bars show real-time analysis status
   - Status messages indicate current operation

2. **Visualization**
   - Charts are now more responsive
   - Better use of screen space with two-column layout
   - Consistent styling across all visualizations

3. **Error Handling**
   - Clear error messages
   - Graceful fallbacks for missing data
   - Status indicators for all operations

4. **Data Processing**
   - Efficient single-pass analysis
   - Local processing to reduce API calls
   - Better memory management

## Getting Help

If you continue to experience issues:
1. Check this troubleshooting guide
2. Review the error messages
3. Verify your setup
4. Contact support with specific error details 