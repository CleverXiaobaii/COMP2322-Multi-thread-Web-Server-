# COMP2322-Multi-thread-Web-Server-

## First Stage (Framework)

This repository now includes a first-stage multi-threaded web server implemented with
basic socket programming in Python.

Current first-stage capabilities:

- Accept TCP connections on configured host and port.
- Create one worker thread per client connection.
- Read and print the raw HTTP request header.
- Parse the request line in a basic way.
- Write request records to a log file.
- Return a minimal HTTP response and close the connection.

Not yet implemented in first stage:

- Full GET/HEAD file serving.
- 304/403/404 complete behavior.
- Last-Modified and If-Modified-Since handling.
- Persistent keep-alive handling.

## Project Structure

- server/src: server-side source code.
- server/resource: server resource files and configuration.
- client/src: client-side source code.

## Run

1. Edit server configuration in server/resource/config.py.
2. Start server from project root:

python3 -m server.src.app

Configuration fields:

- host
- port
- log_path
- buffer_size
- max_header_bytes

## Quick Test

In another terminal:

curl -i http://127.0.0.1:8080/

Then check server output and configured log file for request records.

## Client First Stage

The first-stage client is in client/src/app.py and uses client/resource/config.py.

Run one client in one terminal:

python3 -m client.src.app

To run multiple clients, open multiple terminals and run the same command in each
terminal. Each terminal controls its own independent client instance.