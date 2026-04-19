"""
Local backup for Firebase inventory data.
Saves logs + items to D:/Coding/inventory/backups/YYYY-MM-DD_HHmm.json.
Keeps only the most recent N backups to bound disk use.
"""
import json, os, sys, io, urllib.request, datetime, glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

FIREBASE_BASE = "https://order-system-dddca-default-rtdb.firebaseio.com"
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
KEEP = 168  # ~7 days if run hourly

os.makedirs(BACKUP_DIR, exist_ok=True)


def fetch(path):
    url = f"{FIREBASE_BASE}/{path}.json"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def main():
    snapshot = {
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "items": fetch("inventory/items"),
        "logs": fetch("inventory/logs"),
        "order": fetch("inventory/order"),
    }
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    path = os.path.join(BACKUP_DIR, f"{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    items_count = len([x for x in (snapshot["items"] or []) if x])
    logs_count = len(snapshot["logs"] or [])
    print(f"[{stamp}] saved {path} ({items_count} items, {logs_count} logs)")

    files = sorted(glob.glob(os.path.join(BACKUP_DIR, "*.json")))
    if len(files) > KEEP:
        for old in files[:len(files) - KEEP]:
            os.remove(old)
            print(f"  pruned {os.path.basename(old)}")


if __name__ == "__main__":
    main()
