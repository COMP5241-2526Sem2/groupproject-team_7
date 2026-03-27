# Sync Learn: Multimodal AI Smart Review Platform

> An AI-synchronized learning ecosystem that semantically aligns lecture notes with videos, creating a closed loop of "learning-practice-assessment."

[![Open in Codespaces](https://classroom.github.com/assets/launch-codespace-2972f46106e565e64193e422d61a12cf1da4916b45550586e14ef0a7c637dd04.svg)](https://classroom.github.com/open-in-codespaces?assignment_repo_id=22668957)

---

## Background

Currently, students face a disconnection between lecture notes and videos during review. When encountering difficult points in their notes, students waste significant time manually searching for corresponding explanations in lengthy videos. Meanwhile, teachers lack precise insights into students' actual knowledge gaps, making final reviews unfocused and inefficient.

**Sync Learn** addresses this gap through a semantic alignment engine that automatically matches knowledge points in lecture notes with key video frames, shifting students from "passive viewing" to "active learning."

---

## Core Objectives

- **Semantic Alignment**: Automatically match knowledge points in notes with key video frames for instant navigation
- **Immediate Feedback**: Enable "learning by doing" through AI-generated quizzes
- **Learning Insights**: Provide teachers with video heatmaps and AI-generated review briefs

---

## Core Modules

The platform features a **three-panel layout** that integrates the entire learning process:

| Module | Interaction Mode | Core Functions |
|:-------|:-----------------|:----------------|
| **① Interactive Notes Module** (Left) | Uploaded by teachers/students + AI recognition | PPT/PDF display, knowledge point anchors, real-time highlighting |
| **② Smart Video Player Module** (Top Right) | Uploaded by teachers + AI indexing | Video playback, progress bar heatmap, keyframe navigation |
| **③ AI Learning Assistant Module** (Bottom Right) | AI-generated | Q&A dialog, instant quizzes, wrong-answer backtracking |

---

## Core Interaction Logic

### 1. Notes-Video Synchronization

The system leverages an AI engine (ASR + OCR + Embedding) to achieve precise alignment:

- **Hover Interaction**: Hovering over a knowledge point in the notes reveals a "Jump to Explanation" icon
- **Instant Navigation**: Clicking the icon jumps the video to the corresponding timestamp (accurate to the second)
- **Visual Tracking**: As the video plays, the corresponding paragraph in the notes highlights and auto-scrolls

### 2. "Learn-and-Practice" AI Quizzes

- **Automatic Trigger**: Quiz appears after a knowledge point segment finishes playing
- **Manual Trigger**: Students click "Knowledge Check" in the dialog box
- **Wrong-Answer Backtracking**: Incorrect answers link directly back to the relevant video segment for remediation

### 3. AI Learning Assistant

- Leverages RAG technology to provide answers with precise multimodal citations (keyframes, slide regions, video timestamps)
- Supports natural language queries and returns answers with source references

---

## Teacher Dashboard: Learning Insights

### Student Behavior Heatmap

| Dimension | Visualization | Business Insight |
|:----------|:---------------|:------------------|
| **Video Progress Bar** | Color overlay (Red = High frequency) | Identifies segments frequently rewatched, paused, or skipped |
| **Notes Pages** | Heat bar next to thumbnails | Highlights "problematic" pages where students struggle |

### AI-Generated Review Brief

The system automatically generates a natural language summary that identifies:

- **Difficulty Extraction**: Top 5 knowledge points with highest quiz error rates
- **Query Clustering**: Semantic clustering of student questions from the dialog
- **Review Recommendations**: Targeted suggestions, e.g., "Recommend focusing on this formula derivation during the review session"

---

## Technical Implementation

### Core Algorithms

- **Semantic Alignment Engine**: ASR (speech-to-text) + OCR + Embedding for knowledge point-to-video frame matching
- **RAG Technology**: AI assistant retrieves information from course materials to provide answers with source citations

### Backend Architecture

**Asynchronous Processing**: Celery + Vercel Redis handle complex media file processing without impacting user experience

| Layer | Technology |
|:------|:----------|
| Frontend | React 18 |
| Backend | Flask |
| Database | Supabase (PostgreSQL) |
| AI Services | OpenAI Embeddings + GPT-4 |
| Caching & Queue | Vercel Redis |

---

## Comparison with Traditional Platforms

| Dimension | Traditional LMS | Sync Learn |
|:----------|:----------------|:-----------|
| **Content Navigation** | Manually scrubbing through long videos | Semantic jump from notes to video |
| **Student Assessment** | Manually created static quizzes | AI-generated quizzes synchronized with knowledge points |
| **Teacher Feedback** | Basic metrics like "Video Completion %" | Heatmaps + AI-summarized learning gaps |
| **Q&A Support** | Forum-based or delayed email responses | Instant AI Q&A with multimodal citations |

---

## Prototype Reference

The platform adopts a left-right split-screen layout, with the video player positioned at the top right and the AI interaction area at the bottom right.

- **Layout**: Three-panel structure — left notes area (anchor highlighting) + top-right video player + bottom-right AI assistant
- **Figma Prototype**: [https://batch-equity-33459089.figma.site](https://batch-equity-33459089.figma.site)

---

## Development Roadmap

The platform will be developed in four phases, evolving from a basic MVP to a fully-featured insight engine. This phased approach ensures core synchronization features are perfected before adding advanced analytics.

| Phase | Focus |
|:------|:------|
| Phase 1 | MVP — Notes upload, video upload, basic playback |
| Phase 2 | Semantic alignment engine (ASR + OCR + Embedding) |
| Phase 3 | AI quiz system & wrong-answer backtracking |
| Phase 4 | Teacher dashboard, heatmaps & AI review briefs |

---

## Start the Program on Codespaces

### Frontend
```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run the application
npm start
```

### Backend
```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```