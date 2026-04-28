import json
import boto3
import urllib.request

TELEGRAM_TOKEN = TOKEN
CHAT_ID = "7846778914"

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('BLEScans')

# Anchor node friendly names
ANCHOR_NAMES = {
    "esp32-c6-ble":     "Canteen",
    "maker-feather-s3": "Library",
    "board-c":          "Classroom"
}

# Items and their ESP32 MAC addresses (update with real MACs later)
ITEMS = {
    "🔑 Keys": "Tag-Keys",  # ← BLE name
    "Earphones" : "Bowie WM01"
}

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)

def send_keyboard(text, options):
    keyboard = [[{"text": opt}] for opt in options]
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id": CHAT_ID,
        "text": text,
        "reply_markup": {
            "keyboard": keyboard,
            "one_time_keyboard": True,
            "resize_keyboard": True
        }
    }).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)

def locate_item(item_name):
    mac = ITEMS.get(item_name)
    if not mac:
        return f"❌ Unknown item!"

    # Scan DynamoDB for all readings of this MAC
    response = table.scan()
    items = response.get("Items", [])

    # Find strongest RSSI per anchor for this MAC
    anchor_rssi = {}
    for item in items:
        if item.get("name", "").lower() == mac.lower():
            thing = item["thing"]
            rssi = float(item["rssi"])
            ts = int(item["ts"])
            if thing not in anchor_rssi or ts > anchor_rssi[thing]["ts"]:
                anchor_rssi[thing] = {"rssi": rssi, "ts": ts}

    if not anchor_rssi:
        return (
            f"⚠️ *{item_name}* not found!\n"
            f"Make sure the tag is powered on."
        )

    # Find anchor with strongest RSSI (closest to 0)
    nearest = max(anchor_rssi, key=lambda k: anchor_rssi[k]["rssi"])
    location = ANCHOR_NAMES.get(nearest, nearest)
    rssi_val = anchor_rssi[nearest]["rssi"]

    return (
        f"📍 *{item_name}* was last seen near:\n\n"
        f"📌 *{location}*\n"
        f"📶 Signal strength: {rssi_val} dBm\n"
        f"👁 Seen by {len(anchor_rssi)} anchor(s)"
    )

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        message = body.get("message", {})
        text = message.get("text", "").strip()

        if text in ["/start", "/lost"]:
            send_keyboard(
                "🔍 Which item did you lose?",
                list(ITEMS.keys())
            )

        elif text in ITEMS:
            result = locate_item(text)
            send_message(result)

        elif text == "/status":
            send_message(
                "✅ *BLE Tracker Online*\n\n"
                f"📦 Tracking {len(ITEMS)} items\n"
                f"📡 {len(ANCHOR_NAMES)} anchor nodes\n\n"
                "Send /lost to locate an item!"
            )

        else:
            send_message(
                "👋 Welcome to BLE Tracker!\n\n"
                "/lost — Find a lost item\n"
                "/status — System status"
            )

    except Exception as e:
        print(f"Error: {str(e)}")
        send_message(f"❌ Error: {str(e)}")

    return {"statusCode": 200}