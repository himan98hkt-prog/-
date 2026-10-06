import { ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, TextInputProps, View, ViewStyle } from 'react-native';
import { CardKind, KIND_LABEL, SyncStatus } from '../core/types';

export const C = {
  bg: '#F5F6F8',
  card: '#FFFFFF',
  text: '#1B1F24',
  sub: '#6B7280',
  line: '#E5E7EB',
  primary: '#1F6FEB',
  primarySoft: '#E8F0FE',
  ok: '#16A34A',
  warn: '#D97706',
  err: '#DC2626',
  kind: { customer: '#1F6FEB', partner: '#7C3AED', other: '#6B7280' } as Record<CardKind, string>,
};

export function Button({
  title,
  onPress,
  variant = 'primary',
  disabled,
  loading,
  style,
}: {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
  disabled?: boolean;
  loading?: boolean;
  style?: ViewStyle;
}) {
  const bg = variant === 'primary' ? C.primary : variant === 'danger' ? '#FEE2E2' : C.primarySoft;
  const fg = variant === 'primary' ? '#fff' : variant === 'danger' ? C.err : C.primary;
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [s.btn, { backgroundColor: bg, opacity: disabled ? 0.4 : pressed ? 0.8 : 1 }, style]}
    >
      {loading ? <ActivityIndicator color={fg} /> : <Text style={[s.btnText, { color: fg }]}>{title}</Text>}
    </Pressable>
  );
}

export function KindPicker({ value, onChange }: { value: CardKind; onChange: (k: CardKind) => void }) {
  return (
    <View style={s.segment}>
      {(Object.keys(KIND_LABEL) as CardKind[]).map((k) => (
        <Pressable
          key={k}
          accessibilityRole="button"
          accessibilityState={{ selected: value === k }}
          onPress={() => onChange(k)}
          style={[s.segItem, value === k && { backgroundColor: C.kind[k] }]}
        >
          <Text style={[s.segText, value === k && { color: '#fff' }]}>{KIND_LABEL[k]}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export function KindBadge({ kind }: { kind: CardKind }) {
  return (
    <View style={[s.badge, { borderColor: C.kind[kind] }]}>
      <Text style={[s.badgeText, { color: C.kind[kind] }]}>{KIND_LABEL[kind]}</Text>
    </View>
  );
}

export function Field({ label, ...props }: TextInputProps & { label: string }) {
  return (
    <View style={s.field}>
      <Text style={s.fieldLabel}>{label}</Text>
      <TextInput placeholderTextColor="#9CA3AF" style={[s.input, props.multiline && { minHeight: 64 }]} {...props} />
    </View>
  );
}

export function Section({ title, children, right }: { title: string; children: ReactNode; right?: ReactNode }) {
  return (
    <View style={s.section}>
      <View style={s.sectionHead}>
        <Text style={s.sectionTitle}>{title}</Text>
        {right}
      </View>
      {children}
    </View>
  );
}

export function SyncDot({ status }: { status?: SyncStatus }) {
  const color = !status ? C.line : status.state === 'ok' ? C.ok : status.state === 'error' ? C.err : C.warn;
  return <View style={[s.dot, { backgroundColor: color }]} />;
}

export const s = StyleSheet.create({
  btn: { minHeight: 50, borderRadius: 12, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 16 },
  btnText: { fontSize: 16, fontWeight: '700' },
  segment: { flexDirection: 'row', backgroundColor: '#EEF0F3', borderRadius: 12, padding: 4, gap: 4 },
  segItem: { flex: 1, paddingVertical: 10, borderRadius: 9, alignItems: 'center' },
  segText: { fontSize: 15, fontWeight: '600', color: C.text },
  badge: { borderWidth: 1, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1 },
  badgeText: { fontSize: 11, fontWeight: '700' },
  field: { marginBottom: 10 },
  fieldLabel: { fontSize: 13, color: C.sub, marginBottom: 4 },
  input: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: C.line,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
    color: C.text,
  },
  section: { backgroundColor: C.card, borderRadius: 14, padding: 16, marginBottom: 12 },
  sectionHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: C.text },
  dot: { width: 8, height: 8, borderRadius: 4 },
  muted: { color: C.sub, fontSize: 13 },
});
