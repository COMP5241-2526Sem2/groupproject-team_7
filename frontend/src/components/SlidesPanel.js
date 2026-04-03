import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  uploadSlide,
  getSlidesByCourse,
  getPageImageUrl,
  getSlideFileUrl,
  deleteSlide,
  extractKnowledgePoints,
  getExtractKPStatus,
  getSlide,
} from '../services/api';
import {
  ChevronRight,
  ChevronLeft,
  FileText,
  Sparkles,
  Highlighter,
  Layers,
} from 'lucide-react';
import clsx from 'clsx';

function SlidesPanel({
  courseId,
  courseTitle,
  onJumpToTimestamp,
  currentVideoTime,
  targetSlidePage,
}) {
  const [slides, setSlides] = useState([]);
  const [currentSlide, setCurrentSlide] = useState(null);
  const [currentPage, setCurrentPage] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractStatus, setExtractStatus] = useState('');
  const [selection, setSelection] = useState(null);
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);
  const contentRef = useRef(null);

  useEffect(() => {
    if (courseId) {
      setSlides([]);
      setCurrentSlide(null);
      setCurrentPage(0);
      loadSlides();
    } else {
      setSlides([]);
      setCurrentSlide(null);
      setCurrentPage(0);
    }
  }, [courseId]);

  useEffect(() => {
    if (!targetSlidePage) return;
    const { slideId, pageNumber } = targetSlidePage;
    const targetSlide = slides.find((s) => s.id === slideId);
    if (targetSlide) {
      setCurrentSlide(targetSlide);
      const pageIndex = (targetSlide.pages || []).findIndex(
        (p) => p.page_number === pageNumber
      );
      if (pageIndex >= 0) setCurrentPage(pageIndex);
    }
  }, [targetSlidePage, slides]);

  const loadSlides = async () => {
    try {
      const res = await getSlidesByCourse(courseId);
      setSlides(res.data);
      if (res.data.length > 0) {
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
    const allowed = [
      'application/pdf',
      'application/vnd.ms-powerpoint',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    ];
    if (!allowed.includes(file.type) && !/\.(pdf|ppt|pptx)$/i.test(file.name)) {
      alert('Please upload a PDF, PPT, or PPTX file.');
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
        const remaining = slides.filter((s) => s.id !== id);
        setCurrentSlide(remaining[0] || null);
        setCurrentPage(0);
      }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    if (!currentSlide) return;
    if (pollRef.current) clearInterval(pollRef.current);
    getExtractKPStatus(currentSlide.id)
      .then((res) => {
        if (res.data?.state === 'running') {
          setExtracting(true);
          setExtractStatus(res.data.message || 'Extracting...');
          startPolling(currentSlide.id);
        }
      })
      .catch(() => {});
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
          try {
            const slideRes = await getSlide(slideId);
            setCurrentSlide(slideRes.data);
            setSlides((prev) =>
              prev.map((s) => (s.id === slideRes.data.id ? slideRes.data : s))
            );
          } catch {}
          if (st.created === 0) {
            alert('Knowledge points already exist for all pages.');
          }
        } else if (st.state === 'error') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setExtracting(false);
          setExtractStatus('');
          alert('Knowledge point extraction failed: ' + (st.error || 'Unknown error'));
        }
      } catch {
        // ignore
      }
    }, 3000);
  };

  const handleExtractKP = async () => {
    if (!currentSlide || extracting) return;
    setExtracting(true);
    setExtractStatus('Starting...');
    try {
      await extractKnowledgePoints(currentSlide.id);
      startPolling(currentSlide.id);
    } catch (err) {
      console.error('KP extraction failed:', err);
      alert('Knowledge point extraction failed: ' + (err.response?.data?.error || err.message));
      setExtracting(false);
      setExtractStatus('');
    }
  };

  const pages = currentSlide?.pages || [];

  const handleTextMouseUp = useCallback(() => {
    const sel = window.getSelection();
    const text = sel?.toString()?.trim();
    if (!text || text.length < 2) {
      setSelection(null);
      return;
    }
    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    setSelection({
      text,
      x: rect.left + rect.width / 2,
      y: rect.top,
    });
  }, []);

  useEffect(() => {
    const onDocClick = () => setSelection(null);
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const chapterLabel = currentSlide?.original_filename || 'Slides';

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-[#FFFBF7]/30">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-stone-200/90 px-5 py-4">
        <div className="flex min-w-0 flex-wrap items-center gap-1 text-xs text-stone-500">
          <span className="max-w-[140px] truncate font-medium text-stone-800">
            {courseTitle || 'Untitled Course'}
          </span>
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-stone-400" />
          <span className="flex min-w-0 items-center gap-1 text-stone-700">
            <FileText className="h-3.5 w-3.5 shrink-0 text-red-800/85" />
            <span className="truncate">{chapterLabel}</span>
          </span>
        </div>
        {currentSlide && (
          <span className="rounded-full border border-stone-200/90 bg-[#F5EFE3]/90 px-2.5 py-0.5 text-[11px] text-stone-600">
            Page {currentPage + 1} / {pages.length || '?'}
          </span>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-hidden p-5">
        {currentSlide ? (
          <div className="flex h-full min-h-0 flex-col gap-4">
            <div
              ref={contentRef}
              className="relative min-h-0 flex-1 overflow-hidden rounded-card border border-stone-200/80 bg-[#FAF8F3] shadow-[0_4px_32px_rgba(92,33,33,0.06)]"
            >
              <div
                className="h-full overflow-auto p-4"
                onMouseUp={handleTextMouseUp}
              >
                {pages.length > 0 && pages[currentPage]?.thumbnail_path ? (
                  <div className="flex justify-center">
                    <img
                      src={getPageImageUrl(pages[currentPage].id)}
                      alt={`Slide ${currentPage + 1}`}
                      className="max-h-[min(52vh,560px)] w-auto rounded-inner shadow-lg ring-1 ring-black/5"
                      draggable={false}
                    />
                  </div>
                ) : pages.length > 0 ? (
                  <div className="prose prose-sm max-w-none text-stone-800 selection:bg-red-100/90">
                    {pages[currentPage]?.content_text || 'No text available on this page.'}
                  </div>
                ) : (
                  <div className="h-[min(52vh,560px)] w-full overflow-hidden rounded-inner bg-white shadow-inner ring-1 ring-black/5">
                    <iframe
                      src={getSlideFileUrl(currentSlide.filename || '')}
                      title="Slide viewer"
                      className="h-full w-full"
                    />
                  </div>
                )}
              </div>

              {pages.length > 1 && (
                <>
                  <button
                    type="button"
                    disabled={currentPage === 0}
                    onClick={() => setCurrentPage((p) => p - 1)}
                    className="absolute left-3 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-stone-300/90 bg-white/90 text-stone-800 shadow-md backdrop-blur-md transition hover:border-red-800/25 hover:bg-[#FFFBF7] disabled:opacity-30"
                    aria-label="Previous page"
                  >
                    <ChevronLeft className="h-5 w-5" />
                  </button>
                  <button
                    type="button"
                    disabled={currentPage >= pages.length - 1}
                    onClick={() => setCurrentPage((p) => p + 1)}
                    className="absolute right-3 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-stone-300/90 bg-white/90 text-stone-800 shadow-md backdrop-blur-md transition hover:border-red-800/25 hover:bg-[#FFFBF7] disabled:opacity-30"
                    aria-label="Next page"
                  >
                    <ChevronRight className="h-5 w-5" />
                  </button>
                </>
              )}

              {selection && (
                <div
                  className="pointer-events-auto fixed z-50 flex -translate-x-1/2 -translate-y-full gap-1 rounded-control border border-stone-200/90 bg-white p-1 shadow-lg backdrop-blur-md"
                  style={{ left: selection.x, top: selection.y - 8 }}
                  onMouseDown={(e) => e.stopPropagation()}
                >
                  <button
                    type="button"
                    className="flex items-center gap-1 rounded px-2 py-1 text-[11px] text-stone-800 hover:bg-[#F5EFE3]"
                    onClick={() => {
                      window.dispatchEvent(
                        new CustomEvent('synclearn-ask-ai', {
                          detail: { text: selection.text },
                        })
                      );
                      setSelection(null);
                    }}
                  >
                    <Sparkles className="h-3.5 w-3.5 text-red-800" />
                    Ask AI
                  </button>
                  <button
                    type="button"
                    className="flex items-center gap-1 rounded px-2 py-1 text-[11px] text-stone-800 hover:bg-[#F5EFE3]"
                    onClick={() => setSelection(null)}
                  >
                    <Highlighter className="h-3.5 w-3.5 text-amber-700" />
                    Highlight
                  </button>
                  <button
                    type="button"
                    className="flex items-center gap-1 rounded px-2 py-1 text-[11px] text-stone-800 hover:bg-[#F5EFE3]"
                    onClick={() => setSelection(null)}
                  >
                    <Layers className="h-3.5 w-3.5 text-emerald-700" />
                    Card
                  </button>
                </div>
              )}
            </div>

            {pages.length > 0 && (
              <div className="shrink-0 rounded-inner border border-stone-200/90 bg-white/70 p-3 shadow-sm backdrop-blur-sm">
                <p className="mb-2 px-1 text-[10px] font-medium uppercase tracking-wide text-stone-500">
                  Page Thumbnails
                </p>
                <div className="flex gap-2 overflow-x-auto pb-1 pt-0.5">
                  {pages.map((p, idx) => (
                    <button
                      key={p.id || idx}
                      type="button"
                      onClick={() => setCurrentPage(idx)}
                      className={clsx(
                        'group relative h-16 w-[4.5rem] shrink-0 overflow-hidden rounded-control border transition-all duration-200',
                        idx === currentPage
                          ? 'border-red-800/50 ring-2 ring-red-900/15'
                          : 'border-transparent hover:z-10 hover:scale-110 hover:border-stone-300 hover:shadow-md'
                      )}
                    >
                      {p.thumbnail_path ? (
                        <img
                          src={getPageImageUrl(p.id)}
                          alt=""
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center bg-stone-200 text-[10px] text-stone-600">
                          {idx + 1}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {pages[currentPage]?.knowledge_points?.length > 0 && (
              <div className="max-h-36 shrink-0 space-y-1.5 overflow-y-auto rounded-inner border border-stone-200/90 bg-white/75 p-3 shadow-sm">
                <p className="text-[10px] font-medium uppercase tracking-wide text-stone-500">
                  Knowledge Points
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {pages[currentPage].knowledge_points.map((kp) => {
                    const isActive =
                      kp.video_timestamp != null &&
                      currentVideoTime >= kp.video_timestamp &&
                      currentVideoTime < kp.video_timestamp + 30;
                    return (
                      <button
                        key={kp.id}
                        type="button"
                        onClick={() =>
                          kp.video_timestamp != null &&
                          onJumpToTimestamp(kp.video_timestamp)
                        }
                        title={kp.content}
                        className={clsx(
                          'max-w-full rounded-full border px-2 py-1 text-left text-[11px] transition',
                          isActive
                            ? 'border-red-800/40 bg-red-50 text-stone-900 shadow-sm'
                            : 'border-stone-200/90 bg-[#F5EFE3]/80 text-stone-700 hover:border-stone-300'
                        )}
                      >
                        {kp.title}
                        {kp.video_timestamp != null && (
                          <span className="ml-1 font-mono text-[10px] text-red-800/90">
                            {Math.floor(kp.video_timestamp / 60)}:
                            {String(Math.floor(kp.video_timestamp % 60)).padStart(
                              2,
                              '0'
                            )}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {currentSlide?.processed && (
              <div className="shrink-0">
                <button
                  type="button"
                  onClick={handleExtractKP}
                  disabled={extracting}
                  className="w-full rounded-control border border-red-800/25 bg-gradient-to-r from-red-50 to-[#F5EFE3] py-2.5 text-xs font-medium text-red-950 transition hover:border-red-800/40 disabled:opacity-50"
                >
                  {extracting
                    ? `${extractStatus || 'Extracting...'}`
                    : 'Extract Knowledge Points'}
                </button>
              </div>
            )}

            <div className="flex shrink-0 flex-wrap gap-2 border-t border-stone-200/80 pt-4">
              {slides.map((s) => (
                <div
                  key={s.id}
                  className={clsx(
                    'flex max-w-[200px] cursor-pointer items-center gap-1 rounded-full border px-2 py-1 text-[11px] transition',
                    s.id === currentSlide.id
                      ? 'border-red-800/40 bg-red-50 text-stone-900'
                      : 'border-stone-200/90 bg-white/80 text-stone-600 hover:border-stone-300'
                  )}
                  onClick={() => {
                    setCurrentSlide(s);
                    setCurrentPage(0);
                  }}
                >
                  <span className="min-w-0 flex-1 truncate">{s.original_filename}</span>
                  <button
                    type="button"
                    className="shrink-0 text-stone-400 hover:text-red-800"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(s.id);
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="rounded-full border border-dashed border-stone-300 px-3 py-1 text-[11px] text-stone-500 hover:border-red-800/35 hover:text-stone-700"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                + Add Slides
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.ppt,.pptx"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files[0]) handleUpload(e.target.files[0]);
                  e.target.value = '';
                }}
              />
            </div>
          </div>
        ) : (
          <div
            className={clsx(
              'flex h-full min-h-[280px] flex-col items-center justify-center gap-5 rounded-card border border-dashed border-stone-300/90 bg-[#F5EFE3]/40 p-10 text-center transition',
              dragOver && 'border-red-800/45 bg-red-50/70'
            )}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <div className="text-sm font-medium text-stone-800">Upload Learning Materials</div>
            <p className="max-w-sm text-xs text-stone-500">
              AI will parse content and align it with video knowledge points
            </p>
            <div
              className="w-full max-w-md cursor-pointer rounded-inner border border-stone-200/90 bg-white/80 px-6 py-8 shadow-sm transition hover:border-red-800/30"
              onClick={() => !uploading && fileInputRef.current?.click()}
            >
              <p className="text-xs text-stone-600">
                {uploading ? 'Uploading...' : 'Drag a file here, or click to choose'}
              </p>
              <p className="mt-2 text-[11px] text-stone-500">Supports PDF / PPT / PPTX</p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.ppt,.pptx"
              className="hidden"
              onChange={(e) => {
                if (e.target.files[0]) handleUpload(e.target.files[0]);
                e.target.value = '';
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default SlidesPanel;
