CREATE TABLE raw.frontpage_traces (
    cellid SERIAL PRIMARY KEY,
    exampleid INTEGER REFERENCES raw.frontpage_examples (exampleid),
    ingoing BOOLEAN NOT NULL,
    circuit BIGINT NOT NULL,
    stream BIGINT NOT NULL,
    command VARCHAR(40) NOT NULL,
    length INTEGER NOT NULL,
    t_trace NUMERIC NOT NULL
);
