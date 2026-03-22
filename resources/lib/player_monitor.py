import requests
import xbmc
import xbmcaddon
import xbmcgui

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
        self.rating_prompt_shown = False

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
                xbmc.log("MDBList Scrobbler: Scrobbling disabled for media type '{}'".format(media_type), level=xbmc.LOGDEBUG)
                return None
        except TypeError:
            xbmc.log("MDBList Scrobbler: Unrecognised media type '{}', skipping".format(media_type), level=xbmc.LOGDEBUG)
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
                show_ids = fix_unique_ids(self.video_info.get("uniqueid", {}), media_type)
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
            xbmc.log("MDBList Scrobbler: Event '{}' disabled in settings, skipping".format(event), level=xbmc.LOGDEBUG)
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
            else:
                xbmc.log("MDBList Scrobbler: Scrobbled '{}' to {} ({})".format(event, endpoint, response.status_code), level=xbmc.LOGDEBUG)
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
            self.video_info = jsonrpc_request(
                "Player.GetItem",
                {
                    "playerid": 1,
                    "properties": [
                        "title",
                        "tvshowid",
                        "showtitle",
                        "season",
                        "episode",
                        "firstaired",
                        "premiered",
                        "year",
                        "uniqueid",
                    ],
                },
            ).get("item")
        except Exception as e:
            xbmc.log("MDBList Scrobbler: fetch_video_info failed - {}".format(e), level=xbmc.LOGERROR)
            self.video_info = None

        if not self.video_info:
            xbmc.log("MDBList Scrobbler: No video info available, scrobbling disabled for this item", level=xbmc.LOGDEBUG)
            return

        media_type = self.video_info.get("type")
        item_id = self.video_info.get("id")
        uniqueid = self.video_info.get("uniqueid", {})
        xbmc.log(
            "MDBList Scrobbler: Detected item type={} id={} uniqueid={} title={}".format(
                media_type, item_id, uniqueid,
                self.video_info.get("title") or self.video_info.get("showtitle")
            ),
            level=xbmc.LOGDEBUG,
        )

        if media_type == "episode":
            tvshowid = self.video_info.get("tvshowid")
            if tvshowid and tvshowid != -1:
                try:
                    tvshow = jsonrpc_request("VideoLibrary.GetTVShowDetails", {"tvshowid": tvshowid, "properties": ["uniqueid"]}).get("tvshowdetails")
                    self.video_info["tvshow"] = tvshow or {}
                    xbmc.log("MDBList Scrobbler: tvshow uniqueid={}".format(self.video_info["tvshow"].get("uniqueid", {})), level=xbmc.LOGDEBUG)
                except Exception as e:
                    xbmc.log("MDBList Scrobbler: Failed to fetch tvshow details - {}".format(e), level=xbmc.LOGWARNING)
                    self.video_info["tvshow"] = {}
            else:
                xbmc.log("MDBList Scrobbler: tvshowid={}, skipping library lookup, will use episode uniqueid".format(tvshowid), level=xbmc.LOGDEBUG)
                self.video_info["tvshow"] = {}

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

    def reset_playback_state(self):
        self.total_time = None
        self.current_time = None
        self.video_info = {}
        self.rating_prompt_shown = False

    def get_progress_percent(self):
        if not self.total_time or self.current_time is None:
            return None

        if self.total_time <= 0:
            return None

        current_time = min(max(int(self.current_time), 0), int(self.total_time))

        return round((current_time / int(self.total_time)) * 100, 2)

    def should_prompt_for_rating(self, playback_event: str):
        if self.rating_prompt_shown or not self.video_info:
            return False

        if not self.settings.getBool("rating.prompt.enabled"):
            return False

        if playback_event == "end":
            if not self.settings.getBool("rating.prompt.on_end"):
                return False
        elif playback_event == "stop":
            if not self.settings.getBool("rating.prompt.on_stop"):
                return False
        else:
            return False

        media_type = self.video_info.get("type")
        if media_type == "movie":
            if not self.settings.getBool("rating.prompt.movie"):
                return False
            library_id = self.video_info.get("id")
        elif media_type == "episode":
            if not self.settings.getBool("rating.prompt.episode"):
                return False
            library_id = self.video_info.get("id")
        else:
            return False

        if library_id in (None, -1):
            if not self.settings.getBool("rating.save.mdblist"):
                xbmc.log("MDBList Scrobbler: Skipping rating prompt, item is not in Kodi library and MDBList rating disabled", level=xbmc.LOGDEBUG)
                return False
            xbmc.log("MDBList Scrobbler: Item not in Kodi library, Kodi rating will be skipped but MDBList rating can proceed", level=xbmc.LOGDEBUG)

        if self.settings.getBool("rating.prompt.unrated_only"):
            media_type = self.video_info.get("type")
            try:
                if media_type == "movie":
                    details = jsonrpc_request("VideoLibrary.GetMovieDetails", {"movieid": library_id, "properties": ["userrating"]}).get("moviedetails", {})
                elif media_type == "episode":
                    details = jsonrpc_request("VideoLibrary.GetEpisodeDetails", {"episodeid": library_id, "properties": ["userrating"]}).get("episodedetails", {})
                else:
                    details = {}
                if int(details.get("userrating", 0) or 0) > 0:
                    return False
            except Exception as e:
                xbmc.log("MDBList Scrobbler: Failed to fetch userrating - {}".format(e), level=xbmc.LOGWARNING)

        progress_percent = self.get_progress_percent()
        if progress_percent is None:
            progress_percent = 100.0

        return progress_percent >= float(self.settings.getInt("rating.prompt.progress"))

    def save_kodi_rating(self, rating: int):
        if not self.settings.getBool("rating.save.kodi"):
            return False

        media_type = self.video_info.get("type")

        if media_type == "movie":
            method = "VideoLibrary.SetMovieDetails"
            params = {"movieid": self.video_info.get("id"), "userrating": rating}
        elif media_type == "episode":
            method = "VideoLibrary.SetEpisodeDetails"
            params = {"episodeid": self.video_info.get("id"), "userrating": rating}
        else:
            return False

        try:
            jsonrpc_request(method, params)
            self.video_info["userrating"] = rating
            return True
        except Exception as exception:
            xbmc.log("MDBList Scrobbler: Failed to save Kodi rating - {}".format(str(exception)), level=xbmc.LOGERROR)
            return False

    def save_mdblist_rating(self, rating: int):
        if not self.settings.getBool("rating.save.mdblist"):
            return False

        media_type = self.video_info.get("type")

        if media_type == "movie":
            movie_ids = fix_unique_ids(self.video_info.get("uniqueid", {}), "movie")
            if not movie_ids:
                xbmc.log("MDBList Scrobbler: Cannot rate movie on MDBList, no supported IDs", level=xbmc.LOGWARNING)
                return False
            payload = {"movies": [{"ids": movie_ids, "rating": rating}]}
        elif media_type == "episode":
            show_ids = fix_unique_ids(self.video_info.get("tvshow", {}).get("uniqueid", {}), "episode")
            if not show_ids:
                show_ids = fix_unique_ids(self.video_info.get("uniqueid", {}), "episode")
            if not show_ids:
                xbmc.log("MDBList Scrobbler: Cannot rate episode on MDBList, no supported show IDs", level=xbmc.LOGWARNING)
                return False
            payload = {
                "shows": [{
                    "ids": show_ids,
                    "seasons": [{
                        "number": self.video_info.get("season"),
                        "episodes": [{"number": self.video_info.get("episode"), "rating": rating}]
                    }]
                }]
            }
        else:
            return False

        base_url = self.settings.getString("url")
        apikey = self.settings.getString("apikey")

        if not base_url or not apikey:
            xbmc.log("MDBList Scrobbler: Cannot rate on MDBList, URL or API key not configured", level=xbmc.LOGERROR)
            return False

        if base_url.endswith("/"):
            base_url = base_url[:-1]

        url = "{}/sync/ratings?apikey={}".format(base_url, apikey)

        try:
            response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code >= 400:
                xbmc.log("MDBList Scrobbler: MDBList rating error {} response={}".format(
                    response.status_code, response.text[:200]), level=xbmc.LOGERROR)
                return False
            return True
        except requests.exceptions.RequestException as exception:
            xbmc.log("MDBList Scrobbler: MDBList rating request failed - {}".format(str(exception)), level=xbmc.LOGERROR)
            return False

    def prompt_for_rating(self, playback_event: str):
        if not self.should_prompt_for_rating(playback_event):
            return

        heading = "Rate {}".format(self.video_info.get("title") or self.video_info.get("showtitle") or "item")
        choices = ["Skip"] + ["{}".format(value) for value in range(1, 11)]
        selection = xbmcgui.Dialog().select(heading, choices)

        self.rating_prompt_shown = True

        if selection <= 0:
            return

        rating = selection
        saved = []
        if self.save_kodi_rating(rating):
            saved.append("Kodi")
        if self.save_mdblist_rating(rating):
            saved.append("MDBList")
        if saved:
            self.show_message("Saved {}/10 to {}".format(rating, " & ".join(saved)))

    def onAVStarted(self):
        xbmc.log("MDBList Scrobbler: onAVStarted", level=xbmc.LOGDEBUG)
        self.load_settings()
        self.reset_playback_state()
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
        xbmc.log("MDBList Scrobbler: onPlayBackStopped (video_info present={})".format(bool(self.video_info)), level=xbmc.LOGDEBUG)
        if not self.video_info:
            return

        self.update_time()
        self.send_request("stop")
        self.stop_interval_timer()
        self.prompt_for_rating("stop")
        self.video_info = {}

    def onPlayBackEnded(self):
        xbmc.log("MDBList Scrobbler: onPlayBackEnded (video_info present={})".format(bool(self.video_info)), level=xbmc.LOGDEBUG)
        if not self.video_info:
            return

        self.update_time()
        self.send_request("end")
        self.stop_interval_timer()
        self.prompt_for_rating("end")
        self.video_info = {}

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
