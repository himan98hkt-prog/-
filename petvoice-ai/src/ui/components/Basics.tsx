import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type ViewStyle } from 'react-native';
import { font, HIT_SIZE, radius, space } from '../theme';
import { useStyles, useTheme, type Theme } from '../useTheme';

export function Card({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  const styles = useStyles(makeStyles);
  const { shadow } = useTheme();
  return <View style={[styles.card, shadow, style]}>{children}</View>;
}

export function SectionTitle({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  return (
    <View style={styles.sectionTitle}>
      <Text accessibilityRole="header" style={[font.h3, { color: colors.text }]}>
        {children}
      </Text>
      {right}
    </View>
  );
}

interface ButtonProps {
  label: string;
  onPress: () => void;
  variant?: 'primary' | 'ghost' | 'danger' | 'pro';
  disabled?: boolean;
  loading?: boolean;
  icon?: React.ReactNode;
  style?: ViewStyle;
}

export function Button({ label, onPress, variant = 'primary', disabled, loading, icon, style }: ButtonProps) {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();

  const tone = {
    primary: { bg: colors.primary, fg: colors.onPrimary, border: 'transparent' },
    ghost: { bg: 'transparent', fg: colors.textSoft, border: colors.border },
    danger: { bg: colors.dangerSoft, fg: colors.danger, border: 'transparent' },
    pro: { bg: colors.pro, fg: colors.onPro, border: 'transparent' },
  }[variant];

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: Boolean(disabled || loading), busy: Boolean(loading) }}
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: tone.bg, borderColor: tone.border, opacity: disabled ? 0.45 : pressed ? 0.85 : 1 },
        style,
      ]}
    >
      {loading ? <ActivityIndicator color={tone.fg} /> : icon}
      <Text style={[font.bodyStrong, { color: tone.fg }]}>{label}</Text>
    </Pressable>
  );
}

export function Chip({
  label,
  selected,
  onPress,
  locked,
}: {
  label: string;
  selected?: boolean;
  onPress: () => void;
  locked?: boolean;
}) {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: Boolean(selected), disabled: false }}
      accessibilityLabel={label}
      onPress={onPress}
      style={[styles.chip, selected && { backgroundColor: colors.primary, borderColor: colors.primary }]}
    >
      <Text style={[font.small, { color: selected ? colors.onPrimary : colors.textSoft }]}>
        {locked ? `🔒 ${label}` : label}
      </Text>
    </Pressable>
  );
}

export function Badge({ text, bg, fg }: { text: string; bg: string; fg: string }) {
  const styles = useStyles(makeStyles);
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <Text style={[font.tiny, { color: fg }]}>{text}</Text>
    </View>
  );
}

export function Empty({ emoji, title, desc }: { emoji: string; title: string; desc?: string }) {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  return (
    <View style={styles.empty}>
      <Text style={{ fontSize: 44 }} accessibilityElementsHidden importantForAccessibility="no">
        {emoji}
      </Text>
      <Text accessibilityRole="header" style={[font.h3, { color: colors.text, marginTop: space.md, textAlign: 'center' }]}>
        {title}
      </Text>
      {desc ? (
        <Text style={[font.small, { color: colors.textSoft, textAlign: 'center', marginTop: space.xs }]}>{desc}</Text>
      ) : null}
    </View>
  );
}

/** 켜고 끄는 설정 한 줄 */
export function ToggleRow({
  label,
  desc,
  value,
  onChange,
  disabled,
}: {
  label: string;
  desc?: string;
  value: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
}) {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityLabel={label}
      accessibilityHint={desc}
      accessibilityState={{ checked: value, disabled: Boolean(disabled) }}
      onPress={() => onChange(!value)}
      disabled={disabled}
      style={[styles.toggleRow, { opacity: disabled ? 0.45 : 1 }]}
    >
      <View style={{ flex: 1 }}>
        <Text style={[font.body, { color: colors.text }]}>{label}</Text>
        {desc ? <Text style={[font.small, { color: colors.textSoft }]}>{desc}</Text> : null}
      </View>
      <View style={[styles.track, value && { backgroundColor: colors.primary }]}>
        <View style={[styles.knob, value && { alignSelf: 'flex-end' }]} />
      </View>
    </Pressable>
  );
}

const makeStyles = ({ colors }: Theme) =>
  StyleSheet.create({
    card: {
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      padding: space.lg,
      borderWidth: 1,
      borderColor: colors.border,
    },
    sectionTitle: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: space.sm,
      marginBottom: space.sm,
    },
    button: {
      minHeight: HIT_SIZE + 8,
      borderRadius: radius.md,
      borderWidth: 1,
      paddingHorizontal: space.lg,
      paddingVertical: space.md,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: space.sm,
    },
    chip: {
      minHeight: HIT_SIZE,
      justifyContent: 'center',
      paddingHorizontal: space.md,
      paddingVertical: space.sm,
      borderRadius: radius.pill,
      backgroundColor: colors.surfaceAlt,
      borderWidth: 1,
      borderColor: colors.border,
    },
    badge: {
      paddingHorizontal: space.sm,
      paddingVertical: 3,
      borderRadius: radius.pill,
      alignSelf: 'flex-start',
    },
    empty: { alignItems: 'center', paddingVertical: space.xxl, paddingHorizontal: space.xl },
    toggleRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: space.md,
      minHeight: HIT_SIZE,
      paddingVertical: space.sm,
    },
    track: {
      width: 50,
      height: 30,
      borderRadius: radius.pill,
      backgroundColor: colors.border,
      padding: 3,
      justifyContent: 'center',
    },
    knob: { width: 24, height: 24, borderRadius: 12, backgroundColor: colors.surface },
  });
