# 版本紀錄

## 1.1.0（2026-10-17）

- 預設數位印刷檢查新增：小字、安全邊距、細線、白色疊印（白色物件設疊印列紅燈）。
- 安裝腳本：`--target both`；自動在 Skill 資料夾建立 `.venv` 並安裝套件；新增 `--update`，舊版移到 `skill-backups/` 備份；偵測舊路徑與舊名稱並提醒。
- Skill 會自動使用安裝資料夾內的 `.venv`，不必再手動提供 Python 路徑。
- 省略 `--out` 時，報告改建在來源檔旁，不再寫進 Skill 安裝資料夾。
- Illustrator 指令碼：連結遺失時改標為「連結遺失」並附錯誤訊息；文字改按格式區段讀取，大檔更快。（仍待實際 Illustrator 驗證）
- 修正文件與訊息中的簡體字；SKILL.md 說明與預設範圍一致；AI 版本與四色黑細節移到 `references/version-black.md`。
- 新增 AGPL-3.0 授權。

## 1.0.0

- 以 `prepress-manager` 名稱發布（原 `illustrator-preflight`）。
