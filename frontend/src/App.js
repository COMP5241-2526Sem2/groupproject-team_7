import React, { useState, useEffect, useCallback } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { MessageSquare, Subtitles, ClipboardList } from 'lucide-react';
import clsx from 'clsx';
import SideNav from './components/SideNav';
import SlidesPanel from './components/SlidesPanel';
import VideoPlayer from './components/VideoPlayer';
import ChatAssistant from './components/ChatAssistant';
import QuizPanel from './components/QuizPanel';
import TranscriptPanel from './components/TranscriptPanel';
import CourseSelector from './components/CourseSelector';
import TeacherDashboard from './components/TeacherDashboard';
import { getCourses, createCourse } from './services/api';

const tabs = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'transcript', label: 'Transcript', icon: Subtitles },
  { id: 'quiz', label: 'Quiz', icon: ClipboardList },
];

function App() {
  const [courses, setCourses] = useState([]);
  const [currentCourse, setCurrentCourse] = useState(null);
  const [videoTimestamp, setVideoTimestamp] = useState(0);
  const [currentVideoTime, setCurrentVideoTime] = useState(0);
  const [currentVideoId, setCurrentVideoId] = useState(null);
  const [slidePage, setSlidePage] = useState(null);
  const [bottomTab, setBottomTab] = useState('chat');
  const [view, setView] = useState('learn');

  const loadCourses = useCallback(async () => {
    try {
      const res = await getCourses();
      setCourses(res.data);
      if (res.data.length > 0) {
        setCurrentCourse((c) => c || res.data[0]);
      }
    } catch {
      // API not available yet — that's fine during development
    }
  }, []);

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

  const focusCourseSelect = () => {
    document.getElementById('synclearn-course-select')?.focus();
  };

  const openAiTab = () => {
    setView('learn');
    setBottomTab('chat');
  };

  return (
    <div className="flex h-full min-h-0 w-full text-stone-800">
      <SideNav
        view={view}
        onViewChange={setView}
        onFocusCourses={focusCourseSelect}
        onOpenAiTab={openAiTab}
      />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex shrink-0 flex-wrap items-center justify-between gap-4 border-b border-stone-200/80 bg-[#FFFBF7]/90 px-6 py-4 shadow-sm backdrop-blur-md">
          <div className="min-w-0">
            <h1 className="text-sm font-semibold tracking-tight text-stone-800">
              <span className="bg-gradient-to-r from-red-800 to-red-950 bg-clip-text text-transparent">
                Sync Learn
              </span>
              <span className="ml-2 text-xs font-normal text-stone-500">
                Multimodal AI Smart Review
              </span>
            </h1>
          </div>
          <CourseSelector
            courses={courses}
            currentCourse={currentCourse}
            onSelect={setCurrentCourse}
            onCreate={handleCreateCourse}
          />
        </header>

        {view === 'dashboard' ? (
          <div className="min-h-0 flex-1 overflow-auto p-6">
            <div className="sync-glass sync-glass-hover mx-auto max-w-6xl rounded-card p-6">
              <TeacherDashboard
                courseId={currentCourse?.id}
                onJumpToTimestamp={handleJumpToTimestamp}
                onSwitchToLearn={() => setView('learn')}
              />
            </div>
          </div>
        ) : (
          <div className="flex min-h-0 flex-1 gap-5 overflow-hidden px-6 pb-6 pt-3">
            <section className="sync-glass sync-glass-hover flex w-[65%] min-w-0 shrink-0 flex-col overflow-hidden rounded-card border-stone-200/70">
              <SlidesPanel
                courseId={currentCourse?.id}
                courseTitle={currentCourse?.title}
                onJumpToTimestamp={handleJumpToTimestamp}
                currentVideoTime={currentVideoTime}
                targetSlidePage={slidePage}
              />
            </section>

            <section className="flex min-h-0 w-[35%] min-w-[280px] shrink-0 flex-col gap-5 overflow-hidden">
              <div className="sync-glass sync-glass-hover flex min-h-0 flex-[0_0_42%] flex-col overflow-hidden rounded-card border-stone-200/70">
                <VideoPlayer
                  courseId={currentCourse?.id}
                  seekTimestamp={videoTimestamp}
                  onTimeUpdate={setCurrentVideoTime}
                  onJumpToSlide={handleJumpToSlide}
                  onCurrentVideoChange={setCurrentVideoId}
                />
              </div>

              <div className="sync-glass sync-glass-hover flex min-h-0 min-h-[240px] flex-1 flex-col overflow-hidden rounded-card border-stone-200/70">
                <div className="flex shrink-0 border-b border-stone-200/80 bg-[#FFFBF7]/50">
                  {tabs.map(({ id, label, icon: Icon }) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setBottomTab(id)}
                      className={clsx(
                        'relative flex flex-1 items-center justify-center gap-1.5 py-3 text-[11px] font-semibold uppercase tracking-wide transition',
                        bottomTab === id
                          ? 'text-red-900'
                          : 'text-stone-500 hover:text-stone-700'
                      )}
                    >
                      <Icon className="h-3.5 w-3.5" strokeWidth={2} />
                      {label}
                      {bottomTab === id && (
                        <motion.span
                          layoutId="sync-tab-pill"
                          className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-gradient-to-r from-red-700 to-red-900"
                        />
                      )}
                    </button>
                  ))}
                </div>

                <div className="relative min-h-0 flex-1 overflow-hidden">
                  <AnimatePresence mode="wait">
                    {bottomTab === 'chat' && (
                      <motion.div
                        key="chat"
                        role="tabpanel"
                        initial={{ opacity: 0, x: 12 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -12 }}
                        transition={{ duration: 0.2 }}
                        className="absolute inset-0 flex flex-col"
                      >
                        <ChatAssistant
                          courseId={currentCourse?.id}
                          onJumpToTimestamp={handleJumpToTimestamp}
                        />
                      </motion.div>
                    )}
                    {bottomTab === 'transcript' && (
                      <motion.div
                        key="transcript"
                        role="tabpanel"
                        initial={{ opacity: 0, x: 12 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -12 }}
                        transition={{ duration: 0.2 }}
                        className="absolute inset-0 flex flex-col"
                      >
                        <TranscriptPanel
                          videoId={currentVideoId}
                          currentTime={currentVideoTime}
                          onJumpToTime={handleJumpToTimestamp}
                        />
                      </motion.div>
                    )}
                    {bottomTab === 'quiz' && (
                      <motion.div
                        key="quiz"
                        role="tabpanel"
                        initial={{ opacity: 0, x: 12 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -12 }}
                        transition={{ duration: 0.2 }}
                        className="absolute inset-0 flex flex-col"
                      >
                        <QuizPanel
                          courseId={currentCourse?.id}
                          onJumpToTimestamp={handleJumpToTimestamp}
                        />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
