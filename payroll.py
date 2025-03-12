import streamlit as st
import pandas as pd
import numpy as np
import pytesseract
from PIL import Image
import pdf2image
import io
import os
import openai
import tempfile
import csv
from datetime import datetime
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set page config
st.set_page_config(
    page_title="AI Payroll Verification System",
    page_icon="💼",
    layout="wide"
)

# Initialize OpenAI API key from environment variable
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    st.error("OpenAI API key not found in environment variables. Please add OPENAI_API_KEY to your .env file.")
    st.stop()
else:
    # Set the API key for the session
    st.session_state.openai_api_key = openai_api_key

# Initialize session state variables if they don't exist
if 'payroll_data' not in st.session_state:
    st.session_state.payroll_data = None
if 'receipt_text' not in st.session_state:
    st.session_state.receipt_text = None
if 'verification_results' not in st.session_state:
    st.session_state.verification_results = None

# Function to extract text from images using Tesseract OCR
def extract_text_from_image(image):
    try:
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        st.error(f"Error extracting text from image: {e}")
        return None

# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(pdf_file.read())
            tmp_path = tmp.name
        
        images = pdf2image.convert_from_path(tmp_path)
        os.unlink(tmp_path)  # Remove the temporary file
        
        text = ""
        for image in images:
            text += extract_text_from_image(image) + "\n"
        
        return text
    except Exception as e:
        st.error(f"Error extracting text from PDF: {e}")
        return None

