"""Messages shown in the private panel (never on the projector). ``ui_lang``: ``en`` or ``zh-TW``."""
from __future__ import annotations

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "warn.none": "No source window. Click the window to project and press {pick}.",
        "warn.closed": "Source window closed (projector holds the last frame).",
        "warn.minimized": "Source window minimised (projector holds the last frame).",
        "warn.obscured": "Source window is covered (mss mode can only capture uncovered windows).",
        "warn.on_projector": "Source window is on the projector display. Press {bring} to bring it back.",
        "note.source": "Projecting: {title}",
        "note.refused": "Cannot project this window: {why}",
        "note.brought": "Moved the source window next to the panel.",
        "note.popups_on": "Follow popups: on",
        "note.popups_off": "Follow popups: off (press {pick} to project a popup)",
        "note.clip_on": "Mouse confined to the presenter display",
        "note.clip_off": "Mouse unlocked: it can reach the projector (the audience will see the real cursor)",
        "why.own_window": "it belongs to this tool",
        "why.panel_window": "the panel is private",
        "why.blocked_class": "this window class is in never_source_classes",
        "why.desktop": "desktop and taskbar cannot be projected",
        "ai.disabled": "The AI helper is disabled. Set ai_helper.enabled to true in config.json.",
        "ai.busy": "Still answering the previous question. Press Stop or wait.",
        "ai.start_failed": "Cannot start claude: {err}",
        "ai.sent": "Sent, thinking…",
        "ai.timeout": "No answer after {secs} s; stopped. Try a shorter question.",
        "ai.exit": "claude exited with code {code}: {err}",
        "ai.context": "(Current section: {context})",
    },
    "zh-TW": {
        "warn.none": "找不到投影來源，請點一下要投影的視窗再按 {pick}",
        "warn.closed": "來源視窗已關閉（投影停在最後一格）",
        "warn.minimized": "來源視窗已縮小（投影停在最後一格）",
        "warn.obscured": "來源視窗被擋住（mss 模式只能投沒被擋住的視窗）",
        "warn.on_projector": "來源視窗在投影螢幕上，請按 {bring} 搬回主螢幕",
        "note.source": "投影來源：{title}",
        "note.refused": "不能投影這個視窗：{why}",
        "note.brought": "已把來源視窗搬到面板左邊",
        "note.popups_on": "自動跟隨彈窗：開",
        "note.popups_off": "自動跟隨彈窗：關（彈窗要按 {pick} 才會投影）",
        "note.clip_on": "滑鼠已鎖在主螢幕",
        "note.clip_off": "滑鼠鎖定已解除：可以移到投影螢幕（觀眾會看到真游標）",
        "why.own_window": "這是本工具自己的視窗",
        "why.panel_window": "面板是私人的",
        "why.blocked_class": "這類視窗列在 never_source_classes",
        "why.desktop": "桌面或工作列不能投影",
        "ai.disabled": "AI 助手未啟用。請在 config.json 把 ai_helper.enabled 設為 true。",
        "ai.busy": "上一題還在回答，請先按「停止」或稍等。",
        "ai.start_failed": "無法啟動 claude：{err}",
        "ai.sent": "已送出，思考中…",
        "ai.timeout": "超過 {secs} 秒，已中止。可以把問題改短一點再問。",
        "ai.exit": "claude 結束碼 {code}：{err}",
        "ai.context": "（目前段落：{context}）",
    },
}


def t(lang: str, key: str, **kw) -> str:
    table = MESSAGES.get(lang) or MESSAGES["en"]
    msg = table.get(key) or MESSAGES["en"].get(key, key)
    return msg.format(**kw) if kw else msg
