CREATE TABLE raw.frontpage_examples (
    exampleid SERIAL PRIMARY KEY,
    hsid INTEGER REFERENCES raw.hs_history (hsid), 
    crawlid INTEGER REFERENCES raw.crawls (crawlid),
    t_scrape TIMESTAMP NOT NULL
);
