import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  uploadVideo,
  getVideosByCourse,
  getVideoStreamUrl,
  deleteVideo,
  getKnowledgePointsByCourse,
} from '../services/api';
import {
  Play,
  Pause,
  Film,
  ChevronRight,
} from 'lucide-react';
import clsx from 'clsx';

function buildHeatBuckets(knowledgePoints, duration, segments = 56) {
  const buckets = new Array(segments).fill(0);
  if (!duration || duration <= 0) return buckets.map(() => 0);
  knowledgePoints.forEach((kp) => {
    if (kp.video_timestamp == null) return;
    const i = Math.min(
      segments - 1,
      Math.floor((kp.video_timestamp / duration) * segments)
    );
    buckets[i] += (kp.confidence ?? 0.45) + 0.15;
  });
  const max = Math.max(...buckets, 1e-6);
  return buckets.map((b) => b / max);
}

function formatTime(sec) {
  if (sec == null || Number.isNaN(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function VideoPlayer({
  courseId,
  seekTimestamp,
  onTimeUpdate,
  onJumpToSlide,
  onCurrentVideoChange,
}) {
  const [videos, setVideos] = useState([]);
  const [currentVideo, setCurrentVideo] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const [knowledgePoints, setKnowledgePoints] = useState([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [paused, setPaused] = useState(true);
  const [hovering, setHovering] = useState(false);
  const videoRef = useRef(null);
  const fileInputRef = useRef(null);
  const hideChromeTimer = useRef(null);

  useEffect(() => {
    onCurrentVideoChange?.(currentVideo?.id ?? null);
  }, [currentVideo?.id, onCurrentVideoChange]);

  useEffect(() => {
    if (courseId) {
      setVideos([]);
      setCurrentVideo(null);
      setUploadProgress(0);
      loadVideos();
      loadKnowledgePoints();
    } else {
      setVideos([]);
      setCurrentVideo(null);
      setKnowledgePoints([]);
      setUploadProgress(0);
    }
  }, [courseId]);

  const loadKnowledgePoints = async () => {
    try {
      const res = await getKnowledgePointsByCourse(courseId);
      setKnowledgePoints(res.data || []);
    } catch {
      setKnowledgePoints([]);
    }
  };

  useEffect(() => {
    if (videoRef.current && seekTimestamp > 0) {
      videoRef.current.currentTime = seekTimestamp;
      videoRef.current.play().catch(() => {});
    }
  }, [seekTimestamp]);

  const loadVideos = async () => {
    try {
      const res = await getVideosByCourse(courseId);
      setVideos(res.data);
      if (res.data.length > 0) {
        setCurrentVideo(res.data[0]);
      }
    } catch {
      // API not available yet
    }
  };

  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current) {
      const t = videoRef.current.currentTime;
      setCurrentTime(t);
      onTimeUpdate?.(t);
    }
  }, [onTimeUpdate]);

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration || 0);
    }
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play().catch(() => {});
    } else {
      videoRef.current.pause();
    }
  };

  const seekTo = (t) => {
    if (videoRef.current) {
      videoRef.current.currentTime = t;
      videoRef.current.play().catch(() => {});
    }
  };

  const onProgressClick = (e) => {
    if (!duration || !videoRef.current) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    seekTo(Math.max(0, Math.min(duration, pct * duration)));
  };

  const heatBuckets = buildHeatBuckets(knowledgePoints, duration);

  const handleUpload = async (file) => {
    if (!courseId) {
      alert('Please create or select a course first.');
      return;
    }
    if (!file) return;
    const allowedTypes = ['video/mp4', 'video/webm', 'video/ogg', 'video/quicktime'];
    const allowedExts = /\.(mp4|webm|ogg|mov)$/i;
    if (!allowedTypes.includes(file.type) && !allowedExts.test(file.name)) {
      alert('Please upload an MP4, WebM, OGG, or MOV video.');
      return;
    }
    setUploading(true);
    setUploadProgress(0);
    try {
      const res = await uploadVideo(courseId, file, (progressEvent) => {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        setUploadProgress(percent);
      });
      setVideos((prev) => [...prev, res.data]);
      if (!currentVideo) setCurrentVideo(res.data);
      loadKnowledgePoints();
    } catch (err) {
      console.error('Upload failed:', err);
      alert('Upload failed: ' + (err.response?.data?.error || err.message));
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteVideo(id);
      setVideos((prev) => prev.filter((v) => v.id !== id));
      if (currentVideo?.id === id) {
        setCurrentVideo(videos.length > 1 ? videos.find((v) => v.id !== id) : null);
      }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const activeSyncKp = (() => {
    const sorted = [...knowledgePoints]
      .filter((kp) => kp.video_timestamp != null)
      .sort((a, b) => a.video_timestamp - b.video_timestamp);
    let active = null;
    for (let i = sorted.length - 1; i >= 0; i--) {
      if (currentTime >= sorted[i].video_timestamp) {
        active = sorted[i];
        break;
      }
    }
    return active;
  })();

  const scheduleHideChrome = () => {
    if (hideChromeTimer.current) clearTimeout(hideChromeTimer.current);
    hideChromeTimer.current = setTimeout(() => {
      if (!videoRef.current?.paused) setHovering(false);
    }, 2600);
  };

  const onMouseMoveOnVideo = () => {
    setHovering(true);
    scheduleHideChrome();
  };

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-[#FFFBF7]/50">
      <div className="flex items-center justify-between border-b border-stone-200/90 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-red-50 ring-1 ring-red-900/15">
            <Film className="h-4 w-4 text-red-800" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-xs font-semibold text-stone-800">Smart Video</p>
            <p className="truncate text-[11px] text-stone-500">
              {currentVideo ? currentVideo.original_filename : 'No video loaded'}
            </p>
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {currentVideo ? (
          <div className="flex flex-col gap-3">
            <div
              className="relative w-full overflow-hidden rounded-inner border border-white/10 bg-black/40 shadow-inner"
              style={{ aspectRatio: '16 / 9' }}
              onMouseEnter={() => setHovering(true)}
              onMouseMove={onMouseMoveOnVideo}
              onMouseLeave={() => {
                if (videoRef.current?.paused) setHovering(true);
                else scheduleHideChrome();
              }}
            >
              <video
                ref={videoRef}
                src={getVideoStreamUrl(currentVideo.filename)}
                className="h-full w-full object-contain"
                playsInline
                onTimeUpdate={handleTimeUpdate}
                onLoadedMetadata={handleLoadedMetadata}
                onPlay={() => { setPaused(false); setHovering(true); }}
                onPause={() => { setPaused(true); setHovering(true); }}
              />

              {paused && (
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/20">
                  <button
                    type="button"
                    onClick={togglePlay}
                    className="pointer-events-auto flex h-14 w-14 items-center justify-center rounded-full border border-white/20 bg-white/10 backdrop-blur-md transition hover:bg-white/15"
                    aria-label="Play"
                  >
                    <Play className="h-7 w-7 text-white" fill="currentColor" />
                  </button>
                </div>
              )}

              <div
                className={clsx(
                  'absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent px-3 pb-2 pt-10 transition-opacity duration-300',
                  hovering || paused ? 'opacity-100' : 'opacity-0 pointer-events-none'
                )}
              >
                <div className="mb-2 rounded-control border border-white/15 bg-black/35 px-2 py-1.5 backdrop-blur-md">
                  <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-stone-300">
                    Knowledge Heatmap
                  </p>
                  <div className="flex h-5 w-full gap-px overflow-hidden rounded-sm bg-black/50">
                    {heatBuckets.map((intensity, i) => (
                      <button
                        key={i}
                        type="button"
                        title="Jump to timestamp"
                        onClick={(e) => {
                          e.stopPropagation();
                          const t = ((i + 0.5) / heatBuckets.length) * (duration || 0);
                          seekTo(t);
                        }}
                        className="h-full min-w-0 flex-1 rounded-[1px] transition hover:brightness-125"
                        style={{
                          background: `linear-gradient(180deg, rgba(185,28,28,${0.2 + intensity * 0.75}) 0%, rgba(234,179,8,${0.12 + intensity * 0.45}) 100%)`,
                        }}
                      />
                    ))}
                  </div>
                </div>

                <div
                  className="relative mb-2 h-2 cursor-pointer rounded-full bg-stone-900/90"
                  onClick={onProgressClick}
                  role="slider"
                  aria-valuenow={currentTime}
                  aria-valuemin={0}
                  aria-valuemax={duration}
                >
                  <div
                    className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-red-600 to-red-900"
                    style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }}
                  />
                  {knowledgePoints
                    .filter((kp) => kp.video_timestamp != null && duration > 0)
                    .map((kp) => (
                      <button
                        key={kp.id}
                        type="button"
                        title={kp.title || 'Knowledge point'}
                        onClick={(e) => {
                          e.stopPropagation();
                          seekTo(kp.video_timestamp);
                          if (kp.slide_id != null && kp.page_number != null) {
                            onJumpToSlide?.(kp.slide_id, kp.page_number);
                          }
                        }}
                        className="absolute top-1/2 h-3 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-amber-300 shadow-[0_0_8px_rgba(251,191,36,0.65)] ring-1 ring-white/35"
                        style={{ left: `${(kp.video_timestamp / duration) * 100}%` }}
                      />
                    ))}
                </div>

                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={togglePlay}
                    className="flex h-9 w-9 items-center justify-center rounded-control border border-white/15 bg-white/10 text-white backdrop-blur-md hover:bg-white/15"
                    aria-label={paused ? 'Play' : 'Pause'}
                  >
                    {paused ? (
                      <Play className="h-4 w-4" fill="currentColor" />
                    ) : (
                      <Pause className="h-4 w-4" />
                    )}
                  </button>
                  <span className="font-mono text-[11px] text-stone-100">
                    {formatTime(currentTime)} / {formatTime(duration)}
                  </span>
                </div>
              </div>
            </div>

            {activeSyncKp && (
              <button
                type="button"
                onClick={() =>
                  onJumpToSlide?.(activeSyncKp.slide_id, activeSyncKp.page_number)
                }
                className="flex w-full items-center justify-between gap-2 rounded-inner border border-red-800/20 bg-red-50/90 px-3 py-2.5 text-left text-xs text-stone-800 shadow-sm transition hover:border-red-800/35 hover:bg-[#F5EFE3]"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <ChevronRight className="h-4 w-4 shrink-0 text-red-800" />
                  <span className="truncate">
                    Synced slide p.{activeSyncKp.page_number}: {activeSyncKp.title}
                  </span>
                </span>
                <span className="shrink-0 text-[10px] text-red-900/80">Jump</span>
              </button>
            )}

            {videos.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-[10px] font-medium uppercase tracking-wide text-stone-500">
                  Video List
                </p>
                <div className="flex max-h-28 flex-col gap-1 overflow-y-auto pr-1">
                  {videos.map((v) => (
                    <div
                      key={v.id}
                      className={clsx(
                        'flex cursor-pointer items-center gap-2 rounded-control border px-2 py-1.5 text-xs transition',
                        v.id === currentVideo.id
                          ? 'border-red-800/35 bg-red-50 text-stone-900'
                          : 'border-transparent bg-white/70 text-stone-600 hover:border-stone-200 hover:bg-[#F5EFE3]/90'
                      )}
                      onClick={() => setCurrentVideo(v)}
                    >
                      <Play className="h-3 w-3 shrink-0 opacity-70" />
                      <span className="min-w-0 flex-1 truncate">{v.original_filename}</span>
                      <button
                        type="button"
                        className="shrink-0 rounded p-0.5 text-stone-400 hover:bg-red-50 hover:text-red-800"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(v.id);
                        }}
                        title="Delete"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    className="rounded-control border border-dashed border-stone-300/90 bg-transparent py-1.5 text-center text-xs text-stone-500 hover:border-red-800/35 hover:text-stone-700"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                  >
                    {uploading ? `Uploading ${uploadProgress}%` : '+ Add Video'}
                  </button>
                </div>
              </div>
            )}

            <input
              ref={fileInputRef}
              type="file"
              accept="video/mp4,video/webm,video/ogg"
              className="hidden"
              onChange={(e) => {
                if (e.target.files[0]) handleUpload(e.target.files[0]);
                e.target.value = '';
              }}
            />
          </div>
        ) : (
          <div
            className={clsx(
              'flex flex-col items-center justify-center gap-4 rounded-inner border border-dashed border-stone-300/90 bg-[#F5EFE3]/50 p-6 text-center transition',
              dragOver && 'border-red-800/40 bg-red-50/80'
            )}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const f = e.dataTransfer.files[0];
              if (f) handleUpload(f);
            }}
          >
            <p className="text-sm font-medium text-stone-800">Upload Class Recording</p>
            <p className="max-w-xs text-xs text-stone-500">
              AI will index content and align it with slide knowledge points
            </p>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="rounded-control bg-gradient-to-r from-red-800 to-red-950 px-4 py-2 text-sm text-[#FFFBF7] shadow-glass disabled:opacity-50"
            >
              {uploading ? `Uploading ${uploadProgress}%` : 'Choose Video File'}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="video/mp4,video/webm,video/ogg"
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

export default VideoPlayer;
