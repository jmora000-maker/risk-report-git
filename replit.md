# Risk Report

Synthesize a Risk Register into a Risk Report using a format constrained prompt and an OpenAI LLM

## Run & Operate

- enter valid cvs risk register file in inputs folder
- 
## Stack

- API: gpt-4o-mini LLM

## Where things live

inputs - risk register, cleaned risk register
outputs - risk narrative report, risk report json
logs - app log
src - python script

## Architecture decisions

- Three Phase Pipeline - Data Preprocessing, AI Analysis, Report Generation
- Functions in each phase invoked during Main execution flow

## Product

- Current: command line input cvs and output report text
- Demonstration: Wrap in Streamlit interface
- Future: Use as basis with RAG and project documents to ID unregistered risks

## User preferences

- a GUI for demonstrations

## Gotchas

- the input file keys map to the preprocessing stage and LLM response JSON schema


