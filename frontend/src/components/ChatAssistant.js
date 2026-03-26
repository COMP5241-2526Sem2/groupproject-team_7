import React, { useState, useEffect, useRef } from 'react';
import { getChatHistory, sendChatMessage, clearChat } from '../services/api';
import '../styles/ChatAssistant.css';

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
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadHistory = async () => {
    try {
      const res = await getChatHistory(courseId);
      setMessages(res.data);
    } catch {
      // API not available yet
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || !courseId || loading) return;

    // Optimistically display user message
    const userMsg = { role: 'user', content: text, created_at: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await sendChatMessage(courseId, text);
      setMessages((prev) => [...prev, res.data.assistant_message]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Sorry, something went wrong. Please try again.', created_at: new Date().toISOString() },
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
    <>
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-icon">💬</span>
          AI Learning Assistant
        </div>
        <div className="chat-header-actions">
          {courseId ? (
            <span className="panel-status chat-status online">● Ready</span>
          ) : (
            <span className="panel-status chat-status">● Waiting for slides</span>
          )}
          {messages.length > 0 && (
            <button className="chat-clear-btn" onClick={handleClear} title="Clear chat">
              🗑
            </button>
          )}
        </div>
      </div>

      <div className="panel-body chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <span className="chat-empty-icon">💡</span>
            <h3>Upload slides to start asking questions</h3>
            <p>AI will answer based on your slides content and locate relevant video segments.</p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className={`chat-message chat-message-${msg.role}`}>
              <div className="chat-avatar">
                {msg.role === 'user' ? '👤' : '🤖'}
              </div>
              <div className="chat-bubble">
                <div className="chat-bubble-content">{msg.content}</div>
                {msg.citations && msg.citations.length > 0 && (
                  <div className="chat-citations">
                    {msg.citations.map((cite, i) => (
                      <span
                        key={i}
                        className={`chat-citation-tag ${cite.type === 'video' ? 'citation-video' : 'citation-slide'}`}
                        onClick={() => {
                          if (cite.type === 'video' && cite.timestamp && onJumpToTimestamp) {
                            onJumpToTimestamp(cite.timestamp);
                          }
                        }}
                        title={cite.label}
                      >
                        {cite.type === 'video' ? '🎬' : '📍'} {cite.label}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        {loading && (
          <div className="chat-message chat-message-assistant">
            <div className="chat-avatar">🤖</div>
            <div className="chat-bubble">
              <div className="chat-typing">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={courseId ? 'Ask about your slides or lecture...' : 'Please upload PDF / PPT slides first...'}
          disabled={!courseId || loading}
          rows={1}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={!input.trim() || !courseId || loading}
        >
          ➤
        </button>
      </div>
    </>
  );
}

export default ChatAssistant;
