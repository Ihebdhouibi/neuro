"""
PaddleOCR Engine: Implementation of OCR engine using PaddleOCR.
"""
# CRITICAL: Import paths_config FIRST to override HOME before PaddleOCR import
try:
    from config.paths_config import setup_environment
    setup_environment()
except ImportError:
    pass  # paths_config might not be available in all contexts

import time
import os
import sys
import logging
import uuid
from typing import Dict, List, Any, Union, Optional, TYPE_CHECKING

from sympy import true

# Type hints only - no runtime import
if TYPE_CHECKING:
    import numpy as np
    from PIL import Image

# Lazy imports - only imported when needed
# numpy and PIL are expensive to import (~1-2s total)
_np = None
_Image = None


def _lazy_import_numpy():
    """Lazy import numpy only when needed."""
    global _np
    if _np is None:
        import numpy as np
        _np = np
    return _np


def _lazy_import_pil():
    """Lazy import PIL only when needed."""
    global _Image
    if _Image is None:
        from PIL import Image
        _Image = Image
    return _Image


def get_writable_logs_dir(module_name="Engine"):
    """Get a writable directory for logs, handling frozen executables"""
    if getattr(sys, 'frozen', False):
        # Running as frozen executable - use temp directory
        if os.environ.get('TEMP'):
            base_temp = os.environ['TEMP']
        else:
            base_temp = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Temp')
        logs_dir = os.path.join(base_temp, 'OCR-Engine-Logs', module_name)
    else:
        # Running as script - use logs directory next to the script
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    
    try:
        os.makedirs(logs_dir, exist_ok=True)
        return logs_dir
    except (PermissionError, OSError):
        # Fallback to temp if we can't create the preferred location
        fallback = os.path.join(os.path.expanduser('~'), '.ocr-engine-logs', module_name)
        os.makedirs(fallback, exist_ok=True)
        return fallback

try:
    # Try relative imports first (when used as part of a package)
    from .ocr_engine_interface import OCREngineInterface
except ImportError:
    # Fall back to direct imports when running standalone
    from ocr_engine_interface import OCREngineInterface

# LAZY IMPORT: Don't import PaddleOCR at module load time
# Instead, import it only when initialize() is called
# This saves ~8 seconds of import time if PaddleOCR is never used
PADDLE_AVAILABLE = None  # Unknown until first use
_PaddleOCR = None  # Cache the class once imported


def _lazy_import_paddleocr():
    """
    Lazy import PaddleOCR only when needed.
    This defers the expensive import until initialize() is called.
    
    Returns:
        tuple: (PaddleOCR_class, is_available)
    """
    global PADDLE_AVAILABLE, _PaddleOCR
    
    # Return cached import if already done
    if _PaddleOCR is not None:
        return _PaddleOCR, PADDLE_AVAILABLE
    
    # CRITICAL: Set HOME/USERPROFILE to installation dir BEFORE importing PaddleOCR
    # This prevents .paddleocr folder from being created in C:\Users\username\
    try:
        install_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Save original values
        if 'ORIGINAL_HOME' not in os.environ:
            os.environ['ORIGINAL_HOME'] = os.environ.get('HOME', os.environ.get('USERPROFILE', ''))
        if 'ORIGINAL_USERPROFILE' not in os.environ:
            os.environ['ORIGINAL_USERPROFILE'] = os.environ.get('USERPROFILE', '')
        
        # Override HOME and USERPROFILE to installation directory
        os.environ['HOME'] = install_dir
        os.environ['USERPROFILE'] = install_dir
        
        # Also set PPOCR_HOME explicitly
        paddleocr_home = os.path.join(install_dir, '.paddleocr')
        os.makedirs(paddleocr_home, exist_ok=True)
        os.environ['PPOCR_HOME'] = paddleocr_home
        
        logging.debug(f"Set HOME={install_dir} before PaddleOCR import")
        logging.debug(f"Set PPOCR_HOME={paddleocr_home}")
    except Exception as e:
        logging.warning(f"Could not override HOME/USERPROFILE: {e}")
    
    # Try to import PaddleOCR
    try:
        from paddleocr import PaddleOCR
        _PaddleOCR = PaddleOCR
        PADDLE_AVAILABLE = True
        return PaddleOCR, True
    except ImportError:
        PADDLE_AVAILABLE = False
        logging.warning("PaddleOCR not available. Please install with: pip install paddleocr")
        return None, False


