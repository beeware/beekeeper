# Use an official Python runtime as a parent image
FROM python:3.6-slim

# Set the working directory to /app
WORKDIR /app

# Copy the runtest script into the container
ADD . /app

# Add the requirements for the container
RUN pip install -r requirements.txt

# Run the test
CMD ["./runtests.sh"]
