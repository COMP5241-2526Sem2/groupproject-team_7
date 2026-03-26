import React, { useState } from 'react';
import '../styles/CourseSelector.css';

function CourseSelector({ courses, currentCourse, onSelect, onCreate }) {
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
    <div className="course-selector">
      <label className="cs-label">Course:</label>
      <select
        className="cs-select"
        value={currentCourse?.id || ''}
        onChange={(e) => {
          const c = courses.find((c) => c.id === Number(e.target.value));
          if (c) onSelect(c);
        }}
      >
        {courses.length === 0 && <option value="">No courses</option>}
        {courses.map((c) => (
          <option key={c.id} value={c.id}>
            {c.title}
          </option>
        ))}
      </select>
      {!showCreate ? (
        <button className="cs-btn" onClick={() => setShowCreate(true)}>
          + New Course
        </button>
      ) : (
        <div className="cs-create-form">
          <input
            className="cs-input"
            placeholder="Course title..."
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            autoFocus
          />
          <button className="cs-btn cs-btn-confirm" onClick={handleCreate}>
            Create
          </button>
          <button className="cs-btn" onClick={() => setShowCreate(false)}>
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

export default CourseSelector;
