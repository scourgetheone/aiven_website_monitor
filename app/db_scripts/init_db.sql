/*
    init_db.sql

    This script creates the needed tables for the aiven-website-monitor app
*/

CREATE TABLE IF NOT EXISTS websites(
    id serial PRIMARY KEY,
    url VARCHAR (2048) UNIQUE NOT NULL,
    check_interval INTEGER DEFAULT 5,
    up_regex TEXT
);

CREATE TABLE IF NOT EXISTS website_status(
    kafka_topic VARCHAR (256) NOT NULL,
    kafka_partition_id INTEGER NOT NULL,
    kafka_offset_id INTEGER NOT NULL,
    website_id INTEGER REFERENCES websites(id),
    timestamp_utc TIMESTAMP NOT NULL,
    request_info JSON NOT NULL,
    PRIMARY KEY (kafka_topic, kafka_partition_id, kafka_offset_id, website_id)
);
