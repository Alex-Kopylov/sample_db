# Database Question Answering Service

Python package scaffold for a LangGraph-backed SQL agent over the sample CSV data.

## Quick start

Spin up your own instance in three steps:

```bash
make setup                 # install deps, scaffold .env, build the database
# edit .env and set OPENAI_API_KEY
make run                   # start the LangGraph API server
```

`make setup` runs `uv sync`, copies `.env.example` to `.env` (when missing), and
builds the SQLite database at `data/app.db`. The API is then served at
`http://127.0.0.1:2024` (docs at `http://127.0.0.1:2024/docs`).

## Setup

Install dependencies:

```bash
uv sync
```

Copy the example environment file and add your OpenAI API key:

```bash
cp .env.example .env
# then edit .env: OPENAI_API_KEY=...
```

## Usage

Start the LangGraph API server:

```bash
make run
```

This runs:

```bash
uv run langgraph dev
```

The API is available at `http://127.0.0.1:2024`. API docs are available at
`http://127.0.0.1:2024/docs`.

Use assistant id `sql_agent`. You can create a thread with `POST /threads` and
then run it with `POST /threads/{id}/runs`, or use stateless `POST /runs`.

Example stateless run:

```bash
curl -s -X POST http://127.0.0.1:2024/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "assistant_id": "sql_agent",
    "input": {
      "messages": [
        {
          "role": "user",
          "content": "How many completed orders are there?"
        }
      ]
    }
  }'
```

The database is created automatically at `data/app.db` from `schema.sql` and
the CSV files in `data/` when the graph is imported. You can also create
it manually with:

```bash
make db
```
