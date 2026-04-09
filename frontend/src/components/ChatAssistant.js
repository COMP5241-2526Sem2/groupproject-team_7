import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { getChatHistory, sendChatMessage, clearChat } from '../services/api';
import { Bot, User, Trash2, Link2 } from 'lucide-react';
import clsx from 'clsx';

function ChatAssistant({ courseId, onJumpToTimestamp }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (courseId) {
      loadHistory();
    } else {
      setMessages([]);
    }
  }, [courseId]);

  useEffect(() => {
    const handler = (e) => {
      const t = e.detail?.text;
      if (typeof t === 'string' && t.trim()) {
        setInput((prev) => (prev ? `${prev}\n${t}` : t));
      }
    };
    window.addEventListener('synclearn-ask-ai', handler);
    return () => window.removeEventListener('synclearn-ask-ai', handler);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const loadHistory = async () => {
    try {
      const res = await getChatHistory(courseId);
      setMessages(res.data);
    } catch {
      // API not available yet
    }
  };

  const runSlashPrefix = (raw) => {
    const t = raw.trim();
    if (t.startsWith('/summarize')) return t.replace(/^\/summarize\s*/i, 'Please generate a structured summary based on the current course content:');
    if (t.startsWith('/quiz')) return t.replace(/^\/quiz\s*/i, 'Please draft quiz ideas based on slide and video content (formal questions can be generated later in the Quiz panel):');
    return t;
  };

  const handleSend = async () => {
    const raw = input.trim();
    if (!raw || !courseId || loading) return;
    const text = runSlashPrefix(raw);

    const userMsg = {
      role: 'user',
      content: raw,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await sendChatMessage(courseId, text);
      setMessages((prev) => [...prev, res.data.assistant_message]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, the request failed. Please try again later.',
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    try {
      await clearChat(courseId);
      setMessages([]);
    } catch {
      // ignore
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#FFFBF7]/40">
      <div className="flex items-center justify-between border-b border-stone-200/90 px-4 py-3">
        <span className="text-[11px] font-medium uppercase tracking-wide text-stone-500">
          Conversation
        </span>
        <div className="flex items-center gap-2">
          {courseId ? (
            <span className="text-[11px] text-emerald-700">● Ready</span>
          ) : (
            <span className="text-[11px] text-stone-400">● Waiting for course</span>
          )}
          {messages.length > 0 && (
            <button
              type="button"
              onClick={handleClear}
              className="rounded p-1 text-stone-500 hover:bg-stone-200/80 hover:text-stone-800"
              title="Clear conversation"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-10 text-center text-stone-500">
            <Bot className="h-10 w-10 text-red-900/25" />
            <p className="text-sm text-stone-600">Upload slides to ask course-based questions.</p>
            <p className="text-[11px] text-stone-500">
              Try{' '}
              <code className="rounded border border-stone-200 bg-[#F5EFE3] px-1.5 py-0.5 text-stone-700">
                /summarize
              </code>{' '}
              or{' '}
              <code className="rounded border border-stone-200 bg-[#F5EFE3] px-1.5 py-0.5 text-stone-700">
                /quiz
              </code>
            </p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              className={clsx(
                'flex gap-2',
                msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'
              )}
            >
              <div
                className={clsx(
                  'flex h-8 w-8 shrink-0 items-center justify-center rounded-full border',
                  msg.role === 'user'
                    ? 'border-red-800/25 bg-red-50'
                    : 'border-stone-300 bg-[#F5EFE3]'
                )}
              >
                {msg.role === 'user' ? (
                  <User className="h-4 w-4 text-red-800" />
                ) : (
                  <Bot className="h-4 w-4 text-red-950/80" />
                )}
              </div>
              <div
                className={clsx(
                  'max-w-[92%] rounded-inner border px-3 py-2 text-xs leading-relaxed',
                  msg.role === 'user'
                    ? 'border-red-200/90 bg-red-50/90 text-stone-800'
                    : 'border-stone-200/90 bg-white text-stone-800 shadow-sm'
                )}
              >
                {msg.role === 'assistant' ? (
                  <div className="prose prose-stone prose-sm max-w-none prose-pre:bg-stone-100 prose-pre:rounded-md prose-code:text-red-900 prose-headings:text-stone-800">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                )}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5 border-t border-stone-200/80 pt-2">
                    {msg.citations.map((cite, i) => (
                      <button
                        key={i}
                        type="button"
                        className="inline-flex items-center gap-1 rounded-full border border-stone-200 bg-[#F5EFE3]/90 px-2 py-0.5 text-[10px] text-stone-600 hover:border-red-800/35"
                        onClick={() => {
                          if (cite.type === 'video' && cite.timestamp != null) {
                            onJumpToTimestamp?.(cite.timestamp);
                          }
                        }}
                        title={cite.label}
                      >
                        <Link2 className="h-3 w-3 opacity-70" />
                        {cite.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        {loading && (
          <div className="flex gap-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-stone-300 bg-[#F5EFE3]">
              <Bot className="h-4 w-4 text-red-950/80" />
            </div>
            <div className="rounded-inner border border-stone-200 bg-white px-3 py-2 shadow-sm">
              <div className="flex gap-1">
                <span className="h-2 w-2 animate-bounce rounded-full bg-red-800 [animation-delay:-0.2s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-red-700 [animation-delay:-0.1s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-amber-700/90" />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div
        className={clsx(
          'relative border-t border-stone-200/90 bg-[#FFFBF7]/60 p-4',
          loading && 'sync-ai-input-glow'
        )}
      >
        <div className="flex gap-2">
          <textarea
            className="sync-input-cmd max-h-32 min-h-[44px] flex-1 resize-none text-xs"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              courseId
                ? 'Ask a question, or use /summarize or /quiz...'
                : 'Please upload slides and select a course first.'
            }
            disabled={!courseId || loading}
            rows={2}
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={!input.trim() || !courseId || loading}
            className="self-end rounded-control bg-gradient-to-r from-red-800 to-red-950 px-3 py-2 text-xs font-semibold text-[#FFFBF7] shadow-glass disabled:opacity-40"
          >
            Send
          </button>
        </div>
        <p className="mt-2 text-[10px] text-stone-500">
          Shift+Enter for newline · citations can jump to video time or slide page
        </p>
      </div>
    </div>
  );
}

export default ChatAssistant;
