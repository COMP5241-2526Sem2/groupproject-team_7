import React, { useState } from 'react';
import { BookOpen } from 'lucide-react';

function CourseSelector({ courses, currentCourse, onSelect, onCreate, allowCreate = true }) {
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState('');

  const handleCreate = () => {
    if (newTitle.trim()) {
      onCreate(newTitle.trim());
      setNewTitle('');
      setShowCreate(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-2 text-stone-500">
        <BookOpen className="h-4 w-4 text-red-800/90" />
        <label htmlFor="synclearn-course-select" className="text-xs font-medium">
          Course
        </label>
      </div>
      <select
        id="synclearn-course-select"
        className="sync-input-cmd min-w-[160px] max-w-[240px] cursor-pointer text-xs"
        value={currentCourse?.id || ''}
        onChange={(e) => {
          const c = courses.find((x) => x.id === Number(e.target.value));
          if (c) onSelect(c);
        }}
      >
        {courses.length === 0 && <option value="">No courses yet</option>}
        {courses.map((c) => (
          <option key={c.id} value={c.id}>
            {c.title}
          </option>
        ))}
      </select>
      {allowCreate && !showCreate ? (
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="rounded-control border border-stone-300/90 bg-[#F5EFE3]/80 px-3 py-1.5 text-xs text-stone-700 transition hover:border-red-800/35 hover:bg-[#EDE4D6]"
        >
          + New Course
        </button>
      ) : allowCreate ? (
        <div className="flex flex-wrap items-center gap-2">
          <input
            className="sync-input-cmd w-40 text-xs"
            placeholder="Course title..."
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            autoFocus
          />
          <button
            type="button"
            onClick={handleCreate}
            className="rounded-control bg-gradient-to-r from-red-800 to-red-950 px-3 py-1.5 text-xs font-medium text-[#FFFBF7]"
          >
            Create
          </button>
          <button
            type="button"
            onClick={() => setShowCreate(false)}
            className="rounded-control border border-stone-300/80 px-3 py-1.5 text-xs text-stone-500 hover:bg-stone-100"
          >
            Cancel
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default CourseSelector;
