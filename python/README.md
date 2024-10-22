# IHTC 2024 competition

Check the [IHTC 2024 competition website](https://ihtc2024.github.io/) for more information.

## Installation

Most dependencies are managed by creating a python virtual environment:

```
cd ihtc2024/python/
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements-dev.txt
```

For graph functionality, graph-tool is used and it's a bit tricky.

Check instructions for installing graph tool here:
https://graph-tool.skewed.de/installation.html#debian-ubuntu-gnulinux

Also check here for how to add it to the virtual environment https://jolo.xyz/blog/2018/12/07/installing-graph-tool-with-virtualenv

```bash
sudo apt-get install python3-graph-tool
sudo apt-get install libgtk-3-dev libgirepository1.0-dev
```
