# =====================================================================
# CAFE NEUROTICO - GAME LIBRARY MANAGER
# =====================================================================
# Note: This entire codebase was generated using AI assistance.
# The structure, logic, and design were human-directed, but the 
# Python implementation was handled by the machine. 
# Expect unconventional patterns.
# This application was 100% conceptualized by a human and 100% coded by AI. Built to solve a personal obsession with library management.
# Feel free to fork it, refactor it, or laugh at it
# =====================================================================

import sys, csv, os, urllib.parse, urllib.request, json, shutil, sqlite3, zipfile, subprocess, shlex, time
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

if 'APPIMAGE' in os.environ:
    BASE_DIR = os.path.dirname(os.environ['APPIMAGE'])
elif getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_DIR = os.path.join(BASE_DIR, "GameManagerConfig")
IMG_DIR = os.path.join(CONFIG_DIR, "images")
DB_PATH = os.path.join(CONFIG_DIR, "games.db")
BROWSER_DATA_DIR = os.path.join(CONFIG_DIR, "browser_data")

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(BROWSER_DATA_DIR, exist_ok=True)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class NumericItem(QTableWidgetItem):
    def __lt__(self, other):
        try: return float(self.text().strip() or 0) < float(other.text().strip() or 0)
        except ValueError: return super().__lt__(other)

