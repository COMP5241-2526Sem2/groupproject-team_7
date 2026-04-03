import React from 'react';
import {
  Home,
  GraduationCap,
  History,
  Library,
  LayoutDashboard,
} from 'lucide-react';
import clsx from 'clsx';

function SideNav({ view, onViewChange, onFocusCourses, onOpenAiTab }) {
  const items = [
    {
      id: 'home',
      icon: Home,
      label: 'Home',
      onClick: () => onViewChange('learn'),
      active: view === 'learn',
    },
    {
      id: 'dashboard',
      icon: LayoutDashboard,
      label: 'Instructor Dashboard',
      onClick: () => onViewChange('dashboard'),
      active: view === 'dashboard',
    },
    {
      id: 'courses',
      icon: GraduationCap,
      label: 'Courses',
      onClick: () => onFocusCourses?.(),
      active: false,
    },
    {
      id: 'history',
      icon: History,
      label: 'History',
      onClick: () => {},
      active: false,
    },
    {
      id: 'library',
      icon: Library,
      label: 'AI Library',
      onClick: () => onOpenAiTab?.(),
      active: false,
    },
  ];

  return (
    <nav
      className="flex w-16 shrink-0 flex-col items-center gap-3 border-r border-red-950/40 bg-gradient-to-b from-[#6B1E1E] via-[#5c1a1a] to-[#4a1414] py-5 shadow-[4px_0_32px_rgba(74,20,20,0.2)]"
      aria-label="Main navigation"
    >
      <div className="mb-1 flex h-10 w-10 items-center justify-center rounded-inner bg-[#F5EFE3] text-xs font-bold text-[#6B1E1E] shadow-md ring-1 ring-white/20">
        SL
      </div>
      {items.map(({ id, icon: Icon, label, onClick, active }) => (
        <button
          key={id}
          type="button"
          title={label}
          onClick={onClick}
          className={clsx(
            'flex h-11 w-11 items-center justify-center rounded-control border transition-all duration-200',
            active
              ? 'border-[#F5EFE3]/35 bg-white/15 text-[#F5EFE3] shadow-inner'
              : 'border-transparent text-red-100/75 hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/10 hover:text-[#FFFBF7]'
          )}
        >
          <Icon className="h-5 w-5" strokeWidth={1.75} />
        </button>
      ))}
    </nav>
  );
}

export default SideNav;
