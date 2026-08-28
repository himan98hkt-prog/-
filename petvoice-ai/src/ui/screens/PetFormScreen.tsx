import React, { useState } from 'react';
import { Alert, Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { PET_LABEL } from '../../core/emotions';
import { FREE_PET_LIMIT, canAddPet } from '../../core/quota';
import type { PetType } from '../../core/types';
import { usePetStore } from '../../store/usePetStore';
import { Button, Card, Chip } from '../components/Basics';
import { pickPhoto } from '../media';
import { useNavigation } from '../navigation';
import { colors, font, radius, space } from '../theme';

/** 반려동물 등록·수정 */
export function PetFormScreen() {
  const nav = useNavigation();
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
      Alert.alert('이름을 알려 주세요', '분석 결과의 말풍선에 이름이 쓰여요.');
      return;
    }
    const ageMonths = age.trim() ? Number(age.trim()) : undefined;
    if (ageMonths != null && (!Number.isFinite(ageMonths) || ageMonths < 0 || ageMonths > 400)) {
      Alert.alert('나이를 확인해 주세요', '개월 수로 입력해 주세요. (예: 18)');
      return;
    }

    const payload = { name: trimmed, type, breed: breed.trim() || undefined, ageMonths, photoUri };

    if (existing) {
      updatePet(existing.id, payload);
      nav.back();
      return;
    }
    if (!canAddPet(pets.length, subscription)) {
      Alert.alert(
        '무료로는 한 마리까지예요',
        `프로로 업그레이드하면 여러 마리를 각각 기록할 수 있어요. (무료 ${FREE_PET_LIMIT}마리)`,
        [
          { text: '닫기', style: 'cancel' },
          { text: '프로 보기', onPress: () => nav.navigate('paywall') },
        ],
      );
      return;
    }
    addPet(payload);
    nav.back();
  };

  return (
    <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
      <Text style={font.h1}>{existing ? '프로필 수정' : '반려동물 등록'}</Text>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel="사진 고르기"
        onPress={async () => {
          const uri = await pickPhoto();
          if (uri) setPhotoUri(uri);
        }}
        style={styles.photo}
      >
        {photoUri ? (
          <Image source={{ uri: photoUri }} style={styles.photoImg} />
        ) : (
          <>
            <Text style={{ fontSize: 34 }}>📷</Text>
            <Text style={[font.tiny, { color: colors.textSoft }]}>사진 추가</Text>
          </>
        )}
      </Pressable>

      <Card style={{ gap: space.lg }}>
        <View style={{ gap: space.sm }}>
          <Text style={font.bodyStrong}>어떤 아이인가요?</Text>
          <View style={{ flexDirection: 'row', gap: space.sm }}>
            {(['DOG', 'CAT'] as PetType[]).map((t) => (
              <Chip key={t} label={PET_LABEL[t]} selected={type === t} onPress={() => setType(t)} />
            ))}
          </View>
        </View>

        <Field label="이름" value={name} onChange={setName} placeholder="예: 초코" />
        <Field label="견종 / 묘종 (선택)" value={breed} onChange={setBreed} placeholder="예: 포메라니안" />
        <Field label="나이 (개월, 선택)" value={age} onChange={setAge} placeholder="예: 18" keyboardType="number-pad" />
      </Card>

      <Button label={existing ? '수정 저장' : '등록하기'} onPress={save} />
      <Button label="취소" variant="ghost" onPress={nav.back} />
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
  return (
    <View style={{ gap: space.xs }}>
      <Text style={font.bodyStrong}>{label}</Text>
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

const styles = StyleSheet.create({
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
    minHeight: 48,
    backgroundColor: colors.surface,
    color: colors.text,
    fontSize: 15,
  },
});
