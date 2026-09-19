# -*- coding: utf-8 -*-
"""乾跑：先確認庫存裡那些外部圖，透過我們的代理到底抓不抓得到。

在杰哥按下「開始抓回來」之前先知道會有幾張失敗、失敗的是哪些，
比讓他按下去跑一半才發現好。**這支完全不寫入任何東西。**
"""
import io, sys, json, re, collections, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests
from concurrent.futures import ThreadPoolExecutor

DB = "https://order-system-dddca-default-rtdb.firebaseio.com"
PROXY = "https://product-image-finder-production-1e1b.up.railway.app/api/proxy?url="

items = requests.get(DB + "/inventory/items.json", timeout=90).json() or {}
rows = list(items.values()) if isinstance(items, dict) else [x for x in items if x]

targets = []
own = 0
for it in rows:
    if not isinstance(it, dict):
        continue
    if it.get("ph"):
        continue
    u = (it.get("img") or "").strip()
    if not u.lower().startswith("http"):
        continue
    if re.match(r"https?://([a-z0-9-]+\.)*yamusic\.com\.tw/", u, re.I):
        own += 1
        continue
    targets.append((it.get("n") or it.get("id"), u))

print("庫存 %d 筆；指向我們官網 %d 張（預設不抓）；要抓的外部圖 %d 張\n"
      % (len(rows), own, len(targets)))


def probe(t):
    name, u = t
    try:
        r = requests.get(PROXY + urllib.parse.quote(u, safe=""), timeout=45, stream=True)
        ct = (r.headers.get("Content-Type") or "").lower()
        n = len(r.raw.read(400000, decode_content=True) or b"")
        r.close()
        ok = r.status_code == 200 and ct.startswith("image/") and n > 0
        return (name, u, r.status_code, ct.split(";")[0], n, ok)
    except Exception as e:
        return (name, u, "ERR", str(e)[:40], 0, False)


with ThreadPoolExecutor(max_workers=3) as ex:
    out = list(ex.map(probe, targets))

ok = [o for o in out if o[5]]
bad = [o for o in out if not o[5]]
print("=" * 62)
print("抓得到：%d 張" % len(ok))
print("抓不到：%d 張   << 這些要人工處理（自己拍或換一張）" % len(bad))
print("=" * 62)

hosts_ok = collections.Counter(re.match(r"https?://([^/]+)", o[1]).group(1) for o in ok)
hosts_bad = collections.Counter(re.match(r"https?://([^/]+)", o[1]).group(1) for o in bad)
if hosts_ok:
    print("\n【抓得到的來源】")
    for h, n in hosts_ok.most_common(12):
        print("   %-44s %3d" % (h, n))
if bad:
    print("\n【抓不到的來源】")
    for h, n in hosts_bad.most_common(12):
        print("   %-44s %3d" % (h, n))
    print("\n【抓不到的商品（前 20）】")
    for name, u, code, ct, n, _ in bad[:20]:
        print("   [%s] %-26s %s" % (code, str(name)[:26], u[:66]))
    io.open("_backfill_unreachable.txt", "w", encoding="utf-8").write(
        "\n".join("%s\t%s\t%s" % (o[2], o[0], o[1]) for o in bad))
    print("\n清單輸出：_backfill_unreachable.txt")

if ok:
    avg = sum(o[4] for o in ok) / len(ok)
    print("\n抓得到的圖平均原始大小 %.0f KB；壓過之後每張約 30~170KB，"
          % (avg / 1024))
    print("%d 張大約會佔 Firebase %.1f MB。" % (len(ok), len(ok) * 0.12))
