# Kaito

A Python application based on Responses API with a user-friendly interactive interface.

## Features

- File management and metadata storage
- Vector store integration for embeddings
- Interactive CLI with InquirerPy
- SQLite-based file database
- User data persistence

## Project Structure

```
kaito/
├── src/kaito/              # Main application package
│   ├── engine.py           # Core engine logic
│   ├── file_db.py          # File database management
│   ├── vector_store.py     # Vector storage and retrieval
│   ├── ui_helper.py        # UI utilities and helpers
│   └── datatypes/          # Custom data type definitions
├── tests/                  # Test suite
├── user_data/              # User files and metadata storage
├── main.py                 # Application entry point
├── pyproject.toml          # Project configuration and dependencies
├── Makefile                # Development commands
└── README.md               # This file
```

## Setup

### Installation

*Prerequisites: Python 3.11 and above*

Install dependencies using the Makefile:
```bash
make install
```

#### OpenAI API Key
- Paste your OpenAI API key into .env.example
- Rename `.env.example` to `.env`

#### Files Search Support
- Create a folder `user_data` under this repo
- Create an empty JSON file named `files.json`, and edit as follows:
```json
{}
```
- Copy your PDF files into the folder

## Usage

Run the application:
```bash
make run
```

## License

MIT
