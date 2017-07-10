# Use an official Python runtime as a parent image
FROM python:3.6-slim

# Set the working directory to /app
WORKDIR /app

# Copy the runtest script into the container
ADD . /app

# Get some core tools
RUN apt-get update
RUN apt-get install -yy curl unzip

# Run the test with a waggle report
CMD ["./run.sh"]
