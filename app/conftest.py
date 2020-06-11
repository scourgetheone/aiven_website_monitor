import pytest
import kafka

import app.utils as utils

@pytest.fixture(scope="session", autouse=True)
def before_after_tests():
    # Set up some test websites that are valid
    utils.init_db(test=True)

    # Create a test topic
    try:
        utils.create_topics(['test'])
    except kafka.errors.TopicAlreadyExistsError:
        print('topic \'test\' already exists!')
        print('Kafka topics were not properly removed during last test round!')

    yield

    # Delete all database tables and the kafka topic called 'test'
    utils.drop_all_tables(test=True)

    try:
        utils.delete_topics(['test'])
    except kafka.errors.UnknownTopicOrPartitionError:
        print ('topic \'test\' has already been removed!?')