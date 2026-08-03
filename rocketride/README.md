# RocketRide pipelines

Both files are generated from `src/adapters/vendors.py` — the same definitions
the live demo runs. Component names (`webhook`, `prompt`, `llm_anthropic`,
`response_answers`, `response_text`) were confirmed against the live server's
own catalogue (`client.get_services()`, 140 providers), not the SDK docstrings
— the docstring example shows providers that do not exist on the server.

- `announcer-echo.pipe` — runs with no model key. Every brokered decision is
  sent through it and returns a stored-object receipt (verified live: distinct
  `objectId` per action).
- `announcer.pipe` — the spoken-announcement form. Replace
  `${ANTHROPIC_API_KEY}` with a real key (RocketRide passes YOUR key through
  to Anthropic; all 20 of their Claude profiles list `apikey` as required).

Load either with:

```python
started = await client.use(filepath="rocketride/announcer-echo.pipe")
```
