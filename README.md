# illustrator-preflight｜AI 印前完稿健檢

供 **Codex 與 Claude Code** 使用的繁體中文、唯讀印前檢查 Skill。預設以數位印刷交付為主，檢查色彩模式、文字外框、出血尺寸、圖片有效解析度、圖片嵌入／連結、AI 版本相容性與四色黑。WCAG／色覺檢查不在預設範圍。

## 安裝

需 Git、Python 3.10+。在終端機執行：

```sh
git clone https://github.com/stw80418-hue/illustrator-preflight.git
cd illustrator-preflight
python scripts/install_skill.py --target codex
python scripts/install_skill.py --target claude
python -m venv .venv
```

Windows：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

macOS／Linux：

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest tests -q
```

安裝腳本只複製來源碼，不複製稿件與輸出，不覆寫既有 Skill。Codex 安裝到 `~/.agents/skills/illustrator-preflight`；Claude Code 到 `~/.claude/skills/illustrator-preflight`。若已有同名舊版（包括 Codex 的舊路徑 `~/.codex/skills`），請先備份並移出舊版以免重複載入。重新開啟對話，再指定剛建立的 Python 虛擬環境路徑。

Codex：`$illustrator-preflight 檢查這份 AI，以數位印刷為主。`

Claude Code：`/illustrator-preflight 檢查這份 AI，以數位印刷為主。`

兩者都可用自然語言要求檢查。這裡的 Claude 指本機 Claude Code，不保證 Claude 網頁版／Cowork 能執行本機 Illustrator。

## 第一次使用

將稿件放在儲存庫外的私人工作資料夾，告訴助理檔案與 Python 路徑；或直接執行：

```sh
python scripts/preflight.py /path/to/design.ai --scope digital --out /path/to/new-report
```

`python` 須換成已安裝依賴的虛擬環境 Python。輸出目錄必須是新的。完整操作見 [首次檢查](references/first-run.md) 與 [圖片嵌入檢查](references/image-embedding.md)。

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
