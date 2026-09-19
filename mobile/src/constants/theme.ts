/**
 * Below are the colors that are used in the app. The colors are defined in the light and dark mode.
 * There are many other ways to style your app. For example, [Nativewind](https://www.nativewind.dev/), [Tamagui](https://tamagui.dev/), [unistyles](https://reactnativeunistyles.vercel.app), etc.
 */

import '@/global.css';

import { Platform } from 'react-native';

export const Colors = {
  light: {
    text: '#282522',
    background: '#F5F0E8',
    backgroundElement: '#EDE3D5',
    backgroundSelected: '#DCC9B5',
    textSecondary: '#716960',
    ink: '#282522',
    muted: '#716960',
    surface: '#FFFCF7',
    line: '#D9CCBC',
    terracotta: '#B95F45',
    error: '#A13E35',
  },
  dark: {
    text: '#FFF8EE',
    background: '#282522',
    backgroundElement: '#3B332D',
    backgroundSelected: '#59483B',
    textSecondary: '#C8B9A9',
    ink: '#FFF8EE',
    muted: '#C8B9A9',
    surface: '#382F29',
    line: '#5D4F43',
    terracotta: '#E28A68',
    error: '#F08B7D',
  },
} as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

export const Fonts = Platform.select({
  ios: {
    /** iOS `UIFontDescriptorSystemDesignDefault` */
    sans: 'system-ui',
    /** iOS `UIFontDescriptorSystemDesignSerif` */
    serif: 'ui-serif',
    /** iOS `UIFontDescriptorSystemDesignRounded` */
    rounded: 'ui-rounded',
    /** iOS `UIFontDescriptorSystemDesignMonospaced` */
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-serif)',
    rounded: 'var(--font-rounded)',
    mono: 'var(--font-mono)',
  },
});

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
export const MaxContentWidth = 800;
