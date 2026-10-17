# 雙引擎能力、限制與計算

## 架構

`Illustrator JSX / PDF / raster → common evidence model → rule engine → JSON + Markdown → issue/CVD previews`。

兩引擎各自報告，不以名稱或頁序強行合併原生文件與最終 PDF；送印的版本、Artboard 對應與輸出設定仍需核對。可使用 `--pdf` 一次產生兩組報告。

| 檢查 | Illustrator JSX（ENGINE A） | PDF／Raster（ENGINE B）與限制 |
|---|---|---|
| Artboard、尺寸與單位 | artboardRect、rulerUnits；統一輸出 mm | PDF TrimBox；未宣告時暫列 MediaBox 並標示限制；PDF 點與 UserUnit |
| 出血四邊 | DOM 不可靠，灰燈 | 必須明確存在 TrimBox、BleedBox 才計算；不能證明實際滿版覆蓋 |
| 安全邊界 | 文字與已標 important 的物件 bbox | 文字 bbox／已標重要物件；不能自動保證找到 Logo／QR |
| 色彩 | CMYK、RGB、Gray、Lab、Spot；列色票（含未使用者） | 原始 content operators 的 process colors、Separation／DeviceN 名稱；不把渲染 RGB 當原始 RGB |
| 圖片 PPI | linked raster 像素由 Pillow 讀，DOM boundingBox × matrix；嵌入像素未知 | 每個 image occurrence 的像素與 transform；同圖不同大小分別計算 |
| Missing Link | File.exists，可讀取時列連結路徑 | PDF 只能知道已內嵌於 PDF，不能還原 AI 連結 |
| 字型 | characterAttributes 的 font、style、size；混合文字逐 run | 擷取文字與 PDF font reference；未實作完整缺字／嵌字合規驗證 |
| Missing Font | 已開檔可能替代字型，因此預設灰燈；可加已核對證據 | 不能藉已渲染字型證明原 AI 不缺字型 |
| Live／Outlined | TextFrame 證明 live；一般 path 不證明 outlined | 路徑無法還原字型或原字級；不將「無文字」當「已外框」 |
| 小字／多色黑 | 字級、CMYK、色版數交叉 | 原始 PDF text painting 的字級×矩陣與 CMYK；位置未可靠對應時不畫標記 |
| TAC | 可取得的 CMYK fill／stroke；Linked CMYK raster | 8-bit 原生 CMYK、identity Decode、unfiltered／Flate 圖片可精確統計；CMYK JPEG、DeviceN、其他 Decode 預設灰燈 |
| Spot／Pantone | 色票名與使用物件；未使用色票分開標 | Separation／DeviceN 名稱，不驗證實體 Pantone 庫 |
| 疊印 | fillOverprint／strokeOverprint／文字 overprint 屬性 | 追蹤 ExtGState 與 q/Q、Form，白色 process 疊印紅燈；白墨 Spot 不等同 process white |
| 透明度／混合 | opacity、blendingMode；Opacity Mask 灰燈 | ExtGState ca／CA／BM／SMask；不等於全功能透明度合成分析 |
| 細線 | strokeWidth | 渲染 path 線寬；非等比變形、外觀效果仍需核對 |
| 加工 | Layer／物件／Spot 名稱關鍵字 | 色版名稱候選；不能證明加工線正確或為預期設定 |
| Hidden／Locked／Non-printing | 圖層及父層狀態、物件 hidden／locked | PDF 無法還原未輸出或已刪除的 Illustrator 物件 |
| Contrast | 經核對的 sRGB 單色前景背景注記 | 自動支援不透明、無疊印／群組／遮罩、已證明單色矩形或白底的文字；使用渲染 RGB 作螢幕 sRGB 參考。照片／漸層／遮擋／特殊效果灰燈 |
| 色覺模擬 | imageCapture Artboard PNG | PDF 轉 RGB 預覽；非軟打樣／分色打樣 |
| 色彩資訊語意 | 需標註 semantic_pairs | 程式不能僅憑顏色判斷紅綠是否代表付款或分類 |
| PDF/X、ICC | 需最終 PDF | 讀版本、PDF/X Info／XMP 宣告、OutputIntent 及 ICC 存在／通道數；不驗證整套 PDF/X 規範 |

## TAC

向量 CMYK 數值使用百分比：`TAC = C + M + Y + K`。C90 M80 Y80 K100 得 350%，上限 300% 時超出 50%。特別色不直接加入 process TAC；也不把 RGB 轉成某個猜測的 CMYK 配方來宣布通過。

