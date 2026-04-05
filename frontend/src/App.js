import React, { useState, useEffect, useCallback } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { MessageSquare, ClipboardList, Subtitles } from 'lucide-react';
import clsx from 'clsx';
import SideNav from './components/SideNav';
import SlidesPanel from './components/SlidesPanel';
import VideoPlayer from './components/VideoPlayer';
import TranscriptPanel from './components/TranscriptPanel';
import ChatAssistant from './components/ChatAssistant';
import QuizPanel from './components/QuizPanel';
import CourseSelector from './components/CourseSelector';
import TeacherDashboard from './components/TeacherDashboard';
import TeacherResourceManager from './components/TeacherResourceManager';
import RoleGate from './components/RoleGate';
import { getCourses, createCourse } from './services/api';

const tabs = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'transcript', label: 'Transcript', icon: Subtitles },
  { id: 'quiz', label: 'Quiz', icon: ClipboardList },
];

const getStoredRole = () => {
  try {
    return localStorage.getItem('synclearn-role');
  } catch {
    return null;
  }
};

const detectStudentId = () => {
  try {
    const params = new URLSearchParams(window.location.search);
    const fromQuery =
      params.get('student_id') ||
      params.get('studentId') ||
      params.get('sid') ||
      params.get('uid');
    if (fromQuery) {
      localStorage.setItem('synclearn-student-id', fromQuery);
      return fromQuery;
    }

    const fromWindow = window.__SYNCLEARN_STUDENT_ID__;
    if (fromWindow) {
      localStorage.setItem('synclearn-student-id', String(fromWindow));
      return String(fromWindow);
    }

    return localStorage.getItem('synclearn-student-id');
  } catch {
    return null;
  }
};

const getStoredStudentId = () => {
  try {
    return localStorage.getItem('synclearn-student-id');
  } catch {
    return null;
  }
};

const normalizeStudentId = (value) => {
  const raw = String(value || '').trim();
  return raw || null;
};

