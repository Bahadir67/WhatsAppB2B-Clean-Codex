# Repository Guidelines

## Project Structure & Module Organization
Keep the multi-agent runtime organized around `src/core/`. `swarm_b2b_system.py` orchestrates the agent cluster and Flask API, `whatsapp-webhook-sender.js` handles the WhatsApp bridge, `product-list-server-v2.js` serves HTML catalogs, and `config.js` centralizes paths and ports. Database helpers and SQL utilities sit alongside them; avoid scattering new modules outside `src/core` unless they are migrations (`migrations/`) or generated catalog HTML (`product-pages/`). Data seeds and manual SQL live in `sql/`. Session artifacts go under `whatsapp-sessions/`; they should not be committed.

## Build, Test, and Development Commands
Install dependencies with `pip install -r requirements.txt` and `npm install`. Run the full stack locally via `start_services.bat`, which opens the Swarm API, WhatsApp bridge, and product server in separate consoles. For focused work, use `python src/core/swarm_b2b_system.py` and `node src/core/whatsapp-webhook-sender.js`; `npm run dev` enables nodemon reloading for the WhatsApp service. Validate the OpenRouter integration before shipping with `python test_openrouter.py`. Cloudflare tunneling is optional; invoke `start_tunnel.bat` after setting `TUNNEL_PORT` in `.env`.

## Coding Style & Naming Conventions
Python modules follow four-space indentation, `snake_case` helpers, and docstrings for agents and tools; keep imports grouped standard, third-party, then local. JavaScript files use four-space indents, camelCase for functions and variables, and uppercase constants for configuration keys. Preserve UTF-8 logging (Turkish labels and emojis are intentional). Prefer small, single-purpose modules added under `src/core` and expose configuration through `config.js` or environment variables.

## Testing Guidelines
Regression coverage is primarily manual. Extend `test_openrouter.py` for API smoke checks and add new scripts under `tests/` or `src/core/tests/` if you introduce automated flows. Mirror the service name in the filename (`whatsapp_service_test.py`, `product-list.server.test.js`) and ensure scripts use environment variables rather than hard-coded tokens. Run relevant tests before packaging a pull request and capture console excerpts for any non-trivial fix.

## Commit & Pull Request Guidelines
Use imperative, scope-prefixed commit messages (for example `feat(bot): add catalog link formatter`) to clarify the impacted service. Describe migrations, schema updates, or new environment keys explicitly in the body. Pull requests should link issues, outline validation steps (commands run, logs inspected), and include screenshots for UI or catalog changes. Note any secrets or generated artifacts that must stay local.

## Environment & Operations
Never commit `.env`, session folders, or files inside `product-pages/`; treat them as runtime outputs. After adjusting ports or tunnel settings, update `config.js` and document the change in the pull request. When new SQL is required, add a numbered file under `migrations/` and keep statements idempotent.
