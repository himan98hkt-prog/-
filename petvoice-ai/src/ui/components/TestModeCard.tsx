import React, { useEffect, useState } from 'react';
import { Alert, StyleSheet, Text, TextInput } from 'react-native';
import { isConfigured } from '../../api';
import { clearTestKey, getTestKey, isTestKeyUsable, maskKey, setTestKey } from '../../api/testKey';
import { useT } from '../../i18n/useT';
import { font, HIT_SIZE, radius, space } from '../theme';
import { useStyles, useTheme, type Theme } from '../useTheme';
import { Button, Card, SectionTitle } from './Basics';

/**
 * 테스트 빌드에서만 나타나는 카드.
 *
 * 서버가 이미 설정돼 있으면 보여 줄 이유가 없다 — 그때는 제품 경로가 정상이다.
 */
export function TestModeCard() {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  const { t } = useT();
  const [input, setInput] = useState('');
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    void getTestKey().then(setSaved);
  }, []);

  if (!isTestKeyUsable() || isConfigured) return null;

  const save = async () => {
    const value = input.trim();
    if (!value) return;
    await setTestKey(value);
    setSaved(value);
    setInput('');
    Alert.alert(t('testMode.savedToast'));
  };

  const clear = async () => {
    await clearTestKey();
    setSaved(null);
    Alert.alert(t('testMode.clearedToast'));
  };

  return (
    <Card style={{ gap: space.md, borderColor: colors.warnLine, backgroundColor: colors.warnSoft }}>
      <SectionTitle>{t('testMode.title')}</SectionTitle>
      <Text style={[font.small, { color: colors.textSoft }]}>{t('testMode.warning')}</Text>

      <Text style={[font.bodyStrong, { color: colors.text }]}>
        {saved ? t('testMode.saved', { masked: maskKey(saved) }) : t('testMode.empty')}
      </Text>

      <TextInput
        accessibilityLabel={t('testMode.placeholder')}
        value={input}
        onChangeText={setInput}
        placeholder={t('testMode.placeholder')}
        placeholderTextColor={colors.textFaint}
        autoCapitalize="none"
        autoCorrect={false}
        secureTextEntry
        style={styles.input}
      />

      <Button label={t('testMode.save')} onPress={() => void save()} disabled={!input.trim()} />
      {saved ? <Button label={t('testMode.clear')} variant="danger" onPress={() => void clear()} /> : null}
    </Card>
  );
}

const makeStyles = ({ colors }: Theme) =>
  StyleSheet.create({
    input: {
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radius.md,
      paddingHorizontal: space.md,
      paddingVertical: space.md,
      minHeight: HIT_SIZE + 4,
      backgroundColor: colors.surface,
      color: colors.text,
      fontSize: 15,
    },
  });
