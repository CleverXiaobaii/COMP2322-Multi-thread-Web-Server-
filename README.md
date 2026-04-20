# How to Compile and Run the Multi-thread Web Server Project

## 1.Prerequisites
- Python 3.10 or above
- Recommended: Use a virtual environment (venv)
- Go to the project root directory and do the following

## 2. Start the Server
```
python server/src/app.py
```

- The server will listen on the configured port (default: 8080).
- You can modify `server/src/config.py` and `client/src/config.py` for basic configuration (host, port, etc).

## 3. Run the Client

Open a new terminal:
```
cd <project root directory>/client/src
python app.py
```

- Follow the on-screen prompts to interact with the server.
- Example commands:
  - `GET /data`
  - `GET /logo`
  - `HEAD /data`
  - `quit` (to exit)

## 4. Notes
- All dependencies are pure Python, no compilation is needed.
- For PDF extraction tools, see tools/read_pdf_and_save.py and requirements-pdf.txt.
- Logs and resources are stored in the respective resource/ folders.

## 5. Troubleshooting
- Ensure the server is running before starting the client.
- If ports are in use, change the port in config.py.
- For any issues, check the terminal output for error messages.
