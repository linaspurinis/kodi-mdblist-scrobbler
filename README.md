# MDBList Scrobbler for Kodi

This addon for Kodi sends scrobble events for movies and episodes to the MDBList API using JSON POST requests.

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
