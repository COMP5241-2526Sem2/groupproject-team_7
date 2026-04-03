import React, { useState, useEffect } from 'react';
import {
  getDashboardSummary,
  getDifficultyAnalysis,
  getChatInsights,
  generateReviewBrief,
} from '../services/api';
import '../styles/TeacherDashboard.css';

function TeacherDashboard({ courseId, onJumpToTimestamp, onSwitchToLearn }) {
  const [summary, setSummary] = useState(null);
  const [difficulties, setDifficulties] = useState(null);
  const [chatInsights, setChatInsights] = useState(null);
  const [reviewBrief, setReviewBrief] = useState('');
  const [generatingBrief, setGeneratingBrief] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (courseId) {
      loadDashboardData();
    } else {
      setSummary(null);
      setDifficulties(null);
      setChatInsights(null);
      setReviewBrief('');
    }
  }, [courseId]);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [sumRes, diffRes, chatRes] = await Promise.all([
        getDashboardSummary(courseId),
        getDifficultyAnalysis(courseId),
        getChatInsights(courseId),
      ]);
      setSummary(sumRes.data);
      setDifficulties(diffRes.data);
      setChatInsights(chatRes.data);
    } catch (err) {
      console.error('Dashboard load failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateBrief = async () => {
    if (!courseId || generatingBrief) return;
    setGeneratingBrief(true);
    try {
      const res = await generateReviewBrief(courseId);
      setReviewBrief(res.data.brief || res.data.error || 'No brief generated.');
    } catch (err) {
      setReviewBrief('Failed to generate review brief.');
    } finally {
      setGeneratingBrief(false);
    }
  };

  const formatTimestamp = (ts) => {
    if (ts == null) return null;
    const m = Math.floor(ts / 60);
    const s = Math.floor(ts % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  };

  if (!courseId) {
    return (
      <div className="dashboard-container">
        <div className="dashboard-empty">
          <span className="dashboard-empty-icon">ANALYTICS</span>
          <h2>Teacher Dashboard</h2>
          <p>Select a course to view learning analytics.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="dashboard-container">
        <div className="dashboard-loading">Loading dashboard data...</div>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <h2>Teacher Dashboard</h2>
        {summary && <span className="dashboard-course">{summary.course_title}</span>}
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="dashboard-cards">
          <div className="dash-card">
            <div className="dash-card-number">{summary.slides_count}</div>
            <div className="dash-card-label">Slides</div>
          </div>
          <div className="dash-card">
            <div className="dash-card-number">{summary.videos_count}</div>
            <div className="dash-card-label">Videos</div>
          </div>
          <div className="dash-card">
            <div className="dash-card-number">{summary.knowledge_points_count}</div>
            <div className="dash-card-label">Knowledge Points</div>
          </div>
          <div className="dash-card">
            <div className="dash-card-number">{summary.quizzes_count}</div>
            <div className="dash-card-label">Quiz Questions</div>
          </div>
          <div className="dash-card">
            <div className="dash-card-number">{summary.total_quiz_attempts}</div>
            <div className="dash-card-label">Quiz Attempts</div>
          </div>
          <div className="dash-card">
            <div className="dash-card-number">
              {summary.total_quiz_attempts > 0 ? `${Math.round(summary.quiz_accuracy * 100)}%` : '—'}
            </div>
            <div className="dash-card-label">Accuracy</div>
          </div>
          <div className="dash-card">
            <div className="dash-card-number">{summary.chat_questions_count}</div>
            <div className="dash-card-label">Chat Questions</div>
          </div>
        </div>
      )}

      <div className="dashboard-grid">
        {/* Difficulty Analysis */}
        <div className="dashboard-section">
          <h3>Top Difficult Knowledge Points</h3>
          {difficulties && difficulties.difficulties.length > 0 ? (
            <div className="difficulty-list">
              {difficulties.difficulties.map((d, i) => (
                <div key={d.knowledge_point_id} className="difficulty-item">
                  <div className="difficulty-rank">#{i + 1}</div>
                  <div className="difficulty-info">
                    <div className="difficulty-title">{d.title}</div>
                    <div className="difficulty-stats">
                      <span className="error-rate-badge">
                        Error Rate: {Math.round(d.error_rate * 100)}%
                      </span>
                      <span className="attempt-count">
                        {d.total_errors}/{d.total_attempts} wrong
                      </span>
                    </div>
                  </div>
                  {d.video_timestamp != null && (
                    <button
                      className="difficulty-jump-btn"
                      onClick={() => {
                        if (onJumpToTimestamp) onJumpToTimestamp(d.video_timestamp);
                        if (onSwitchToLearn) onSwitchToLearn();
                      }}
                    >
                      Video {formatTimestamp(d.video_timestamp)}
                    </button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="dashboard-no-data">No quiz attempts yet. Students need to take quizzes first.</p>
          )}
        </div>

        {/* Student Chat Insights */}
        <div className="dashboard-section">
          <h3>Student Questions</h3>
          {chatInsights && chatInsights.total_questions > 0 ? (
            <>
              <p className="insight-count">{chatInsights.total_questions} questions asked</p>
              <div className="questions-list">
                {chatInsights.recent_questions.map((q, i) => (
                  <div key={i} className="question-item">
                    <span className="question-text">{q.content}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="dashboard-no-data">No student questions yet.</p>
          )}
        </div>
      </div>

      {/* AI Review Brief */}
      <div className="dashboard-section review-brief-section">
        <div className="review-brief-header">
          <h3>AI Review Brief</h3>
          <button
            className="generate-brief-btn"
            onClick={handleGenerateBrief}
            disabled={generatingBrief}
          >
            {generatingBrief ? 'Generating...' : 'Generate Review Brief'}
          </button>
        </div>
        {reviewBrief ? (
          <div className="review-brief-content">
            {reviewBrief.split('\n').map((line, i) => (
              <p key={i}>{line}</p>
            ))}
          </div>
        ) : (
          <p className="dashboard-no-data">
            Click "Generate Review Brief" to get an AI-powered summary of learning gaps and review recommendations.
          </p>
        )}
      </div>
    </div>
  );
}

export default TeacherDashboard;
