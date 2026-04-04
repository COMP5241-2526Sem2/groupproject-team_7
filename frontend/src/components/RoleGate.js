import React from 'react';
import { GraduationCap, School } from 'lucide-react';

function RoleGate({ onChoose }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#2a1010] via-[#4b1818] to-[#1a1a2e] px-6 py-10 text-[#FFFBF7]">
      <div className="w-full max-w-4xl rounded-[28px] border border-white/10 bg-white/8 p-8 shadow-[0_24px_80px_rgba(0,0,0,0.35)] backdrop-blur-xl">
        <div className="mb-8 text-center">
          <p className="mb-3 text-sm uppercase tracking-[0.35em] text-[#F5EFE3]/70">
            Sync Learn
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Choose your role
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-sm leading-6 text-[#F5EFE3]/80 sm:text-base">
            Teachers manage courses, resources, and learning analytics. Students open the same
            courses to study slides, watch linked videos, and review knowledge points.
          </p>
          <p className="mx-auto mt-2 max-w-2xl text-xs text-[#F5EFE3]/65 sm:text-sm">
            Student login uses auto-detected student ID from URL parameters (for example: ?sid=3035987654).
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <button
            type="button"
            onClick={() => onChoose('teacher')}
            className="group rounded-[24px] border border-white/12 bg-[#F5EFE3] p-6 text-left text-[#4a1414] shadow-lg transition hover:-translate-y-1 hover:shadow-xl"
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#6B1E1E] text-[#F5EFE3] shadow-md">
              <School className="h-6 w-6" />
            </div>
            <h2 className="text-xl font-semibold">Teacher</h2>
            <p className="mt-2 text-sm leading-6 text-[#5c4343]">
              Manage courses, upload documents, attach video links, and inspect learning analytics.
            </p>
            <div className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-[#6B1E1E]">
              Enter teacher dashboard
            </div>
          </button>

          <button
            type="button"
            onClick={() => onChoose('student')}
            className="group rounded-[24px] border border-white/12 bg-white/10 p-6 text-left text-[#FFFBF7] shadow-lg transition hover:-translate-y-1 hover:shadow-xl"
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#F5EFE3] text-[#6B1E1E] shadow-md">
              <GraduationCap className="h-6 w-6" />
            </div>
            <h2 className="text-xl font-semibold">Student</h2>
            <p className="mt-2 text-sm leading-6 text-[#F5EFE3]/80">
              Open a course, read its slides, watch the linked lecture video, and review generated
              knowledge points and quizzes.
            </p>
            <div className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-[#F5EFE3]">
              Enter learning workspace
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}

export default RoleGate;