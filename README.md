# 庫存管理系統 / Inventory Management

**專案**：YA! 玩音樂 多人協作庫存管理
**架構**：單檔 HTML + Firebase Realtime Database
**部署**：GitHub Pages — https://yaukulele.github.io/inventory/

## 檔案

- `index.html` — 整個 app（前端 + Firebase 存取），單一檔案不需要 build

## Firebase

- Realtime DB：`order-system-dddca-default-rtdb.firebaseio.com`
- `inventory/items` — 品項陣列 `{id,b,c,n,q,z,img?,ph?,dsc?}`
- `inventory/photos/<photoId>` — 手機拍的照片 `{t,d,by,at,n}`（`t`=240px 縮圖、`d`=1280px 大圖，都是 JPEG dataURI）
- `inventory/logs` — 異動紀錄陣列（最新在前，上限 500 筆）
- `inventory/order` — 排序 / 版本標記

## 使用者

`US` 陣列：快速預覽、Allie、阿淵、雨停、小愷、向秦

## 寫入原則（重要）

**務必用 transaction 路徑**，不要直接 `dbI.set(整個陣列)`：
- `fbTxItem(id, updater)` — 原子更新單一 item
- `fbAddItemTx(it)` — 新增
- `fbDelItemTx(id)` — 刪除
- `fbAppendLogTx(entry)` — 寫入紀錄（保留最新 500）
- `fbSetOrdKey(key, value)` — 排序更新

直接 `dbI.set()` 會互相覆寫，多人同時操作會丟資料。

## 商品圖片（重要）

一個商品的圖只會有一種來源，`img`（外部網址）與 `ph`（手機拍的照片編號）互斥：
填網址就清掉 `ph`，拍照就清掉 `img`。判斷有沒有圖一律用 `itemHasImg(it)`，
畫縮圖一律用 `itemImgEl(it, style, onErr)`（自拍照會自己去抓縮圖填 src）。

**照片絕對不要塞進 `inventory/items`**：items 是整包載入的陣列（約 470 筆 / 124KB），
每個人開頁就整包下載，塞 base64 會膨脹成好幾 MB。照片一律另存 `inventory/photos/<id>`，
items 上只留 20 幾字元的 `ph`。清單只抓 `photos/<id>/t`（縮圖 2~20KB），
點開看大圖才抓 `photos/<id>/d`。

換照片 / 清照片後要呼叫 `fbPhotoDropIfUnused(舊id, 本商品id)` 清掉沒人用的舊照片
（會先確認沒有別的商品指著同一張，「🔁 複製」出來的商品會共用同一張）。

## 本地預覽

```bash
cd D:/Coding/inventory
python -m http.server 8787
```

手機打開 `http://<電腦 IP>:8787/`（同 Wi-Fi）

## 部署

push 到 GitHub main，GitHub Pages 自動重部署。
