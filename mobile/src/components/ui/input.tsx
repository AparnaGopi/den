import { StyleSheet, Text, TextInput, type TextInputProps, View } from 'react-native';

import { Colors, Fonts, Spacing } from '@/constants/theme';

export function Input({ label, error, ...props }: TextInputProps & { label: string; error?: string }) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        {...props}
        placeholderTextColor={Colors.light.muted}
        style={[styles.input, error && styles.inputError]}
      />
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  field: { gap: Spacing.one },
  label: { color: Colors.light.ink, fontFamily: Fonts.sans, fontSize: 14, fontWeight: '700' },
  input: {
    backgroundColor: Colors.light.surface,
    borderColor: Colors.light.line,
    borderRadius: 12,
    borderWidth: 1,
    color: Colors.light.ink,
    fontFamily: Fonts.sans,
    fontSize: 16,
    minHeight: 54,
    paddingHorizontal: Spacing.three,
  },
  inputError: { borderColor: Colors.light.error },
  error: { color: Colors.light.error, fontFamily: Fonts.sans, fontSize: 13 },
});