# Function to verify payroll data with OpenAI
def verify_with_openai(payroll_data, receipt_text):
    try:
        # Convert DataFrame to a string representation
        payroll_str = payroll_data.to_string()
        
        # Create a prompt for OpenAI
        prompt = f"""
        Analyze the following payroll data and receipt information to identify any discrepancies or anomalies.
        
        Payroll Data:
        {payroll_str}
        
        Receipt Text:
        {receipt_text}
        
        Please check for matches or discrepancies in:
        1. Employee names
        2. Salary amounts
        3. Payment dates
        4. Any other anomalies that might indicate fraud or errors
        
        For each discrepancy, indicate the severity (low, medium, high) and provide a brief explanation.
        Format the response as JSON with the following structure:
        {{
            "matches": [
                {{"item": "employee_name", "status": "match", "details": "John Doe appears in both payroll and receipt"}}
            ],
            "discrepancies": [
                {{"item": "salary_amount", "severity": "high", "details": "Salary in receipt ($5000) does not match payroll ($4500) for John Doe"}}
            ],
            "overall_assessment": "Brief summary of findings"
        }}
        """
        
        # Call OpenAI API
        client = openai.OpenAI(api_key=st.session_state.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a financial auditor specialized in payroll verification."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse the response
        verification_result = response.choices[0].message.content
        return verification_result
    except Exception as e:
        st.error(f"Error during OpenAI verification: {e}")
        return None

# App title and description
st.title("🔍 AI-Powered Payroll Verification System")
st.markdown("""
This system helps you verify payroll data against receipts using AI technology.
Upload your payroll Excel file and a receipt (image or PDF) to get started.
""")

# Sidebar with instructions
with st.sidebar:
    st.header("Instructions")
    st.markdown("""
    ### How to use:
    1. Upload a payroll Excel file
    2. Upload a receipt (image or PDF)
    3. Click 'Verify Payroll Data'
    4. Review the results
    5. Download the verification report
    """)

# Create two columns for file uploads
col1, col2 = st.columns(2)

# Payroll Excel upload
with col1:
    st.subheader("📊 Upload Payroll Data")
    payroll_file = st.file_uploader("Upload an Excel file containing payroll data", type=["xlsx", "xls"])
    
    if payroll_file is not None:
        try:
            payroll_data = pd.read_excel(payroll_file)
            st.session_state.payroll_data = payroll_data
            st.success("Payroll data loaded successfully!")
            
            # Display payroll data
            st.dataframe(payroll_data)
        except Exception as e:
            st.error(f"Error reading payroll file: {e}")

# Receipt upload
with col2:
    st.subheader("🧾 Upload Receipt")
    receipt_file = st.file_uploader("Upload an image or PDF of the receipt", type=["jpg", "jpeg", "png", "pdf"])
    
    if receipt_file is not None:
        try:
            # Check if it's a PDF or an image
            if receipt_file.type == "application/pdf":
                receipt_text = extract_text_from_pdf(receipt_file)
            else:
                image = Image.open(receipt_file)
                st.image(image, caption="Uploaded Receipt", use_column_width=True)
                receipt_text = extract_text_from_image(image)
            
            if receipt_text:
                st.session_state.receipt_text = receipt_text
                st.success("Receipt processed successfully!")
                
                # Display extracted text
                with st.expander("View Extracted Text"):
                    st.text(receipt_text)
            else:
                st.error("Failed to extract text from the receipt.")
        except Exception as e:
            st.error(f"Error processing receipt: {e}")

# Verification button
st.markdown("---")
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    verify_button = st.button("🔍 Verify Payroll Data", use_container_width=True, disabled=not (
        st.session_state.get('payroll_data') is not None and 
        st.session_state.get('receipt_text') is not None
    ))

# Process verification
if verify_button:
    with st.spinner("Verifying payroll data using AI..."):
        verification_json = verify_with_openai(
            st.session_state.payroll_data,
            st.session_state.receipt_text
        )
        
        if verification_json:
            st.session_state.verification_results = verification_json
            st.success("Verification completed!")

# Display verification results
if st.session_state.get('verification_results'):
    st.markdown("---")
    st.subheader("🔎 Verification Results")
    
    try:
        import json
        results = json.loads(st.session_state.verification_results)
        
        # Overall assessment
        st.info(f"**Overall Assessment**: {results.get('overall_assessment', 'No overall assessment provided')}")
        
        # Create tabs for matches and discrepancies
        tab1, tab2 = st.tabs(["✅ Matches", "❌ Discrepancies"])
        
        with tab1:
            if results.get('matches'):
                matches_df = pd.DataFrame(results['matches'])
                st.dataframe(matches_df)
            else:
                st.write("No matches found.")
        
        with tab2:
            if results.get('discrepancies'):
                discrepancies_df = pd.DataFrame(results['discrepancies'])
                
                # Apply styling based on severity
                def highlight_severity(s):
                    styles = []
                    for val in s:
                        if val == 'high':
                            styles.append('background-color: #ffcccc')
                        elif val == 'medium':
                            styles.append('background-color: #ffffcc')
                        else:
                            styles.append('background-color: #ccffcc')
                    return styles
                
                if 'severity' in discrepancies_df.columns:
                    styled_df = discrepancies_df.style.apply(
                        lambda x: highlight_severity(x) if x.name == 'severity' else [''] * len(x),
                        axis=0
                    )
                    st.dataframe(styled_df)
                else:
                    st.dataframe(discrepancies_df)
            else:
                st.write("No discrepancies found.")
        
        # Download button for verification report
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            # Prepare CSV data
            csv_data = io.StringIO()
            writer = csv.writer(csv_data)
            
            # Write headers
            writer.writerow(['Verification Report - Generated on ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow([])
            writer.writerow(['Overall Assessment'])
            writer.writerow([results.get('overall_assessment', 'No overall assessment provided')])
            writer.writerow([])
            
            # Write matches
            writer.writerow(['Matches'])
            if results.get('matches'):
                writer.writerow([key for key in results['matches'][0].keys()])
                for match in results['matches']:
                    writer.writerow([match.get(key, '') for key in results['matches'][0].keys()])
            else:
                writer.writerow(['No matches found'])
            writer.writerow([])
            
            # Write discrepancies
            writer.writerow(['Discrepancies'])
            if results.get('discrepancies'):
                writer.writerow([key for key in results['discrepancies'][0].keys()])
                for discrepancy in results['discrepancies']:
                    writer.writerow([discrepancy.get(key, '') for key in results['discrepancies'][0].keys()])
            else:
                writer.writerow(['No discrepancies found'])
            
            csv_data.seek(0)
            
            st.download_button(
                label="📊 Download Verification Report",
                data=csv_data,
                file_name=f"payroll_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    except Exception as e:
        st.error(f"Error displaying verification results: {e}")
        st.code(st.session_state.verification_results)

# # Footer
# st.markdown("---")
# st.markdown("### 📝 Notes")
# st.markdown("""
# - This system uses OpenAI's API to analyze payroll data against receipt information.
# - The AI checks for discrepancies in employee names, salary amounts, payment dates, and other anomalies.
# - For best results, ensure your payroll Excel file has clear column headers and your receipt is clearly readable.
# - All processing is done securely and no data is stored permanently.
# """)