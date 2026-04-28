from awsiot import mqtt5_client_builder
from awscrt import mqtt5
import threading
import time
import json

endpoint = "a3fjs7l9x4f669-ats.iot.ap-southeast-1.amazonaws.com"
cert_filepath = "/Users/oka_kurniawan/OneDriveSUTD/60_003_Product_Design_Studio/AWS_IoT/Certificates/98704745be7ade8a767c79e70051314d226cb69ee004a0e226a255e66a79690b-certificate.pem.crt"
key_filepath = "/Users/oka_kurniawan/OneDriveSUTD/60_003_Product_Design_Studio/AWS_IoT/Certificates/98704745be7ade8a767c79e70051314d226cb69ee004a0e226a255e66a79690b-private.pem.key"
client_id = "basicPubSub"

TIMEOUT = 100
message_topic = "esp32/esp32-to-aws"

# Events used within callbacks to progress sample
connection_success_event = threading.Event()
stopped_event = threading.Event()


# Callback when any publish is received
def on_publish_received(publish_packet_data):
    publish_packet = publish_packet_data.publish_packet
    print("==== Received message from topic '{}': {} ====\n".format(
        publish_packet.topic, publish_packet.payload.decode('utf-8')))
    data_json = publish_packet.payload.decode('utf-8')
    data_dict = json.loads(data_json)
    if data_dict["data"] is not None:
        print(data_dict["timestamp"], data_dict["data"])


# Callback for the lifecycle event Stopped
def on_lifecycle_stopped(lifecycle_stopped_data: mqtt5.LifecycleStoppedData):
    print("Lifecycle Stopped\n")
    stopped_event.set()


# Callback for lifecycle event Attempting Connect
def on_lifecycle_attempting_connect(lifecycle_attempting_connect_data: mqtt5.LifecycleAttemptingConnectData):
    print("Lifecycle Connection Attempt\nConnecting to endpoint: '{}' with client ID'{}'".format(
        endpoint, client_id))


# Callback for the lifecycle event Connection Success
def on_lifecycle_connection_success(lifecycle_connect_success_data: mqtt5.LifecycleConnectSuccessData):
    connack_packet = lifecycle_connect_success_data.connack_packet
    print("Lifecycle Connection Success with reason code:{}\n".format(
        repr(connack_packet.reason_code)))
    connection_success_event.set()


# Callback for the lifecycle event Connection Failure
def on_lifecycle_connection_failure(lifecycle_connection_failure: mqtt5.LifecycleConnectFailureData):
    print("Lifecycle Connection Failure with exception:{}".format(
        lifecycle_connection_failure.exception))


# Callback for the lifecycle event Disconnection
def on_lifecycle_disconnection(lifecycle_disconnect_data: mqtt5.LifecycleDisconnectData):
    print("Lifecycle Disconnected with reason code:{}".format(
        lifecycle_disconnect_data.disconnect_packet.reason_code if lifecycle_disconnect_data.disconnect_packet else "None"))


if __name__ == "__main__":
    client = mqtt5_client_builder.mtls_from_path(
        endpoint=endpoint,
        cert_filepath=cert_filepath,
        pri_key_filepath=key_filepath,
        on_publish_received=on_publish_received,
        on_lifecycle_stopped=on_lifecycle_stopped,
        on_lifecycle_attempting_connect=on_lifecycle_attempting_connect,
        on_lifecycle_connection_success=on_lifecycle_connection_success,
        on_lifecycle_connection_failure=on_lifecycle_connection_failure,
        on_lifecycle_disconnection=on_lifecycle_disconnection,
        client_id=client_id)

    print("==== Starting client ====")
    client.start()

    if not connection_success_event.wait(TIMEOUT):
        raise TimeoutError("Connection timeout")

    # Subscribe
    print("==== Subscribing to topic '{}' ====".format(message_topic))
    subscribe_future = client.subscribe(subscribe_packet=mqtt5.SubscribePacket(
        subscriptions=[mqtt5.Subscription(
            topic_filter=message_topic,
            qos=mqtt5.QoS.AT_LEAST_ONCE)]
    ))
    suback = subscribe_future.result(TIMEOUT)
    print("Suback received with reason code:{}\n".format(suback.reason_codes))

    while True:
        print("looping waiting for message.")
        time.sleep(1)
