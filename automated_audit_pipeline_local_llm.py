import pandas as pd
import pdfplumber
import ollama
from pathlib import Path

# --- FILE PATHS (Dynamic - relative to script location) ---
script_dir = Path(__file__).parent
data_dir = script_dir / 'data'

excel_path = data_dir / 'sample.xlsx'
pdf_path = data_dir / 'sample.pdf'

def local_ai_audit():
    print("--- 🧠 STEP 1: LOCAL AI ANALYZING POLICY ---")
    
    # 1. Read the PDF content
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Extract text from the first page for the AI to "read"
            policy_text = pdf.pages[0].extract_text()
    except Exception as e:
        print(f"❌ Could not read PDF: {e}")
        return

    # 2. Use Llama 3 to interpret the policy
    # We ask the AI to be very specific so we can use its answer in our code
    prompt = f"""
    Analyze this banking policy: '{policy_text[:1500]}'
    Based ONLY on the text above, are the following 3 items MANDATORY for a new account?
    1. Government ID
    2. SSN/Tax ID
    3. Sanctions Screening
    
    Respond strictly in this format:
    ID: [Yes/No], SSN: [Yes/No], Sanctions: [Yes/No]
    """

    print("Requesting interpretation from Llama 3...")
    response = ollama.chat(model='llama3:latest', messages=[
        {'role': 'user', 'content': prompt},
    ])
    
    # In 2026, we access content directly via .message.content
    ai_logic = response.message.content
    print(f"AI Decision: {ai_logic.strip()}")

    # 3. Convert AI text into variables our script can use
    rules = {
        "require_id": "ID: Yes" in ai_logic,
        "require_ssn": "SSN: Yes" in ai_logic,
        "require_sanctions": "Sanctions: Yes" in ai_logic
    }

    # --- STEP 2: AUDIT THE EXCEL DATA ---
    print("\n--- 📊 STEP 2: RUNNING CROSS-DOCUMENT AUDIT ---")
    df = pd.read_excel(excel_path)
    
    def check_compliance(row):
        violations = []
        if rules["require_id"] and str(row['ID_Verified']).upper() == 'NO':
            violations.append("Missing ID")
        if rules["require_ssn"] and str(row['SSN_Collected']).upper() == 'NO':
            violations.append("Missing SSN")
        if rules["require_sanctions"] and str(row['Sanctions_Screened']).upper() != 'PASSED':
            violations.append(f"Sanctions Issue: {row['Sanctions_Screened']}")
        
        return ", ".join(violations) if violations else "Compliant"

    df['Audit_Result'] = df.apply(check_compliance, axis=1)

    # --- STEP 3: FINAL REPORT ---
    print("\n--- 🚨 AUDIT EXCEPTIONS FOUND ---")
    exceptions = df[df['Audit_Result'] != "Compliant"]
    
    if not exceptions.empty:
        print(exceptions[['Customer_Name', 'Audit_Result']])
        # Optional: Save to a new file
        exceptions.to_excel("Audit_Exceptions_Report.xlsx", index=False)
        print("\n✅ Exceptions saved to 'Audit_Exceptions_Report.xlsx'")
    else:
        print("🎉 No exceptions found. All accounts meet the AI-interpreted policy.")

if __name__ == "__main__":
    local_ai_audit()