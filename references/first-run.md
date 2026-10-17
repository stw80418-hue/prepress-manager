# 第一次檢查

先依儲存庫 README 安裝 Skill 與 Python 依賴。以下指令在 Skill 根目錄執行；若由 Codex／Claude Code 呼叫，必須使用該 Skill 實際安裝路徑，不把相對 scripts 路徑誤認為使用者工作目錄。

```sh
python scripts/preflight.py /path/to/design.ai --scope digital --out /path/to/new-report
```

輸出目錄必須不存在；省略 `--out` 時自動建在來源檔旁（`<檔名>-preflight-<時間>`）。腳本不覆寫原稿。`python` 請用 Skill 根目錄 `.venv` 內的 Python（安裝腳本已建立）。PDF 相容 AI 只檢查 PDF 區；無 PDF 相容區時改用 Illustrator 原生腳本。

## Illustrator 原生資料

1. 以 Illustrator 開啟原稿副本；記錄缺字型與連結警告。
2. 「檔案 > 指令碼 > 其他指令碼」執行本 Skill 的 `scripts/illustrator_inspector.jsx`。
3. 選輸出父資料夾；它建立新的 `illustrator-inspection-<timestamp>`。
4. 將 `illustrator-inspection.json` 路徑交給 Codex 或 Claude Code，或作為上述 CLI 輸入。

JSX 不儲存 AI，但尚未完成實際 Illustrator 宿主驗證。單靠 PDF 無法證明原 AI 圖片已嵌入、文字全數外框或儲存相容版本。

## 設定與規格

成品尺寸與出血可直接用 `--size 210x297 --bleed 3`（優先於設定檔，印刷廠規格仍最優先）。`--settings job-settings.json` 可設定 `bleed_mm`、`minimum_image_ppi`、`target_size_mm`、`maximum_ai_major_version` 等。印刷廠規格經核對後以 `--spec PRINT_SPEC.json` 使用，優先於使用者設定。Schema 見 PRINT_SPEC.schema.json。

一般使用 `digital`，不生成 WCAG 或色覺報告。`all`／`accessibility` 僅限另行明確要求。

預設產出 PREFLIGHT_REPORT.md、INSPECTION.json、ISSUES.json、EFFECTIVE_RULES.json、RUN_MANIFEST.json 與問題預覽。請將所有實際檢查輸出存放在公開儲存庫外。Python 腳本不含上傳功能；使用 AI 助理時另受該服務的資料處理政策影響。
