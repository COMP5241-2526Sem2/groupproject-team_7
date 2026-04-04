import React, { useState, useEffect, useCallback } from 'react';
import {
  getCourses,
  createCourse,
  updateCourse,
  deleteCourse,
  uploadSlide,
  getSlidesByCourse,
  deleteSlide,
  getVideosByCourse,
  createVideoLink,
  deleteVideo,
} from '../services/api';
import '../styles/TeacherDashboard.css';

const isSupportedVideoLink = (value) => {
  if (!value) return false;
  try {
    const parsed = new URL(value.trim());
    if (!/^https?:$/i.test(parsed.protocol)) return false;
    const host = (parsed.hostname || '').toLowerCase();
    const path = (parsed.pathname || '').toLowerCase();

    if (host.endsWith('youtube.com') || host.endsWith('youtu.be')) return true;
    if (host.endsWith('vimeo.com')) return true;
    if (path.endsWith('.mp4') || path.endsWith('.webm') || path.endsWith('.ogg') || path.endsWith('.mov')) return true;
    return false;
  } catch {
    return false;
  }
};

function TeacherResourceManager({ courseId, onCoursesChanged, onCourseCreated, onCourseSelected }) {
  const [courses, setCourses] = useState([]);
  const [coursesLoading, setCoursesLoading] = useState(false);
  const [newCourseTitle, setNewCourseTitle] = useState('');
  const [newCourseDescription, setNewCourseDescription] = useState('');
  const [editingCourseId, setEditingCourseId] = useState(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [editingDescription, setEditingDescription] = useState('');
  const [courseActionId, setCourseActionId] = useState(null);

  const [resourceSlides, setResourceSlides] = useState([]);
  const [resourceVideos, setResourceVideos] = useState([]);
  const [loadingResources, setLoadingResources] = useState(false);
  const [uploadingSlide, setUploadingSlide] = useState(false);
  const [addingVideoLink, setAddingVideoLink] = useState(false);
  const [videoLinkUrl, setVideoLinkUrl] = useState('');
  const [videoLinkTitle, setVideoLinkTitle] = useState('');

  const loadCourses = useCallback(async () => {
    setCoursesLoading(true);
    try {
      const res = await getCourses();
      setCourses(res.data || []);
    } catch (err) {
      console.error('Course list load failed:', err);
      setCourses([]);
    } finally {
      setCoursesLoading(false);
    }
  }, []);

  const refreshCourses = useCallback(async () => {
    await loadCourses();
    onCoursesChanged?.();
  }, [loadCourses, onCoursesChanged]);

  const loadResourceData = useCallback(async (targetCourseId = courseId) => {
    if (!targetCourseId) return;
    setLoadingResources(true);
    try {
      const [slidesRes, videosRes] = await Promise.all([
        getSlidesByCourse(targetCourseId),
        getVideosByCourse(targetCourseId),
      ]);
      setResourceSlides(slidesRes.data || []);
      setResourceVideos(videosRes.data || []);
    } catch (err) {
      console.error('Resource load failed:', err);
      setResourceSlides([]);
      setResourceVideos([]);
    } finally {
      setLoadingResources(false);
    }
  }, [courseId]);

  useEffect(() => {
    loadCourses();
  }, [loadCourses]);

  useEffect(() => {
    if (courseId) {
      loadResourceData(courseId);
    } else {
      setResourceSlides([]);
      setResourceVideos([]);
    }
  }, [courseId, loadResourceData]);

  const handleCreateCourse = async () => {
    const title = newCourseTitle.trim();
    if (!title || courseActionId) return;
    setCourseActionId('create');
    try {
      const res = await createCourse({ title, description: newCourseDescription.trim() });
      setNewCourseTitle('');
      setNewCourseDescription('');
      onCourseCreated?.(res.data);
      await refreshCourses();
    } catch (err) {
      console.error('Create course failed:', err);
      alert('Failed to create course: ' + (err.response?.data?.error || err.message));
    } finally {
      setCourseActionId(null);
    }
  };

  const handleSelectCourse = (course) => {
    onCourseSelected?.(course);
  };

  const startEditCourse = (course) => {
    setEditingCourseId(course.id);
    setEditingTitle(course.title || '');
    setEditingDescription(course.description || '');
  };

  const cancelEditCourse = () => {
    setEditingCourseId(null);
    setEditingTitle('');
    setEditingDescription('');
  };

  const handleSaveCourse = async (courseIdToSave) => {
    if (courseActionId) return;
    const title = editingTitle.trim();
    if (!title) {
      alert('Course title is required.');
      return;
    }
    setCourseActionId(courseIdToSave);
    try {
      await updateCourse(courseIdToSave, {
        title,
        description: editingDescription.trim(),
      });
      cancelEditCourse();
      await refreshCourses();
    } catch (err) {
      console.error('Update course failed:', err);
      alert('Failed to update course: ' + (err.response?.data?.error || err.message));
    } finally {
      setCourseActionId(null);
    }
  };

  const handleDeleteCourse = async (course) => {
    if (courseActionId) return;
    if (!window.confirm(`Delete course "${course.title}"? This will remove its resources too.`)) {
      return;
    }
    setCourseActionId(course.id);
    try {
      await deleteCourse(course.id);
      if (editingCourseId === course.id) {
        cancelEditCourse();
      }
      await refreshCourses();
    } catch (err) {
      console.error('Delete course failed:', err);
      alert('Failed to delete course: ' + (err.response?.data?.error || err.message));
    } finally {
      setCourseActionId(null);
    }
  };

  const handleUploadSlide = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !courseId || uploadingSlide) return;
    setUploadingSlide(true);
    try {
      await uploadSlide(courseId, file);
      await Promise.all([loadResourceData(courseId), refreshCourses()]);
    } catch (err) {
      console.error('Slide upload failed:', err);
      alert('Failed to upload document: ' + (err.response?.data?.error || err.message));
    } finally {
      setUploadingSlide(false);
    }
  };

  const handleAddVideoLink = async () => {
    if (!courseId || addingVideoLink) return;
    const url = videoLinkUrl.trim();
    if (!/^https?:\/\//i.test(url)) {
      alert('Please enter a valid http(s) video URL.');
      return;
    }
    if (!isSupportedVideoLink(url)) {
      alert('Unsupported link. Please use a YouTube/Vimeo URL or a direct video file link (.mp4/.webm/.ogg/.mov).');
      return;
    }
    setAddingVideoLink(true);
    try {
      await createVideoLink(courseId, url, videoLinkTitle.trim());
      setVideoLinkUrl('');
      setVideoLinkTitle('');
      await Promise.all([loadResourceData(courseId), refreshCourses()]);
    } catch (err) {
      console.error('Video link save failed:', err);
      alert('Failed to save video link: ' + (err.response?.data?.error || err.message));
    } finally {
      setAddingVideoLink(false);
    }
  };

  const handleDeleteResourceSlide = async (slideId) => {
    if (!window.confirm('Delete this document resource?')) return;
    try {
      await deleteSlide(slideId);
      await Promise.all([loadResourceData(courseId), refreshCourses()]);
    } catch (err) {
      console.error('Delete slide failed:', err);
      alert('Failed to delete document: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleDeleteResourceVideo = async (videoId) => {
    if (!window.confirm('Delete this video resource?')) return;
    try {
      await deleteVideo(videoId);
      await Promise.all([loadResourceData(courseId), refreshCourses()]);
    } catch (err) {
      console.error('Delete video failed:', err);
      alert('Failed to delete video resource: ' + (err.response?.data?.error || err.message));
    }
  };

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <div>
          <h2>Teacher Resource Home</h2>
          <p className="dashboard-subtitle">
            Manage course containers and upload teaching resources for students.
          </p>
        </div>
      </div>

      <div className="dashboard-section course-management-section">
        <div className="dashboard-section-head">
          <div>
            <h3>Course Management</h3>
            <p className="dashboard-section-desc">
              Create, edit, or delete courses. These are the teacher-owned containers for PPT/PDF and video resources.
            </p>
          </div>
          <button
            type="button"
            className="generate-brief-btn"
            onClick={refreshCourses}
            disabled={coursesLoading}
          >
            {coursesLoading ? 'Refreshing...' : 'Refresh Courses'}
          </button>
        </div>

        <div className="course-create-form">
          <input
            className="course-create-input"
            placeholder="Course title"
            value={newCourseTitle}
            onChange={(e) => setNewCourseTitle(e.target.value)}
          />
          <input
            className="course-create-input course-create-input-wide"
            placeholder="Course description (optional)"
            value={newCourseDescription}
            onChange={(e) => setNewCourseDescription(e.target.value)}
          />
          <button
            type="button"
            className="generate-brief-btn"
            onClick={handleCreateCourse}
            disabled={courseActionId === 'create'}
          >
            {courseActionId === 'create' ? 'Creating...' : 'Create Course'}
          </button>
        </div>

        <div className="course-management-list">
          {courses.length > 0 ? (
            courses.map((course) => {
              const isEditing = editingCourseId === course.id;
              const isActive = courseId === course.id;
              return (
                <div
                  key={course.id}
                  className={`course-management-item ${isActive ? 'is-active' : ''} cursor-pointer text-left`}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleSelectCourse(course)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSelectCourse(course);
                    }
                  }}
                >
                  {isEditing ? (
                    <div className="course-edit-form">
                      <input
                        className="course-create-input"
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                      />
                      <input
                        className="course-create-input course-create-input-wide"
                        value={editingDescription}
                        onChange={(e) => setEditingDescription(e.target.value)}
                      />
                      <div className="course-edit-actions">
                        <button
                          type="button"
                          className="generate-brief-btn"
                          onClick={() => handleSaveCourse(course.id)}
                          disabled={courseActionId === course.id}
                        >
                          {courseActionId === course.id ? 'Saving...' : 'Save'}
                        </button>
                        <button
                          type="button"
                          className="course-secondary-btn"
                          onClick={cancelEditCourse}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="course-management-info">
                        <div className="course-management-title-row">
                          <strong>{course.title}</strong>
                          {isActive && <span className="course-active-badge">Current</span>}
                        </div>
                        <p>{course.description || 'No description provided.'}</p>
                        <div className="course-management-meta">
                          <span>{course.slides_count || 0} slides</span>
                          <span>{course.videos_count || 0} videos</span>
                        </div>
                      </div>
                      <div className="course-edit-actions">
                        <button
                          type="button"
                          className="course-secondary-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            startEditCourse(course);
                          }}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="course-delete-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteCourse(course);
                          }}
                          disabled={courseActionId === course.id}
                        >
                          Delete
                        </button>
                      </div>
                    </>
                  )}
                </div>
              );
            })
          ) : (
            <p className="dashboard-no-data">No courses yet. Create one to start managing resources.</p>
          )}
        </div>
      </div>

      <div className="dashboard-section course-management-section">
        <div className="dashboard-section-head">
          <div>
            <h3>Course Resource Management</h3>
            <p className="dashboard-section-desc">
              For the selected course, upload PPT/PDF/PPTX documents and register lecture replay video links.
            </p>
          </div>
          <button
            type="button"
            className="generate-brief-btn"
            onClick={() => loadResourceData(courseId)}
            disabled={!courseId || loadingResources}
          >
            {loadingResources ? 'Refreshing...' : 'Refresh Resources'}
          </button>
        </div>

        {courseId ? (
          <div className="resource-grid">
            <div className="resource-card">
              <h4>Document Storage (PPT/PDF/PPTX)</h4>
              <p className="resource-hint">Upload course slides for students to open and review.</p>
              <label className="resource-upload-btn">
                <input
                  type="file"
                  accept=".pdf,.ppt,.pptx,application/pdf,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                  onChange={handleUploadSlide}
                  disabled={uploadingSlide}
                />
                {uploadingSlide ? 'Uploading...' : 'Upload Document'}
              </label>
              <div className="resource-list">
                {resourceSlides.length > 0 ? (
                  resourceSlides.map((slide) => (
                    <div key={slide.id} className="resource-item">
                      <div>
                        <div className="resource-title">{slide.original_filename}</div>
                        <div className="resource-meta">{slide.total_pages || 0} pages</div>
                      </div>
                      <button
                        type="button"
                        className="course-delete-btn"
                        onClick={() => handleDeleteResourceSlide(slide.id)}
                      >
                        Delete
                      </button>
                    </div>
                  ))
                ) : (
                  <p className="dashboard-no-data">No documents uploaded yet.</p>
                )}
              </div>
            </div>

            <div className="resource-card">
              <h4>Video Storage (Replay Link)</h4>
              <p className="resource-hint">Paste a lecture replay URL so students can open it in the player.</p>
              <div className="resource-link-form">
                <input
                  className="course-create-input"
                  placeholder="Video title (optional)"
                  value={videoLinkTitle}
                  onChange={(e) => setVideoLinkTitle(e.target.value)}
                />
                <input
                  className="course-create-input"
                  placeholder="https://..."
                  value={videoLinkUrl}
                  onChange={(e) => setVideoLinkUrl(e.target.value)}
                />
                <button
                  type="button"
                  className="generate-brief-btn"
                  onClick={handleAddVideoLink}
                  disabled={addingVideoLink}
                >
                  {addingVideoLink ? 'Saving...' : 'Add Video Link'}
                </button>
              </div>
              <div className="resource-list">
                {resourceVideos.length > 0 ? (
                  resourceVideos.map((video) => (
                    <div key={video.id} className="resource-item">
                      <div>
                        <div className="resource-title">{video.original_filename}</div>
                        <div className="resource-meta">
                          {video.source_type === 'external' ? 'External link' : 'Uploaded video'}
                        </div>
                      </div>
                      <div className="resource-actions">
                        {video.external_url && (
                          <a
                            href={video.external_url}
                            target="_blank"
                            rel="noreferrer"
                            className="course-secondary-btn"
                          >
                            Open
                          </a>
                        )}
                        <button
                          type="button"
                          className="course-delete-btn"
                          onClick={() => handleDeleteResourceVideo(video.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="dashboard-no-data">No video resources yet.</p>
                )}
              </div>
            </div>
          </div>
        ) : (
          <p className="dashboard-no-data">Select a course first, then manage its document and video resources.</p>
        )}
      </div>
    </div>
  );
}

export default TeacherResourceManager;