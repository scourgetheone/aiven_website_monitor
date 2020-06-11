"""test_end_to_end.py

Tests the end to end functionality between the website_checker and broker_db_sync modules.
"""
from kafka import KafkaProducer

import pytest
import requests
import psycopg2
import json
import kafka

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
    print('Got message from kafka broker')

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
            print ('testing key {}'.format(key))
            assert json_from_db[key] == json_message_received[key]

    print('Finished test_end_to_end')

def test_invalid_website(producer):
    """Test invalid URLs
    """
    # First, define a website with an unsupported protocol (e.g ftp)
    # Here we mock the results from utils.get_websites
    website = { 'id': 4, 'url': 'ftp://google.com', 'check_interval': 5 }

    assert website_checker.poll_website(producer, website, 'test') == None

    # Next, a 'website' with a totally random url
    website = { 'id': 5, 'url': '%_24141+9/?', 'check_interval': 5 }
    assert website_checker.poll_website(producer, website, 'test') == None

    # Next, a 'website' with a valid url but probably unreachable
    website = {
        'id': 6, 'url': 'https://google2.com',
        'check_interval': 5, 'up_regex': ''
    }
    assert 'RequestException' in website_checker.poll_website(producer, website, 'test')['status_code']

    print('Finished test_invalid_website')


def test_regex_pattern(producer, monkeypatch):
    """Test regex patterns
    """
    # First, define a website with a regex pattern to test against
    # Here we mock the results from utils.get_websites
    website = {
        'id': 4,
        'url': 'https://help.aiven.io',
        'check_interval': 5,
        'up_regex': 'Advice and answers from the Aiven Team'
    }

    mock_response = AttrDict(
        status_code=200,
        elapsed=AttrDict(
            seconds=2,
            microseconds=123,
        ),
        text="""
        </div>
            <h1 class="header__headline">
                Advice and answers from the Aiven Team
            </h1>
        <form action="/en/" autocomplete="off" class="header__form search">
        """
    )

    # Here we mock the requests function, since we don't want to
    # rely on external websites that may be down
    def mock_requests_get(_):
        return mock_response

    monkeypatch.setattr(requests, 'get', mock_requests_get)

    # Poll the website and send the response to Kafka
    message_to_send = website_checker.poll_website(producer, website, 'test')
    print('Polled website and sent message from kafka broker')

    # Verify that the pattern was correctly matched
    assert message_to_send.get('regex_match') == True

    # --
    # Update the response text to something that does not match the regex:
    mock_response['text'] = """
        Service Temporarily Available
    """

    def mock_requests_get2(_):
        return mock_response

    monkeypatch.setattr(requests, 'get', mock_requests_get2)

    # Poll the website and send the response to Kafka
    message_to_send = website_checker.poll_website(producer, website, 'test')
    print('Polled website and sent message from kafka broker')

    # Verify that the pattern was not correctly matched
    assert message_to_send.get('regex_match') == False

    print('Finished test_regex_pattern')