原生 8-bit CMYK 圖片每像素：`100 × (c + m + y + k) / 255`；計算 max、mean、`count(TAC > limit) / total × 100%`。先升為浮點，避免 uint8 溢位。這包含裁切區外／遮罩下像素，不是可見頁面的最終墨量。

透明度、疊印、色彩轉換、紙材、RIP 與 ICC 分色會影響最終 TAC；此版本未做整頁 separation renderer。ICC 存在不表示有可直接讀取的通用 TAC 上限。上限必須來自廠商規格、已核對的 ICC 配套說明或使用者設定，且以規格來源優先。

## Effective PPI

基本公式：`pixels / (placed_points / 72)`。300 px 放成 2 inch 得 150 PPI，與原圖 DPI 標籤不同。

PDF 影像單位正方形的矩陣為 `[a,b,c,d,e,f]`：`PPIx = 72 × W / hypot(a,b)`，`PPIy = 72 × H / hypot(c,d)`。旋轉不改變解析度；不能用旋轉後軸向 bbox 寬高。非等比縮放分別報 X/Y。剪切另將每像素映射矩陣 `[[a/W,c/H],[b/W,d/H]]` 的最大奇異值取倒數乘 72，作最差主方向 PPI。判斷用此 minimum。

原始縮放比例只在原始 DPI 有可靠 metadata 時輸出：`native_DPI / effective_PPI × 100%`；缺 DPI 則灰燈／null，不用 PDF 的常見 96 DPI 預設猜原始尺寸。Illustrator embedded 圖片無原始像素時不從 points 猜像素。

## Contrast

使用 sRGB gamma 解碼、相對亮度 `0.2126R + 0.7152G + 0.0722B`、`(Lighter+0.05)/(Darker+0.05)`。預設一般字 4.5:1、大字 3:1；大字為 ≥18 pt 或已知粗體 ≥14 pt。未證實粗體時採一般門檻。設定可改 AAA 等門檻。

WCAG 是螢幕／網頁標準；這裡是印刷閱讀的輔助參考，不宣稱印刷品通過 WCAG。CMYK、Lab、Spot 沒有可核對的輸出至 sRGB 證據時不臆造對比色。自動 PDF 對比會在證據中說明「renderer RGB treated as sRGB」，有 ICC 精準色彩要求時仍需校樣。

## 色覺模擬

使用 `colorspacious.cvd.machado_et_al_2009_matrix()`，Machado、Oliveira、Fernandes 2009，severity=100 的 protanomaly／deuteranomaly／tritanomaly 矩陣產出對應 -opia 預覽。先把 sRGB 解碼為線性 RGB，再乘矩陣，裁切色域後轉回 sRGB。不是降飽和或灰階。

已核對的資訊色彩對在模擬後計算 CIELab ΔE76。預設 <10 列候選风险，可調；這不是通用色盲合規門檻。必須保留色彩語意、文字／形狀等冗餘線索的人工檢查。RGB／HEX 可由同一 sRGB 值計算；CMYK 沒有原始來源時列 null，禁止猜配方。

## 引用與套件

- [Adobe：安裝與執行 Illustrator scripts](https://helpx.adobe.com/illustrator/desktop/automate-visualize-data/automate-actions/install-and-run-scripts.html)
- [Adobe Illustrator scripting resources](https://developer.adobe.com/illustrator/scripting/)；DOM 属性以安裝版本的 Scripting Reference 為準。
- [PyMuPDF Page API](https://pymupdf.readthedocs.io/en/latest/page.html)：image occurrence、text trace、drawing、render。
- [pikepdf 圖片文件](https://pikepdf.readthedocs.io/en/latest/topics/images.html)：PDF 原生資源與圖片樣本。
- [colorspacious 原始模型介面](https://github.com/njsmith/colorspacious/blob/master/colorspacious/cvd.py)：本專案透過 library 呼叫，未複製整份矩陣。
- [Machado 模型與作者補充資料](https://www.inf.ufrgs.br/~oliveira/pubs_files/CVD_Simulation/CVD_Simulation.html)
- [W3C Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)

requirements：PyMuPDF（PDF 幾何與渲染）、pikepdf（PDF 原始結構）、Pillow（raster/PNG）、NumPy（像素與矩陣）、colorspacious（色覺模型、Lab）、python-docx（規格）、jsonschema（設定驗證）、pytest（測試）。依各套件授權使用，發佈整合產品時另核對 PyMuPDF 的 AGPL／商用條款。
