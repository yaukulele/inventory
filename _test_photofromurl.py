# -*- coding: utf-8 -*-
"""驗「抓圖回來」這條路 —— 用**真的瀏覽器**跑**index.html 裡真正的那份程式**。

為什麼不能用 node 測：compressPhoto 靠 canvas / createImageBitmap，node 沒有。
為什麼不是另外重寫一份來測：那只會測到副本，index.html 改壞了測不出來。
做法：從 index.html 原封不動抽出需要的函式 → 塞進測試頁 → 本機起一個小 server
給 headless Chrome 讀 → 頁面跑完把結果 POST 回來。用 POST 回報而不是等時間到，
才不會「還沒跑完就把畫面 dump 走」（第一版就是這樣只印出 running…）。
"""
import io, os, re, sys, json, threading, subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
src = io.open(os.path.join(HERE, "index.html"), encoding="utf-8").read()


def grab(pattern, label):
    m = re.search(pattern, src, re.S)
    assert m, "抽不出 " + label
    return m.group(0)


parts = [
    grab(r"const IMG_FINDER=\"[^\"]+\";", "IMG_FINDER"),
    grab(r"const PHOTO_MAX_DIM=.*?const THUMB_DIM=\d+;", "photo consts"),
    grab(r"function isOwnImgUrl\(u\)\{.*?\n\}", "isOwnImgUrl"),
    grab(r"function normalizeImgUrl\(url\)\{.*?\n\}", "normalizeImgUrl"),
    grab(r"async function _loadBitmap\(file\)\{.*?\n\}", "_loadBitmap"),
    grab(r"function _drawScaled\(src,maxDim\)\{.*?\n\}", "_drawScaled"),
    grab(r"function _phValid\(d\)\{[^\n]*\}", "_phValid"),
    grab(r"async function compressPhoto\(file\)\{.*?\n\}", "compressPhoto"),
    grab(r"async function photoFromUrl\(url\)\{.*?\n\}", "photoFromUrl"),
]
print("從 index.html 抽出 %d 段真實程式碼" % len(parts))

CASES = [
    ("SHOPLINE 圖床（庫存實際會遇到的）",
     "https://img.shoplineapp.com/media/image_clips/6853d9937432bb11d6ea0b05/original.png?1750325651", True),
    ("catbox 臨時空間（庫存有 21 張）", "https://files.catbox.moe/8sxr4o.jpg", None),
    ("蝦皮圖床", "https://down-tw.img.susercontent.com/file/tw-11134207-7r98o-lssr0f1q3n7z8b", None),
    ("根本不是圖（HTML 頁）", "https://example.com/", False),
    ("不存在的圖", "https://yamusic.com.tw/zzz-not-a-real-image.jpg", False),
    ("危險協議要被擋", "javascript:alert(1)", False),
    ("內網位址要被擋（SSRF）", "http://127.0.0.1:8080/x.jpg", False),
]

PAGE = """<!doctype html><meta charset="utf-8"><body><pre id="out">running…</pre>
<script>
%s

const CASES = %s;
const OWN = [
  ["https://yamusic.com.tw/static/uploads/products/p1_0.jpg", true],
  ["https://www.yamusic.com.tw/x.jpg", true],
  ["https://img.shoplineapp.com/a.png", false],
  ["https://evil-yamusic.com.tw.attacker.net/a.jpg", false],
  ["", false]
];

function say(lines){
  document.getElementById("out").textContent = lines.join("\\n");
  try{ fetch("/result", {method:"POST", body: lines.join("\\n")}); }catch(e){}
}

(async () => {
  const lines = [];
  try {
    lines.push("== isOwnImgUrl（判斷是不是我們自己的圖）==");
    for (const [u, want] of OWN) {
      const got = !!isOwnImgUrl(u);
      lines.push((got === want ? "PASS  " : "FAIL  ") + (u || "(空字串)") + "  -> " + got);
    }
    lines.push("");
    lines.push("== photoFromUrl（真的去抓、真的壓縮）==");
    for (const c of CASES) {
      const [label, url, want] = c;
      try {
        const p = await photoFromUrl(url);
        const okShape = p && typeof p.t === "string" && p.t.indexOf("data:image/") === 0
                          && typeof p.d === "string" && p.d.indexOf("data:image/") === 0;
        const kb = Math.round((p && p.bytes || 0) / 1024);
        if (want === false) lines.push("FAIL  " + label + "  -> 不該成功卻成功了");
        else if (!okShape) lines.push("FAIL  " + label + "  -> 回傳的格式不對");
        else lines.push("PASS  " + label + "  -> 抓到並壓好 (" + kb + "KB, " + p.w + "x" + p.h + ")");
      } catch (e) {
        const msg = (e && e.message) || String(e);
        if (want === true) lines.push("FAIL  " + label + "  -> 應該成功卻失敗：" + msg);
        else if (want === false) lines.push("PASS  " + label + "  -> 正確擋下：" + msg);
        else lines.push("INFO  " + label + "  -> 抓不到，程式有正確回報：" + msg);
      }
    }
  } catch (e) {
    lines.push("FATAL " + ((e && e.stack) || e));
  }
  lines.push("== DONE ==");
  say(lines);
})();
</script></body>""" % ("\n".join(parts), json.dumps(CASES, ensure_ascii=False))

result = {"body": None}
evt = threading.Event()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        b = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        result["body"] = self.rfile.read(n).decode("utf-8", "replace")
        self.send_response(204)
        self.end_headers()
        evt.set()


srv = HTTPServer(("127.0.0.1", 8731), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

proc = subprocess.Popen(
    [CHROME, "--headless", "--disable-gpu", "--no-first-run",
     "--user-data-dir=" + os.path.join(HERE, "_t_profile"),
     "http://127.0.0.1:8731/"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
got = evt.wait(150)
proc.terminate()
srv.shutdown()

print()
print(result["body"] if got else "（逾時，頁面沒有回報結果）")

import shutil
shutil.rmtree(os.path.join(HERE, "_t_profile"), ignore_errors=True)
