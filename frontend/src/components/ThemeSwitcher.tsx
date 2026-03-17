import { useTheme } from '../contexts/ThemeContext';
import { Button } from '@/components/ui/button';
import { Moon, Sun } from 'lucide-react';

export const ThemeSwitcher = () => {
  const { theme, toggleTheme } = useTheme();

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      className="relative h-8 w-8"
      aria-label="Toggle theme"
    >
      <Sun
        className={`h-4 w-4 text-amber-500 transition-all duration-300 ${
          theme === 'dark' ? 'rotate-0 scale-100' : 'rotate-90 scale-0'
        }`}
      />
      <Moon
        className={`absolute h-4 w-4 text-slate-700 dark:text-slate-400 transition-all duration-300 ${
          theme === 'light' ? 'rotate-0 scale-100' : '-rotate-90 scale-0'
        }`}
      />
    </Button>
  );
};
