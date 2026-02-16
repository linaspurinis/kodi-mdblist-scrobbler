import requests
import xbmc
import xbmcaddon

from resources.lib.timer import Timer
from resources.lib.utils import jsonrpc_request, fix_unique_ids


REQUEST_TIMEOUT_SECONDS = 10


class PlayerMonitor(xbmc.Player):
    def __init__(self):
        super().__init__()

        self.settings = None
        self.interval_timer = None

        self.total_time = None
        self.current_time = None

        self.video_info = {}

        self.load_settings()

    def show_message(self, message: str):
        jsonrpc_request("GUI.ShowNotification", {"title": "MDBList Scrobbler", "message": message})

    def load_settings(self):
        self.settings = xbmcaddon.Addon().getSettings()

    def build_payload(self, event: str):
        if not self.video_info:
            return None

        media_type = self.video_info.get("type")

        try:
            if not self.settings.getBool("mediatype.{}".format(media_type)):
                return None
        except TypeError:
            return None

        total_time = self.getTotalTime() if self.isPlaying() else self.total_time
        current_time = self.getTime() if self.isPlaying() else self.current_time

        if total_time is not None:
            if total_time < 0:
                total_time = 0
            else:
                total_time = int(total_time)

        if current_time is not None:
            if current_time < 0:
                current_time = 0
            else:
                current_time = int(current_time)

        if total_time and current_time is not None:
            progress_percent = round((current_time / total_time) * 100, 2)
        else:
            xbmc.log(
                "MDBList Scrobbler: Skipping {} event due to missing/invalid playback time (total={}, current={})".format(
                    event, total_time, current_time
                ),
                level=xbmc.LOGDEBUG,
            )
            return None

        if media_type == "episode":
            show_ids = fix_unique_ids(self.video_info.get("tvshow", {}).get("uniqueid", {}), media_type)
            if not show_ids:
                xbmc.log("MDBList Scrobbler: Skipping episode scrobble, no supported show IDs found", level=xbmc.LOGWARNING)
                return None

            return {
                "show": {
                    "ids": show_ids,
                    "season": {
                        "number": self.video_info.get("season"),
                        "episode": {
                            "number": self.video_info.get("episode")
                        }
                    }
                },
                "progress": progress_percent,
                "app_version": xbmcaddon.Addon().getAddonInfo("version")
            }

        if media_type == "movie":
            movie_ids = fix_unique_ids(self.video_info.get("uniqueid", {}), media_type)
            if not movie_ids:
                xbmc.log("MDBList Scrobbler: Skipping movie scrobble, no supported movie IDs found", level=xbmc.LOGWARNING)
                return None

            return {
                "movie": {
                    "ids": movie_ids
                },
                "progress": progress_percent,
                "app_version": xbmcaddon.Addon().getAddonInfo("version")
            }

        return None

    def send_request(self, event: str):
        if not self.settings.getBool("event.{}".format(event)):
            return

        json_data = self.build_payload(event)
        if not json_data:
            return

        base_url = self.settings.getString("url")
        if not base_url:
            xbmc.log("MDBList API URL not configured!", level=xbmc.LOGERROR)
            self.show_message("MDBList API URL not configured!")
            return

        apikey = self.settings.getString("apikey")
        if not apikey:
            xbmc.log("MDBList API key not configured!", level=xbmc.LOGERROR)
            self.show_message("MDBList API key not configured!")
            return

        endpoint = self.event_to_endpoint(event)
        if not endpoint:
            return

        if base_url.endswith("/"):
            base_url = base_url[:-1]

        url = "{}{}?apikey={}".format(base_url, endpoint, apikey)

        try:
            response = requests.post(url, json=json_data, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code >= 400:
                response_snippet = response.text[:200]
                xbmc.log(
                    "MDBList Scrobbler: API error {} on {} payload={} response={}".format(
                        response.status_code, endpoint, json_data, response_snippet
                    ),
                    level=xbmc.LOGERROR,
                )
                self.show_message("API Error {}: {}".format(response.status_code, response.text[:50]))
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            pass  # Already logged above
        except requests.exceptions.RequestException as exception:
            xbmc.log("MDBList Scrobbler: Request failed - {}".format(str(exception)), level=xbmc.LOGERROR)
            self.show_message("Request failed: {}".format(str(exception)[:50]))
        except Exception as exception:
            xbmc.log("MDBList Scrobbler: Unexpected failure - {}".format(str(exception)), level=xbmc.LOGERROR)
            self.show_message("Request failed: {}".format(str(exception)[:50]))

    def event_to_endpoint(self, event: str):
        if event in ["start", "resume", "seek", "interval"]:
            return "/scrobble/start"
        if event == "pause":
            return "/scrobble/pause"
        if event in ["stop", "end"]:
            return "/scrobble/stop"
        return None

    def fetch_video_info(self):
        try:
            self.video_info = jsonrpc_request("Player.GetItem", {"playerid": 1, "properties": ["tvshowid", "showtitle", "season", "episode", "firstaired", "premiered", "year", "uniqueid"]}).get("item")
        except:
            self.video_info = None

        if not self.video_info:
            return

        if self.video_info.get("type") == "episode":
            self.video_info["tvshow"] = jsonrpc_request("VideoLibrary.GetTVShowDetails", {"tvshowid": self.video_info.get("tvshowid"), "properties": ["uniqueid"]}).get("tvshowdetails")

    def start_interval_timer(self):
        self.interval_timer = Timer(self.settings.getInt("interval"), self.onInterval)
        self.interval_timer.start()

    def stop_interval_timer(self):
        if not self.interval_timer or not self.interval_timer.is_alive():
            return

        self.interval_timer.stop()

    def update_time(self):
        if self.isPlaying():
            self.total_time = self.getTotalTime()
            self.current_time = self.getTime()

    def onAVStarted(self):
        self.fetch_video_info()
        self.update_time()

        self.send_request("start")
        self.start_interval_timer()

    def onPlayBackPaused(self):
        if not self.video_info:
            return

        self.update_time()
        self.send_request("pause")
        self.stop_interval_timer()

    def onPlayBackResumed(self):
        if not self.video_info:
            return

        self.send_request("resume")
        self.start_interval_timer()

    def onPlayBackStopped(self):
        if not self.video_info:
            return

        self.send_request("stop")
        self.stop_interval_timer()

    def onPlayBackEnded(self):
        if not self.video_info:
            return

        self.send_request("end")
        self.stop_interval_timer()

    def onPlayBackSeek(self, time: int, seekOffset: int):
        if not self.video_info:
            return

        self.update_time()
        self.send_request("seek")

    def onPlayBackSeekChapter(self, chapter: int):
        if not self.video_info:
            return

        self.update_time()
        self.send_request("seek")

    def onInterval(self):
        if not self.video_info:
            return

        self.update_time()
        self.send_request("interval")
