import React, { useEffect, useRef, useState } from 'react';
import { Subtitles } from 'lucide-react';
import {
  getVideo,
  transcribeVideo,
  getTranscribeStatus,
  cancelTranscribe,
  getVideoTranscript,
} from '../services/api';

function formatTimestamp(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return '0:00';
  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${minutes}:${String(secs).padStart(2, '0')}`;
}

function TranscriptPanel({ videoId, currentTime, onJumpToTime }) {
  const [videoInfo, setVideoInfo] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [transcribing, setTranscribing] = useState(false);
  const [asrProgress, setAsrProgress] = useState({ progress: 0, message: '' });
  const [asrError, setAsrError] = useState('');
  const transcriptRef = useRef(null);
  const pollRef = useRef(null);

  const clearPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const loadTranscript = async (id) => {
    try {
      const res = await getVideoTranscript(id);
      setTranscript(res.data || []);
    } catch {
      setTranscript([]);
    }
  };

  const startPoll = (id) => {
    clearPolling();
    pollRef.current = setInterval(async () => {
      try {
        const res = await getTranscribeStatus(id);
        const status = res.data || {};
        if (status.state === 'running') {
          setTranscribing(true);
          setAsrProgress({
            progress: status.progress || 0,
            message: status.message || 'Processing...',
          });
        } else if (status.state === 'done') {
          clearPolling();
          setAsrProgress({ progress: 100, message: 'Completed' });
          setTranscribing(false);
          await loadTranscript(id);
        } else if (status.state === 'error') {
          clearPolling();
          setTranscribing(false);
          setAsrProgress({ progress: 0, message: '' });
          setAsrError(status.error || 'Transcription failed.');
        }
      } catch {
        clearPolling();
        setTranscribing(false);
      }
    }, 3000);
  };

  useEffect(() => {
    let active = true;

    const loadVideo = async () => {
      if (!videoId) {
        setVideoInfo(null);
        setTranscript([]);
        setTranscribing(false);
        setAsrProgress({ progress: 0, message: '' });
        setAsrError('');
        clearPolling();
        return;
      }

      try {
        const res = await getVideo(videoId);
        if (!active) return;
        setVideoInfo(res.data || null);
        if (res.data?.source_type === 'external') {
          setTranscript([]);
          setTranscribing(false);
          setAsrProgress({ progress: 0, message: '' });
          setAsrError('External video links are preview-only and cannot be transcribed.');
          clearPolling();
          return;
        }

        setAsrError('');
        await loadTranscript(videoId);
        const statusRes = await getTranscribeStatus(videoId);
        const status = statusRes.data || {};
        if (status.state === 'running') {
          setTranscribing(true);
          setAsrProgress({
            progress: status.progress || 0,
            message: status.message || 'Processing...',
          });
          startPoll(videoId);
        } else if (status.state === 'error') {
          setTranscribing(false);
          setAsrError(status.error || 'Transcription failed.');
        } else {
          setTranscribing(false);
          setAsrProgress({ progress: 0, message: '' });
        }
      } catch {
        if (!active) return;
        setVideoInfo(null);
        setTranscript([]);
        setTranscribing(false);
        setAsrError('Unable to load the current video.');
      }
    };

    loadVideo();

    return () => {
      active = false;
      clearPolling();
    };
  }, [videoId]);

  useEffect(() => {
    if (transcriptRef.current && transcript.length > 0) {
      const activeNode = transcriptRef.current.querySelector('.transcript-seg-active');
      if (activeNode) {
        activeNode.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }, [currentTime, transcript.length]);

  const handleTranscribe = async () => {
    if (!videoId || transcribing) return;
    if (videoInfo?.source_type === 'external') {
      setAsrError('External video links are preview-only and cannot be transcribed.');
      return;
    }
    setTranscribing(true);
    setAsrProgress({ progress: 0, message: 'Starting...' });
    setAsrError('');
    try {
      await transcribeVideo(videoId);
      startPoll(videoId);
    } catch (err) {
      setTranscribing(false);
      setAsrProgress({ progress: 0, message: '' });
      setAsrError(err.response?.data?.error || err.message || 'Transcription failed.');
    }
  };

  const handleCancel = async () => {
    if (!videoId) return;
    try {
      await cancelTranscribe(videoId);
      setTranscribing(false);
      setAsrProgress({ progress: 0, message: '' });
      clearPolling();
    } catch (err) {
      console.error(err);
    }
  };

  if (!videoId) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center text-stone-500">
        <Subtitles className="h-10 w-10 text-red-900/20" />
        <p className="text-sm text-stone-600">Select an uploaded video to view and generate its transcript here.</p>
      </div>
    );
  }

  if (videoInfo?.source_type === 'external') {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center text-stone-500">
        <Subtitles className="h-10 w-10 text-red-900/20" />
        <p className="text-sm text-stone-600">External video links are preview-only and do not support transcription.</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#FFFBF7]/40">
      {transcript.length > 0 ? (
        <div ref={transcriptRef} className="min-h-0 flex-1 space-y-1 overflow-y-auto px-4 py-3">
          {transcript.map((seg) => {
            const isActive = currentTime >= seg.start_time && currentTime < seg.end_time;
            return (
              <button
                key={seg.id}
                type="button"
                onClick={() => onJumpToTime?.(seg.start_time)}
                className={`w-full rounded-control border px-2 py-2 text-left text-xs transition-colors ${
                  isActive
                    ? 'transcript-seg-active border-red-800/35 bg-red-50 text-stone-800 shadow-sm'
                    : 'border-transparent bg-white/70 text-stone-600 hover:border-stone-200 hover:bg-[#F5EFE3]/80'
                }`}
              >
                <span className="mr-2 font-mono text-[10px] text-red-800/90">
                  {formatTimestamp(seg.start_time)}
                </span>
                <span className="leading-relaxed">{seg.text}</span>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
          <button
            type="button"
            onClick={handleTranscribe}
            disabled={transcribing}
            className="rounded-control bg-gradient-to-r from-red-800 to-red-950 px-4 py-2 text-sm font-medium text-[#FFFBF7] shadow-glass transition hover:opacity-95 disabled:opacity-50"
          >
            {transcribing ? 'Transcribing...' : 'Generate Transcript (ASR)'}
          </button>
          {transcribing && (
            <div className="w-full max-w-xs space-y-2">
              <div className="h-1.5 overflow-hidden rounded-full bg-stone-200">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-red-700 to-red-900 transition-all"
                  style={{ width: `${asrProgress.progress}%` }}
                />
              </div>
              <p className="text-[11px] text-stone-500">
                {asrProgress.progress}% — {asrProgress.message}
              </p>
              <button
                type="button"
                onClick={handleCancel}
                className="text-xs text-red-800/90 underline-offset-2 hover:underline"
              >
                Cancel and Retry
              </button>
            </div>
          )}
          {!transcribing && (
            <>
              <p className="max-w-xs text-xs text-stone-500">
                Generate a transcript for the selected uploaded video, then use it for click-to-seek review.
              </p>
              {asrError && (
                <p className="max-w-sm rounded-control border border-red-200 bg-red-50 px-3 py-2 text-left text-[11px] text-red-800">
                  {asrError}
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default TranscriptPanel;