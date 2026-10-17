# 共同證據模型 v1 與人工補充

座標統一為 point、`[left,top,right,bottom]`、y 向下。Illustrator 使用全文件座標（y 反號），PDF 使用取消旋轉的 MediaBox viewport；預覽採相同座標系。跨 Artboard 物件會列在每個相交 Artboard；未落在任何 Artboard 的項目使用 null。不要猜位置。

頂層：`schema_version:1`、`engine`、`source`、`artboards`、`objects`、`limitations`；可選 `metadata`、`semantic_pairs`。

Artboard：`id`（唯一整數）、`name`、`rect`、`bleed_mm`（top/bottom/left/right 或 null）；可選 `preview_rect`。預覽檔應放在 inspector JSON 同目錄，名稱為 `artboard-01-original.png`。

物件常用欄位：

| 欄位 | 單位／含義 |
|---|---|
| name、kind、artboard、bbox、evidence | 唯一名稱＋Artboard 用於注記配對；kind=text/image/path/layer/swatch/paint |
| fill、stroke、color | `{space,values,name}`；CMYK 0–100、RGB 0–1、Gray 0–1（1=白）、Lab 原值、Spot 含 name/tint/alternate |
| font、weight、bold、font_size_pt、text | bold 必须有字型屬性依據；不猜 weight；text 報告只顯示前 30 字 |
| missing_font、outlined、reverse | true/false/null；未取得就是 null，不把「可渲染」當 missing_font=false |
| pixels、image_transform | `[width,height]` 像素，矩陣將單位正方形映射至 pt |
| native_dpi、effective_ppi | native metadata 或 null；effective 由程式計算 x/y/minimum |
| link_state、path | linked/embedded/missing/unknown；路徑只讀，不執行 |
| tac_stats | maximum、average、over_limit_percent、basis；必須是真正原生 CMYK 樣本，不能手填猜測 |
| opacity、blend_mode、opacity_mask | 0–100、名稱、true/false/null |
| overprint_fill、overprint_stroke | bool/null，缺欄位不代表 false |
| hidden、locked、non_printing | 原生物件與父層可查時才填 |
| important、background_cmyk、cvd_difficult | 需語意／色彩證據，供交叉檢查 |

## 補充注記

`--annotations annotations.json` 只接受指定欄位，來源必須與 `INSPECTION.json` 的 `source` 完全一致。先查看實際物件名稱／Artboard，再建立檔案；不要使用下面的例子冒充實際證據。

```json
{
  "source": "必須與檢查資料 source 完全相同",
  "objects": [
    {
      "name": "Test text",
      "artboard": 1,
      "evidence": "人工確認單色背景、無透明度、無遮擋；前景背景為已指定的 sRGB 色彩",
      "fields": {
        "important": true,
        "reverse": false,
        "contrast_pair": {
          "foreground": [0.7, 0.7, 0.7],
          "background": [1, 1, 1],
          "color_space": "sRGB",
          "background_type": "solid",
          "verified": true,
          "evidence": "對應文字與背景物件的已核對 sRGB 值；不是目測"
        }
      }
    }
  ],
  "semantic_pairs": [
    {
      "name": "付款狀態圖例",
      "artboard": 1,
      "verified": true,
      "evidence": "設計師確認紅／綠對應兩種付款狀態，未加標籤或圖示",
      "non_color_cue": false,
      "a": {"srgb": [1, 0, 0], "HEX": "#FF0000", "RGB": [255, 0, 0], "CMYK": null},
      "b": {"srgb": [0, 0.68, 0], "HEX": "#00AD00", "RGB": [0, 173, 0], "CMYK": null}
    }
  ]
}
```

若有 ICC 轉換，記錄來源 profile、輸出 sRGB profile、轉換工具／intent；沒有來源 CMYK 時保留 null。`non_color_cue` 的判斷需真的檢查文字／Icon／Pattern／形狀。

原始 PDF paint event 與文字幾何 span 會分開保留，因為文字、色彩與座標不一定能一一對應。同一段文字可能有兩組證據與多條結果，報告計數不是獨立物件數。不能擅自把無 bbox 的 paint event 套到相鄰文字。
