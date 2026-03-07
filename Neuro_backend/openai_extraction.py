#!/usr/bin/env python3
import os, sys, json, re
from pathlib import Path
import pandas as pd
from typing import Optional
from datetime import datetime

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, skip
    pass

# --- OpenAI client setup with support for free alternatives ---
from openai import OpenAI

# Get API configuration from environment variables
API_PROVIDER = os.getenv("API_PROVIDER", "openai").lower()  # openai, deepseek, or custom
API_KEY = os.getenv("API_KEY", "")
API_BASE_URL = os.getenv("API_BASE_URL", "")  # For DeepSeek or custom endpoints

# Initialize client based on provider (only if API_KEY is provided)
client = None
if API_KEY:
    if API_PROVIDER == "deepseek":
        # DeepSeek API endpoint
        base_url = API_BASE_URL or "https://api.deepseek.com/v1"
        client = OpenAI(api_key=API_KEY, base_url=base_url)
    elif API_PROVIDER == "openai":
        # Standard OpenAI (including free tier if using custom endpoint)
        base_url = API_BASE_URL or "https://api.openai.com/v1"
        if base_url and base_url != "https://api.openai.com/v1":
            client = OpenAI(api_key=API_KEY, base_url=base_url)
        else:
            client = OpenAI(api_key=API_KEY)
    else:
        # Custom provider - use provided base URL
        if API_BASE_URL:
            client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
        else:
            raise ValueError(f"API_BASE_URL is required for custom provider '{API_PROVIDER}'")

# Default model - can be overridden via environment variable
DEFAULT_MODEL = os.getenv("API_MODEL", "gpt-4o-mini")

# =========================
# Prompt: Extract medical form data
# =========================
PROMPT_INSTRUCTIONS = r"""
You are given OCR text from a medical/orthoptic care form document. The text may contain HTML tables, markdown, or plain text.

Extract structured data and return STRICT JSON **only** matching this exact schema:
{
  "form_date": "YYYY-MM-DD or null",
  "patient": {
    "last_name": null,
    "first_name": null,
    "nir": null,
    "birth_date": "YYYY-MM-DD or null"
  },
  "doctor": {
    "full_name": null,
    "rpps": null
  },
  "orthoptic_care": {
    "description": null,
    "acts_prescribed": []
  },
  "ocr_raw_text": null
}

Extraction rules (MANDATORY):

A) Date Format
- Extract form_date from "Date :" fields. Convert DD/MM/YYYY to YYYY-MM-DD format
- Extract birth_date from "Date de naissance" fields. Convert DD/MM/YYYY to YYYY-MM-DD format
- Example: "11/10/2025" becomes "2025-10-11", "01/03/1985" becomes "1985-03-01"
- If date format is unclear or incomplete, use null

B) Patient Information
- Extract last_name from "Nom :" or "Last Name" fields (often in HTML tables)
- Extract first_name from "Prénom :" or "First Name" fields (often in HTML tables)
- Extract nir from "N° Sécurité Sociale (NIR) :" or "NIR" fields
- Extract birth_date from "Date de naissance :" or "Birth Date" fields
- Look for HTML table structures like <table><tr><td>Nom :</td><td>DUPONT</td></tr></table>
- If information is not found, use null (not empty string)

C) Doctor Information
- Extract full_name from "Dr. :" or "Docteur :" or "Doctor :" fields
- Extract rpps from "RPPS :" fields
- Look for patterns like "Dr. : Pierre MARTIN" or "RPPS : 10001234567"
- If information is not found, use null

D) Orthoptic Care
- Extract acts_prescribed as an array of act codes (e.g., ["AMY 7", "AMY 15"])
- Look for lines starting with "- AMY" or similar act codes
- Extract description if there's a general description of the care
- If no acts are found, use empty array []

E) OCR Raw Text
- Include the original OCR text in ocr_raw_text field
- This helps with verification and debugging

F) Output
- Output JSON ONLY. No prose, no code fences, no markdown.
- All fields must be present in the output, even if null
- Use null for missing values, not empty strings (except for acts_prescribed which is an array)
- Convert dates from DD/MM/YYYY to YYYY-MM-DD format
"""

