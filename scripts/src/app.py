import os
import sys
import contextlib
import io
import time
import logging
from pathlib import Path
import streamlit as st

# Import the updated engineering layers from generate_risk_report.py
from generate_risk_report import (
    input_folder,
    output_folder,
    log_folder,
    ingest_file,          # <-- Swapped old load_from_csv function for ingestion routing
    normalize_risk_data,
    save_data,            # Handles dynamic type output exports (.csv vs .xlsx)
    get_json_data,
    fetch_llm_report,
    save_to_json_file,
    generate_narrative,
    save_narrative_to_file
)

# --- UTILITY TO CAPTURE STDOUT ---
#This class redirects standard output to a Streamlit text component in real-time.
class StreamlitStdoutRedirector(contextlib.AbstractContextManager):
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.string_io = io.StringIO()

    def __enter__(self):
        # Capture all print() statements and route them to our string buffer
        sys.stdout = self.string_io
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Restore the original stdout
        sys.stdout = sys.__stdout__

    def update_ui(self):
        # Refresh the text wrapper container with whatever has printed during execution
        self.placeholder.code(self.string_io.getvalue())


# --- CORE PIPELINE EXECUTION WRAPPER ---
def run_automated_pipeline(log_placeholder, input_file):
    """Executes the complete risk management data pipeline using reactive UI variable parameters."""
    input_file_path = os.path.join(input_folder, input_file)

    # Pre-execution file evaluation safety gate
    if not os.path.isfile(input_file_path):
        st.error(f"Error: Target file '{input_file}' not found in the 'inputs' directory.")
        return None

    # Deconstruct extension traits dynamically based on user context textbox selection
    file_path_obj = Path(input_file_path)
    name = file_path_obj.stem
    ext = file_path_obj.suffix.lower()

    # Target export routing destinations
    cleaned_file = input_folder / f"{name}_cleaned{ext}"
    json_output_file = output_folder / "risk_report.json"
    narrative_report = output_folder / "risk_narrative_report.txt"
    api_key = os.environ.get("Risk_Report_Key")

    # Capture print() statements and route them visually to our console readout component
    with contextlib.redirect_stdout(io.StringIO()) as buffer:
        try:
            print("Pipeline started.")
            log_placeholder.code(buffer.getvalue())  # Update UI with current buffer

            # Step 1: Unified dynamic spreadsheet ingestion (.csv, .xlsx, .xls, .txt)
            data_from_file = ingest_file(input_file_path)
            print(f"Loaded {len(data_from_file)} risks from register source file: '{input_file}'")
            log_placeholder.code(buffer.getvalue()) 

            # Step 2: Inherent and residual score logic preprocessing
            clean_data = normalize_risk_data(data_from_file)
            print("Spreadsheet normalization metrics computed.")
            log_placeholder.code(buffer.getvalue())    

            # Step 3: Intermediate backup serialization matching input extensions
            save_data(cleaned_file, clean_data, ext)
            print(f"Normalized working snapshot stored to: '{cleaned_file.name}'")
            log_placeholder.code(buffer.getvalue())

            # Step 4: JSON processing conversions
            json_payload = get_json_data(clean_data)
            print("Data structures packaged into a JSON text payload layout.")
            log_placeholder.code(buffer.getvalue())

            # Step 5: Secure OpenAI chat completion request transaction
            print("Transmitting contextual payload parameters to OpenAI for strategic synthesis...")
            log_placeholder.code(buffer.getvalue())
            llm_data = fetch_llm_report(json_payload, api_key)
            print("Response successfully decrypted and parsed by application server.")
            log_placeholder.code(buffer.getvalue())

            # Step 6: Final structural artifact export procedures
            save_to_json_file(json_output_file, llm_data)
            print(f"System JSON schema metrics saved to: '{json_output_file.name}'")

            narrative = generate_narrative(llm_data)
            save_narrative_to_file(narrative_report, narrative)
            print(f"Executive text summary report saved to: '{narrative_report.name}'")

            print("Pipeline completed successfully.")
            log_placeholder.code(buffer.getvalue())

            return narrative

        except Exception as e:
            st.error(f"Pipeline crashed with an unhandled traceback exception: {e}")
            logging.error(f"Streamlit runtime pipeline execution failure: {e}", exc_info=True)
            return None


# --- STREAMLIT UI CONFIGURATION ---
st.set_page_config(
    page_title="Next-Gen Risk Analytics",
    layout="wide"
)

st.title("Automated Risk Analyst")
st.markdown("---")                             # Horizontal divider

# Split dashboard workspace view evenly into two layout control blocks
col1, col2 = st.columns(2)

with col1:
    st.subheader("Control Center")

    # Reactive user textbox component mapping straight to inputs directory files
    target_filename = st.text_input(
        label="Source Filename", 
        value="test_risk.xlsx", 
        help="Type the full name of the file located inside your 'inputs' folder (e.g., test_risk.xlsx, test_risk.csv. test_risk.txt)"
    )

    # Core system action trigger interface button
    start_pipeline = st.button("Generate Risk Report", use_container_width=True, type="primary")

    st.subheader("Live Operation Logs")
    # Interactive log tracing viewport block
    console_logs = st.empty()
    console_logs.code("System idling... Enter a valid input file and click the execution button to begin.")

# Active process handler evaluations
if start_pipeline:
    with st.spinner("Processing risk parameters..."):
        # Forward operational console and typed filename target downstream into execution stack
        final_narrative = run_automated_pipeline(console_logs, target_filename)

    if final_narrative:
        with col2:
            st.subheader("Generated Executive Narrative")

            # Custom styled HTML markdown layout window containing scrollable report payload results
            st.markdown(
                f"""
                <div style="
                    background-color: #1e293b; 
                    color: #f8fafc; 
                    padding: 20px; \
                    border-radius: 8px; \
                    height: 550px; \
                    overflow-y: scroll; \
                    white-space: pre-wrap; \
                    font-family: monospace;\
                    border: 1px solid #334155;\
                    line-height: 1.5;\
                ">{final_narrative}</div>
                """, 
                unsafe_allow_html=True
            )

            # Native browser download button widget asset mapping final strings out of RAM memory
            st.download_button(
                label="Download Risk Narrative Report (.txt)",
                data=final_narrative,
                file_name="risk_narrative_report.txt",
                mime="text/plain",
                use_container_width=True
            )