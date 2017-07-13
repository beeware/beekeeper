#!/bin/bash

# Download and unpack code at the test SHA
curl -s -L -u $GITHUB_USERNAME:$GITHUB_ACCESS_TOKEN https://github.com/$GITHUB_OWNER/$GITHUB_PROJECT_NAME/archive/$SHA.zip -o code.zip
unzip code.zip

echo
echo "Python version=`python --version`"
echo "Node version=`node --version`"
echo "NPM version=`npm --version`"
echo

# Run checks
echo beefore
echo "    --username $GITHUB_USERNAME"
echo "    --repository $GITHUB_OWNER/$GITHUB_PROJECT_NAME"
echo "    --pull-request $GITHUB_PR_NUMBER"
echo "    --commit $SHA"
echo "    $TASK $GITHUB_PROJECT_NAME-$SHA"

beefore --username $GITHUB_USERNAME \
    --repository $GITHUB_OWNER/$GITHUB_PROJECT_NAME \
    --pull-request $GITHUB_PR_NUMBER \
    --commit $SHA \
    $TASK $GITHUB_PROJECT_NAME-$SHA
