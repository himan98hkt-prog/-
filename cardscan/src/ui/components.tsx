// 공용 UI — "Ink & Gold" 디자인. 화면은 이 파일과 theme.ts 만 써서 같은 느낌을 낸다.
import Ionicons from '@expo/vector-icons/Ionicons';
import * as Haptics from 'expo-haptics';
import { LinearGradient } from 'expo-linear-gradient';
import { ComponentProps, ReactNode, useRef } from 'react';
import {
  ActivityIndicator, Animated, Platform, Pressable, PressableProps, StyleProp, StyleSheet, Text, TextInput, TextInputProps, View, ViewStyle,
} from 'react-native';
import { CardKind, KIND_LABEL, SyncStatus } from '../core/types';
import { FONT, gradientFor, monogram, RADIUS, shadow, T, type } from './theme';
import { t } from '../i18n';

/** 예전 화면 코드와의 호환용 색 이름 */
export const C = {
  bg: T.bg,
  card: T.surface,
  text: T.text,
  sub: T.sub,
  line: T.line,
  primary: T.primary,
  primarySoft: T.primarySoft,
  ok: T.ok,
  warn: T.warn,
  err: T.err,
  kind: T.kind,
};

export type IconName = ComponentProps<typeof Ionicons>['name'];
export function Icon({ name, size = 20, color = T.text }: { name: IconName; size?: number; color?: string }) {
  return <Ionicons name={name} size={size} color={color} />;
}

/** 가벼운 진동 — 누르는 맛 */
export function tap(kind: 'light' | 'select' | 'success' = 'light') {
  if (Platform.OS === 'web') return;
  if (kind === 'select') Haptics.selectionAsync().catch(() => {});
  else if (kind === 'success') Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
  else Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
}

/** 누르면 살짝 작아졌다 돌아오는 Pressable */
// 바깥(Pressable)이 맡아야 줄 배치가 맞는 스타일 — flex:1 버튼이 옆으로 늘어나도록
const OUTER_KEYS = ['flex', 'flexGrow', 'flexShrink', 'flexBasis', 'alignSelf', 'width', 'minWidth', 'maxWidth', 'margin', 'marginTop', 'marginBottom', 'marginLeft', 'marginRight', 'marginHorizontal', 'marginVertical', 'position', 'top', 'left', 'right', 'bottom', 'zIndex'] as const;

export function PressableScale({ style, children, onPress, disabled, haptic = true, ...rest }: PressableProps & { style?: StyleProp<ViewStyle>; haptic?: boolean; children: ReactNode }) {
  const scale = useRef(new Animated.Value(1)).current;
  const to = (v: number) => Animated.spring(scale, { toValue: v, useNativeDriver: true, speed: 40, bounciness: 6 }).start();
  const flat = { ...((StyleSheet.flatten(style) ?? {}) as object) } as Record<string, unknown>;
  const outer: Record<string, unknown> = {};
  for (const k of OUTER_KEYS) {
    if (k in flat) {
      outer[k] = flat[k];
      delete flat[k];
    }
  }
  const stretch = outer.flex != null || outer.width != null || outer.alignSelf === 'stretch';
  return (
    <Pressable
      {...rest}
      style={outer as ViewStyle}
      disabled={disabled}
      onPressIn={() => to(0.97)}
      onPressOut={() => to(1)}
      onPress={(e) => {
        if (haptic) tap();
        onPress?.(e);
      }}
    >
      <Animated.View style={[flat as ViewStyle, stretch && { flexGrow: 1 }, { transform: [{ scale }] }, disabled ? { opacity: 0.45 } : null]}>{children}</Animated.View>
    </Pressable>
  );
}

export function Button({
  title,
  onPress,
  variant = 'primary',
  icon,
  disabled,
  loading,
  style,
}: {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'danger' | 'gold' | 'dark';
  icon?: IconName;
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const fg = variant === 'secondary' ? T.primary : variant === 'danger' ? T.err : variant === 'gold' ? T.ink : '#fff';
  const content = loading ? (
    <ActivityIndicator color={fg} />
  ) : (
    <View style={s.btnInner}>
      {icon ? <Icon name={icon} size={18} color={fg} /> : null}
      <Text style={[s.btnText, { color: fg }]}>{title}</Text>
    </View>
  );
  const gradient: [string, string] | null =
    variant === 'primary' ? ['#4B6BFF', '#2C46E0'] : variant === 'gold' ? ['#E9CB8C', '#C89B4E'] : variant === 'dark' ? [T.ink3, T.ink] : null;
  return (
    <PressableScale accessibilityRole="button" onPress={onPress} disabled={disabled || loading} style={[s.btn, variant === 'primary' && shadow(1), style]}>
      {gradient ? (
        <LinearGradient colors={gradient} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.btnFill}>
          {content}
        </LinearGradient>
      ) : (
        <View style={[s.btnFill, { backgroundColor: variant === 'danger' ? T.errSoft : T.primarySoft }]}>{content}</View>
      )}
    </PressableScale>
  );
}

/** 둥근 아이콘 버튼 + 아래 글자 (상세 화면 빠른 실행) */
export function ActionButton({ icon, label, onPress, tone = T.primary }: { icon: IconName; label: string; onPress: () => void; tone?: string }) {
  return (
    <PressableScale onPress={onPress} style={s.action}>
      <View style={[s.actionCircle, { backgroundColor: tone + '14' }]}>
        <Icon name={icon} size={22} color={tone} />
      </View>
      <Text style={s.actionLabel}>{label}</Text>
    </PressableScale>
  );
}

