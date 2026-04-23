"""
Test different PaddleOCR input methods to find a workaround for OneDNN/PIR error
"""

import os
import cv2
import numpy as np
from PIL import Image
import traceback

# Disable OneDNN before importing PaddleOCR
os.environ['FLAGS_use_mkldnn'] = 'False'
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_enable_pir_in_executor'] = '0'
os.environ['CUDA_VISIBLE_DEVICES'] = ''

from paddleocr import PaddleOCR

# Test frame path
test_frame = r"d:\Projects\neuro\Neuro_backend\video_analysis\frames\frame_0001_t0s.png"

if not os.path.exists(test_frame):
    print(f"❌ Test frame not found: {test_frame}")
    print("Please run analyze_video.py first to extract at least one frame")
    exit(1)

print("="*80)
print("PADDLEOCR WORKAROUND TESTS")
print("="*80)
print(f"Test frame: {test_frame}\n")

# Initialize PaddleOCR
print("Initializing PaddleOCR...")
ocr = PaddleOCR(lang='fr', use_textline_orientation=True)
print("✅ Initialized\n")

# Test 1: File path (string)
print("\n" + "="*80)
print("TEST 1: File path (string)")
print("="*80)
try:
    result = ocr.predict(test_frame, return_word_box=True)
    print("✅ SUCCESS - File path works!")
    print(f"   Result type: {type(result)}")
    print(f"   Result length: {len(result) if result else 0}")
except Exception as e:
    print(f"❌ FAILED - {type(e).__name__}: {str(e)[:100]}")
    if "ConvertPirAttribute" in str(e):
        print("   🔴 OneDNN/PIR error detected")

# Test 2: OpenCV BGR numpy array
print("\n" + "="*80)
print("TEST 2: OpenCV BGR numpy array")
print("="*80)
try:
    img_bgr = cv2.imread(test_frame)
    print(f"   Array shape: {img_bgr.shape}, dtype: {img_bgr.dtype}")
    result = ocr.predict(img_bgr, return_word_box=True)
    print("✅ SUCCESS - BGR numpy array works!")
    print(f"   Result type: {type(result)}")
    print(f"   Result length: {len(result) if result else 0}")
except Exception as e:
    print(f"❌ FAILED - {type(e).__name__}: {str(e)[:100]}")
    if "ConvertPirAttribute" in str(e):
        print("   🔴 OneDNN/PIR error detected")

# Test 3: OpenCV RGB numpy array
print("\n" + "="*80)
print("TEST 3: OpenCV RGB numpy array (BGR->RGB conversion)")
print("="*80)
try:
    img_bgr = cv2.imread(test_frame)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    print(f"   Array shape: {img_rgb.shape}, dtype: {img_rgb.dtype}")
    result = ocr.predict(img_rgb, return_word_box=True)
    print("✅ SUCCESS - RGB numpy array works!")
    print(f"   Result type: {type(result)}")
    print(f"   Result length: {len(result) if result else 0}")
except Exception as e:
    print(f"❌ FAILED - {type(e).__name__}: {str(e)[:100]}")
    if "ConvertPirAttribute" in str(e):
        print("   🔴 OneDNN/PIR error detected")

# Test 4: PIL Image
print("\n" + "="*80)
print("TEST 4: PIL Image object")
print("="*80)
try:
    img_pil = Image.open(test_frame)
    print(f"   PIL size: {img_pil.size}, mode: {img_pil.mode}")
    result = ocr.predict(img_pil, return_word_box=True)
    print("✅ SUCCESS - PIL Image works!")
    print(f"   Result type: {type(result)}")
    print(f"   Result length: {len(result) if result else 0}")
except Exception as e:
    print(f"❌ FAILED - {type(e).__name__}: {str(e)[:100]}")
    if "ConvertPirAttribute" in str(e):
        print("   🔴 OneDNN/PIR error detected")

# Test 5: PIL Image converted to numpy
print("\n" + "="*80)
print("TEST 5: PIL Image -> numpy array")
print("="*80)
try:
    img_pil = Image.open(test_frame)
    img_np = np.array(img_pil)
    print(f"   Array shape: {img_np.shape}, dtype: {img_np.dtype}")
    result = ocr.predict(img_np, return_word_box=True)
    print("✅ SUCCESS - PIL->numpy works!")
    print(f"   Result type: {type(result)}")
    print(f"   Result length: {len(result) if result else 0}")
except Exception as e:
    print(f"❌ FAILED - {type(e).__name__}: {str(e)[:100]}")
    if "ConvertPirAttribute" in str(e):
        print("   🔴 OneDNN/PIR error detected")

# Test 6: uint8 numpy array (ensure correct dtype)
print("\n" + "="*80)
print("TEST 6: Explicit uint8 numpy array")
print("="*80)
try:
    img_bgr = cv2.imread(test_frame)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_uint8 = img_rgb.astype(np.uint8)  # Explicitly ensure uint8
    print(f"   Array shape: {img_uint8.shape}, dtype: {img_uint8.dtype}")
    print(f"   Value range: [{img_uint8.min()}, {img_uint8.max()}]")
    result = ocr.predict(img_uint8, return_word_box=True)
    print("✅ SUCCESS - Explicit uint8 works!")
    print(f"   Result type: {type(result)}")
    print(f"   Result length: {len(result) if result else 0}")
except Exception as e:
    print(f"❌ FAILED - {type(e).__name__}: {str(e)[:100]}")
    if "ConvertPirAttribute" in str(e):
        print("   🔴 OneDNN/PIR error detected")

print("\n" + "="*80)
print("TESTS COMPLETE")
print("="*80)
print("\n✅ If any test succeeded, use that method in analyze_video.py")
print("❌ If all tests failed, this is a PaddlePaddle internal bug to report")
print("\nReport to: https://github.com/PaddlePaddle/PaddleOCR/issues")
