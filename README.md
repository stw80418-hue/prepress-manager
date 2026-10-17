# Prepress Manager｜印前管理員

供 **Codex 與 Claude Code** 使用的繁體中文、唯讀印前檢查 Skill。預設以數位印刷交付為主，檢查色彩模式、文字外框、出血尺寸、圖片有效解析度、圖片嵌入／連結、AI 版本相容性、四色黑、小字、安全邊距、細線與白色疊印。WCAG／色覺檢查不在預設範圍。

## 安裝說明與操作手冊

📘 **新手安裝說明＋操作手冊：留下 Email 免費索取 → [圈外設計 OUT OF DESIGN](SIGNUP_URL)**

手冊內容：Codex／Claude Code 逐步安裝、第一次檢查、印刷廠規格怎麼給、Illustrator 指令碼用法、報告燈號判讀與常見問題。

需求：Codex 或 Claude Code（本機版）、Git、Python 3.10+；檢查 AI 原生資料需另有 Adobe Illustrator。這裡的 Claude 指本機 Claude Code，Claude 網頁版不能執行本機程式。

## 能力與限制

- PDF 相容 AI／PDF：解析頁框、可取得的物件色彩、圖片有效 PPI 與繪製資訊。不是完整 AI 私有格式解析器，也不是 PDF/X 認證器。
- Illustrator JSX：讀取原生文件資料，需另有合法安裝的 Adobe Illustrator。尚待實際 Illustrator 宿主驗證。
- 已外框文字無法可靠還原字級；PDF 內有圖片不等於原 AI 已嵌入。
- AI 版本預設以 CS6（16）為門檻；建立軟體版本較新會提醒，但不能拿它當作已確認的儲存相容版本。
- 四色黑區分小字風險與一般 Rich Black；不自動轉色、嵌入、外框、降存或覆寫原稿。
- 預設 3 mm／300 PPI 是工作門檻，印刷廠規格優先。未發現問題不等於一定可送印。

## 隱私與測試

本儲存庫只有程式、設定、空白報告模板、文件與合成測試產生器；不包含任何使用者稿件、印刷廠文件、實際健檢報告、預覽、來源路徑或專案記憶。`.gitignore` 另排除常見稿件／輸出；勿強制加入私人資料。

`pytest tests -q` 測試共用 Python 引擎；測試會在暫存目錄建立合成檔案。測試通過不代表已驗證 Illustrator 或印刷機台。依賴各自遵循上游授權（包含 PyMuPDF 的授權條款）。

官方安裝格式：[Codex Skills](https://learn.chatgpt.com/docs/build-skills)、[Claude Code Skills](https://code.claude.com/docs/en/skills)。

## 從舊名稱升級

原名稱為 `illustrator-preflight`。請將舊 Skill 資料夾移到 skills 目錄外備份，再安裝 `prepress-manager`，避免兩個版本同時載入（安裝腳本偵測到會提醒）。原有稿件與歷次報告不需更名。

## 版本與授權

版本紀錄見 [CHANGELOG.md](CHANGELOG.md)。

程式碼以 [GNU AGPL-3.0](LICENSE) 授權，© 2026 圈外設計 OUT OF DESIGN。依賴套件各自遵循其授權（PyMuPDF 為 AGPL-3.0）。

安裝說明、操作手冊與其他教學內容不屬於上述開源授權，版權所有，請勿轉載或轉售。
