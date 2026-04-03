import React, { useState, useEffect, useRef } from 'react';
import {
  transcribeVideo,
  getTranscribeStatus,
  cancelTranscribe,
  getVideoTranscript,
} from '../services/api';
import { Subtitles } from 'lucide-react';

function TranscriptPanel({ videoId, currentTime, onJumpToTime }) {
  const [transcript, setTranscript] = useState([]);
  const [transcribing, setTranscribing] = useState(false);
  const [asrProgress, setAsrProgress] = useState({ progress: 0, message: '' });
  const transcriptRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    if (videoId) {
      loadTranscript(videoId);
      getTranscribeStatus(videoId)
        .then((res) => {
          if (res.data.state === 'running') {
            setTranscribing(true);
            setAsrProgress({
              progress: res.data.progress || 0,
              message: res.data.message || 'Processing...',
            });
            startPoll(videoId);
          }
        })
        .catch(() => {});
    } else {
      setTranscript([]);
      setTranscribing(false);
      setAsrProgress({ progress: 0, message: '' });
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [videoId]);

  useEffect(() => {
    if (transcriptRef.current && transcript.length > 0) {
      const active = transcriptRef.current.querySelector('.transcript-seg-active');
      if (active) {
        active.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }, [currentTime, transcript.length]);

  const startPoll = (id) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await getTranscribeStatus(id);
        if (s.data.state === 'running') {
          setAsrProgress({
            progress: s.data.progress || 0,
            message: s.data.message || 'Processing...',
          });
        } else if (s.data.state === 'done') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setAsrProgress({ progress: 100, message: 'Completed' });
          await loadTranscript(id);
          setTranscribing(false);
        } else if (s.data.state === 'error') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setTranscribing(false);
          setAsrProgress({ progress: 0, message: '' });
        }
      } catch {
        clearInterval(pollRef.current);
        pollRef.current = null;
        setTranscribing(false);
      }
    }, 3000);
  };

  const loadTranscript = async (id) => {
    try {
      const res = await getVideoTranscript(id);
      setTranscript(res.data || []);
    } catch {
      setTranscript([]);
    }
  };

  const handleTranscribe = async () => {
    if (!videoId || transcribing) return;
    setTranscribing(true);
    setAsrProgress({ progress: 0, message: 'Starting...' });
    try {
      await transcribeVideo(videoId);
      startPoll(videoId);
    } catch (err) {
      alert('Transcription failed: ' + (err.response?.data?.error || err.message));
      setTranscribing(false);
      setAsrProgress({ progress: 0, message: '' });
    }
  };

  const handleCancel = async () => {
    if (!videoId) return;
    try {
      await cancelTranscribe(videoId);
      setTranscribing(false);
      setAsrProgress({ progress: 0, message: '' });
      if (pollRef.current) clearInterval(pollRef.current);
    } catch (err) {
      console.error(err);
    }
  };

  if (!videoId) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center text-stone-500">
        <Subtitles className="h-10 w-10 text-red-900/20" />
        <p className="text-sm text-stone-600">Upload a video to view the synced transcript here.</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#FFFBF7]/40">
      {transcript.length > 0 ? (
        <div
          ref={transcriptRef}
          className="min-h-0 flex-1 space-y-1 overflow-y-auto px-4 py-3"
        >
          {transcript.map((seg) => {
            const isActive =
              currentTime >= seg.start_time && currentTime < seg.end_time;
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
                  {Math.floor(seg.start_time / 60)}:
                  {String(Math.floor(seg.start_time % 60)).padStart(2, '0')}
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
            <p className="max-w-xs text-xs text-stone-500">
              After transcript generation, it can align with slides and supports click-to-seek playback.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default TranscriptPanel;
