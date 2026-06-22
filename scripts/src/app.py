import os
import contextlib
import logging
from pathlib import Path
import streamlit as st
from datetime import date
import requests
import pandas as pd
import csv
import json

# --- UTILITY TO CAPTURE STDOUT ---
# This class redirects standard output to a Streamlit text component in real-time.
class StreamlitStdoutRedirector:
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.output_str = ""

    def write(self, text):
        self.output_str += text
        self.placeholder.code(self.output_str, language="text")

    def flush(self):
        pass

# --- PATHS ---
current_script_dir=Path(__file__).resolve().parent
project_root=current_script_dir.parent
input_folder = project_root / "inputs"
log_folder = project_root / "logs"
output_folder = project_root / "outputs"


# --- SCRIPT: generate_risk_report.py FUNCTIONS
# --- GLOBAL CONSTANTS ---

ALLOWED_CATEGORIES = (
    "Schedule",
    "Cost",
    "Technical",
    "Vendor",
    "Compliance",
    "Resource",
    "Security",
    "Scope",
    "Stakeholder",
    "Quality",
    "External",
    "Data",
    "Operational",
    "Procurement",
)

ALLOWED_STATUS = {"Open", "Watching", "Response in Progress", "Escalated", "Closed"}

ALLOWED_RESPONSE_STRATEGIES = {"Avoid", "Mitigate", "Transfer", "Accept", "Escalate"}

today = date.today().strftime("%B %d, %Y")

# --- DATA LOADING ---

# Routes the file to the correct loader based on extension.
def ingest_file(input_file_path):
    ext = Path(input_file_path).suffix.lower()
    if ext == ".csv":
        return load_from_csv(input_file_path)
    elif ext == ".txt":
        return load_from_csv(input_file_path)
    elif ext in [".xlsx", ".xls"]:
        return load_from_excel(input_file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


# Read the first sheet by default; handles NaN values cleanly by converting them to empty strings"""
def load_from_excel(input_file):
    df = pd.read_excel(input_file, dtype=str)
    df = df.fillna("")
    return df.to_dict(orient="records")


# Reads a CSV file and converts it to a list of dictionaries using the csv module."""
def load_from_csv(input_file):
    with open(input_file, newline="", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f)]

# --- DATA NORMALIZATION ---
def normalize_risk_data(dict_data):
    # clean up text fields
    for row in dict_data:  # iterate over each row
        if "risk_id" in row:  # check if the key exists
            row["risk_id"] = row["risk_id"].strip()  # strip whitespace
        if "title" in row:  # check if the key exists
            row["title"] = row["title"].strip()  # strip whitespace

        # validate category enumeration
        if "category" in row:  # check if the key exists
            category = row["category"].strip()  # strip whitespace
            if category not in ALLOWED_CATEGORIES:  # check if the value is allowed
                logging.warning(f"Invalid category: {category}")  # log a warning if not allowed

        # validate status enumeration
        if "status" in row:  # check if the key exists
            status = row["status"].strip()  # strip whitespace
            if status not in ALLOWED_STATUS:  # check if the value is allowed
                logging.warning(f"Invalid status: {status}")  # log a warning if not allowed

        # validate response strategy enumeration
        if "response_strategy" in row:
            response_strategy = row["response_strategy"].strip()
            if response_strategy not in ALLOWED_RESPONSE_STRATEGIES:
                logging.warning(f"Invalid response strategy: {response_strategy}")

        # convert numeric fields to integers
        row["risk_score"] = int(row.get("risk_score", 0))  # convert to integer
        row["probability"] = int(row.get("probability", 0))  # convert to integer
        row["impact"] = int(row.get("impact", 0))  # convert to integer
        row["residual_probability"] = int(row.get("residual_probability", 0))  # convert to integer
        row["residual_impact"] = int(row.get("residual_impact", 0))  # convert to integer

        # calculate inherent score
        row["inherent_score"] = row["probability"] * row["impact"]  # calculate inherent score
        row["residual_score"] = row["residual_probability"] * row["residual_impact"]  # calculate residual score

    # Sort by residual first, then by inherent (this gives priority to residual score)
    dict_data.sort(key=lambda x: x["residual_score"], reverse=True)
    dict_data.sort(key=lambda x: x["inherent_score"], reverse=True)
    return dict_data

