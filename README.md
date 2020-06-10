## Aiven website status tracking app

### Requirements
Implement a system that monitors website availability over the network, produces metrics about this and passes these events through an Aiven Kafka instance into an Aiven PostgreSQL database.

### Installing required packages (Debian)

- sudo apt install libpq-dev
- pip install -r requirements.txt

### Application overview

- website_checker: checks the availability of websites defined in the DB's _websites_ table, and puts messages to the Kafka broker.
- broker_db_sync: consumes the Kafka messages, process the data, and then save it into the _website_status_ table

### Database

Tables:
- _websites_: a table that stores a list of websites which we will check
    - **url** varchar(2048) required: The website's URL against which a periodic GET request will be made
    - **check_interval** INTEGER default 5: How often in seconds to check for the website's availability
    - **up_regex** TEXT: an optional regex pattern used in order to look for any texts in the GET response that should be found

- _website_status_: a table that gathers the website status
    - **website_id** INTEGER REFERENCES WEBSITES()
    - **timestamp_utc** TIMESTAMPTZ required: a timestamp utc of when the check request was made
    - **request_info** json: a JSON object containing information about the check request, e.g status code, response time

### TODOs

- setup connections to kafka and postgres (done)
- get rough prototype of producer/consumer scripts working (done)
- implement website checker
- write database DDL scripts (done)
- implement database writer
- write tests
- refine README.md
- (optional) write utility functions to create/remove kafka topics, access postgres database to list website status to terminal

### What to test

Ideas:
- test correct/incorrect website urls
- handle special HTTP codes like 404 (page not found, so skip logging it)
- test the data format going in and out of kafka
- database testing: replicate an existing database, then perform testing on it in various scenarios (like try to fail a test by removing a database column or adding wrong data type etc...)

### Attributions

- https://help.aiven.io/en/articles/489573-getting-started-with-aiven-postgresql