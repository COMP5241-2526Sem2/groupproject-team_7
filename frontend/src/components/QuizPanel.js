import React, { useState, useEffect } from 'react';
import { getQuizzes, generateQuizzes, submitQuizAttempt, clearQuizzes } from '../services/api';
import { ClipboardList, Sparkles, Trash2 } from 'lucide-react';
import clsx from 'clsx';

function QuizPanel({ courseId, onJumpToTimestamp }) {
  const [quizzes, setQuizzes] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [answers, setAnswers] = useState({});
  const [results, setResults] = useState({});
  const [score, setScore] = useState(null);

  useEffect(() => {
    if (courseId) {
      setQuizzes([]);
      setAnswers({});
      setResults({});
      setScore(null);
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
    if (results[quizId]) return;
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
          video_timestamp: res.data.video_timestamp,
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

  useEffect(() => {
    if (quizzes.length > 0 && Object.keys(results).length === quizzes.length) {
      const correct = Object.values(results).filter((r) => r.is_correct).length;
      setScore({ correct, total: quizzes.length });
    }
  }, [results, quizzes.length]);

  const getOptionLetter = (option, index) => {
    const match = option.match(/^([A-Da-d])[\.\)\s]/);
    if (match) return match[1].toUpperCase();
    return String.fromCharCode(65 + index);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#FFFBF7]/40">
      <div className="flex items-center justify-between border-b border-stone-200/90 px-4 py-3">
        <span className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-stone-500">
          <ClipboardList className="h-3.5 w-3.5" />
          Quiz
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleGenerate}
            disabled={!courseId || generating}
            className="inline-flex items-center gap-1 rounded-control border border-red-800/25 bg-red-50 px-2.5 py-1 text-[11px] font-medium text-red-950 transition hover:border-red-800/45 hover:bg-[#F5EFE3] disabled:opacity-40"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {generating ? 'Generating...' : 'Generate Quiz'}
          </button>
          {quizzes.length > 0 && (
            <button
              type="button"
              onClick={handleClear}
              className="rounded p-1 text-stone-500 hover:bg-stone-200/80 hover:text-stone-800"
              title="Clear"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {score && (
          <div
            className={clsx(
              'rounded-inner border px-3 py-2.5 text-center text-sm font-semibold',
              score.correct === score.total
                ? 'border-emerald-500/45 bg-emerald-50 text-emerald-800'
                : 'border-stone-200/90 bg-white text-stone-800 shadow-sm'
            )}
          >
            Score {score.correct}/{score.total}
            {score.correct === score.total && ' - Perfect!'}
          </div>
        )}

        {quizzes.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-12 text-center text-stone-500">
            <ClipboardList className="h-10 w-10 text-red-900/20" />
            <p className="text-sm text-stone-600">No quiz yet</p>
            <p className="max-w-xs text-xs text-stone-500">
              Upload slides and click "Generate Quiz" to create AI questions.
            </p>
          </div>
        ) : (
          quizzes.map((quiz, idx) => {
            const result = results[quiz.id];
            const selected = answers[quiz.id];
            const videoTimestamp = result?.video_timestamp ?? quiz.video_timestamp;
            return (
              <div
                key={quiz.id}
                className={clsx(
                  'rounded-inner border px-3 py-3 transition',
                  result
                    ? result.is_correct
                      ? 'border-emerald-300/80 bg-emerald-50/80'
                      : 'border-rose-200 bg-rose-50/60'
                    : 'border-stone-200/90 bg-white shadow-sm'
                )}
              >
                <div className="mb-2 text-xs font-medium leading-snug text-stone-800">
                  <span className="mr-2 text-[10px] font-semibold text-red-800">Q{idx + 1}</span>
                  {quiz.question}
                </div>
                <div className="space-y-1.5">
                  {quiz.options.map((option, i) => {
                    const letter = getOptionLetter(option, i);
                    const isSelected = selected === letter;
                    const isCorrect = result && letter === result.correct_answer;
                    const isWrong = result && isSelected && !result.is_correct;
                    return (
                      <button
                        key={i}
                        type="button"
                        onClick={() => handleSelectAnswer(quiz.id, letter)}
                        className={clsx(
                          'w-full rounded-control border px-2 py-2 text-left text-xs transition',
                          isCorrect && 'border-emerald-500/55 bg-emerald-50 text-emerald-900',
                          isWrong && 'border-rose-500/50 bg-rose-50 text-rose-900',
                          !result && isSelected && 'border-red-800/35 bg-red-50',
                          !result && !isSelected && 'border-transparent bg-[#F5EFE3]/60 text-stone-700 hover:border-stone-300'
                        )}
                      >
                        {option}
                      </button>
                    );
                  })}
                </div>
                {!result && selected && (
                  <button
                    type="button"
                    onClick={() => handleSubmitAnswer(quiz.id)}
                    className="mt-2 w-full rounded-control bg-gradient-to-r from-red-800 to-red-950 py-1.5 text-xs font-medium text-[#FFFBF7] shadow-glass"
                  >
                    Submit Answer
                  </button>
                )}
                {result && (
                  <div className="mt-2 space-y-2 text-xs">
                    <p
                      className={
                        result.is_correct ? 'text-emerald-700' : 'text-rose-700'
                      }
                    >
                      {result.is_correct
                        ? 'Correct'
                        : `Incorrect - Correct option: ${result.correct_answer}`}
                    </p>
                    {result.explanation && (
                      <p className="text-stone-600">
                        {result.explanation}
                        {videoTimestamp != null && onJumpToTimestamp && (
                          <button
                            type="button"
                            onClick={() => onJumpToTimestamp(videoTimestamp)}
                            className="ml-1 inline-flex items-center text-[11px] font-medium text-red-800 underline-offset-2 hover:underline"
                            aria-label="Jump to key frame"
                          >
                            {Math.floor(videoTimestamp / 60)}:
                            {String(Math.floor(videoTimestamp % 60)).padStart(2, '0')}
                          </button>
                        )}
                      </p>
                    )}
                    {!result.explanation && videoTimestamp != null && onJumpToTimestamp && (
                      <button
                        type="button"
                        onClick={() => onJumpToTimestamp(videoTimestamp)}
                        className="text-[11px] font-medium text-red-800 underline-offset-2 hover:underline"
                        aria-label="Jump to key frame"
                      >
                        {Math.floor(videoTimestamp / 60)}:
                        {String(Math.floor(videoTimestamp % 60)).padStart(2, '0')}
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export default QuizPanel;
