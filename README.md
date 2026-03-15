# Autonomous IT Procurement Agent

Python prototype that converts a natural-language procurement request into a structured search, scrapes Amazon and Flipkart, evaluates the returned products with an LLM, and shows approved results in a Gradio web interface.

## Project Architecture

The project is organized as a small pipeline with a simple orchestration layer in `src/agent.py`. The agent runs three main steps: parse the user request, search both e-commerce sources, and evaluate/sort the resulting candidates. Request parsing is handled in `src/request_parser.py`, product validation is handled in `src/evaluator.py`, and the shared data contracts live in `src/schemas.py`.

Source-specific scraping logic is isolated under `src/scrapers/`. `amazon.py` and `flipkart.py` use Playwright to open search/product pages and BeautifulSoup to extract titles, prices, and spec details from rendered HTML. LLM access is centralized in `src/llm_client.py`, which tries Gemini first and falls back to Groq if needed. The main web entry point for the assignment is `gradio-app.py`, while `app.py` remains an alternative Panel UI.

## Dependencies

Core dependencies used by this project:
- `playwright` for browser automation
- `playwright-stealth` for Amazon anti-bot hardening
- `beautifulsoup4` and `lxml` for HTML parsing
- `langchain-core`, `langchain-community`, and `langgraph` for orchestration and LLM workflow
- `langchain-google-genai` for Gemini access
- `langchain-groq` for Groq fallback access
- `pydantic` for typed request/result schemas
- `python-dotenv` for loading environment variables from `.env`
- `gradio` for the main web interface
- `panel` for the optional alternate UI

Install everything with the provided requirements file.

## Installation And Run

1. Create and activate a virtual environment.

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. Install Python dependencies.

   ```powershell
   pip install -r requirements.txt
   ```

3. Install the Playwright browser used by the scrapers.

   ```powershell
   python -m playwright install chromium
   ```

4. Create a `.env` file in the project root and set at least one LLM provider key.

   ```env
   GOOGLE_API_KEY=your_google_key
   GROQ_API_KEY=your_groq_key
   ```

5. Run the Gradio app.

   ```powershell
   python gradio-app.py
   ```

6. Open the local URL printed by Gradio in your browser.

## How To Use The Gradio Web Interface

1. Start the app with `python gradio-app.py`.
2. In the `Procurement Request` box, enter a request such as a laptop or monitor requirement.
3. Adjust `Max products/platform` to control how many product pages are scraped from Amazon and Flipkart.
4. Click `Run` to process your request.
5. Review the `Parsed Request` JSON to confirm the extracted constraints.
6. Review the `Results` area for pipeline steps, errors, approved products, matched specs, pricing, and links.
7. Click `Run Demo 2` if you want to test the second built-in sample request quickly.

## Design Notes

A LangGraph workflow in `src/agent.py` coordinates three coarse stages: request parsing, multi-source search, and AI-based evaluation. This keeps the control flow simple while still separating responsibilities cleanly: parser logic, scraper logic, evaluator logic, and UI logic each live in their own files. The search stage runs Amazon and Flipkart scraping in worker threads so Playwright can operate safely even when the UI framework is running its own event loop.

Playwright is used because these sites rely on rendered, client-side content and dynamic page behavior. BeautifulSoup is used after page render because it makes HTML extraction shorter and more robust than deeply chaining browser selectors everywhere. I ensured strict evaluation by giving the LLM structured product specifications and enforcing deterministic JSON outputs using Pydantic schemas

Edge cases are handled mainly through layered fallbacks and strict filtering. Both scrapers use multiple selectors because e-commerce layouts change often. The extraction logic falls back to alternative metadata such as LD+JSON, Open Graph tags, and generic selectors when primary selectors fail. Missing prices or specs do not crash the pipeline; those fields are passed through as partial data and the evaluator decides whether the product is acceptable. Search failures from one platform are captured as errors so the full run can still continue with the other source.

## Notes

- E-commerce DOM structure changes frequently, so selectors may need periodic updates.
- The evaluator is intentionally strict and may reject listings with incomplete or ambiguous specifications.
- `app.py` is available as an optional Panel interface, but `gradio-app.py` is the primary UI described in this README.

If I had more time, I would add live streaming progress logs in the UI, caching for repeated searches, and stronger automated tests around scraper selector fallbacks.
