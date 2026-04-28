# I Built a BLE Tracker That Texts You When You Lose Your Stuff 📡

By Daniel Napitu

---

Ok so this started because I kept losing things. Like genuinely could not keep track of my 
bag, my keys, nothing.

So I built a BLE-based asset tracking system. Small ESP32 tags sit on your items and 
broadcast their name over Bluetooth constantly. Anchor nodes placed around the space 
pick up those signals and report to AWS. When you want to find something, you just text 
your Telegram bot and it tells you where it was last seen.

No app. No frontend. No drama. Just Telegram.

---

## How It Actually Works

There are two types of boards in this system:

**Tags** — sit on your item (bag, keys, earphones, whatever). They do literally one thing: 
broadcast their name over BLE. That's it. They're just constantly going "I'M HERE, I'M HERE" 
all day.

**Anchor Nodes** — fixed around the space. They scan for nearby BLE devices every few 
seconds, and whenever they find one they publish the device name, MAC address, signal 
strength (RSSI), and a timestamp to AWS via WiFi and MQTT. They also advertise their own 
BLE name so other anchors can detect them too.

The logic for finding something is simple, whichever anchor had the strongest signal 
for your item's tag is the one it's closest to. That's your location.

```
Tag broadcasts BLE ("Tag-Keys", "Bowie WM01", etc.)
         ↓
Anchor node picks it up, publishes to AWS IoT Core via MQTT
         ↓
IoT Core Rule triggers Lambda → stores in DynamoDB
         ↓
You text /lost on Telegram
         ↓
Bot checks DynamoDB, finds strongest RSSI, replies:
"Your Keys were last seen near: Canteen 📍"
```

Simple, clean, and it actually works.

---

## What You Need

**Hardware:**
- 2x ESP32-C6 DevKitC (Espressif official boards)
- USB-C cables — make sure they're data cables, not charge-only. 
  I spent way too long troubleshooting a connection issue that was just a bad cable.
- Powerbank if you want the tag to run without being plugged into a computer

**Accounts:**
- AWS Free Tier — you genuinely won't get charged for this project
- Telegram

**Arduino Libraries:**
- PubSubClient by Nick O'Leary
- ArduinoJson by Benoit Blanchon
- NimBLE-Arduino by h2zero

---

## Step 1: Getting Arduino IDE to Talk to the ESP32-C6

Add this in **File → Preferences → Additional Board Manager URLs:**
```
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

Install the ESP32 package via **Tools → Board → Board Manager**, select **ESP32C6 Dev Module**.

**If upload keeps failing:** Hold BOOT, press and release RESET, let go of BOOT, click Upload.
This is the move every single time.

**If Serial Monitor shows nothing:** Press the physical RESET button after uploading. 
Also check baud rate is 115200. I forgot this more times than I'd like to admit.

**On Mac, finding the right port:** Run `ls /dev/cu.*` in Terminal before and after plugging 
in the board. Whatever new entry appears — that's your port. The `/dev/cu.URT0` one that 
sometimes shows up by default doesn't work.

**Before uploading:** Set **Tools → Partition Scheme → Huge APP (3MB No OTA)**. NimBLE + 
WiFi + TLS together is too big for the default partition. You'll get "sketch too big (108%)" 
if you forget this.

---

## Step 2: AWS IoT Core — Creating Your Things

Go to AWS IoT Core (region: ap-southeast-1 if you're in Singapore) and create a Thing 
for each anchor node.

1. **Manage → Things → Create single thing**
2. Name it (e.g. Node-A, Node-B)
3. Auto-generate certificate
4. Create a policy called `esp32-ble-policy`:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["iot:Connect", "iot:Publish", "iot:Subscribe", "iot:Receive"],
    "Resource": "*"
  }]
}
```

5. Download all the certificate files. You only get one chance. Do it.

Get your endpoint via CloudShell:
```bash
aws iot describe-endpoint --endpoint-type iot:Data-ATS
```

---

## Step 3: The Anchor Node Code (blink.ino)

Each anchor runs the same code — just change THING_NAME and the BLE advertised name per board.

