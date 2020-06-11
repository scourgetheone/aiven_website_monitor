"""broker_db_sync.py

consumes the Kafka messages, process the data, and then save it into the _website_status_ table
"""
from json.decoder import JSONDecodeError
from psycopg2.errors import (
    UniqueViolation,
    ForeignKeyViolation,
    InvalidDatetimeFormat,
)

import kafka
import json

import app.utils as utils

def sync_to_db(kafka_topic='website_status', test=False):
    """Fetches messages from Kafka and persist them to the pgsql database

        Args:
        - kafka_topic str: the name of the kafka topic
        - test bool: if True, sets the offset to 'earliest'
          and return the first result only
    """
    try:
        # HACK: auto_offset_reset is set to earliest when testing
        # because I can't figure out (yet) why the in test_end_to_end_function
        # the broker always starts from offset 1 (should start from 0?)
        consumer = kafka.KafkaConsumer(
            kafka_topic,
            auto_offset_reset='earliest' if test else 'latest',
            group_id='test_group',
            **utils.read_json_config('kafka_config.json'),
        )

        with utils.connect_to_db(test=test, include_conn=True) as conn_obj:
            conn, cursor = conn_obj

            # Read from website_status topic and sync to the database
            for message in consumer:
                print ("%s:%d:%d: key=%s value=%s" % (message.topic, message.partition,
                    message.offset, message.key,
                    message.value))

                json_message = json.loads(message.value)

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
                # Commit after every successful fetch from the Kafka broker
                conn.commit()

                if test:
                    consumer.close()
                    return message

    except JSONDecodeError as e:
        print(e)
        return message, JSONDecodeError
    except UniqueViolation as e:
        print(e)
        return message, UniqueViolation
    except ForeignKeyViolation as e:
        print(e)
        return message, ForeignKeyViolation
    except InvalidDatetimeFormat as e:
        print(e)
        return message, InvalidDatetimeFormat

    except KeyboardInterrupt:
        consumer.close()


if __name__ == '__main__':
    sync_to_db()
