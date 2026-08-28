import React, { useEffect, useRef } from 'react';
import { Animated, Easing, Pressable, StyleSheet, Text, View } from 'react-native';
import { font, space } from '../theme';
import { useTheme } from '../useTheme';

interface Props {
  recording: boolean;
  disabled?: boolean;
  /** 남은 녹음 시간(초). 녹음 중이 아니면 undefined */
  secondsLeft?: number;
  /** 버튼 안에 쓰는 글자 (녹음 전) */
  idleLabel: string;
  /** 스크린리더가 읽을 문구 */
  a11yLabel: string;
  onPress: () => void;
}

/**
 * 원형 펄스 애니메이션이 적용된 녹음 버튼.
 * 녹음 중에는 링이 계속 퍼져 나가 "지금 듣고 있다"는 걸 보여 준다.
 */
export function PulseRecordButton({ recording, disabled, secondsLeft, idleLabel, a11yLabel, onPress }: Props) {
  const { colors } = useTheme();
  const pulse = useRef(new Animated.Value(0)).current;
  const loopRef = useRef<Animated.CompositeAnimation | null>(null);

  useEffect(() => {
    if (recording) {
      pulse.setValue(0);
      loopRef.current = Animated.loop(
        Animated.timing(pulse, {
          toValue: 1,
          duration: 1400,
          easing: Easing.out(Easing.ease),
          useNativeDriver: true,
        }),
      );
      loopRef.current.start();
    } else {
      loopRef.current?.stop();
      pulse.setValue(0);
    }
    return () => loopRef.current?.stop();
  }, [recording, pulse]);

  const ringStyle = (delay: number) => ({
    transform: [{ scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.9 + delay] }) }],
    opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.35 - delay * 0.4, 0] }),
  });

  return (
    <View style={styles.wrap}>
      {recording ? (
        <>
          <Animated.View
            style={[styles.ring, { backgroundColor: colors.primaryVivid }, ringStyle(0)]}
            pointerEvents="none"
          />
          <Animated.View
            style={[styles.ring, { backgroundColor: colors.primaryVivid }, ringStyle(0.25)]}
            pointerEvents="none"
          />
        </>
      ) : null}

      <Pressable
        accessibilityRole="button"
        accessibilityLabel={a11yLabel}
        accessibilityState={{ disabled: Boolean(disabled), busy: recording }}
        onPress={onPress}
        disabled={disabled}
        style={({ pressed }) => [
          styles.button,
          { backgroundColor: recording ? colors.danger : colors.primary },
          { opacity: disabled ? 0.4 : pressed ? 0.9 : 1 },
        ]}
      >
        <Text style={[styles.icon, { color: colors.onPrimary }]}>{recording ? '■' : '🎙'}</Text>
        <Text style={[font.tiny, styles.label, { color: colors.onPrimary }]}>
          {recording ? `${secondsLeft ?? 0}` : idleLabel}
        </Text>
      </Pressable>
    </View>
  );
}

const SIZE = 132;

const styles = StyleSheet.create({
  wrap: { width: SIZE * 2, height: SIZE, alignItems: 'center', justifyContent: 'center', alignSelf: 'center' },
  ring: { position: 'absolute', width: SIZE, height: SIZE, borderRadius: SIZE / 2 },
  button: {
    width: SIZE,
    height: SIZE,
    borderRadius: SIZE / 2,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.xs,
  },
  icon: { fontSize: 38 },
  label: { letterSpacing: 0.5, textAlign: 'center', paddingHorizontal: space.sm },
});
