# 測試與驗證範圍

`python -m pytest tests -q` 驗證合成模型、實際生成 PDF 的解析、公式、未知處理、規格優先權與不覆寫。這不是實際 Illustrator 宿主測試。

`python tests/generate_cases.py` 產生 `tests/fixtures/`，每案包含 inspector JSON、合成 thumbnail、PDF。thumbnail 明確標示 Synthetic preview，不能當作 JSON 的真實渲染。PDF fixtures 僅供該引擎能保留的內容；例如缺 AI link 不能存在於 PDF 結構中。

`python tests/run_examples.py` 執行所有 fixtures，生成 `output/test-cases/`，以及測試總表；若該輸出存在，腳本拒絕覆寫。

| TEST | 情境 | 預期 |
|---|---|---|
| 01 | 正常 CMYK | 已觀測的數值無紅燈，仍有未知與範圍限制 |
| 02 | RGB image | 黃燈 RGB |
| 03 | 150 PPI | 紅燈 Effective PPI |
| 04 | Missing Link | 紅燈；用合成 DOM 證據，PDF 無此能力 |
| 05 | 5 pt | 黃燈小字 |
| 06 | 四色黑小字 | 紅燈小字套印，亦有 TAC 紅燈 |
| 07 | TAC 350% | 紅燈，超過 default 50% |
| 08 | process White + Overprint | 紅燈 |
| 09 | Spot | 黃燈；不是直接判錯 |
| 10 | 0.1 pt | 黃燈細線 |
| 11 | 紅綠圖例 | 已標註資訊語意後，檢查模擬差異與 color-only 黃燈 |
| 12 | 低對比 | Accessibility 黃燈，不當印刷錯誤 |
| 13 | 5 pt + Light + 低對比 | Accessibility 紅燈 |
| 14 | 已知四邊 0 bleed | 紅燈；未知框值另測灰燈 |
| 15 | 刀模＋白墨 | 特殊加工清單；不因名稱判錯 |

額外測試：PPI 旋轉／剪切、200／300 門檻、contrast 1:1／21:1、CMYK uint8 TAC、Machado 參考數值、缺 TrimBox、不可解析 AI、複雜背景不能通過、規格衝突與非法設定、輸出不得覆寫、來源前後一致、四張色覺 PNG。

## 真實 Illustrator 驗收（尚待使用者的實際檔案與宿主）

1. 用不含敏感資訊的副本，記錄 Illustrator 版本與 OS。
2. 建立 2 個不同尺寸 Artboard、旋轉／非等比縮放的 linked raster、embedded raster、5/6 pt 混合字級、Spot、白色疊印與隱藏圖層。
3. 執行 JSX；比較 Artboard 面板、字元面板、連結面板與屬性面板，逐項記錄 JSON 與 UI 是否一致。
4. 特別核對 `boundingBox × matrix` 與 Illustrator 顯示的 Effective PPI；剪切可有不同 UI 定義，須保留 X/Y 與最差主方向說明。對嵌入圖預期原始像素未知。
5. 缺字型測試需記錄開檔提示；不要以開檔後字型物件可讀取宣布字型沒遺失。
6. 確認執行前後原 AI 的 SHA-256 相同，文件未被腳本儲存；切勿把另一次手動存檔變更誤算為腳本修改。
7. 存在多重填色、Envelope、Opacity Mask、Mesh、Symbol 或插件物件時，確認報告保留未知，另看實際送印 PDF 與印刷廠檢查結果。

測試證明實作可重現規則與解析支援子集；不證明所有 Illustrator 版本、PDF 內容、ICC／RIP 都已涵蓋。
