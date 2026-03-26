import React, { useState, useEffect } from 'react';
import { getQuizzes, generateQuizzes, submitQuizAttempt, clearQuizzes } from '../services/api';
import '../styles/QuizPanel.css';

function QuizPanel({ courseId, onJumpToTimestamp }) {
  const [quizzes, setQuizzes] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [answers, setAnswers] = useState({});    // {quizId: 'A'}
  const [results, setResults] = useState({});    // {quizId: {is_correct, correct_answer, explanation}}
  const [score, setScore] = useState(null);

  useEffect(() => {
    if (courseId) {
      loadQuizzes();
    } else {
      setQuizzes([]);
      setAnswers({});
      setResults({});
      setScore(null);
    }
  }, [courseId]);

  const loadQuizzes = async () => {
    try {
      const res = await getQuizzes(courseId);
      setQuizzes(res.data);
    } catch {
      // API not available
    }
  };

  const handleGenerate = async () => {
    if (!courseId || generating) return;
    setGenerating(true);
    setAnswers({});
    setResults({});
    setScore(null);
    try {
      const res = await generateQuizzes(courseId, 5);
      const data = res.data;
      if (data.error) {
        alert(data.error);
        setQuizzes([]);
      } else {
        setQuizzes(data.quizzes || []);
      }
    } catch (err) {
      console.error('Quiz generation failed:', err);
      const msg = err.response?.data?.error || 'Quiz generation failed. Please try again.';
      alert(msg);
    } finally {
      setGenerating(false);
    }
  };

  const handleSelectAnswer = (quizId, answer) => {
    if (results[quizId]) return; // Already answered
    setAnswers((prev) => ({ ...prev, [quizId]: answer }));
  };

  const handleSubmitAnswer = async (quizId) => {
    const selected = answers[quizId];
    if (!selected || results[quizId]) return;
    try {
      const res = await submitQuizAttempt(quizId, selected);
      setResults((prev) => ({
        ...prev,
        [quizId]: {
          is_correct: res.data.is_correct,
          correct_answer: res.data.correct_answer,
          explanation: res.data.explanation,
        },
      }));
    } catch (err) {
      console.error('Submit failed:', err);
    }
  };

  const handleClear = async () => {
    try {
      await clearQuizzes(courseId);
      setQuizzes([]);
      setAnswers({});
      setResults({});
      setScore(null);
    } catch {
      // ignore
    }
  };

  // Calculate score when all answered
  useEffect(() => {
    if (quizzes.length > 0 && Object.keys(results).length === quizzes.length) {
      const correct = Object.values(results).filter((r) => r.is_correct).length;
      setScore({ correct, total: quizzes.length });
    }
  }, [results, quizzes.length]);

  const getOptionLetter = (option, index) => {
    // Try to extract letter from "A. ..." format
    const match = option.match(/^([A-Da-d])[\.\)\s]/);
    if (match) return match[1].toUpperCase();
    // Fallback: use position-based letter
    return String.fromCharCode(65 + index); // A, B, C, D
  };

  return (
    <>
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-icon">📝</span>
          Quiz
        </div>
        <div className="quiz-header-actions">
          <button
            className="quiz-generate-btn"
            onClick={handleGenerate}
            disabled={!courseId || generating}
          >
            {generating ? '⏳ Generating...' : '🎲 Generate Quiz'}
          </button>
          {quizzes.length > 0 && (
            <button className="quiz-clear-btn" onClick={handleClear} title="Clear quizzes">
              🗑
            </button>
          )}
        </div>
      </div>

      <div className="panel-body quiz-body">
        {score && (
          <div className={`quiz-score ${score.correct === score.total ? 'perfect' : ''}`}>
            🏆 Score: {score.correct}/{score.total}
            {score.correct === score.total && ' — Perfect!'}
          </div>
        )}

        {quizzes.length === 0 ? (
          <div className="quiz-empty">
            <span className="quiz-empty-icon">📝</span>
            <h3>No quizzes yet</h3>
            <p>Upload slides and click "Generate Quiz" to create AI-powered quiz questions.</p>
          </div>
        ) : (
          quizzes.map((quiz, idx) => {
            const result = results[quiz.id];
            const selected = answers[quiz.id];
            return (
              <div key={quiz.id} className={`quiz-card ${result ? (result.is_correct ? 'correct' : 'incorrect') : ''}`}>
                <div className="quiz-question">
                  <span className="quiz-num">Q{idx + 1}</span>
                  {quiz.question}
                </div>
                <div className="quiz-options">
                  {quiz.options.map((option, i) => {
                    const letter = getOptionLetter(option, i);
                    const isSelected = selected === letter;
                    const isCorrect = result && letter === result.correct_answer;
                    const isWrong = result && isSelected && !result.is_correct;
                    return (
                      <div
                        key={i}
                        className={`quiz-option ${isSelected ? 'selected' : ''} ${isCorrect ? 'correct' : ''} ${isWrong ? 'wrong' : ''}`}
                        onClick={() => handleSelectAnswer(quiz.id, letter)}
                      >
                        {option}
                      </div>
                    );
                  })}
                </div>
                {!result && selected && (
                  <button
                    className="quiz-submit-btn"
                    onClick={() => handleSubmitAnswer(quiz.id)}
                  >
                    Submit Answer
                  </button>
                )}
                {result && (
                  <div className={`quiz-result ${result.is_correct ? 'correct' : 'incorrect'}`}>
                    <div className="quiz-result-icon">
                      {result.is_correct ? '✅ Correct!' : `❌ Incorrect — Answer: ${result.correct_answer}`}
                    </div>
                    {result.explanation && (
                      <div className="quiz-explanation">{result.explanation}</div>
                    )}
                    {!result.is_correct && quiz.video_timestamp != null && onJumpToTimestamp && (
                      <button
                        className="quiz-backtrack-btn"
                        onClick={() => onJumpToTimestamp(quiz.video_timestamp)}
                      >
                        🎬 Review in Video ({Math.floor(quiz.video_timestamp / 60)}:{String(Math.floor(quiz.video_timestamp % 60)).padStart(2, '0')})
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </>
  );
}

export default QuizPanel;
