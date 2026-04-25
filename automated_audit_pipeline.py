import os
import json
import re
import tkinter as tk
from tkinter import filedialog
from dotenv import load_dotenv

import pandas as pd
import pdfplumber
import ollama
from pathlib import Path
from litellm import completion


# --- PATHS ---
script_dir = Path(os.getcwd())
env_path = script_dir / ".env"
load_dotenv(dotenv_path=env_path)


# --- LLM FALLBACK FUNCTION ---
def get_ai_policy_decision(prompt):
    try:
        print("⚡ Trying Gemini...")
        response = completion(
            model="gemini/gemini-3-flash-preview",
            messages=[{"role": "user", "content": prompt}],
        )
        return response["choices"][0]["message"]["content"]

    except Exception as e:
        print(f"❌ Gemini failed: {e}")

    try:
        print("🧠 Falling back to Ollama...")
        response = ollama.chat(
            model="llama3:latest",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.message.content

    except Exception as e:
        print(f"❌ Ollama failed: {e}")
        raise RuntimeError("All LLM providers failed.")


# --- JSON EXTRACTION ---
def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    raise ValueError("No JSON found in response")


# --- SAFE JSON PARSER WITH RETRY ---
def safe_get_rules(prompt):
    for attempt in range(3):
        ai_logic = get_ai_policy_decision(prompt)

        print("\n--- RAW AI RESPONSE ---")
        print(ai_logic)
        print("------------------------\n")

        try:
            json_text = extract_json(ai_logic)
            return json.loads(json_text)

        except Exception as e:
            print(f"⚠️ JSON parse failed: {e}")
            print("🔁 Retrying...\n")

    raise ValueError("Failed to get valid JSON from AI")


# --- FILE SELECTION ---
def select_files():
    root = tk.Tk()
    root.attributes('-topmost', True)
    root.focus_force()
    root.withdraw()

    print("📄 Please select your PDF file...")
    pdf_path = Path(filedialog.askopenfilename(
        title="Select PDF File",
        filetypes=[("PDF Files", "*.pdf")],
        parent=root
    ))

    print("📂 Please select your Excel file...")
    excel_path = Path(filedialog.askopenfilename(
        title="Select Excel File",
        filetypes=[("Excel Files", "*.xlsx *.xls")],
        parent=root
    ))

    root.destroy()

    if not pdf_path or str(pdf_path) == "." or not excel_path or str(excel_path) == ".":
        raise ValueError("❌ No file selected. Please select both files.")

    print(f"✅ PDF:   {pdf_path}")
    print(f"✅ Excel: {excel_path}")

    return pdf_path, excel_path


# --- MAIN AUDIT FUNCTION ---
def local_ai_audit(pdf_path, excel_path):
    print("--- 🧠 STEP 1: AI ANALYZING POLICY ---")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            policy_text = pdf.pages[0].extract_text()
    except Exception as e:
        print(f"❌ Could not read PDF: {e}")
        return

    prompt = f"""
    Analyze this banking policy: '{policy_text[:1500]}'

    Return ONLY a JSON object.

    Do NOT include:
    - explanations
    - markdown
    - backticks
    - extra text

    Format:

    {{
      "require_id": true/false,
      "require_ssn": true/false,
      "require_sanctions": true/false
    }}
    """

    print("Requesting interpretation from LLM chain...")

    try:
        rules = safe_get_rules(prompt)
    except Exception as e:
        print(f"❌ AI processing failed: {e}")
        return

    print(f"✅ Parsed Rules: {rules}")

    print("\n--- 📊 STEP 2: RUNNING CROSS-DOCUMENT AUDIT ---")

    df = pd.read_excel(excel_path)

    def check_compliance(row):
        violations = []

        if rules.get("require_id") and str(row['ID_Verified']).upper() == 'NO':
            violations.append("Missing ID")

        if rules.get("require_ssn") and str(row['SSN_Collected']).upper() == 'NO':
            violations.append("Missing SSN")

        if rules.get("require_sanctions") and str(row['Sanctions_Screened']).upper() != 'PASSED':
            violations.append(f"Sanctions Issue: {row['Sanctions_Screened']}")

        return ", ".join(violations) if violations else "Compliant"

    df['Audit_Result'] = df.apply(check_compliance, axis=1)

    print("\n--- 🚨 AUDIT EXCEPTIONS FOUND ---")

    exceptions = df[df['Audit_Result'] != "Compliant"]

    if not exceptions.empty:
        print(exceptions[['Customer_Name', 'Audit_Result']])
        output_path = script_dir / "Audit_Exceptions_Report.xlsx"
        exceptions.to_excel(output_path, index=False)
        print(f"\n✅ Exceptions saved to '{output_path}'")
    else:
        print("🎉 No exceptions found. All accounts meet the AI-interpreted policy.")


# --- ENTRY POINT ---
def main():
    pdf_path, excel_path = select_files()
    local_ai_audit(pdf_path, excel_path)


if __name__ == "__main__":
    main()