# =========================
# Schema for medical form extraction
# =========================
EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["form_date", "patient", "doctor", "orthoptic_care", "ocr_raw_text"],
    "properties": {
        "form_date": {
            "type": ["string", "null"],
            "pattern": "^(\\d{4}-\\d{2}-\\d{2}|null)$"
        },
        "patient": {
            "type": "object",
            "additionalProperties": False,
            "required": ["last_name", "first_name", "nir", "birth_date"],
            "properties": {
                "last_name": {"type": ["string", "null"]},
                "first_name": {"type": ["string", "null"]},
                "nir": {"type": ["string", "null"]},
                "birth_date": {
                    "type": ["string", "null"],
                    "pattern": "^(\\d{4}-\\d{2}-\\d{2}|null)$"
                }
            }
        },
        "doctor": {
            "type": "object",
            "additionalProperties": False,
            "required": ["full_name", "rpps"],
            "properties": {
                "full_name": {"type": ["string", "null"]},
                "rpps": {"type": ["string", "null"]}
            }
        },
        "orthoptic_care": {
            "type": "object",
            "additionalProperties": False,
            "required": ["description", "acts_prescribed"],
            "properties": {
                "description": {"type": ["string", "null"]},
                "acts_prescribed": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        },
        "ocr_raw_text": {"type": ["string", "null"]}
    }
}

# =========================
# Date conversion helpers
# =========================
def convert_date_format(date_str: Optional[str]) -> Optional[str]:
    """
    Convert date from DD/MM/YYYY to YYYY-MM-DD format.
    Returns None if date_str is None, empty, or invalid.
    """
    if not date_str or date_str.lower() in ['null', 'none', '']:
        return None
    
    # If already in YYYY-MM-DD format, return as is
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    
    # Try to parse DD/MM/YYYY format
    try:
        # Try DD/MM/YYYY format
        date_obj = datetime.strptime(date_str.strip(), '%d/%m/%Y')
        return date_obj.strftime('%Y-%m-%d')
    except ValueError:
        try:
            # Try YYYY-MM-DD format (already correct)
            date_obj = datetime.strptime(date_str.strip(), '%Y-%m-%d')
            return date_str.strip()
        except ValueError:
            # If parsing fails, return None
            print(f"Warning: Could not parse date format: {date_str}")
            return None

# =========================
# OpenAI helpers
# =========================
def _responses_extract(md_text: str, model: str) -> dict:
    """Try using Responses API with structured output"""
    try:
        # Note: Responses API may not support response_format parameter
        # Try without it first, or skip Responses API entirely
        if not hasattr(client, 'responses'):
            raise AttributeError("Responses API not available")
        
        # Try Responses API without response_format (it may not support it)
        resp = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": "You extract structured data from OCR text and return strict JSON only."},
                {"role": "user", "content": PROMPT_INSTRUCTIONS + "\n\nOCR TEXT:\n" + md_text},
            ],
            temperature=0,
        )
        print("resp=====>", resp)
        parsed = json.loads(resp.output_text.strip())
        
        # Convert dates to proper format
        form_date = parsed.get("form_date")
        birth_date = parsed.get("patient", {}).get("birth_date")
        
        result = {
            "form_date": convert_date_format(form_date),
            "patient": {
                "last_name": parsed.get("patient", {}).get("last_name"),
                "first_name": parsed.get("patient", {}).get("first_name"),
                "nir": parsed.get("patient", {}).get("nir"),
                "birth_date": convert_date_format(birth_date)
            },
            "doctor": {
                "full_name": parsed.get("doctor", {}).get("full_name"),
                "rpps": parsed.get("doctor", {}).get("rpps")
            },
            "orthoptic_care": {
                "description": parsed.get("orthoptic_care", {}).get("description"),
                "acts_prescribed": parsed.get("orthoptic_care", {}).get("acts_prescribed", [])
            },
            "ocr_raw_text": md_text if md_text else None
        }
        
        return result
    except AttributeError:
        # Responses API not available, fall back to chat
        raise Exception("Responses API not available")
    except Exception as e:
        print(f"Responses API error: {e}")
        raise

