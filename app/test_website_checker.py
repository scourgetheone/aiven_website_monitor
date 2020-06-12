"""test_end_to_end.py

Tests the website_checker module:
- test correct/incorrect website urls
- test the regex when receiving responses from website checks
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


@pytest.fixture(scope='module')
def producer():
    producer = KafkaProducer(
        value_serializer=lambda m: json.dumps(m).encode('ascii'),
        **utils.read_json_config('kafka_config.json'),
    )
    return producer

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