# --- DATA SAVING ---
# Saves data to a file in the original format (CSV or Excel) using pandas."""
def save_data(output_file, dict_data, original_ext):
    if original_ext in [".csv", ".txt"]:
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=dict_data[0].keys())
            writer.writeheader()
            writer.writerows(dict_data)
    elif original_ext in [".xlsx", ".xls"]:
        df = pd.DataFrame(dict_data)
        df.to_excel(output_file, index=False)
    return None

# --- JSON CONVERSION ---
def get_json_data(dict_data):
    json_data = json.dumps(dict_data)
    return json_data  # payload is a JSON string

# --- LLM INTEGRATION ---
def fetch_llm_report(json_data, api_key):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    prompt = f"""
   You are a project risk analyst. Today's date is: {today}. Read the provided risk register data and produce a synthesized risk report.

   Your task is to analyze the risks, identify the most important patterns, summarize overall exposure, and generate a risk report in STRICT JSON only.

   Rules:
   1. Output must be valid JSON.
   2. Do not include markdown fences.
   3. Do not include any text before or after the JSON.
   4. Use exactly the schema and field names provided below.
   5. If a value is unknown, use an empty string for text fields, 0 for numeric fields, and [] for arrays.
   6. Do not invent risks that are not present in the input.
   7. Base all conclusions only on the provided input data.
   8. Keep summaries concise, specific, and professional.
   9. For "top_risks", include up to 10 highest-priority open or active risks, sorted by highest inherent or residual exposure available.
   10. For "detailed_risk_analysis", include up to 10 highest-priority risks unless fewer are provided.
   11. Treat "high_risks" as risks with risk_score >= 15 unless an explicit priority field is provided.
   12. If residual_score is unavailable, set it to 0.
   13. If trend cannot be determined from the data, state that trend cannot be determined from the provided snapshot.
   14.For "top_risks", the summary should connect the risk to a concrete project consequence such as milestone slippage, budget overrun, failed control audit, deployment delay, regulatory exposure, or service disruption.

   Report structure:
   The executive summary should describe the total risk picture, concentration by category, and whether risk exposure is rising, stable, or improving.
   The category summary should aggregate risk themes such as schedule, cost, technical, vendor, compliance, or resource.
   The top risks section should rank by inherent or residual score and explain why each matters in plain business language.
   The detailed analysis should not repeat the raw register verbatim; it should interpret the risk, response adequacy, and next action.
   The conclusions should separate three things: immediate actions, management escalations, and lower-priority watch items.

 Required JSON schema:
 {{
   "report_metadata": {{
     "project_name": "string",
     "report_date": "string",
     "input_file": "string",
     "total_risks": 0,
     "open_risks": 0,
     "high_risks": 0
     "active_risks": 0
   }},
   "executive_summary": {{
     "overall_summary": "string",
     "key_drivers": ["string"],
     "trend_statement": "string",
     "management_attention": ["string"]
   }},
   "portfolio_summary": {{
     "risks_by_category": [
       {{
         "category": "string",
         "count": 0,
         "average_score": 0,
         "max_score":0,
         "highest_score": 0
         }}
     ],
     "risks_by_status": [
       {{
         "status": "string",
         "count": 0
         }}
     ],
   "top_risks": [
       {{
         "risk_id": "string",
         "title": "string",
         "category": "string",
         "owner": "string",
         "status": "string",
         "inherent_score": 0,
         "residual_score": 0,
         "summary": "string"
       }}
     ]
   }},
   "detailed_risk_analysis": [
     {{
       "risk_id": "string",
       "title": "string",
       "category": "string",
       "owner": "string",
       "status": "string",
       "inherent_score": 0,
       "residual_score": 0,
       "why_it_matters": "string",
       "summary": "string",
       "trigger": "string",
       "current_response": "string",
       "contingency_plan": "string",
       "next_action": "string"
       "adequacy": "string"
     }}
   ],
   "conclusions": {{
     "priority_actions": ["string"],
     "escalations": ["string"],
     "watch_items": ["string"]
     "summary": "string"
   }}
   }}

   Field interpretation:
   - project_name: Use the provided project name if present; otherwise use "General Report".
   - report_date: Use the provided report date if present; otherwise use the current date.
   - input_file: Use the provided input filename if present; otherwise use "".
   - total_risks: Total number of risk records in the input.
   - open_risks: Count of risks whose status suggests active monitoring or unresolved exposure, such as Open, Watching, Response in Progress, or Escalated.
   - high_risks: Count of risks with risk_score >= 15, unless an explicit priority field overrides this.
   - overall_summary: A brief assessment of the total project risk picture.
   - key_drivers: Main themes driving risk exposure, such as vendor dependency, schedule compression, resource gaps, compliance uncertainty, or technical complexity.
   - trend_statement: Describe trend only if the input supports it. Otherwise say trend cannot be determined from the provided snapshot.
   - management_attention: Short statements of where leadership focus is needed.
   - risks_by_category: Aggregate counts and scoring by category.
   - risks_by_status: Aggregate counts by status with brief interpretation.
   - top_risks: Highest-priority risks summarized in one to two sentences each.
   - detailed_risk_analysis: Focus on the most important risks and provide actionable interpretation.
   - priority_actions: Immediate actions recommended for the next reporting period.
   - escalations: Items requiring leadership or sponsor attention.
   - watch_items: Lower-immediacy items that should continue to be monitored.
   - summary: A brief summary of the conclusions.

   Scoring guidance:
   - Use risk_score as the inherent_score when available.
   - If risk_score is not available but probability and impact are available, compute inherent_score = probability * impact.
   - Use residual_score if present.
   - If residual_score is not present but residual_probability and residual_impact are present, compute residual_score = residual_probability * residual_impact.
   - Otherwise set residual_score to 0.

   Status guidance:
   - Treat these as open/active unless the input clearly indicates otherwise: Open, Watching, Response in Progress, Escalated.
   - Treat Closed as not open.
   - If status values differ, infer the nearest equivalent conservatively.

   RISK_REGISTER:{json_data}"""

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "You are a risk analyst. Return valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        raw_ai_output = response.json()["choices"][0]["message"]["content"]  # extract the response text
        clean_ai_output = raw_ai_output.replace("```json", "").replace("```", "").strip()  # remove markdown fences
        clean_ai_dict = json.loads(clean_ai_output)  # convert to dictionary
        return clean_ai_dict
    else:
        print(f"DEBUG: API Failed: {response.status_code}")
        raise Exception(f"API Failed: {response.status_code}")

