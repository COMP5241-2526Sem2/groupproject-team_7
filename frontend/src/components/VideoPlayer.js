import React, { useState, useEffect, useRef } from 'react';
import { uploadVideo, getVideosByCourse, getVideoStreamUrl, deleteVideo, transcribeVideo, getTranscribeStatus, getVideoTranscript, getKnowledgePointsByCourse } from '../services/api';
import '../styles/VideoPlayer.css';

function VideoPlayer({ courseId, seekTimestamp, onTimeUpdate, onJumpToSlide }) {
  const [videos, setVideos] = useState([]);
  const [currentVideo, setCurrentVideo] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [transcript, setTranscript] = useState([]);
  const [knowledgePoints, setKnowledgePoints] = useState([]);
  const [currentTime, setCurrentTime] = useState(0);
  const videoRef = useRef(null);
  const fileInputRef = useRef(null);
  const transcriptRef = useRef(null);

  useEffect(() => {
    if (courseId) {
      loadVideos();
      loadKnowledgePoints();
    } else {
      setVideos([]);
      setCurrentVideo(null);
      setKnowledgePoints([]);
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

  // Seek to timestamp when parent requests it
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
      if (res.data.length > 0 && !currentVideo) {
        setCurrentVideo(res.data[0]);
      }
    } catch {
      // API not available yet
    }
  };

  // Load transcript when video changes
  useEffect(() => {
    if (currentVideo) {
      loadTranscript(currentVideo.id);
      // Resume polling if ASR is already running
      getTranscribeStatus(currentVideo.id).then((res) => {
        if (res.data.state === 'running') {
          setTranscribing(true);
          const poll = setInterval(async () => {
            try {
              const s = await getTranscribeStatus(currentVideo.id);
              if (s.data.state === 'done') {
                clearInterval(poll);
                await loadTranscript(currentVideo.id);
                setTranscribing(false);
              } else if (s.data.state === 'error') {
                clearInterval(poll);
                setTranscribing(false);
              }
            } catch {
              clearInterval(poll);
              setTranscribing(false);
            }
          }, 5000);
        }
      }).catch(() => {});
    } else {
      setTranscript([]);
    }
  }, [currentVideo?.id]);

  const loadTranscript = async (videoId) => {
    try {
      const res = await getVideoTranscript(videoId);
      setTranscript(res.data || []);
    } catch {
      setTranscript([]);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const t = videoRef.current.currentTime;
      setCurrentTime(t);
      if (onTimeUpdate) onTimeUpdate(t);
    }
  };

  const handleTranscribe = async () => {
    if (!currentVideo || transcribing) return;
    setTranscribing(true);
    try {
      await transcribeVideo(currentVideo.id);
      // Poll for completion
      const poll = setInterval(async () => {
        try {
          const res = await getTranscribeStatus(currentVideo.id);
          const { state, error } = res.data;
          if (state === 'done') {
            clearInterval(poll);
            await loadTranscript(currentVideo.id);
            setTranscribing(false);
          } else if (state === 'error') {
            clearInterval(poll);
            alert('Transcription failed: ' + (error || 'Unknown error'));
            setTranscribing(false);
          }
          // state === 'running' → keep polling
        } catch {
          clearInterval(poll);
          setTranscribing(false);
        }
      }, 5000); // poll every 5 seconds
    } catch (err) {
      console.error('Transcription failed:', err);
      alert('Transcription failed: ' + (err.response?.data?.error || err.message));
      setTranscribing(false);
    }
  };

  const jumpToTime = (time) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      videoRef.current.play().catch(() => {});
    }
  };

  // Auto-scroll transcript to current segment
  useEffect(() => {
    if (transcriptRef.current && transcript.length > 0) {
      const active = transcriptRef.current.querySelector('.transcript-seg.active');
      if (active) {
        active.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }, [currentTime]);

  const handleUpload = async (file) => {
    if (!courseId) {
      alert('Please create or select a course first.');
      return;
    }
    if (!file) return;
    const allowedTypes = ['video/mp4', 'video/webm', 'video/ogg', 'video/quicktime'];
    const allowedExts = /\.(mp4|webm|ogg|mov)$/i;
    if (!allowedTypes.includes(file.type) && !allowedExts.test(file.name)) {
      alert('Please upload a valid video file (MP4, WebM, OGG, MOV).');
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

  return (
    <>
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-icon">🎬</span>
          Smart Video Player
        </div>
        <div className="panel-status">
          {currentVideo ? currentVideo.original_filename : 'No video loaded'}
        </div>
      </div>

      <div className="panel-body video-panel-body">
        {currentVideo ? (
          <div className="video-container">
            <video
              ref={videoRef}
              src={getVideoStreamUrl(currentVideo.filename)}
              controls
              className="video-element"
              onTimeUpdate={handleTimeUpdate}
            />
            {/* Slide sync bar — shows current matched slide page */}
            {knowledgePoints.length > 0 && (() => {
              // Find the KP whose timestamp range covers currentTime
              const sorted = [...knowledgePoints]
                .filter(kp => kp.video_timestamp != null)
                .sort((a, b) => a.video_timestamp - b.video_timestamp);
              let activeKP = null;
              for (let i = sorted.length - 1; i >= 0; i--) {
                if (currentTime >= sorted[i].video_timestamp) {
                  activeKP = sorted[i];
                  break;
                }
              }
              if (!activeKP) return null;
              return (
                <div
                  className="slide-sync-bar"
                  onClick={() => onJumpToSlide && onJumpToSlide(activeKP.slide_id, activeKP.page_number)}
                  title="Click to jump to this slide page"
                >
                  <span className="slide-sync-icon">📄</span>
                  <span className="slide-sync-text">
                    Page {activeKP.page_number}: {activeKP.title}
                  </span>
                  <span className="slide-sync-hint">← Click to view slide</span>
                </div>
              );
            })()}
            {/* Transcript / Transcribe controls */}
            <div className="video-transcript-area">
              {transcript.length > 0 ? (
                <div className="transcript-panel" ref={transcriptRef}>
                  <div className="transcript-header">
                    <span>📝 Transcript</span>
                    <span className="transcript-count">{transcript.length} segments</span>
                  </div>
                  <div className="transcript-segments">
                    {transcript.map((seg) => {
                      const isActive = currentTime >= seg.start_time && currentTime < seg.end_time;
                      return (
                        <div
                          key={seg.id}
                          className={`transcript-seg ${isActive ? 'active' : ''}`}
                          onClick={() => jumpToTime(seg.start_time)}
                        >
                          <span className="seg-time">
                            {Math.floor(seg.start_time / 60)}:{String(Math.floor(seg.start_time % 60)).padStart(2, '0')}
                          </span>
                          <span className="seg-text">{seg.text}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="transcribe-prompt">
                  <button
                    className="transcribe-btn"
                    onClick={handleTranscribe}
                    disabled={transcribing}
                  >
                    {transcribing ? '⏳ Transcribing (this may take a minute)...' : '🎤 Transcribe Video (ASR)'}
                  </button>
                  <p className="transcribe-hint">Generate captions & enable semantic alignment with slides</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="video-upload-area">
            <div className="upload-placeholder">
              <span className="upload-icon">🎥</span>
              <h3>Upload Lecture Video</h3>
              <p>AI will index content and link to knowledge points</p>

              <div
                className={`upload-dropzone ${dragOver ? 'drag-over' : ''} ${uploading ? 'disabled' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const f = e.dataTransfer.files[0];
                  if (f) handleUpload(f);
                }}
                onClick={() => !uploading && fileInputRef.current?.click()}
              >
                <p>{uploading ? `Uploading... ${uploadProgress}%` : 'Drag and drop video here, or'}</p>
                {uploading && (
                  <div className="upload-progress-bar">
                    <div className="upload-progress-fill" style={{ width: `${uploadProgress}%` }} />
                  </div>
                )}
                {!uploading && <span className="upload-link">Click to select file</span>}
                <p className="upload-hint">Supports .mp4, .webm, .ogg formats (max 2GB)</p>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept="video/mp4,video/webm,video/ogg"
                style={{ display: 'none' }}
                onChange={(e) => {
                  if (e.target.files[0]) handleUpload(e.target.files[0]);
                  e.target.value = '';
                }}
              />
            </div>
          </div>
        )}

        {/* Video list below player when a video is loaded */}
        {videos.length > 0 && currentVideo && (
          <div className="video-list">
            {videos.map((v) => (
              <div
                key={v.id}
                className={`video-list-item ${v.id === currentVideo.id ? 'active' : ''}`}
                onClick={() => setCurrentVideo(v)}
              >
                <span className="video-list-icon">▶</span>
                <span className="video-list-name">{v.original_filename}</span>
                <button
                  className="video-list-delete"
                  onClick={(e) => { e.stopPropagation(); handleDelete(v.id); }}
                  title="Delete"
                >
                  ×
                </button>
              </div>
            ))}
            <button
              className="video-add-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              + Add Video
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="video/mp4,video/webm,video/ogg"
              style={{ display: 'none' }}
              onChange={(e) => {
                if (e.target.files[0]) handleUpload(e.target.files[0]);
                e.target.value = '';
              }}
            />
          </div>
        )}
      </div>
    </>
  );
}

export default VideoPlayer;
