"""test_broker_db_sync.py

Tests the various database operations done by the broker_db_sync module:
- test success scenarios
- test adding wrong data formats and key constraint fails to websites and website_status tables
"""

from psycopg2.errors import (
    UniqueViolation,
    ForeignKeyViolation,
    InvalidDatetimeFormat,
)
from json.decoder import JSONDecodeError

import pytest
import kafka
import datetime

from app.utils import AttrDict

import app.utils as utils
import app.website_checker as website_checker
import app.broker_db_sync as broker_db_sync


def test_insert_correct_website_status(monkeypatch):
    """Tests to see if inserting a valid website status entry works

    """
    # First, we create a valid website for testing (can be a fictitious url)
    website_id = utils.add_new_website('https://gitlab.com', test=True)

    # Create a mock kafka consumer
    class mock_kafka_consumer():
        def __init__(self, *args, **kwargs):
            self.messages = [
                AttrDict(
                    topic='test',
                    partition=0,
                    offset=0,
                    key=None,
                    value="""{{
                        "website_db_id": "{}",
                        "timestamp_utc": "{}"
                    }}""".format(
                        website_id,
                        str(datetime.datetime.utcnow()),
                    )
                )
            ]
            super().__init__()

        def close(self):
            pass

        def __iter__(self):
            return iter(self.messages)

    with utils.connect_to_db(test=True) as cursor:
        monkeypatch.setattr(kafka, 'KafkaConsumer', mock_kafka_consumer)

        message_received, _ = broker_db_sync.sync_to_db('test', True)
        print('Got message from kafka broker')

        assert message_received

def test_insert_incorrect_website_status(monkeypatch):
    """Tests to see if inserting invalid website status entries fail
    """
    # First, we create a valid website entry for testing (can be a fictitious url)
    website_id = utils.add_new_website('https://gitlab2.com', test=True)

    # Initialize some valid values
    timestamp_utc = str(datetime.datetime.utcnow())
    json_data = '{"test": "hello world"}'

    # Second, we will insert a valid entry so we can test for primary key constraint
    # fails later
    with utils.connect_to_db(test=True) as cursor:
        with utils.connect_to_db(test=True) as cursor:
            cursor.execute('INSERT INTO website_status\
                (kafka_topic, kafka_partition_id, kafka_offset_id, website_id, timestamp_utc, request_info)\
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING request_info',
                (
                    'test', 0, 1, website_id,
                    timestamp_utc, json_data
                )
            )

    # Now, we test for various failure scenarios (extra quote mark ")
    fail_messages = [
        # Test incorrect JSON format
        AttrDict(
            topic='test',
            partition=0,
            offset=0,
            key=None,
            value="""{{
                ""website_db_id": "{}",
                "timestamp_utc": "{}"
            }}""".format(
                website_id,
                timestamp_utc,
            ),
            exception=JSONDecodeError,
        ),
        # Test primary key constraint (offset = 1 already exists)
        AttrDict(
            topic='test',
            partition=0,
            offset=1,
            key=None,
            value="""{{
                "website_db_id": "{}",
                "timestamp_utc": "{}"
            }}""".format(
                website_id,
                timestamp_utc,
            ),
            exception=UniqueViolation,
        ),
        # Test foreign key constraint (website_id 99 does not exist)
        AttrDict(
            topic='test',
            partition=0,
            offset=2,
            key=None,
            value="""{{
                "website_db_id": "{}",
                "timestamp_utc": "{}"
            }}""".format(
                99,
                timestamp_utc,
            ),
            exception=ForeignKeyViolation,
        ),
        # Test invalid datetime format (timestamp_utc is an empty string)
        AttrDict(
            topic='test',
            partition=0,
            offset=2,
            key=None,
            value="""{{
                "website_db_id": "{}",
                "timestamp_utc": "{}"
            }}""".format(
                website_id,
                '',
            ),
            exception=InvalidDatetimeFormat,
        ),
    ]

    for fail_message in fail_messages:
        # Create a mock kafka consumer
        class mock_kafka_consumer():
            def __init__(self, *args, **kwargs):
                self.messages = [fail_message]
                super().__init__()

            def close(self):
                pass

            def __iter__(self):
                return iter(self.messages)

        with utils.connect_to_db(test=True) as cursor:
            monkeypatch.setattr(kafka, 'KafkaConsumer', mock_kafka_consumer)

            message_received, exception = broker_db_sync.sync_to_db('test', True)
            print('Got message from kafka broker')

            assert type(exception) == fail_message.exception
