import React, { useState } from 'react';
import { Alert, Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { PET_LABEL_KEY } from '../../core/emotions';
import { FREE_PET_LIMIT, canAddPet } from '../../core/quota';
import type { PetType } from '../../core/types';
import { useT } from '../../i18n/useT';
import { usePetStore } from '../../store/usePetStore';
import { Button, Card, Chip } from '../components/Basics';
import { pickPhoto } from '../media';
import { useNavigation } from '../navigation';
import { font, HIT_SIZE, radius, space } from '../theme';
import { useStyles, useTheme, type Theme } from '../useTheme';

/** 반려동물 등록·수정 */
export function PetFormScreen() {
  const nav = useNavigation();
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  const tr = useT();
  const { t } = tr;
  const editingId = nav.current.params?.petId as string | undefined;

  const pets = usePetStore((s) => s.pets);
  const subscription = usePetStore((s) => s.subscription);
  const addPet = usePetStore((s) => s.addPet);
  const updatePet = usePetStore((s) => s.updatePet);

  const existing = pets.find((p) => p.id === editingId);
  const [name, setName] = useState(existing?.name ?? '');
  const [type, setType] = useState<PetType>(existing?.type ?? 'DOG');
  const [breed, setBreed] = useState(existing?.breed ?? '');
  const [age, setAge] = useState(existing?.ageMonths != null ? String(existing.ageMonths) : '');
  const [photoUri, setPhotoUri] = useState(existing?.photoUri);

  const save = () => {
    const trimmed = name.trim();
    if (!trimmed) {
      Alert.alert(t('petForm.nameRequired'), t('petForm.nameRequiredDesc'));
      return;
    }
    const ageMonths = age.trim() ? Number(age.trim()) : undefined;
    if (ageMonths != null && (!Number.isFinite(ageMonths) || ageMonths < 0 || ageMonths > 400)) {
      Alert.alert(t('petForm.ageInvalid'), t('petForm.ageInvalidDesc'));
      return;
    }

    const payload = { name: trimmed, type, breed: breed.trim() || undefined, ageMonths, photoUri };

    if (existing) {
      updatePet(existing.id, payload);
      nav.back();
      return;
    }
    if (!canAddPet(pets.length, subscription)) {
      Alert.alert(t('petForm.limitTitle'), t('petForm.limitDesc', { limit: FREE_PET_LIMIT }), [
        { text: t('common.close'), style: 'cancel' },
        { text: t('petForm.viewPro'), onPress: () => nav.navigate('paywall') },
      ]);
      return;
    }
    addPet(payload);
    nav.back();
  };

  return (
    <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
      <Text accessibilityRole="header" style={[font.h1, { color: colors.text }]}>
        {t(existing ? 'petForm.titleEdit' : 'petForm.titleNew')}
      </Text>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t('petForm.photoA11y')}
        onPress={async () => {
          const uri = await pickPhoto(tr);
          if (uri) setPhotoUri(uri);
        }}
        style={styles.photo}
      >
        {photoUri ? (
          <Image source={{ uri: photoUri }} style={styles.photoImg} accessibilityIgnoresInvertColors />
        ) : (
          <>
            <Text style={{ fontSize: 34 }}>📷</Text>
            <Text style={[font.tiny, { color: colors.textSoft }]}>{t('petForm.photoAdd')}</Text>
          </>
        )}
      </Pressable>

      <Card style={{ gap: space.lg }}>
        <View style={{ gap: space.sm }}>
          <Text style={[font.bodyStrong, { color: colors.text }]}>{t('petForm.which')}</Text>
          <View style={{ flexDirection: 'row', gap: space.sm }}>
            {(['DOG', 'CAT'] as PetType[]).map((value) => (
              <Chip
                key={value}
                label={t(PET_LABEL_KEY[value])}
                selected={type === value}
                onPress={() => setType(value)}
              />
            ))}
          </View>
        </View>

        <Field
          label={t('petForm.name')}
          value={name}
          onChange={setName}
          placeholder={t('petForm.namePlaceholder')}
        />
        <Field
          label={t('petForm.breed')}
          value={breed}
          onChange={setBreed}
          placeholder={t('petForm.breedPlaceholder')}
        />
        <Field
          label={t('petForm.age')}
          value={age}
          onChange={setAge}
          placeholder={t('petForm.agePlaceholder')}
          keyboardType="number-pad"
        />
      </Card>

      <Button label={t(existing ? 'petForm.saveEdit' : 'petForm.save')} onPress={save} />
      <Button label={t('common.cancel')} variant="ghost" onPress={nav.back} />
    </ScrollView>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  keyboardType,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  keyboardType?: 'default' | 'number-pad';
}) {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  return (
    <View style={{ gap: space.xs }}>
      <Text style={[font.bodyStrong, { color: colors.text }]}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor={colors.textFaint}
        keyboardType={keyboardType ?? 'default'}
        style={styles.input}
      />
    </View>
  );
}

const makeStyles = ({ colors }: Theme) =>
  StyleSheet.create({
    page: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
    photo: {
      alignSelf: 'center',
      width: 120,
      height: 120,
      borderRadius: 60,
      backgroundColor: colors.surfaceAlt,
      borderWidth: 1,
      borderColor: colors.border,
      alignItems: 'center',
      justifyContent: 'center',
      gap: space.xs,
      overflow: 'hidden',
    },
    photoImg: { width: '100%', height: '100%' },
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
