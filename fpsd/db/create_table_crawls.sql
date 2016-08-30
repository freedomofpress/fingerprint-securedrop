CREATE TABLE raw.crawls (
    crawlid SERIAL PRIMARY KEY,
    page_load_timeout INTEGER,
    wait_on_page INTEGER,
    wait_after_closing_circuits INTEGER,
    entry_node VARCHAR(200),
    os VARCHAR(200),
    kernel VARCHAR(40),
    kernel_version VARCHAR(40),
    python_version VARCHAR(20),
    tor_version VARCHAR(20),
    tb_version VARCHAR(20),
    crawler_version VARCHAR(20),
    city VARCHAR(40),
    country VARCHAR(40),
    asn INTEGER,
    ip INET
);
