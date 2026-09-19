import { ActivityIndicator, Pressable, StyleSheet, Text, type PressableProps } from 'react-native';

import { Colors, Fonts, Spacing } from '@/constants/theme';

export function Button({ label, loading = false, variant = 'primary', ...props }: PressableProps & {
  label: string;
  loading?: boolean;
  variant?: 'primary' | 'secondary';
}) {
  return (
    <Pressable
      {...props}
      accessibilityRole="button"
      disabled={props.disabled || loading}
      style={({ pressed }) => [
        styles.button,
        variant === 'secondary' && styles.secondary,
        pressed && styles.pressed,
        (props.disabled || loading) && styles.disabled,
      ]}>
      {loading ? <ActivityIndicator color={variant === 'primary' ? Colors.light.surface : Colors.light.terracotta} /> : <Text style={[styles.label, variant === 'secondary' && styles.secondaryLabel]}>{label}</Text>}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: 'center',
    backgroundColor: Colors.light.ink,
    borderRadius: 12,
    justifyContent: 'center',
    minHeight: 54,
    paddingHorizontal: Spacing.four,
  },
  secondary: { backgroundColor: Colors.light.surface, borderColor: Colors.light.line, borderWidth: 1 },
  label: { color: Colors.light.surface, fontFamily: Fonts.sans, fontSize: 15, fontWeight: '700' },
  secondaryLabel: { color: Colors.light.ink },
  pressed: { opacity: 0.78 },
  disabled: { opacity: 0.5 },
});