class PaddleOCREngine(OCREngineInterface):
    """
    OCR engine implementation using PaddleOCR.
    """
    
    def __init__(self, mode: str = "develop", temp_dir: Optional[str] = None):
        """
        Initialize the PaddleOCR engine.
        
        Args:
            mode: Logging/debugging mode - 'production', 'develop', or 'debug'
            temp_dir: Optional temp directory for page images. If None, uses installation folder fallback.
        """
        self.engine = None
        self.config = {
            "lang": "fr",
            "return_word_box": True,
            "text_det_box_thresh": 0.5,
            "auto_rotate": True,
        }
        self.supported_languages = [
            'ch', 'en', 'fr', 'german', 'korean', 'japan', 'chinese_cht', 
            'ta', 'te', 'ka', 'latin', 'arabic'
        ]
        self.is_initialized = False
        
        # Configure temp directory for page images
        if temp_dir:
            self.temp_dir = temp_dir
        else:
            # Fallback to installation folder (old behavior)
            self.temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'temp')
        
        # Set up logging
        self._setup_logging(mode)
    
    def _setup_logging(self, mode: str) -> None:
        """
        Set up logging based on the mode.
        
        Args:
            mode: 'production', 'develop', or 'debug'
        """
        self.mode = mode
        
        # Configure logger for this module
        logger = logging.getLogger('PaddleOCR')
        
        # Set logging level based on mode
        if mode == "production":
            logger.setLevel(logging.CRITICAL)
            # In production mode, we don't create log files
            # Remove any existing handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
                
            # Add only console handler in production mode
            console_handler = logging.StreamHandler()
            console_format = logging.Formatter('%(levelname)s - %(message)s')
            console_handler.setFormatter(console_format)
            logger.addHandler(console_handler)
        else:
            # Create logs directory if it doesn't exist (only for non-production modes)
            logs_dir = get_writable_logs_dir("Engine")
            
            # Define log file path
            log_file = os.path.join(logs_dir, f"paddle_ocr_{mode}.log")
            
            # Set level based on mode
            if mode == "develop":
                logger.setLevel(logging.INFO)
            elif mode == "debug":
                logger.setLevel(logging.DEBUG)
            else:
                logger.setLevel(logging.WARNING)
                
            # Create handlers if they don't exist yet
            if not logger.handlers:
                # File handler
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                file_handler.setFormatter(file_format)
                logger.addHandler(file_handler)
                
                # Console handler
                console_handler = logging.StreamHandler()
                console_format = logging.Formatter('%(levelname)s - %(message)s')
                console_handler.setFormatter(console_format)
                logger.addHandler(console_handler)
        
        self.logger = logger
        if mode != "production":
            self.logger.info(f"PaddleOCR engine initialized in {mode} mode")
        
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the PaddleOCR engine with the provided configuration.
        
        Args:
            config: Dictionary containing engine-specific configuration.
        """
        # Lazy import PaddleOCR only when needed (saves ~8s at startup)
        PaddleOCR, is_available = _lazy_import_paddleocr()
        
        if not is_available:
            error_msg = "PaddleOCR is not installed. Please install with: pip install paddleocr"
            self.logger.error(error_msg)
            raise ImportError(error_msg)
        
        # Update config with provided values
        self.config.update(config)
        
        # Validate language
        if self.config["lang"] not in self.supported_languages:
            self.logger.warning(f"Language '{self.config['lang']}' not in supported languages. Defaulting to 'fr'.")
            self.config["lang"] = "fr"
        
        # Initialize PaddleOCR
        try:
            self.logger.info(f"Initializing PaddleOCR with language: {self.config['lang']}")
            
            # Enable document orientation classification only if auto_rotate is enabled
            use_orientation_classify = self.config.get("auto_rotate", False)
            
            
            # Set PaddleOCR home directory to installation folder
            import os
            install_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            paddleocr_home = os.path.join(install_dir, '.paddleocr')
            os.makedirs(paddleocr_home, exist_ok=True)
            os.environ['PPOCR_HOME'] = paddleocr_home
            
            self.engine = PaddleOCR(
                lang=self.config["lang"],
                # New parameters for PaddleOCR 3.20
                return_word_box=self.config["return_word_box"],
                
                # Detection model - Mobile version
                text_detection_model_name='PP-OCRv5_mobile_det',  # Or 'en_PP-OCRv3_det_mobile'
                # Recognition model - Mobile version
                text_recognition_model_name='PP-OCRv5_mobile_rec',  # Or 'en_PP-OCRv3_rec_mobile'
                
                # Document orientation classification (only enabled when auto_rotate=True)
                use_doc_orientation_classify=use_orientation_classify,  # Conditional based on auto_rotate
                
                # Document unwarping (perspective correction)
                use_doc_unwarping=False,  # Disable unless documents are curved/warped
                
                use_textline_orientation=True,  # Text line orientation detection

                # Detection confidence threshold
                text_det_thresh=0.3,  # Increase from default 0.3 (less strict = faster)
                
                # Bounding box threshold (filters weak detections)
                text_det_box_thresh=0.50,  # Increase from default 0.5 (eliminate weak boxes early)
                
                # Unclip ratio (text box expansion)
                text_det_unclip_ratio=1.5,  # Reduce from default 1.6 (smaller boxes = faster)
                
                # Maximum side length for detection input
                text_det_limit_side_len=960,  # Default is often 960, try 720 for speed
                
                # Limit type
                text_det_limit_type='max',  # 'max' or 'min' - 'max' limits the longest side

                # Batch processing 
                text_recognition_batch_size=16
            )
            self.is_initialized = True
            self.logger.info(f"PaddleOCR engine successfully initialized with language: {self.config['lang']}")
        except Exception as e:
            error_msg = f"Failed to initialize PaddleOCR engine: {str(e)}"
            self.logger.error(error_msg)
            raise
    
    def _ensure_initialized(self):
        """Ensure the engine is initialized before use."""
        if not self.is_initialized:
            self.logger.warning("PaddleOCR engine not initialized. Initializing with default config.")
            self.initialize(self.config)
    
    def _load_image(self, image: Union[str, Any]) -> Any:
        """
        Load an image from various input types.
        
        Args:
            image: Can be a file path, numpy array, or PIL Image object.
            
        Returns:
            Numpy array containing the image or file path.
        """
        if isinstance(image, str):
            if not os.path.exists(image):
                error_msg = f"Image file not found: {image}"
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            self.logger.debug(f"Loading image from file: {image}")
            # PaddleOCR works with file paths directly
            return image
        else:
            # Lazy import numpy and PIL only when processing non-string images
            np = _lazy_import_numpy()
            Image = _lazy_import_pil()
            
            if isinstance(image, np.ndarray):
                self.logger.debug(f"Using numpy array image with shape: {image.shape}")
                return image
            elif isinstance(image, Image.Image):
                self.logger.debug(f"Converting PIL image to numpy array, size: {image.size}")
                return np.array(image)
            else:
                error_msg = f"Unsupported image type: {type(image)}"
                self.logger.error(error_msg)
                raise TypeError(error_msg)
    
    def recognize(self, image: Union[str, Any]) -> Dict[str, Any]:
        """
        Perform OCR on the provided image.
        
        Args:
            image: Can be a file path, numpy array, or PIL Image object.
            
        Returns:
            Dictionary containing OCR results with keys:
            - 'text': List of recognized text strings
            - 'confidence': List of confidence scores (0-1)
            - 'boxes': List of bounding boxes for recognized text
            - 'processing_time': Time taken for OCR in seconds
        """
        self._ensure_initialized()
        
        image_name = image if isinstance(image, str) else "in-memory image"
        self.logger.info(f"Performing OCR on {image_name}")
        
        start_time = time.time()
        
        # Initialize dt_polys max coordinates (used for determining actual detection image size)
        dt_polys_max_x = dt_polys_max_y = 0
        
        try:
            # Process the image
            img = self._load_image(image)
            
            # Get image dimensions and save page image to temp for PDF/A sandwich export
            np = _lazy_import_numpy()
            Image = _lazy_import_pil()
            
            page_image_path = None
            if isinstance(img, str):
                # Load image to get dimensions
                pil_img = Image.open(img)
                img_width, img_height = pil_img.size
                # Save to temp (use original if it's already a file)
                page_image_path = img
            elif isinstance(img, np.ndarray):
                img_height, img_width = img.shape[:2]
                # Convert numpy array to PIL and save to temp with DPI metadata
                pil_img = Image.fromarray(img)
                os.makedirs(self.temp_dir, exist_ok=True)
                page_image_path = os.path.join(self.temp_dir, f'page_{uuid.uuid4().hex}.jpg')
                # Save as JPEG with 85% quality for 97% size reduction vs PNG
                # DPI=1 so 1 pixel = 1 point in PDF (no scaling)
                pil_img.save(page_image_path, format='JPEG', quality=85, optimize=True, dpi=(1, 1))
            else:
                img_width, img_height = img.size
                # PIL Image - save to temp with DPI metadata
                os.makedirs(self.temp_dir, exist_ok=True)
                page_image_path = os.path.join(self.temp_dir, f'page_{uuid.uuid4().hex}.jpg')
                # Save as JPEG with 85% quality for 97% size reduction vs PNG
                # DPI=1 so 1 pixel = 1 point in PDF (no scaling)
                img.save(page_image_path, format='JPEG', quality=85, optimize=True, dpi=(1, 1))
            
            self.logger.debug(f"Starting PaddleOCR recognition on image with dimensions: {img_width}x{img_height}")
            self.logger.debug(f"Page image saved to: {page_image_path}")
            
            # Use predict method with return_word_box for PaddleOCR 3.20
            # Wrap in try-except to handle blank pages that may cause KeyError in PaddleOCR
            try:
                result = self.engine.predict(img, return_word_box=self.config["return_word_box"])
            except (KeyError, IndexError, AttributeError) as ocr_err:
                # PaddleOCR may throw KeyError on blank pages (e.g., 'text_word_region' not found)
                self.logger.warning(f"PaddleOCR internal error (likely blank page): {ocr_err}")
                self.logger.info("Returning empty OCR result for blank page")
                result = []  # Empty result for blank page
            
            # Check for document rotation and rotate the saved background image if needed
            rotation_angle = 0
            if result and len(result) > 0:
                first_result = result[0]
                if hasattr(first_result, 'json') and 'res' in first_result.json:
                    res = first_result.json['res']
                    
                    # Check if document was rotated by PaddleOCR
                    if 'doc_preprocessor_res' in res:
                        doc_prep = res['doc_preprocessor_res']
                        if isinstance(doc_prep, dict) and 'angle' in doc_prep:
                            rotation_angle = doc_prep.get('angle', 0)
                            if rotation_angle != 0:
                                self.logger.info(f"[ROTATION] Document rotation detected: {rotation_angle} degrees")
                                self.logger.info(f"[ROTATION] auto_rotate config: {self.config.get('auto_rotate', False)}")
                                
                                # Check if auto_rotate is disabled
                                if not self.config.get("auto_rotate", False):
                                    error_msg = (
                                        f"PROCESSING ABORTED: Document contains rotated pages but auto_rotate is disabled.\n"
                                        f"Please either:\n"
                                        f"1. Enable auto_rotate in your configuration (set autorotate: true)\n"
                                        f"2. Provide a correctly oriented document"
                                    )
                                    raise ValueError(error_msg)
                                
                                # Rotate the saved background image to match the OCR text orientation
                                if page_image_path and os.path.exists(page_image_path):
                                    try:
                                        # Load the image
                                        bg_img = Image.open(page_image_path)
                                        
                                        # Rotate image based on detected angle
                                        # PaddleOCR angle: 0=no rotation, 90=rotate 90° CCW, 180=rotate 180°, 270/-90=rotate 90° CW
                                        if rotation_angle == 90:
                                            rotated_img = bg_img.rotate(90, expand=True)  # Rotate 90° CCW to match text
                                        elif rotation_angle == 180:
                                            rotated_img = bg_img.rotate(180, expand=True)
                                        elif rotation_angle == 270 or rotation_angle == -90:
                                            rotated_img = bg_img.rotate(-90, expand=True)  # Rotate 90° CW to match text
                                        else:
                                            rotated_img = bg_img
                                        
                                        # Save the rotated image back
                                        if rotated_img != bg_img:
                                            rotated_img.save(page_image_path, format='JPEG', quality=85, optimize=True, dpi=(1, 1))
                                            # Update dimensions to match rotated image
                                            img_width, img_height = rotated_img.size
                                            self.logger.info(f"Background image rotated and saved. New dimensions: {img_width}x{img_height}")
                                        
                                        bg_img.close()
                                        if rotated_img != bg_img:
                                            rotated_img.close()
                                    except Exception as rot_err:
                                        self.logger.error(f"Failed to rotate background image: {rot_err}")
            
            # DEBUG: Check dt_polys to find actual detection image dimensions
            if result and len(result) > 0:
                first_result = result[0]
                if hasattr(first_result, 'json') and 'res' in first_result.json:
                    res = first_result.json['res']
                    if 'dt_polys' in res:
                        dt_polys = res['dt_polys']
                        if dt_polys and len(dt_polys) > 0:
                            max_x = max_y = 0
                            for poly in dt_polys:
                                if isinstance(poly, (list, tuple)):
                                    for point in poly:
                                        if isinstance(point, (list, tuple)) and len(point) >= 2:
                                            max_x = max(max_x, point[0])
                                            max_y = max(max_y, point[1])
                            dt_polys_max_x = max_x
                            dt_polys_max_y = max_y
                            self.logger.info(f"DEBUG dt_polys max: x={dt_polys_max_x:.0f}, y={dt_polys_max_y:.0f}")
            
            # Parse OCR results - extract line-level and word-level data
            texts = []
            confidences = []
            boxes = []
            word_texts = []
            word_boxes = []
            
            if result and len(result) > 0:
                for r in result:
                    # Check if result has the new format with word-level information (PaddleOCR 3.x/PaddleX)
                    if hasattr(r, 'json') and r.json:
                        res_dict = r.json.get("res", {})
                        
                        # Line-level extraction
                        line_texts = res_dict.get("rec_texts", [])
                        line_boxes = res_dict.get("dt_polys", [])
                        line_scores = res_dict.get("rec_scores", [])  # Confidence scores
                        
                        for i, text in enumerate(line_texts):
                            if i < len(line_boxes):
                                texts.append(text)
                                # Use actual confidence if available
                                conf = line_scores[i] if i < len(line_scores) else 0.99
                                confidences.append(float(conf))
                                boxes.append(line_boxes[i])
                        
                        # Word-level extraction (new in PaddleOCR 3.20+)
                        text_word = res_dict.get("text_word", [])
                        text_word_boxes = res_dict.get("text_word_boxes", [])
                        
                        if text_word and text_word_boxes:
                            for i, word_list in enumerate(text_word):
                                if i < len(text_word_boxes):
                                    for j, word in enumerate(word_list):
                                        if word.strip() and j < len(text_word_boxes[i]):
                                            word_texts.append(word)
                                            word_boxes.append(text_word_boxes[i][j])
                    else:
                        # Handle older PaddleOCR versions (list of [bbox, (text, confidence)])
                        for line in r:
                            if isinstance(line, (list, tuple)):
                                # New format check: can be 2 or 3 elements
                                if len(line) == 2:
                                    # Format: [box, (text, confidence)]
                                    box = line[0]
                                    text_conf = line[1]
                                    
                                    if isinstance(text_conf, (list, tuple)) and len(text_conf) == 2:
                                        text, confidence = text_conf
                                    else:
                                        text = str(text_conf)
                                        confidence = 0.0
                                    
                                    texts.append(text)
                                    confidences.append(float(confidence))
                                    boxes.append(box)
                                elif len(line) >= 3:
                                    # Format: [box, text, confidence, ...]
                                    box = line[0]
                                    text = line[1]
                                    confidence = line[2] if len(line) > 2 else 0.0
                                    texts.append(text)
                                    confidences.append(float(confidence))
                                    boxes.append(box)
            
            # Analyze bbox coordinate space
            max_bbox_x = max_bbox_y = 0
            for box in boxes:
                if isinstance(box[0], (list, tuple)):
                    # Polygon format
                    for point in box:
                        max_bbox_x = max(max_bbox_x, point[0])
                        max_bbox_y = max(max_bbox_y, point[1])
                else:
                    # Flat rectangle format
                    if len(box) >= 4:
                        max_bbox_x = max(max_bbox_x, box[0], box[2])
                        max_bbox_y = max(max_bbox_y, box[1], box[3])
            
            self.logger.info(f"Bbox max coordinates: ({max_bbox_x:.0f}, {max_bbox_y:.0f})")
            self.logger.info(f"Detection space (dt_polys): ({dt_polys_max_x:.0f}, {dt_polys_max_y:.0f})")
            self.logger.info(f"Original image: ({img_width}, {img_height})")
            
            # Determine which coordinate space bboxes are in
            bbox_in_detection = (abs(max_bbox_x - dt_polys_max_x) < 100 and abs(max_bbox_y - dt_polys_max_y) < 100)
            bbox_in_original = (abs(max_bbox_x - img_width) < 100 and abs(max_bbox_y - img_height) < 100)
            
            if bbox_in_detection:
                self.logger.warning("WARNING: Bboxes are in DETECTION space, not original!")
                self.logger.warning("    Scaling is needed but aspect ratio mismatch may cause errors")
            elif bbox_in_original:
                self.logger.info("SUCCESS: Bboxes are in ORIGINAL image space (no scaling needed)")
            else:
                self.logger.error(f"ERROR: Unknown bbox coordinate space! max=({max_bbox_x},{max_bbox_y})")
            
            processing_time = time.time() - start_time
            
            self.logger.info(f"OCR completed in {processing_time:.2f}s. Found {len(texts)} line elements, {len(word_texts)} word elements.")
            self.logger.info(f"DEBUG: Returning image dimensions: {img_width}x{img_height}")
            self.logger.info(f"DEBUG: Page image path: {page_image_path}")
            if self.mode == "debug":
                self.logger.debug(f"Recognized texts: {texts[:5]}...")  # Show first 5
                self.logger.debug(f"Confidence scores: {confidences[:5]}...")
                
            # Prepare return result
            result_dict = {
                'text': texts,  # Line-level text
                'confidence': confidences,  # Line-level confidence
                'boxes': boxes,  # Line-level bounding boxes
                'processing_time': processing_time,
                'line_text': texts,       # Line-level text
                'line_boxes': boxes,      # Line-level bounding boxes (polygons)
                'word_text': word_texts,  # Word-level text
                'word_boxes': word_boxes, # Word-level bounding boxes (rectangles)
                'image_width': img_width,  # Image width for layout preservation
                'image_height': img_height, # Image height for layout preservation
                'page_image_path': page_image_path  # Path to temp page image for PDF/A sandwich
            }
            
            # If rotation was applied and auto_rotate is enabled, include rotated image as base64
            self.logger.info(f"[ROTATION] Pre-encode check: rotation_angle={rotation_angle}, auto_rotate={self.config.get('auto_rotate', False)}, page_image_path={page_image_path}, exists={os.path.exists(page_image_path) if page_image_path else False}")
            if rotation_angle > 0 and self.config.get("auto_rotate", False) and page_image_path and os.path.exists(page_image_path):
                try:
                    from PIL import Image
                    import io
                    import base64
                    
                    # Load the rotated image
                    rotated_img = Image.open(page_image_path)
                    
                    # Convert to base64
                    buffer = io.BytesIO()
                    rotated_img.save(buffer, format='JPEG', quality=95)
                    rotated_img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    
                    result_dict['rotated_image_b64'] = rotated_img_b64
                    result_dict['rotation_angle'] = rotation_angle
                    self.logger.info(f"[ROTATION] Including rotated image in result (angle={rotation_angle}°)")
                    
                    rotated_img.close()
                except Exception as e:
                    self.logger.error(f"Failed to encode rotated image as base64: {e}")
            
            return result_dict
            
        except ValueError as e:
            # Re-raise ValueError immediately (e.g., rotation errors)
            raise
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Error during OCR recognition: {str(e)}"
            self.logger.error(error_msg)
            
            # Add more debug info
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            
            return {
                'text': [],
                'confidence': [],
                'boxes': [],
                'processing_time': processing_time,
                'error': str(e)
            }
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """
        Update the engine's configuration.
        
        Args:
            config: Dictionary containing engine-specific configuration updates.
        """
        old_config = self.config.copy()
        self.config.update(config)
        
        self.logger.info(f"Updating PaddleOCR engine configuration")
        
        if self.mode == "debug":
            self.logger.debug(f"Old config: {old_config}")
            self.logger.debug(f"New config: {self.config}")
        
        # If critical parameters changed, re-initialize the engine
        critical_params = ["lang", "use_textline_orientation", "use_doc_orientation_classify",
                          "return_word_box", "auto_rotate",
                          "text_detection_model_name", "text_recognition_model_name"]
