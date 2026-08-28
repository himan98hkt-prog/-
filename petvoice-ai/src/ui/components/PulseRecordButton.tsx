import React, { useEffect, useRef } from 'react';
import { Animated, Easing, Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, font, space } from '../theme';

interface Props {
  recording: boolean;
  disabled?: boolean;
  /** 남은 녹음 시간(초). 녹음 중이 아니면 undefined */
  secondsLeft?: number;
  onPress: () => void;
}

/**
 * 원형 펄스 애니메이션이 적용된 녹음 버튼.
 * 녹음 중에는 링이 계속 퍼져 나가 "지금 듣고 있다"는 걸 보여 준다.
 */
export function PulseRecordButton({ recording, disabled, secondsLeft, onPress }: Props) {
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
    transform: [
      {
        scale: pulse.interpolate({
          inputRange: [0, 1],
          outputRange: [1, 1.9 + delay],
        }),
      },
    ],
    opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.35 - delay * 0.4, 0] }),
  });

  return (
    <View style={styles.wrap}>
      {recording ? (
        <>
          <Animated.View style={[styles.ring, ringStyle(0)]} pointerEvents="none" />
          <Animated.View style={[styles.ring, ringStyle(0.25)]} pointerEvents="none" />
        </>
      ) : null}

      <Pressable
        accessibilityRole="button"
        accessibilityLabel={recording ? '녹음 중지' : '3초 소리 녹음 시작'}
        accessibilityState={{ disabled: Boolean(disabled), busy: recording }}
        onPress={onPress}
        disabled={disabled}
        style={({ pressed }) => [
          styles.button,
          recording && styles.buttonRecording,
          { opacity: disabled ? 0.4 : pressed ? 0.9 : 1 },
        ]}
      >
        <Text style={styles.icon}>{recording ? '■' : '🎙'}</Text>
        <Text style={[font.tiny, styles.label]}>
          {recording ? `${secondsLeft ?? 0}초` : '3초 녹음'}
        </Text>
      </Pressable>
    </View>
  );
}

const SIZE = 132;

const styles = StyleSheet.create({
  wrap: { width: SIZE * 2, height: SIZE, alignItems: 'center', justifyContent: 'center', alignSelf: 'center' },
  ring: {
    position: 'absolute',
    width: SIZE,
    height: SIZE,
    borderRadius: SIZE / 2,
    backgroundColor: colors.primary,
  },
  button: {
    width: SIZE,
    height: SIZE,
    borderRadius: SIZE / 2,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.xs,
  },
  buttonRecording: { backgroundColor: colors.danger },
  icon: { fontSize: 38, color: '#FFFFFF' },
  label: { color: '#FFFFFF', letterSpacing: 0.5 },
});
