import os
import uuid
import logging
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app import db
from app.models.slide import Slide, SlidePage
from app.models.course import Course
from app.services.s3_service import get_s3_service

slides_bp = Blueprint("slides", __name__)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "ppt", "pptx"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@slides_bp.route("/upload", methods=["POST"])
def upload_slide():
    """Upload a slide file (PDF/PPTX) to S3 and process it."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type. Use PDF, PPT, or PPTX."}), 400

    course_id = request.form.get("course_id")
    if not course_id:
        return jsonify({"error": "course_id is required"}), 400

    course = db.session.get(Course, int(course_id))
    if not course:
        return jsonify({"error": "Course not found"}), 404

    # Generate unique filename
    original_filename = secure_filename(file.filename)
    ext = original_filename.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    s3_key = f"slides/{int(course_id)}/{unique_filename}"

    # Upload to S3
    try:
        s3_service = get_s3_service()
        file.seek(0)  # Reset file pointer
        s3_service.upload_file(file, s3_key, content_type="application/octet-stream")
    except Exception as e:
        logger.error(f"Failed to upload slide to S3: {e}")
        return jsonify({"error": "Failed to upload file"}), 500

    # Store in database with S3 key (not local path)
    slide = Slide(
        course_id=int(course_id),
        filename=unique_filename,
        original_filename=original_filename,
        file_type=ext,
        file_path=s3_key,  # Store S3 key instead of local path
    )
    db.session.add(slide)
    db.session.commit()

    # Process the file (extract text and generate thumbnails)
    if ext == "pdf":
        try:
            _process_pdf(slide)
        except Exception as e:
            logger.warning("PDF processing error for slide %s: %s", slide.id, e)
    elif ext in ("ppt", "pptx"):
        try:
            _process_pptx(slide)
        except Exception as e:
            logger.warning("PPTX processing error for slide %s: %s", slide.id, e)

    # Generate embeddings for slide pages
    try:
        from app.services.alignment_service import embed_slide_pages
        embed_slide_pages(slide.id)
    except Exception as e:
        logger.warning("Slide embedding error: %s", e)

    return jsonify(slide.to_dict()), 201


def _process_pdf(slide):
    """Extract text and generate thumbnails from a PDF file stored in S3."""
    import fitz  # PyMuPDF
    
    s3_service = get_s3_service()
    
    # Download PDF from S3 to temp file for processing
    temp_pdf_path = s3_service.download_to_temp_file(slide.file_path)
    
    try:
        doc = fitz.open(temp_pdf_path)
        slide.total_pages = len(doc)

        for i, page in enumerate(doc):
            text = page.get_text() or ""
            
            # Render page to image (2x zoom for clarity)
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            
            # Save thumbnail to temp file, then upload to S3
            img_filename = f"page_{i + 1}.png"
            thumbnail_s3_key = f"slides/{slide.course_id}/{slide.id}/thumbnails/{img_filename}"
            
            # Convert image to bytes and upload
            img_bytes = pix.tobytes("png")
            from io import BytesIO
            img_obj = BytesIO(img_bytes)
            s3_service.upload_file(img_obj, thumbnail_s3_key, content_type="image/png")
            
            slide_page = SlidePage(
                slide_id=slide.id,
                page_number=i + 1,
                content_text=text,
                thumbnail_path=thumbnail_s3_key,  # Store S3 key
            )
            db.session.add(slide_page)

        doc.close()
        slide.processed = True
        db.session.commit()
    finally:
        # Clean up temp file
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)


def _process_pptx(slide):
    """Extract text and render images from PPTX files stored in S3."""
    import subprocess
    import tempfile
    import fitz  # PyMuPDF
    from pptx import Presentation
    from io import BytesIO

    s3_service = get_s3_service()
    
    # Download PPTX from S3 to temp file
    temp_pptx_path = s3_service.download_to_temp_file(slide.file_path)
    
    try:
        # Extract text from PPTX
        prs = Presentation(temp_pptx_path)
        slide.total_pages = len(prs.slides)

        slide_texts = []
        for pptx_slide in prs.slides:
            texts = []
            for shape in pptx_slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        para_text = paragraph.text.strip()
                        if para_text:
                            texts.append(para_text)
                if shape.has_table:
                    for row in shape.table.rows:
                        row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_texts:
                            texts.append(" | ".join(row_texts))
            slide_texts.append("\n".join(texts))

        # Create temporary directory for conversion
        temp_dir = tempfile.mkdtemp()
        
        # Convert PPTX to PDF using LibreOffice for image rendering
        pdf_path = None
        try:
            result = subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    temp_dir,
                    temp_pptx_path,
                ],
                capture_output=True,
                timeout=120,
            )
            base_name = os.path.splitext(os.path.basename(temp_pptx_path))[0]
            candidate = os.path.join(temp_dir, f"{base_name}.pdf")
            if os.path.exists(candidate):
                pdf_path = candidate
        except Exception as e:
            logger.warning("LibreOffice conversion failed: %s", e)

        # Generate thumbnails from converted PDF or fallback to text-only
        if pdf_path:
            doc = fitz.open(pdf_path)
            for i in range(min(len(doc), slide.total_pages)):
                page = doc[i]
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                
                # Upload thumbnail to S3
                img_filename = f"page_{i + 1}.png"
                thumbnail_s3_key = f"slides/{slide.course_id}/{slide.id}/thumbnails/{img_filename}"
                
                img_bytes = pix.tobytes("png")
                img_obj = BytesIO(img_bytes)
                s3_service.upload_file(img_obj, thumbnail_s3_key, content_type="image/png")

                slide_page = SlidePage(
                    slide_id=slide.id,
                    page_number=i + 1,
                    content_text=slide_texts[i] if i < len(slide_texts) else "",
                    thumbnail_path=thumbnail_s3_key,  # Store S3 key
                )
                db.session.add(slide_page)
            doc.close()
        else:
            # Fallback: text-only if LibreOffice unavailable
            for i, text in enumerate(slide_texts):
                slide_page = SlidePage(
                    slide_id=slide.id,
                    page_number=i + 1,
                    content_text=text,
                )
                db.session.add(slide_page)

        slide.processed = True
        db.session.commit()
    finally:
        # Clean up temp files
        if os.path.exists(temp_pptx_path):
            os.remove(temp_pptx_path)
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    db.session.commit()


@slides_bp.route("/course/<int:course_id>", methods=["GET"])
def get_slides_by_course(course_id):
    slides = Slide.query.filter_by(course_id=course_id).order_by(Slide.created_at.desc()).all()
    return jsonify([s.to_dict() for s in slides])


@slides_bp.route("/<int:slide_id>", methods=["GET"])
def get_slide(slide_id):
    slide = db.session.get(Slide, slide_id)
    if not slide:
        return jsonify({"error": "Slide not found"}), 404
    return jsonify(slide.to_dict())


@slides_bp.route("/file/<int:slide_id>", methods=["GET"])
def get_slide_download_url(slide_id):
    """Get presigned URL for downloading the slide file from S3."""
    slide = db.session.get(Slide, slide_id)
    if not slide:
        return jsonify({"error": "Slide not found"}), 404
    
    try:
        s3_service = get_s3_service()
        presigned_url = s3_service.generate_presigned_url(slide.file_path, expiration=3600)
        return jsonify({"url": presigned_url, "original_filename": slide.original_filename})
    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        return jsonify({"error": "Failed to generate download URL"}), 500


@slides_bp.route("/page-image/<int:page_id>", methods=["GET"])
def get_page_image_url(page_id):
    """Get presigned URL for accessing a slide page thumbnail from S3."""
    page = db.session.get(SlidePage, page_id)
    if not page or not page.thumbnail_path:
        return jsonify({"error": "Page image not found"}), 404
    
    try:
        s3_service = get_s3_service()
        presigned_url = s3_service.generate_presigned_url(page.thumbnail_path, expiration=3600)
        return jsonify({"url": presigned_url})
    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        return jsonify({"error": "Failed to generate image URL"}), 500


@slides_bp.route("/<int:slide_id>", methods=["DELETE"])
def delete_slide(slide_id):
    """Delete a slide and all its associated files from S3."""
    slide = db.session.get(Slide, slide_id)
    if not slide:
        return jsonify({"error": "Slide not found"}), 404

    try:
        s3_service = get_s3_service()
        
        # Delete the slide file itself
        s3_service.delete_file(slide.file_path)
        
        # Delete the slide's thumbnail directory (all thumbnails with the slide ID prefix)
        thumbnails_prefix = f"slides/{slide.course_id}/{slide.id}/"
        s3_service.delete_directory(thumbnails_prefix)
        
    except Exception as e:
        logger.error(f"Failed to delete slide files from S3: {e}")
        return jsonify({"error": "Failed to delete slide files"}), 500

    db.session.delete(slide)
    db.session.commit()
    return jsonify({"message": "Slide deleted"})