# --- JSON SAVING ---
def save_to_json_file(output_file, clean_ai_dict):
    with open(output_file, "w", encoding="utf-8") as f:  # open the file for writing
        json_string = json.dumps(clean_ai_dict, indent=4)  # convert the dictionary to a JSON string
        f.write(json_string)  # write the JSON string to the file
    return None

# --- NARRATIVE GENERATION ---
def generate_narrative(clean_ai_dict):
    report_metadata = clean_ai_dict.get("report_metadata", {})
    executive_summary = clean_ai_dict.get("executive_summary", {})
    portfolio_summary = clean_ai_dict.get("portfolio_summary", {})
    top_risks = clean_ai_dict.get("top_risks", [])
    detailed_risk_analysis = clean_ai_dict.get("detailed_risk_analysis", [])
    conclusions = clean_ai_dict.get("conclusions", {})

    lines = []

    # Title
    project_name = report_metadata.get("project_name", "Unknown Project")
    report_metadata.get("report_date", "Unknown Date")
    total_risks = report_metadata.get("total_risks", "Unknown")
    active_risks = report_metadata.get("active_risks", "Unknown")

    lines.append(f"RISK REPORT")
    lines.append(f"Project: {project_name}")
    lines.append(f"Report Date: {today}")
    lines.append("")
    lines.append(
        f"This report summarizes {total_risks} identified risks, of which {active_risks} are currently active.")
    lines.append("")

    # Executive Summary
    lines.append("EXECUTIVE SUMMARY")
    lines.append(executive_summary.get("overall_summary", "No executive summary provided."))
    lines.append("")

    trend_statement = executive_summary.get("trend_statement")
    if trend_statement:
        lines.append(f"Overall trend: {trend_statement}")
        lines.append("")

    key_drivers = executive_summary.get("key_drivers", [])
    if key_drivers:
        lines.append("The principal risk drivers across the portfolio are "
                     + ", ".join(key_drivers[:-1])
                     + (", and " + key_drivers[-1] if len(key_drivers) > 1 else key_drivers[0])
                     + ".")
        lines.append("")

    management_attention = executive_summary.get("management_attention", [])
    if management_attention:
        lines.append("Management attention is most needed in the following areas:")
        for item in management_attention:
            lines.append(f"- {item}")
        lines.append("")

    # Portfolio Overview
    lines.append("PORTFOLIO OVERVIEW")
    risks_by_category = portfolio_summary.get("risks_by_category", [])
    # This sorts the list of dictionaries by the 'count' key in descending order
    sorted_categories = sorted(risks_by_category, key=lambda x: x.get("count", 0), reverse=True)

    if risks_by_category:
        for cat in sorted_categories:
            category = cat.get("category", "Unspecified")
            count = cat.get("count", "Unknown")
            avg_score = cat.get("average_score", "Unknown")
            max_score = cat.get("highest_score", "Unknown")
            commentary = cat.get("commentary", "")
            lines.append(
                f"- {category} risks represent {count} items in the register, "
                f"with an average score of {avg_score} and a highest score of {max_score}. "
                f"{commentary}".strip()
            )
        lines.append("")
    else:
        lines.append("- No portfolio concentration data was provided.")
        lines.append("")

    # Top Risk Themes
    lines.append("TOP RISK THEMES")
    if sorted_categories:
        top_categories = [c.get("category", "Unspecified") for c in sorted_categories[:3]]
        if top_categories:
            lines.append(
                "- The main themes emerging from the portfolio are concentrated in "
                + ", ".join(top_categories[:-1])
                + (", and " + top_categories[-1] if len(top_categories) > 1 else top_categories[0])
                + "."
            )
            lines.append("")
    else:
        lines.append("No dominant portfolio themes could be identified from the available data.")
        lines.append("")

    # Top Risks
    lines.append("TOP RISKS REQUIRING IMMEDIATE ATTENTION")
    if detailed_risk_analysis:
        for risk in detailed_risk_analysis:
            risk_id = risk.get("risk_id", "Unknown ID")
            title = risk.get("title", "Untitled Risk")
            owner = risk.get("owner", "Unassigned")
            status = risk.get("status", "Unknown")
            inherent = risk.get("inherent_score", "Unknown")
            residual = risk.get("residual_score", "Unknown")
            why_it_matters = risk.get("why_it_matters", "No impact narrative provided.")
            current_response = risk.get("current_response", "No current response documented.")
            adequacy = risk.get("response_adequacy", "Response adequacy not assessed.")
            next_action = risk.get("next_action", "No next action defined.")

            lines.append(f"{risk_id} - {title}: This risk is currently {status} and owned by {owner}.")
            lines.append(f"- Its inherent score is {inherent}, and its residual score is {residual}.")
            lines.append(f"- {why_it_matters} Current response: {current_response}. ")
            lines.append(f"- Assessment of response adequacy: {adequacy}.")
            lines.append(f"- Next required action: {next_action}.")
            lines.append("")
    elif top_risks:
        for risk in top_risks:
            lines.append(
                f"{risk.get('risk_id', 'Unknown ID')} - {risk.get('title', 'Untitled Risk')}: "
                f"{risk.get('summary', 'No summary provided.')}"
            )
            lines.append("")
    else:
        lines.append("No top risks were provided.")
        lines.append("")

    # Immediate Actions
    priority_actions = conclusions.get("priority_actions", [])
    lines.append("IMMEDIATE ACTIONS")
    if priority_actions:
        for action in priority_actions:
            lines.append(f"- {action}")
    else:
        lines.append("No immediate actions were identified.")
    lines.append("")

    # Escalations
    escalations = conclusions.get("escalations", [])
    lines.append("ESCALATIONS")
    if escalations:
        for esc in escalations:
            lines.append(f"- {esc}")
    else:
        lines.append("No escalations were identified.")
    lines.append("")

    # Watch Items
    watch_items = conclusions.get("watch_items", [])
    lines.append("WATCH ITEMS")
    if watch_items:
        for item in watch_items:
            lines.append(f"- {item}")
    else:
        lines.append("No watch items were identified.")
    lines.append("")

    # Conclusion
    lines.append("CONCLUSION")
    final_conclusion = conclusions.get("summary", "No conclusion provided.")
    lines.append(f"{final_conclusion}")

    return "\n".join(lines).strip()

