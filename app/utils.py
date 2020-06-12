"""utils.py

Various utility functions helping the above modules, and also facilitating testing modules
"""
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
def connect_to_db(test=False, include_conn=False):
    """Connects to the pgsql database defined in pgsql_config.json

        Args:
        - test bool: if True, connects to the database defined in test_pgsql_config.json
        - include_conn bool: if True, also include the connection object and yields a tuple

        Should be used with the 'when' directive, which yields the cursor object
        and automatically commits and closes the connection.
    """
    config_file = 'pgsql_config.json'
    if test:
        config_file = 'test_pgsql_config.json'

    conn = psycopg2.connect(read_json_config(config_file)['uri'])
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    yield_obj = (conn, cursor) if include_conn else cursor

    try:
        yield yield_obj
    finally:
        # Commit the statements
        conn.commit()
        # Close the connection
        cursor.close()
        conn.close()


def test_database_connection(test=False):
    with connect_to_db(test) as cursor:
        cursor.execute('SELECT 1 = 1')
        result = cursor.fetchone()

        print (result)

def init_db(test=False):
    """Initializes the empty database with required tables

        Args:
        - test bool: if True, connects to the database defined in test_pgsql_config.json
    """
    with connect_to_db(test) as cursor:
        init_db_filepath = os.path.join(os.path.dirname(__file__), 'db_scripts/init_db.sql')
        print (open(init_db_filepath, "r").read())

        cursor.execute(open(init_db_filepath, "r").read())

        print ('Finished initializing the database.')

def drop_all_tables(test=False):
    """Drops all tables from a database

        Args:
        - test bool: if True, connects to the database defined in test_pgsql_config.json
    """
    with connect_to_db(test) as cursor:
        init_db_filepath = os.path.join(os.path.dirname(__file__), 'db_scripts/drop_all_tables.sql')
        print (open(init_db_filepath, "r").read())

        cursor.execute(open(init_db_filepath, "r").read())

        print ('Finished dropping all tables from the database.')

def add_new_website(website_url, check_interval=5, up_regex='', test=False):
    """Adds a new website to the websites table

        Args:
        - website_url str: the website's url
        - check_interval int: how often in seconds should the website be checked
        - up_regex str: an optional regex expression that will be used when
          checking the website
        - test bool: if True, connects to the database defined in test_pgsql_config.json

        Returns the database id of the website
    """
    with connect_to_db(test) as cursor:
        # First, we check if the new website already exists but soft-deleted
        cursor.execute("SELECT * FROM websites \
            WHERE url = '{}' AND deleted = TRUE".format(website_url))
        existing_website = cursor.fetchone()

        if existing_website:
            print('Website already exists but soft-deleted. Will now un-delete...')
            cursor.execute('UPDATE websites SET deleted = FALSE \
                WHERE id = {}'.format(existing_website['id']))

            return existing_website['id']
        else:
            cursor.execute('INSERT INTO websites (url, check_interval, up_regex)\
                VALUES (%s, %s, %s) RETURNING id',
                (website_url, check_interval, up_regex))
            # Return the id of the newly created website entry
            row = cursor.fetchone()

            return row['id']

def get_websites(id=None, test=False):
    """Gets a list of websites

        Args:
        - id int: optional id of a website. The function will then filter by id and return only a single DictRow result
        - test bool: if True, connects to the database defined in test_pgsql_config.json

        Returns a list of DictRows holding website information if id=None else
        returns a single DictRow if website is found
    """
    with connect_to_db(test) as cursor:
        where_clause = 'WHERE id = {} AND deleted = FALSE'.format(id)
        if not id:
            where_clause = 'WHERE deleted = FALSE'

        cursor.execute('SELECT * FROM websites {}'.format(where_clause))

        if not id:
            rows = cursor.fetchall()
        else: rows = cursor.fetchone()

        return rows


def remove_website(id, test=False):
    """Removes a website

        Args:
        - id int: the database id of the website
        - test bool: if True, connects to the database defined in test_pgsql_config.json
    -
    """
    if not id or type(id) != int:
        raise TypeError('id must be an integer')

    with connect_to_db(test) as cursor:
        cursor.execute('UPDATE websites SET deleted = TRUE WHERE id = {}'.format(id))

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

    print ('Finished deleting topics {}'.format(topics))

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

    print ('Finished adding topics {}'.format(topics))

#
# *** Other misc functions ***
#

class AttrDict(dict):
    """Conveniently access dictionary keys like object attributes

    Blatantly copied from:
    https://stackoverflow.com/questions/4984647/accessing-dict-keys-like-an-attribute
    """
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self