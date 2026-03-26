import React, { useState, useEffect, useRef } from 'react';
import { uploadSlide, getSlidesByCourse, getSlideFileUrl, getPageImageUrl, deleteSlide, extractKnowledgePoints, getExtractKPStatus, getSlide } from '../services/api';
import '../styles/SlidesPanel.css';

function SlidesPanel({ courseId, onJumpToTimestamp, currentVideoTime, targetSlidePage }) {
  const [slides, setSlides] = useState([]);
  const [currentSlide, setCurrentSlide] = useState(null);
  const [currentPage, setCurrentPage] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractStatus, setExtractStatus] = useState('');
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    if (courseId) {
      loadSlides();
    } else {
      setSlides([]);
      setCurrentSlide(null);
    }
  }, [courseId]);

  // Jump to slide page when triggered from VideoPlayer
  useEffect(() => {
    if (!targetSlidePage) return;
    const { slideId, pageNumber } = targetSlidePage;
    // Find the slide in our list
    const targetSlide = slides.find(s => s.id === slideId);
    if (targetSlide) {
      setCurrentSlide(targetSlide);
      // pages are sorted by page_number; find the index
      const pageIndex = (targetSlide.pages || []).findIndex(p => p.page_number === pageNumber);
      if (pageIndex >= 0) {
        setCurrentPage(pageIndex);
      }
    }
  }, [targetSlidePage]);

  const loadSlides = async () => {
    try {
      const res = await getSlidesByCourse(courseId);
      setSlides(res.data);
      if (res.data.length > 0 && !currentSlide) {
        setCurrentSlide(res.data[0]);
        setCurrentPage(0);
      }
    } catch {
      // API not available yet
    }
  };

  const handleUpload = async (file) => {
    if (!courseId) {
      alert('Please create or select a course first.');
      return;
    }
    if (!file) return;
    const allowed = ['application/pdf', 'application/vnd.ms-powerpoint',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation'];
    if (!allowed.includes(file.type) && !/\.(pdf|ppt|pptx)$/i.test(file.name)) {
      alert('Please upload PDF, PPT, or PPTX files.');
      return;
    }
    setUploading(true);
    try {
      const res = await uploadSlide(courseId, file);
      setSlides((prev) => [...prev, res.data]);
      if (!currentSlide) {
        setCurrentSlide(res.data);
        setCurrentPage(0);
      }
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const handleDelete = async (id) => {
    try {
      await deleteSlide(id);
      setSlides((prev) => prev.filter((s) => s.id !== id));
      if (currentSlide?.id === id) {
        setCurrentSlide(slides.length > 1 ? slides.find((s) => s.id !== id) : null);
        setCurrentPage(0);
      }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Resume polling if extraction is running when slide changes
  useEffect(() => {
    if (!currentSlide) return;
    if (pollRef.current) clearInterval(pollRef.current);
    // Check if an extraction is already running for this slide
    getExtractKPStatus(currentSlide.id).then((res) => {
      if (res.data?.state === 'running') {
        setExtracting(true);
        setExtractStatus(res.data.message || 'Extracting...');
        startPolling(currentSlide.id);
      }
    }).catch(() => {});
  }, [currentSlide?.id]);

  const startPolling = (slideId) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await getExtractKPStatus(slideId);
        const st = res.data;
        if (st.state === 'running') {
          setExtractStatus(st.message || 'Extracting...');
        } else if (st.state === 'done') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setExtracting(false);
          setExtractStatus('');
          // Reload slide data to show new KPs
          try {
            const slideRes = await getSlide(slideId);
            setCurrentSlide(slideRes.data);
            setSlides((prev) => prev.map((s) => (s.id === slideRes.data.id ? slideRes.data : s)));
          } catch {}
          if (st.created === 0) {
            alert('All pages already have knowledge points.');
          }
        } else if (st.state === 'error') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setExtracting(false);
          setExtractStatus('');
          alert('KP extraction failed: ' + (st.error || 'Unknown error'));
        }
      } catch {
        // ignore polling errors
      }
    }, 3000);
  };

  const handleExtractKP = async () => {
    if (!currentSlide || extracting) return;
    setExtracting(true);
    setExtractStatus('Starting extraction...');
    try {
      await extractKnowledgePoints(currentSlide.id);
      startPolling(currentSlide.id);
    } catch (err) {
      console.error('KP extraction failed:', err);
      alert('KP extraction failed: ' + (err.response?.data?.error || err.message));
      setExtracting(false);
      setExtractStatus('');
    }
  };

  const pages = currentSlide?.pages || [];

  return (
    <>
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-icon">📄</span>
          Slides Document
        </div>
        {currentSlide && (
          <div className="panel-status">
            {currentSlide.original_filename} — Page {currentPage + 1}/{pages.length || '?'}
          </div>
        )}
      </div>

      <div className="panel-body slides-panel-body">
        {currentSlide ? (
          <div className="slides-viewer">
            {/* Slide content */}
            <div className="slide-content">
              {pages.length > 0 && pages[currentPage]?.thumbnail_path ? (
                <div className="slide-image-wrapper">
                  <img
                    src={getPageImageUrl(pages[currentPage].id)}
                    alt={`Slide ${currentPage + 1}`}
                    className="slide-page-image"
                    draggable={false}
                  />
                </div>
              ) : pages.length > 0 ? (
                <div className="slide-text-content">
                  {pages[currentPage]?.content_text || 'No text extracted for this page.'}
                </div>
              ) : (
                <div className="slide-file-view">
                  <iframe
                    src={getSlideFileUrl(currentSlide.filename || '')}
                    title="Slide viewer"
                    className="slide-iframe"
                  />
                </div>
              )}
            </div>

            {/* Navigation */}
            {pages.length > 1 && (
              <div className="slide-nav">
                <button
                  className="slide-nav-btn"
                  disabled={currentPage === 0}
                  onClick={() => setCurrentPage((p) => p - 1)}
                >
                  ◀ Prev
                </button>
                <span className="slide-nav-info">
                  {currentPage + 1} / {pages.length}
                </span>
                <button
                  className="slide-nav-btn"
                  disabled={currentPage >= pages.length - 1}
                  onClick={() => setCurrentPage((p) => p + 1)}
                >
                  Next ▶
                </button>
              </div>
            )}

            {/* Knowledge point anchors */}
            {pages[currentPage]?.knowledge_points?.length > 0 && (
              <div className="slide-knowledge-points">
                <h4>Knowledge Points</h4>
                {pages[currentPage].knowledge_points.map((kp) => {
                  const isActive = kp.video_timestamp != null &&
                    currentVideoTime >= kp.video_timestamp &&
                    currentVideoTime < kp.video_timestamp + 30;
                  return (
                    <div
                      key={kp.id}
                      className={`knowledge-point-tag ${kp.confidence >= 0.7 ? 'high-confidence' : kp.confidence >= 0.4 ? 'med-confidence' : 'low-confidence'} ${isActive ? 'kp-active' : ''}`}
                      onClick={() => kp.video_timestamp != null && onJumpToTimestamp(kp.video_timestamp)}
                      title={kp.content}
                    >
                      <span className="kp-title">📌 {kp.title}</span>
                      <span className="kp-meta">
                        {kp.video_timestamp != null && (
                          <span className="kp-timestamp">🎬 {Math.floor(kp.video_timestamp / 60)}:{String(Math.floor(kp.video_timestamp % 60)).padStart(2, '0')}</span>
                        )}
                        {kp.confidence > 0 && (
                          <span className={`kp-confidence ${kp.confidence >= 0.7 ? 'high' : kp.confidence >= 0.4 ? 'med' : 'low'}`}>
                            {Math.round(kp.confidence * 100)}%
                          </span>
                        )}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Extract KP button */}
            {currentSlide?.processed && (
              <div className="slide-extract-kp">
                <button
                  className="extract-kp-btn"
                  onClick={handleExtractKP}
                  disabled={extracting}
                >
                  {extracting ? `⏳ ${extractStatus || 'Extracting...'}` : '🧠 Extract Knowledge Points'}
                </button>
              </div>
            )}

            {/* Slide list sidebar */}
            <div className="slides-list">
              {slides.map((s) => (
                <div
                  key={s.id}
                  className={`slides-list-item ${s.id === currentSlide.id ? 'active' : ''}`}
                  onClick={() => { setCurrentSlide(s); setCurrentPage(0); }}
                >
                  <span className="slides-list-name">{s.original_filename}</span>
                  <button
                    className="slides-list-delete"
                    onClick={(e) => { e.stopPropagation(); handleDelete(s.id); }}
                  >×</button>
                </div>
              ))}
              <button
                className="slides-add-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                + Add Slides
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.ppt,.pptx"
                style={{ display: 'none' }}
                onChange={(e) => {
                  if (e.target.files[0]) handleUpload(e.target.files[0]);
                  e.target.value = '';
                }}
              />
            </div>
          </div>
        ) : (
          /* Upload area — matches Figma prototype */
          <div className="slides-upload-area">
            <div className="upload-placeholder">
              <span className="upload-icon">📤</span>
              <h3>Upload Learning Materials</h3>
              <p>AI will automatically parse content and link video knowledge points</p>

              <div
                className={`upload-dropzone ${dragOver ? 'drag-over' : ''} ${uploading ? 'disabled' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => !uploading && fileInputRef.current?.click()}
              >
                <div className="upload-format-icons">
                  <span className="format-badge pdf">PDF</span>
                  <span className="format-badge ppt">PPT</span>
                </div>
                <p>{uploading ? 'Uploading...' : 'Drag and drop files here, or'}</p>
                {!uploading && <span className="upload-link">Click to select files</span>}
                <p className="upload-hint">Supports .pdf, .ppt, .pptx formats</p>
              </div>

              <div className="demo-banner">
                💡 Demo Mode: Upload any file to experience the full workflow
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.ppt,.pptx"
                style={{ display: 'none' }}
                onChange={(e) => {
                  if (e.target.files[0]) handleUpload(e.target.files[0]);
                  e.target.value = '';
                }}
              />
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default SlidesPanel;