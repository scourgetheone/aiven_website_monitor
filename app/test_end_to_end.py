"""test_end_to_end.py

Tests the end to end functionality between the website_checker and broker_db_sync modules:
- test polling the wesbite using
- test the data format going in and out of the kafka service
- test adding the website check message to the database
"""
from kafka import KafkaProducer
from psycopg2.errors import (
    NotNullViolation,
    InvalidTextRepresentation,
    UniqueViolation,
)

import pytest
import requests
import psycopg2
import json

from app.utils import AttrDict

import app.utils as utils
import app.website_checker as website_checker
import app.broker_db_sync as broker_db_sync


@pytest.fixture(scope='module')
def producer():
    producer = KafkaProducer(
        value_serializer=lambda m: json.dumps(m).encode('ascii'),
        **utils.read_json_config('kafka_config.json'),
    )
    return producer

def test_end_to_end_function(producer, monkeypatch):
    """Entire end-to-end test to see if website gets polled and
    the data goes through the Kafka messaging system properly.
    """
    # First, add a website that we know will work
    website = None
    try:
        website_id = utils.add_new_website('https://google.com', test=True)
        website = utils.get_websites(id=website_id, test=True)
    except psycopg2.errors.UniqueViolation:
        print('website already exists!')
        print('Database tables were not properly removed during last test round!')

        website = utils.get_websites()[0]

    # Here we mock the requests function, since we don't want to
    # rely on external websites that may be down
    def mock_requests_get(_):
        return AttrDict(
            status_code=200,
            elapsed=AttrDict(
                seconds=2,
                microseconds=123,
            ),
            text="<div>Mock data</div>"
        )

    monkeypatch.setattr(requests, 'get', mock_requests_get)

    message_to_send = website_checker.poll_website(producer, website, 'test')
    print('Polled website and sent message from kafka broker')

    message_received, _ = broker_db_sync.sync_to_db('test', True)
    print('Got message from kafka broker and forwarded to the database')

    # Verify that the kafka topic is 'test', and the partition and offset
    # are both at 0 (make sure that we are on an empty kafka topic)
    assert message_received.topic == 'test'
    assert message_received.partition == 0
    assert message_received.offset == 0

    json_message_received = json.loads(message_received.value)

    # Verify that the message data remained intact through Kafka
    for key, _ in json_message_received.items():
        assert json_message_received[key] == message_to_send[key]

    # Verify that the message is in the database
    with utils.connect_to_db(test=True) as cursor:
        cursor.execute('SELECT * FROM website_status WHERE website_id = {}'.format(
            website['id']
        ))
        row = cursor.fetchone()

        assert row['kafka_topic']        == message_received.topic
        assert row['kafka_partition_id'] == message_received.partition
        assert row['kafka_offset_id']    == message_received.offset
        assert row['website_id']         == json_message_received['website_db_id']
        assert str(row['timestamp_utc']) == json_message_received['timestamp_utc']

        json_from_db = row['request_info']

        for key, _ in json_from_db.items():
            assert json_from_db[key] == json_message_received[key]

    print('Finished test_end_to_end')

#
# ** Database-related **
#

def test_insert_correct_website_data():
    """Tests to see if inserting a valid website entry works
    """
    with utils.connect_to_db(test=True) as cursor:
        cursor.execute('INSERT INTO websites (url, check_interval, up_regex)\
            VALUES (%s, %s, %s) RETURNING id',
            ('https://facebook.com', 6, ''))

        # Return the id of the newly created website entry
        row = cursor.fetchone()
        assert row

def test_insert_incorrect_website_data():
    """Tests to see if inserting invalid website entries fail
    """
    # First we put in a valid entry.
    # We will test uniqueness of the url later
    with utils.connect_to_db(test=True) as cursor:
        cursor.execute('INSERT INTO websites (url, check_interval, up_regex)\
            VALUES (%s, %s, %s) RETURNING id',
            ('https://aiven.io', 6, ''))

    test_data = [
        [None, 4, None, NotNullViolation], # Null url
        ['asd', 'asd', None, InvalidTextRepresentation], # Non integer for check_interval
        ['https://aiven.io', 4, None, UniqueViolation], # Unique constraint check
    ]

    for data in test_data:
        exception = data.pop()

        with pytest.raises(exception):
            # NOTE: We create a new connection for every test case here
            # Because psycopg2 will raise a InFailedSqlTransaction if
            # we try to run another query after the previousone failed and
            # raises an exception
            with utils.connect_to_db(test=True) as cursor:
                cursor.execute('INSERT INTO websites (url, check_interval, up_regex)\
                    VALUES (%s, %s, %s) RETURNING id',
                    tuple(data)
                )
