import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// --- Courses ---
export const getCourses = () => api.get('/courses');
export const createCourse = (data) => api.post('/courses', data);
export const getCourse = (id) => api.get(`/courses/${id}`);
export const updateCourse = (id, data) => api.put(`/courses/${id}`, data);
export const deleteCourse = (id) => api.delete(`/courses/${id}`);

// --- Slides ---
export const uploadSlide = (courseId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('course_id', courseId);
  return api.post('/slides/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const getSlidesByCourse = (courseId) => api.get(`/slides/course/${courseId}`);
export const getSlide = (id) => api.get(`/slides/${id}`);
export const deleteSlide = (id) => api.delete(`/slides/${id}`);
export const getSlideFileUrl = (filename) => `${API_BASE}/slides/file/${filename}`;
export const getPageImageUrl = (pageId) => `${API_BASE}/slides/page-image/${pageId}`;

// --- Videos ---
const CHUNK_SIZE = 5 * 1024 * 1024; // 5 MB per chunk

export const uploadVideo = async (courseId, file, onUploadProgress) => {
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
  const totalSize = file.size;
  let uploadedBytes = 0;

  // 1. Init
  const initRes = await api.post('/videos/upload/init', {
    filename: file.name,
    course_id: courseId,
    total_chunks: totalChunks,
  });
  const { upload_id } = initRes.data;

  // 2. Upload chunks sequentially
  for (let i = 0; i < totalChunks; i++) {
    const start = i * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, file.size);
    const chunk = file.slice(start, end);

    const formData = new FormData();
    formData.append('file', chunk);
    formData.append('upload_id', upload_id);
    formData.append('chunk_index', i);

    await api.post('/videos/upload/chunk', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
      onUploadProgress: (e) => {
        if (onUploadProgress) {
          const loaded = uploadedBytes + (e.loaded || 0);
          onUploadProgress({ loaded, total: totalSize });
        }
      },
    });
    uploadedBytes += (end - start);
    if (onUploadProgress) {
      onUploadProgress({ loaded: uploadedBytes, total: totalSize });
    }
  }

  // 3. Complete
  const completeRes = await api.post('/videos/upload/complete', { upload_id });
  return completeRes;
};
export const getVideosByCourse = (courseId) => api.get(`/videos/course/${courseId}`);
export const getVideo = (id) => api.get(`/videos/${id}`);
export const deleteVideo = (id) => api.delete(`/videos/${id}`);
export const getVideoStreamUrl = (filename) => `${API_BASE}/videos/stream/${filename}`;
export const transcribeVideo = (videoId) => api.post(`/videos/${videoId}/transcribe`);
export const getTranscribeStatus = (videoId) => api.get(`/videos/${videoId}/transcribe/status`);
export const getVideoTranscript = (videoId) => api.get(`/videos/${videoId}/transcript`);

// --- Chat ---
export const getChatHistory = (courseId) => api.get(`/chat/${courseId}`);
export const sendChatMessage = (courseId, content) =>
  api.post(`/chat/${courseId}`, { content });
export const clearChat = (courseId) => api.delete(`/chat/${courseId}`);

// --- Knowledge Points ---
export const extractKnowledgePoints = (slideId) =>
  api.post(`/knowledge-points/extract/${slideId}`);
export const getExtractKPStatus = (slideId) =>
  api.get(`/knowledge-points/extract/${slideId}/status`);
export const getKnowledgePointsByCourse = (courseId) =>
  api.get(`/knowledge-points/course/${courseId}`);
export const getKnowledgePointsByPage = (pageId) =>
  api.get(`/knowledge-points/page/${pageId}`);
export const deleteKnowledgePoint = (kpId) =>
  api.delete(`/knowledge-points/${kpId}`);
export const realignKnowledgePoints = (courseId) =>
  api.post(`/knowledge-points/align/${courseId}`);

// --- Quizzes ---
export const generateQuizzes = (courseId, numQuestions = 5) =>
  api.post(`/quizzes/generate/${courseId}`, { num_questions: numQuestions });
export const getQuizzes = (courseId) => api.get(`/quizzes/course/${courseId}`);
export const submitQuizAttempt = (quizId, selectedAnswer) =>
  api.post(`/quizzes/${quizId}/attempt`, { selected_answer: selectedAnswer });
export const clearQuizzes = (courseId) => api.delete(`/quizzes/course/${courseId}`);
export const getQuizStats = (courseId) => api.get(`/quizzes/stats/${courseId}`);

// --- Dashboard ---
export const getDashboardSummary = (courseId) => api.get(`/dashboard/summary/${courseId}`);
export const getDifficultyAnalysis = (courseId) => api.get(`/dashboard/difficulty/${courseId}`);
export const getChatInsights = (courseId) => api.get(`/dashboard/chat-insights/${courseId}`);
export const generateReviewBrief = (courseId) => api.post(`/dashboard/review-brief/${courseId}`);

export default api;
