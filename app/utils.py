from contextlib import contextmanager
from kafka import KafkaAdminClient
from kafka.admin import NewTopic
from psycopg2.extras import RealDictCursor

import os
import json
import psycopg2


def read_json_config(file):
    """Reads in a json file from the same directory as this module and outputs a python dict

        Args:
            file: the path to a json file
    """
    with open(os.path.join(os.path.dirname(__file__), file)) as f:
        CONFIG = json.load(f)

        # Process the config values to try to get the correct path to a file,
        # if the path is prepended with "$DIRPATH$/", which means the path to
        # the directory of this module
        for key, value in CONFIG.items():
            if type(value) == str and '$DIRPATH$/' in value:
                relative_path = ''.join(value.split('$DIRPATH$/')[1:])
                new_path = os.path.join(os.path.dirname(__file__), relative_path)
                CONFIG[key] = new_path

        return CONFIG

#
# *** Database utility functions ***
#

@contextmanager
def connect_to_db():
    conn = psycopg2.connect(read_json_config('pgsql_config.json')['uri'])
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        yield cursor
    finally:
        # Commit the statements
        conn.commit()
        # Close the connection
        cursor.close()
        conn.close()


def test_database_connection():
    with connect_to_db() as cursor:
        cursor.execute('SELECT 1 = 1')
        result = cursor.fetchone()

        print (result)

def init_db():
    """Initializes the empty database with required tables
    """
    with connect_to_db() as cursor:
        init_db_filepath = os.path.join(os.path.dirname(__file__), 'db_scripts/init_db.sql')
        print (open(init_db_filepath, "r").read())

        cursor.execute(open(init_db_filepath, "r").read())

        print ('Done.')

def add_new_website(website_url, check_interval=5, up_regex=''):
    """Adds a new website to the websites table

        Args:
        - website_url str: the website's url
        - check_interval int: how often in seconds should the website be checked
        - up_regex str: an optional regex expression that will be used when
          checking the website
    """
    with connect_to_db() as cursor:
        cursor.execute('INSERT INTO websites (url, check_interval, up_regex)\
            VALUES (%s, %s, %s) RETURNING id',
            (website_url, check_interval, up_regex))

        # Return the id of the newly created website entry
        id = cursor.fetchone()

        return id['id']

def get_websites(debug=False):
    """Gets a list of websites

        Args:
        - debug: prints the results. Useful when executing from the terminal

        Returns a list of DictRows holding website information
    """
    with connect_to_db() as cursor:
        cursor.execute('SELECT * FROM websites')
        rows = cursor.fetchall()

        if debug:
            for row in rows:
                print ('id: {}, url: {} , check interval: {}s, up_regex: {}'.format(
                    row['id'], row['url'], row['check_interval'], row['up_regex']))

        return rows


def remove_website(id):
    if not id or type(id) != int:
        raise TypeError('id must be an integer')

    with connect_to_db() as cursor:
        cursor.execute('DELETE FROM websites where id = {}'.format(id))

        return 'OK'

#
# *** Kafka utility functions ***
#

def get_kafka_admin_client():
    """Returns a KafkaAdminClient object based on configurations in kafka_config.json
    """
    return KafkaAdminClient(**read_json_config('kafka_config.json'))

def delete_topics(topics):
    """Deletes a list of topics

        Args:
        - topics: a list of strings of topic names

    """
    if not topics:
        return

    admin = get_kafka_admin_client()
    admin.delete_topics(topics)

def create_topics(topics):
    """Creates a list of topics

        Args:
        - topics: a list of strings of topic names

    """
    if not topics:
        return

    admin = get_kafka_admin_client()
    new_topics = map(lambda topic: NewTopic(topic, 1, 3), topics)
    admin.create_topics(new_topics)
