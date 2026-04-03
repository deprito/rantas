'use client';

import { Moon, Sun, Monitor } from 'lucide-react';
import { useTheme } from './theme-provider';
import { Button } from './ui/button';

const themes: Array<'light' | 'dark' | 'system'> = ['light', 'dark', 'system'];

const themeIcons = {
  light: Sun,
  dark: Moon,
  system: Monitor,
};

const themeLabels = {
  light: 'Light Mode',
  dark: 'Dark Mode',
  system: 'System Theme',
};

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  const cycleTheme = () => {
    const currentIndex = themes.indexOf(theme);
    const nextIndex = (currentIndex + 1) % themes.length;
    setTheme(themes[nextIndex]);
  };

  const Icon = themeIcons[theme];

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={cycleTheme}
      className="w-full justify-start gap-2"
      title={themeLabels[theme]}
    >
      <Icon className="h-4 w-4" />
      <span>{themeLabels[theme]}</span>
    </Button>
  );
}
