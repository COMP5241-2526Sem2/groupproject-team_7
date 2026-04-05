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

function isDirectVideoUrl(url) {
  return /\.(mp4|webm|ogg|mov)(\?.*)?$/i.test(url || '');
}

function getYoutubeEmbedUrl(url, startAt = null, seekToken = 0) {
  try {
    const parsed = new URL(url);
    const params = new URLSearchParams({
      enablejsapi: '1',
      playsinline: '1',
      rel: '0',
      modestbranding: '1',
    });
    if (typeof window !== 'undefined' && window.location?.origin) {
      params.set('origin', window.location.origin);
    }
    if (startAt != null && Number.isFinite(startAt)) {
      params.set('start', String(Math.max(0, Math.floor(startAt))));
      params.set('autoplay', '1');
      params.set('syncseek', String(seekToken));
    }
    if (parsed.hostname.includes('youtube.com')) {
      const videoId = parsed.searchParams.get('v');
      if (videoId) return `https://www.youtube.com/embed/${videoId}?${params.toString()}`;
      const pathParts = parsed.pathname.split('/').filter(Boolean);
      if (pathParts[0] === 'embed' && pathParts[1]) {
        return `https://www.youtube.com/embed/${pathParts[1]}?${params.toString()}`;
      }
      if (pathParts[0] === 'watch' && parsed.searchParams.get('v')) {
        return `https://www.youtube.com/embed/${parsed.searchParams.get('v')}?${params.toString()}`;
      }
    }
    if (parsed.hostname.includes('youtu.be')) {
      const videoId = parsed.pathname.split('/').filter(Boolean)[0];
      if (videoId) return `https://www.youtube.com/embed/${videoId}?${params.toString()}`;
    }
  } catch {
    return null;
  }
  return null;
}

function getVimeoEmbedUrl(url, startAt = null, seekToken = 0) {
  try {
    const parsed = new URL(url);
    if (!parsed.hostname.includes('vimeo.com')) return null;
    const videoId = parsed.pathname.split('/').filter(Boolean).pop();
    if (!videoId) return null;
    const params = new URLSearchParams({ api: '1', playsinline: '1' });
    if (startAt != null && Number.isFinite(startAt)) {
      params.set('autoplay', '1');
      params.set('syncseek', String(seekToken));
      return `https://player.vimeo.com/video/${videoId}?${params.toString()}#t=${Math.max(0, Math.floor(startAt))}s`;
    }
    return `https://player.vimeo.com/video/${videoId}?${params.toString()}`;
  } catch {
    return null;
  }
}

function getExternalProvider(url) {
  const youtube = getYoutubeEmbedUrl(url, null, 0);
  if (youtube) return 'youtube';
  const vimeo = getVimeoEmbedUrl(url, null, 0);
  if (vimeo) return 'vimeo';
  return null;
}

function getExternalPlaybackUrl(url, startAt = null, seekToken = 0) {
  return getYoutubeEmbedUrl(url, startAt, seekToken) || getVimeoEmbedUrl(url, startAt, seekToken) || null;
}

function isSupportedPreviewLink(value) {
  if (!value) return false;
  try {
    const parsed = new URL(value.trim());
    const host = (parsed.hostname || '').toLowerCase();
    const path = (parsed.pathname || '').toLowerCase();
    if (!/^https?:$/i.test(parsed.protocol)) return false;
    if (host.endsWith('youtube.com') || host.endsWith('youtu.be')) return true;
    if (host.endsWith('vimeo.com')) return true;
    return /\.(mp4|webm|ogg|mov)(\?.*)?$/i.test(path + parsed.search);
  } catch {
    return false;
  }
}

function pickPrimaryVideo(videos, preferredId = null) {
  if (!videos?.length) return null;
  const uploadedVideos = videos.filter((v) => v.source_type === 'uploaded');
  const pool = uploadedVideos.length ? uploadedVideos : videos;
  if (preferredId != null) {
    const preferred = pool.find((v) => v.id === preferredId);
    if (preferred) return preferred;
  }
  return pool[0] || null;
}

