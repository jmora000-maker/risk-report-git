import os
import sys
import contextlib
import io
import time
import logging
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="Next-Gen Risk Dashboard")

# Import your existing pipeline functions 
# (Assuming your script is named generate_risk_report.py)
from generate_risk_report import (
    input_folder,
    output_folder,
    log_folder,
    load_from_csv,
    normalize_risk_data,
    save_to_csv_file,
    get_json_data,
    fetch_llm_report,
    save_to_json_file,
    generate_narrative,
    save_narrative_to_file
)

# --- UTILITY TO CAPTURE STDOUT ---
class StreamlitStdoutRedirector(contextlib.AbstractContextManager):
    """Redirects standard output to a Streamlit text container in real-time."""
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.string_io = io.StringIO()

    def __enter__(self):
        sys.stdout = self.string_io
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = sys.__stdout__

    def update_ui(self):
        # Refresh the text area with whatever has been printed so far
        self.placeholder.code(self.string_io.getvalue())

# --- STREAMLIT UI CONFIGURATION ---
st.set_page_config(
    page_title="Next-Gen Risk Analytics",
    layout="wide"
)

st.title("Next-Gen Risk Report Generator")
st.markdown("""
This application automates the ingestion of project risks, processes them via an AI Synthesis engine, and produces downstream data matrices and a professional executive narrative.
""")

st.sidebar.header("Pipeline Configuration")
target_filename = st.sidebar.text_input("Target Input File Name", value="test_risk.txt")

# Set up paths relative to your script
full_input_path = input_folder / target_filename
json_output_file = output_folder / "risk_report.json"
narrative_report = output_folder / "risk_narrative_report.txt"

st.sidebar.markdown(f"**Target Ingestion Path:**\n`{full_input_path}`")

# --- MAIN AUTOMATED EXECUTION TRACER ---
def run_automated_pipeline(stdout_holder):
    with StreamlitStdoutRedirector(stdout_holder) as redirector:
        # 1. Validation Check
        if not full_input_path.is_file():
            print(f"Error: '{target_filename}' does not exist in {input_folder}.")
            redirector.update_ui()
            st.error(f"Target file not found at: {full_input_path}")
            return False

        print(f"'{target_filename}' discovered automatically in inputs folder.")
        print("Pipeline started.")
        redirector.update_ui()

        # Define cleaned CSV output file name
        cleaned_file = input_folder / f"{full_input_path.stem}_cleaned{full_input_path.suffix}"

        # Fetch API Key
        api_key = os.environ.get("Risk_Report_Key")
        if not api_key:
            print("CRITICAL ERROR: 'Risk_Report_Key' environment variable is missing.")
            redirector.update_ui()
            st.error("Missing API Key! Please set the 'Risk_Report_Key' in Replit Secrets.")
            return False

        # 2. Extract & Normalize
        data_from_csv = load_from_csv(full_input_path)
        print(f"{len(data_from_csv)} risks loaded from '{target_filename}'.")
        redirector.update_ui()

        clean_data = normalize_risk_data(data_from_csv)
        print("Data normalized.")
        redirector.update_ui()

        save_to_csv_file(cleaned_file, clean_data)
        print(f"Normalized data saved to '{cleaned_file.name}'.")
        redirector.update_ui()

        # 3. Payload Conversion
        json_payload = get_json_data(clean_data)
        print("Data converted to JSON for LLM payload.")
        print("Sending payload to LLM for synthesis. This may take a moment...")
        redirector.update_ui()

        # 4. LLM Query execution
        try:
            llm_data = fetch_llm_report(json_payload, api_key)
            print("LLM analysis successfully parsed.")
            redirector.update_ui()
        except Exception as e:
            print(f"Pipeline Interrupted: {str(e)}")
            redirector.update_ui()
            st.error(f"LLM API Call failed: {e}")
            return False

        # 5. Save Outputs
        save_to_json_file(json_output_file, llm_data)
        print(f"LLM JSON data saved to '{json_output_file.name}'.")
        redirector.update_ui()

        narrative = generate_narrative(llm_data)
        save_narrative_to_file(narrative_report, narrative)
        print(f"Narrative report saved to '{narrative_report.name}'.")
        print("Pipeline completed successfully.")
        redirector.update_ui()
        
        return narrative

# --- UI ACTION TRIGGER ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Execution Controls")
    # Single execution button as requested
    start_pipeline = st.button("Process & Generate Risk Report", type="primary", use_container_width=True)
    
    st.markdown("### Real-time Console Log")
    # This element acts as our real-time terminal readout window
    console_logs = st.empty()
    console_logs.code("System idling... Click the button above to begin execution.")

if start_pipeline:
    with st.spinner("Processing delivery risk parameters..."):
        final_narrative = run_automated_pipeline(console_logs)
        
    if final_narrative:
        with col2:
            st.subheader("Generated Executive Narrative")
            
            # Custom CSS styling wrapped in Markdown to provide a scrollable text container
            st.markdown(
                f"""
                <div style="
                    background-color: #1e293b; 
                    color: #f8fafc; 
                    padding: 20px; 
                    border-radius: 8px; 
                    height: 550px; 
                    overflow-y: scroll; 
                    white-space: pre-wrap; 
                    font-family: monospace;
                    border: 1px solid #334155;
                    line-height: 1.5;
                ">{final_narrative}</div>
                """, 
                unsafe_allow_html=True  # Ensure this says 'unsafe_allow_html', not 'unsafe_allow_code'
            )
            
            # Simple direct download button for convenience
            st.download_button(
                label="Download Narrative Report (.txt)",
                data=final_narrative,
                file_name="risk_narrative_report.txt",
                mime="text/plain",
                use_container_width=True
            )