```cpp
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <NimBLEDevice.h>
#include <NimBLEServer.h>
#include <NimBLEAdvertising.h>

#define WIFI_SSID     "SUTD_Guest"
#define WIFI_PASSWORD ""
#define AWS_ENDPOINT  "YOUR_ENDPOINT-ats.iot.ap-southeast-1.amazonaws.com"
#define MQTT_TOPIC    "esp32/ble/scan"
#define THING_NAME    "Node B"   // ← change per board

// Paste your Root CA, Device Cert, Private Key here

WiFiClientSecure net;
PubSubClient mqtt(net);

void startAdvertising() {
  NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
  adv->setName("Node B");   // ← change per board
  adv->start();
}

class ScanCallbacks : public NimBLEScanCallbacks {
  void onResult(const NimBLEAdvertisedDevice* device) override {
    JsonDocument doc;
    doc["thing"] = THING_NAME;
    doc["mac"]   = device->getAddress().toString().c_str();
    doc["rssi"]  = device->getRSSI();
    doc["name"]  = device->haveName() ? device->getName().c_str() : "Unknown";
    doc["ts"]    = millis();

    char payload[256];
    serializeJson(doc, payload);
    if (mqtt.connected()) mqtt.publish(MQTT_TOPIC, payload);
  }
};

void scanAndPublish() {
  NimBLEDevice::getAdvertising()->stop();
  NimBLEDevice::getScan()->start(8, false); // 8 second scan window
  NimBLEDevice::getScan()->clearResults();
  NimBLEDevice::getAdvertising()->start();
}

void setup() {
  Serial.begin(115200);
  connectWiFi();
  NimBLEDevice::init("Node B");   // ← change per board

  NimBLEScan* scan = NimBLEDevice::getScan();
  scan->setScanCallbacks(new ScanCallbacks(), false);
  scan->setActiveScan(true);
  scan->setInterval(100);
  scan->setWindow(99);

  startAdvertising();
  connectMQTT();
}

void loop() {
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();
  scanAndPublish();
  delay(3000);
}
```

When it's working, Serial Monitor looks like this:
```
=== ESP32-C6 BLE Anchor + Scanner ===
WiFi connected! IP: 10.37.0.229
BLE Advertising started as: Node B
Connected to AWS IoT Core!
Starting BLE scan...
Published: {"thing":"Node B","mac":"98:a3:16:b1:d5:2a","rssi":-42,"name":"Tag-Keys","ts":94367}
Scan complete!
```

The scan briefly stops advertising while it runs (you can't do both simultaneously on BLE 
hardware), then resumes. The 8-second scan window is the sweet spot I landed on after 
testing — long enough to reliably catch nearby devices, not so long that it's offline 
for advertising for ages.

---

## Step 4: DynamoDB

Go to DynamoDB, create a table called `BLEScans`:
- Partition key: `mac` — String
- Sort key: `ts` — Number

Leave everything else default. That's it for this step.

---

## Step 5: Lambda to Store Scan Data (StoringRSSI.py)

This Lambda triggers every time IoT Core receives an MQTT message and writes it to DynamoDB.

```python
import json
import boto3
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('BLEScans')

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    
    try:
        mac   = event['mac']
        ts    = Decimal(str(event['ts']))
        rssi  = Decimal(str(event['rssi']))
        name  = event.get('name', 'Unknown')
        thing = event.get('thing', 'Unknown')
        
        table.put_item(Item={
            'mac':   mac,
            'ts':    ts,
            'rssi':  rssi,
            'name':  name,
            'thing': thing
        })
        
        print(f"Stored: {mac} | RSSI: {rssi} | from: {thing}")
        return {'statusCode': 200, 'body': 'OK'}
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {'statusCode': 500, 'body': str(e)}
```

The `Decimal(str(...))` thing for RSSI and ts is important — DynamoDB doesn't accept 
Python floats directly. Spent longer than I should have on a ValidationException before 
figuring this out.

Setup:
- Attach `AmazonDynamoDBFullAccess` to the Lambda's IAM role
- In IoT Core, create a Rule: SQL `SELECT * FROM 'esp32/ble/scan'` → Action: Lambda → this function

---

## Step 6: Telegram Bot Setup

1. Find **@BotFather** on Telegram → `/newbot` → save your token
2. Find **@userinfobot** → send any message → save your Chat ID

Then create an HTTP API in API Gateway:
- Add integration → Lambda → your bot Lambda
- Create route: POST `/webhook`
- Deploy to `$default` stage

