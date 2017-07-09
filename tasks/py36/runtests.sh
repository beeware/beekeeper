#!/bin/bash

# Download and unpack code at the test SHA
wget https://github.com/$(GITHUB_OWNER)/$(GITHUB_PROJECT_NAME)/archive/$(SHA).zip
unzip $(SHA).zip
cd $(GITHUB_PROJECT_NAME)-$(SHA)

# Install repository (and thus install dependencies)
pip install -e .

# Run tests
python setup.py test