# --- NARRATIVE SAVING ---
def save_narrative_to_file(output_file, narrative):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(narrative)
    return None

# --- CORE PIPELINE EXECUTION WRAPPER ---
def run_automated_pipeline(log_placeholder, input_file):
    """Executes the complete risk management data pipeline using reactive UI variable parameters."""
    input_file_path = os.path.join(input_folder, input_file)

    # Pre-execution file evaluation safety gate
    if not os.path.isfile(input_file_path):
        st.error(f"Error: Target file '{input_file}' not found.")
        return None

    # Deconstruct extension traits dynamically based on user context textbox selection
    file_path_obj = Path(input_file_path)
    name = file_path_obj.stem
    ext = file_path_obj.suffix.lower()

    # Target export routing destinations
    cleaned_file = input_folder / f"{name}_cleaned{ext}"
    json_output_file = output_folder / "risk_report.json"
    narrative_report = output_folder / "risk_narrative_report.txt"
    api_key = os.environ.get("OPENAI_API_KEY")

    try:
        print("PIPELINE STARTED.")

        # Step 1: Unified dynamic spreadsheet ingestion (.csv, .xlsx, .xls, .txt)
        print(f"STEP #1: Loading risks from source file.")
        data_from_file = ingest_file(input_file_path)

        # Step 2: Inherent and residual score logic preprocessing
        print("STEP #2: Normalizing risk data.")
        clean_data = normalize_risk_data(data_from_file)


        # Step 3: JSON processing conversions
        print("STEP #3: Packaging data into JSON.")
        json_payload = get_json_data(clean_data)


        # Step 4: Secure OpenAI API completion request transaction
        print("STEP #4: Transmitting payload to OpenAI...")
        print(" -> Please wait for a few moments ...")
        llm_data = fetch_llm_report(json_payload, api_key)

        #Step 5: Create Narrative Report
        print(f"STEP #5: Generating Risk Report.")
        narrative = generate_narrative(llm_data)
        save_narrative_to_file(narrative_report, narrative)

        print("PIPELINE COMPLETED.")

        return narrative

    except Exception as e:
        st.error(f"Pipeline crashed with an unhandled traceback exception: {e}")
        logging.error(f"Streamlit runtime pipeline execution failure: {e}", exc_info=True)
        return None


