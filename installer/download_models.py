"""Download PaddleOCR 3.2.0 models for offline bundling."""
import os
import sys

os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

# PADDLEX_HOME is set by the calling script
paddlex_home = os.environ.get('PADDLEX_HOME', '')
if not paddlex_home:
    print('ERROR: PADDLEX_HOME not set')
    sys.exit(1)

print(f'Downloading models to: {paddlex_home}')

from paddleocr import PaddleOCR
import numpy as np

ocr = PaddleOCR(
    use_textline_orientation=True,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    text_detection_model_name='PP-OCRv5_mobile_det',
    text_recognition_model_name='PP-OCRv5_mobile_rec',
)

# Run on a tiny dummy image to force model download + compilation
dummy = np.zeros((100, 300, 3), dtype=np.uint8)
dummy[20:80, 20:280] = 255
try:
    result = ocr.predict(dummy)
    print(f'Model download complete. PADDLEX_HOME={paddlex_home}')
except Exception as e:
    print(f'OCR test run note: {e}')
    print('Models should still be cached.')

print('Done')