function VideoPlayer({
  courseId,
  seekTimestamp,
  seekSignal,
  preferredVideoId,
  onTimeUpdate,
  onJumpToSlide,
  onCurrentVideoChange,
}) {
  const PREVIEW_LINK_STORAGE_KEY = 'synclearn-preview-links-v1';
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
  const [externalSeekAt, setExternalSeekAt] = useState(null);
  const [externalSeekToken, setExternalSeekToken] = useState(0);
  const [previewLinks, setPreviewLinks] = useState({});
  const videoRef = useRef(null);
  const iframeRef = useRef(null);
  const fileInputRef = useRef(null);
  const hideChromeTimer = useRef(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(PREVIEW_LINK_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        setPreviewLinks(parsed);
      }
    } catch {
      setPreviewLinks({});
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(PREVIEW_LINK_STORAGE_KEY, JSON.stringify(previewLinks));
    } catch {
      // ignore
    }
  }, [previewLinks]);

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

  const loadVideos = async () => {
    try {
      const res = await getVideosByCourse(courseId);
      setVideos(res.data);
      setCurrentVideo(preferredVideoId ? pickPrimaryVideo(res.data, preferredVideoId) : null);
    } catch {
      // API not available yet
    }
  };

  useEffect(() => {
    if (!preferredVideoId || !videos.length) return;
    const preferred = pickPrimaryVideo(videos, preferredVideoId);
    if (preferred && preferred.id !== currentVideo?.id) {
      setCurrentVideo(preferred);
    }
  }, [preferredVideoId, videos, currentVideo?.id]);

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
      return;
    }

    if (!iframeRef.current?.contentWindow) return;
    if (externalProvider === 'youtube') {
      setExternalSeekAt(t);
      setExternalSeekToken((v) => v + 1);
      iframeRef.current.contentWindow.postMessage(
        JSON.stringify({ event: 'command', func: 'seekTo', args: [t, true] }),
        '*'
      );
      iframeRef.current.contentWindow.postMessage(
        JSON.stringify({ event: 'command', func: 'playVideo', args: [] }),
        '*'
      );
      return;
    }

    if (externalProvider === 'vimeo') {
      setExternalSeekAt(t);
      setExternalSeekToken((v) => v + 1);
      iframeRef.current.contentWindow.postMessage({ method: 'setCurrentTime', value: t }, '*');
      iframeRef.current.contentWindow.postMessage({ method: 'play' }, '*');
      return;
    }
  };

  const onProgressClick = (e) => {
    if (!duration || (!videoRef.current && !iframeRef.current)) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    seekTo(Math.max(0, Math.min(duration, pct * duration)));
  };

  const currentVideoPreviewUrl =
    currentVideo?.source_type === 'uploaded' ? previewLinks[currentVideo?.id] || null : null;
  const effectiveExternalUrl = currentVideoPreviewUrl || (currentVideo?.source_type === 'external' ? currentVideo?.external_url : null);

  const videoScopedKnowledgePoints = knowledgePoints.filter(
    (kp) => kp.video_timestamp != null && (kp.video_id == null || kp.video_id === currentVideo?.id)
  );
  const heatBuckets = buildHeatBuckets(videoScopedKnowledgePoints, duration);
  const currentVideoSrc = getVideoStreamUrl(currentVideo?.filename || '');
  const isExternalVideo = Boolean(effectiveExternalUrl);
  const externalProvider = isExternalVideo ? getExternalProvider(effectiveExternalUrl) : null;
  const externalPlaybackUrl = isExternalVideo
    ? getExternalPlaybackUrl(effectiveExternalUrl, externalSeekAt, externalSeekToken)
    : null;
  const canPlayDirectly = !isExternalVideo || isDirectVideoUrl(effectiveExternalUrl);
  const canShowTimeline = canPlayDirectly;

  useEffect(() => {
    if (!seekTimestamp || seekTimestamp <= 0) return;
    seekTo(seekTimestamp);
  }, [seekTimestamp, seekSignal, currentVideo?.id]);

  useEffect(() => {
    if (canPlayDirectly) return;
    const fallbackDuration = Number(currentVideo?.duration || 0);
    if (fallbackDuration > 0) {
      setDuration(fallbackDuration);
    }
  }, [canPlayDirectly, currentVideo?.id, currentVideo?.duration]);

  useEffect(() => {
    setExternalSeekAt(null);
    setExternalSeekToken(0);
  }, [currentVideo?.id]);

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
      setPreviewLinks((prev) => {
        if (!(id in prev)) return prev;
        const next = { ...prev };
        delete next[id];
        return next;
      });
      if (currentVideo?.id === id) {
        setCurrentVideo(videos.length > 1 ? videos.find((v) => v.id !== id) : null);
      }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleBindPreviewLink = () => {
    if (!currentVideo || currentVideo.source_type !== 'uploaded') return;
    const existing = previewLinks[currentVideo.id] || '';
    const value = window.prompt('Bind a preview link for this uploaded video (YouTube/Vimeo/direct file):', existing);
    if (value == null) return;
    const normalized = value.trim();
    if (!normalized) {
      setPreviewLinks((prev) => {
        if (!(currentVideo.id in prev)) return prev;
        const next = { ...prev };
        delete next[currentVideo.id];
        return next;
      });
      return;
    }
    if (!isSupportedPreviewLink(normalized)) {
      alert('Unsupported link. Please use YouTube/Vimeo or a direct video file URL.');
      return;
    }
    setPreviewLinks((prev) => ({ ...prev, [currentVideo.id]: normalized }));
  };

  const activeSyncKp = (() => {
    const sorted = [...videoScopedKnowledgePoints]
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
        {currentVideo?.source_type === 'uploaded' && (
          <button
            type="button"
            onClick={handleBindPreviewLink}
            className="shrink-0 rounded-control border border-stone-300/90 bg-white/80 px-2.5 py-1 text-[11px] text-stone-700 transition hover:border-red-800/35"
            title="Bind an external preview link while keeping backend alignment on this uploaded video"
          >
            {currentVideoPreviewUrl ? 'Edit Preview Link' : 'Bind Preview Link'}
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {currentVideo ? (
          <div className="flex flex-col gap-3">
            <div
              className="relative w-full overflow-hidden rounded-inner border border-white/10 bg-black/40 shadow-inner"
              style={{ aspectRatio: '16 / 9', maxHeight: 'min(52vh, 640px)' }}
              onMouseEnter={() => setHovering(true)}
              onMouseMove={onMouseMoveOnVideo}
              onMouseLeave={() => {
                if (videoRef.current?.paused) setHovering(true);
                else scheduleHideChrome();
              }}
            >
              {canPlayDirectly ? (
                <video
                  ref={videoRef}
                  src={currentVideoSrc}
                  className="h-full w-full object-contain"
                  playsInline
                  onTimeUpdate={handleTimeUpdate}
                  onLoadedMetadata={handleLoadedMetadata}
                  onPlay={() => { setPaused(false); setHovering(true); }}
                  onPause={() => { setPaused(true); setHovering(true); }}
                />
              ) : externalPlaybackUrl ? (
                <iframe
                  ref={iframeRef}
                  src={externalPlaybackUrl}
                  title={currentVideo.original_filename}
                  className="h-full w-full"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  allowFullScreen
                />
              ) : (
                <iframe
                  ref={iframeRef}
                  src={currentVideo.external_url}
                  title={currentVideo.original_filename}
                  className="h-full w-full"
                  allow="autoplay; fullscreen; picture-in-picture"
                  allowFullScreen
                />
              )}

              {canPlayDirectly && paused && (
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

              {canShowTimeline && (
                <div
                  className={clsx(
                    'absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent px-3 pb-2 pt-10 transition-opacity duration-300',
                    canPlayDirectly
                      ? (hovering || paused ? 'opacity-100' : 'opacity-0 pointer-events-none')
                      : 'opacity-100'
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
                    {videoScopedKnowledgePoints
                      .filter((kp) => duration > 0)
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
                    {canPlayDirectly ? (
                      <>
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
                      </>
                    ) : (
                      <span className="text-[11px] text-stone-200">
                        External video preview only
                      </span>
                    )}
                  </div>
                </div>
              )}

              {isExternalVideo && !canPlayDirectly && (
                <div className="absolute right-3 top-3 rounded-control border border-white/15 bg-black/45 px-3 py-1.5 text-[11px] text-stone-100 backdrop-blur-md">
                  External preview (alignment still uses uploaded video)
                </div>
              )}
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