Register the webhook in CloudShell:
```bash
curl -X POST https://api.telegram.org/botYOUR_TOKEN/setWebhook?url=https://YOUR_API_GW_URL/webhook
```

Should return `{"ok":true,"result":true}`. If you get 404, token is wrong. If 403, check API Gateway is deployed.

---

## Step 7: The Telegram Bot Lambda (TeleBot.py)

This handles all the Telegram interactions. User sends /lost, gets a keyboard, picks an 
item, gets back the location. The key design decision: track by BLE name, not MAC address. 
MAC addresses randomize constantly (phones do this, ESP32s can too). Names don't.

```python
import json
import boto3
import urllib.request

TELEGRAM_TOKEN = "YOUR_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('BLEScans')

ANCHOR_NAMES = {
    "Node A":  "Canteen",
    "Node B":  "Library",
}

ITEMS = {
    "🔑 Keys":   "Tag-Keys",
    "Earphones": "Bowie WM01"
}

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)

def send_keyboard(text, options):
    keyboard = [[{"text": opt}] for opt in options]
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id": CHAT_ID, "text": text,
        "reply_markup": {"keyboard": keyboard, "one_time_keyboard": True, "resize_keyboard": True}
    }).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)

def locate_item(item_name):
    tag_name = ITEMS.get(item_name)
    if not tag_name:
        return "❌ Unknown item!"

    items = table.scan().get("Items", [])
    anchor_rssi = {}

    for item in items:
        if item.get("name", "").lower() == tag_name.lower():
            thing = item["thing"]
            rssi = float(item["rssi"])
            ts = int(item["ts"])
            if thing not in anchor_rssi or ts > anchor_rssi[thing]["ts"]:
                anchor_rssi[thing] = {"rssi": rssi, "ts": ts}

    if not anchor_rssi:
        return f"⚠️ *{item_name}* not found!\nMake sure the tag is powered on."

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
        text = body.get("message", {}).get("text", "").strip()

        if text in ["/start", "/lost"]:
            send_keyboard("🔍 Which item did you lose?", list(ITEMS.keys()))
        elif text in ITEMS:
            send_message(locate_item(text))
        elif text == "/status":
            send_message(f"✅ *BLE Tracker Online*\n\n📦 Tracking {len(ITEMS)} items\n📡 {len(ANCHOR_NAMES)} anchor nodes\n\nSend /lost to locate an item!")
        else:
            send_message("👋 Welcome to BLE Tracker!\n\n/lost — Find a lost item\n/status — System status")

    except Exception as e:
        print(f"Error: {str(e)}")
        send_message(f"❌ Error: {str(e)}")

    return {"statusCode": 200}
```

Set timeout to **30 seconds** — default 3 seconds isn't enough for Telegram API calls 
plus DynamoDB. You'll get a sandbox timeout error if you forget this.

---

## The Result

```
You: /lost

Bot: 🔍 Which item did you lose?
     [🔑 Keys]  [Earphones]

You: 🔑 Keys

Bot: 📍 Keys was last seen near:
     📌 Canteen
     📶 Signal strength: -42 dBm
     👁 Seen by 1 anchor(s)
```

Works on your phone, anywhere, anytime. Total AWS cost: $0.

---

## Architecture

```
ESP32-C6 Tag
└── Advertises BLE name ("Tag-Keys", "Bowie WM01")

ESP32-C6 Anchor Node (x2, named Node A / Node B)
├── BLE scan every 3 seconds
├── Publishes to AWS IoT Core via MQTT (port 8883, TLS)
└── Also advertises own BLE name

AWS IoT Core
└── Rule: SELECT * FROM 'esp32/ble/scan'
    └── Lambda: StoringRSSI.py → DynamoDB (BLEScans)

Telegram
└── API Gateway POST /webhook
    └── Lambda: TeleBot.py → DynamoDB → reply with location
```

---

## What I'd Do Differently

If I was starting over, I would use 3 anchor nodes instead of 2 from the beginning. 
With 3 you can do proper trilateration and get actual x/y coordinates rather than 
just "nearest anchor". Would also test my USB cables earlier because one bad cable 
cost me like 30 minutes of my life.

But as a working proof of concept? It does exactly what it's supposed to do, 
runs for free on AWS, and lives in Telegram which honestly makes way more sense 
than building a frontend. I'm happy with it 🫡
