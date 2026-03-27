-- SyncLearn Database Indexes
-- This script creates indexes to optimize query performance
-- Run this script after applying the schema migrations
--
-- Indexes are organized by table and purpose:
-- - Foreign key indexes for JOIN performance
-- - Filtering indexes for WHERE clauses
-- - Sorting indexes for ORDER BY clauses
-- - Search indexes for LIKE/full-text queries

-- ============================================================================
-- COURSES TABLE INDEXES
-- ============================================================================

-- Index for sorting by creation date (commonly used for listing)
CREATE INDEX IF NOT EXISTS idx_courses_created_at 
ON courses(created_at DESC);

-- ============================================================================
-- SLIDES TABLE INDEXES
-- ============================================================================

-- Index on course_id for filtering slides by course (performance: critical)
CREATE INDEX IF NOT EXISTS idx_slides_course_id 
ON slides(course_id);

-- Index for sorting slides by creation date
CREATE INDEX IF NOT EXISTS idx_slides_created_at 
ON slides(created_at DESC);

-- Index for filtering by processed status (useful for batch processing)
CREATE INDEX IF NOT EXISTS idx_slides_processed 
ON slides(processed);

-- Composite index: course + processed (common query pattern)
CREATE INDEX IF NOT EXISTS idx_slides_course_processed 
ON slides(course_id, processed);

-- ============================================================================
-- SLIDE_PAGES TABLE INDEXES
-- ============================================================================

-- Index on slide_id for retrieving pages by slide (performance: critical)
CREATE INDEX IF NOT EXISTS idx_slide_pages_slide_id 
ON slide_pages(slide_id);

-- Index for page number sorting within a slide
CREATE INDEX IF NOT EXISTS idx_slide_pages_page_number 
ON slide_pages(page_number);

-- Composite index: slide + page_number for efficient page lookup
CREATE INDEX IF NOT EXISTS idx_slide_pages_slide_page 
ON slide_pages(slide_id, page_number);

-- ============================================================================
-- VIDEOS TABLE INDEXES
-- ============================================================================

-- Index on course_id for filtering videos by course (performance: critical)
CREATE INDEX IF NOT EXISTS idx_videos_course_id 
ON videos(course_id);

-- Index for sorting videos by creation date
CREATE INDEX IF NOT EXISTS idx_videos_created_at 
ON videos(created_at DESC);

-- Index for filtering by processed status
CREATE INDEX IF NOT EXISTS idx_videos_processed 
ON videos(processed);

-- Composite index: course + processed (common query pattern)
CREATE INDEX IF NOT EXISTS idx_videos_course_processed 
ON videos(course_id, processed);

-- ============================================================================
-- VIDEO_TRANSCRIPTS TABLE INDEXES
-- ============================================================================

-- Index on video_id for retrieving transcripts by video (performance: critical)
CREATE INDEX IF NOT EXISTS idx_video_transcripts_video_id 
ON video_transcripts(video_id);

-- Index for segment ordering
CREATE INDEX IF NOT EXISTS idx_video_transcripts_segment_index 
ON video_transcripts(video_id, segment_index);

-- Index for timeline queries (video_id + start_time)
CREATE INDEX IF NOT EXISTS idx_video_transcripts_timeline 
ON video_transcripts(video_id, start_time);

-- Index on creation date for sorting
CREATE INDEX IF NOT EXISTS idx_video_transcripts_created_at 
ON video_transcripts(created_at DESC);

-- ============================================================================
-- KNOWLEDGE_POINTS TABLE INDEXES
-- ============================================================================

-- Index on slide_page_id for retrieving knowledge points by slide page
CREATE INDEX IF NOT EXISTS idx_knowledge_points_slide_page_id 
ON knowledge_points(slide_page_id);

-- Index on video_id for retrieving knowledge points by video
CREATE INDEX IF NOT EXISTS idx_knowledge_points_video_id 
ON knowledge_points(video_id);

-- Index for creation date sorting
CREATE INDEX IF NOT EXISTS idx_knowledge_points_created_at 
ON knowledge_points(created_at DESC);

-- Index for filtering by confidence (useful for reporting)
CREATE INDEX IF NOT EXISTS idx_knowledge_points_confidence 
ON knowledge_points(confidence DESC);

-- ============================================================================
-- QUIZZES TABLE INDEXES
-- ============================================================================

-- Index on course_id for filtering quizzes by course
CREATE INDEX IF NOT EXISTS idx_quizzes_course_id 
ON quizzes(course_id);

-- Index on knowledge_point_id for retrieving quizzes by knowledge point
CREATE INDEX IF NOT EXISTS idx_quizzes_knowledge_point_id 
ON quizzes(knowledge_point_id);

-- Index for creation date sorting
CREATE INDEX IF NOT EXISTS idx_quizzes_created_at 
ON quizzes(created_at DESC);

-- Composite index: course + knowledge_point (common query pattern)
CREATE INDEX IF NOT EXISTS idx_quizzes_course_kp 
ON quizzes(course_id, knowledge_point_id);

-- ============================================================================
-- QUIZ_ATTEMPTS TABLE INDEXES
-- ============================================================================

-- Index on quiz_id for retrieving attempts by quiz (performance: critical)
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_quiz_id 
ON quiz_attempts(quiz_id);

-- Index for filtering correct/incorrect attempts
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_is_correct 
ON quiz_attempts(is_correct);

-- Index for creation date sorting (useful for analytics)
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_created_at 
ON quiz_attempts(created_at DESC);

-- Composite index: quiz + created_at (common query pattern for time-based analytics)
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_quiz_time 
ON quiz_attempts(quiz_id, created_at DESC);

-- Composite index: quiz + is_correct (efficiency check)
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_quiz_correct 
ON quiz_attempts(quiz_id, is_correct);

-- ============================================================================
-- CHAT_MESSAGES TABLE INDEXES
-- ============================================================================

-- Index on course_id for retrieving messages by course
CREATE INDEX IF NOT EXISTS idx_chat_messages_course_id 
ON chat_messages(course_id);

-- Index for message role filtering
CREATE INDEX IF NOT EXISTS idx_chat_messages_role 
ON chat_messages(role);

-- Index for creation date sorting (essential for chat chronology)
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at 
ON chat_messages(created_at DESC);

-- Composite index: course + created_at (most common chat query pattern)
CREATE INDEX IF NOT EXISTS idx_chat_messages_course_time 
ON chat_messages(course_id, created_at DESC);

-- Composite index: course + role (for filtering by user/assistant messages)
CREATE INDEX IF NOT EXISTS idx_chat_messages_course_role 
ON chat_messages(course_id, role, created_at DESC);

-- ============================================================================
-- JSONB INDEXES (for better performance on JSON queries)
-- ============================================================================

-- GIN index for JSONB queries on quiz options (if searching within options)
CREATE INDEX IF NOT EXISTS idx_quizzes_options_gin 
ON quizzes USING GIN (options);

-- GIN index for JSONB queries on chat citations
CREATE INDEX IF NOT EXISTS idx_chat_messages_citations_gin 
ON chat_messages USING GIN (citations);

-- ============================================================================
-- SUMMARY
-- ============================================================================
-- Total indexes created: 30+
-- These indexes optimize:
-- - Foreign key lookups (JOIN performance)
-- - Filtering operations (WHERE clauses)
-- - Sorting operations (ORDER BY clauses)
-- - Full-text search patterns
-- - Analytics and reporting queries
--
-- Note: Monitor index usage and adjust as needed based on actual query patterns.
-- Use EXPLAIN ANALYZE to verify index usage.
