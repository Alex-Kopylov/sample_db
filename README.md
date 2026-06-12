# Database Question Answering Service

Python package scaffold for a LangGraph-backed SQL agent over the sample CSV data.

## Setup

```bash
uv sync
```

Create `.env` and add your OpenAI API key:

```bash
OPENAI_API_KEY=...
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
the CSV files in this repository when the graph is imported. You can also create
it manually with:

```bash
make db
```
