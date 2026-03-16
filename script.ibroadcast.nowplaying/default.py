"""
iBroadcast Now Playing
Full-screen album art display that updates as tracks change.
"""

import threading
import xbmc
import xbmcgui
import xbmcaddon

ADDON = xbmcaddon.Addon()

ACTION_BACK         = 10
ACTION_NAV_BACK     = 92
ACTION_STOP         = 13
ACTION_SELECT       = 7


class NowPlayingWindow(xbmcgui.Window):

    def __init__(self):
        super().__init__()
        self._lock        = threading.Lock()
        self._running     = True
        self._last_thumb  = None
        self._last_title  = None
        self._last_artist = None
        self._last_album  = None
        self._setup_controls()
        self._update()
        self._start_monitor()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _setup_controls(self):
        w = self.getWidth()
        h = self.getHeight()

        # Full-screen blurred album art as background
        self.bg_art = xbmcgui.ControlImage(0, 0, w, h, "", aspectRatio=0)
        self.bg_art.setColorDiffuse("0x99FFFFFF")   # slight dim
        self.addControl(self.bg_art)

        # Centred album art (square, 60 % of the shorter screen edge)
        art_size = int(min(w, h) * 0.60)
        art_x    = (w - art_size) // 2
        art_y    = (h - art_size) // 2 - int(h * 0.07)
        self.art = xbmcgui.ControlImage(art_x, art_y, art_size, art_size, "",
                                        aspectRatio=1)
        self.addControl(self.art)

        # Labels below the art
        label_y = art_y + art_size + 20
        self.lbl_title = xbmcgui.ControlLabel(
            0, label_y, w, 50, "",
            font="font20", textColor="0xFFFFFFFF",
            alignment=0x00000002,   # centre-X
        )
        self.addControl(self.lbl_title)

        self.lbl_artist = xbmcgui.ControlLabel(
            0, label_y + 54, w, 36, "",
            font="font16", textColor="0xFFCCCCCC",
            alignment=0x00000002,
        )
        self.addControl(self.lbl_artist)

        self.lbl_album = xbmcgui.ControlLabel(
            0, label_y + 94, w, 30, "",
            font="font16", textColor="0xFF999999",
            alignment=0x00000002,
        )
        self.addControl(self.lbl_album)

        # "Nothing playing" fallback
        self.lbl_idle = xbmcgui.ControlLabel(
            0, h // 2 - 20, w, 40, "Nothing is playing",
            font="font20", textColor="0xFFFFFFFF",
            alignment=0x00000002,
        )
        self.addControl(self.lbl_idle)

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def _update(self):
        player = xbmc.Player()
        playing = player.isPlayingAudio()

        thumb  = xbmc.getInfoLabel("Player.Art(thumb)")  if playing else ""
        title  = xbmc.getInfoLabel("Player.Title")       if playing else ""
        artist = xbmc.getInfoLabel("Player.Artist")      if playing else ""
        album  = xbmc.getInfoLabel("Player.Album")       if playing else ""

        with self._lock:
            self.lbl_idle.setVisible(not playing)
            self.art.setVisible(playing)
            self.bg_art.setVisible(playing)
            self.lbl_title.setVisible(playing)
            self.lbl_artist.setVisible(playing)
            self.lbl_album.setVisible(playing)

            if thumb != self._last_thumb:
                self.art.setImage(thumb)
                self.bg_art.setImage(thumb)
                self._last_thumb = thumb

            if title != self._last_title:
                self.lbl_title.setLabel(title)
                self._last_title = title

            if artist != self._last_artist:
                self.lbl_artist.setLabel(artist)
                self._last_artist = artist

            if album != self._last_album:
                self.lbl_album.setLabel(album)
                self._last_album = album

    # ------------------------------------------------------------------
    # Background monitor thread
    # ------------------------------------------------------------------

    def _start_monitor(self):
        t = threading.Thread(target=self._monitor_loop, daemon=True)
        t.start()

    def _monitor_loop(self):
        monitor = xbmc.Monitor()
        while self._running and not monitor.abortRequested():
            monitor.waitForAbort(1)
            self._update()

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def onAction(self, action):
        if action.getId() in (ACTION_BACK, ACTION_NAV_BACK, ACTION_STOP, ACTION_SELECT):
            self._running = False
            self.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    win = NowPlayingWindow()
    win.doModal()
    del win
