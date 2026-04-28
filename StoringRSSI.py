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