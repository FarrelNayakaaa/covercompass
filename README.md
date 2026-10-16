# CoverCompass

AI agent for insurance (FinTechathon 2026, Topic D). Work in progress.

## Setup
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in LLM_API_KEY

## Run
streamlit run src/app.py

## Test
pytest
