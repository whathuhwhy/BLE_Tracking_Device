/*
 * This ESP32 code is created by esp32io.com
 *
 * This ESP32 code is released in the public domain
 *
 * For more detail (instruction and wiring diagram), visit https://esp32io.com/tutorials/esp32-aws-iot
 */

#include "secrets.h"
#include <WiFiClientSecure.h>
#include <MQTTClient.h>
#include <ArduinoJson.h>
#include "WiFi.h"

// The MQTT topics that this device should publish/subscribe
#define AWS_IOT_PUBLISH_TOPIC "esp32/esp32-to-aws"
#define AWS_IOT_SUBSCRIBE_TOPIC "esp32/aws-to-esp32"

#define PUBLISH_INTERVAL 4000  // 4 seconds

WiFiClientSecure net = WiFiClientSecure();
MQTTClient client = MQTTClient(256);

unsigned long lastPublishTime = 0;

void setup() {
  Serial.begin(9600);

  // set the ADC attenuation to 11 dB (up to ~3.3V input)
  analogSetAttenuation(ADC_11db);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.println("ESP32 connecting to Wi-Fi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  connectToAWS();
}

void loop() {
  client.loop();

  if (millis() - lastPublishTime > PUBLISH_INTERVAL) {
    sendToAWS();
    lastPublishTime = millis();
  }
}

void connectToAWS() {
  // Configure WiFiClientSecure to use the AWS IoT device credentials
  net.setCACert(AWS_CERT_CA);
  net.setCertificate(AWS_CERT_CRT);
  net.setPrivateKey(AWS_CERT_PRIVATE);

  // Connect to the MQTT broker on the AWS endpoint we defined earlier
  client.begin(AWS_IOT_ENDPOINT, 8883, net);

  // Create a handler for incoming messages
  client.onMessage(messageHandler);

  Serial.print("ESP32 connecting to AWS IOT");

  while (!client.connect(THINGNAME)) {
    Serial.print(".");
    delay(100);
  }
  Serial.println();

  if (!client.connected()) {
    Serial.println("ESP32 - AWS IoT Timeout!");
    return;
  }

  // Subscribe to a topic, the incoming messages are processed by messageHandler() function
  client.subscribe(AWS_IOT_SUBSCRIBE_TOPIC);

  Serial.println("ESP32  - AWS IoT Connected!");
}

void sendToAWS() {
  StaticJsonDocument<200> message;
  message["timestamp"] = millis();
  message["data"] = analogRead(0); // Or you can read data from other sensors
  char messageBuffer[512];
  serializeJson(message, messageBuffer);  // print to client

  client.publish(AWS_IOT_PUBLISH_TOPIC, messageBuffer);

  Serial.println("sent:");
  Serial.print("- topic: ");
  Serial.println(AWS_IOT_PUBLISH_TOPIC);
  Serial.print("- payload:");
  Serial.println(messageBuffer);
}

void messageHandler(String &topic, String &payload) {
  Serial.println("received:");
  Serial.println("- topic: " + topic);
  Serial.println("- payload:");
  Serial.println(payload);

  // You can process the incoming data as json object, then control something
  /*
  StaticJsonDocument<200> doc;
  deserializeJson(doc, payload);
  const char* message = doc["message"];
  */
}
