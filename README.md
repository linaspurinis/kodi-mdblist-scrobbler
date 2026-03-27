# MDBList Scrobbler for Kodi

This addon for Kodi sends scrobble events for movies and episodes to the MDBList API using JSON POST requests. It also supports prompting you to rate content after watching and saving those ratings to Kodi and/or MDBList.

## Installation

Download this repository as a zip archive and install it in Kodi using "Install from zip file" in the add-on browser (Settings > Addons). NOTE requires "Enable Unknown Sources" to be enabled first.

After that, configure the MDBList API URL and API key in the addon settings.

## Scrobble requests

The addon sends HTTP POST requests containing a JSON payload.

A request is sent once the playback starts, pauses, resumes or stops.

Additionally to that, it's also possible to regularly send the current progress while playing movies or episodes (i.e. not paused). This feature can be configured on the "Interval" page in the addon settings.

Events are mapped to MDBList endpoints as follows:

| Event    | MDBList endpoint  |
|----------|-------------------|
| start    | /scrobble/start   |
| pause    | /scrobble/pause   |
| resume   | /scrobble/start   |
| stop     | /scrobble/stop    |
| end      | /scrobble/stop    |
| seek     | /scrobble/start   |
| interval | /scrobble/start   |

Each event can be enabled or disabled individually in the addon settings.

### Playback progress reporting

The `progress` property is especially useful in combination with the `interval` event as it contains the current playback progress. But the progress is also included in other events like `pause`, `seek` or `stop`.

Progress is sent as a percentage (0-100) in the `progress` field.

### Payload structure

The following examples provide the usual structure which will be used for sending the data to MDBList.

**Movies**

```json
{
  "movie": {
    "ids": {
    "imdb": "tt0088763"
    }
  },
  "progress": 0.0
}
```

**Episodes**

```json
{
  "show": {
    "ids": {
      "tvdb": "75897"
    },
    "season": {
      "number": 20,
      "episode": {
        "number": 1
      }
    }
  },
  "progress": 0.0
}
```

## Rating prompt

After finishing or stopping playback, the addon can prompt you to rate the movie or episode on a scale of 1–10.

### Configuration

All rating options are available in the addon settings under the "Rating" section:

| Setting | Description |
|---------|-------------|
| Enable rating prompt | Master toggle for the rating feature |
| Prompt on playback end | Show prompt when playback finishes naturally |
| Prompt on playback stop | Show prompt when playback is manually stopped |
| Prompt for movies | Enable rating prompt for movies |
| Prompt for episodes | Enable rating prompt for episodes |
| Only prompt if unrated | Skip prompt if the item already has a user rating in Kodi |
| Minimum progress (%) | Only prompt if playback reached this percentage (e.g. 80 to skip if you barely watched) |
| Save rating to Kodi | Write the rating back to the Kodi library as a user rating |
| Save rating to MDBList | Send the rating to MDBList via `/sync/ratings` |

### How it works

When playback ends or stops, a selection dialog appears with the title of the movie or episode and choices from 1 to 10 (plus Skip). Selecting a number saves the rating to the configured destinations and shows a confirmation notification. The prompt is shown at most once per playback session.

Ratings are sent to MDBList using the following payload structure:

**Movies**

```json
{
  "movies": [
    {
      "ids": { "imdb": "tt0088763" },
      "rating": 8
    }
  ]
}
```

**Episodes**

```json
{
  "shows": [
    {
      "ids": { "tvdb": "75897" },
      "seasons": [
        {
          "number": 1,
          "episodes": [
            { "number": 3, "rating": 7 }
          ]
        }
      ]
    }
  ]
}
```

### Supported IDs

The addon resolves media identifiers using the following ID types:

| Media type | Supported IDs |
|------------|---------------|
| Movies | imdb, tmdb, trakt, kitsu, mdblist |
| Episodes | imdb, tmdb, trakt, tvdb, mdblist |

Common Kodi aliases (e.g. `imdbnumber`, `themoviedb`, `tvdb_id`) are automatically mapped to their canonical forms.
