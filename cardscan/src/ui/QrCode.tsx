import { useMemo } from 'react';
import { t } from '../i18n';
import { View } from 'react-native';
import { darkRuns, qrMatrix } from '../core/qr';

/** 순수 View 로 그리는 QR — 별도 네이티브 라이브러리 없이 동작 */
export function QrCode({ value, size = 240 }: { value: string; size?: number }) {
  const matrix = useMemo(() => qrMatrix(value), [value]);
  const quiet = 4; // QR 규격의 바깥 여백(칸)
  const n = matrix.length + quiet * 2;
  const cell = size / n;
  return (
    <View style={{ width: size, height: size, backgroundColor: '#fff' }} accessibilityLabel={t('명함 QR 코드')}>
      {matrix.map((row, r) =>
        darkRuns(row).map(([c, len]) => (
          <View
            key={`${r}-${c}`}
            style={{ position: 'absolute', top: (r + quiet) * cell, left: (c + quiet) * cell, width: len * cell + 0.5, height: cell + 0.5, backgroundColor: '#000' }}
          />
        )),
      )}
    </View>
  );
}