/** 회사 색 그라데이션 + 이니셜 — 이 앱의 시그니처 */
export function Avatar({ name, company, size = 48, favorite }: { name: string; company: string; size?: number; favorite?: boolean }) {
  const [a, b] = gradientFor(company || name);
  return (
    <View style={[{ width: size, height: size }, favorite && { padding: 2, borderRadius: size * 0.34, backgroundColor: T.gold }]}>
      <LinearGradient colors={[a, b]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[s.avatar, { borderRadius: size * 0.32 }]}>
        <Text style={[s.avatarText, { fontSize: size * 0.42, lineHeight: size * 0.56 }]}>{monogram(name, company)}</Text>
      </LinearGradient>
    </View>
  );
}

export function KindPicker({ value, onChange, dark }: { value: CardKind; onChange: (k: CardKind) => void; dark?: boolean }) {
  return (
    <View style={[s.segment, dark && { backgroundColor: 'rgba(255,255,255,0.08)' }]}>
      {(Object.keys(KIND_LABEL) as CardKind[]).map((k) => {
        const on = value === k;
        return (
          <Pressable
            key={k}
            accessibilityRole="button"
            accessibilityState={{ selected: on }}
            onPress={() => {
              tap('select');
              onChange(k);
            }}
            style={[s.segItem, on && { backgroundColor: dark ? T.gold : T.kind[k] }]}
          >
            <Text style={[s.segText, dark && { color: 'rgba(255,255,255,0.75)' }, on && { color: dark ? T.ink : '#fff' }]}>{t(KIND_LABEL[k])}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function KindBadge({ kind }: { kind: CardKind }) {
  return (
    <View style={[s.badge, { backgroundColor: T.kind[kind] + '18' }]}>
      <Text style={[s.badgeText, { color: T.kind[kind] }]}>{t(KIND_LABEL[kind])}</Text>
    </View>
  );
}

export function Chip({ label, on, onPress, tone = T.text, icon }: { label: string; on?: boolean; onPress?: () => void; tone?: string; icon?: IconName }) {
  return (
    <Pressable
      onPress={() => {
        tap('select');
        onPress?.();
      }}
      style={[s.chip, on && { backgroundColor: tone, borderColor: tone }]}
    >
      {icon ? <Icon name={icon} size={13} color={on ? '#fff' : tone} /> : null}
      <Text style={[s.chipText, on && { color: '#fff' }]}>{label}</Text>
    </Pressable>
  );
}

export function Field({ label, ...props }: TextInputProps & { label: string }) {
  return (
    <View style={s.field}>
      {label ? <Text style={s.fieldLabel}>{label}</Text> : null}
      <TextInput placeholderTextColor={T.faint} style={[s.input, props.multiline && { minHeight: 64, textAlignVertical: 'top' }]} {...props} />
    </View>
  );
}

export function Section({ title, children, right, icon }: { title: string; children: ReactNode; right?: ReactNode; icon?: IconName }) {
  return (
    <View style={s.section}>
      {title || right ? (
        <View style={s.sectionHead}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 }}>
            {icon ? <Icon name={icon} size={18} color={T.goldDeep} /> : null}
            <Text style={s.sectionTitle}>{title}</Text>
          </View>
          {right}
        </View>
      ) : null}
      {children}
    </View>
  );
}

export function SyncDot({ status }: { status?: SyncStatus }) {
  const color = !status ? T.line : status.state === 'ok' ? T.ok : status.state === 'error' ? T.err : T.warn;
  return <View style={[s.dot, { backgroundColor: color }]} />;
}

export const s = StyleSheet.create({
  btn: { borderRadius: RADIUS.md, minHeight: 52 },
  btnFill: { flex: 1, minHeight: 52, borderRadius: RADIUS.md, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 18 },
  btnInner: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  btnText: { ...type(16, '700'), lineHeight: 22 },
  action: { alignItems: 'center', gap: 6, minWidth: 56 },
  actionCircle: { width: 52, height: 52, borderRadius: 26, alignItems: 'center', justifyContent: 'center' },
  actionLabel: { ...type(12, '600', T.sub) },
  avatar: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontFamily: FONT, color: '#fff', fontWeight: '800' },
  segment: { flexDirection: 'row', backgroundColor: '#ECEEF4', borderRadius: RADIUS.md, padding: 4, gap: 4 },
  segItem: { flex: 1, paddingVertical: 10, borderRadius: 11, alignItems: 'center' },
  segText: { ...type(15, '700'), lineHeight: 20 },
  badge: { borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2 },
  badgeText: { ...type(11, '700'), lineHeight: 15 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 13, paddingVertical: 8, borderRadius: 18, backgroundColor: '#fff', borderWidth: 1, borderColor: T.line },
  chipText: { ...type(13, '600'), lineHeight: 17 },
  field: { marginBottom: 12 },
  fieldLabel: { ...type(13, '600', T.sub), marginBottom: 6 },
  input: {
    fontFamily: FONT,
    backgroundColor: '#F8F9FC',
    borderWidth: 1,
    borderColor: T.line,
    borderRadius: RADIUS.sm + 2,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: T.text,
  },
  section: { backgroundColor: T.surface, borderRadius: RADIUS.lg, padding: 18, marginBottom: 14, ...shadow(1) },
  sectionHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  sectionTitle: { ...type(17, '800') },
  dot: { width: 8, height: 8, borderRadius: 4 },
  muted: { ...type(13, '400', T.sub) },
});
