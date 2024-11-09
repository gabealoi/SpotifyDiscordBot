# Use the official Python 3.12 slim image as the base image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file into the container
COPY requirements.txt /app/

# Install dependencies from the requirements.txt file
RUN pip install --no-cache-dir -r requirements.txt


# Install dependencies and ffmpeg
RUN apt-get update && \
    apt-get install -y \
    software-properties-common && \
    add-apt-repository ppa:jonathonf/ffmpeg-4 && \
    apt-get update && \
    apt-get install -y ffmpeg

# Optionally, clean up the apt cache to reduce image size
RUN rm -rf /var/lib/apt/lists/*
# Install ffmpeg
# RUN apt install ffmpeg

# Copy the rest of your application files into the container
COPY . /app/


# Set the entry point to run the bot
CMD ["python", "bot.py"]
