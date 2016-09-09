# Test Database Setup

## Setup tablefunc

The `postgresql-contrib` package will need to be added as we make use of an extension to postgresql `tablefunc` in some of the queries (`crosstab()` requires the `tablefunc` extension):

```
sudo apt-get install postgresql-contrib
```

In order to use the crosstab() function, the additional module `tablefunc` must be installed once per database. From psql:

```
fpsd=> CREATE EXTENSION tablefunc; 
testfpsd=> CREATE EXTENSION tablefunc; 
```

## Create new database

As postgres user:

```
fpsd=> CREATE DATABASE testfpsd WITH OWNER fp_user;
```

We now want to create the tables, and drop some of the foriegn key constraints so that we don't have to fill a ton of tables when we run tests. As fp_user:

```
testfpsd=> \i create_schema_raw.sql
CREATE SCHEMA
testfpsd=> \i create_table_hs_history.sql
CREATE TABLE
testfpsd=> \i create_table_crawls.sql    
CREATE TABLE
testfpsd=> \i create_table_frontpage_examples.sql
CREATE TABLE
testfpsd=> \i create_table_frontpage_traces.sql
CREATE TABLE
testfpsd=> \i create_schema_features.sql
psql:create_schema_features.sql:1: NOTICE:  schema "features" does not exist, skipping
DROP SCHEMA
CREATE SCHEMA
testfpsd=> ALTER TABLE raw.frontpage_traces DROP CONSTRAINT frontpage_traces_exampleid_fkey;
ALTER TABLE
testfpsd=> ALTER TABLE raw.frontpage_examples DROP CONSTRAINT frontpage_examples_hsid_fkey;
ALTER TABLE
testfpsd=> ALTER TABLE raw.frontpage_examples DROP CONSTRAINT frontpage_examples_crawlid_fkey;
ALTER TABLE
```