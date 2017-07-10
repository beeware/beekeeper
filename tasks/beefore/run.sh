#!/bin/bash

# Download and unpack code at the test SHA
curl -s -L -u $GITHUB_USERNAME:$GITHUB_ACCESS_TOKEN https://github.com/$GITHUB_OWNER/$GITHUB_PROJECT_NAME/archive/$SHA.zip -o code.zip
unzip code.zip

echo "Python version=`python --version`"
echo "Node version=`node --version`
echo "NPM version=`npm --version`

# Run checks
echo beefore -u $GITHUB_USERNAME -r $GITHUB_OWNER/$GITHUB_PROJECT_NAME -p $GITHUB_PR_NUMBER -c $SHA $TASK $GITHUB_PROJECT_NAME-$SHA
beefore -u $GITHUB_USERNAME -r $GITHUB_OWNER/$GITHUB_PROJECT_NAME -p $GITHUB_PR_NUMBER -c $SHA $TASK $GITHUB_PROJECT_NAME-$SHA
