# Aiven website status tracking app

## Requirements

Implement a system that monitors website availability over the network, produces metrics about this and passes these events through an Aiven Kafka instance into an Aiven PostgreSQL database.

## Installing required packages (Debian)

I assume that you are using python3. Sorry python2 people :(

Prerequisites:
- 3.8 >= python --version >= 3.4 . Tested on python 3.7.1
- A python virtual environment for convenience. I use [pyenv virtualenv](https://github.com/pyenv/pyenv-virtualenv)

From a terminal, do the following:
- (optional) `sudo apt install libpq-dev`: this is a prerequisite for psycopg2. For additional prerequisites, please refer to: https://www.psycopg.org/docs/install.html#prerequisites
- (optional) `sudo apt install python3-dev`: also for psycopg2
- Then, go to the cloned repo's root directory and run: `pip install -r requirements.txt` and `python setup.py develop`
- You have also received (hopefully) a zipped file containing keys and config files needed to connect to the Aiven pgsql and kafka instances. Unzip the contents of this zip file in the **app/** folder. Your app/ folder should look like this after unzipping:
```
-app/
----ssl/
-------kafkaCARoot.pem
-------kafkacertificate.pem
-------kafkakey.pem
----kafka_config.json
----pgsql_config.json
----test_pgsql_config.json
```

## Application overview

- **app.website_checker**: checks the availability of websites defined in the DB's _websites_ table, and puts messages to the Kafka broker. The website_checker module uses timeloop to run jobs asynchronously in threads for each website to poll. Each website entry defines it's own polling interval (see tables definitions in the Database section below)
- **app.broker_db_sync**: consumes the Kafka messages, process the data, and then save it into the _website_status_ table
- **app.utils**: Various utility functions helping the above modules, and also facilitating testing modules

## Running the application

To run the module that polls websites and sends to the kafka broker, run in a terminal:
```shell
python -m app.website_checker
```
To run the module that consumes messages from the kafka broker, run in another terminal:
```shell
python -m app.broker_db_sync
```

If you would like to see currently which websites are being polled, open **pgcli** (HOSTNAME, PORT, USER, and PASSWORD to database is in pgsql_config.json in the "secret" zip file)
```shell
pgcli -h HOSTNAME -p PORT -u USER -W homework

SELECT * FROM websites;
```

**If you would like to add a new website for testing**, you can use a utility function:
```shell
python -c "import app.utils as utils;utils.add_new_website('http://google.com', )"
```
The **utils.add_new_website** function accepts these arguments:
- *website_url* str: the website's url
- *check_interval* int: how often in seconds should the website be checked
- *up_regex* str: an optional regex expression that will be used when checking the website
Alternatively you can run the insert statement to insert a new website.
```sql
INSERT INTO websites (url, check_interval, up_regex)
VALUES ('http://google.com', 5, '')
```

**If you would like to remove a website**, you can use a utility function:
```shell
python -c "import app.utils as utils;utils.remove_website('ID')"
```
Replace 'ID' with the database ID of the website.
Alternatively you can run the delete statement to remove a website.
```sql
DELETE FROM websites where id = ID
```

## Database

Tables:
- _websites_: a table that stores a list of websites which we will check
    - **url** varchar(2048) UNIQUE NOT NULL: The website's URL against which a periodic GET request will be made
    - **check_interval** INTEGER DEFAULT 5: How often in seconds to check for the website's availability
    - **up_regex** TEXT: an optional regex pattern used in order to look for any texts in the GET response that should be found

- _website_status_: a table that gathers the website status
    - **kafka_topic**  VARCHAR (256) NOT NULL: the kafka topic from which the data was fetched
    - **kafka_partition_id** INTEGER NOT NULL: the kafka partition
    - **kafka_offset_id** INTEGER NOT NULL: : the kafka offset
    - **website_id** INTEGER REFERENCES websites(id): foreign key pointing to the website in websites table
    - **timestamp_utc** TIMESTAMP NOT NULL: a timestamp utc of when the check request was made
    - **request_info** json NOT NULL: a JSON object containing information about the check request, e.g status code, response time
    - **PRIMARY KEY** (kafka_topic, kafka_partition_id, kafka_offset_id, website_id)

## Task checklist

- setup connections to kafka and postgres (done)
- get rough prototype of producer/consumer scripts working (done)
- implement website checker (done)
- write database DDL scripts (done)
- implement database writer (done)
- implement regex checking of website content (done)
- check handling of website with invalid url using timeloop (done)
- write tests (done)
- refine README.md and write instructions (done)
- package keys and config files into zip (done)
- write utility functions to create/remove kafka topics, access postgres database to list website status to terminal (kindof done via app/utils.py) (done)

## What and how to test

What is tested:
- test correct/incorrect website urls (done)
- test the data format going in and out of kafka (done)
- test vital functions broker_db_sync.sync_to_db() and website_checker.poll_website()
- test adding wrong data formats and key constraint fails to websites and website_status tables

How to test:

From the code repository's root directory, run `pytest -s` for verbosity or just `pytest`. Use -k to select individual modules or functions, e.g: `pytest -s -k 'test_insert_incorrect_website_status'`

```shell
pytest
pytest -s
pytest -s -k 'test_insert_incorrect_website_status'
```

## Limitations / unverified features

- Production deployment limitations: The website_checker.py runs threaded jobs based on the number of websites defined in the websites table. In a production setting, perhaps each job could be run as a separate docker container. Thus the code needs to be updated to accommodate this.
- The kafka producers/consumers assumes that the topic has only 1 partition for simplicity. The topic created for this project, "website_status" has the default setup of having only 1 partition. As a result, only 1 consumer should be running. Running additional consumers (app.broker_db_sync) will have them idle unless the currently running producer is stopped.

## Attributions

- https://help.aiven.io/en/articles/489573-getting-started-with-aiven-postgresql
- https://stackoverflow.com/questions/26899001/pytest-how-do-i-use-global-session-wide-fixtures
- http://maximilianchrist.com/python/databases/2016/08/13/connect-to-apache-kafka-from-python-using-ssl.html
- https://dev.to/wangonya/asserting-exceptions-with-pytest-8hl
