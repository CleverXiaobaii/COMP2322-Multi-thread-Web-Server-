# Client Module

This directory is reserved for client-side implementation.

- Place client source code in client/src.
- Add test client scripts and resources here in later stages.

## First Stage Client

The first-stage client is implemented in client/src/app.py.

### Run

1. Edit request target and request line in client/src/config.py.
2. Start one client instance in one terminal:

python3 -m client.src.app

### Multiple Clients

To run multiple clients, open multiple terminals and execute the same command in each
terminal. Each terminal runs one independent client instance.
