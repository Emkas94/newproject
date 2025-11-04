"""
OCR (Optical Character Recognition) module for video frames.
"""
from typing import List, Dict, Any


def extract_text_from_frames(
    video_path: str,
    interval: int = 5
) -> List[Dict[str, Any]]:
    """
    Extract text from video frames using OCR.
    
    Args:
        video_path: Path to video file
        interval: Seconds between frames to sample
        
    Returns:
        List of segments with 'start', 'end', 'text'
    """
    # TODO: Implement actual OCR
    # This is a stub that returns sample data
    
    try:
        import cv2
        import pytesseract
        from videotext.utils import extract_frames
        
        frames = extract_frames(video_path, interval)
        segments = []
        
        for frame_info in frames:
            timestamp = frame_info['timestamp']
            frame = frame_info['frame']
            
            # Run OCR
            text = pytesseract.image_to_string(frame, lang='rus+eng')
            
            if text.strip():
                segments.append({
                    'start': timestamp,
                    'end': timestamp + interval,
                    'text': text.strip()
                })
        
        return segments
        
    except ImportError:
        # Return stub data if dependencies not available
        return [
            {
                'start': 0.0,
                'end': 5.0,
                'text': '[STUB] OCR недоступен. Установите opencv-python и pytesseract.'
            }
        ]
    except Exception as e:
        raise RuntimeError(f"OCR extraction failed: {e}") from e
