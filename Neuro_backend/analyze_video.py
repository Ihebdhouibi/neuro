"""
Video Frame Extraction and Analysis Tool
Extracts frames from FSE demo video and performs OCR analysis
"""

import cv2
import os
import sys
import traceback
from datetime import datetime
import json

# NOTE: The working paddle_ocr_engine.py does NOT need the MKLDNN workaround
# because it explicitly uses mobile models (PP-OCRv5_mobile_det/rec).
# We keep the workaround as a safety net in case default models trigger OneDNN bug.
os.environ['PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT'] = 'False'

print("="*80)
print("STARTING VIDEO ANALYSIS")
print("="*80)
print("🔧 Using same initialization as working paddle_ocr_engine.py")
print("   Models: PP-OCRv5_mobile_det + PP-OCRv5_mobile_rec")
print("="*80 + "\n")

from paddleocr import PaddleOCR

# Log versions
try:
    import paddle
    print(f"PaddlePaddle version: {paddle.__version__}")
except:
    print("Could not determine PaddlePaddle version")

try:
    import paddleocr
    print(f"PaddleOCR version: {paddleocr.__version__ if hasattr(paddleocr, '__version__') else 'unknown'}")
except:
    print("Could not determine PaddleOCR version")

print("="*80 + "\n")

# Configuration
VIDEO_PATH = r"D:\Projects\neuro\20250930_073650.mp4"
OUTPUT_DIR = r"d:\Projects\neuro\Neuro_backend\video_analysis"
FRAMES_DIR = os.path.join(OUTPUT_DIR, "frames")
LOG_FILE = os.path.join(OUTPUT_DIR, "analysis_log.txt")
JSON_LOG = os.path.join(OUTPUT_DIR, "analysis_data.json")
INTERVAL_SECONDS = 3  # Extract frame every 3 seconds

# Create output directories
os.makedirs(FRAMES_DIR, exist_ok=True)

# Initialize PaddleOCR
print("Initializing PaddleOCR...")
print("="*80)
print("PaddleOCR Configuration: Matching paddle_ocr_engine.py settings")
print("="*80)

try:
    ocr = PaddleOCR(
        lang='fr',
        # Match working paddle_ocr_engine.py initialization
        text_detection_model_name='PP-OCRv5_mobile_det',
        text_recognition_model_name='PP-OCRv5_mobile_rec',
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True,
        text_det_thresh=0.3,
        text_det_box_thresh=0.50,
        text_det_unclip_ratio=1.5,
        text_det_limit_side_len=960,
        text_det_limit_type='max',
        text_recognition_batch_size=16,
    )
    print("✅ PaddleOCR initialized successfully!")
    print("="*80 + "\n")
except Exception as init_error:
    print("="*80)
    print("❌ FATAL: PaddleOCR initialization failed!")
    print("="*80)
    print(f"Error: {init_error}")
    print("\nFull traceback:")
    traceback.print_exc()
    print("="*80)
    sys.exit(1)

# Open log file
log_file = open(LOG_FILE, 'w', encoding='utf-8')
log_file.write(f"FSE Video Analysis Log\n")
log_file.write(f"Video: {VIDEO_PATH}\n")
log_file.write(f"Analysis started: {datetime.now()}\n")
log_file.write("="*80 + "\n\n")

# Storage for all frame data
all_frames_data = []

def log(message):
    """Write to both console and log file"""
    print(message)
    log_file.write(message + "\n")
    log_file.flush()

