"""website_checker.py

checks the availability of websites defined in the DB's _websites_ table, and puts messages to the Kafka broker. The website_checker module uses timeloop to run jobs asynchronously in threads for each website to poll. Each website entry defines it's own polling interval.
"""

from timeloop import Timeloop
from kafka import KafkaProducer
from datetime import datetime, timedelta

import re
import requests
import json

from app.utils import AttrDict

import app.utils as utils

timeloop = Timeloop()

def poll_website(producer, website, kafka_topic):
    """Polls a website using the requests library

        Args:
        - producer KafkaProducer: a KafkaProducer object
        - website dict: the website dict object. Usually from utils.get_websites()
        - kafka_topic str: the kafka topic to send messages to
    """
    response = None

    try:
        response = requests.get(website['url'])
    except requests.exceptions.InvalidSchema:
        print ('website with id: {} has an invalid connection schema! Url: {}'.format(website['id'], website['url']))
        return
    except requests.exceptions.InvalidURL:
        print ('website with id: {} has an invalid url! Url: {}'.format(website['id'], website['url']))
        return
    except requests.exceptions.RequestException as e:
        print ('website with id: {} cannot be reached! Url: {}'.format(website['id'], website['url']))
        response = AttrDict(
            status_code='RequestException: {}'.format(e),
            elapsed=AttrDict(
                seconds=0,
                microseconds=0,
            ),
            text=''
        )
    finally:
        if not response:
            return

        message = {
            'website_db_id': website['id'],
            'url': website['url'],
            'status_code': response.status_code,
            'elapsed': '{}.{}'.format(response.elapsed.seconds, response.elapsed.microseconds),
            'timestamp_utc': str(datetime.utcnow()),
        }

        # Compare the regex pattern if set:
        if website['up_regex']:
            if re.search(website['up_regex'], response.text):
                # Add additional information to the message
                message['regex_match'] = True
            else: message['regex_match'] = False

        producer.send(kafka_topic, message)
        producer.flush()

        return message

def schedule_job(producer, website, kafka_topic):
    """Schedules jobs using timeloop

        Args:
        - producer KafkaProducer: a KafkaProducer object
        - website dict: the website dict object. Usually from utils.get_websites()
        - kafka_topic str: the kafka topic to send messages to
    """
    @timeloop.job(interval=timedelta(seconds=website['check_interval']))
    def timeloop_job():
        poll_website(producer, website, kafka_topic)

def run_checker(kafka_topic='website_status'):
    """Runs website polling jobs using timeloop

        Args:
        - kafka_topic str: the kafka topic to send messages to
    """
    try:
        producer = KafkaProducer(
            value_serializer=lambda m: json.dumps(m).encode('ascii'),
            **utils.read_json_config('kafka_config.json'),
        )

        for website in utils.get_websites():
            schedule_job(producer, website, kafka_topic)

        timeloop.start(block=True)

    except KeyboardInterrupt:
        producer.close()

if __name__ == '__main__':
    run_checker()
