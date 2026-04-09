#!/usr/bin/env python3
"""Generate thumbnails for existing videos."""

import os
import sys

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("ERROR: cv2 not available")
    sys.exit(1)

# Set up path for imports
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models.video import Video


def extract_thumbnail(video_path, video_id, thumbnails_dir):
    """Extract the first frame of a video as a thumbnail."""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"  ❌ Could not open video {video_path}")
            return False
        
        ret, frame = cap.read()
        if not ret:
            print(f"  ❌ Could not read first frame")
            cap.release()
            return False
        
        # Resize frame
        height, width = frame.shape[:2]
        aspect_ratio = width / height
        thumb_height = 240
        thumb_width = int(thumb_height * aspect_ratio)
        frame_resized = cv2.resize(frame, (thumb_width, thumb_height))
        
        os.makedirs(thumbnails_dir, exist_ok=True)
        thumbnail_path = os.path.join(thumbnails_dir, f"{video_id}_thumb.jpg")
        cv2.imwrite(thumbnail_path, frame_resized)
        
        print(f"  ✅ Extracted thumbnail for video {video_id}")
        cap.release()
        return True
    except Exception as e:
        print(f"  ❌ Error extracting thumbnail: {e}")
        return False


if __name__ == "__main__":
    app = create_app()
    
    with app.app_context():
        # Get all uploaded videos
        videos = Video.query.filter(Video.file_path.notlike('%://%')).all()
        
        if not videos:
            print("No local videos found")
            sys.exit(0)
        
        print(f"Found {len(videos)} local videos")
        
        upload_folder = os.environ.get("UPLOAD_FOLDER", "uploads")
        thumbnails_dir = os.path.join(upload_folder, "videos", "thumbnails")
        
        success_count = 0
        for video in videos:
            if os.path.exists(video.file_path):
                print(f"Processing video {video.id}: {video.original_filename}")
                if extract_thumbnail(video.file_path, video.id, thumbnails_dir):
                    success_count += 1
            else:
                print(f"  ⚠️  File not found: {video.file_path}")
        
        print(f"\n✅ Generated {success_count}/{len(videos)} thumbnails")
