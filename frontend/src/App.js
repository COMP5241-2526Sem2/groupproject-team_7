import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import SlidesPanel from './components/SlidesPanel';
import VideoPlayer from './components/VideoPlayer';
import ChatAssistant from './components/ChatAssistant';
import QuizPanel from './components/QuizPanel';
import CourseSelector from './components/CourseSelector';
import TeacherDashboard from './components/TeacherDashboard';
import './styles/App.css';
import { getCourses, createCourse } from './services/api';

function App() {
  const [courses, setCourses] = useState([]);
  const [currentCourse, setCurrentCourse] = useState(null);
  const [videoTimestamp, setVideoTimestamp] = useState(0);
  const [currentVideoTime, setCurrentVideoTime] = useState(0);
  const [slidePage, setSlidePage] = useState(null); // { slideId, pageNumber }
  const [bottomTab, setBottomTab] = useState('chat');
  const [view, setView] = useState('learn'); // 'learn' or 'dashboard'

  const loadCourses = useCallback(async () => {
    try {
      const res = await getCourses();
      setCourses(res.data);
      if (res.data.length > 0 && !currentCourse) {
        setCurrentCourse(res.data[0]);
      }
    } catch {
      // API not available yet — that's fine during development
    }
  }, [currentCourse]);

  useEffect(() => {
    loadCourses();
  }, [loadCourses]);

  const handleCreateCourse = async (title) => {
    try {
      const res = await createCourse({ title });
      setCourses((prev) => [res.data, ...prev]);
      setCurrentCourse(res.data);
    } catch (err) {
      console.error('Failed to create course:', err);
    }
  };

  const handleJumpToTimestamp = (timestamp) => {
    setVideoTimestamp(timestamp);
  };

  const handleJumpToSlide = (slideId, pageNumber) => {
    setSlidePage({ slideId, pageNumber, _ts: Date.now() });
  };

  return (
    <div className="app">
      <Header view={view} onViewChange={setView} />
      <div className="app-toolbar">
        <CourseSelector
          courses={courses}
          currentCourse={currentCourse}
          onSelect={setCurrentCourse}
          onCreate={handleCreateCourse}
        />
      </div>

      {view === 'dashboard' ? (
        <TeacherDashboard
          courseId={currentCourse?.id}
          onJumpToTimestamp={handleJumpToTimestamp}
          onSwitchToLearn={() => setView('learn')}
        />
      ) : (
        <div className="app-content">
          {/* Left Panel — Slides / Notes */}
          <div className="panel panel-left">
            <SlidesPanel
              courseId={currentCourse?.id}
              onJumpToTimestamp={handleJumpToTimestamp}
              currentVideoTime={currentVideoTime}
              targetSlidePage={slidePage}
            />
          </div>

          {/* Right Panels — Video + AI Chat */}
          <div className="panel-right-wrapper">
            <div className="panel panel-top-right">
              <VideoPlayer
                courseId={currentCourse?.id}
                seekTimestamp={videoTimestamp}
                onTimeUpdate={setCurrentVideoTime}
                onJumpToSlide={handleJumpToSlide}
              />
            </div>
            <div className="panel panel-bottom-right">
              <div className="bottom-tabs">
                <button
                  className={`bottom-tab ${bottomTab === 'chat' ? 'active' : ''}`}
                  onClick={() => setBottomTab('chat')}
                >
                  💬 Chat
                </button>
                <button
                  className={`bottom-tab ${bottomTab === 'quiz' ? 'active' : ''}`}
                  onClick={() => setBottomTab('quiz')}
                >
                  📝 Quiz
                </button>
              </div>
              {bottomTab === 'chat' ? (
                <ChatAssistant courseId={currentCourse?.id} onJumpToTimestamp={handleJumpToTimestamp} />
              ) : (
                <QuizPanel courseId={currentCourse?.id} onJumpToTimestamp={handleJumpToTimestamp} />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
