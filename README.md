# FingerprintSecureDrop

The code herein can be used to collect Tor cell traces, which can be used to
train classifiers to website fingerprint SecureDrop (SD) instances. The idea is
to use this as a way to test server-side defense mitigations we hope to
implement. If you're interested in website fingerprinting and defenses
(especially in relation to Tor), please feel encouraged to come talk with a
group of researchers in a Gitter chatroom at
https://gitter.im/freedomofpress/Website_Fingerprinting. 

We're hoping to the code in this repo a little more composable soon, so you can
make some modifications to get this going for your own onion service (or perhaps
even regular site). Until then, you could still try it out on SecureDrop, and
then analyze the traces with your favorite classifiers. If you do so, please
share your results with us! (Preferably, using PGP.)

`sort_onions.py` first scrapes onion service URLs from some popular onion
service indexes, and then scrapes each of those .onion URLs. If it encounters an
up-to-date SD, it stores it as such. If it encounters a site that doesn't
mention SD at all, it also stores that URL in a different set. These are the two
sets that really matter (i.e., are used by `crawl_onions.py`). Out-of-date SDs
could mess with our results (shame on you admins ;-P), and we also ignore sites
that even mention SD as a precaution against sites like Greenpeace's heavily
modified, very out-of-date SecureDrop that they seem to have rebranded as
"SafeSource," but fortunately still includes the string "SecureDrop" on the
homepage. Thus we can catch it with this precautionary measure. Hopefully, no
sites have made minor changes to SecureDrop and also dropped mention of
SecureDrop, because that would have potential to mess up our results. I believe
that's probably unlikely.

`crawl_onions.py` crawls onion services roughly following Tao and Goldberg (see
https://cypherpunks.ca/~iang/pubs/webfingerprint-wpes.pdf, Appendix A, Algorithm
1). Collecting a trace for a single site happens roughly as follows:

* Load single onion service in Tor Browser (using a virtual framebuffer for
    headless operation by default)
* Wait 5 (configurable) seconds after the initial page onload event to capture
    traffic after the initial onload event
* Use stem to identify the unique, singular Tor circuit id for the rendezvous
    circuit to meet the onion service we're loading
* Read the Tor cell log from our modified `tor` binary and collects all DATA
    cells from that circuit id
    * Write these as `(time, direction)` pairs in a file on disk, adjusted so
        the first cell is time zero
* Close all circuits with stem

The adversary model we are assuming is as follows. First, our adversary is in
control of our guard node. Thus, they are able to separate individual streams
(rendezvous circuits are actually not multiplexed within TCP streams like
general circuits, but I mention this because it's relevant to general circuits,
which are multiplexed). Second, our adversary has read Kwon et. al's circuit
fingerprint paper (see
https://www.usenix.org/system/files/conference/usenixsecurity15/sec15-paper-kwon.pdf)
and is capable of fingerprinting our rendezvous circuits with 100% accuracy. The
way we collect traces described above is representative of the capabilities of
such an adversary.

Lastly, `config.ini` is a general configuration file, for those who just want to
run the script and tinker with some parameters. This should be expanded in the
future to expose even more functionality and make it easy to swap out your own
website for SD in order to test fingerprinting defenses on your own hidden
service.

## Getting Started

This repo uses submodules, so use `git clone --recursive`.

* Requires Ansible >= 2.0
* Requires Vagrant

To get a properly configured VM bootstrapped for crawling, run:

```
cd FingerprintSecureDrop
vagrant up
```

We seriously recommend using the Vagrantfile and Ansible playbook, which will
sping up a VM and provision it for you, it is not strictly necessary. A lot of
things are necessary to get this to work otherwise including compiling a custom
version of Tor. We will not be providing instructions for how to do this, but
the patched `relay.c` is here and everything you'd need to do to get this code
running can be figured out by reading through the Ansible playbook.

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