def extract_and_analyze_frames():
    """Extract frames from video and analyze each one"""
    
    # Open video
    video = cv2.VideoCapture(VIDEO_PATH)
    
    if not video.isOpened():
        log(f"ERROR: Could not open video file: {VIDEO_PATH}")
        return
    
    # Get video properties
    fps = video.get(cv2.CAP_PROP_FPS)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    
    log(f"Video Properties:")
    log(f"  FPS: {fps}")
    log(f"  Total Frames: {total_frames}")
    log(f"  Duration: {duration:.2f} seconds")
    log(f"  Frame interval: {INTERVAL_SECONDS} seconds")
    log(f"  Expected frames to extract: {int(duration / INTERVAL_SECONDS)}")
    log("\n" + "="*80 + "\n")
    
    frame_interval = int(fps * INTERVAL_SECONDS)
    frame_count = 0
    saved_count = 0
    
    while True:
        ret, frame = video.read()
        
        if not ret:
            break
        
        # Extract frame at intervals
        if frame_count % frame_interval == 0:
            saved_count += 1
            timestamp = frame_count / fps
            
            # Convert BGR to RGB (OpenCV uses BGR, PaddleOCR expects RGB)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Save frame (for visual inspection)
            frame_filename = f"frame_{saved_count:04d}_t{int(timestamp)}s.png"
            frame_path = os.path.join(FRAMES_DIR, frame_filename)
            cv2.imwrite(frame_path, frame)  # Save original BGR for file
            
            log(f"\n{'='*80}")
            log(f"FRAME {saved_count} - Timestamp: {int(timestamp)}s ({timestamp/60:.1f}min)")
            log(f"{'='*80}")
            log(f"Saved: {frame_filename}")
            log(f"Frame shape: {frame_rgb.shape}")
            log(f"Frame dtype: {frame_rgb.dtype}")
            log(f"Frame value range: [{frame_rgb.min()}, {frame_rgb.max()}]")
            
            # Perform OCR on saved image file (more stable than numpy array)
            log("\n🔍 Performing OCR...")
            log(f"  - Input: File path (safer than numpy array)")
            log(f"  - File: {frame_path}")
            log(f"  - Calling ocr.predict()...")
            
            try:
                log("  - [TRACE] Before ocr.predict() call")
                # Use file path instead of numpy array - more stable
                result = ocr.predict(frame_path)
                log("  - [TRACE] After ocr.predict() call - SUCCESS")
                log(f"  - [TRACE] Result type: {type(result)}")
                log(f"  - [TRACE] Result length: {len(result) if result else 0}")
                
                # Parse PaddleOCR 3.x result format
                texts = []
                confidences = []
                boxes = []
                
                if result and len(result) > 0:
                    for r in result:
                        # Check if result has the new format with .json attribute
                        if hasattr(r, 'json') and r.json:
                            res_dict = r.json.get("res", {})
                            
                            # Extract line-level data
                            line_texts = res_dict.get("rec_texts", [])
                            line_boxes = res_dict.get("dt_polys", [])
                            line_scores = res_dict.get("rec_scores", [])
                            
                            for i, text in enumerate(line_texts):
                                if i < len(line_boxes):
                                    texts.append(text)
                                    conf = line_scores[i] if i < len(line_scores) else 0.99
                                    confidences.append(float(conf))
                                    boxes.append(line_boxes[i])
                
                if texts:
                    log(f"\nExtracted Text ({len(texts)} text blocks):")
                    log("-" * 80)
                    
                    frame_data = {
                        "frame_number": saved_count,
                        "timestamp_seconds": int(timestamp),
                        "filename": frame_filename,
                        "ocr_results": []
                    }
                    
                    # Log extracted text
                    for idx, (text, confidence) in enumerate(zip(texts, confidences)):
                        frame_data["ocr_results"].append({
                            "text": text,
                            "confidence": round(confidence, 3)
                        })
                        
                        log(f"{idx+1:3d}. [{confidence:.3f}] {text}")
                    
                    # Try to identify key fields
                    log("\n" + "-" * 80)
                    log("FIELD DETECTION:")
                    log("-" * 80)
                    
                    detected_fields = identify_fields(texts)
                    frame_data["detected_fields"] = detected_fields
                    
                    for field, value in detected_fields.items():
                        log(f"  {field}: {value}")
                    
                    all_frames_data.append(frame_data)
                    
                else:
                    log("No text detected in this frame")
                    all_frames_data.append({
                        "frame_number": saved_count,
                        "timestamp_seconds": int(timestamp),
                        "filename": frame_filename,
                        "ocr_results": [],
                        "detected_fields": {}
                    })
                    
            except Exception as e:
                log("\n" + "="*80)
                log("❌ OCR ERROR DETECTED")
                log("="*80)
                log(f"Error type: {type(e).__name__}")
                log(f"Error message: {str(e)}")
                log("\n--- FULL PYTHON TRACEBACK ---")
                log(traceback.format_exc())
                log("="*80)
                
                # Additional debugging info
                log("\n--- DEBUGGING INFORMATION ---")
                log(f"Frame number: {saved_count}")
                log(f"Frame shape: {frame_rgb.shape}")
                log(f"Frame dtype: {frame_rgb.dtype}")
                log(f"Timestamp: {int(timestamp)}s")
                log(f"Saved frame path: {frame_path}")
                
                # Check if it's the specific OneDNN/PIR error
                error_str = str(e)
                if "ConvertPirAttribute2RuntimeAttribute" in error_str:
                    log("\n🔴 IDENTIFIED: OneDNN/PIR Conversion Error")
                    log("This is a known issue in PaddlePaddle's PIR compilation with OneDNN backend")
                    log("\nPossible causes:")
                    log("  1. PIR (Program Intermediate Representation) incompatibility")
                    log("  2. OneDNN backend not fully supporting certain operations")
                    log("  3. PaddlePaddle version compatibility issue")
                    log("\nAttempted workarounds:")
                    log("  ✅ Set FLAGS_use_mkldnn=False")
                    log("  ✅ Set FLAGS_enable_pir_api=0")
                    log("  ✅ Set FLAGS_enable_pir_in_executor=0")
                    log("  ✅ Disabled GPU (use_gpu=False)")
                    log("  ✅ Converted image to RGB numpy array")
                    log("\n⚠️  ERROR PERSISTS - May be a PaddlePaddle internal bug")
                    log("\nRecommendation: Report to PaddlePaddle/PaddleOCR GitHub:")
                    log("  - https://github.com/PaddlePaddle/PaddleOCR/issues")
                    log("  - https://github.com/PaddlePaddle/Paddle/issues")
                
                log("="*80)
                
                all_frames_data.append({
                    "frame_number": saved_count,
                    "timestamp_seconds": int(timestamp),
                    "filename": frame_filename,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                })
        
        frame_count += 1
    
    video.release()
    
    log("\n" + "="*80)
    log(f"ANALYSIS COMPLETE")
    log("="*80)
    log(f"Total frames processed: {frame_count}")
    log(f"Frames extracted and analyzed: {saved_count}")
    log(f"Frames saved to: {FRAMES_DIR}")
    log(f"Analysis log: {LOG_FILE}")
    log(f"JSON data: {JSON_LOG}")
    
    # Save JSON data
    with open(JSON_LOG, 'w', encoding='utf-8') as f:
        json.dump({
            "video_path": VIDEO_PATH,
            "analysis_date": datetime.now().isoformat(),
            "total_frames_extracted": saved_count,
            "frames": all_frames_data
        }, f, indent=2, ensure_ascii=False)
    
    log("\nJSON data saved successfully")