def _chat_fallback_extract(md_text: str, model: str) -> dict:
    """Fallback to chat completions with JSON mode"""
    try:
        print(f"Attempting chat completion with model: {model}")
        chat = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You extract structured data from OCR text and return strict JSON only. Follow the schema exactly."},
                {"role": "user", "content": PROMPT_INSTRUCTIONS + "\n\nOCR TEXT:\n" + md_text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = chat.choices[0].message.content.strip()
        print(f"Chat completion response received, length: {len(content)}")
        
        # Remove markdown code fences if present
        if content.startswith("```"):
            content = re.sub(r"^```(json)?", "", content).strip()
            content = re.sub(r"```$", "", content).strip()
        
        parsed = json.loads(content)
        print(f"Parsed JSON successfully. Keys: {list(parsed.keys())}")
        
        # Ensure all required fields are present and match schema
        # Convert dates to proper format
        form_date = parsed.get("form_date")
        birth_date = parsed.get("patient", {}).get("birth_date")
        
        result = {
            "form_date": convert_date_format(form_date),
            "patient": {
                "last_name": parsed.get("patient", {}).get("last_name"),
                "first_name": parsed.get("patient", {}).get("first_name"),
                "nir": parsed.get("patient", {}).get("nir"),
                "birth_date": convert_date_format(birth_date)
            },
            "doctor": {
                "full_name": parsed.get("doctor", {}).get("full_name"),
                "rpps": parsed.get("doctor", {}).get("rpps")
            },
            "orthoptic_care": {
                "description": parsed.get("orthoptic_care", {}).get("description"),
                "acts_prescribed": parsed.get("orthoptic_care", {}).get("acts_prescribed", [])
            },
            "ocr_raw_text": md_text if md_text else None  # Store full OCR text
        }
        
        return result
    except Exception as e:
        print(f"Chat fallback error: {type(e).__name__}: {e}")
        raise

def call_openai_extract(md_text: str, model: Optional[str] = None) -> dict:
    """Extract structured data from OCR text using OpenAI-compatible API"""
    if model is None:
        model = DEFAULT_MODEL
    
    # Check if client is initialized
    if client is None:
        print(f"ERROR: API_KEY is not configured. Please set API_KEY environment variable.")
        print(f"API_KEY configured: {bool(API_KEY)}")
        print(f"API_PROVIDER: {API_PROVIDER}")
        print(f"API_BASE_URL: {API_BASE_URL or 'Not set (using default)'}")
        return {
            "form_date": None,
            "patient": {
                "last_name": None,
                "first_name": None,
                "nir": None,
                "birth_date": None
            },
            "doctor": {
                "full_name": None,
                "rpps": None
            },
            "orthoptic_care": {
                "description": None,
                "acts_prescribed": []
            },
            "ocr_raw_text": md_text if md_text else None
        }
    
    print(f"Starting extraction with model: {model}, API provider: {API_PROVIDER}")
    print(f"OCR text length: {len(md_text) if md_text else 0} characters")
    
    # Skip Responses API and go directly to chat completions (more reliable)
    try:
        print("Using chat completions API...")
        return _chat_fallback_extract(md_text, model)
    except Exception as e:
        # If chat completions fails, try Responses API as fallback
        try:
            print("Chat completions failed, trying Responses API...")
            return _responses_extract(md_text, model)
        except Exception as e2:
            # If all else fails, return schema-compliant empty structure
            print(f"Both extraction methods failed. Last error: {type(e2).__name__}: {e2}")
            print(f"API_KEY configured: {bool(API_KEY)}")
            print(f"API_BASE_URL: {API_BASE_URL or 'Not set (using default)'}")
            return {
                "form_date": None,
                "patient": {
                    "last_name": None,
                    "first_name": None,
                    "nir": None,
                    "birth_date": None
                },
                "doctor": {
                    "full_name": None,
                    "rpps": None
                },
                "orthoptic_care": {
                    "description": None,
                    "acts_prescribed": []
                },
                "ocr_raw_text": md_text if md_text else None
            }

# =========================
# Course helpers (kept for compatibility, but simplified)
# =========================
def load_course_reference(path: Path) -> dict:
    """Load the sample schema JSON file"""
    return json.loads(path.read_text(encoding="utf-8"))

# =========================
# DataFrame builder for medical form data
# =========================
def build_dataframe_from_extract(extract: dict) -> pd.DataFrame:
    """
    Build a simple DataFrame from the extracted medical form data.
    Returns a 2D list representation suitable for the API.
    """
    rows = []
    
    # Header row
    rows.append(["Field", "Value"])
    
    # Form date
    rows.append(["Form Date", extract.get("form_date") or ""])
    
    # Patient information
    patient = extract.get("patient", {})
    rows.append(["Patient - Last Name", patient.get("last_name") or ""])
    rows.append(["Patient - First Name", patient.get("first_name") or ""])
    rows.append(["Patient - NIR", patient.get("nir") or ""])
    rows.append(["Patient - Birth Date", patient.get("birth_date") or ""])
    
    # Doctor information
    doctor = extract.get("doctor", {})
    rows.append(["Doctor - Full Name", doctor.get("full_name") or ""])
    rows.append(["Doctor - RPPS", doctor.get("rpps") or ""])
    
    # Orthoptic care
    orthoptic = extract.get("orthoptic_care", {})
    rows.append(["Orthoptic Care - Description", orthoptic.get("description") or ""])
    acts = orthoptic.get("acts_prescribed", [])
    if acts:
        for i, act in enumerate(acts, 1):
            rows.append([f"Act {i}", act])
    else:
        rows.append(["Acts Prescribed", "None"])
    
    return pd.DataFrame(rows)


def build_eleven_row_dataframe(course: dict, extraction: dict) -> pd.DataFrame:
    """
    Compatibility function - now builds medical form DataFrame
    """
    return build_dataframe_from_extract(extraction)

# =========================
# Excel writer (kept for compatibility)
# =========================
def write_excel(df: pd.DataFrame, out_path: Path):
    out_path = Path(out_path)
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, header=False, sheet_name="Extracted Data")
        wb = writer.book
        ws = writer.sheets["Extracted Data"]

        header_fmt = wb.add_format({"bold": True, "align": "left", "valign": "vcenter", "border": 1})
        cell_fmt = wb.add_format({"align": "left", "valign": "vcenter", "border": 1})
        label_fmt = wb.add_format({"bold": True, "align": "right", "valign": "vcenter", "border": 1})

        nrows, ncols = df.shape
        ws.set_column(0, 0, 30)
        ws.set_column(1, ncols - 1, 40)

        for r in range(nrows):
            for c in range(ncols):
                v = df.iat[r, c]
                fmt = cell_fmt
                if c == 0:
                    fmt = label_fmt
                if r == 0:  # Header row
                    fmt = header_fmt
                ws.write(r, c, v, fmt)

# =========================
# CLI
# =========================
def main():
    if len(sys.argv) < 4:
        print("Usage: python build_scorecard.py <input.md> <sample_schema.json> <output.xlsx>")
        sys.exit(1)

    in_md = Path(sys.argv[1])
    schema_json = Path(sys.argv[2])
    out_xlsx = Path(sys.argv[3])

    md_text = in_md.read_text(encoding="utf-8", errors="ignore")
    schema = load_course_reference(schema_json)
    extract = call_openai_extract(md_text)
    print("extract=====>", json.dumps(extract, indent=2, ensure_ascii=False))

    # Build DataFrame from extraction
    df = build_dataframe_from_extract(extract)
    write_excel(df, out_xlsx)
    print(f"Wrote {out_xlsx}")

if __name__ == "__main__":
    main()
