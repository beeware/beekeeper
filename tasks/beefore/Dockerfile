# Use an official Python runtime as a parent image
FROM python:3.6-slim

# Set the working directory to /app
WORKDIR /app

# Copy the runtest script into the container
ADD . /app

# Get some core tools
RUN apt-get update
RUN apt-get install -yy curl unzip

# Add the node package source and install nodejs
RUN curl -sL https://deb.nodesource.com/setup_6.x -o nodesource_setup.sh
RUN chmod 755 nodesource_setup.sh
RUN ./nodesource_setup.sh
RUN apt-get install -yy nodejs
RUN npm install npm

# Add the requirements for the container
RUN pip install -r requirements.txt

# Install node requirements
RUN npm install

# Run the test
CMD ["./run.sh"]
