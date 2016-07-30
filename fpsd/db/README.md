# Initial Database Setup

(writing out for documentation, TODO put these setup tasks in ansible)

## Setup user and database

Change password in `create_db.sql` from `thisisnottherealpasswordcomeonyall` to what you want the password to be and then run:

`$ psql -f create_db.sql`

## Set environmental variables

```
$ export PGHOST=localhost
$ export PGPORT=5432
$ export PGDATABASE=fpsd
$ export PGUSER=fp_user
```

## Create the `raw` schema and tables

Needs to be done in order due to foreign key constraints

```
$ psql -f create_schema_raw.sql
$ psql -f create_table_crawls.sql
$ psql -f create_table_hs_history.sql
$ psql -f create_table_frontpage_examples.sql
$ psql -f create_table_frontpage_traces.sql
```

## Create the `features` schema

`$ psql -f create_schema_features.sql`