function App() {
  const [courses, setCourses] = useState([]);
  const [currentCourse, setCurrentCourse] = useState(null);
  const [videoTimestamp, setVideoTimestamp] = useState(0);
  const [videoSeekSignal, setVideoSeekSignal] = useState(0);
  const [currentVideoTime, setCurrentVideoTime] = useState(0);
  const [currentVideoId, setCurrentVideoId] = useState(null);
  const [preferredVideoId, setPreferredVideoId] = useState(null);
  const [slidePage, setSlidePage] = useState(null);
  const [bottomTab, setBottomTab] = useState('chat');
  const [role, setRole] = useState(getStoredRole);
  const [studentId, setStudentId] = useState(getStoredStudentId);
  const [view, setView] = useState(() => (getStoredRole() === 'teacher' ? 'teacher-home' : 'learn'));

  useEffect(() => {
    try {
      if (role) {
        localStorage.setItem('synclearn-role', role);
      } else {
        localStorage.removeItem('synclearn-role');
      }
    } catch {
      // ignore persistence errors
    }
  }, [role]);

  useEffect(() => {
    try {
      if (studentId) {
        localStorage.setItem('synclearn-student-id', studentId);
      } else {
        localStorage.removeItem('synclearn-student-id');
      }
    } catch {
      // ignore persistence errors
    }
  }, [studentId]);

  useEffect(() => {
    if (role === 'teacher') {
      setView('teacher-home');
      setBottomTab('chat');
    } else if (role === 'student') {
      setView('learn');
      setBottomTab('chat');
    }
  }, [role]);

  useEffect(() => {
    if (role === 'student' && (view === 'dashboard' || view === 'teacher-home')) {
      setView('learn');
    }
  }, [role, view]);

  const loadCourses = useCallback(async () => {
    try {
      const res = await getCourses();
      setCourses(res.data);
      setCurrentCourse((current) => {
        if (!res.data.length) return null;
        if (current && res.data.some((course) => course.id === current.id)) {
          return current;
        }
        return res.data[0];
      });
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

  const handleJumpToTimestamp = (timestamp, videoId = null) => {
    if (videoId != null) {
      setPreferredVideoId(videoId);
    }
    setVideoTimestamp(timestamp);
    setVideoSeekSignal((v) => v + 1);
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

  const handleChooseRole = (nextRole) => {
    if (nextRole === 'student') {
      const detectedId = normalizeStudentId(detectStudentId());
      if (detectedId) {
        setStudentId(detectedId);
      } else {
        const input = window.prompt('Cannot auto-detect student ID. Please enter your student ID:');
        const manualId = normalizeStudentId(input);
        if (!manualId) {
          alert('Student ID is required to enter student mode.');
          return;
        }
        setStudentId(manualId);
      }
    }
    setRole(nextRole);
  };

  const handleLogout = () => {
    setRole(null);
    setView('learn');
    setBottomTab('chat');
    setVideoTimestamp(0);
    setVideoSeekSignal(0);
    setCurrentVideoTime(0);
    setCurrentVideoId(null);
    setPreferredVideoId(null);
    setSlidePage(null);
  };

  const handleResetStudentId = () => {
    const input = window.prompt('Enter your student ID:');
    const manualId = normalizeStudentId(input);
    if (!manualId) {
      alert('Student ID was not updated.');
      return;
    }
    setStudentId(manualId);
  };

  if (!role) {
    const detectedId = normalizeStudentId(detectStudentId());
    return <RoleGate onChoose={handleChooseRole} detectedStudentId={detectedId} />;
  }

  return (
    <div className="flex h-full min-h-0 w-full text-stone-800">
      <SideNav
        view={view}
        onViewChange={setView}
        onFocusCourses={focusCourseSelect}
        onOpenAiTab={openAiTab}
        role={role}
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
          <div className="flex flex-wrap items-center gap-3">
            <div className="rounded-full border border-stone-200/80 bg-white/80 px-3 py-1.5 text-xs text-stone-600">
              Role: <span className="font-semibold text-stone-800">{role === 'teacher' ? 'Teacher' : 'Student'}</span>
            </div>
            {role === 'student' && studentId && (
              <div className="rounded-full border border-stone-200/80 bg-white/80 px-3 py-1.5 text-xs text-stone-600">
                Student ID: <span className="font-semibold text-stone-800">{studentId}</span>
              </div>
            )}
            {role === 'student' && (
              <button
                type="button"
                onClick={handleResetStudentId}
                className="rounded-control border border-stone-300/90 bg-white px-3 py-1.5 text-xs text-stone-700 transition hover:border-red-800/35"
              >
                Change Student ID
              </button>
            )}
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-control border border-stone-300/90 bg-[#F5EFE3]/80 px-3 py-1.5 text-xs text-stone-700 transition hover:border-red-800/35 hover:bg-[#EDE4D6]"
            >
              Logout
            </button>
            <CourseSelector
              courses={courses}
              currentCourse={currentCourse}
              onSelect={setCurrentCourse}
              onCreate={handleCreateCourse}
              allowCreate={role === 'teacher'}
            />
          </div>
        </header>

        {role === 'teacher' && view === 'teacher-home' ? (
          <div className="min-h-0 flex-1 overflow-auto p-6">
            <div className="sync-glass sync-glass-hover mx-auto max-w-6xl rounded-card p-6">
              <TeacherResourceManager
                courseId={currentCourse?.id}
                onCoursesChanged={loadCourses}
                onCourseCreated={setCurrentCourse}
                onCourseSelected={setCurrentCourse}
              />
            </div>
          </div>
        ) : role === 'teacher' && view === 'dashboard' ? (
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
            <section className="sync-glass sync-glass-hover flex min-w-0 flex-1 basis-0 flex-col overflow-hidden rounded-card border-stone-200/70">
              <SlidesPanel
                courseId={currentCourse?.id}
                courseTitle={currentCourse?.title}
                onJumpToTimestamp={handleJumpToTimestamp}
                currentVideoTime={currentVideoTime}
                targetSlidePage={slidePage}
                onSelectLinkedVideo={(video) => setPreferredVideoId(video?.id || null)}
              />
            </section>

            <section className="flex min-h-0 flex-1 basis-0 min-w-0 flex-col gap-5 overflow-y-auto">
              <div className="sync-glass sync-glass-hover flex min-h-0 flex-none flex-col overflow-hidden rounded-card border-stone-200/70">
                <VideoPlayer
                  courseId={currentCourse?.id}
                  seekTimestamp={videoTimestamp}
                  seekSignal={videoSeekSignal}
                  preferredVideoId={preferredVideoId}
                  onTimeUpdate={setCurrentVideoTime}
                  onJumpToSlide={handleJumpToSlide}
                  onCurrentVideoChange={setCurrentVideoId}
                />
              </div>

              <div className="sync-glass sync-glass-hover flex min-h-0 min-h-[360px] flex-1 flex-col overflow-hidden rounded-card border-stone-200/70">
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