# --- STREAMLIT UI CONFIGURATION ---
st.set_page_config(
    page_title="AI Risk Report Generator",
    layout="wide"
)

st.title("Risk Report Dashboard")
st.caption("Automated narrative synthesis to transform dense spreadsheet registers into high-impact, executive-ready risk intelligence.")
st.markdown("---")                             # Horizontal divider

# Split dashboard workspace view evenly into two layout control blocks
col1, col2 = st.columns(2)

with col1:
    st.subheader("System Configuration")

    # Reactive user textbox component mapping straight to inputs directory files
    target_filename = st.text_input(
        label="Source Filename", 
        value="test_risk.xlsx", 
        help="Type the full name of the file located inside your 'inputs' folder (e.g., test_risk.xlsx, test_risk.csv, test_risk.txt)"
    )

    # Core system action trigger interface button
    start_pipeline = st.button("Generate Risk Report", use_container_width=True, type="primary")

    st.subheader("Pipeline Summary")
    # Interactive log tracing viewport block
    console_logs = st.empty()
    console_logs.info("Click 'Generate Risk Report' button to begin.")

# Persistent frame layout setup for Column 2 immediately on boot
with col2:
    st.subheader("Report Workspace")
    report_placeholder = st.empty()

    # Pre-execution placeholder info state setup
    report_placeholder.info("The risk report will populate here upon synthesis.")

# Active process handler evaluations
if start_pipeline:
    redirector = StreamlitStdoutRedirector(console_logs)

    with st.spinner("Processing risk parameters..."):
        # Wrap the stream interceptor strictly around the pipeline engine call 
        with contextlib.redirect_stdout(redirector):
            final_narrative = run_automated_pipeline(console_logs, target_filename)

    if final_narrative:
        with col2:
            # Overwrite the initial info alert box inside the locked workspace column element
            report_placeholder.markdown(
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
                unsafe_allow_html=True
            )

            # Native browser download button widget asset mapping final strings out of RAM memory
            st.download_button(
                label="Download Risk Report (.txt)",
                data=final_narrative,
                file_name="risk_narrative_report.txt",
                mime="text/plain",
                use_container_width=True
            )