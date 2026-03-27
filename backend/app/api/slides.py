import os
import uuid
import logging
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from app.services.s3_service import get_s3_service
from app.services.supabase_repo import (
    select_rows,
    select_one_by_id,
    insert_row,
    update_row_by_id,
    delete_row_by_id,
    get_slide_payload,
)

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

    course = select_one_by_id("courses", int(course_id), columns="id")
    if not course:
        return jsonify({"error": "Course not found"}), 404

    # Generate unique filename for S3 and keep original name for UX display.
    original_filename = secure_filename(file.filename)
    ext = original_filename.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    s3_key = f"slides/{int(course_id)}/{unique_filename}"

    try:
        s3_service = get_s3_service()
        file.seek(0)
        s3_service.upload_file(file, s3_key, content_type="application/octet-stream")
    except Exception as e:
        logger.error("Failed to upload slide to S3: %s", e)
        return jsonify({"error": "Failed to upload file"}), 500

    slide = insert_row(
        "slides",
        {
            "course_id": int(course_id),
            "filename": unique_filename,
            "original_filename": original_filename,
            "file_type": ext,
            "file_path": s3_key,
        },
    )

    if ext == "pdf":
        try:
            _process_pdf(slide)
        except Exception as e:
            logger.warning("PDF processing error for slide %s: %s", slide["id"], e)
    elif ext in ("ppt", "pptx"):
        try:
            _process_pptx(slide)
        except Exception as e:
            logger.warning("PPTX processing error for slide %s: %s", slide["id"], e)

    try:
        from app.services.alignment_service import embed_slide_pages

        embed_slide_pages(slide["id"])
    except Exception as e:
        logger.warning("Slide embedding error: %s", e)

    refreshed = select_one_by_id("slides", slide["id"])
    return jsonify(get_slide_payload(refreshed)), 201


def _process_pdf(slide):
    """Extract text and generate thumbnails from a PDF file stored in S3."""
    import fitz
    from io import BytesIO

    s3_service = get_s3_service()
    temp_pdf_path = s3_service.download_to_temp_file(slide["file_path"])

    try:
        doc = fitz.open(temp_pdf_path)
        update_row_by_id("slides", slide["id"], {"total_pages": len(doc)})

        for i, page in enumerate(doc):
            text = page.get_text() or ""
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)

            img_filename = f"page_{i + 1}.png"
            thumbnail_s3_key = f"slides/{slide['course_id']}/{slide['id']}/thumbnails/{img_filename}"
            img_bytes = pix.tobytes("png")
            s3_service.upload_file(BytesIO(img_bytes), thumbnail_s3_key, content_type="image/png")

            insert_row(
                "slide_pages",
                {
                    "slide_id": slide["id"],
                    "page_number": i + 1,
                    "content_text": text,
                    "thumbnail_path": thumbnail_s3_key,
                },
            )

        doc.close()
        update_row_by_id("slides", slide["id"], {"processed": True})
    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)


def _process_pptx(slide):
    """Extract text and render images from PPTX files stored in S3."""
    import subprocess
    import tempfile
    import fitz
    from pptx import Presentation
    from io import BytesIO

    s3_service = get_s3_service()
    temp_pptx_path = s3_service.download_to_temp_file(slide["file_path"])

    try:
        prs = Presentation(temp_pptx_path)
        update_row_by_id("slides", slide["id"], {"total_pages": len(prs.slides)})

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

        temp_dir = tempfile.mkdtemp()
        pdf_path = None
        try:
            subprocess.run(
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

        if pdf_path:
            doc = fitz.open(pdf_path)
            for i in range(min(len(doc), len(slide_texts))):
                page = doc[i]
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)

                img_filename = f"page_{i + 1}.png"
                thumbnail_s3_key = f"slides/{slide['course_id']}/{slide['id']}/thumbnails/{img_filename}"
                s3_service.upload_file(BytesIO(pix.tobytes("png")), thumbnail_s3_key, content_type="image/png")

                insert_row(
                    "slide_pages",
                    {
                        "slide_id": slide["id"],
                        "page_number": i + 1,
                        "content_text": slide_texts[i] if i < len(slide_texts) else "",
                        "thumbnail_path": thumbnail_s3_key,
                    },
                )
            doc.close()
        else:
            for i, text in enumerate(slide_texts):
                insert_row(
                    "slide_pages",
                    {
                        "slide_id": slide["id"],
                        "page_number": i + 1,
                        "content_text": text,
                    },
                )

        update_row_by_id("slides", slide["id"], {"processed": True})
    finally:
        if os.path.exists(temp_pptx_path):
            os.remove(temp_pptx_path)
        if "temp_dir" in locals() and os.path.exists(temp_dir):
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)


@slides_bp.route("/course/<int:course_id>", methods=["GET"])
def get_slides_by_course(course_id):
    slides = select_rows(
        "slides",
        filters=[("eq", "course_id", course_id)],
        order_by="created_at",
        ascending=False,
    )
    return jsonify([get_slide_payload(s) for s in slides])


@slides_bp.route("/<int:slide_id>", methods=["GET"])
def get_slide(slide_id):
    slide = select_one_by_id("slides", slide_id)
    if not slide:
        return jsonify({"error": "Slide not found"}), 404
    return jsonify(get_slide_payload(slide))


@slides_bp.route("/file/<int:slide_id>", methods=["GET"])
def get_slide_download_url(slide_id):
    """Get presigned URL for downloading the slide file from S3."""
    slide = select_one_by_id("slides", slide_id)
    if not slide:
        return jsonify({"error": "Slide not found"}), 404

    try:
        s3_service = get_s3_service()
        presigned_url = s3_service.generate_presigned_url(slide["file_path"], expiration=3600)
        return jsonify({"url": presigned_url, "original_filename": slide["original_filename"]})
    except Exception as e:
        logger.error("Failed to generate presigned URL: %s", e)
        return jsonify({"error": "Failed to generate download URL"}), 500


@slides_bp.route("/page-image/<int:page_id>", methods=["GET"])
def get_page_image_url(page_id):
    """Get presigned URL for accessing a slide page thumbnail from S3."""
    page = select_one_by_id("slide_pages", page_id)
    if not page or not page.get("thumbnail_path"):
        return jsonify({"error": "Page image not found"}), 404

    try:
        s3_service = get_s3_service()
        presigned_url = s3_service.generate_presigned_url(page["thumbnail_path"], expiration=3600)
        return jsonify({"url": presigned_url})
    except Exception as e:
        logger.error("Failed to generate presigned URL: %s", e)
        return jsonify({"error": "Failed to generate image URL"}), 500


@slides_bp.route("/<int:slide_id>", methods=["DELETE"])
def delete_slide(slide_id):
    """Delete a slide and all its associated files from S3."""
    slide = select_one_by_id("slides", slide_id)
    if not slide:
        return jsonify({"error": "Slide not found"}), 404

    try:
        s3_service = get_s3_service()
        s3_service.delete_file(slide["file_path"])
        thumbnails_prefix = f"slides/{slide['course_id']}/{slide['id']}/"
        s3_service.delete_directory(thumbnails_prefix)
    except Exception as e:
        logger.error("Failed to delete slide files from S3: %s", e)
        return jsonify({"error": "Failed to delete slide files"}), 500

    delete_row_by_id("slides", slide_id)
    return jsonify({"message": "Slide deleted"})
