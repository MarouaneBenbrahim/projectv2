Environment setup
-----------------

Create a `.env` file in the project root with:

```
OPENAI_API_KEY=your_openai_api_key_here
```

Install dependencies:

```
pip install -r requirements.txt
```

Optional: The AI advice button in the ML widget requires `OPENAI_API_KEY`.

Repository structure
--------------------

- `main_complete_integration.py`: Primary entry point (dashboard + APIs)
- `core/`: Power and traffic subsystems
- `config/`: Settings, logging, database models/config
- `api/`: (if used) API modules
- `frontend/`: Static assets (if any)
- `data/`: SUMO networks, telemetry, and artifacts
- `tests/`: Test scripts
- `archive/entrypoints/`: Older entry-point scripts (kept for reference)

Run
---

```
pip install -r requirements.txt
python main_complete_integration.py
```

Notes
-----
- SUMO must be installed and `SUMO_HOME` set for traffic simulation.
- AI features are optional; set `OPENAI_API_KEY` in `.env` to enable.

