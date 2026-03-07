"""
Video Frame Extractor and Analyzer for FSE Demo Video
Extracts frames at regular intervals and logs analysis for supervision
"""
import cv2
import os
from datetime import datetime

def extract_and_analyze_frames(
    video_path: str,
    output_dir: str = "video_analysis",
    interval_seconds: int = 3,
    log_file: str = "frame_analysis_log.txt"
):
    """
    Extract frames from FSE demo video and create analysis log
    
    Args:
        video_path: Path to demo video
        output_dir: Directory to save extracted frames
        interval_seconds: Extract frame every N seconds
        log_file: Path to analysis log file
    """
    
    # Create output directory
    frames_dir = os.path.join(os.path.dirname(video_path), output_dir)
    os.makedirs(frames_dir, exist_ok=True)
    
    # Open video
    video = cv2.VideoCapture(video_path)
    if not video.isOpened():
        print(f"ERROR: Could not open video file: {video_path}")
        return
    
    # Get video properties
    fps = video.get(cv2.CAP_PROP_FPS)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Calculate frame interval
    frame_interval = int(fps * interval_seconds)
    
    # Initialize log
    log_path = os.path.join(os.path.dirname(video_path), log_file)
    with open(log_path, 'w', encoding='utf-8') as log:
        log.write("="*80 + "\n")
        log.write("FSE DEMO VIDEO ANALYSIS LOG\n")
        log.write("="*80 + "\n")
        log.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"Video Path: {video_path}\n")
        log.write(f"Video Duration: {duration:.2f} seconds\n")
        log.write(f"Video Resolution: {width}x{height}\n")
        log.write(f"FPS: {fps:.2f}\n")
        log.write(f"Total Frames: {total_frames}\n")
        log.write(f"Extraction Interval: Every {interval_seconds} seconds (every {frame_interval} frames)\n")
        log.write(f"Output Directory: {frames_dir}\n")
        log.write("="*80 + "\n\n")
    
    print(f"Video Info:")
    print(f"  Duration: {duration:.2f} seconds")
    print(f"  Resolution: {width}x{height}")
    print(f"  FPS: {fps:.2f}")
    print(f"  Extracting every {interval_seconds} seconds...")
    print(f"  Saving frames to: {frames_dir}")
    print(f"  Analysis log: {log_path}")
    print()
    
    # Extract frames
    frame_count = 0
    saved_count = 0
    
    while True:
        ret, frame = video.read()
        if not ret:
            break
        
        # Save frame at interval
        if frame_count % frame_interval == 0:
            timestamp = frame_count / fps
            frame_filename = f"frame_{saved_count:04d}_t{int(timestamp):03d}s.png"
            frame_path = os.path.join(frames_dir, frame_filename)
            
            cv2.imwrite(frame_path, frame)
            
            # Log frame extraction
            with open(log_path, 'a', encoding='utf-8') as log:
                log.write(f"FRAME #{saved_count:04d}\n")
                log.write(f"  Filename: {frame_filename}\n")
                log.write(f"  Timestamp: {int(timestamp//60)}m {int(timestamp%60)}s\n")
                log.write(f"  Frame Number: {frame_count}/{total_frames}\n")
                log.write(f"  Resolution: {frame.shape[1]}x{frame.shape[0]}\n")
                log.write(f"  File Path: {frame_path}\n")
                log.write("\n  VISUAL ANALYSIS:\n")
                log.write("  " + "-"*76 + "\n")
                log.write("  [ ] Window title visible? (Gestion des Actes / GALAXIE Centre de Soins)\n")
                log.write("  [ ] Patient name visible?\n")
                log.write("  [ ] NIR/IPP visible?\n")
                log.write("  [ ] Prescripteur P.Code visible?\n")
                log.write("  [ ] AMY Code visible?\n")
                log.write("  [ ] **FSE Number visible?** (CRITICAL - Check top-left, top-right, title bar)\n")
                log.write("  [ ] Date prescription visible?\n")
                log.write("  [ ] Ajouter button visible? (Yellow button)\n")
                log.write("  [ ] Valider FSE button visible?\n")
                log.write("  [ ] Other notable elements:\n")
                log.write("\n  NOTES:\n")
                log.write("  (Manually fill in observations after reviewing frame)\n")
                log.write("  " + "-"*76 + "\n")
                log.write("\n" + "="*80 + "\n\n")
            
            print(f"✓ Saved frame {saved_count:04d} @ {int(timestamp)}s - {frame_filename}")
            saved_count += 1
        
        frame_count += 1
    
    video.release()
    
    # Final summary
    with open(log_path, 'a', encoding='utf-8') as log:
        log.write("\n" + "="*80 + "\n")
        log.write("EXTRACTION SUMMARY\n")
        log.write("="*80 + "\n")
        log.write(f"Total Frames Processed: {frame_count}\n")
        log.write(f"Frames Extracted: {saved_count}\n")
        log.write(f"Extraction Complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write("="*80 + "\n\n")
        log.write("TODO - MANUAL REVIEW:\n")
        log.write("-"*80 + "\n")
        log.write("1. Review each frame image in: {}\n".format(frames_dir))
        log.write("2. Fill in the checklist for each frame above\n")
        log.write("3. **PRIORITY**: Identify where FSE number appears (if visible)\n")
        log.write("4. Note P.Code values seen (for prescribers)\n")
        log.write("5. Note AMY codes seen\n")
        log.write("6. Identify trigger points (Ajouter button, Valider FSE button)\n")
        log.write("7. Document any unexpected elements or screen layouts\n")
        log.write("-"*80 + "\n")
    
    print(f"\n{'='*80}")
    print(f"EXTRACTION COMPLETE!")
    print(f"{'='*80}")
    print(f"Total frames extracted: {saved_count}")
    print(f"Frames saved to: {frames_dir}")
    print(f"Analysis log: {log_path}")
    print(f"\nNext steps:")
    print(f"  1. Review frames in: {frames_dir}")
    print(f"  2. Check analysis log: {log_path}")
    print(f"  3. Look for FSE number location (CRITICAL)")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    video_path = r"D:\Projects\neuro\20250930_073650.mp4"
    extract_and_analyze_frames(
        video_path=video_path,
        output_dir="video_analysis",
        interval_seconds=3,
        log_file="frame_analysis_log.txt"
    )
