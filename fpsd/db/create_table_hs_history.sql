CREATE TABLE raw.hs_history (
    hsid SERIAL PRIMARY KEY,
    hs_url VARCHAR(40) NOT NULL, 
    is_sd BOOLEAN NOT NULL, 
    sd_version VARCHAR(10) NOT NULL, 
    is_current VARCHAR(10) NOT NULL,
    class VARCHAR(40) NOT NULL, 
    t_sort TIMESTAMP NOT NULL
);
