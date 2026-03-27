-- SyncLearn Database Schema Migration
-- This script initializes all required tables for the Supabase PostgreSQL database
-- Compatible with Supabase and standard PostgreSQL 12+
-- 
-- Run this script in order to set up the database schema.
-- In Supabase: Navigate to SQL Query editor and paste this entire script.

-- Create courses table
-- Stores course metadata and information
CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create slides table
-- Stores slide file metadata (PDFs, PPTs, etc.)
CREATE TABLE IF NOT EXISTS slides (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(10) NOT NULL, -- pdf, ppt, pptx
    file_path VARCHAR(500) NOT NULL,
    total_pages INTEGER DEFAULT 0,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create slide_pages table
-- Stores individual slide page content and embeddings
CREATE TABLE IF NOT EXISTS slide_pages (
    id SERIAL PRIMARY KEY,
    slide_id INTEGER NOT NULL REFERENCES slides(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    content_text TEXT DEFAULT '',
    thumbnail_path VARCHAR(500) DEFAULT '',
    embedding BYTEA, -- serialized float32 array for vector embeddings
    UNIQUE(slide_id, page_number)
);

-- Create videos table
-- Stores video file metadata
CREATE TABLE IF NOT EXISTS videos (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    duration FLOAT DEFAULT 0, -- seconds
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create video_transcripts table
-- Stores ASR transcript segments for videos with timestamps
CREATE TABLE IF NOT EXISTS video_transcripts (
    id SERIAL PRIMARY KEY,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    segment_index INTEGER NOT NULL,
    start_time FLOAT NOT NULL, -- seconds
    end_time FLOAT NOT NULL, -- seconds
    text TEXT NOT NULL,
    embedding BYTEA, -- serialized float32 array for vector embeddings
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(video_id, segment_index)
);

-- Create knowledge_points table
-- Stores learning objectives and content alignment between slides and videos
CREATE TABLE IF NOT EXISTS knowledge_points (
    id SERIAL PRIMARY KEY,
    slide_page_id INTEGER NOT NULL REFERENCES slide_pages(id) ON DELETE CASCADE,
    video_id INTEGER REFERENCES videos(id) ON DELETE SET NULL,
    title VARCHAR(300) NOT NULL,
    content TEXT DEFAULT '',
    video_timestamp FLOAT, -- seconds into video
    confidence FLOAT DEFAULT 0.0, -- alignment confidence score
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create quizzes table
-- Stores quiz questions associated with courses and knowledge points
CREATE TABLE IF NOT EXISTS quizzes (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    knowledge_point_id INTEGER REFERENCES knowledge_points(id) ON DELETE SET NULL,
    question TEXT NOT NULL,
    options JSONB NOT NULL, -- ["A. ...", "B. ...", ...]
    correct_answer VARCHAR(10) NOT NULL,
    explanation TEXT DEFAULT '',
    video_timestamp FLOAT, -- seconds
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create quiz_attempts table
-- Stores student attempts and responses to quiz questions
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id SERIAL PRIMARY KEY,
    quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    selected_answer VARCHAR(10) NOT NULL,
    is_correct BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create chat_messages table
-- Stores chat messages between users and the AI assistant
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- user / assistant
    content TEXT NOT NULL,
    citations JSONB DEFAULT '[]', -- [{type, source, timestamp, ...}]
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create updated_at trigger for courses table
-- Automatically updates the updated_at timestamp when a record is modified
CREATE OR REPLACE FUNCTION update_courses_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS courses_updated_at_trigger ON courses;
CREATE TRIGGER courses_updated_at_trigger
BEFORE UPDATE ON courses
FOR EACH ROW
EXECUTE FUNCTION update_courses_updated_at();
