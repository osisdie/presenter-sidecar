[English](README.md) | **繁體中文**

# presenter-sidecar

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg?logo=python&logoColor=white)](requirements-windows.txt)
[![Platform: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6.svg?logo=windows&logoColor=white)](#系統需求)
[![CI](https://github.com/osisdie/presenter-sidecar/actions/workflows/ci.yml/badge.svg)](https://github.com/osisdie/presenter-sidecar/actions/workflows/ci.yml)
[![AI helper: optional](https://img.shields.io/badge/AI%20helper-optional-8A63D2.svg)](#講者面板)

**只投影一個視窗，其他的都留在自己的螢幕上。**

![presenter-sidecar：筆電上是你的視窗和私人面板；投影只顯示選定的視窗和大游標；遠端看到螢幕 2](docs/media/layout.svg)

presenter-sidecar 把你選定的「一個視窗」即時投到投影機，加上大游標；筆電上另有一個只有你看得到的側邊面板：
會跟著投影頁面自動翻頁的講稿、各段計時，以及可選用的唯讀 AI 助手。

| 投影：只有選定的視窗，等比縮放加黑邊，加上游標光圈與點擊波紋 | 私人面板：講稿跟著投影的分頁切換 |
|---|---|
| ![投影畫面：範例網頁左右有黑邊，按鈕上有黃色游標光圈](docs/media/projector.png) | <img src="docs/media/panel.png" width="300" alt="側邊面板顯示 Demo C 講稿、步驟列停在第 2 步、段落計時和自動跟隨提示"> |

<details><summary>自動跟隨動畫（GIF）</summary>

<img src="docs/media/auto-follow.gif" width="300" alt="投影的分頁換了，面板講稿從 Demo A 跳到 Demo B、Demo C 再到 Q&amp;A">

</details>

所有截圖都是用 [`scripts/media/render_media.py`](scripts/media/render_media.py) 從 [`examples/`](examples/) 的虛構內容產生的。

## 目錄

- [為什麼需要它](#為什麼需要它)
- [和其他做法比較](#和其他做法比較)
- [系統需求](#系統需求)
- [快速開始](#快速開始)
- [熱鍵](#熱鍵)
- [選擇投影來源](#選擇投影來源)
- [講者面板](#講者面板)
- [用範例網站試講稿自動跟隨](#用範例網站試講稿自動跟隨)
- [設定](#設定)
- [選用：在 WSL 執行面板伺服器](#選用在-wsl-執行面板伺服器)
- [在 Meet、Teams、Zoom 分享](#在-meetteamszoom-分享)
- [限制](#限制)
- [隱私與安全](#隱私與安全)
- [開發](#開發)
- [授權](#授權)

## 為什麼需要它

用筆電接投影機、設成「延伸」時，投影上是一整個桌面：通知、剛用過的終端機、不小心切到的分頁都會被看到。
設成「同步顯示」更糟，觀眾連你的講稿都看得到。

presenter-sidecar 把投影當成「視窗鏡像」：你選一個視窗（通常是瀏覽器），投影上就只畫那個視窗，等比縮放、加黑邊。
終端機、聊天軟體、講稿和面板永遠不會出現在投影上，就算它們在筆電上蓋住了來源視窗也一樣。

## 和其他做法比較

| | presenter-sidecar | OBS「視窗投影」 | PowerPoint 簡報者檢視畫面 | 同步顯示 |
|---|---|---|---|---|
| 只顯示一個視窗 | ✅ | ✅（要先建場景） | 只有投影片 | ❌ 整個螢幕 |
| 任何程式、任何網頁都能用 | ✅ | ✅ | ❌ | ✅ |
| 自動跟隨彈窗（例如登入授權視窗） | ✅ 自動 | ❌ 要另外加來源 | 不適用 | ✅ |
| 投影上的大游標、聚光燈、點擊波紋 | ✅ | 要裝外掛 | 雷射筆 | ❌ |
| 跟著投影頁面切換的私人講稿 | ✅ | ❌ | ✅（只限投影片） | ❌ |
| 各段計時 | ✅ | ❌ | 一個計時器 | ❌ |
| 設定 | `start.bat` | 場景與來源 | 內建 | 內建 |

錄影、直播用 OBS 比較好；全部內容都在一份投影片裡時，PowerPoint 的簡報者檢視畫面比較好。
presenter-sidecar 適合在瀏覽器、文件、終端機示範和實際 App 之間來回切換的演講與工作坊。

## 系統需求

- **Windows 10 2004 以上或 Windows 11**，接第二個螢幕（投影機或螢幕），顯示模式設為**延伸**。
- Windows 版 **Python 3.11 以上**（[python.org](https://www.python.org/downloads/) 或 `py` 啟動器）。以 Python 3.14 測試。
- **Google Chrome 或 Microsoft Edge**（當作面板視窗）。
- 選用：已登入的 [Claude Code CLI](https://docs.claude.com/en/docs/claude-code)（AI 助手用）。

投影鏡像只能在 Windows 上執行（用到 Win32 和 Windows Graphics Capture）。面板伺服器只用 Python 標準函式庫，哪裡都能跑。

## 快速開始

```bat
git clone https://github.com/osisdie/presenter-sidecar.git
cd presenter-sidecar
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
.venv\Scripts\python.exe mirror.py --selfcheck
```

接著雙擊 **`start.bat`**。第一次執行會把 `config.example.json` 複製成 `config.json`，然後：

1. 啟動面板伺服器 `http://127.0.0.1:8765`；
2. 在筆電螢幕右側開一個 Chrome／Edge `--app` 視窗當面板，使用獨立的瀏覽器設定檔
   （`%LOCALAPPDATA%\presenter-sidecar-panel`），不影響你平常的瀏覽器；
3. 啟動 `mirror.py`，把來源視窗投到第二個螢幕。

點一下要投影的視窗，按 **F7**；按 **Shift+F7** 把它擺到面板左邊。結束時雙擊 **`stop.bat`**，只會關掉 `start.bat` 開的東西。

## 熱鍵

全域熱鍵，焦點在哪個視窗都有效。全部可以在 `config.json` 的 `hotkeys` 修改（例如 F7 已被其他程式佔用時；
註冊失敗的熱鍵會顯示在面板上）。

| 預設 | 作用（`hotkeys` 的鍵） |
|---|---|
| **F7** | 把目前的前景視窗設為投影來源（`pick`） |
| **Shift+F7** | 把來源視窗搬回筆電螢幕、面板左邊（`bring`） |
| **F8** | 凍結／解除凍結投影。要輸入私人資料前先按（`freeze`） |
| **F9** | 「請稍候」畫面／切回（`blank`） |
| **F10** | 游標樣式：光圈 ↔ 聚光燈（`style`） |
| **Ctrl+Alt+PgDn／PgUp** | 講稿下一節／上一節，不必切到面板（`next`／`prev`） |
| **Ctrl+Alt+P** | 自動跟隨彈窗：開／關（`popups`） |
| **Ctrl+Alt+L** | 滑鼠鎖在筆電螢幕：開／關（`clip`） |
| **Ctrl+Alt+Q** | 結束投影（`quit`；面板還會開著，全部關閉請用 `stop.bat`） |

- 大游標只在**游標真的在來源視窗上**時才畫；游標在面板或擋在前面的視窗上時不畫。
- 左鍵是紅色波紋、右鍵是藍色波紋；按住左鍵時光圈外框變紅。
- 滑鼠鎖定（預設開）時，觀眾不會看到真游標跑到投影上。

## 選擇投影來源

- **啟動時**：找標題包含 `source_title_contains` 任一項的第一個視窗。預設是空清單，會用啟動當下的前景視窗
  （終端機除外）；隨時可以按 F7 換。
- **鎖定視窗本身**：選定後就跟著那個視窗，切分頁、標題改變都不會跑掉；移動、縮放、最大化都會跟上。
- **縮小或關閉**：投影停在最後一格，只有面板會顯示提醒。
- **永遠不投影**：終端機類（`never_source_classes`：Windows Terminal、主控台、mintty…）、面板、桌面和工作列。
- **彈窗**（`follow_popups`，Ctrl+Alt+P 切換）：來源視窗的同一個程式**新開**一個獨立視窗（例如 OAuth 登入視窗）時，
  投影自動切過去，關掉後切回來源。選單、提示框、網址列下拉清單、工具視窗、小於 `popup_min_size` 的視窗、
  在其他螢幕上的視窗都不會被跟。
- **擷取方式**（`capture_backend`，預設 `auto`）：
  1. **WGC**（Windows Graphics Capture）：直接擷取視窗本身，被擋住也完整；畫面沒變化時不耗 CPU。
  2. **PrintWindow**（`PW_RENDERFULLCONTENT`）：WGC 不能用時改用這個，被擋住也完整。
  3. **mss**：最後的備援，只在視窗完全沒被擋住時擷取。

## 講者面板

只有你看得到的 Chrome／Edge 小視窗，標題是「Presenter Panel」。

**講稿**
- 讀 `notes_files` 列出的 Markdown 檔，每個 `##` 標題是一節。用 ←／→、PgUp／PgDn、下拉選單，
  或在任何地方按 Ctrl+Alt+PgDn／PgUp 翻頁。A−／A+ 調字體大小。
- `notes_files` 存檔即生效：在 `config.json` 加減講稿檔，回面板按 F5 就好，不用重新啟動。
- **步驟導覽**（節選單下面第二排：◀ `4. 重點回顧（4/4）` ▶）：一節裡面，**整段只有一行粗體編號標題**
  的段落就是一步：

  ```markdown
  **1. 新增一盆植物**

  - 名字、品種、盆子大小。

  **2. 觸發一次提醒**
  ```

  沒有這種段落的節，改用 `###` 小標當步驟；兩種都沒有就不顯示這一排。
  半形句點後面要空一格才算步驟（`**2.5 million**` 不算）；全形 `3．` 後面可以不空格。
  - 用 ↑／↓ 或 K／J（或下拉選單、◀ ▶）換上一步／下一步。選到的那一步會捲到講稿最上面，左邊出現黃色框線；
    自己捲動時，下拉選單也會跟著換。
  - 某一步比講稿畫面還高時：↓ 先在這一步裡往下捲（每次最多 80% 畫面，捲到這一步結尾為止），再換下一步；↑ 也一樣先捲回這一步的標題。
  - 換節時從步驟 1 開始。面板重新載入時，回到上次那一節、那一步。
  - 沒有步驟的節，↑／↓ 照舊捲動講稿。
- **⌨ 快捷鍵一覽**：按 A−／A+ 旁邊的 ⌨，或按 **?**，所有按鍵列在同一頁。全域熱鍵列的是 `mirror.py` 啟動時實際註冊的
  （被其他程式佔用的會標出來）；mirror 未連線時改列 `hotkeys` 設定。mirror 只在啟動時讀 `hotkeys`，改熱鍵需重開 mirror。
  按 Esc、? 或 ✕ 關閉，焦點回到打開前的位置。在輸入框打字時，? 不會觸發。

  面板按鍵（先點一下面板）：

  | 按鍵 | 動作 |
  |---|---|
  | **←／→**、**PgUp／PgDn** | 上一節／下一節 |
  | **↑／↓**、**K／J** | 上一步／下一步（沒有步驟時：捲動） |
  | **Home** | 回到第一節 |
  | **?** | 開／關快捷鍵一覽（**Esc** 關閉） |
  | **F5** | 重新載入面板（改了講稿或 `config.json` 後） |

  Ctrl、Alt、Meta 組合鍵不會被面板攔下，所以 Ctrl+Alt+PgDn／PgUp 仍交給全域熱鍵。
- **自動跟隨**：投影的頁面換了，講稿就跳到對應段落。規則在 `notes_rules`，由上往下比對、第一個符合的生效，存檔即生效：
  - `title_contains` 比對分頁標題（Chrome 的視窗標題就是目前分頁的標題）；
  - `url_contains` 比對完整網址，**含 `#錨點`**；需要 `cdp_url`（見下方）。
- 只有「對應的段落改變」時才跳，所以手動翻頁不會被蓋掉；沒有對應規則的頁面不會讓講稿跳動。

**計時**
- 段落和分鐘數來自 `pacing_file`（格式見 [`examples/pacing.md`](examples/pacing.md)）。
- 按「開始」，每段按「下一段」，或直接點段落。用掉 80% 變橘色，超時變紅色。
- 翻到屬於另一段的講稿時，面板會問你要不要把計時切過去。

**AI 助手**（選用，預設關閉）
- 演講中可以問講稿或教材的問題。背景是在 `ai_helper.workdir` 執行 Claude Code CLI 的 `claude -p`，答案串流顯示。
- 唯讀：只能用 `Read`、`Grep`、`Glob`；不能執行指令、不能改檔、不能上網；秘密檔案在工具層就被擋
  （見[隱私與安全](#隱私與安全)）。會延續同一段對話，按「新對話」重新開始。
- 啟用方式：安裝並登入 Claude Code CLI，在 `config.json` 設定：

  ```json
  "ai_helper": { "enabled": true, "workdir": "examples", "timeout_sec": 180 }
  ```

  `claude` 不在 `PATH` 上時設定 `claude_bin`；要指定模型設定 `model`；改完重新啟動。
  問題和它讀到的檔案會送到模型供應商，只在你可以分享這些內容時啟用。

## 用範例網站試講稿自動跟隨

不需要任何帳號：

```bat
.venv\Scripts\python.exe -m http.server 3000 --bind 127.0.0.1 -d examples\demo-site
```

用瀏覽器開 `http://localhost:3000/`，在上面按 F7，再依序點 **Intro**、**Demo**、**Q&A**。
頁面標題會跟著段落改變，所以用範例的標題規則就能讓講稿跟著跳。想試 `#錨點` 網址規則，
用 DevTools 連接埠啟動那個瀏覽器並設定 `cdp_url`（請先讀安全說明）：

```bat
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%TEMP%\demo-profile" http://localhost:3000/
```

```json
"cdp_url": "http://127.0.0.1:9222"
```

測試投影鏡像本身的自我測試頁在 [`web/selftest/`](web/selftest/README.md)。

## 設定

repo 裡只有 `config.example.json`；你自己的 `config.json` 不進版控。以 `_` 開頭的鍵是註解。
座標一律是實體像素。改完要重新啟動；`notes_files`、`pacing_file`、`notes_rules` 例外，存檔即生效（講稿檔清單要在面板按 F5）。

| 鍵 | 預設 | 說明 |
|---|---|---|
| `ui_lang` | `en` | 面板語言：`en` 或 `zh-TW` |
| `hotkeys` | 見[熱鍵](#熱鍵) | 動作 → 按鍵組合；`""` 代表停用 |
| `source_display`／`target_display` | `""` | 例如 `\\.\DISPLAY1`。空白：主螢幕／第一個其他螢幕。沒有第二個螢幕時用視窗模式測試 |
| `panel_width_ratio`／`panel_width_px` | `0.26`／`0` | 面板寬度；`panel_width_px` 大於 0 時優先 |
| `panel_topmost` | `true` | 面板永遠在最上層 |
| `reserve_work_area` | `false` | 用 AppBar 保留面板區，最大化的視窗會避開面板（啟動／關閉時已最大化的視窗會縮放一次） |
| `clip_cursor_to_source` | `true` | 滑鼠鎖在筆電螢幕（Ctrl+Alt+L 切換） |
| `source_title_contains` | `[]` | 啟動時自動選取的標題關鍵字，依序比對 |
| `never_source_classes` | 終端機類 | 永遠不能投影的視窗類別 |
| `capture_backend` | `auto` | `auto`、`wgc`、`printwindow` 或 `mss` |
| `follow_popups`／`popup_min_size` | `true`／`[320, 240]` | 彈窗跟隨 |
| `fps`／`smooth_scale` | `25`／`true` | 更新率上限、縮放品質 |
| `pointer_*`、`spotlight_*`、`ripple_*` | | 游標大小、顏色、聚光燈、波紋 |
| `blank_text`／`blank_subtext`／`font_path` | | 「請稍候」畫面的文字與字型（中文請設定 `font_path`，例如 `C:\\Windows\\Fonts\\msjh.ttc`） |
| `panel_host`／`panel_port` | `127.0.0.1`／`8765` | 面板伺服器位址（只能是本機） |
| `panel_runtime`／`wsl_distro` | `windows`／`""` | 面板伺服器在哪裡執行 |
| `panel_browser` | `""` | 面板用的 Chrome／Edge 路徑；空白＝自動尋找 |
| `content_root` | `.` | 講稿、計時檔與 AI 助手的根目錄 |
| `notes_files`／`pacing_file` | 範例 | 講稿（Markdown）與計時檔；存檔即生效 |
| `notes_auto_follow`／`notes_follow_doc` | `true`／`""` | 自動跟隨預設值；要在哪份講稿裡跳（空白＝目前在看的那份） |
| `cdp_url` | `""` | 網址規則用的 DevTools 位址；空白＝只用標題規則 |
| `notes_rules` | 範例 | 自動跟隨規則 |
| `ai_helper` | `enabled: false` | `claude_bin`、`model`、`timeout_sec`、`extra_args`、`workdir`、`system_prompt` |

## 選用：在 WSL 執行面板伺服器

預設 `start.ps1` 用 Windows venv 的 Python 執行 `panel_server.py`。如果你的講稿和 Claude Code CLI 都在 WSL 裡，可以改成：

```json
"panel_runtime": "wsl",
"wsl_distro": ""
```

`wsl_distro` 空白代表預設的發行版。repo 放在 Windows 磁碟或 WSL 裡都可以（在 WSL 裡時從 `\\wsl.localhost\...` 開 `start.bat`）。
Windows 必須能連到 WSL 的 `127.0.0.1`：WSL 預設的 localhost 轉送或 `networkingMode=mirrored` 都可以。WSL 端只需要 `python3`。

## 在 Meet、Teams、Zoom 分享

- 分享**「整個畫面 → 螢幕 2」**（投影螢幕）。Meet：*分享螢幕 → 整個螢幕 → 第 2 個*；
  Teams：*分享 → 螢幕 → 螢幕 2*；Zoom：*分享螢幕 → 螢幕 2*。
- **不要**分享筆電螢幕，也不要只分享單一分頁：前者會把面板一起分享出去，後者切換視窗時就不會跟著換。
- 開始分享前先按 F9 切到「請稍候」，確認遠端看到的畫面正確，再按 F9 切回來。

## 限制

- **只投一個視窗（加上它的彈窗）。** 右鍵選單、網址列下拉清單、擴充功能彈出框是另外的小視窗，不會出現在投影上；
  網頁裡面的對話框屬於同一個視窗，會正常出現。
- **系統對話框**（另存新檔、選檔案）常常很小或沒有標題，不一定會被跟隨；需要時按 F7 切過去，做完再按 F7 切回來。
  UAC 提示、鎖定畫面、Ctrl+Alt+Del 在安全桌面上，永遠擷取不到。
- **DRM 影片**（串流平台）和部分硬體加速影片會變成黑畫面。
- 筆電開了 **HDR** 時擷取的顏色會偏灰，演講時請關掉 HDR。
- 會保持**原比例**並加黑邊；想讓字大一點，在瀏覽器按 Ctrl＋加號放大。
- **改了縮放比例或投影解析度**（例如 125% 改 150%）：重新執行 `start.bat`，座標才會重新偵測。
- 投影上的游標一律是箭頭，不會變成文字游標或手指。
- 凍結（F8）、來源縮小或關閉時，投影上不畫游標。
- 來源視窗不要放在投影螢幕上，會被投影畫面蓋住；面板會提醒，按 Shift+F7 搬回來。
- `mirror.py` 被強制結束時，`stop.bat` 會補做清理（AppBar、滑鼠鎖定）；右側還留著空白區就再執行一次。

## 隱私與安全

- **沒有啟用 AI 助手時，資料不會離開你的電腦。** 面板伺服器只綁 `127.0.0.1`，`Host` 標頭不是 `127.0.0.1`／`localhost`
  的請求一律拒絕（防 DNS rebinding），每個 POST 都要帶 `X-Panel: 1`（其他網頁無法跨站送出）。
- **面板永遠不會被投影**：依標題和視窗本身排除。
- **AI 助手**（預設關閉）：Claude Code CLI 以非互動方式啟動，參數包括 `--tools Read,Grep,Glob`、
  `--disallowedTools Bash Edit Write NotebookEdit WebFetch WebSearch`、`--permission-mode dontAsk`、`--strict-mcp-config`，
  並用權限規則擋掉 `.env*`、`*.key`、`*.pem`、SSH 金鑰、`*.local.md`、`.git/`、`config.json` 和 `logs/`。
  它在 `ai_helper.workdir` 裡執行，請指向你的演講資料夾，不要指向整個家目錄。你的問題和它讀到的檔案會送到模型供應商。
- **CDP（`cdp_url`）** 是選用的。用 `--remote-debugging-port` 啟動的瀏覽器會接受**本機任何程式**的指令
  （讀網頁、讀 cookie、執行腳本）。請只：
  - 綁在本機（預設就是），並使用獨立的投影用設定檔（`--user-data-dir`），不要登入任何敏感帳號；
  - 演講結束就關掉那個瀏覽器。

  presenter-sidecar 只接受本機（loopback）的 `cdp_url`，而且每個分頁只執行一個唯讀運算式
  （`document.visibilityState`、`document.hasFocus()`、`location.href`）。
- **觀眾看不到**：來源標題、警告和提示只會出現在面板上。

## 開發

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q                     # 單元測試，不需要螢幕（Linux／macOS／Windows）
node --test tests/js/*.test.js          # 面板的步驟規則（web/steps.js）跑共用測資
scripts/check/install-hooks.sh          # pre-commit：gitleaks＋私人字詞掃描
scripts/check/scan-private.sh --all
```

| 路徑 | 內容 |
|---|---|
| `mirror.py` | Windows：選來源、擷取、縮放、投影視窗、游標、熱鍵、AppBar |
| `panel_server.py` | 面板網頁伺服器與 AI 助手後端（只用標準函式庫） |
| `presenter_sidecar/` | 純邏輯模組：幾何、視窗規則、講稿規則、熱鍵、設定、CDP、訊息 |
| `web/` | 面板前端（`index.html`、`panel.js`、`panel.css`；不碰 DOM 的 `md.js`、`steps.js` 可在 node 測試）與 `selftest/` 測試頁 |
| `examples/` | 虛構的講稿（英文與繁體中文）、檢查清單、計時檔、範例網站 |
| `start.ps1`／`stop.ps1`（`.bat`） | 啟動與關閉全部 |
| `tests/` | 單元測試 |
| `scripts/media/` | 重新產生 `docs/media/` 的範例截圖（headless；需要 `playwright` 和 `pillow`） |

另見 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [SECURITY.md](SECURITY.md)。

## 授權

[MIT](LICENSE) © osisdie。第三方套件與授權見 [THIRD_PARTY.md](THIRD_PARTY.md)
（pygame-ce 是 LGPL-2.1，以未修改的動態函式庫方式使用）。
