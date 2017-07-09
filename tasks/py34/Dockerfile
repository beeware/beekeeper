# Use an official Python runtime as a parent image
FROM python:3.4-slim

# Set the working directory to /app
WORKDIR /app

# Copy the runtest script into the container
ADD . /app

# Run the test with a waggle report
CMD ["./runtests.sh"]
