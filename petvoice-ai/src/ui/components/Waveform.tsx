import React from 'react';
import { StyleSheet, View } from 'react-native';
import { normalizeLevels } from '../../core/audio';
import { radius, space } from '../theme';
import { useTheme } from '../useTheme';

/**
 * 녹음할 때 측정해 둔 음량으로 그리는 파형.
 * 실제 오디오를 디코딩하지 않고 미터링 값만 쓰기 때문에 가볍다.
 */
export function Waveform({ levels, active }: { levels: number[]; active?: boolean }) {
  const { colors } = useTheme();
  const bars = normalizeLevels(levels, 40);
  if (bars.length === 0) return null;

  return (
    <View style={styles.row} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      {bars.map((value, index) => (
        <View
          key={index}
          style={[
            styles.bar,
            {
              height: `${Math.max(8, value * 100)}%`,
              backgroundColor: active ? colors.primaryVivid : colors.border,
            },
          ]}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    height: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    paddingHorizontal: space.xs,
  },
  bar: { flex: 1, borderRadius: radius.pill, minHeight: 3 },
});
