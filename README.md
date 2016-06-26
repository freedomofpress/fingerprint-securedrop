# FingerprintSecureDrop

The code herein can be used to collect cell traces, which can be used to train
classifiers to website fingerprint SecureDrop instances.

## Getting Started

This repo uses submodules, so use `git clone --recursive`.

* Requires Ansible >= 2.0
* Requires Vagrant

To get a properly configured VM bootstrapped for crawling, run:

```
vagrant up
```

from the repo root.

### Running the Sorter

```
vagrant ssh
cd ~/FingerprintSecureDrop
./sort_onions.py
```

To look at the crawler log while it's running run `tail -f
logging/crawler-log-latest.txt`. Sorter data will be timestamped with
`logging/class-data-latest.pickle` being symlinked to the latest data
(timestamping and symlinking like this is done with all logs and data files that
are created by the Python processes in this repo).

### Running the Crawler

```
vagrant ssh
cd ~/FingerprintSecureDrop
./crawl_onions.py
```

To look at the crawler log while it's running run `tail -f
logging/crawler-log-latest.txt`, and to look at the raw Tor cell log run `tail
-f logging/tor_cell_seq.log`.

### Deploying to remote servers

Todo: write