def identify_fields(texts):
    """Try to identify key FSE fields from OCR results"""
    fields = {}
    
    # texts is now a simple list of strings
    if not texts:
        return fields
    
    # Combine all text
    all_text = " ".join(texts)
    all_text_lower = all_text.lower()
    
    # Look for specific patterns
    for text in texts:
        text_lower = text.lower()
        
        # Patient name (often appears early)
        if "test" in text_lower and "idem" in text_lower:
            fields["patient_name"] = text
        
        # IPP/NIR (contains numbers and pattern like "15035 > 27 03 99")
        if ">" in text and any(char.isdigit() for char in text):
            fields["nir_ipp"] = text
        
        # P.Code (likely 2-4 uppercase letters alone)
        if len(text) <= 6 and text.isupper() and text.isalpha():
            if "p_code_candidate" not in fields:
                fields["p_code_candidate"] = []
            fields["p_code_candidate"].append(text)
        
        # AMY codes
        if "amy" in text_lower:
            if "amy_codes" not in fields:
                fields["amy_codes"] = []
            fields["amy_codes"].append(text)
        
        # Dates (DD/MM/YYYY pattern)
        if "/" in text and any(char.isdigit() for char in text):
            if "dates" not in fields:
                fields["dates"] = []
            fields["dates"].append(text)
        
        # Numbers that could be FSE number (5-6 digits)
        if text.isdigit() and 5 <= len(text) <= 6:
            if "number_candidates" not in fields:
                fields["number_candidates"] = []
            fields["number_candidates"].append(text)
        
        # RPPS (11 digits)
        if text.isdigit() and len(text) == 11:
            fields["rpps_candidate"] = text
        
        # Buttons
        if "ajouter" in text_lower:
            fields["ajouter_button"] = "DETECTED"
        if "valider" in text_lower:
            fields["valider_button"] = "DETECTED"
    
    return fields

if __name__ == "__main__":
    try:
        log("Starting video analysis...\n")
        extract_and_analyze_frames()
        log("\n✅ Analysis completed successfully!")
        
    except Exception as e:
        log(f"\n❌ Error during analysis: {str(e)}")
        import traceback
        log(traceback.format_exc())
    
    finally:
        log_file.close()
        print(f"\n📁 Results saved to: {OUTPUT_DIR}")
        print(f"📄 Log file: {LOG_FILE}")
        print(f"📊 JSON data: {JSON_LOG}")
        print(f"🖼️  Frames: {FRAMES_DIR}")
