# FingerprintSecureDrop

The code herein can be used to collect cell traces, which can be used to train
classifiers to website fingerprint SecureDrop instances.

## Getting Started

This repo uses submodules, so `git clone --recursive`.

* Requires Ansible >= 2.0

```
vagrant up
vagrant ssh
```

### Running the Sorter

TODO: write

### Running the Crawler

```
vagrant ssh
cd ~/FingerprintSecureDrop
. bin/activate
./crawl_hidden_services.py
```

To look at the logs while it's running, tail `logging/crawler-log-latest.txt`.
