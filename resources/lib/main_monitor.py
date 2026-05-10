import xbmc
import xbmcaddon

from resources.lib import oauth
from resources.lib.player_monitor import PlayerMonitor


class MainMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()

        self.player_monitor = PlayerMonitor()
        try:
            status = "Connected" if oauth.get_access_token() else "Not connected"
            xbmcaddon.Addon().setSettingString("oauth_status", status)
        except Exception:
            pass

    def onSettingsChanged(self):
        self.player_monitor.load_settings()
