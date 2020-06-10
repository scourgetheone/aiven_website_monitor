# https://help.aiven.io/en/articles/489573-getting-started-with-aiven-postgresql
# http://maximilianchrist.com/python/databases/2016/08/13/connect-to-apache-kafka-from-python-using-ssl.html

from kafka import KafkaConsumer

import json

import app.utils as utils

def sync_to_db():
    consumer = KafkaConsumer(
        'website_status',
        #auto_offset_reset='earliest',
        #enable_auto_commit=False,
        group_id='test_group',
        **utils.read_json_config('kafka_config.json'),
    )

    # Read from website_status topic and sync to the database
    for message in consumer:
        print ("%s:%d:%d: key=%s value=%s" % (message.topic, message.partition,
            message.offset, message.key,
            message.value))

        json_message = json.loads(message.value)

        with utils.connect_to_db() as cursor:
            cursor.execute('INSERT INTO website_status\
                (kafka_topic, kafka_partition_id, kafka_offset_id, website_id, timestamp_utc, request_info)\
                VALUES (%s, %s, %s, %s, %s, %s)',
                (
                    message.topic,
                    message.partition,
                    message.offset,
                    json_message['website_db_id'],
                    json_message['timestamp_utc'],
                    json.dumps(json_message),
                )
            )


if __name__ == '__main__':
    sync_to_db()
