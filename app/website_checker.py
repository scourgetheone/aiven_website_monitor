# http://maximilianchrist.com/python/databases/2016/08/13/connect-to-apache-kafka-from-python-using-ssl.html

from timeloop import Timeloop
from kafka import KafkaProducer
from datetime import datetime, timedelta

import requests
import json

import app.utils as utils

timeloop = Timeloop()

producer = KafkaProducer(
    value_serializer=lambda m: json.dumps(m).encode('ascii'),
    **utils.read_json_config('kafka_config.json'),
)

def schedule_job(website):

    @timeloop.job(interval=timedelta(seconds=website['check_interval']))
    def poll_website():
        response = requests.get(website['url'])
        message = {
            'website_db_id': website['id'],
            'url': website['url'],
            'status_code': response.status_code,
            'elapsed': '{}.{}'.format(response.elapsed.seconds, response.elapsed.microseconds),
            'timestamp_utc': str(datetime.now()),
        }

        producer.send('website_status', message)
        producer.flush()


def setup_polling():
    """Sets up polling jobs after getting the website list from the DB
    """
    for website in utils.get_websites():
        schedule_job(website)

def run_polling():
    """Runs website polling jobs using timeloop
    """
    setup_polling()
    timeloop.start(block=True)

if __name__ == '__main__':
    run_polling()