class AspectRatioLabel(QLabel):
    def __init__(self, text=""):
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setMinimumSize(100, 100)
        self._pixmap = None
        self.setStyleSheet("border: 1px solid gray;")

    def setPixmap(self, pixmap):
        self._pixmap = pixmap
        self.update_pixmap()

    def update_pixmap(self):
        if self._pixmap and not self._pixmap.isNull():
            super().setPixmap(self._pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        self.update_pixmap()
        super().resizeEvent(event)

class InternalBrowser(QDialog):
    def __init__(self, url, title, profile, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Browsing: {title}")
        self.resize(1100, 750)
        layout = QVBoxLayout(self)
        self.browser = QWebEngineView()
        self.page = QWebEnginePage(profile, self.browser)
        self.browser.setPage(self.page)
        self.browser.setUrl(QUrl(url))
        layout.addWidget(self.browser)

class SyncBrowser(QDialog):
    def __init__(self, url, store_type, profile, parent=None):
        super().__init__(parent)
        self.store_type = store_type
        self.setWindowTitle(f"Connect to {store_type.capitalize()}")
        self.resize(1200, 800)
        layout = QVBoxLayout(self)
        lbl = QLabel(f"Please log in to {store_type.capitalize()}. Once you can see your account/library page, click the Fetch button below!")
        lbl.setStyleSheet("font-weight: bold; color: #ffeb3b; padding: 5px; font-size: 14px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        self.btn_fetch = QPushButton(f"✅ I am logged in! Fetch my {store_type.capitalize()} Games")
        self.btn_fetch.setStyleSheet("QPushButton { background-color: #2e7d32; color: white; font-weight: bold; font-size: 16px; padding: 12px; } QPushButton:hover { background-color: #388e3c; } QPushButton:pressed { background-color: #1b5e20; }")
        layout.addWidget(self.btn_fetch)
        self.browser = QWebEngineView()
        self.page = QWebEnginePage(profile, self.browser)
        self.browser.setPage(self.page)
        self.browser.setUrl(QUrl(url))
        layout.addWidget(self.browser)


class EditGameDialog(QDialog):
    def __init__(self, parent, game_ids, db, all_games):
        super().__init__(parent)
        self.game_ids = game_ids; self.db = db; self.all_games = all_games; self.is_batch = len(game_ids) > 1
        self.setWindowTitle("Batch Edit Games" if self.is_batch else "Edit Game Details")
        self.resize(550, 600)
        layout = QVBoxLayout(self)
        if self.is_batch:
            warn = QLabel(f"⚠️ BATCH EDITING {len(game_ids)} GAMES\nOnly fields you type text into will be updated. Leave fields blank to keep original values.")
            warn.setStyleSheet("color: #ffeb3b; font-weight: bold; background-color: #d32f2f; padding: 8px;")
            warn.setWordWrap(True); warn.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(warn)
        form = QFormLayout()
        self.inputs = {}
        fields = ["Game", "Store", "Genre", "Released", "Metacritic", "HLTB_Main", "Acquired", "DEV", "PUB", "Coop", "NumPlayers", "Tags", "SimilarGames", "LaunchCommand"]
        field_idx = {"Game":6, "Store":1, "Genre":9, "Released":8, "Metacritic":7, "HLTB_Main":13, "Acquired":12, "DEV":10, "PUB":11, "Coop":24, "NumPlayers":25, "Tags":19, "SimilarGames":26, "LaunchCommand":27}
        game_data = None
        if not self.is_batch: game_data = next((g for g in self.all_games if g[0] == game_ids[0]), None)
        for f in fields:
            inp = QLineEdit()
            if not self.is_batch and game_data: inp.setText(str(game_data[field_idx[f]] or ""))
            form.addRow(f + ":", inp); self.inputs[f] = inp

        self.chk_fav = QCheckBox("⭐ Favorite"); self.chk_want = QCheckBox("📌 Want to Play")
        self.chk_playing = QCheckBox("▶️ Playing"); self.chk_finished = QCheckBox("✅ Finished")
        if self.is_batch:
            for cb in [self.chk_fav, self.chk_want, self.chk_playing, self.chk_finished]: cb.setTristate(True); cb.setCheckState(Qt.CheckState.PartiallyChecked)
        elif game_data:
            self.chk_fav.setChecked(str(game_data[2] or "").upper() == "YES"); self.chk_want.setChecked(str(game_data[3] or "").upper() == "YES")
            self.chk_playing.setChecked(str(game_data[4] or "").upper() == "YES"); self.chk_finished.setChecked(str(game_data[5] or "").upper() == "YES")

        chk_lay = QHBoxLayout(); chk_lay.addWidget(self.chk_fav); chk_lay.addWidget(self.chk_want); chk_lay.addWidget(self.chk_playing); chk_lay.addWidget(self.chk_finished)
        form.addRow(chk_lay)
        self.edit_desc = QTextEdit()
        if not self.is_batch and game_data: self.edit_desc.setText(str(game_data[18] or ""))
        form.addRow("Description:", self.edit_desc)
        layout.addLayout(form)
        btn_save = QPushButton("💾 Save Changes")
        btn_save.setStyleSheet("QPushButton { background-color: #2b5797; color: white; font-weight: bold; padding: 10px; } QPushButton:hover { background-color: #3b6ba5; }")
        btn_save.clicked.connect(self.save_data); layout.addWidget(btn_save)

    def save_data(self):
        for gid in self.game_ids:
            for f, inp in self.inputs.items():
                val = inp.text().strip()
                if self.is_batch and not val: continue
                self.db.update_game_info(gid, f, val)
            for cb, field in [(self.chk_fav, "FAV"), (self.chk_want, "WANT_TO_PLAY"), (self.chk_playing, "PLAYING"), (self.chk_finished, "FINISHED")]:
                if cb.checkState() == Qt.CheckState.Checked: self.db.update_game_info(gid, field, "YES")
                elif cb.checkState() == Qt.CheckState.Unchecked: self.db.update_game_info(gid, field, "")
            desc_val = self.edit_desc.toPlainText().strip()
            if not self.is_batch or desc_val: self.db.update_game_info(gid, "Description", desc_val)
        self.accept()

class SGDBImageDialog(QDialog):
    def __init__(self, parent, game_name, api_key, local_game_id):
        super().__init__(parent)
        self.setWindowTitle(f"SteamGridDB Covers - {game_name}"); self.resize(800, 600)
        self.api_key = api_key; self.game_name = game_name; self.local_game_id = local_game_id; self.selected_image_path = None
        layout = QVBoxLayout(self)
        self.status_lbl = QLabel("Searching SteamGridDB...")
        self.status_lbl.setStyleSheet("font-weight: bold; font-size: 14px;"); layout.addWidget(self.status_lbl)
        self.list_widget = QListWidget(); self.list_widget.setViewMode(QListView.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(160, 240)); self.list_widget.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_widget.setSpacing(10); self.list_widget.itemDoubleClicked.connect(self.select_image); layout.addWidget(self.list_widget)
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel"); btn_cancel.clicked.connect(self.reject)
        self.btn_apply = QPushButton("Apply Selected")
        self.btn_apply.setEnabled(False)
        self.btn_apply.setStyleSheet("QPushButton { background-color: #2e7d32; color: white; font-weight: bold; } QPushButton:disabled { background-color: gray; }")
        self.btn_apply.clicked.connect(self.select_image_btn)
        self.list_widget.itemSelectionChanged.connect(lambda: self.btn_apply.setEnabled(bool(self.list_widget.selectedItems())))
        btn_layout.addStretch(); btn_layout.addWidget(btn_cancel); btn_layout.addWidget(self.btn_apply); layout.addLayout(btn_layout)
        QTimer.singleShot(100, self.load_images)

    def load_images(self):
        name_encoded = urllib.parse.quote(self.game_name)
        headers = {"Authorization": f"Bearer {self.api_key}", "User-Agent": "Mozilla/5.0"}
        try:
            req1 = urllib.request.Request(f"https://www.steamgriddb.com/api/v2/search/autocomplete/{name_encoded}", headers=headers)
            resp1 = json.loads(urllib.request.urlopen(req1).read())
            if not resp1.get('success') or not resp1.get('data'): self.status_lbl.setText("Game not found on SteamGridDB."); return
            sgdb_id = resp1['data'][0]['id']
            self.status_lbl.setText("Fetching high-quality covers..."); QApplication.processEvents()
            req2 = urllib.request.Request(f"https://www.steamgriddb.com/api/v2/grids/game/{sgdb_id}?dimensions=600x900", headers=headers)
            resp2 = json.loads(urllib.request.urlopen(req2).read())
            grids = resp2.get('data', [])
            if not grids: self.status_lbl.setText("No 600x900 covers found for this game."); return
            self.status_lbl.setText(f"Found {len(grids)} covers. Double-click or select and Apply:")
            for grid in grids:
                try:
                    img_req = urllib.request.Request(grid.get('thumb'), headers={"User-Agent": "Mozilla/5.0"})
                    img_data = urllib.request.urlopen(img_req).read()
                    pixmap = QPixmap(); pixmap.loadFromData(img_data)
                    item = QListWidgetItem(); item.setIcon(QIcon(pixmap)); item.setData(Qt.ItemDataRole.UserRole, grid.get('url'))
                    self.list_widget.addItem(item)
                except: pass
                QApplication.processEvents()
        except urllib.error.HTTPError as e:
            if e.code == 403: self.status_lbl.setText("HTTP 403: Forbidden. Invalid SGDB API Key!")
            else: self.status_lbl.setText(f"HTTP Error: {e.code}")
        except Exception as e: self.status_lbl.setText(f"Error fetching data: {e}")

    def select_image_btn(self):
        if self.list_widget.selectedItems(): self.select_image(self.list_widget.selectedItems()[0])

    def select_image(self, item):
        full_url = item.data(Qt.ItemDataRole.UserRole)
        self.status_lbl.setText("Downloading selected cover..."); self.btn_apply.setEnabled(False); QApplication.processEvents()
        try:
            path = os.path.join(IMG_DIR, f"{self.local_game_id}_CoverArt_sgdb.jpg")
            req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response, open(path, 'wb') as out_file: shutil.copyfileobj(response, out_file)
            self.selected_image_path = path; self.accept()
        except Exception as e: self.status_lbl.setText(f"Failed to download image: {e}"); self.btn_apply.setEnabled(True)

class GameDB:
    def __init__(self, db_name=DB_PATH):
        self.conn = sqlite3.connect(db_name); self.create_table()
    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT, Store TEXT, FAV TEXT, WANT_TO_PLAY TEXT,
            PLAYING TEXT, FINISHED TEXT, Game TEXT, METACRITIC TEXT, RELEASED TEXT, GENRE TEXT,
            DEV TEXT, PUB TEXT, Acquired TEXT, HLTB_Main TEXT, HLTB_Main_Side TEXT, HLTB_Comp TEXT,
            CoverArt TEXT, Screenshot TEXT, Description TEXT, Tags TEXT,
            SteamAppID TEXT, SteamRating TEXT, Price TEXT, LowestPrice TEXT,
            Coop TEXT, NumPlayers TEXT, SimilarGames TEXT, LaunchCommand TEXT)""")
        cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("PRAGMA table_info(games)")
        existing_cols = [col[1] for col in cursor.fetchall()]
        for col in ["PLAYING", "FINISHED", "SteamAppID", "SteamRating", "Price", "LowestPrice", "Coop", "NumPlayers", "SimilarGames", "LaunchCommand"]:
            if col not in existing_cols: cursor.execute(f"ALTER TABLE games ADD COLUMN {col} TEXT")
        self.conn.commit()
    def get_all_games(self): return self.conn.cursor().execute("SELECT * FROM games").fetchall()
    def update_game_info(self, game_id, field, value):
        self.conn.cursor().execute(f"UPDATE games SET {field} = ? WHERE id = ?", (value, game_id)); self.conn.commit()
    def delete_game(self, game_id):
        self.conn.cursor().execute("DELETE FROM games WHERE id = ?", (game_id,)); self.conn.commit()
    def get_setting(self, key):
        res = self.conn.cursor().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return res[0] if res else ""
    def set_setting(self, key, value):
        self.conn.cursor().execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)); self.conn.commit()

class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #121212;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel()
        splash_path = resource_path("splashscreen.jpg")
        if os.path.exists(splash_path):
            pixmap = QPixmap(splash_path).scaled(600, 600, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl.setPixmap(pixmap)
        else:
            lbl.setText("SPLASH SCREEN MISSING")
            lbl.setStyleSheet("color: white; font-weight: bold; font-size: 20px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        self.prog = QProgressBar()
        self.prog.setTextVisible(False)
        self.prog.setFixedHeight(8)
        self.prog.setStyleSheet("QProgressBar { border: none; background-color: #333; } QProgressBar::chunk { background-color: #39ff14; }")
        layout.addWidget(self.prog)

        lbl_text = QLabel("by Shampoo Is a Lie")
        lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_text.setStyleSheet("color: #E0E0E0; font-weight: bold; font-size: 16px; padding: 10px; font-family: sans-serif;")
        layout.addWidget(lbl_text)


class GameLibraryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cafe Neurotico - Game Library Manager")
        self.resize(1400, 950)
        self.db = GameDB(); self.is_dark_mode = True
        self.all_games = []; self.gallery_columns = 7; self.current_game_id = None
        self._updating_list = False; self._updating_filters = False
        self.gallery_sort = "A-Z"

        self.current_screens = []
        self.current_screen_idx = 0
        self.screen_timer = QTimer(self)
        self.screen_timer.timeout.connect(self.next_screenshot)

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(350)
        self.search_timer.timeout.connect(self.trigger_search)

        self.init_ui(); self.apply_theme(); self.fetch_data()

    def get_web_profile(self):
        if not hasattr(self, 'web_profile'):
            self.web_profile = QWebEngineProfile("GameManagerProfile", self)
            self.web_profile.setPersistentStoragePath(BROWSER_DATA_DIR)
            self.web_profile.setCachePath(BROWSER_DATA_DIR)
            self.web_profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        return self.web_profile

    def get_bg_browser(self):
        if not hasattr(self, 'bg_browser'):
            self.bg_browser = QWebEngineView()
            self.bg_page = QWebEnginePage(self.get_web_profile(), self.bg_browser)
            self.bg_page.profile().setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            self.bg_browser.setPage(self.bg_page)
        return self.bg_browser

    def trigger_search(self):
        self.apply_filters()
        self.filter_sidebar()

    def init_ui(self):
        left_bar_container = QWidget()
        left_bar_container.setFixedWidth(280)
        left_layout = QVBoxLayout(left_bar_container)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(15)

        nav_layout = QHBoxLayout()
        btn_list = QPushButton("List")
        btn_gallery = QPushButton("Gallery")
        btn_list.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        btn_gallery.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.sidebar_toggle_btn = QPushButton("☰ Tags")
        self.sidebar_toggle_btn.clicked.connect(self.toggle_sidebar)
        nav_layout.addWidget(btn_list); nav_layout.addWidget(btn_gallery); nav_layout.addWidget(self.sidebar_toggle_btn)
        left_layout.addLayout(nav_layout)

        self.add_game_btn = QPushButton("+ Add Game")
        self.add_game_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 10px; border-radius: 4px; } QPushButton:hover { background-color: #1976D2; }")
        add_menu = QMenu()
        act_auto = QAction("Automated Add (Steam)", self); act_auto.triggered.connect(self.add_game_auto)
        act_man = QAction("Manual Add (Blank)", self); act_man.triggered.connect(self.add_game_manual)
        self.add_game_btn.setMenu(add_menu); add_menu.addAction(act_auto); add_menu.addAction(act_man)
        left_layout.addWidget(self.add_game_btn)

        search_group = QGroupBox("Search & Filter")
        sg_layout = QVBoxLayout(search_group); sg_layout.setContentsMargins(10, 25, 10, 10)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search games (name, year, genre...)...")
        self.search_bar.textChanged.connect(self.search_timer.start)
        self.search_bar.returnPressed.connect(self.show_sidebar_on_search)

        self.search_name_only = QCheckBox("Search Name Only"); self.search_name_only.stateChanged.connect(self.apply_filters)
        self.search_fuzzy = QCheckBox("Fuzzy Search"); self.search_fuzzy.stateChanged.connect(self.apply_filters)

        sg_layout.addWidget(self.search_bar); sg_layout.addWidget(self.search_name_only); sg_layout.addWidget(self.search_fuzzy)
        left_layout.addWidget(search_group)

        see_only_group = QGroupBox("See")
        so_layout = QGridLayout(see_only_group); so_layout.setContentsMargins(10, 25, 10, 10)
        self.btn_all = QPushButton("All Games"); self.btn_all.setCheckable(True); self.btn_all.setChecked(True)
        self.btn_playable = QPushButton("Playable"); self.btn_playable.setCheckable(True)
        self.btn_fav = QPushButton("Favs"); self.btn_fav.setCheckable(True)
        self.btn_want = QPushButton("Want"); self.btn_want.setCheckable(True)
        self.btn_steam = QPushButton("Steam"); self.btn_steam.setCheckable(True)
        self.btn_epic = QPushButton("Epic"); self.btn_epic.setCheckable(True)
        self.btn_gog = QPushButton("GOG"); self.btn_gog.setCheckable(True)
        self.btn_phys = QPushButton("Physical"); self.btn_phys.setCheckable(True)
        self.btn_others = QPushButton("Others"); self.btn_others.setCheckable(True)
        self.btn_emulation = QPushButton("Emulation"); self.btn_emulation.setCheckable(True)
        for b in [self.btn_all, self.btn_playable, self.btn_fav, self.btn_want, self.btn_steam, self.btn_epic, self.btn_gog, self.btn_phys, self.btn_others, self.btn_emulation]:
            b.toggled.connect(self.on_filter_toggled)
        so_layout.addWidget(self.btn_all, 0, 0); so_layout.addWidget(self.btn_playable, 0, 1)
        so_layout.addWidget(self.btn_fav, 1, 0); so_layout.addWidget(self.btn_want, 1, 1)
        so_layout.addWidget(self.btn_steam, 2, 0); so_layout.addWidget(self.btn_epic, 2, 1)
        so_layout.addWidget(self.btn_gog, 3, 0); so_layout.addWidget(self.btn_phys, 3, 1)
        so_layout.addWidget(self.btn_others, 4, 0); so_layout.addWidget(self.btn_emulation, 4, 1)
        left_layout.addWidget(see_only_group)

        menu_group = QGroupBox("Menu")
        mg_layout = QHBoxLayout(menu_group)
        mg_layout.setContentsMargins(10, 25, 10, 10)

        self.btn_connect_menu = QPushButton("Connect")
        self.btn_connect_menu.clicked.connect(self.open_connect_dialog)
        self.btn_tools_menu = QPushButton("Tools")
        self.btn_tools_menu.clicked.connect(self.open_tools_dialog)

        mg_layout.addWidget(self.btn_connect_menu)
        mg_layout.addWidget(self.btn_tools_menu)
        left_layout.addWidget(menu_group)

        left_layout.addStretch()

        logo_label = QLabel()
        logo_path = resource_path("logo.png")
        if os.path.exists(logo_path):
            logo_pixmap = QPixmap(logo_path).scaledToWidth(260, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setStyleSheet("background: transparent; border: none;")
        else:
            logo_label.setText("LOGO MISSING")
            logo_label.setStyleSheet("background: transparent; border: none; font-weight: bold; color: gray;")
        left_layout.addWidget(logo_label)

        self.right_sidebar_container = QWidget(); self.right_sidebar_container.setFixedWidth(220)
        right_sidebar_layout = QVBoxLayout(self.right_sidebar_container); right_sidebar_layout.setContentsMargins(0,0,0,0)
        self.sidebar = QTreeWidget(); self.sidebar.setHeaderHidden(True); self.sidebar.itemClicked.connect(self.apply_filters)
        right_sidebar_layout.addWidget(self.sidebar); self.right_sidebar_container.hide()

        self.stack = QStackedWidget()
        self.stack.currentChanged.connect(lambda idx: self.resize_gallery() if idx == 1 else None)

        self.list_view = QTableWidget(); self.list_view.setColumnCount(10)
        self.list_view.setHorizontalHeaderLabels(["Launch", "Fav", "Want", "Game", "Store", "Genre", "Released", "Metacritic", "HLTB", "Acquired"])
        self.list_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.list_view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.list_view.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.list_view.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.list_view.cellDoubleClicked.connect(lambda r, c: self.open_detail_view(self.list_view.item(r, 3).data(Qt.ItemDataRole.UserRole)))
        self.list_view.setSortingEnabled(True); self.list_view.itemChanged.connect(self.list_item_changed)

        self.list_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.list_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(self.show_context_menu)

        gallery_widget = QWidget(); gal_layout = QVBoxLayout(gallery_widget); gal_controls = QHBoxLayout()
        gal_controls.addWidget(QLabel("Sort:"))
        btn_sort_az = QPushButton("A-Z"); btn_sort_az.clicked.connect(lambda: self.set_gallery_sort("A-Z"))
        btn_sort_fav = QPushButton("Favs"); btn_sort_fav.clicked.connect(lambda: self.set_gallery_sort("FAV"))
        btn_sort_want = QPushButton("Want"); btn_sort_want.clicked.connect(lambda: self.set_gallery_sort("WANT"))
        gal_controls.addWidget(btn_sort_az); gal_controls.addWidget(btn_sort_fav); gal_controls.addWidget(btn_sort_want)
        gal_controls.addStretch(); gal_controls.addWidget(QLabel("Items per row:"))
        for cols in [3, 5, 7, 10]:
            btn = QPushButton(str(cols)); btn.clicked.connect(lambda checked, c=cols: self.set_gallery_cols(c)); gal_controls.addWidget(btn)

        self.gallery_view = QListWidget(); self.gallery_view.setViewMode(QListView.ViewMode.IconMode); self.gallery_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.gallery_view.setWordWrap(True); self.gallery_view.itemDoubleClicked.connect(lambda item: self.open_detail_view(item.data(Qt.ItemDataRole.UserRole)))
        gal_layout.addLayout(gal_controls); gal_layout.addWidget(self.gallery_view)

        self.detail_view = QWidget(); self.setup_detail_view()
        self.stack.addWidget(self.list_view); self.stack.addWidget(gallery_widget); self.stack.addWidget(self.detail_view)

        main_layout = QHBoxLayout(); main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(left_bar_container); main_layout.addWidget(self.stack); main_layout.addWidget(self.right_sidebar_container)
        central_widget = QWidget(); central_widget.setLayout(main_layout); self.setCentralWidget(central_widget)

    def open_connect_dialog(self):
        self.dlg_connect = QDialog(self)
        self.dlg_connect.setWindowTitle("Connect & Links")
        self.dlg_connect.resize(300, 350)
        layout = QVBoxLayout(self.dlg_connect)

        lbl_stores = QLabel("Store Sync")
        lbl_stores.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_stores)

        self.btn_sync_steam = QPushButton("Steam")
        self.btn_sync_steam.clicked.connect(self.handle_steam_sync)
        self.btn_sync_gog = QPushButton("GOG")
        self.btn_sync_gog.clicked.connect(self.handle_gog_sync)
        self.btn_sync_epic = QPushButton("Epic")
        self.btn_sync_epic.clicked.connect(self.open_sync_epic)

        layout.addWidget(self.btn_sync_steam)
        layout.addWidget(self.btn_sync_gog)
        layout.addWidget(self.btn_sync_epic)

        self.update_connect_buttons()

        lbl_links = QLabel("External Links")
        lbl_links.setStyleSheet("font-weight: bold; margin-top: 15px;")
        layout.addWidget(lbl_links)

        for b in ["YouTube", "IsThereAnyDeal", "ProtonDB", "HowLongToBeat"]:
            btn = QPushButton(b)
            btn.clicked.connect(lambda checked, name=b: self.open_external_link_general(name))
            layout.addWidget(btn)

        self.dlg_connect.exec()
        self.btn_sync_steam = None; self.btn_sync_gog = None; self.btn_sync_epic = None

    def open_tools_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Tools")
        dlg.resize(350, 450)
        layout = QVBoxLayout(dlg)

        lbl_fetch = QLabel("Batch Fetch")
        lbl_fetch.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_fetch)

        btn_fetch_all = QPushButton("Fetch ALL Missing Data")
        btn_fetch_all.clicked.connect(self.batch_fetch_everything)
        btn_fetch_info = QPushButton("Fetch Missing Game Info")
        btn_fetch_info.clicked.connect(self.batch_fetch_info)
        btn_fetch_art = QPushButton("Fetch Missing Artwork")
        btn_fetch_art.clicked.connect(self.batch_fetch_art)
        btn_fetch_desc = QPushButton("Fetch Missing Descriptions")
        btn_fetch_desc.clicked.connect(self.batch_fetch_desc)

        layout.addWidget(btn_fetch_all); layout.addWidget(btn_fetch_info)
        layout.addWidget(btn_fetch_art); layout.addWidget(btn_fetch_desc)

        lbl_io = QLabel("Import / Export & Backup")
        lbl_io.setStyleSheet("font-weight: bold; margin-top: 15px;")
        layout.addWidget(lbl_io)

        btn_imp_csv = QPushButton("Import CSV"); btn_imp_csv.clicked.connect(self.import_csv_dialog)
        btn_exp_csv = QPushButton("Export to CSV"); btn_exp_csv.clicked.connect(self.export_csv_dialog)
        btn_tmpl = QPushButton("Download CSV Template"); btn_tmpl.clicked.connect(self.download_csv_template)
        btn_sgdb = QPushButton("Set SteamGridDB Key"); btn_sgdb.clicked.connect(self.import_sgdb_key)
        btn_bak_save = QPushButton("Save Backup (.zip)"); btn_bak_save.clicked.connect(self.save_backup)
        btn_bak_rec = QPushButton("Recover Backup (.zip)"); btn_bak_rec.clicked.connect(self.recover_backup)
        btn_clr_data = QPushButton("Clear Browser Data"); btn_clr_data.clicked.connect(self.clear_browser_data)

        layout.addWidget(btn_imp_csv); layout.addWidget(btn_exp_csv); layout.addWidget(btn_tmpl)
        layout.addWidget(btn_sgdb); layout.addWidget(btn_bak_save); layout.addWidget(btn_bak_rec)
        layout.addWidget(btn_clr_data)

        lbl_ui = QLabel("Interface")
        lbl_ui.setStyleSheet("font-weight: bold; margin-top: 15px;")
        layout.addWidget(lbl_ui)

        btn_theme = QPushButton("Toggle Theme")
        btn_theme.clicked.connect(self.toggle_theme)
        layout.addWidget(btn_theme)

        dlg.exec()

    def open_external_link_general(self, platform):
        urls = {"YouTube": "https://www.youtube.com/", "IsThereAnyDeal": "https://isthereanydeal.com/", "ProtonDB": "https://www.protondb.com/", "HowLongToBeat": "https://howlongtobeat.com/"}
        browser = InternalBrowser(urls[platform], platform, self.get_web_profile(), self)
        browser.exec()

    def show_sidebar_on_search(self):
        if not self.right_sidebar_container.isVisible(): self.right_sidebar_container.setVisible(True)

    def toggle_sidebar(self):
        self.right_sidebar_container.setVisible(not self.right_sidebar_container.isVisible())

    def on_filter_toggled(self, checked):
        if self._updating_filters: return
        sender = self.sender(); self._updating_filters = True
        if sender == self.btn_all and checked:
            for b in [self.btn_playable, self.btn_fav, self.btn_want, self.btn_steam, self.btn_epic, self.btn_gog, self.btn_phys, self.btn_others, self.btn_emulation]:
                b.setChecked(False)
        elif sender != self.btn_all and checked:
            self.btn_all.setChecked(False)
            if sender in [self.btn_steam, self.btn_epic, self.btn_gog, self.btn_phys, self.btn_others, self.btn_emulation]:
                for b in [self.btn_steam, self.btn_epic, self.btn_gog, self.btn_phys, self.btn_others, self.btn_emulation]:
                    if b != sender: b.setChecked(False)
        self._updating_filters = False; self.apply_filters()


    def apply_filters(self):
        search_text = self.search_bar.text().lower(); is_fuzzy = self.search_fuzzy.isChecked()
        sel_item = self.sidebar.currentItem()
        cat_filter = sel_item.parent().text(0) if sel_item and sel_item.parent() else ""
        val_filter = sel_item.text(0) if sel_item and sel_item.parent() else ""

        show_fav = self.btn_fav.isChecked(); show_want = self.btn_want.isChecked(); show_playable = self.btn_playable.isChecked()

        active_stores = []
        if self.btn_steam.isChecked(): active_stores.append("steam")
        if self.btn_epic.isChecked(): active_stores.append("epic")
        if self.btn_gog.isChecked(): active_stores.append("gog")
        if self.btn_phys.isChecked(): active_stores.append("physical")
        if self.btn_others.isChecked(): active_stores.append("others")
        if self.btn_emulation.isChecked(): active_stores.append("emulation")

        filtered_games = []
        for g in self.all_games:
            game_id, store, fav, want, playing, finished, name = g[:7]; name = str(name or "")
            if not name.strip(): continue

            if show_fav and str(fav).upper() != "YES": continue
            if show_want and str(want).upper() != "YES": continue
            if show_playable and not str(g[27] or "").strip(): continue
            if active_stores:
                if not any(s in str(store).lower() for s in active_stores): continue

            if cat_filter == "Stores" and str(store).strip() != val_filter: continue
            if cat_filter == "Genres" and str(g[9]).strip() != val_filter: continue

            if search_text:
                if self.search_name_only.isChecked():
                    searchable_data = name.lower()
                else:
                    searchable_data = " ".join([str(val) for val in g[1:] if val]).lower()

                if is_fuzzy:
                    if not all(char in searchable_data for char in search_text.replace(" ", "")): continue
                else:
                    search_terms = search_text.split()
                    if not all(term in searchable_data for term in search_terms): continue

            filtered_games.append(g)

        if self.gallery_sort == "A-Z": filtered_games.sort(key=lambda x: (0 if str(x[27]).strip() else 1, str(x[6] or "").lower()))
        elif self.gallery_sort == "FAV": filtered_games.sort(key=lambda x: (0 if str(x[2]).upper() == "YES" else 1, 0 if str(x[27]).strip() else 1, str(x[6] or "").lower()))
        elif self.gallery_sort == "WANT": filtered_games.sort(key=lambda x: (0 if str(x[3]).upper() == "YES" else 1, 0 if str(x[27]).strip() else 1, str(x[6] or "").lower()))

        self.render_views(filtered_games)

    def render_views(self, games):
        self._updating_list = True
        self.list_view.setSortingEnabled(False); self.list_view.setRowCount(len(games)); self.gallery_view.clear()

        if self.is_dark_mode: colors = {"steam": QColor(135, 206, 250), "epic": QColor(255, 255, 153), "gog": QColor(221, 160, 221), "physical": QColor(144, 238, 144), "others": QColor(144, 238, 144), "emulation": QColor(255, 165, 0)}
        else: colors = {"steam": QColor(0, 0, 205), "epic": QColor(184, 134, 11), "gog": QColor(128, 0, 128), "physical": QColor(0, 100, 0), "others": QColor(0, 100, 0), "emulation": QColor(210, 105, 30)}

        for row_idx, game in enumerate(games):
            game_id, store, fav, want, playing, finished, name, meta, released, genre, dev, pub, acq, hltb = game[:14]; cover_path = game[16]
            has_cmd = bool(str(game[27] or "").strip())

            icons = ""
            if str(fav).upper() == "YES": icons += "★ "
            if str(want).upper() == "YES": icons += "⚑ "
            if str(playing).upper() == "YES": icons += "▶ "
            if str(finished).upper() == "YES": icons += "✓ "
            display_name = f"{icons}{name}"

            fav_item = QTableWidgetItem(); fav_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            fav_item.setCheckState(Qt.CheckState.Checked if str(fav).upper() == "YES" else Qt.CheckState.Unchecked)
            want_item = QTableWidgetItem(); want_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            want_item.setCheckState(Qt.CheckState.Checked if str(want).upper() == "YES" else Qt.CheckState.Unchecked)

            name_item = QTableWidgetItem(display_name); name_item.setData(Qt.ItemDataRole.UserRole, game_id)

            if has_cmd:
                l_btn = QPushButton("Play")
                l_btn.setStyleSheet("QPushButton { background-color: #2e7d32; color: white; font-weight: bold; border-radius: 2px; padding: 2px; } QPushButton:hover { background-color: #388e3c; }")
                l_btn.clicked.connect(lambda checked, gid=game_id: self.launch_game(gid))
                self.list_view.setCellWidget(row_idx, 0, l_btn)
            else: self.list_view.setCellWidget(row_idx, 0, QWidget())

            for key, col in colors.items():
                if key in str(store).lower(): name_item.setForeground(QBrush(col)); break

            self.list_view.setItem(row_idx, 1, fav_item); self.list_view.setItem(row_idx, 2, want_item)
            self.list_view.setItem(row_idx, 3, name_item); self.list_view.setItem(row_idx, 4, QTableWidgetItem(str(store)))
            self.list_view.setItem(row_idx, 5, QTableWidgetItem(str(genre))); self.list_view.setItem(row_idx, 6, NumericItem(str(released)))
            self.list_view.setItem(row_idx, 7, NumericItem(str(meta))); self.list_view.setItem(row_idx, 8, QTableWidgetItem(str(hltb)))
            self.list_view.setItem(row_idx, 9, QTableWidgetItem(str(acq)))

            gal_item = QListWidgetItem(self.gallery_view); gal_item.setData(Qt.ItemDataRole.UserRole, game_id)
            w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(4,4,4,4)

            img_lbl = QLabel(); img_lbl.setScaledContents(True)
            if cover_path and os.path.exists(cover_path):
                pixmap = QPixmap(cover_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(180, 270, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                img_lbl.setPixmap(pixmap)
            else:
                pixmap = QPixmap(180, 270); pixmap.fill(QColor(60, 60, 60)); painter = QPainter(pixmap); painter.setPen(QColor(255, 255, 255))
                f = painter.font(); f.setPointSize(12); painter.setFont(f)
                painter.drawText(pixmap.rect(), int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap), str(name)); painter.end()
                img_lbl.setPixmap(pixmap)

            title_lbl = QLabel(display_name); title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); title_lbl.setWordWrap(True); title_lbl.setFixedHeight(35)
            for key, col in colors.items():
                if key in str(store).lower(): title_lbl.setStyleSheet(f"color: {col.name()}; font-weight: bold;"); break

            gal_launch_btn = QPushButton("Play")
            if has_cmd:
                gal_launch_btn.setStyleSheet("QPushButton { background-color: #2e7d32; color: white; font-weight: bold; border-radius: 3px; padding: 4px; } QPushButton:hover { background-color: #388e3c; }")
                gal_launch_btn.clicked.connect(lambda checked, gid=game_id: self.launch_game(gid))
            else:
                gal_launch_btn.setEnabled(False); gal_launch_btn.setText("No Command"); gal_launch_btn.setStyleSheet("background-color: transparent; color: gray; border: none;")

            img_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents); title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            vl.addWidget(img_lbl); vl.addWidget(title_lbl); vl.addWidget(gal_launch_btn)
            self.gallery_view.setItemWidget(gal_item, w)

        self.list_view.setSortingEnabled(True); self._updating_list = False; self.resize_gallery()

    def list_item_changed(self, item):
        if self._updating_list: return
        col = item.column()
        if col in [1, 2]:
            game_item = self.list_view.item(item.row(), 3)
            if not game_item: return
            game_id = game_item.data(Qt.ItemDataRole.UserRole)
            val = "YES" if item.checkState() == Qt.CheckState.Checked else ""
            field = "FAV" if col == 1 else "WANT_TO_PLAY"
            self.db.update_game_info(game_id, field, val)
            for i, g in enumerate(self.all_games):
                if g[0] == game_id:
                    lst = list(g); lst[2 if col == 1 else 3] = val
                    self.all_games[i] = tuple(lst); break
            QTimer.singleShot(0, self.apply_filters)

    def set_gallery_cols(self, num): self.gallery_columns = num; self.resize_gallery()

    def resize_gallery(self):
        if self.gallery_view.viewport().width() > 0:
            width = self.gallery_view.viewport().width() - 30; item_w = width // self.gallery_columns
            new_size = QSize(item_w, int(item_w * 1.5) + 80); self.gallery_view.setGridSize(new_size)
            for i in range(self.gallery_view.count()): self.gallery_view.item(i).setSizeHint(new_size)

    def open_detail_view(self, game_id):
        self.current_game_id = game_id; game = next((g for g in self.all_games if g[0] == game_id), None)
        if not game: return
        self.stack.setCurrentIndex(2)
        def get_val(idx): return str(game[idx] or "") if idx < len(game) else ""
        g_name = get_val(6); s_name = get_val(1); self.lblNameOverlay.setText(g_name)

        icon_name = f"icon_{s_name.lower()}.png"
        icon_path = resource_path(icon_name)
        if os.path.exists(icon_path):
            self.lblStoreIconOverlay.setPixmap(QPixmap(icon_path).scaledToHeight(48, Qt.TransformationMode.SmoothTransformation))
            self.lblStoreIconOverlay.setText("")
        else: self.lblStoreIconOverlay.setPixmap(QPixmap()); self.lblStoreIconOverlay.setText(s_name)

        self.chk_fav.setChecked(get_val(2).upper() == "YES"); self.chk_want.setChecked(get_val(3).upper() == "YES")
        self.chk_playing.setChecked(get_val(4).upper() == "YES"); self.chk_finished.setChecked(get_val(5).upper() == "YES")

        self.edit_name.setText(g_name); self.edit_store.setText(s_name)
        self.edit_genre.setText(get_val(9)); self.edit_released.setText(get_val(8))
        self.edit_meta.setText(get_val(7)); self.edit_hltb.setText(get_val(13))
        self.edit_acquired.setText(get_val(12)); self.edit_dev.setText(get_val(10))
        self.edit_pub.setText(get_val(11)); self.edit_coop.setText(get_val(24))
        self.edit_numplayers.setText(get_val(25)); self.edit_tags.setText(get_val(19))
        self.edit_similar.setText(get_val(26)); self.edit_launch_cmd.setText(get_val(27))
        self.edit_desc.setText(get_val(18))

        cover = get_val(16)
        if cover and os.path.exists(cover): self.lbl_cover.setPixmap(QPixmap(cover)); self.lbl_cover.setText("")
        else: self.lbl_cover.setPixmap(QPixmap()); self.lbl_cover.setText("No Cover")

        screen_val = get_val(17)
        self.current_screens = screen_val.split('|') if screen_val else []
        self.current_screen_idx = 0; self.update_screenshot_display(); self.screen_timer.start(4000)

    def save_detail_changes(self):
        if not self.current_game_id: return
        self.db.update_game_info(self.current_game_id, "FAV", "YES" if self.chk_fav.isChecked() else "")
        self.db.update_game_info(self.current_game_id, "WANT_TO_PLAY", "YES" if self.chk_want.isChecked() else "")
        self.db.update_game_info(self.current_game_id, "PLAYING", "YES" if self.chk_playing.isChecked() else "")
        self.db.update_game_info(self.current_game_id, "FINISHED", "YES" if self.chk_finished.isChecked() else "")
        self.db.update_game_info(self.current_game_id, "Game", self.edit_name.text()); self.db.update_game_info(self.current_game_id, "Store", self.edit_store.text())
        self.db.update_game_info(self.current_game_id, "GENRE", self.edit_genre.text()); self.db.update_game_info(self.current_game_id, "RELEASED", self.edit_released.text())
        self.db.update_game_info(self.current_game_id, "METACRITIC", self.edit_meta.text()); self.db.update_game_info(self.current_game_id, "HLTB_Main", self.edit_hltb.text())
        self.db.update_game_info(self.current_game_id, "Acquired", self.edit_acquired.text()); self.db.update_game_info(self.current_game_id, "DEV", self.edit_dev.text())
        self.db.update_game_info(self.current_game_id, "PUB", self.edit_pub.text()); self.db.update_game_info(self.current_game_id, "Coop", self.edit_coop.text())
        self.db.update_game_info(self.current_game_id, "NumPlayers", self.edit_numplayers.text()); self.db.update_game_info(self.current_game_id, "Tags", self.edit_tags.text())
        self.db.update_game_info(self.current_game_id, "SimilarGames", self.edit_similar.text()); self.db.update_game_info(self.current_game_id, "LaunchCommand", self.edit_launch_cmd.text())
        self.db.update_game_info(self.current_game_id, "Description", self.edit_desc.toPlainText())
        QMessageBox.information(self, "Saved", "Game details updated successfully!"); self.fetch_data()

    def show_context_menu(self, position):
        selected_rows = list(set(item.row() for item in self.list_view.selectedItems()))
        if not selected_rows: return
        menu = QMenu()
        if len(selected_rows) == 1:
            action_fetch = menu.addAction("Auto Fetch Missing Data")
            action_edit = menu.addAction("Edit Game")
            action_del = menu.addAction("Delete Game")
        else:
            action_fetch = menu.addAction("Batch Auto Fetch Missing Data")
            action_edit = menu.addAction("Batch Edit Games")
            action_del = menu.addAction("Batch Delete Games")
        action = menu.exec(self.list_view.viewport().mapToGlobal(position))
        game_ids = [self.list_view.item(r, 3).data(Qt.ItemDataRole.UserRole) for r in selected_rows]
        if action == action_fetch: self.batch_auto_fetch_specific(game_ids)
        elif action == action_edit: self.open_batch_edit_dialog(game_ids)
        elif action == action_del: self.delete_specific_games(game_ids)

    def open_batch_edit_dialog(self, game_ids):
        dialog = EditGameDialog(self, game_ids, self.db, self.all_games)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.fetch_data()

    def delete_specific_games(self, game_ids):
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Deletion")
        msg.setText(f"Are you sure you want to permanently delete {len(game_ids)} game(s) from your library?")
        msg.setIcon(QMessageBox.Icon.Warning)
        btn_del = msg.addButton("Delete Forever", QMessageBox.ButtonRole.DestructiveRole)
        btn_del.setStyleSheet("QPushButton { background-color: #d32f2f; color: white; font-weight: bold; padding: 5px; } QPushButton:hover { background-color: #e53935; }")
        msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() == btn_del:
            for gid in game_ids: self.db.delete_game(gid)
            self.fetch_data()
            if self.stack.currentIndex() == 2 and self.current_game_id in game_ids: self.close_detail_view()

    def _select_steam_game(self, name_str, interactive=False):
        name_encoded = urllib.parse.quote(name_str)
        try:
            url = f"https://store.steampowered.com/api/storesearch/?term={name_encoded}&l=english&cc=US"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            data = json.loads(urllib.request.urlopen(req).read())
            if data.get('total', 0) > 0:
                items = data['items']
                if interactive and len(items) > 1:
                    options = {f"{item['name']} ({item['id']})": str(item['id']) for item in items}
                    selected_text, ok = QInputDialog.getItem(self, "Select Game", f"Multiple matches found for '{name_str}'. Choose the correct one:", list(options.keys()), 0, False)
                    if ok and selected_text: return options[selected_text], selected_text.rsplit(' (', 1)[0]
                    else: return None, name_str
                else:
                    if not interactive:
                        for item in items:
                            if item['name'].lower() == name_str.lower(): return str(item['id']), item['name']
                    return str(items[0]['id']), items[0]['name']
        except: pass
        return None, name_str

    def batch_auto_fetch_specific(self, game_ids):
        games_to_fetch = [g for g in self.all_games if g[0] in game_ids]
        if not games_to_fetch: return
        progress = QProgressDialog("Fetching missing data...", "Cancel", 0, len(games_to_fetch), self)
        progress.setWindowTitle("Auto Fetch Data")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        api_key = self.db.get_setting("steamgriddb_api")
        for i, g in enumerate(games_to_fetch):
            progress.setValue(i); QApplication.processEvents()
            if progress.wasCanceled(): break
            game_id, name = g[0], g[6]
            if not name.strip(): continue
            needs_cover = not bool(g[16] and os.path.exists(str(g[16])))
            needs_screen = not bool(g[17] and os.path.exists(str(g[17]).split('|')[0]))
            needs_desc = not str(g[18] or "").strip()
            appid, resolved_name = self._select_steam_game(str(name), interactive=False)
            if appid:
                self._fetch_info_for_game(game_id, resolved_name, appid)
                if needs_desc: self._fetch_desc_for_game(game_id, resolved_name, appid)
                if needs_cover or needs_screen: self._fetch_art_for_game(game_id, resolved_name, api_key, needs_cover, needs_screen, appid)
        progress.setValue(len(games_to_fetch))
        self.fetch_data()
        QMessageBox.information(self, "Complete", "Finished fetching data for selected games!")

    def setup_detail_view(self):
        main_layout = QVBoxLayout(self.detail_view)
        back_btn = QPushButton("< Back to Library")
        back_btn.clicked.connect(self.close_detail_view)
        main_layout.addWidget(back_btn)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll_content = QWidget(); scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)
        content = QHBoxLayout(scroll_content)
        left_widget = QWidget(); left_panel = QVBoxLayout(left_widget)
        self.media_container_widget = QWidget()
        self.media_container_widget.setMinimumHeight(400)
        media_grid = QGridLayout(self.media_container_widget)
        media_grid.setContentsMargins(0,0,0,0)

        self.lbl_screenshot = AspectRatioLabel("Screenshot")
        self.lbl_screenshot.setStyleSheet("border: none; background-color: black;")
        media_grid.addWidget(self.lbl_screenshot, 0, 0)

        self.overlay_widget = QWidget()
        self.overlay_widget.setStyleSheet("background: transparent;")
        media_grid.addWidget(self.overlay_widget, 0, 0)

        overlay_lay = QGridLayout(self.overlay_widget)
        overlay_lay.setContentsMargins(20, 20, 20, 20)

        self.lblStoreIconOverlay = QLabel()
        self.lblStoreIconOverlay.setStyleSheet("color: white; font-size: 24px; font-weight: bold; background: transparent;")
        shadow_store = QGraphicsDropShadowEffect(self.lblStoreIconOverlay)
        shadow_store.setBlurRadius(8); shadow_store.setColor(QColor(0, 0, 0, 200)); shadow_store.setOffset(2, 2)
        self.lblStoreIconOverlay.setGraphicsEffect(shadow_store)
        overlay_lay.addWidget(self.lblStoreIconOverlay, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        overlay_lay.setRowStretch(1, 1)

        self.cover_wrapper = QWidget()
        self.cover_wrapper.setStyleSheet("background: transparent;")
        cover_wrap_lay = QVBoxLayout(self.cover_wrapper)
        cover_wrap_lay.setContentsMargins(0, 0, 0, 10)
        self.lbl_cover = AspectRatioLabel("CoverArt")
        self.lbl_cover.setFixedSize(160, 240)
        self.lbl_cover.setStyleSheet("border: 2px solid white; background-color: rgba(0,0,0,150);")
        cover_wrap_lay.addWidget(self.lbl_cover)
        overlay_lay.addWidget(self.cover_wrapper, 2, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)

        self.lblNameOverlay = QLabel("Game Title")
        self.lblNameOverlay.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self.lblNameOverlay.setWordWrap(True)
        self.lblNameOverlay.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Minimum)
        font_huge = QFont("Arial Black", 32, QFont.Weight.ExtraBold)
        if not font_huge.exactMatch(): font_huge = QFont("sans-serif", 32, QFont.Weight.Bold)
        self.lblNameOverlay.setFont(font_huge)
        self.lblNameOverlay.setStyleSheet("color: white; background: transparent;")
        shadow = QGraphicsDropShadowEffect(self.lblNameOverlay)
        shadow.setBlurRadius(12); shadow.setColor(QColor(0, 0, 0, 200)); shadow.setOffset(2, 2)
        self.lblNameOverlay.setGraphicsEffect(shadow)
        overlay_lay.addWidget(self.lblNameOverlay, 2, 1, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        left_panel.addWidget(self.media_container_widget, 1)

        img_controls_lay = QHBoxLayout()

        btn_screenshot_menu = QPushButton("Screenshot ▼")
        scr_menu = QMenu()
        act_scr_auto = QAction("Auto-Fetch", self); act_scr_auto.triggered.connect(lambda: self.auto_fetch_image("Screenshot"))
        act_scr_man = QAction("Manual Add", self); act_scr_man.triggered.connect(lambda: self.set_custom_image("Screenshot", self.lbl_screenshot))
        act_scr_clr = QAction("Clear Image", self); act_scr_clr.triggered.connect(lambda: self.clear_image("Screenshot", self.lbl_screenshot))
        scr_menu.addAction(act_scr_auto); scr_menu.addAction(act_scr_man); scr_menu.addSeparator(); scr_menu.addAction(act_scr_clr)
        btn_screenshot_menu.setMenu(scr_menu)

        btn_cover_menu = QPushButton("Cover ▼")
        cov_menu = QMenu()
        act_cov_auto = QAction("Auto-Fetch", self); act_cov_auto.triggered.connect(lambda: self.auto_fetch_image("CoverArt"))
        act_cov_man = QAction("Manual Add", self); act_cov_man.triggered.connect(lambda: self.set_custom_image("CoverArt", self.lbl_cover))
        act_cov_clr = QAction("Clear Image", self); act_cov_clr.triggered.connect(lambda: self.clear_image("CoverArt", self.lbl_cover))
        cov_menu.addAction(act_cov_auto); cov_menu.addAction(act_cov_man); cov_menu.addSeparator(); cov_menu.addAction(act_cov_clr)
        btn_cover_menu.setMenu(cov_menu)

        btn_cover_sgdb = QPushButton("SGDB")
        btn_cover_sgdb.setStyleSheet("QPushButton { background-color: #2a475e; color: white; font-weight: bold; } QPushButton:hover { background-color: #3b6283; }")
        btn_cover_sgdb.clicked.connect(self.open_sgdb_cover_dialog)

        img_controls_lay.addWidget(btn_screenshot_menu)
        img_controls_lay.addWidget(btn_cover_menu)
        img_controls_lay.addWidget(btn_cover_sgdb)
        left_panel.addLayout(img_controls_lay)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(5)
        links = [("YouTube", "fav_youtube.ico"), ("IsThereAnyDeal", "fav_isthereanydeal.png"), ("ProtonDB", "fav_protondb.ico"), ("HowLongToBeat", "fav_howlongtobeat.ico"), ("Steam", "fav_steam.ico"), ("GOG", "fav_GOG.ico")]
        for b, ico in links:
            btn = QPushButton(b)
            btn.setStyleSheet("QPushButton { font-size: 10px; font-weight: bold; padding: 4px; }")
            ico_path = resource_path(ico)
            if os.path.exists(ico_path): btn.setIcon(QIcon(ico_path))
            btn.clicked.connect(lambda checked, name=b: self.open_external_link(name))
            actions_layout.addWidget(btn)
        left_panel.addLayout(actions_layout)

        right_widget = QWidget(); right_panel = QFormLayout(right_widget)
        self.edit_name = QLineEdit(); self.edit_dev = QLineEdit(); self.edit_pub = QLineEdit(); self.edit_tags = QLineEdit(); self.edit_desc = QTextEdit()
        self.edit_store = QLineEdit(); self.edit_genre = QLineEdit(); self.edit_released = QLineEdit(); self.edit_meta = QLineEdit(); self.edit_hltb = QLineEdit()
        self.edit_coop = QLineEdit(); self.edit_numplayers = QLineEdit(); self.edit_similar = QLineEdit(); self.edit_acquired = QLineEdit()
        self.edit_launch_cmd = QLineEdit(); self.edit_launch_cmd.setPlaceholderText("e.g., steam steam://rungameid/12345 or /path/to/game.sh")

        btn_auto_all = QPushButton("✨ Auto-Fetch All Missing Data")
        btn_auto_all.setStyleSheet("QPushButton { background-color: #2b5797; color: white; font-weight: bold; padding: 6px; } QPushButton:hover { background-color: #3b6ba5; } QPushButton:pressed { background-color: #1a3a68; }")
        btn_auto_all.clicked.connect(self.auto_fetch_all_data)
        right_panel.addRow(btn_auto_all)

        status_layout = QHBoxLayout()
        self.chk_fav = QCheckBox("⭐ Favorite"); self.chk_want = QCheckBox("📌 Want to Play"); self.chk_playing = QCheckBox("▶️ Playing"); self.chk_finished = QCheckBox("✅ Finished")
        status_layout.addWidget(self.chk_fav); status_layout.addWidget(self.chk_want); status_layout.addWidget(self.chk_playing); status_layout.addWidget(self.chk_finished)

        right_panel.addRow(status_layout); right_panel.addRow("Game Name:", self.edit_name)
        right_panel.addRow("Store:", self.edit_store); right_panel.addRow("Genre:", self.edit_genre)
        right_panel.addRow("Released (Year):", self.edit_released); right_panel.addRow("Metacritic Score:", self.edit_meta)
        right_panel.addRow("HLTB:", self.edit_hltb); right_panel.addRow("Acquired (Date):", self.edit_acquired)
        right_panel.addRow("Developer:", self.edit_dev); right_panel.addRow("Publisher:", self.edit_pub)
        right_panel.addRow("Co-op (Local/Online):", self.edit_coop); right_panel.addRow("Number of Players:", self.edit_numplayers)
        right_panel.addRow("Tags:", self.edit_tags); right_panel.addRow("Popular Similar Games:", self.edit_similar)
        right_panel.addRow("Description:", self.edit_desc); right_panel.addRow("Launch Command:", self.edit_launch_cmd)

        content.addWidget(left_widget, 7); content.addWidget(right_widget, 3)

        bottom_btns = QHBoxLayout()
        launch_btn = QPushButton("🚀 Launch Game")
        launch_btn.setStyleSheet("QPushButton { background-color: #2e7d32; color: white; font-weight: bold; padding: 12px; font-size: 14px; } QPushButton:hover { background-color: #388e3c; } QPushButton:pressed { background-color: #1b5e20; }")
        launch_btn.clicked.connect(self.launch_current_game)
        save_btn = QPushButton("💾 Save Changes")
        save_btn.setStyleSheet("QPushButton { font-weight: bold; padding: 12px; font-size: 14px; }")
        save_btn.clicked.connect(self.save_detail_changes)
        del_btn = QPushButton("🗑️ Remove Game")
        del_btn.setStyleSheet("QPushButton { background-color: #d32f2f; color: white; font-weight: bold; padding: 12px; font-size: 14px; } QPushButton:hover { background-color: #e53935; } QPushButton:pressed { background-color: #b71c1c; }")
        del_btn.clicked.connect(self.delete_current_game)
        bottom_btns.addWidget(launch_btn); bottom_btns.addWidget(save_btn); bottom_btns.addWidget(del_btn)
        main_layout.addLayout(bottom_btns)


    def launch_game(self, game_id):
        game = next((g for g in self.all_games if g[0] == game_id), None)
        if not game: return
        cmd = str(game[27] or "").strip()
        if not cmd: return
        try:
            subprocess.Popen(shlex.split(cmd), start_new_session=True)
            self.setWindowState(Qt.WindowState.WindowMinimized)
        except Exception as e: QMessageBox.critical(self, "Launch Error", f"Failed to execute command.\n{e}")

    def launch_current_game(self):
        if not self.current_game_id: return
        cmd = self.edit_launch_cmd.text().strip()
        if not cmd:
            QMessageBox.warning(self, "Missing Command", "Please enter a valid Launch Command first and save.")
            return
        try:
            subprocess.Popen(shlex.split(cmd), start_new_session=True)
            self.setWindowState(Qt.WindowState.WindowMinimized)
        except Exception as e: QMessageBox.critical(self, "Launch Error", f"Failed to execute command.\n{e}")

    def import_sgdb_key(self):
        key, ok = QInputDialog.getText(self, "SteamGridDB Key", "Enter your private SteamGridDB API Key:\n(Get it from steamgriddb.com/profile/api)")
        if ok and key:
            self.db.set_setting("steamgriddb_api", key.strip())
            QMessageBox.information(self, "Saved", "SteamGridDB API Key saved securely to database!")

    def export_csv_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "GameManager_Export.csv", "CSV Files (*.csv)")
        if path:
            try:
                cursor = self.db.conn.cursor()
                cursor.execute("SELECT * FROM games")
                rows = cursor.fetchall(); headers = [desc[0] for desc in cursor.description]
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f); writer.writerow(headers); writer.writerows(rows)
                QMessageBox.information(self, "Success", "Library successfully exported to CSV!")
            except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def download_csv_template(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV Template", "GameManager_Template.csv", "CSV Files (*.csv)")
        if path:
            try:
                headers = ["Store", "FAV", "WANT TO PLAY", "Game", "METACRITIC", "RELEASED", "GENRE", "DEV", "PUB", "Acquired", "HLTB Main"]
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f); writer.writerow(headers)
                QMessageBox.information(self, "Success", "Template CSV generated successfully!")
            except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def save_backup(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Backup", "GameManager_Backup.zip", "ZIP Files (*.zip)")
        if path:
            try:
                files_to_zip = []
                if os.path.exists(DB_PATH): files_to_zip.append((DB_PATH, "games.db"))
                if os.path.exists(IMG_DIR):
                    for root, dirs, files in os.walk(IMG_DIR):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arcname = os.path.join("images", os.path.relpath(full_path, IMG_DIR))
                            files_to_zip.append((full_path, arcname))

                progress = QProgressDialog("Saving backup...", "Cancel", 0, len(files_to_zip), self)
                progress.setWindowTitle("Backup Status"); progress.setWindowModality(Qt.WindowModality.WindowModal)

                with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for i, (fp, arc) in enumerate(files_to_zip):
                        if progress.wasCanceled(): break
                        zipf.write(fp, arc); progress.setValue(i + 1); QApplication.processEvents()

                progress.setValue(len(files_to_zip))
                QMessageBox.information(self, "Success", "Database and Images successfully backed up to ZIP!")
            except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def recover_backup(self):
        path, _ = QFileDialog.getOpenFileName(self, "Recover Backup", "", "ZIP Files (*.zip)")
        if path:
            reply = QMessageBox.question(self, 'Confirm Restore', 'This will completely overwrite your current database and images. Are you sure?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self.db.conn.close()
                    with zipfile.ZipFile(path, 'r') as zipf:
                        info_list = zipf.infolist()
                        progress = QProgressDialog("Restoring backup...", "Cancel", 0, len(info_list), self)
                        progress.setWindowTitle("Restore Status"); progress.setWindowModality(Qt.WindowModality.WindowModal)
                        for i, info in enumerate(info_list):
                            if progress.wasCanceled(): break
                            zipf.extract(info, CONFIG_DIR); progress.setValue(i + 1); QApplication.processEvents()
                        progress.setValue(len(info_list))
                    self.db = GameDB(); self.fetch_data()
                    QMessageBox.information(self, "Success", "Backup completely restored!")
                except Exception as e: QMessageBox.critical(self, "Error", f"Failed to restore backup:\n{e}")

    def clear_browser_data(self):
        reply = QMessageBox.question(self, 'Clear Browser Data', 'Are you sure you want to clear all browser data and cookies? This will log you out of all stores.', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if hasattr(self, 'web_profile'):
                self.web_profile.cookieStore().deleteAllCookies()
                self.web_profile.clearHttpCache()
            self.db.set_setting("steam_connected", "0"); self.db.set_setting("gog_connected", "0"); self.db.set_setting("epic_connected", "0")
            self.update_connect_buttons()
            QMessageBox.information(self, "Cleared", "Browser data and cookies cleared successfully!")

    def delete_current_game(self):
        if not self.current_game_id: return
        self.delete_specific_games([self.current_game_id])
        self.current_game_id = None; self.stack.setCurrentIndex(0)

    def fetch_data(self):
        self.update_connect_buttons()
        self.all_games = self.db.get_all_games(); self.update_sidebar(); self.apply_filters()

    def update_sidebar(self):
        self.sidebar.clear(); stores = set(); genres = set()
        for g in self.all_games:
            if not str(g[6]).strip(): continue
            if g[1]: stores.add(g[1].strip())
            if g[9]: genres.add(g[9].strip())
        root_all = QTreeWidgetItem(self.sidebar, ["All Games"]); root_store = QTreeWidgetItem(self.sidebar, ["Stores"])
        for s in sorted(list(stores)): QTreeWidgetItem(root_store, [s])
        root_genre = QTreeWidgetItem(self.sidebar, ["Genres"])
        for g in sorted(list(genres)): QTreeWidgetItem(root_genre, [g])
        self.sidebar.expandAll()
        if not self.sidebar.currentItem(): self.sidebar.setCurrentItem(root_all)

    def filter_sidebar(self):
        query = self.search_bar.text().lower()
        for root in [self.sidebar.topLevelItem(1), self.sidebar.topLevelItem(2)]:
            if not root: continue
            for i in range(root.childCount()):
                child = root.child(i)
                child.setHidden(query not in child.text(0).lower() and query != "")

    def set_gallery_sort(self, s_type): self.gallery_sort = s_type; self.apply_filters()

    def open_sgdb_cover_dialog(self):
        api_key = self.db.get_setting("steamgriddb_api")
        if not api_key:
            QMessageBox.warning(self, "API Key Missing", "Please set your SteamGridDB API Key in Tools -> Import/Export -> Set SteamGridDB Key first.")
            return
        game_name = self.edit_name.text()
        if not game_name or not self.current_game_id: return
        dialog = SGDBImageDialog(self, game_name, api_key, self.current_game_id)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_image_path:
            self.db.update_game_info(self.current_game_id, "CoverArt", dialog.selected_image_path)
            self.lbl_cover.setPixmap(QPixmap(dialog.selected_image_path))
            self.lbl_cover.setText("")
            self.fetch_data()

    def close_detail_view(self):
        self.screen_timer.stop()
        self.stack.setCurrentIndex(0)

    def update_screenshot_display(self):
        if self.current_screens and len(self.current_screens) > 0:
            if os.path.exists(self.current_screens[self.current_screen_idx]):
                self.lbl_screenshot.setPixmap(QPixmap(self.current_screens[self.current_screen_idx]))
            else:
                self.lbl_screenshot.setText("Screenshot Missing"); self.lbl_screenshot.setPixmap(QPixmap())
        else:
            self.lbl_screenshot.setText("No Screenshot"); self.lbl_screenshot.setPixmap(QPixmap())

    def prev_screenshot(self):
        if self.current_screens and len(self.current_screens) > 1:
            self.current_screen_idx = (self.current_screen_idx - 1) % len(self.current_screens)
            self.update_screenshot_display()

    def next_screenshot(self):
        if self.current_screens and len(self.current_screens) > 1:
            self.current_screen_idx = (self.current_screen_idx + 1) % len(self.current_screens)
            self.update_screenshot_display()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_gallery()

    def update_connect_buttons(self):
        if not getattr(self, 'btn_sync_steam', None): return
        for store, btn, text in [("steam", self.btn_sync_steam, "Steam"), ("gog", self.btn_sync_gog, "GOG"), ("epic", self.btn_sync_epic, "Epic")]:
            if self.db.get_setting(f"{store}_connected") == "1" and store != "epic":
                btn.setText(f"✓ {text}")
                btn.setStyleSheet("QPushButton { background-color: #2e7d32; color: white; font-weight: bold; padding: 5px;} QPushButton:hover { background-color: #388e3c; }")
            else:
                btn.setText(text); btn.setStyleSheet("")

    def handle_steam_sync(self): self.open_sync_steam()

    def open_sync_steam(self):
        dialog = QDialog(self); dialog.setWindowTitle("Steam API Import"); dialog.resize(500, 250)
        layout = QVBoxLayout(dialog)
        info = QLabel("Valve's web logins are notoriously strict for scrapers. The most reliable way to import your Steam library is using the official Steam API.\n\n1. Get an API Key at: https://steamcommunity.com/dev/apikey\n2. Find your 17-digit SteamID64 (from your profile URL or steamid.io).\n\n* Your profile's 'Game Details' must be set to Public.")
        info.setWordWrap(True); info.setStyleSheet("font-size: 13px;"); layout.addWidget(info)

        form = QFormLayout()
        edit_steamid = QLineEdit(self.db.get_setting("steam_id")); edit_steamid.setPlaceholderText("e.g. 76561197960287930")
        edit_apikey = QLineEdit(self.db.get_setting("steam_api_key")); edit_apikey.setPlaceholderText("32-character hex key")
        form.addRow("SteamID64:", edit_steamid); form.addRow("Steam API Key:", edit_apikey)
        layout.addLayout(form)

        btn_fetch = QPushButton("Fetch Library via API")
        btn_fetch.setStyleSheet("QPushButton { background-color: #2e7d32; color: white; font-weight: bold; padding: 10px; font-size: 14px; } QPushButton:hover { background-color: #388e3c; } QPushButton:pressed { background-color: #1b5e20; }")

        def perform_fetch():
            steam_id = edit_steamid.text().strip(); api_key = edit_apikey.text().strip()
            if not steam_id or not api_key: QMessageBox.warning(dialog, "Missing Info", "Please enter both your SteamID and API Key."); return
            btn_fetch.setText("Fetching... Please wait"); btn_fetch.setEnabled(False); QApplication.processEvents()
            self.db.set_setting("steam_id", steam_id); self.db.set_setting("steam_api_key", api_key)

            url = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={api_key}&steamid={steam_id}&include_appinfo=true"
            try:
                data = json.loads(urllib.request.urlopen(urllib.request.Request(url)).read())
                if 'response' not in data or 'games' not in data['response']:
                    QMessageBox.warning(dialog, "Error", "Could not fetch games. Ensure your Steam profile 'Game Details' is set to Public.")
                    btn_fetch.setText("Fetch Library via API"); btn_fetch.setEnabled(True); return

                games = data['response']['games']
                cursor = self.db.conn.cursor()
                cursor.execute("SELECT SteamAppID FROM games WHERE Store='Steam'")
                existing = {str(r[0]).strip() for r in cursor.fetchall() if r[0]}
                added = 0

                for g in games:
                    appid = str(g['appid']); name = g.get('name', 'Unknown Game').strip()
                    if appid not in existing and name:
                        cursor.execute("INSERT INTO games (Store, Game, SteamAppID, LaunchCommand) VALUES (?, ?, ?, ?)", ("Steam", name, appid, f"steam steam://rungameid/{appid}"))
                        added += 1; existing.add(appid)
                self.db.conn.commit(); self.db.set_setting("steam_connected", "1"); self.update_connect_buttons(); self.fetch_data()
                dialog.accept()

                if added > 0:
                    QMessageBox.information(self, "Sync Complete", f"Imported {added} new games from Steam! Starting auto-fetch...")
                    self.batch_fetch_everything()
                else: self.statusBar().showMessage("Steam sync complete. No new games found.", 5000)
            except urllib.error.HTTPError as e:
                 QMessageBox.critical(dialog, "API Error", f"HTTP Error {e.code}: Make sure your API Key and SteamID are exactly correct.\n(If it says 403 Forbidden, your key is wrong. If it says 500, your profile is private).")
                 btn_fetch.setText("Fetch Library via API"); btn_fetch.setEnabled(True)
            except Exception as e:
                QMessageBox.critical(dialog, "API Error", f"Failed to connect to Steam API.\n\nError: {e}")
                btn_fetch.setText("Fetch Library via API"); btn_fetch.setEnabled(True)

        btn_fetch.clicked.connect(perform_fetch); layout.addWidget(btn_fetch)
        dialog.exec()

    def handle_gog_sync(self):
        if self.db.get_setting("gog_connected") == "1":
            self.statusBar().showMessage("Syncing GOG library in background...")
            browser = self.get_bg_browser()
            browser.loadFinished.connect(self._bg_gog_loaded)
            browser.setUrl(QUrl("https://www.gog.com/account/getFilteredProducts?hiddenFlag=0&mediaType=1&page=1&totalPages=50"))
        else: self.open_sync_gog()

    def _bg_gog_loaded(self, ok):
        try: self.get_bg_browser().loadFinished.disconnect(self._bg_gog_loaded)
        except TypeError: pass
        if ok: self.get_bg_browser().page().toHtml(self._process_bg_gog)
        else: self.db.set_setting("gog_connected", "0"); self.update_connect_buttons(); self.open_sync_gog()

    def _process_bg_gog(self, html):
        try:
            clean_json = html[html.find('{'):html.rfind('}')+1]
            data = json.loads(clean_json)
            if 'products' not in data: self.db.set_setting("gog_connected", "0"); self.update_connect_buttons(); self.open_sync_gog(); return
            self.process_gog_data(data['products'])
        except: self.db.set_setting("gog_connected", "0"); self.update_connect_buttons(); self.open_sync_gog()

    def open_sync_gog(self):
        self.sync_dialog = SyncBrowser("https://www.gog.com/login", "gog", self.get_web_profile(), self)
        self.sync_dialog.btn_fetch.clicked.connect(self.do_manual_gog_sync)
        self.sync_dialog.exec()

    def do_manual_gog_sync(self):
        self.sync_dialog.browser.setUrl(QUrl("https://www.gog.com/account/getFilteredProducts?hiddenFlag=0&mediaType=1&page=1&totalPages=50"))
        QTimer.singleShot(3000, lambda: self.sync_dialog.browser.page().toHtml(self._process_manual_gog))

    def _process_manual_gog(self, html):
        try:
            clean_json = html[html.find('{'):html.rfind('}')+1]
            data = json.loads(clean_json)
            if 'products' not in data:
                QMessageBox.warning(self.sync_dialog, "Not Ready", "Could not extract GOG games. Ensure you are completely logged in.")
                return
            self.sync_dialog.accept()
            self.process_gog_data(data['products'])
        except Exception as e: QMessageBox.warning(self.sync_dialog, "Error", f"Failed to read GOG data.\n{e}")

    def process_gog_data(self, products):
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT Game FROM games WHERE Store='GOG'")
            existing = {str(r[0]).strip().lower() for r in cursor.fetchall() if r[0]}
            added = 0
            for g in products:
                name = str(g.get('title', '')).strip()
                if name and name.lower() not in existing:
                    cursor.execute("INSERT INTO games (Store, Game) VALUES (?, ?)", ("GOG", name))
                    added += 1
            self.db.conn.commit(); self.db.set_setting("gog_connected", "1"); self.update_connect_buttons()
            self.fetch_data()
            if added > 0:
                QMessageBox.information(self, "Sync Complete", f"Imported {added} new games from GOG! Starting auto-fetch...")
                self.batch_fetch_everything()
            else: self.statusBar().showMessage("GOG sync complete. No new games found.", 5000)
        except Exception as e: QMessageBox.critical(self, "Error", f"Failed to parse library.\n{e}")

    def open_sync_epic(self):
        QMessageBox.information(self, "Epic Games Limitation", "Due to Epic Games' aggressive anti-bot protection (Cloudflare), embedded browsers are actively blocked from fetching your library via their secure APIs.\n\nTo import your Epic games, please export your library as a CSV using a community tool like Heroic Games Launcher or GOG Galaxy, and use the 'Import CSV' function.")
        self.update_connect_buttons()

    def clear_image(self, field, label):
        if not self.current_game_id: return
        reply = QMessageBox.question(self, 'Clear Image', f'Are you sure you want to clear {field}?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.update_game_info(self.current_game_id, field, "")
            if field == "Screenshot":
                self.current_screens = []
                self.current_screen_idx = 0
                self.update_screenshot_display()
            else:
                label.setPixmap(QPixmap())
                label.setText(f"No {field}")
            self.fetch_data()

    def set_custom_image(self, field, label):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if file_path and self.current_game_id:
            ext = os.path.splitext(file_path)[1]; new_path = os.path.join(IMG_DIR, f"{self.current_game_id}_{field}{ext}")
            shutil.copy(file_path, new_path)
            if field == "Screenshot":
                current_val = self.db.conn.cursor().execute("SELECT Screenshot FROM games WHERE id=?", (self.current_game_id,)).fetchone()[0]
                new_val = f"{current_val}|{new_path}" if current_val else new_path
                self.db.update_game_info(self.current_game_id, field, new_val)
                self.current_screens = new_val.split('|')
                self.current_screen_idx = len(self.current_screens) - 1
                self.update_screenshot_display()
            else:
                self.db.update_game_info(self.current_game_id, field, new_path)
                label.setPixmap(QPixmap(new_path)); label.setText("")
            self.fetch_data()


    def auto_fetch_all_data(self):
        if not self.current_game_id: return
        name = self.edit_name.text()
        self.db.update_game_info(self.current_game_id, "Game", name)
        api_key = self.db.get_setting("steamgriddb_api")
        game = next((g for g in self.all_games if g[0] == self.current_game_id), None)
        needs_cover = not bool(game[16] and os.path.exists(str(game[16]))) if game else True
        needs_screen = not bool(game[17] and os.path.exists(str(game[17]).split('|')[0])) if game else True

        appid, resolved_name = self._select_steam_game(name, interactive=True)
        if not appid: return

        self._fetch_info_for_game(self.current_game_id, resolved_name, appid)
        desc = self._fetch_desc_for_game(self.current_game_id, resolved_name, appid)
        if desc: self.edit_desc.setHtml(desc)
        self._fetch_art_for_game(self.current_game_id, resolved_name, api_key, needs_cover, needs_screen, appid)
        self.fetch_data(); self.open_detail_view(self.current_game_id)
        QMessageBox.information(self, "Success", "Fetched all available missing data and artwork for this game!")

    def batch_fetch_everything(self):
        games_to_fetch = self.all_games
        if not games_to_fetch: return
        progress = QProgressDialog("Fetching ALL missing data...", "Cancel", 0, len(games_to_fetch), self)
        progress.setWindowTitle("Batch Fetch Everything"); progress.setWindowModality(Qt.WindowModality.WindowModal); progress.setAutoClose(True)
        api_key = self.db.get_setting("steamgriddb_api")
        for i, g in enumerate(games_to_fetch):
            progress.setValue(i); QApplication.processEvents()
            if progress.wasCanceled(): break
            game_id, name = g[0], g[6]
            if not name.strip(): continue
            needs_cover = not bool(g[16] and os.path.exists(str(g[16])))
            needs_screen = not bool(g[17] and os.path.exists(str(g[17]).split('|')[0]))
            needs_desc = not str(g[18] or "").strip()
            appid, resolved_name = self._select_steam_game(str(name), interactive=False)
            if appid:
                self._fetch_info_for_game(game_id, resolved_name, appid)
                if needs_desc: self._fetch_desc_for_game(game_id, resolved_name, appid)
                if needs_cover or needs_screen: self._fetch_art_for_game(game_id, resolved_name, api_key, needs_cover, needs_screen, appid)
        progress.setValue(len(games_to_fetch))
        self.fetch_data();
        if self.current_game_id: self.open_detail_view(self.current_game_id)
        QMessageBox.information(self, "Batch Complete", "Finished fetching all missing data!")

    def _fetch_info_for_game(self, game_id, name_str, appid=None):
        try:
            if not appid:
                appid, _ = self._select_steam_game(name_str, interactive=False)
            if not appid: return

            d_url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
            d_data = json.loads(urllib.request.urlopen(urllib.request.Request(d_url)).read())
            if str(appid) in d_data and d_data[str(appid)]['success']:
                app = d_data[str(appid)]['data']
                genre_str = ", ".join([g['description'] for g in app.get('genres', [])])
                date_str = app.get('release_date', {}).get('date', ''); year_str = date_str[-4:] if len(date_str) >= 4 else date_str
                meta_score = str(app.get('metacritic', {}).get('score', ''))
                dev = ", ".join(app.get('developers', [])); pub = ", ".join(app.get('publishers', []))
                cats = [c['description'] for c in app.get('categories', [])]
                coop_str = "None"
                if "Online Co-op" in cats and "Shared/Split Screen Co-op" in cats: coop_str = "Local & Online"
                elif "Online Co-op" in cats: coop_str = "Online"
                elif "Shared/Split Screen Co-op" in cats: coop_str = "Local"
                elif "Co-op" in cats: coop_str = "Online/Local"
                players_str = "Single-player" if "Single-player" in cats else ""
                if "Multi-player" in cats: players_str += ", Multi-player" if players_str else "Multi-player"
                tags_str = ", ".join(cats[:5])
                if genre_str: self.db.update_game_info(game_id, "GENRE", genre_str)
                if year_str: self.db.update_game_info(game_id, "RELEASED", year_str)
                if meta_score: self.db.update_game_info(game_id, "METACRITIC", meta_score)
                if dev: self.db.update_game_info(game_id, "DEV", dev)
                if pub: self.db.update_game_info(game_id, "PUB", pub)
                if coop_str != "None": self.db.update_game_info(game_id, "Coop", coop_str)
                if players_str: self.db.update_game_info(game_id, "NumPlayers", players_str)
                if tags_str: self.db.update_game_info(game_id, "Tags", tags_str)
        except: pass

    def batch_fetch_info(self):
        games_to_fetch = self.all_games
        if not games_to_fetch: return
        progress = QProgressDialog("Fetching metadata...", "Cancel", 0, len(games_to_fetch), self)
        progress.setWindowTitle("Batch Fetch Info"); progress.setWindowModality(Qt.WindowModality.WindowModal); progress.setAutoClose(True)
        for i, g in enumerate(games_to_fetch):
            progress.setValue(i); QApplication.processEvents()
            if progress.wasCanceled(): break
            game_id, name = g[0], g[6]
            if not name.strip(): continue
            appid, resolved_name = self._select_steam_game(str(name), interactive=False)
            if appid: self._fetch_info_for_game(game_id, resolved_name, appid)
        progress.setValue(len(games_to_fetch))
        self.fetch_data();
        if self.current_game_id: self.open_detail_view(self.current_game_id)
        QMessageBox.information(self, "Batch Complete", "Finished fetching game information!")

    def _fetch_art_for_game(self, game_id, name_str, api_key, fetch_cover, fetch_screen, appid=None):
        name_encoded = urllib.parse.quote(name_str)
        try:
            if fetch_cover and api_key:
                headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
                try:
                    req1 = urllib.request.Request(f"https://www.steamgriddb.com/api/v2/search/autocomplete/{name_encoded}", headers=headers)
                    resp1 = json.loads(urllib.request.urlopen(req1).read())
                    if resp1.get('success') and resp1.get('data'):
                        sgdb_id = resp1['data'][0]['id']
                        req2 = urllib.request.Request(f"https://www.steamgriddb.com/api/v2/grids/game/{sgdb_id}?dimensions=600x900", headers=headers)
                        resp2 = json.loads(urllib.request.urlopen(req2).read())
                        if resp2.get('success') and resp2.get('data'):
                            img_url = resp2['data'][0]['url']; path = os.path.join(IMG_DIR, f"{game_id}_CoverArt.jpg")
                            req_img = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
                            with urllib.request.urlopen(req_img) as response, open(path, 'wb') as out_file:
                                shutil.copyfileobj(response, out_file)
                            self.db.update_game_info(game_id, "CoverArt", path); fetch_cover = False
                except: pass

            if fetch_cover or fetch_screen:
                if not appid:
                    appid, _ = self._select_steam_game(name_str, interactive=False)
                if not appid: return

                d_url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
                d_data = json.loads(urllib.request.urlopen(urllib.request.Request(d_url)).read())
                if str(appid) in d_data and d_data[str(appid)]['success']:
                    app = d_data[str(appid)]['data']
                    if fetch_cover:
                        vert_url = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900.jpg"
                        try:
                            urllib.request.urlopen(vert_url); path = os.path.join(IMG_DIR, f"{game_id}_CoverArt.jpg")
                            urllib.request.urlretrieve(vert_url, path); self.db.update_game_info(game_id, "CoverArt", path)
                        except:
                            c_url = app.get('header_image', '')
                            if c_url:
                                path = os.path.join(IMG_DIR, f"{game_id}_CoverArt.jpg"); urllib.request.urlretrieve(c_url, path)
                                self.db.update_game_info(game_id, "CoverArt", path)
                    if fetch_screen:
                        screens = app.get('screenshots', [])
                        if screens:
                            saved_screens = []
                            for idx, sc in enumerate(screens[:5]):
                                s_url = sc['path_full']; path = os.path.join(IMG_DIR, f"{game_id}_Screenshot_{idx}.jpg")
                                urllib.request.urlretrieve(s_url, path); saved_screens.append(path)
                            if saved_screens: self.db.update_game_info(game_id, "Screenshot", "|".join(saved_screens))
        except: pass

    def auto_fetch_image(self, field):
        name = self.edit_name.text()
        api_key = self.db.get_setting("steamgriddb_api")
        needs_cover = (field == "CoverArt"); needs_screen = (field == "Screenshot")
        if needs_cover and not api_key: QMessageBox.information(self, "API Notice", "SteamGridDB requires a private API Key. Falling back to Steam API for Cover Art...")
        appid, resolved_name = self._select_steam_game(name, interactive=True)
        if not appid: return
        self._fetch_art_for_game(self.current_game_id, resolved_name, api_key, needs_cover, needs_screen, appid)
        self.fetch_data(); self.open_detail_view(self.current_game_id)
        QMessageBox.information(self, "Done", f"{field} fetch attempt complete!")

    def batch_fetch_art(self):
        games_to_fetch = [g for g in self.all_games if (not g[16] or not os.path.exists(str(g[16]))) or (not g[17] or not os.path.exists(str(g[17]).split('|')[0]))]
        if not games_to_fetch:
            QMessageBox.information(self, "Done", "All games already have complete artwork!"); return
        progress = QProgressDialog("Fetching artwork...", "Cancel", 0, len(games_to_fetch), self)
        progress.setWindowTitle("Batch Fetch Art"); progress.setWindowModality(Qt.WindowModality.WindowModal); progress.setAutoClose(True)
        api_key = self.db.get_setting("steamgriddb_api")
        for i, g in enumerate(games_to_fetch):
            progress.setValue(i); QApplication.processEvents()
            if progress.wasCanceled(): break
            game_id, name = g[0], g[6]
            if not name.strip(): continue
            needs_cover = not bool(g[16] and os.path.exists(str(g[16])))
            needs_screen = not bool(g[17] and os.path.exists(str(g[17]).split('|')[0]))
            appid, resolved_name = self._select_steam_game(str(name), interactive=False)
            if appid: self._fetch_art_for_game(game_id, resolved_name, api_key, needs_cover, needs_screen, appid)
        progress.setValue(len(games_to_fetch))
        self.fetch_data()
        if self.current_game_id: self.open_detail_view(self.current_game_id)
        QMessageBox.information(self, "Batch Complete", "Finished checking and fetching artwork!")

    def _fetch_desc_for_game(self, game_id, name_str, appid=None):
        try:
            if not appid:
                appid, _ = self._select_steam_game(name_str, interactive=False)
            if not appid: return None
            d_url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
            d_data = json.loads(urllib.request.urlopen(urllib.request.Request(d_url)).read())
            if str(appid) in d_data and d_data[str(appid)]['success']:
                desc = d_data[str(appid)]['data'].get('short_description', '')
                if desc:
                    self.db.update_game_info(game_id, "Description", desc)
                    return desc
        except: pass
        return None

    def auto_fetch_desc(self):
        appid, resolved_name = self._select_steam_game(self.edit_name.text(), interactive=True)
        if not appid: return
        desc = self._fetch_desc_for_game(self.current_game_id, resolved_name, appid)
        if desc: self.edit_desc.setHtml(desc); self.fetch_data(); QMessageBox.information(self, "Success", "Description updated!")
        else: QMessageBox.warning(self, "Failed", "Could not find description online.")

    def batch_fetch_desc(self):
        games_to_fetch = [g for g in self.all_games if not str(g[18] or "").strip()]
        if not games_to_fetch: QMessageBox.information(self, "Done", "All games already have descriptions!"); return
        progress = QProgressDialog("Fetching descriptions...", "Cancel", 0, len(games_to_fetch), self)
        progress.setWindowTitle("Batch Fetch Descriptions"); progress.setWindowModality(Qt.WindowModality.WindowModal); progress.setAutoClose(True)
        for i, g in enumerate(games_to_fetch):
            progress.setValue(i); QApplication.processEvents()
            if progress.wasCanceled(): break
            game_id, name = g[0], g[6]
            if not name.strip(): continue
            appid, resolved_name = self._select_steam_game(str(name), interactive=False)
            if appid: self._fetch_desc_for_game(game_id, resolved_name, appid)
        progress.setValue(len(games_to_fetch))
        self.fetch_data()
        if self.current_game_id: self.open_detail_view(self.current_game_id)
        QMessageBox.information(self, "Batch Complete", "Finished fetching descriptions!")

    def open_external_link(self, platform):
        game_name = urllib.parse.quote(self.edit_name.text())
        urls = {
            "YouTube": f"https://www.youtube.com/results?search_query={game_name}+gameplay",
            "IsThereAnyDeal": f"https://isthereanydeal.com/search/?q={game_name}",
            "ProtonDB": f"https://www.protondb.com/search?q={game_name}",
            "HowLongToBeat": f"https://howlongtobeat.com/?q={game_name}",
            "Steam": f"https://store.steampowered.com/search/?term={game_name}",
            "GOG": f"https://www.gog.com/games?query={game_name}"
        }
        browser = InternalBrowser(urls[platform], platform, self.get_web_profile(), self)
        browser.exec()

    def add_game_auto(self):
        text, ok = QInputDialog.getText(self, "Add Game", "Enter Game Name (Will auto-fetch from Steam):")
        if ok and text:
            appid, resolved_name = self._select_steam_game(text, interactive=True)
            if not appid: return
            try:
                d_url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
                d_data = json.loads(urllib.request.urlopen(urllib.request.Request(d_url)).read())
                if str(appid) in d_data and d_data[str(appid)]['success']:
                    app = d_data[str(appid)]['data']; name = app.get('name', text)
                    dev = ", ".join(app.get('developers', [])); pub = ", ".join(app.get('publishers', []))
                    desc = app.get('short_description', '')

                    cover_path = ""
                    vert_url = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900.jpg"
                    try:
                        urllib.request.urlopen(vert_url); cover_path = os.path.join(IMG_DIR, f"{appid}_cover.jpg")
                        urllib.request.urlretrieve(vert_url, cover_path)
                    except:
                        cover_url = app.get('header_image', '')
                        if cover_url:
                            cover_path = os.path.join(IMG_DIR, f"{appid}_cover.jpg")
                            urllib.request.urlretrieve(cover_url, cover_path)

                    cursor = self.db.conn.cursor()
                    cursor.execute("INSERT INTO games (Game, DEV, PUB, Description, CoverArt, Store, SteamAppID, LaunchCommand) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (name, dev, pub, desc, cover_path, "Steam", str(appid), f"steam steam://rungameid/{appid}"))
                    self.db.conn.commit(); self.fetch_data(); QMessageBox.information(self, "Success", f"'{name}' added automatically!"); return
            except Exception as e: QMessageBox.warning(self, "API Error", f"Could not fetch data automatically.\n{e}")

    def add_game_manual(self):
        cursor = self.db.conn.cursor()
        cursor.execute("INSERT INTO games (Game) VALUES (?)", ("New Game Entry",))
        self.db.conn.commit()
        new_id = cursor.lastrowid
        self.fetch_data(); self.open_detail_view(new_id)

    def import_csv_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select CSV", "", "CSV Files (*.csv)")
        if file_path:
            for enc in ['utf-8-sig', 'cp1252', 'latin-1']:
                try:
                    with open(file_path, newline='', encoding=enc) as f:
                        sample = f.read(2048); f.seek(0)
                        reader = csv.DictReader(f, dialect=csv.Sniffer().sniff(sample) if sample else csv.excel)
                        cursor = self.db.conn.cursor()
                        cursor.execute("SELECT Game, Store FROM games")
                        existing = {(str(r[0]).strip().lower(), str(r[1]).strip().lower()) for r in cursor.fetchall() if r[0]}
                        count = 0; skipped = 0
                        insert_query = "INSERT INTO games (Store, FAV, WANT_TO_PLAY, Game, METACRITIC, RELEASED, GENRE, DEV, PUB, Acquired, HLTB_Main) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                        for row in reader:
                            g_name = row.get('Game','').strip(); s_name = row.get('Store','').strip()
                            if not g_name: continue
                            if (g_name.lower(), s_name.lower()) in existing:
                                skipped += 1; continue
                            cursor.execute(insert_query, (s_name, row.get('FAV',''), row.get('WANT TO PLAY',''), g_name, row.get('METACRITIC',''), row.get('RELEASED',''), row.get('GENRE',''), row.get('DEV',''), row.get('PUB',''), row.get('Acquired',''), row.get('HLTB Main',''))); count += 1
                            existing.add((g_name.lower(), s_name.lower()))
                    self.db.conn.commit(); self.fetch_data()
                    msg = f"Imported {count} new games!"
                    if skipped > 0: msg += f"\nSkipped {skipped} duplicate entries."
                    QMessageBox.information(self, "Success", msg); return
                except UnicodeDecodeError: continue
                except Exception as e: QMessageBox.critical(self, "Error", str(e)); return
            QMessageBox.critical(self, "Error", "Could not read encoding.")

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()
        self.apply_filters()

    def apply_theme(self):
        if self.is_dark_mode: self.setStyleSheet("QMainWindow, QWidget, QDialog, QScrollArea { background-color: #121212; color: #E0E0E0; border: none; } QTableWidget, QListWidget, QTreeWidget { background-color: #1E1E1E; color: #E0E0E0; gridline-color: #333; } QListWidget::item:hover { background-color: #2A2A2A; border-radius: 5px; } QListWidget::item:selected { background-color: #3A3A3A; border-radius: 5px; } QLineEdit, QTextEdit { background-color: #2D2D2D; color: #FFF; border: 1px solid #444; } QPushButton { background-color: #333; color: #FFF; border: 1px solid #555; padding: 5px; font-weight: bold; } QPushButton:hover { background-color: #444; } QPushButton:pressed { background-color: #222; border: 1px inset #777; } QGroupBox { border: 1px solid #444; font-weight: bold; margin-top: 2ex; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; }")
        else: self.setStyleSheet("QMainWindow, QWidget, QDialog, QScrollArea { background-color: #F5F5F5; color: #000; border: none; } QTableWidget, QListWidget, QTreeWidget { background-color: #FFFFFF; color: #000; } QListWidget::item:hover { background-color: #E0E0E0; border-radius: 5px; } QListWidget::item:selected { background-color: #D0D0D0; border-radius: 5px; } QLineEdit, QTextEdit { background-color: #FFFFFF; color: #000; border: 1px solid #CCC; } QPushButton { background-color: #E0E0E0; color: #000; border: 1px solid #AAA; padding: 5px; font-weight: bold; } QPushButton:hover { background-color: #D0D0D0; } QPushButton:pressed { background-color: #B0B0B0; border: 1px inset #888; } QGroupBox { border: 1px solid #CCC; font-weight: bold; margin-top: 2ex; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; }")

if __name__ == '__main__':
    app = QApplication(sys.argv)

    icon_path = resource_path("icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    splash = SplashScreen()
    splash.show()

    for i in range(1, 101):
        splash.prog.setValue(i)
        app.processEvents()
        time.sleep(0.03)

    window = GameLibraryApp()
    splash.close()
    window.show()
    sys.exit(app.exec())
