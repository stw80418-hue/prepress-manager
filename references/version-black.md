# AI 版本與四色黑

## AI 版本

- 門檻 `maximum_ai_major_version: 16`（CS6）。可靠確認儲存版本高於門檻亮黃燈；無證據灰燈。
- 建立軟體較新另亮黃燈，但不能據此斷定未降存。
- PDF 版本、Creator、RoundtripVersion、ContainerVersion 不可冒充已驗證的儲存版本。
- Illustrator DOM 不提供儲存相容版本。人工證據可在 inspector JSON 的 `ai_version` 提供 `saved_major`、`saved_version_verified: true`、`saved_version_evidence`，必須先核對，不可自行猜填。
- 不自動降版。舊版另存可能遺失效果，需使用者確認後另存副本並比對。

## 四色黑

- 解析 CMYK 填色／筆畫；K ≥ `black_k_threshold` 且混入 CMY 為混色黑候選，四通道均非零才稱四色黑。
- 可取得字級且 ≤ `small_black_text_max_pt` 的黑字列紅燈；一般物件與大面積黑列黃燈，不把 Rich Black 一律判錯。
- 外框字、圖片、漸層與 RIP 結果未完整覆蓋須灰燈揭露。
- 不自動改色。

## 參考

- [Adobe 儲存與舊版相容說明](https://helpx.adobe.com/illustrator/using/saving-artwork.html)
- [Adobe 黑色與分色工作流程](https://www.adobe.com/studio/print/pdfs/CS3_color_workflows.pdf)
